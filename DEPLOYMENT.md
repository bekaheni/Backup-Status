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
6.  **Application Directory**: Create the directory where the application will live and set appropriate ownership. It's common practice to use `/var/www/` for web applications.

    ```bash
    sudo mkdir -p /var/www/backup-status
    # Replace 'your_user' with the user that will run the Gunicorn process
    # This user should be the same one specified in the systemd service file
    sudo chown -R adminlocal:adminlocal /var/www/backup-status
    # It's also common to use www-data as the group:
    # sudo chown -R adminlocal:www-data /var/www/backup-status
    sudo chmod -R 755 /var/www/backup-status
    ```
    You will clone your application into `/var/www/backup-status` later.

## Deployment Steps

### 1. Clone the Repository

Connect to your Ubuntu server via SSH. Navigate to the directory you created for the application (`/var/www/backup-status`) and then clone the project repository:

```bash
cd /var/www/backup-status
# Clone the repository into the current directory
git clone https://github.com/bekaheni/Backup-Status.git .
```
This guide will assume the project files are directly under `/var/www/backup-status`.

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

The application uses a `.env` file for configuration. This file should not be committed to Git if it contains secrets (ensure it's in your `.gitignore` file).

a.  **Copy the example file:**
    The `.env.example` file in the repository provides the template for your `.env` file.

    ```bash
    cp .env.example .env
    ```

b.  **Edit `.env` using `nano`:**
    Open the newly created `.env` file using the `nano` text editor:
    ```bash
    nano .env
    ```
    The main purpose of editing this `.env` file is to set a unique `SECRET_KEY` for your application's security. Other values are generally fine as set by the `.env.example` template or are handled elsewhere.

    Here's what the content will look like. Focus on changing `SECRET_KEY`:

    ```env
    # Optional: For reference. The OAuth setup script (gmail_oauth_setup.py)
    # uses credentials.json for Client ID/Secret, not these values.
    GMAIL_CLIENT_ID='YOUR_GMAIL_CLIENT_ID_PLACEHOLDER'
    GMAIL_CLIENT_SECRET='YOUR_GMAIL_CLIENT_SECRET_PLACEHOLDER'

    # Flask settings (usually leave as is for this project)
    FLASK_ENV='production'
    FLASK_APP='app.py'

    # --- MANDATORY CHANGE --- #
    # Replace the placeholder below with a real, strong, unique secret key.
    # Generate one using: python -c "import secrets; print(secrets.token_hex(32))"
    SECRET_KEY='your_very_strong_random_secret_key_here'
    # --- END MANDATORY CHANGE --- #
    ```
    **Key actions for the `.env` file:**

    *   **`SECRET_KEY`**: **This is the most important setting you MUST change.** Replace the placeholder `'your_very_strong_random_secret_key_here'` with a long, random, and unique string. This is critical for securing user sessions. The comment block above this line in the file shows a command you can run on your server to generate a suitable key.

    *   **`GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET`**: You can generally leave these with their placeholder values (e.g., `'YOUR_GMAIL_CLIENT_ID_PLACEHOLDER'`). The script that sets up Gmail access (`gmail_oauth_setup.py`, covered in Section 4) uses your separate `credentials.json` file for the actual Client ID and Secret, not these lines in `.env`. If you do wish to populate these for your own reference in the `.env` file, the values can be found within your `credentials.json` file (which you download from the Google Cloud Console).

    *   **`FLASK_ENV` / `FLASK_APP`**: For this project, these are typically left as `production` and `app.py` respectively, as they were copied from the `.env.example` file.

    **Nano Editor Tips:**
    *   **Pasting**: To paste text (e.g., your Client ID, Secret, or generated Secret Key), you can usually use `Ctrl+Shift+V` (on Linux desktops) or `Right-click` -> `Paste` in your SSH terminal window. Some terminals might use other shortcuts like `Shift+Insert`.
    *   **Saving Changes**: Press `Ctrl+O` (the letter O, not zero), then `Enter` to confirm the filename (`.env`).
    *   **Exiting Nano**: Press `Ctrl+X`.

### 4. Generate Gmail OAuth Token (`gmail_token.json`)

The application requires `gmail_token.json` for OAuth2 authentication with Gmail. 

**Option 1: Copying an Existing Token (Recommended if available and valid)**
If you have already run the `gmail_oauth_setup.py` script (e.g., during local development or on another machine using the *exact same* `credentials.json` that you will use on this server) and have a valid `gmail_token.json`, you can securely copy this existing file to the project root (`/var/www/backup-status/`) on the server. 

*   **How to Copy**: You can use `scp` (Secure Copy Protocol) from your local machine's terminal or an SFTP client (like FileZilla, WinSCP).
    *   **Using `scp` (Command Line):** 
        The general format is: `scp -P <Port_If_Not_22> /path/to/local/gmail_token.json your_user@your_server_ip_or_domain:/path/to/destination/gmail_token.json`

        **Example for a specific setup:**
        If your `gmail_token.json` is at `c:\1\gmail_token.json` on your local Windows machine, your server username is `adminlocal`, your server domain is `serverstatus.bekat.co.uk`, your SSH port is `2323`, and the destination is `/var/www/backup-status/`, the command (run from your local Windows terminal like PowerShell or Git Bash) would be:
        ```bash
        # If using PowerShell/CMD with native OpenSSH scp.exe:
        scp -P 2323 c:\1\gmail_token.json adminlocal@serverstatus.bekat.co.uk:/var/www/backup-status/gmail_token.json

        # If using Git Bash or WSL (note the local path format /c/1/...):
        # scp -P 2323 /c/1/gmail_token.json adminlocal@serverstatus.bekat.co.uk:/var/www/backup-status/gmail_token.json
        ```
        Remember to adjust the local path format (`c:\...` vs `/c/...`) depending on the terminal you use on your local Windows machine.

    *   **Using an SFTP Client (Graphical):** Connect to your server using its IP/domain, your username, password/SSH key, and the SSH port if it's not the default (22). Then navigate to `/var/www/backup-status/` on the server and upload your local `gmail_token.json` file.

*   **Caution**: Ensure this `gmail_token.json` corresponds to the `credentials.json` you are using for this deployment and has the correct scopes. 
*   If you use this method, you can skip step 4b (Run the setup script) below. If in doubt, proceed with Option 2 to generate a new token on the server.

**Option 2: Generating a New Token on the Server**
If you don't have an existing valid token, or prefer to generate one fresh on the server, you'll need to run the `gmail_oauth_setup.py` script *on the server* as described below.

a.  **Prerequisites for generating a new token:**
    *   Ensure your `credentials.json` (downloaded from Google Cloud Console for your project) is present in the project root on the server.
    *   You'll need a way to access a web browser to authorize the application, as the script will provide a URL.

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
    From your project root (`/var/www/backup-status`), with the virtual environment active, run:

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
        listen 81;
        server_name your_domain_or_IP; # Replace with your server's IP or domain

        location / {
            proxy_pass http://127.0.0.1:8000; # Points to Gunicorn
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location /static {
            alias /var/www/backup-status/static; # Path to static files
        }
    }
    ```
    **Important**:
    *   Update `your_domain_or_IP`.
    *   The `alias /var/www/backup-status/static;` line should point to the absolute path to your project's `static` directory. If your app serves static files directly through Flask and Gunicorn (common for smaller apps), you might not strictly need the `location /static` block, but it's good practice for Nginx to handle them. Your current `index.html` references Materialize CSS via CDN, so this static block might be less critical for now unless you add local static assets.

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
    User=adminlocal # Replace with the user that owns the Backup-Status directory
    Group=www-data # Or the group of your_user
    WorkingDirectory=/var/www/backup-status
    Environment="PATH=/var/www/backup-status/venv/bin"
    ExecStart=/var/www/backup-status/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 app:app

    Restart=always

    [Install]
    WantedBy=multi-user.target
    ```
    **Important**:
    *   Replace `your_user` (now `adminlocal`) with the actual username that will run the application. This user (`adminlocal`) should have ownership/read/execute permissions for the project files and virtual environment.
    *   The `WorkingDirectory`, `Environment` PATH, and `ExecStart` path should point to `/var/www/backup-status` and its subdirectories.
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

If you're using `ufw` (Uncomplicated Firewall), allow Nginx traffic. Since Nginx will be listening on port 81 for this application:

```bash
sudo ufw allow 81/tcp  # Allow traffic to port 81
# If you have another application using Nginx on port 80, you might already have 'Nginx Full' or port 80 allowed.
# sudo ufw allow 'Nginx Full' # This allows both HTTP (80) and HTTPS (443)
sudo ufw enable      # If not already enabled
sudo ufw status
```

## Accessing the Dashboard

You should now be able to access your Backup Status Dashboard by navigating to `http://your_domain_or_IP:81` in your web browser (note the `:81` if you changed the port).

## Notes and Troubleshooting

*   **Permissions**: Ensure file and directory permissions are correctly set, especially for the user running Gunicorn.
*   **Logs**:
    *   Nginx logs: `/var/log/nginx/access.log` and `/var/log/nginx/error.log`.
    *   Gunicorn/Application logs (via systemd): `sudo journalctl -u backup_status`.
    *   Flask application's own logging (if configured to write to files, check `app.py`).
*   **`FLASK_ENV=production`**: For production, Flask disables the interactive debugger and uses more performant settings.
*   **Database**: The `instance/backup_status.db` SQLite file will be created/used within the project directory (e.g., `/var/www/backup-status/instance/backup_status.db`). Ensure the Gunicorn process has write permissions to the `instance` directory and the database file if it needs to create or modify it.
*   **APScheduler**: The `APScheduler` is configured to run within the Flask app process. When Gunicorn runs with multiple workers, be mindful of how schedulers behave. For simple tasks like this, it's often fine, but for critical or resource-intensive scheduled tasks, a separate worker process or a dedicated scheduling system (like Celery with a message broker, or cron) might be considered in more complex applications. Given your current setup, it should run in one of the Gunicorn worker processes.

--- 