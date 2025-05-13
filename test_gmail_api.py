from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import json

print("Starting Gmail API test...")

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
    
    # List some recent messages
    results = service.users().messages().list(userId='me', maxResults=5).execute()
    messages = results.get('messages', [])
    
    if not messages:
        print("No messages found.")
    else:
        print("\nRecent messages:")
        for message in messages:
            msg = service.users().messages().get(userId='me', id=message['id']).execute()
            subject = next((header['value'] for header in msg['payload']['headers'] if header['name'].lower() == 'subject'), 'No subject')
            print(f"Subject: {subject}")
            
except Exception as e:
    print(f"\nError accessing Gmail API: {e}")
    print(f"Error type: {type(e).__name__}")
    if hasattr(e, 'args'):
        print("Error args:", e.args) 