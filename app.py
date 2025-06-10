import os
import re
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
import imaplib
import email
from email.header import decode_header
from bs4 import BeautifulSoup
from flask_migrate import Migrate
from proj2 import parse_backup_status as parse_nas_backup_status
from utils import SERVER_COMPANIES, get_company_for_server

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///backup_status.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Database Model
class BackupStatus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    server = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False)
    subject = db.Column(db.String(200))
    body = db.Column(db.Text)
    html_body = db.Column(db.Text)  # Add HTML body field
    company = db.Column(db.String(100))
    email_type = db.Column(db.String(50), nullable=True)  # Add email_type field

def connect_to_imap(email_type='server'):
    try:
        print(f"Attempting to connect to IMAP server for {email_type}...")
        # Get IMAP settings from environment variables
        if email_type == 'server':
            email = os.getenv('EMAIL')
            password = os.getenv('EMAIL_PASSWORD')
            imap_server = os.getenv('IMAP_SERVER', 'mail.remoteone.uk')
            inbox_name = os.getenv('INBOX_NAME', 'INBOX')
        else:  # nas
            email = os.getenv('NAS_EMAIL')
            password = os.getenv('NAS_EMAIL_PASSWORD')
            imap_server = os.getenv('NAS_IMAP_SERVER', 'mail.remoteone.uk')
            inbox_name = os.getenv('NAS_INBOX_NAME', 'INBOX')

        print(f"Connecting to {imap_server}")
        print(f"Using email: {email}")
        # Connect to IMAP server
        mail = imaplib.IMAP4_SSL(imap_server)
        print("Connected to server, attempting login...")
        mail.login(email, password)
        print("Login successful, selecting inbox...")
        mail.select(inbox_name)
        print("Successfully connected to IMAP server")
        return mail
    except Exception as e:
        print(f"Error connecting to IMAP server: {str(e)}")
        print(f"Server: {imap_server}")
        print(f"Email: {email}")
        print(f"Inbox: {inbox_name}")
        return None

def parse_backup_status(body):
    print(f"\nParsing email body for backup statuses...")
    print(f"Full body content:")
    print("-" * 80)
    print(body)
    print("-" * 80)
    
    # Updated pattern to match the actual format:
    # ServerName
    # (ServerID)
    # Success/Failed
    # Date Time
    pattern = re.compile(
        r'([A-Za-z0-9]+)\s*\(([A-Za-z0-9]+)\)\s*([A-Za-z]+)\s*(\d{2}\s+\w{3}\s+\d{4}\s+\d{2}:\d{2})',
        re.DOTALL
    )
    
    results = []
    matches = list(pattern.finditer(body))
    print(f"Found {len(matches)} backup status entries")
    
    if len(matches) == 0:
        print("No matches found. Checking if HTML structure is different...")
        # Try to find any spans with font-weight: bold to see what we're actually getting
        soup = BeautifulSoup(body, 'html.parser')
        bold_spans = soup.find_all('span', style=lambda x: x and 'font-weight: bold' in x)
        print(f"Found {len(bold_spans)} bold spans in the HTML")
        for span in bold_spans:
            print(f"Bold span content: {span.text}")
        
        # Try to find the server name and status directly
        server_name = None
        server_id = None
        status = None
        timestamp = None
        
        # Look for server name and ID
        server_match = re.search(r'([A-Za-z0-9]+)\s*\(([A-Za-z0-9]+)\)', body)
        if server_match:
            server_name = server_match.group(1).strip()
            server_id = server_match.group(2).strip()
            print(f"Found server: {server_name} ({server_id})")
        
        # Look for status
        status_match = re.search(r'(Success|Failed)', body)
        if status_match:
            status = status_match.group(1).strip()
            print(f"Found status: {status}")
        
        # Look for timestamp
        time_match = re.search(r'(\d{2}\s+\w{3}\s+\d{4}\s+\d{2}:\d{2})', body)
        if time_match:
            dt_str = time_match.group(1).strip()
            try:
                timestamp = datetime.strptime(dt_str, "%d %b %Y %H:%M")
                print(f"Found timestamp: {timestamp}")
            except Exception as e:
                print(f"Error parsing date '{dt_str}': {str(e)}")
                timestamp = datetime.now()
        
        if server_name and server_id and status and timestamp:
            result = {
                'server': f"{server_name} ({server_id})",
                'status': 'successful' if status.lower() == 'success' else 'unsuccessful',
                'timestamp': timestamp
            }
            print(f"Created result from individual matches: {result}")
            results.append(result)
    
    for match in matches:
        server_name = match.group(1).strip()
        server_id = match.group(2).strip()
        status = match.group(3).strip()
        dt_str = match.group(4).strip()
        
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

def check_email(email_type='server'):
    try:
        print(f"\nStarting email check for {email_type}...")
        mail = connect_to_imap(email_type)
        if not mail:
            print(f"Failed to connect to IMAP server for {email_type}")
            return

        # Select the inbox first
        print("Selecting inbox...")
        mail.select('inbox')
        
        # Search for all emails
        print("Searching for emails...")
        _, messages = mail.search(None, 'ALL')
        email_ids = messages[0].split()
        print(f"Found {len(email_ids)} messages")
        
        if not email_ids:
            print("No messages found")
            return

        with app.app_context():
            for email_id in email_ids[-50:]:  # Process last 50 emails
                print(f"\nProcessing message {email_id}...")
                # Fetch the email
                _, msg_data = mail.fetch(email_id, '(RFC822)')
                email_body = msg_data[0][1]
                email_message = email.message_from_bytes(email_body)
                
                # Get subject and date
                subject = decode_header(email_message["subject"])[0][0]
                if isinstance(subject, bytes):
                    subject = subject.decode()
                date_header = email_message["date"]
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
                
                if email_message.is_multipart():
                    for part in email_message.walk():
                        content_type = part.get_content_type()
                        content_disposition = str(part.get("Content-Disposition"))
                        
                        if "attachment" not in content_disposition:
                            if content_type == "text/plain":
                                try:
                                    body = part.get_payload(decode=True).decode()
                                except:
                                    body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                            elif content_type == "text/html":
                                try:
                                    html_body = part.get_payload(decode=True).decode()
                                except:
                                    html_body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                else:
                    try:
                        body = email_message.get_payload(decode=True).decode()
                    except:
                        body = email_message.get_payload(decode=True).decode('utf-8', errors='ignore')
                
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
                
                # Parse for server statuses using the appropriate parser
                if email_type == 'nas':
                    statuses = parse_nas_backup_status(body, subject)
                else:
                    statuses = parse_backup_status(body)
                print(f"Found {len(statuses)} backup statuses in email")
                
                for s in statuses:
                    # Only add if this is the latest for this server
                    existing = BackupStatus.query.filter_by(
                        server=s['server'],
                        timestamp=s['timestamp'],
                        email_type=email_type  # Add email_type to filter
                    ).first()
                    
                    if not existing:
                        print(f"Adding new status for {s['server']}")
                        new_status = BackupStatus(
                            server=s['server'],
                            status=s['status'],
                            timestamp=s['timestamp'],
                            subject=subject,
                            body=body or "",
                            html_body=html_body or "",
                            company=get_company_for_server(s['server']),
                            email_type=email_type  # Add email_type to model
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
    finally:
        if mail:
            try:
                mail.close()
                mail.logout()
            except:
                pass

@app.route('/')
def index():
    with app.app_context():
        # Get all servers for server backups
        servers = db.session.query(BackupStatus.server, BackupStatus.company).filter_by(email_type='server').distinct().all()
        # For each server, get the last 2 statuses
        server_statuses = {}
        for server, company in servers:
            statuses = BackupStatus.query.filter_by(server=server, email_type='server').order_by(BackupStatus.timestamp.desc()).limit(2).all()
            if statuses:
                # Use 'Unknown' for None company values
                company_key = company if company else 'Unknown'
                server_statuses.setdefault(company_key, []).append(statuses)
        # Sort companies, handling None values
        companies = sorted(server_statuses.keys())
        # Get the latest update time
        last_update = datetime.now().strftime('%Y-%m-%d %H:%M')
        # Count total servers
        total_servers = sum(len(servers) for servers in server_statuses.values())
        return render_template('index.html',
                              server_statuses=server_statuses,
                              companies=companies,
                              last_update=last_update,
                              total_servers=total_servers)

@app.route('/nas')
def nas_view():
    with app.app_context():
        # Get all servers for NAS backups
        servers = db.session.query(BackupStatus.server, BackupStatus.company).filter_by(email_type='nas').distinct().all()
        # For each server, get the last 2 statuses
        server_statuses = {}
        for server, company in servers:
            statuses = BackupStatus.query.filter_by(server=server, email_type='nas').order_by(BackupStatus.timestamp.desc()).limit(2).all()
            if statuses:
                # Use 'Unknown' for None company values
                company_key = company if company else 'Unknown'
                server_statuses.setdefault(company_key, []).append(statuses)
        # Sort companies, handling None values
        companies = sorted(server_statuses.keys())
        # Get the latest update time
        last_update = datetime.now().strftime('%Y-%m-%d %H:%M')
        # Count total servers
        total_servers = sum(len(servers) for servers in server_statuses.values())
        return render_template('nas.html',
                              server_statuses=server_statuses,
                              companies=companies,
                              last_update=last_update,
                              total_servers=total_servers)

@app.route('/clear')
def clear_backup_status():
    db.session.query(BackupStatus).delete()
    db.session.commit()
    return 'All backup status records deleted.'

@app.route('/clear-database', methods=['POST'])
def clear_database():
    try:
        with app.app_context():
            email_type = request.json.get('email_type', 'server')
            # Get count before deletion for the message
            count = BackupStatus.query.filter_by(email_type=email_type).count()
            # Delete records for the specified email type
            BackupStatus.query.filter_by(email_type=email_type).delete()
            db.session.commit()
            return jsonify({
                "success": True,
                "message": f"Successfully cleared {count} {email_type} backup records from the database"
            })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error clearing database: {str(e)}"
        })

@app.route('/delete-old-emails', methods=['POST'])
def delete_old_emails():
    try:
        email_type = request.json.get('email_type', 'server')
        days_old = 10
        cutoff_date = datetime.now() - timedelta(days=days_old)
        
        # Connect to the appropriate email account
        imap_server = connect_to_imap(email_type)
        if not imap_server:
            return jsonify({'success': False, 'message': 'Failed to connect to email server'})
        
        # Select the inbox before searching
        imap_server.select('inbox')
        
        # Search for emails older than cutoff date
        date_str = cutoff_date.strftime("%d-%b-%Y")
        _, message_numbers = imap_server.search(None, f'(BEFORE {date_str})')
        
        if message_numbers[0]:
            # Delete the emails
            for num in message_numbers[0].split():
                imap_server.store(num, '+FLAGS', '\\Deleted')
            imap_server.expunge()
            imap_server.close()
            imap_server.logout()
            return jsonify({'success': True, 'message': f'Successfully deleted emails older than {days_old} days'})
        else:
            imap_server.close()
            imap_server.logout()
            return jsonify({'success': True, 'message': 'No old emails found to delete'})
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

def update_existing_companies():
    """Update existing records with company information."""
    with app.app_context():
        statuses = BackupStatus.query.all()
        for status in statuses:
            status.company = get_company_for_server(status.server)
        db.session.commit()
        print("Updated all records with new company information")

def init_db():
    with app.app_context():
        db.create_all()
        update_existing_companies()
        print("Database initialized")

# Initialize scheduler with both email types
scheduler = BackgroundScheduler()
# Add immediate jobs for both email types
scheduler.add_job(func=lambda: check_email('server'), trigger="date", run_date=datetime.now())
scheduler.add_job(func=lambda: check_email('nas'), trigger="date", run_date=datetime.now())
# Add recurring jobs for both email types
scheduler.add_job(func=lambda: check_email('server'), trigger="interval", minutes=5)
scheduler.add_job(func=lambda: check_email('nas'), trigger="interval", minutes=5)
scheduler.start()
print("Scheduler started - checking both email accounts immediately and then every 5 minutes")

if __name__ == '__main__':
    init_db()
    update_existing_companies()  # TEMP: update company names in DB after mapping change
    app.run(host='0.0.0.0', port=5000, debug=False) 