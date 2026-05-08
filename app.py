import os
import re
import fcntl
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
import imaplib
import email
from email.header import decode_header
from bs4 import BeautifulSoup
from flask_migrate import Migrate
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
from utils import SERVER_COMPANIES, get_company_for_server, get_expected_servers

def clean_server_name(server_name):
    """Clean up messy server names from email parsing"""
    if not server_name:
        return ""
    
    # Remove server ID part if it exists
    clean_name = server_name.split(' (')[0]
    
    # Remove common prefixes
    prefixes_to_remove = [
        'Email Notification',
        'Backup Offsite Replication',
        'Backup',
        'Offsite', 
        'Replication'
    ]
    
    for prefix in prefixes_to_remove:
        if prefix in clean_name:
            clean_name = clean_name.split(prefix)[-1].strip()
    
    # Remove excessive whitespace and newlines
    clean_name = clean_name.replace('\n', ' ').replace('\r', ' ')
    clean_name = re.sub(r'\s+', ' ', clean_name).strip()
    
    # If we still have a messy name, try to extract the last meaningful part
    if len(clean_name) > 20 or any(word in clean_name for word in ['Backup', 'Offsite', 'Replication', 'Email', 'Notification']):
        parts = clean_name.split()
        for part in reversed(parts):
            if (len(part) > 2 and 
                part not in ['Backup', 'Offsite', 'Replication', 'Email', 'Notification'] and
                not part.startswith('(') and not part.endswith(')')):
                clean_name = part
                break
    
    return clean_name

# Application version
VERSION = "1.2.0"

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configure Flask
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///backup_status.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')  # Change this in production

# Configure session handling - extend login timeout to 24 hours
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(hours=24)

# Custom Jinja2 filter for regex
@app.template_filter('regex_findall')
def regex_findall_filter(text, pattern):
    if text:
        matches = re.findall(pattern, text)
        return matches
    return []

# Custom Jinja2 filter to check if a server is found in database
@app.template_filter('is_server_found')
def is_server_found_filter(expected_server, company, server_statuses):
    """Check if an expected server is found in the database for a given company"""
    if not server_statuses.get(company):
        return False
    
    for server_list in server_statuses[company]:
        for status in server_list:
            clean_status_server = clean_server_name(status.server)
            if expected_server in clean_status_server or expected_server in status.server:
                return True
    return False

# Initialize Flask-SQLAlchemy
db = SQLAlchemy(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User Model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

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
    cleared_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)


class AppConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    servers = db.relationship('ExpectedServer', backref='company', lazy=True, cascade='all, delete-orphan')


class ExpectedServer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email_type = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('company_id', 'name', 'email_type', name='uq_company_server_type'),
    )


def get_config(key, default=None):
    config = AppConfig.query.filter_by(key=key).first()
    return config.value if config else default


def set_config(key, value):
    config = AppConfig.query.filter_by(key=key).first()
    if config:
        config.value = str(value)
        config.updated_at = datetime.utcnow()
    else:
        config = AppConfig(key=key, value=str(value))
        db.session.add(config)
    db.session.commit()


def get_all_companies():
    return Company.query.order_by(Company.name).all()


def get_expected_servers_for_company(company_id, email_type):
    return [s.name for s in ExpectedServer.query.filter_by(company_id=company_id, email_type=email_type).all()]


def get_company_for_server(server_name, email_type):
    server_lower = server_name.lower()
    for es in ExpectedServer.query.filter_by(email_type=email_type).all():
        if es.name.lower() in server_lower:
            return es.company.name
    return 'Other'


def _get_expected_by_name(company_name, email_type):
    company = Company.query.filter(db.func.lower(Company.name) == company_name.lower()).first()
    if not company:
        return []
    return get_expected_servers_for_company(company.id, email_type)


DEFAULT_SERVER_PROMPT = """This app monitors VM backup status emails from Hornetsecurity VM Backup and Altaro VM Backup software. Daily status report emails contain an HTML table listing each server with its backup result shown as a coloured Success or Failed badge.

Extract every server row from the table. For each row return:
- server_name: the server name without the ID in brackets (e.g. "MYSERVER" not "MYSERVER (ABC123)")
- status: "successful" if the backup succeeded, "unsuccessful" if it failed or is overdue
- timestamp_str: the date and time string exactly as it appears in the Backup column, or null if not found

Return an empty list for monthly summaries, licence warnings, software update emails, marketing emails, or any email that does not report individual daily backup results per server.

Return JSON only with no other text. Example:
[{"server_name": "MYSERVER", "status": "successful", "timestamp_str": "15 Mar 2024 14:30"}]"""

DEFAULT_NAS_PROMPT = """This app monitors NAS backup status emails. NAS backup emails typically report a single device per email with the device name in the subject line.

Extract the backup result. Return:
- server_name: the device or NAS name, typically found in the subject line after "on"
- status: "successful" if the backup succeeded, "unsuccessful" if it failed
- timestamp_str: the start time or completion time as it appears in the email, or null if not found

Return an empty list for any email that is not a NAS device backup status report (e.g. marketing, licence warnings, monthly summaries).

Return JSON only with no other text. Example:
[{"server_name": "MYNAS", "status": "successful", "timestamp_str": "Mon, Jan 15 2024 14:30:00"}]"""


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

def parse_backup_status(body, email_timestamp=None):
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
    # Much more aggressive cleaning to handle the messy email format
    # Remove the entire header section that contains "Email Notification", "Backup", "Offsite", "Replication"
    cleaned_body = re.sub(r'(?i).*?email\s+notification.*?(?=\n[A-Za-z]|\n\s*[A-Za-z]|$)', '', body, flags=re.DOTALL)
    cleaned_body = re.sub(r'(?i).*?backup\s+offsite\s+replication.*?(?=\n[A-Za-z]|\n\s*[A-Za-z]|$)', '', cleaned_body, flags=re.DOTALL)
    
    # Remove excessive newlines and normalize whitespace
    cleaned_body = re.sub(r'\n+', '\n', cleaned_body)
    cleaned_body = re.sub(r'\s+', ' ', cleaned_body)
    cleaned_body = cleaned_body.strip()
    
    # More precise pattern that looks for server names followed by (ID) pattern
    pattern = re.compile(
        r'([A-Za-z0-9][A-Za-z0-9\s]*?)\s*\(([A-Za-z0-9]+)\)\s*([A-Za-z]+)\s*(\d{2}\s+\w{3}\s+\d{4}\s+\d{2}:\d{2})',
        re.DOTALL
    )
    
    results = []
    matches = list(pattern.finditer(cleaned_body))
    print(f"Found {len(matches)} backup status entries")
    
    if len(matches) == 0:
        print("No matches found. Checking if HTML structure is different...")
        # Try to find any spans with font-weight: bold to see what we're actually getting
        soup = BeautifulSoup(body, 'html.parser')
        bold_spans = soup.find_all('span', style=lambda x: x and 'font-weight: bold' in x)
        print(f"Found {len(bold_spans)} bold spans in the HTML")
        for span in bold_spans:
            print(f"Bold span content: {span.text}")
        
        # Try to find multiple server entries in the email
        # Look for all server name and ID patterns
        server_matches = re.findall(r'([A-Za-z0-9][A-Za-z0-9\s]*?)\s*\(([A-Za-z0-9]+)\)', cleaned_body)
        print(f"Found {len(server_matches)} server patterns: {server_matches}")
        
        # Look for all status patterns
        status_matches = re.findall(r'(Success|Failed|Overdue)', cleaned_body)
        print(f"Found {len(status_matches)} status patterns: {status_matches}")
        
        # Look for timestamp
        time_match = re.search(r'(\d{2}\s+\w{3}\s+\d{4}\s+\d{2}:\d{2})', cleaned_body)
        timestamp = None
        if time_match:
            dt_str = time_match.group(1).strip()
            try:
                timestamp = datetime.strptime(dt_str, "%d %b %Y %H:%M")
                print(f"Found timestamp: {timestamp}")
            except Exception as e:
                print(f"Error parsing date '{dt_str}': {str(e)}")
                timestamp = datetime.now()
        
        # If no timestamp found, use email timestamp or current time as fallback
        if not timestamp:
            if email_timestamp:
                timestamp = email_timestamp
                print(f"No timestamp found in body, using email timestamp: {timestamp}")
            else:
                timestamp = datetime.now()
                print(f"No timestamp found, using current time: {timestamp}")
        
        # Create results for each server-status combination
        # For now, assume they're in order (server1->status1, server2->status2, etc.)
        for i, (server_name, server_id) in enumerate(server_matches):
            if i < len(status_matches):
                status = status_matches[i]
                result = {
                    'server': f"{server_name} ({server_id})",
                    'status': 'successful' if status.lower() == 'success' else 'unsuccessful',
                    'timestamp': timestamp
                }
                print(f"Created result from individual matches: {result}")
                results.append(result)
            else:
                print(f"Warning: Server {server_name} ({server_id}) has no corresponding status")
    
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

def parse_nas_backup_status(body, subject=None):
    """Parse NAS backup status from email body and subject."""
    print(f"\nParsing NAS email body for backup statuses...")
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

    result = [{
        'server': server,
        'status': status,
        'timestamp': timestamp
    }]
    print(f"Parsed NAS status: {result[0]}")
    return result


def parse_email_with_ai(subject, body, html_body, email_type, email_timestamp=None):
    """Parse backup email using Claude AI, falling back to regex parser on failure."""
    try:
        import anthropic

        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        ai_enabled = get_config('ai_parsing_enabled', 'true')
        if ai_enabled and ai_enabled.lower() != 'true':
            raise ValueError("AI parsing disabled in config")

        prompt_key = 'ai_prompt_server' if email_type == 'server' else 'ai_prompt_nas'
        system_prompt = get_config(prompt_key, DEFAULT_SERVER_PROMPT if email_type == 'server' else DEFAULT_NAS_PROMPT)

        cleaned_body = body
        if not cleaned_body and html_body:
            soup = BeautifulSoup(html_body, 'html.parser')
            cleaned_body = soup.get_text(separator='\n')

        user_message = f"Subject: {subject}\n\nEmail body:\n{cleaned_body}"

        print(f"Calling Claude AI for {email_type} email parsing...")
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )

        raw = response.content[0].text.strip()
        print(f"AI parser raw response (first 300 chars): {raw[:300]}")

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            json_match = re.search(r'\[.*\]', raw, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(0))
            else:
                print(f"AI parser: could not extract JSON from response: {raw[:500]}")
                raise ValueError("No JSON array found in AI response")

        timestamp_formats = [
            "%d %b %Y %H:%M",
            "%a, %b %d %Y %H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%m/%d/%Y %H:%M",
            "%d-%b-%Y %H:%M",
        ]

        results = []
        for item in parsed:
            server_name = (item.get('server_name') or 'Unknown').strip()
            status_str = (item.get('status') or 'unsuccessful').lower()
            status = 'successful' if status_str == 'successful' else 'unsuccessful'
            timestamp_str = item.get('timestamp_str')

            timestamp = None
            if timestamp_str:
                for fmt in timestamp_formats:
                    try:
                        timestamp = datetime.strptime(timestamp_str.strip(), fmt)
                        break
                    except ValueError:
                        continue

            if not timestamp:
                timestamp = email_timestamp or datetime.now()

            results.append({'server': server_name, 'status': status, 'timestamp': timestamp})

        print(f"AI parser extracted {len(results)} result(s)")
        return results

    except Exception as e:
        print(f"AI parsing failed ({type(e).__name__}: {e}), falling back to regex parser")
        if email_type == 'nas':
            return parse_nas_backup_status(body, subject)
        else:
            return parse_backup_status(body, email_timestamp)


def check_email(email_type='server'):
    import traceback
    mail = None
    lock_file = None
    try:
        lock_file = open(f'/tmp/check_email_{email_type}.lock', 'w')
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, OSError):
            print(f"[check_email/{email_type}] Another worker is already running this check — skipping")
            return
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
            new_count = 0
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
                
                # Parse for server statuses using AI parser (with regex fallback)
                statuses = parse_email_with_ai(subject, body, html_body, email_type, email_timestamp)
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
                            company=get_company_for_server(s['server'], email_type),
                            email_type=email_type
                        )
                        db.session.add(new_status)
                        new_count += 1
                        print(f"Added status: Server={s['server']}, Status={s['status']}, Time={s['timestamp']}")
                    else:
                        print(f"Status already exists for {s['server']}")
            
            print(f"[check_email/{email_type}] Committing {new_count} new record(s) to database...")
            db.session.commit()
            print(f"[check_email/{email_type}] Commit successful — {new_count} new record(s) written")
            
    except Exception as e:
        print(f"[check_email/{email_type}] Exception: {type(e).__name__}: {str(e)}")
        print(traceback.format_exc())
        try:
            db.session.rollback()
            print(f"[check_email/{email_type}] Session rolled back after error")
        except Exception as rb_e:
            print(f"[check_email/{email_type}] Rollback also failed: {rb_e}")
    finally:
        if lock_file:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                lock_file.close()
            except Exception:
                pass
        if mail:
            try:
                mail.close()
                mail.logout()
            except:
                pass

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user, remember=True)  # Set remember=True for extended session
            flash('Logged in successfully.', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Invalid username or password.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    with app.app_context():
        # Get the number of statuses to show from query parameter, default to 2
        status_count = request.args.get('status_count', 2, type=int)
        
        # Get all servers for server backups
        servers = db.session.query(BackupStatus.server, BackupStatus.company).filter_by(email_type='server').distinct().all()
        # For each server, get the specified number of statuses
        server_statuses = {}
        for server, company in servers:
            statuses = BackupStatus.query.filter_by(server=server, email_type='server').order_by(BackupStatus.timestamp.desc()).limit(status_count).all()
            if statuses:
                # Use 'Unknown' for None company values
                company_key = company if company else 'Unknown'
                server_statuses.setdefault(company_key, []).append(statuses)
        # Get all companies from DB, combine with those that have data
        all_companies = sorted(set(list(server_statuses.keys()) + [c.name for c in get_all_companies()]))

        # Filter out companies that should not appear on server backup page
        companies_to_exclude = _EXCLUDE_COMPANIES['server']
        all_companies = [company for company in all_companies if company not in companies_to_exclude]

        # Get the latest update time
        last_update = datetime.now().strftime('%Y-%m-%d %H:%M')
        # Count total servers
        total_servers = sum(len(servers) for servers in server_statuses.values())
        return render_template('index.html',
                             server_statuses=server_statuses,
                             companies=all_companies,
                             last_update=last_update,
                             total_servers=total_servers,
                             status_count=status_count,
                             get_expected_servers=lambda company: _get_expected_by_name(company, 'server'),
                             clean_server_name=clean_server_name,
                             version=VERSION)

@app.route('/nas')
@login_required
def nas_view():
    with app.app_context():
        # Get the number of statuses to show from query parameter, default to 2
        status_count = request.args.get('status_count', 2, type=int)
        
        # Get all servers for NAS backups
        servers = db.session.query(BackupStatus.server, BackupStatus.company).filter_by(email_type='nas').distinct().all()
        # For each server, get the specified number of statuses
        server_statuses = {}
        for server, company in servers:
            statuses = BackupStatus.query.filter_by(server=server, email_type='nas').order_by(BackupStatus.timestamp.desc()).limit(status_count).all()
            if statuses:
                # Use 'Unknown' for None company values
                company_key = company if company else 'Unknown'
                server_statuses.setdefault(company_key, []).append(statuses)
        # Get all companies from DB, combine with those that have data
        all_companies = sorted(set(list(server_statuses.keys()) + [c.name for c in get_all_companies()]))

        # Filter out companies that should not appear on NAS page
        companies_to_exclude = _EXCLUDE_COMPANIES['nas']
        all_companies = [company for company in all_companies if company not in companies_to_exclude]

        # Get the latest update time
        last_update = datetime.now().strftime('%Y-%m-%d %H:%M')
        # Count total servers
        total_servers = sum(len(servers) for servers in server_statuses.values())
        return render_template('nas.html',
                              server_statuses=server_statuses,
                              companies=all_companies,
                              last_update=last_update,
                              total_servers=total_servers,
                              status_count=status_count,
                              get_expected_servers=lambda company: _get_expected_by_name(company, 'nas'),
                              clean_server_name=clean_server_name,
                              version=VERSION)

@app.route('/clear')
@login_required
def clear_backup_status():
    db.session.query(BackupStatus).delete()
    db.session.commit()
    return 'All backup status records deleted.'

@app.route('/clear-database', methods=['POST'])
@login_required
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
@login_required
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
            status.company = get_company_for_server(status.server, status.email_type or 'server')
        db.session.commit()
        print("Updated all records with new company information")

def init_db():
    """Initialize the database."""
    with app.app_context():
        # Drop all tables and recreate them
        db.drop_all()
        db.create_all()
        print("Database initialized")

_scheduler = None
_scheduler_lock_file = None  # held open for process lifetime to prevent duplicate schedulers


def start_background_jobs():
    global _scheduler, _scheduler_lock_file
    try:
        _scheduler_lock_file = open('/tmp/scheduler.lock', 'w')
        fcntl.flock(_scheduler_lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (IOError, OSError):
        print("[scheduler] Another worker already holds the scheduler lock — skipping duplicate start")
        try:
            _scheduler_lock_file.close()
        except Exception:
            pass
        _scheduler_lock_file = None
        return

    with app.app_context():
        interval = int(get_config('scheduler_interval_minutes', '5') or '5')

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(func=lambda: check_email('server'), trigger="date", run_date=datetime.now())
    _scheduler.add_job(func=lambda: check_email('nas'), trigger="date", run_date=datetime.now())
    _scheduler.add_job(func=lambda: check_email('server'), trigger="interval", minutes=interval, id='server_check')
    _scheduler.add_job(func=lambda: check_email('nas'), trigger="interval", minutes=interval, id='nas_check')
    _scheduler.start()
    print(f"Scheduler started — checking both email accounts immediately and then every {interval} minute(s)")


def reschedule(interval_minutes):
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.reschedule_job('server_check', trigger='interval', minutes=interval_minutes)
        _scheduler.reschedule_job('nas_check', trigger='interval', minutes=interval_minutes)
        print(f"Scheduler updated to every {interval_minutes} minute(s)")

@app.route('/parsing-logic')
def parsing_logic():
    return render_template('parsing_logic.html')

@app.route('/template')
def template_page():
    return redirect(url_for('configuration_page'))

@app.route('/configuration')
@login_required
def configuration_page():
    server_inbox = os.getenv('EMAIL', 'not set')
    nas_inbox = os.getenv('NAS_EMAIL', 'not set')
    imap_server = os.getenv('IMAP_SERVER', 'not set')
    nas_imap_server = os.getenv('NAS_IMAP_SERVER', 'not set')
    scheduler_interval = int(get_config('scheduler_interval_minutes', '5') or '5')
    ai_parsing_enabled = (get_config('ai_parsing_enabled', 'true') or 'true').lower() == 'true'
    ai_prompt_server = get_config('ai_prompt_server', DEFAULT_SERVER_PROMPT)
    ai_prompt_nas = get_config('ai_prompt_nas', DEFAULT_NAS_PROMPT)
    return render_template('configuration.html',
                           server_inbox=server_inbox,
                           nas_inbox=nas_inbox,
                           imap_server=imap_server,
                           nas_imap_server=nas_imap_server,
                           scheduler_interval=scheduler_interval,
                           ai_parsing_enabled=ai_parsing_enabled,
                           ai_prompt_server=ai_prompt_server,
                           ai_prompt_nas=ai_prompt_nas,
                           version=VERSION)

@app.route('/test-route')
def test_route():
    return "Test route is working!"

@app.route('/debug-servers')
@login_required
def debug_servers():
    """Debug route to show all servers in database"""
    with app.app_context():
        # Get all servers from database
        servers = db.session.query(BackupStatus.server, BackupStatus.company, BackupStatus.email_type).distinct().all()
        
        debug_info = []
        debug_info.append("=== DATABASE SERVERS ===")
        for server, company, email_type in servers:
            debug_info.append(f"Server: '{server}' | Company: '{company}' | Type: '{email_type}'")
            debug_info.append(f"  Cleaned: '{clean_server_name(server)}'")
        
        debug_info.append("\n=== EXPECTED SERVERS ===")
        for company in get_all_companies():
            debug_info.append(f"Company: '{company.name}'")
            for es in company.servers:
                debug_info.append(f"  Expected ({es.email_type}): '{es.name}'")
        
        return "<br>".join(debug_info)

@app.route('/manual-refresh', methods=['GET', 'POST'])
@login_required
def manual_refresh():
    """Manually trigger email checking for both server and NAS emails."""
    print("=== MANUAL REFRESH ROUTE CALLED ===")
    print(f"Request method: {request.method}")
    print(f"Referrer: {request.referrer}")
    try:
        # Check both email types
        print("Starting server email check...")
        check_email('server')
        print("Starting NAS email check...")
        check_email('nas')
        print("Email refresh completed successfully")
        flash('Email refresh completed successfully.', 'success')
    except Exception as e:
        print(f"Error during email refresh: {str(e)}")
        flash(f'Error during email refresh: {str(e)}', 'error')
    
    # Redirect back to the referring page
    redirect_url = request.referrer or url_for('index')
    print(f"Redirecting to: {redirect_url}")
    return redirect(redirect_url)

# Initialize the database and create admin user
with app.app_context():
    db.create_all()
    # Check if admin user exists
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        admin = User(username='admin', is_admin=True)
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("Admin user created")
    else:
        print("Admin user already exists")
    # Seed default AppConfig values if not already present
    defaults = {
        'ai_prompt_server': DEFAULT_SERVER_PROMPT,
        'ai_prompt_nas': DEFAULT_NAS_PROMPT,
        'scheduler_interval_minutes': '5',
        'ai_parsing_enabled': 'true',
    }
    for key, value in defaults.items():
        try:
            db.session.add(AppConfig(key=key, value=value))
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
    print("AppConfig defaults initialised")
    # Seed Company and ExpectedServer tables if ExpectedServer table is empty.
    # Guard on ExpectedServer (not Company) so that if all servers are deleted
    # via the config page the defaults are restored on next startup.
    if ExpectedServer.query.count() == 0:
        _seed_data = {
            'BRB Ltd':      {'server': ['BRBD', 'BRBFAP', 'BRBExchange', 'Remote Desktop'], 'nas': []},
            'Lochlie Ltd':  {'server': ['LochlieApp01', 'LochlieApp02', 'LochlieDC', 'LochlieRD', 'BekatApp02'], 'nas': []},
            'eHeating Ltd': {'server': ['eHeating02', 'eHeating03', 'eHeating04', 'eHeatingACT'], 'nas': []},
            'Caseman Ltd':  {'server': ['CaseNotesCMS', 'CaseNotesNTS', 'CasemanAPP', 'CasemanA', 'WIN10', 'CasemanDC'], 'nas': ['casemanNAS']},
            'JS Wilson Ltd':{'server': ['Remote Desktop', 'Trimble Server'], 'nas': []},
            'NHG Ltd':      {'server': ['NHG'], 'nas': ['NHG']},
            'Bekat IT':     {'server': ['BekatApp01'], 'nas': []},
            'JSW Ltd':      {'server': ['JSW'], 'nas': ['JSW']},
        }
        try:
            for company_name, type_map in _seed_data.items():
                company = Company.query.filter(
                    db.func.lower(Company.name) == company_name.lower()
                ).first()
                if not company:
                    company = Company(name=company_name)
                    db.session.add(company)
                    db.session.flush()
                for etype, names in type_map.items():
                    for sname in names:
                        db.session.add(ExpectedServer(company_id=company.id, name=sname, email_type=etype))
            db.session.commit()
            print("Company and ExpectedServer tables seeded")
            # Re-assign any BackupStatus records stuck as 'Other' that can now be matched
            reassigned = 0
            for status in BackupStatus.query.filter_by(company='Other').all():
                new_company = get_company_for_server(status.server, status.email_type or 'server')
                if new_company != 'Other':
                    status.company = new_company
                    reassigned += 1
            if reassigned:
                db.session.commit()
                print(f"Re-assigned {reassigned} BackupStatus records from 'Other' to correct companies")
        except IntegrityError:
            db.session.rollback()
            print("Company seeding skipped (already exists)")

    # Unconditional startup task: reassign any BackupStatus records still set
    # to 'Other' or None that can now be matched against the ExpectedServer table.
    reassigned = 0
    for status in BackupStatus.query.filter(
        db.or_(BackupStatus.company == 'Other', BackupStatus.company == None)
    ).all():
        new_company = get_company_for_server(status.server, status.email_type or 'server')
        if new_company != 'Other':
            status.company = new_company
            reassigned += 1
    if reassigned:
        db.session.commit()
    print(f"Startup reassignment: {reassigned} BackupStatus record(s) updated from 'Other'/None to correct company")

# ─── User Management Routes ──────────────────────────────────────────────────

@app.route('/users')
@login_required
def users_page():
    if not current_user.is_admin:
        flash('Access restricted to admin users.', 'error')
        return redirect(url_for('index'))
    users = User.query.order_by(User.username).all()
    return render_template('users.html', users=users, current_user=current_user)


@app.route('/users/add', methods=['POST'])
@login_required
def users_add():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Access restricted.'})
    data = request.form
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    is_admin = data.get('is_admin') == 'on'

    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password are required.'})
    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': f'Username "{username}" already exists.'})

    user = User(username=username, is_admin=is_admin)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify({'success': True, 'message': f'User "{username}" created successfully.'})


@app.route('/users/delete', methods=['POST'])
@login_required
def users_delete():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Access restricted.'})
    data = request.get_json() or {}
    user_id = data.get('user_id')

    if user_id == current_user.id:
        return jsonify({'success': False, 'message': 'You cannot delete your own account.'})

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found.'})

    if user.is_admin:
        admin_count = User.query.filter_by(is_admin=True).count()
        if admin_count <= 1:
            return jsonify({'success': False, 'message': 'Cannot delete the last admin user.'})

    db.session.delete(user)
    db.session.commit()
    return jsonify({'success': True, 'message': f'User "{user.username}" deleted.'})


@app.route('/users/change-password', methods=['POST'])
@login_required
def users_change_password():
    data = request.get_json() or {}
    user_id = data.get('user_id')
    new_password = data.get('new_password') or ''

    if not current_user.is_admin and user_id != current_user.id:
        return jsonify({'success': False, 'message': 'You can only change your own password.'})
    if len(new_password) < 8:
        return jsonify({'success': False, 'message': 'Password must be at least 8 characters.'})

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found.'})

    user.set_password(new_password)
    db.session.commit()
    return jsonify({'success': True, 'message': f'Password for "{user.username}" updated.'})


@app.route('/users/toggle-admin', methods=['POST'])
@login_required
def users_toggle_admin():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Access restricted.'})
    data = request.get_json() or {}
    user_id = data.get('user_id')

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found.'})

    if user.is_admin:
        admin_count = User.query.filter_by(is_admin=True).count()
        if admin_count <= 1:
            return jsonify({'success': False, 'message': 'Cannot remove admin from the last admin user.'})

    user.is_admin = not user.is_admin
    db.session.commit()
    role = 'admin' if user.is_admin else 'standard user'
    return jsonify({'success': True, 'message': f'"{user.username}" is now a {role}.'})

# ─────────────────────────────────────────────────────────────────────────────

# ─── Company Management Routes ────────────────────────────────────────────────

@app.route('/configuration/companies')
@login_required
def get_companies():
    if not current_user.is_admin:
        return jsonify({'error': 'Access restricted.'}), 403
    result = []
    for c in get_all_companies():
        def _servers(etype):
            return [{'id': s.id, 'name': s.name}
                    for s in ExpectedServer.query.filter_by(company_id=c.id, email_type=etype).all()]
        result.append({
            'id': c.id,
            'name': c.name,
            'server': _servers('server'),
            'nas': _servers('nas'),
        })
    return jsonify(result)


@app.route('/configuration/companies/add', methods=['POST'])
@login_required
def add_company():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Access restricted.'}), 403
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'success': False, 'message': 'Company name is required.'})
    if Company.query.filter(db.func.lower(Company.name) == name.lower()).first():
        return jsonify({'success': False, 'message': f'Company "{name}" already exists.'})
    company = Company(name=name)
    db.session.add(company)
    db.session.commit()
    return jsonify({'success': True, 'id': company.id, 'name': company.name})


@app.route('/configuration/companies/rename', methods=['POST'])
@login_required
def rename_company():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Access restricted.'}), 403
    data = request.get_json() or {}
    company_id = data.get('company_id')
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'success': False, 'message': 'Company name is required.'})
    company = db.session.get(Company, company_id)
    if not company:
        return jsonify({'success': False, 'message': 'Company not found.'})
    if Company.query.filter(db.func.lower(Company.name) == name.lower(), Company.id != company_id).first():
        return jsonify({'success': False, 'message': f'Company "{name}" already exists.'})
    company.name = name
    db.session.commit()
    return jsonify({'success': True})


@app.route('/configuration/companies/delete', methods=['POST'])
@login_required
def delete_company():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Access restricted.'}), 403
    data = request.get_json() or {}
    company_id = data.get('company_id')
    company = db.session.get(Company, company_id)
    if not company:
        return jsonify({'success': False, 'message': 'Company not found.'})
    db.session.delete(company)
    db.session.commit()
    return jsonify({'success': True})


@app.route('/configuration/servers/add', methods=['POST'])
@login_required
def add_expected_server():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Access restricted.'}), 403
    data = request.get_json() or {}
    company_id = data.get('company_id')
    name = (data.get('name') or '').strip()
    email_type = (data.get('email_type') or '').strip()
    if not company_id or not name or not email_type:
        return jsonify({'success': False, 'message': 'Company, name, and type are required.'})
    if email_type not in ('server', 'nas'):
        return jsonify({'success': False, 'message': 'Invalid email type.'})
    if not db.session.get(Company, company_id):
        return jsonify({'success': False, 'message': 'Company not found.'})
    if ExpectedServer.query.filter(
        ExpectedServer.company_id == company_id,
        db.func.lower(ExpectedServer.name) == name.lower(),
        ExpectedServer.email_type == email_type
    ).first():
        return jsonify({'success': False, 'message': f'Server "{name}" already exists for this company and type.'})
    server = ExpectedServer(company_id=company_id, name=name, email_type=email_type)
    db.session.add(server)
    db.session.commit()
    return jsonify({'success': True, 'id': server.id})


@app.route('/configuration/servers/delete', methods=['POST'])
@login_required
def delete_expected_server():
    if not current_user.is_admin:
        return jsonify({'success': False, 'message': 'Access restricted.'}), 403
    data = request.get_json() or {}
    server_id = data.get('server_id')
    server = db.session.get(ExpectedServer, server_id)
    if not server:
        return jsonify({'success': False, 'message': 'Server not found.'})
    db.session.delete(server)
    db.session.commit()
    return jsonify({'success': True})

# ─────────────────────────────────────────────────────────────────────────────

# ─── JSON API endpoints (redesign step 2) ────────────────────────────────────

_EXCLUDE_COMPANIES = {
    'server': {'JSW Ltd', 'NHG Ltd', 'Bekat IT'},
    'nas':    {'BRB Ltd', 'eHeating Ltd', 'JS Wilson Ltd'},
}


def _relative_time(dt):
    seconds = int((datetime.now() - dt).total_seconds())
    if seconds < 60:
        return 'just now'
    if seconds < 3600:
        return f'{seconds // 60}m ago'
    if seconds < 86400:
        return f'{seconds // 3600}h ago'
    return f'{seconds // 86400}d ago'


def _latest_per_server(email_type):
    """Return the single most-recent BackupStatus row per server for the given email_type."""
    subq = (
        db.session.query(
            BackupStatus.server,
            db.func.max(BackupStatus.timestamp).label('max_ts')
        )
        .filter(BackupStatus.email_type == email_type)
        .group_by(BackupStatus.server)
        .subquery()
    )
    return (
        db.session.query(BackupStatus)
        .join(subq, db.and_(
            BackupStatus.server == subq.c.server,
            BackupStatus.timestamp == subq.c.max_ts,
        ))
        .filter(BackupStatus.email_type == email_type)
        .all()
    )


def _server_present(expected, records):
    """True if expected name is a substring of any record's raw or cleaned server name."""
    for r in records:
        if expected in r.server or expected in clean_server_name(r.server):
            return True
    return False


def _build_status_summary():
    """Shared JSON payload for /api/refresh-status and /api/refresh."""
    latest = BackupStatus.query.order_by(BackupStatus.timestamp.desc()).first()
    last_fetched = latest.timestamp.isoformat() if latest else None

    breakdown = {}
    total_servers = 0

    for email_type in ('server', 'nas'):
        records = _latest_per_server(email_type)
        total = len(records)
        successful = sum(1 for r in records if r.status == 'successful')
        unsuccessful = total - successful

        excluded = _EXCLUDE_COMPANIES[email_type]
        missing = 0
        for company in get_all_companies():
            if company.name in excluded:
                continue
            expected_list = get_expected_servers_for_company(company.id, email_type)
            company_records = [r for r in records if r.company == company.name]
            missing += sum(
                1 for e in expected_list if not _server_present(e, company_records)
            )

        breakdown[email_type] = {
            'total': total,
            'successful': successful,
            'unsuccessful': unsuccessful,
            'missing': missing,
        }
        total_servers += total

    scheduler_interval = int(get_config('scheduler_interval_minutes', '5') or '5')

    return {
        'last_fetched': last_fetched,
        'total_servers': total_servers,
        'breakdown': breakdown,
        'scheduler_interval_minutes': scheduler_interval,
    }


@app.route('/api/refresh-status')
@login_required
def api_refresh_status():
    return jsonify(_build_status_summary())


@app.route('/api/refresh', methods=['POST'])
@login_required
def api_refresh():
    check_email('server')
    check_email('nas')
    return jsonify(_build_status_summary())


@app.route('/api/servers')
@login_required
def api_servers():
    email_type = request.args.get('type', 'server')
    status_filter = request.args.get('status')
    q = request.args.get('q', '').strip().lower()

    excluded = _EXCLUDE_COMPANIES.get(email_type, set())

    all_records = _latest_per_server(email_type)

    display_records = all_records
    if status_filter:
        display_records = [r for r in display_records if r.status == status_filter]
    if q:
        display_records = [
            r for r in display_records
            if q in r.server.lower() or q in clean_server_name(r.server).lower()
        ]

    by_company = {}
    for record in display_records:
        company = record.company or 'Unknown'
        if company in excluded:
            continue
        by_company.setdefault(company, []).append(record)

    all_db_companies = get_all_companies()
    visible_expected = {c.name for c in all_db_companies if c.name not in excluded}
    all_companies = sorted(set(list(by_company.keys()) + list(visible_expected)))

    companies_out = []
    for company in all_companies:
        server_entries = [
            {
                'id': r.id,
                'server': r.server,
                'server_clean': clean_server_name(r.server),
                'company': r.company,
                'status': r.status,
                'timestamp': r.timestamp.isoformat(),
                'timestamp_relative': _relative_time(r.timestamp),
                'subject': r.subject,
                'is_latest': True,
            }
            for r in by_company.get(company, [])
        ]

        company_all_records = [r for r in all_records if r.company == company]
        missing_servers = [
            e for e in _get_expected_by_name(company, email_type)
            if not _server_present(e, company_all_records)
        ]

        if not server_entries and not missing_servers:
            continue

        companies_out.append({
            'name': company,
            'servers': server_entries,
            'missing': missing_servers,
        })

    return jsonify({'companies': companies_out})


# ─────────────────────────────────────────────────────────────────────────────

@app.route('/configuration/save-settings', methods=['POST'])
@login_required
def save_settings():
    data = request.get_json() or {}
    interval = data.get('scheduler_interval_minutes')
    ai_enabled = data.get('ai_parsing_enabled')

    if interval is not None:
        try:
            interval = int(interval)
            if not 1 <= interval <= 60:
                return jsonify({'success': False, 'message': 'Interval must be between 1 and 60 minutes'})
            set_config('scheduler_interval_minutes', str(interval))
            reschedule(interval)
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'Invalid interval value'})

    if ai_enabled is not None:
        set_config('ai_parsing_enabled', 'true' if ai_enabled else 'false')

    return jsonify({'success': True, 'message': 'Settings saved successfully'})


@app.route('/configuration/save-prompt', methods=['POST'])
@login_required
def save_prompt():
    data = request.get_json() or {}
    email_type = data.get('email_type', '').strip()
    prompt = data.get('prompt', '').strip()

    if not email_type or not prompt:
        return jsonify({'success': False, 'message': 'Email type and prompt are required'})
    if email_type not in ('server', 'nas'):
        return jsonify({'success': False, 'message': 'Invalid email type'})

    set_config(f'ai_prompt_{email_type}', prompt)
    return jsonify({'success': True, 'message': 'Prompt saved successfully'})


@app.route('/configuration/reset-prompt', methods=['POST'])
@login_required
def reset_prompt():
    data = request.get_json() or {}
    email_type = data.get('email_type', '').strip()

    if not email_type or email_type not in ('server', 'nas'):
        return jsonify({'success': False, 'message': 'Invalid email type'})

    default = DEFAULT_SERVER_PROMPT if email_type == 'server' else DEFAULT_NAS_PROMPT
    set_config(f'ai_prompt_{email_type}', default)
    return jsonify({'success': True, 'message': 'Prompt reset to default', 'prompt': default})


# Configure session handling
@app.teardown_appcontext
def shutdown_session(exception=None):
    """Clean up the database session at the end of each request."""
    if exception:
        db.session.rollback()
    db.session.close()


start_background_jobs()

if __name__ == '__main__':
    update_existing_companies()  # TEMP: update company names in DB after mapping change
    app.run(host='0.0.0.0', port=5000, debug=False)