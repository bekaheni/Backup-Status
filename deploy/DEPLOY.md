# Deployment Runbook — backup-status

Target directory: `/opt/backup-status`
Domain: `backup.bekat.co.uk`

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
2. `nano .env`
3. Paste and fill in the following:
   ```
   FLASK_ENV=production
   FLASK_APP=app.py
   SECRET_KEY=<generate with: python3 -c "import secrets; print(secrets.token_hex(32))">
   GMAIL_CLIENT_ID=<from credentials.json>
   GMAIL_CLIENT_SECRET=<from credentials.json>
   ```
4. Save and exit nano (`Ctrl+O`, `Enter`, `Ctrl+X`).
5. `chmod 600 .env`
6. Copy `gmail_token.json` and `credentials.json` into `/opt/backup-status/` if not already present.
7. Run database migrations: `flask db upgrade`

---

## 4. Install the systemd service

1. `sudo cp /opt/backup-status/deploy/backup-status.service /etc/systemd/system/backup-status.service`
2. `sudo systemctl daemon-reload`
3. `sudo systemctl enable backup-status`
4. `sudo systemctl start backup-status`
5. `sudo systemctl status backup-status`

---

## 5. Configure Nginx

1. `sudo apt install nginx -y`
2. `sudo cp /opt/backup-status/deploy/backup-status.nginx /etc/nginx/sites-available/backup-status`
3. `sudo ln -s /etc/nginx/sites-available/backup-status /etc/nginx/sites-enabled/backup-status`
4. `sudo nginx -t`
5. `sudo systemctl reload nginx`

---

## 6. Obtain the SSL certificate

1. `sudo apt install certbot python3-certbot-nginx -y`
2. `sudo certbot --nginx -d backup.bekat.co.uk`
3. Follow the prompts; certbot will update the Nginx config automatically.
4. `sudo systemctl reload nginx`
5. Verify auto-renewal: `sudo certbot renew --dry-run`
