import os
import re
from datetime import datetime
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import json
import base64
from bs4 import BeautifulSoup
from flask_migrate import Migrate

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///backup_status.db'
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Database Model
class BackupStatus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    server = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)
    subject = db.Column(db.String(200))
    body = db.Column(db.Text)

def get_gmail_service():
    try:
        print("Attempting to get Gmail service...")
        # Load credentials from gmail_token.json
        with open('gmail_token.json', 'r') as token_file:
            creds_data = json.load(token_file)
        
        creds = Credentials.from_authorized_user_info(creds_data)
        
        # Refresh the token if necessary
        if not creds.valid:
            print("Token invalid, attempting refresh...")
            if creds.refresh_token:
                creds.refresh(Request())
                # Save the refreshed credentials
                with open('gmail_token.json', 'w') as token_file:
                    token_data = {
                        'token': creds.token,
                        'refresh_token': creds.refresh_token,
                        'token_uri': creds.token_uri,
                        'client_id': creds.client_id,
                        'client_secret': creds.client_secret,
                        'scopes': creds.scopes
                    }
                    json.dump(token_data, token_file)
                print("Token refreshed successfully")
            else:
                raise Exception("No refresh token available")
        
        # Create Gmail API service
        service = build('gmail', 'v1', credentials=creds)
        print("Gmail service created successfully")
        return service
    except Exception as e:
        print(f"Error getting Gmail service: {str(e)}")
        return None

def parse_backup_status(body):
    print(f"\nParsing email body for backup statuses...")
    print(f"Body preview: {body[:200]}...")
    
    # Updated pattern to match the HTML format:
    # <span style="font-weight: bold">ServerName</span> <span style="font-size:10px">(ServerID)</span>
    # <div title="Date Time" ...>Status</div>
    pattern = re.compile(
        r'<span style="font-weight: bold">([^<]+)</span>\s*<span style="font-size:10px">\(([^\)]+)\)</span>.*?<div title="(\d{2}\s+\w{3}\s+\d{4}\s+\d{2}:\d{2})".*?<span[^>]*>(\w+)</span>',
        re.DOTALL
    )
    
    results = []
    matches = list(pattern.finditer(body))
    print(f"Found {len(matches)} backup status entries")
    
    for match in matches:
        server_name = match.group(1).strip()
        server_id = match.group(2).strip()
        dt_str = match.group(3).strip()
        status = match.group(4).strip()
        
        print(f"Raw date string from email: {dt_str}")
        
        try:
            # Convert the timestamp string to a Python datetime object
            timestamp = datetime.strptime(dt_str, "%d %b %Y %H:%M")
        except Exception as e:
            print(f"Error parsing date '{dt_str}': {str(e)}")
            timestamp = datetime.now()
        
        result = {
            'server': f"{server_name} ({server_id})",
            'status': 'successful' if status.lower() == 'success' else 'unsuccessful',
            'timestamp': timestamp
        }
        print(f"Parsed status: {result}")
        results.append(result)
    
    return results

def get_body_from_parts(parts):
    body = ""
    html_body = ""
    for part in parts:
        if part['mimeType'] == 'text/plain':
            if 'data' in part['body']:
                try:
                    body += base64.urlsafe_b64decode(part['body']['data']).decode()
                except Exception as e:
                    print(f"Error decoding part: {e}")
        elif part['mimeType'] == 'text/html':
            if 'data' in part['body']:
                try:
                    html_body += base64.urlsafe_b64decode(part['body']['data']).decode()
                except Exception as e:
                    print(f"Error decoding HTML part: {e}")
        elif 'parts' in part:
            sub_body, sub_html = get_body_from_parts(part['parts'])
            body += sub_body
            html_body += sub_html
    return body, html_body

def check_email():
    try:
        print("\nStarting email check...")
        service = get_gmail_service()
        if not service:
            print("Failed to get Gmail service")
            return

        # Get recent messages
        print("Fetching recent messages...")
        results = service.users().messages().list(userId='me', maxResults=50).execute()
        messages = results.get('messages', [])
        print(f"Found {len(messages)} recent messages")
        
        if not messages:
            print("No messages found")
            return

        with app.app_context():
            for message in messages:
                print(f"\nProcessing message {message['id']}...")
                # Get full message details
                msg = service.users().messages().get(userId='me', id=message['id'], format='full').execute()
                
                # Get headers
                headers = msg['payload']['headers']
                subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No subject')
                date_header = next((h['value'] for h in headers if h['name'].lower() == 'date'), None)
                print(f"Subject: {subject}")
                print(f"Date: {date_header}")
                
                # Parse the email timestamp
                if date_header:
                    try:
                        from email.utils import parsedate_to_datetime
                        email_timestamp = parsedate_to_datetime(date_header)
                    except Exception as e:
                        print(f"Error parsing date '{date_header}': {str(e)}")
                        email_timestamp = datetime.now()
                else:
                    email_timestamp = datetime.now()
                
                # Get message body
                body = ""
                html_body = ""
                if 'parts' in msg['payload']:
                    body, html_body = get_body_from_parts(msg['payload']['parts'])
                elif 'body' in msg['payload'] and 'data' in msg['payload']['body']:
                    try:
                        body = base64.urlsafe_b64decode(msg['payload']['body']['data']).decode()
                    except Exception as e:
                        print(f"Error decoding body: {e}")
                # If no plain text, try HTML
                if not body and html_body:
                    print("No plain text body found, using HTML body.")
                    soup = BeautifulSoup(html_body, 'html.parser')
                    body = soup.get_text(separator='\n')
                if not body:
                    print("No email body found, skipping...")
                    continue
                # Print the subject and a snippet of the body for each email
                print(f"Email subject: {subject}")
                print(f"Email body snippet: {body[:300]}\n{'-'*40}")
                # Print the full plain text body for the first email
                if message == messages[0]:
                    print("Full plain text body for the first email:")
                    print(body)
                
                # Parse for server statuses
                statuses = parse_backup_status(body)
                print(f"Found {len(statuses)} backup statuses in email")
                
                for s in statuses:
                    # Only add if this is the latest for this server
                    existing = BackupStatus.query.filter_by(
                        server=s['server'],
                        timestamp=s['timestamp']
                    ).first()
                    
                    if not existing:
                        print(f"Adding new status for {s['server']}")
                        new_status = BackupStatus(
                            server=s['server'],
                            status=s['status'],
                            timestamp=s['timestamp'],
                            subject=subject,
                            body=body
                        )
                        db.session.add(new_status)
                        print(f"Added status: Server={s['server']}, Status={s['status']}, Time={s['timestamp']}")
                    else:
                        print(f"Status already exists for {s['server']}")
            
            db.session.commit()
            print("Database updated successfully")
            
    except Exception as e:
        print(f"Error checking email: {str(e)}")
        import traceback
        print(traceback.format_exc())

@app.route('/')
def index():
    print("\nRendering index page...")
    # Subquery to get the latest timestamp for each server
    subquery = db.session.query(
        BackupStatus.server,
        db.func.max(BackupStatus.timestamp).label('max_time')
    ).group_by(BackupStatus.server).subquery()

    # Join to get the full status row for each server's latest backup
    latest_statuses = db.session.query(BackupStatus).join(
        subquery,
        (BackupStatus.server == subquery.c.server) & (BackupStatus.timestamp == subquery.c.max_time)
    ).order_by(BackupStatus.server).all()

    # Group statuses by server
    grouped_statuses = {}
    for status in latest_statuses:
        server = status.server
        if server not in grouped_statuses:
            grouped_statuses[server] = []
        grouped_statuses[server].append({
            'status': status.status,
            'timestamp': status.timestamp.strftime('%d/%m/%Y %H:%M'),
            'subject': status.subject,
            'body': status.body
        })

    print(f"Found {len(latest_statuses)} latest statuses")
    return render_template('index.html', statuses=grouped_statuses, now=datetime.now())

@app.route('/clear')
def clear_backup_status():
    db.session.query(BackupStatus).delete()
    db.session.commit()
    return 'All backup status records deleted.'

def init_db():
    with app.app_context():
        db.create_all()
        print("Database initialized")

# Initialize scheduler outside of if __name__ == '__main__' block
# This ensures it runs in both development and production
scheduler = BackgroundScheduler()
# Add immediate job
scheduler.add_job(func=check_email, trigger="date", run_date=datetime.now())
# Add recurring job
scheduler.add_job(func=check_email, trigger="interval", minutes=5)
scheduler.start()
print("Scheduler started - checking email immediately and then every 5 minutes")

if __name__ == '__main__':
    init_db()
    app.run(debug=True) 