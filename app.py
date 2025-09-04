import os
import re
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
from utils import SERVER_COMPANIES, get_company_for_server

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
        
        # Try to find multiple server entries in the email
        # Look for all server name and ID patterns
        server_matches = re.findall(r'([A-Za-z0-9]+)\s*\(([A-Za-z0-9]+)\)', body)
        print(f"Found {len(server_matches)} server patterns: {server_matches}")
        
        # Look for all status patterns
        status_matches = re.findall(r'(Success|Failed|Overdue)', body)
        print(f"Found {len(status_matches)} status patterns: {status_matches}")
        
        # Look for timestamp
        time_match = re.search(r'(\d{2}\s+\w{3}\s+\d{4}\s+\d{2}:\d{2})', body)
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
                    statuses = parse_backup_status(body, email_timestamp)
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
                             total_servers=total_servers,
                             status_count=status_count,
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
                              total_servers=total_servers,
                              status_count=status_count,
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
            status.company = get_company_for_server(status.server)
        db.session.commit()
        print("Updated all records with new company information")

def init_db():
    """Initialize the database."""
    with app.app_context():
        # Drop all tables and recreate them
        db.drop_all()
        db.create_all()
        print("Database initialized")

def start_background_jobs():
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

@app.route('/parsing-logic')
def parsing_logic():
    return render_template('parsing_logic.html')

@app.route('/template')
def template_page():
    from flask_login import current_user
    # Provide dummy values for last_update and total_servers for template testing
    return render_template('template.html', last_update='2025-06-12 22:20', total_servers=16, current_user=current_user)

@app.route('/configuration')
def configuration_page():
    from flask_login import current_user
    server_inbox = os.getenv('EMAIL', 'not set')
    nas_inbox = os.getenv('NAS_EMAIL', 'not set')
    return render_template('configuration.html', current_user=current_user, server_inbox=server_inbox, nas_inbox=nas_inbox)

@app.route('/test-route')
def test_route():
    return "Test route is working!"

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

if __name__ == '__main__':
    start_background_jobs()
    update_existing_companies()  # TEMP: update company names in DB after mapping change
    app.run(host='0.0.0.0', port=5000, debug=False)

# Configure session handling
@app.teardown_appcontext
def shutdown_session(exception=None):
    """Clean up the database session at the end of each request."""
    if exception:
        db.session.rollback()
    db.session.close() 