@echo off
echo ========================================
echo   Backup Status Dashboard Setup
echo ========================================
echo.

REM Check if Python is installed
echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://python.org
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

echo Python found. Creating virtual environment...
if exist venv (
    echo Virtual environment already exists.
) else (
    python -m venv venv
    echo Virtual environment created.
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing dependencies...
pip install -r requirements.txt

echo Creating .env file if it doesn't exist...
if not exist .env (
    echo Creating default .env file...
    (
        echo FLASK_ENV=development
        echo FLASK_APP=app.py
        echo SECRET_KEY=dev_secret_key_for_local_development_only
        echo EMAIL=your_server_email@example.com
        echo EMAIL_PASSWORD=your_server_email_password
        echo IMAP_SERVER=mail.remoteone.uk
        echo INBOX_NAME=INBOX
        echo NAS_EMAIL=your_nas_email@example.com
        echo NAS_EMAIL_PASSWORD=your_nas_email_password
        echo NAS_IMAP_SERVER=mail.remoteone.uk
        echo NAS_INBOX_NAME=INBOX
        echo GMAIL_CLIENT_ID=YOUR_GMAIL_CLIENT_ID_PLACEHOLDER
        echo GMAIL_CLIENT_SECRET=YOUR_GMAIL_CLIENT_SECRET_PLACEHOLDER
    ) > .env
    echo Created .env file with default settings
    echo.
    echo IMPORTANT: Please edit .env file with your actual email credentials
    echo You can find the .env file in your project directory
    echo.
)

echo ========================================
echo   Starting Backup Status Dashboard
echo ========================================
echo.
echo The application will be available at: http://localhost:5000
echo.
echo Login credentials:
echo   Username: admin
echo   Password: admin123
echo.
echo Press Ctrl+C to stop the application
echo ========================================
echo.

python app.py

echo.
echo Application stopped.
pause 