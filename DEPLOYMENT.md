# Deployment Guide: Backup Status Dashboard on Ubuntu

This guide outlines the steps to deploy the Backup Status Dashboard (a Python Flask application) to an Ubuntu server. We'll use Gunicorn as the WSGI HTTP server and Nginx as a reverse proxy. `systemd` will be used to manage the Gunicorn process.

## Prerequisites

1.  **Ubuntu Server**: Access to an Ubuntu server (e.g., via SSH).
2.  **Sudo Privileges**: You'll need `sudo` access to install packages and configure services.
3.  **Git**: `git` installed on the server (`sudo apt update && sudo apt install git`).
4.  **Python 3 & Pip**: Python 3 and `pip` installed on the server.
    ```bash
    sudo apt update
    sudo apt install python3 python3-pip python3-venv
    ```
5.  **Domain Name (Optional)**: If you want to access the dashboard via a domain name, ensure it's configured to point to your server's IP address.

## Deployment Steps

### 1. Clone the Repository

Connect to your Ubuntu server via SSH and clone the project repository:

```bash
git clone https://github.com/bekaheni/Backup-Status.git
cd Backup-Status
```

### 2. Set Up Python Virtual Environment & Install Dependencies

Create a Python virtual environment and activate it:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install the required Python packages:

```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables

The application uses a `.env` file for configuration.

a.  **Copy the example file:**

    ```bash
    cp .env.example .env
    ```

b.  **Edit `.env`:**
    Open `.env` with a text editor (like `nano` or `vim`) and fill in your Gmail Client ID and Client Secret:

    ```env
    GMAIL_CLIENT_ID='YOUR_GMAIL_CLIENT_ID'
    GMAIL_CLIENT_SECRET='YOUR_GMAIL_CLIENT_SECRET'
    # Leave FLASK_ENV as production for deployment
    FLASK_ENV='production'
    # You can change the FLASK_APP if your main app file is different, but it's app.py
    FLASK_APP='app.py'
    # You can change the SECRET_KEY to a new random string for better security
    SECRET_KEY='your_strong_random_secret_key'
    ```
    Replace `'YOUR_GMAIL_CLIENT_ID'` and `'YOUR_GMAIL_CLIENT_SECRET'` with your actual credentials. Generate a new `SECRET_KEY`.

### 4. Generate Gmail OAuth Token (`gmail_token.json`)

The application requires `gmail_token.json` for OAuth2 authentication with Gmail. You'll need to run the `gmail_oauth_setup.py` script *on the server* to generate this token.

a.  **Temporarily allow access:**
    Since your server likely doesn't have a graphical browser, you might need to run this script on a local machine that *does* have a browser, using the server's `credentials.json` (if the redirect URIs allow it). Alternatively, if your Google Cloud OAuth consent screen is configured for "Desktop app", you can run it on the server. The script will print a URL. You need to open this URL in a browser on any machine, authorize the application, and then paste the authorization code back into the terminal on the server.

    **Important:** Ensure your `credentials.json` (downloaded from Google Cloud Console, usually named `client_secret_....json` and renamed to `credentials.json` for the setup script) is present in the project root on the server before running the script.

b.  **Run the setup script (ensure your virtual environment is active):**

    ```bash
    python gmail_oauth_setup.py
    ```
    Follow the on-screen instructions. This will create `gmail_token.json` in the project root.

c.  **Secure the token:**
    The `gmail_token.json` file is sensitive. Ensure its permissions are restrictive if necessary, though `.gitignore` should prevent it from being re-committed.

### 5. Test Gunicorn

Gunicorn will serve your Flask application.

a.  **Install Gunicorn (if not already in `requirements.txt`, add it and `pip install gunicorn`):**
    It's good practice to have gunicorn in your requirements:
    ```bash
    pip install gunicorn
    # (then update your local requirements.txt and commit the change)
    # echo "gunicorn" >> requirements.txt
    ```
    Make sure Gunicorn is in your `requirements.txt`. If not, add it and reinstall requirements.

b.  **Test Gunicorn:**
    From your project root (`/Backup-Status`), with the virtual environment active, run:

    ```bash
    gunicorn --workers 3 --bind 0.0.0.0:8000 app:app
    ```
    *   `app:app` refers to the `app` Flask instance inside your `app.py` file.
    *   This will start Gunicorn on port 8000, accessible from any IP.
    *   You can test this by navigating to `http://YOUR_SERVER_IP:8000` in a browser.
    *   Press `Ctrl+C` to stop Gunicorn.

### 6. Set Up Nginx as a Reverse Proxy

Nginx will sit in front of Gunicorn, handling incoming HTTP requests and passing them to Gunicorn. It can also serve static files and handle SSL.

a.  **Install Nginx:**

    ```bash
    sudo apt install nginx
    ```

b.  **Create an Nginx Server Block File:**
    Create a new Nginx configuration file for your application. Replace `your_domain_or_IP` with your server's domain name or IP address.

    ```bash
    sudo nano /etc/nginx/sites-available/backup_status
    ```

    Paste the following configuration into the file:

    ```nginx
    server {
        listen 80;
        server_name your_domain_or_IP; # Replace with your server's IP or domain

        location / {
            proxy_pass http://127.0.0.1:8000; # Points to Gunicorn
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location /static {
            alias /path/to/your/Backup-Status/static; # Replace with actual path
        }
    }
    ```
    **Important**:
    *   Update `your_domain_or_IP`.
    *   Update `/path/to/your/Backup-Status/static` with the absolute path to your project's `static` directory (e.g., `/home/your_user/Backup-Status/static` or `/var/www/Backup-Status/static` if you move it there). If your app serves static files directly through Flask and Gunicorn (common for smaller apps), you might not strictly need the `location /static` block, but it's good practice for Nginx to handle them. Your current `index.html` references Materialize CSS via CDN, so this static block might be less critical for now unless you add local static assets.

c.  **Enable the Nginx Server Block:**
    Create a symbolic link from `sites-available` to `sites-enabled`:

    ```bash
    sudo ln -s /etc/nginx/sites-available/backup_status /etc/nginx/sites-enabled/
    ```

d.  **Test Nginx Configuration and Restart Nginx:**

    ```bash
    sudo nginx -t
    ```
    If the test is successful, restart Nginx:
    ```bash
    sudo systemctl restart nginx
    ```

### 7. Set Up `systemd` to Manage Gunicorn

Using `systemd`, Gunicorn will run as a service, starting on boot and restarting if it fails.

a.  **Create a `systemd` Service File:**

    ```bash
    sudo nano /etc/systemd/system/backup_status.service
    ```

    Paste the following configuration. **Adjust paths and User/Group as necessary.**

    ```ini
    [Unit]
    Description=Gunicorn instance for Backup Status Dashboard
    After=network.target

    [Service]
    User=your_user # Replace with the user that owns the Backup-Status directory
    Group=www-data # Or the group of your_user
    WorkingDirectory=/path/to/your/Backup-Status # Replace with actual path
    Environment="PATH=/path/to/your/Backup-Status/venv/bin" # Replace with actual path
    ExecStart=/path/to/your/Backup-Status/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 app:app

    Restart=always

    [Install]
    WantedBy=multi-user.target
    ```
    **Important**:
    *   Replace `your_user` with the actual username that will run the application (e.g., `ubuntu`, or a dedicated user you create). This user should have ownership/read/execute permissions for the project files and virtual environment.
    *   Replace `/path/to/your/Backup-Status` with the absolute path to your project directory (e.g., `/home/your_user/Backup-Status`).
    *   Ensure the path to `gunicorn` and `venv/bin` in `Environment` and `ExecStart` are correct.

b.  **Start and Enable the Service:**

    ```bash
    sudo systemctl daemon-reload
    sudo systemctl start backup_status
    sudo systemctl enable backup_status
    ```

c.  **Check Service Status:**

    ```bash
    sudo systemctl status backup_status
    ```
    You can also check its logs:
    ```bash
    sudo journalctl -u backup_status
    ```

### 8. Configure Firewall (UFW)

If you're using `ufw` (Uncomplicated Firewall), allow Nginx traffic:

```bash
sudo ufw allow 'Nginx Full' # Allows both HTTP and HTTPS
sudo ufw enable # If not already enabled
sudo ufw status
```

## Accessing the Dashboard

You should now be able to access your Backup Status Dashboard by navigating to `http://your_domain_or_IP` in your web browser.

## Notes and Troubleshooting

*   **Permissions**: Ensure file and directory permissions are correctly set, especially for the user running Gunicorn.
*   **Logs**:
    *   Nginx logs: `/var/log/nginx/access.log` and `/var/log/nginx/error.log`.
    *   Gunicorn/Application logs (via systemd): `sudo journalctl -u backup_status`.
    *   Flask application's own logging (if configured to write to files, check `app.py`).
*   **`FLASK_ENV=production`**: For production, Flask disables the interactive debugger and uses more performant settings.
*   **Database**: The `instance/backup_status.db` SQLite file will be created/used within the project directory. Ensure the Gunicorn process has write permissions to the `instance` directory and the database file if it needs to create or modify it.
*   **APScheduler**: The `APScheduler` is configured to run within the Flask app process. When Gunicorn runs with multiple workers, be mindful of how schedulers behave. For simple tasks like this, it's often fine, but for critical or resource-intensive scheduled tasks, a separate worker process or a dedicated scheduling system (like Celery with a message broker, or cron) might be considered in more complex applications. Given your current setup, it should run in one of the Gunicorn worker processes.

--- 