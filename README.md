# CoreSight Backup Status

CoreSight Backup Status is a Flask web dashboard that monitors server and NAS backup statuses by connecting to two IMAP mailboxes, parsing incoming backup notification emails, storing results in a SQLite database, and displaying them grouped by company with live status updates.

## Features

- Two separate dashboards for server backups and NAS backups
- Automatic email polling every 5 minutes via APScheduler
- Needs Attention panel highlighting failed and missing servers
- Safe Fetch Now button for on-demand refresh without data loss
- Client-side search and status filtering
- 60-second background polling that updates stats without page reload
- Email detail modal showing the original backup notification
- Danger Zone on the Configuration page for database clearing and old email deletion
- Login-protected access via Flask-Login

## Tech Stack

- Flask
- SQLAlchemy with SQLite
- APScheduler
- Flask-Login
- Flask-Migrate
- Gunicorn
- Nginx

## Architecture

APScheduler triggers `check_email` every 5 minutes, which connects to each mailbox via IMAP, parses backup notification emails using `parse_backup_status` or `parse_nas_backup_status`, and stores results in the `BackupStatus` table. Flask routes and JSON API endpoints serve the stored data to the browser dashboard, which polls for updates every 60 seconds client-side.

## Installation

```bash
git clone <repo-url>
cd CoreSightBackup
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your values
python app.py
```

## Configuration

The following environment variables are required in `.env`:

| Variable | Description |
|---|---|
| `SECRET_KEY` | Flask secret key for session signing |
| `EMAIL` | Email address for the server backup mailbox |
| `EMAIL_PASSWORD` | Password or app password for the server backup mailbox |
| `IMAP_SERVER` | IMAP hostname for the server backup mailbox |
| `INBOX_NAME` | Mailbox folder name to monitor for server backup emails |
| `NAS_EMAIL` | Email address for the NAS backup mailbox |
| `NAS_EMAIL_PASSWORD` | Password or app password for the NAS backup mailbox |
| `NAS_IMAP_SERVER` | IMAP hostname for the NAS backup mailbox |
| `NAS_INBOX_NAME` | Mailbox folder name to monitor for NAS backup emails |

## Production Deployment

See `deploy/DEPLOY.md` for full production setup instructions covering Nginx, SSL, and systemd.

## Updating

To deploy updates on the production server:

```bash
git pull
pip install -r requirements.txt
sudo systemctl restart backup-status
```

## File Structure

```
CoreSightBackup/
├── app.py                  # Application entry point, routes, scheduler
├── utils.py                # Email parsing logic
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (not committed)
├── templates/
│   ├── base.html
│   ├── index.html          # Server backup dashboard
│   ├── nas.html            # NAS backup dashboard
│   ├── config.html         # Configuration page
│   └── login.html
├── static/
│   ├── css/
│   └── js/
├── deploy/
│   ├── backup-status.service
│   ├── nginx.conf
│   └── DEPLOY.md
└── backup_status.db        # SQLite database
```
