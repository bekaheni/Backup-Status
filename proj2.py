import os
import re
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
import json
from bs4 import BeautifulSoup
from flask_migrate import Migrate
import imaplib
import email as py_email
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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
    company = db.Column(db.String(100))
    email_type = db.Column(db.String(50), nullable=True)  # Add email_type field

def get_imap_connection():
    EMAIL = os.getenv('EMAIL')
    PASSWORD = os.getenv('EMAIL_PASSWORD')
    IMAP_SERVER = os.getenv('IMAP_SERVER', 'mail.remoteone.uk')
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(EMAIL, PASSWORD)
        return mail
    except Exception as e:
        print(f"Error connecting to IMAP server: {e}")
        return None

def parse_backup_status(body, subject=None):
    print(f"\nParsing email body for backup statuses...")
    print(f"Body preview: {body[:200]}...")

    # Status from subject
    status = 'unsuccessful'
    subj = subject or ''
    if 'successful' in subj.lower():
        status = 'successful'
    elif 'failed' in subj.lower() or 'unsuccessful' in subj.lower():
        status = 'unsuccessful'

    # Device/Server from subject or body
    server = 'Unknown'
    server_match = re.search(r'on (\w+)', subj)
    if server_match:
        server = server_match.group(1)
    else:
        from_match = re.search(r'From (\w+)', body)
        if from_match:
            server = from_match.group(1)

    # Timestamp from body
    timestamp = None
    time_match = re.search(r'Start Time:\s*(.+)', body)
    if time_match:
        time_str = time_match.group(1).strip()
        try:
            timestamp = datetime.strptime(time_str, "%a, %b %d %Y %H:%M:%S")
        except Exception:
            timestamp = time_str  # fallback: raw string
    else:
        timestamp = datetime.now()

    # Task (optional)
    task_match = re.search(r'Backup Task:\s*(.+)', body)
    task = task_match.group(1).strip() if task_match else ''

    result = [{
        'server': server,
        'status': status,
        'timestamp': timestamp,
        'task': task
    }]
    print(f"Parsed status: {result[0]}")
    return result

def check_email():
    try:
        print("\nStarting email check...")
        mail = get_imap_connection()
        if not mail:
            print("Failed to connect to IMAP server")
            return
        mail.select('inbox')
        # Fetch the latest 50 emails
        _, message_numbers = mail.search(None, 'ALL')
        message_ids = message_numbers[0].split()[-50:]
        print(f"Found {len(message_ids)} emails. Showing latest 50:")
        with app.app_context():
            for num in reversed(message_ids):
                _, msg_data = mail.fetch(num, '(RFC822)')
                email_body = msg_data[0][1]
                email_message = py_email.message_from_bytes(email_body)
                subject = email_message['subject']
                from_ = email_message['from']
                date_header = email_message['date']
                print(f"From: {from_} | Subject: {subject} | Date: {date_header}")
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
                # Get message body (plain or HTML)
                body = ""
                html_body = ""
                if email_message.is_multipart():
                    for part in email_message.walk():
                        content_type = part.get_content_type()
                        content_disposition = str(part.get('Content-Disposition'))
                        if content_type == 'text/plain' and 'attachment' not in content_disposition:
                            try:
                                body += part.get_payload(decode=True).decode()
                            except Exception as e:
                                print(f"Error decoding part: {e}")
                        elif content_type == 'text/html' and 'attachment' not in content_disposition:
                            try:
                                html_body += part.get_payload(decode=True).decode()
                            except Exception as e:
                                print(f"Error decoding HTML part: {e}")
                else:
                    content_type = email_message.get_content_type()
                    if content_type == 'text/plain':
                        body = email_message.get_payload(decode=True).decode()
                    elif content_type == 'text/html':
                        html_body = email_message.get_payload(decode=True).decode()
                # If no plain text, try HTML
                if not body and html_body:
                    print("No plain text body found, using HTML body.")
                    soup = BeautifulSoup(html_body, 'html.parser')
                    body = soup.get_text(separator='\n')
                if not body:
                    print("No email body found, skipping...")
                    continue
                print(f"Email subject: {subject}")
                print(f"Email body snippet: {body[:300]}\n{'-'*40}")
                # Parse for server statuses
                statuses = parse_backup_status(body, subject)
                print(f"Found {len(statuses)} backup statuses in email")
                # Save to database as before (existing logic)
                for status in statuses:
                    backup_status = BackupStatus(
                        server=status['server'],
                        status=status['status'],
                        timestamp=status['timestamp'],
                        subject=subject,
                        body=body,
                        company=get_company_for_server(status['server'])
                    )
                    db.session.add(backup_status)
            db.session.commit()
        mail.logout()
    except Exception as e:
        print(f"Error accessing email: {e}")

@app.route('/')
def index():
    with app.app_context():
        # Get all servers
        servers = db.session.query(BackupStatus.server, BackupStatus.company).distinct().all()
        # For each server, get the last 2 statuses
        server_statuses = {}
        for server, company in servers:
            statuses = BackupStatus.query.filter_by(server=server).order_by(BackupStatus.timestamp.desc()).limit(2).all()
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

@app.route('/clear')
def clear_backup_status():
    db.session.query(BackupStatus).delete()
    db.session.commit()
    return 'All backup status records deleted.'

@app.route('/clear-database', methods=['POST'])
def clear_database():
    try:
        with app.app_context():
            # Get count before deletion for the message
            count = BackupStatus.query.count()
            # Delete all records
            BackupStatus.query.delete()
            db.session.commit()
            return jsonify({
                "success": True,
                "message": f"Successfully cleared {count} records from the database"
            })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Error clearing database: {str(e)}"
        })

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

def purge_old_data():
    """Purge backup status records older than 5 days."""
    with app.app_context():
        five_days_ago = datetime.now() - timedelta(days=5)
        old_records = BackupStatus.query.filter(BackupStatus.timestamp < five_days_ago).all()
        count = len(old_records)
        for record in old_records:
            db.session.delete(record)
        db.session.commit()
        print(f"Purged {count} records older than 5 days")

def delete_old_emails():
    """Delete emails older than 10 days from the inbox."""
    try:
        mail = get_imap_connection()
        if not mail:
            return False, "Failed to connect to email server"
        
        mail.select('inbox')
        ten_days_ago = datetime.now() - timedelta(days=10)
        date_str = ten_days_ago.strftime("%d-%b-%Y")
        
        # Search for emails older than 10 days
        _, message_numbers = mail.search(None, f'(BEFORE {date_str})')
        message_ids = message_numbers[0].split()
        
        if not message_ids:
            return True, "No old emails found to delete"
        
        # Delete the emails
        for num in message_ids:
            mail.store(num, '+FLAGS', '\\Deleted')
        
        # Expunge to permanently remove the deleted emails
        mail.expunge()
        mail.close()
        mail.logout()
        
        return True, f"Successfully deleted {len(message_ids)} emails older than 10 days"
    except Exception as e:
        return False, f"Error deleting emails: {str(e)}"

@app.route('/delete-old-emails', methods=['POST'])
def handle_delete_old_emails():
    success, message = delete_old_emails()
    return jsonify({"success": success, "message": message})

# Initialize scheduler outside of if __name__ == '__main__' block
# This ensures it runs in both development and production
scheduler = BackgroundScheduler()
# Add immediate job
scheduler.add_job(func=check_email, trigger="date", run_date=datetime.now())
# Add recurring jobs
scheduler.add_job(func=check_email, trigger="interval", minutes=5)
scheduler.add_job(func=purge_old_data, trigger="interval", days=1)  # Run purge daily
scheduler.start()
print("Scheduler started - checking email immediately and then every 5 minutes, purging old data daily")

if __name__ == '__main__':
    init_db()
    update_existing_companies()  # TEMP: update company names in DB after mapping change
    print("Starting Flask application...")
    print("Access the application at: http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True) 