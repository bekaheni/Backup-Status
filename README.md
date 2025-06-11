# Backup Status Dashboard

A Flask-based web application that monitors and displays the status of server and NAS backups by parsing email notifications.

## Features

- Real-time backup status monitoring
- Email parsing for both server and NAS backup notifications
- Web dashboard with status indicators
- Automatic email checking
- Company-based organization of backup statuses

## Project Structure

- `app.py` - Main application file
- `utils.py` - Utility functions for email parsing
- `templates/` - HTML templates
- `static/` - CSS and JavaScript files
- `tests/` - Test files
- `migrations/` - Database migration files

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure email settings in `app.py`:
```python
EMAIL = "your-email@example.com"
PASSWORD = "your-password"
IMAP_SERVER = "imap.example.com"
```

3. Initialize the database:
```bash
flask db upgrade
```

4. Run the application:
```bash
python app.py
```

## Testing

Run tests using pytest:
```bash
python -m pytest tests/
```

## Deployment

See `DEPLOYMENT.md` for detailed deployment instructions.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
