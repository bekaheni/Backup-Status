# Backup Status Dashboard

A Python-based web dashboard that monitors an email inbox for backup status messages and displays them in a modern Material Design interface.

## Features

- Monitors email inbox for backup status messages
- Displays status in a Material Design card interface
- Auto-refreshes every 5 minutes
- Stores backup history in SQLite database
- Secure credential management using environment variables

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

4. Edit the `.env` file with your email credentials:
   - For Gmail, you'll need to use an App Password
   - For other email providers, adjust the IMAP_SERVER accordingly

## Running the Application

1. Start the application:
   ```bash
   python app.py
   ```

2. Open your browser and navigate to:
   ```
   http://localhost:5000
   ```

## Email Configuration

- The application looks for emails with subjects containing "backup successful" or "backup unsuccessful"
- Make sure your backup system sends emails with these exact phrases in the subject line
- The dashboard will display the most recent backup status

## Security Notes

- Never commit your `.env` file to version control
- Use app-specific passwords for email access
- Keep your dependencies updated

## Troubleshooting

If you encounter any issues:
1. Check your email credentials in the `.env` file
2. Ensure your email provider allows IMAP access
3. Check the console output for any error messages
