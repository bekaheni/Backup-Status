# Deployment Runbook — backup-status

Target directory: `/opt/backup-status`
Domain: `backup.bekat.co.uk`

> Note: the git clone URL should be verified against your actual repository before running.

---

## 1. Pull the code

1. `sudo mkdir -p /opt/backup-status`
2. `sudo chown ubuntu:ubuntu /opt/backup-status`
3. `cd /opt/backup-status`
4. `git clone https://github.com/bekaheni/Backup-Status.git .`

---

## 2. Set up the virtual environment

1. `cd /opt/backup-status`
2. `python3 -m venv venv`
3. `source venv/bin/activate`
4. `pip install -r requirements.txt`

---

## 3. Create the env file

1. `cd /opt/backup-status`
2. Generate a SECRET_KEY by running: `python3 -c "import secrets; print(secrets.token_hex(32))"`
3. `nano .env`
4. Paste and fill in the following:
   ```
   FLASK_ENV=production
   FLASK_APP=app.py
   SECRET_KEY=<paste generated key here>
   EMAIL=<your email address>
   EMAIL_PASSWORD=<your email password>
   IMAP_SERVER=<your IMAP server, e.g. imap.gmail.com>
   INBOX_NAME=<inbox folder name, e.g. INBOX>
   NAS_EMAIL=<NAS email address>
   NAS_EMAIL_PASSWORD=<NAS email password>
   NAS_IMAP_SERVER=<NAS IMAP server>
   NAS_INBOX_NAME=<NAS inbox folder name, e.g. INBOX>
   ```
5. Save and exit nano (`Ctrl+O`, `Enter`, `Ctrl+X`).
6. `chmod 600 .env`

---

## 4. Install the systemd service

1. `sudo cp /opt/backup-status/deploy/backup-status.service /etc/systemd/system/backup-status.service`
2. `sudo systemctl daemon-reload`
3. `sudo systemctl enable backup-status`
4. `sudo systemctl start backup-status`
5. `sudo systemctl status backup-status`

---

## 5. Configure Nginx

1. `sudo cp /opt/backup-status/deploy/backup-status.nginx /etc/nginx/sites-available/backup-status`
2. `sudo ln -s /etc/nginx/sites-available/backup-status /etc/nginx/sites-enabled/backup-status`
3. `sudo nginx -t`
4. `sudo systemctl reload nginx`

---

## 6. Obtain the SSL certificate

1. `sudo certbot --nginx -d backup.bekat.co.uk`
2. Follow the prompts; certbot will update the Nginx config automatically.
3. `sudo systemctl reload nginx`
4. Verify auto-renewal: `sudo certbot renew --dry-run`
