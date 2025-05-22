# Backup Status Dashboard

A Python-based web dashboard that monitors a Gmail inbox for backup status messages and displays them in a modern, responsive card interface. Clicking on a device card reveals the full backup status email in a modal window.

## Features

- Monitors a Gmail inbox for backup status messages using OAuth2 authentication
- Displays backup status in a modern, responsive card interface
- Click any device card to view the full backup status email in a modal
- Auto-refreshes every 5 minutes
- Stores backup history in an SQLite database using SQLAlchemy
- Secure credential management using environment variables and OAuth tokens
- Designed for production deployment with Gunicorn and Nginx

## Setup

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file based on `.env.example`:
   ```bash
   cp .env.example .env
   ```

4. Edit the `.env` file:
   - Set a strong `SECRET_KEY` (see DEPLOYMENT.md for details)
   - Other values are typically fine as provided

5. Set up Gmail OAuth:
   - Download your `credentials.json` from Google Cloud Console and place it in the project root
   - Run the setup script to generate `gmail_token.json`:
     ```bash
     python gmail_oauth_setup.py
     ```
   - Follow the on-screen instructions to authorise access

## Running the Application (Development)

1. Start the application:
   ```bash
   python app.py
   ```

2. Open your browser and navigate to:
   ```
   http://localhost:5000
   ```

## Running in Production

- Use Gunicorn as the WSGI server and Nginx as a reverse proxy (see DEPLOYMENT.md for full instructions):
  ```bash
  gunicorn --workers 3 --bind 0.0.0.0:8000 app:app
  ```
- Configure Nginx to proxy requests to Gunicorn and serve static files

## Email Configuration

- The application looks for backup status emails in your Gmail inbox
- Make sure your backup system sends emails with clear status information
- The dashboard displays the most recent backup status for each device
- Clicking a device card shows the full email content in a modal

## Security Notes

- Never commit your `.env`, `gmail_token.json`, or `credentials.json` to version control
- Use strong, unique secrets for your `.env` file
- Keep your dependencies updated

## Troubleshooting

If you encounter any issues:
1. Check your `.env` and OAuth token setup
2. Ensure your Gmail account and Google Cloud project are configured correctly
3. Check the console output for any error messages
4. See DEPLOYMENT.md for more advanced deployment and troubleshooting tips
