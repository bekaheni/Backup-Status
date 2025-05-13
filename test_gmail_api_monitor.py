from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import json
import base64
import email
from datetime import datetime, timedelta

print("Starting Gmail API Monitor test...")

# Load credentials from gmail_token.json
try:
    with open('gmail_token.json', 'r') as token_file:
        creds_data = json.load(token_file)
    print("Successfully loaded credentials file")
    print("Available scopes:", creds_data.get('scopes', []))
except Exception as e:
    print(f"Error loading credentials file: {e}")
    exit(1)

try:
    creds = Credentials.from_authorized_user_info(creds_data)
    
    # Refresh the token if necessary
    if not creds.valid:
        print("Token invalid, refreshing...")
        if creds.refresh_token:
            creds.refresh(Request())
            # Save the refreshed credentials
            with open('gmail_token.json', 'w') as token_file:
                token_data = {
                    'token': creds.token,
                    'refresh_token': creds.refresh_token,
                    'token_uri': creds.token_uri,
                    'client_id': creds.client_id,
                    'client_secret': creds.client_secret,
                    'scopes': creds.scopes
                }
                json.dump(token_data, token_file)
            print("Token refreshed and saved")
        else:
            print("No refresh token available!")
            exit(1)
    
    print("Successfully created credentials object")
    
    # Create Gmail API service
    service = build('gmail', 'v1', credentials=creds)
    
    # Test API access by getting user profile
    profile = service.users().getProfile(userId='me').execute()
    print(f"\nSuccessfully accessed Gmail API!")
    print(f"Email address: {profile['emailAddress']}")
    print(f"Messages total: {profile['messagesTotal']}")
    
    # Get all messages and filter locally
    print("\nFetching recent messages...")
    results = service.users().messages().list(userId='me', maxResults=10).execute()
    messages = results.get('messages', [])
    
    if not messages:
        print("No messages found.")
    else:
        print(f"\nAnalyzing {len(messages)} recent messages:")
        backup_messages = []
        
        for message in messages:
            msg = service.users().messages().get(userId='me', id=message['id'], format='metadata',
                                               metadataHeaders=['subject', 'from', 'date']).execute()
            headers = msg['payload']['headers']
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No subject')
            sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown sender')
            date = next((h['value'] for h in headers if h['name'].lower() == 'date'), 'Unknown date')
            
            # Check if this is a backup-related message
            if 'backup' in subject.lower():
                backup_messages.append({
                    'subject': subject,
                    'from': sender,
                    'date': date
                })
        
        if not backup_messages:
            print("No backup-related messages found in recent emails.")
        else:
            print(f"\nFound {len(backup_messages)} backup-related messages:")
            for msg in backup_messages:
                print(f"\nFrom: {msg['from']}")
                print(f"Date: {msg['date']}")
                print(f"Subject: {msg['subject']}")
            
except Exception as e:
    print(f"\nError accessing Gmail API: {e}")
    print(f"Error type: {type(e).__name__}")
    if hasattr(e, 'args'):
        print("Error args:", e.args) 