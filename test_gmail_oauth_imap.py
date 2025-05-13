import os
import base64
import json
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

def get_gmail_service():
    try:
        # Load credentials from gmail_token.json
        with open('gmail_token.json', 'r') as token_file:
            creds_data = json.load(token_file)
        
        creds = Credentials.from_authorized_user_info(creds_data)
        
        # Refresh the token if necessary
        if not creds.valid:
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
            else:
                raise Exception("No refresh token available")
        
        # Create Gmail API service
        return build('gmail', 'v1', credentials=creds)
    except Exception as e:
        print(f"Error getting Gmail service: {str(e)}")
        return None

def get_body_from_parts(parts):
    body = ""
    for part in parts:
        if part['mimeType'] == 'text/plain':
            if 'data' in part['body']:
                try:
                    body += base64.urlsafe_b64decode(part['body']['data']).decode()
                except Exception as e:
                    print(f"Error decoding part: {e}")
        elif 'parts' in part:
            body += get_body_from_parts(part['parts'])
    return body

def main():
    try:
        service = get_gmail_service()
        if not service:
            print("Failed to get Gmail service")
            return

        # Get recent messages
        print("\nFetching recent messages...")
        results = service.users().messages().list(userId='me', maxResults=1).execute()  # Only get the most recent
        messages = results.get('messages', [])
        print(f"Found {len(messages)} recent messages")
        
        if not messages:
            print("No messages found")
            return

        # Get the most recent message
        message = messages[0]
        print(f"\nProcessing message {message['id']}...")
        
        # Get full message details
        msg = service.users().messages().get(userId='me', id=message['id'], format='full').execute()
        
        # Get headers
        headers = msg['payload']['headers']
        subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No subject')
        from_header = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'No sender')
        date_header = next((h['value'] for h in headers if h['name'].lower() == 'date'), 'No date')
        
        print("\n=== Email Details ===")
        print(f"Subject: {subject}")
        print(f"From: {from_header}")
        print(f"Date: {date_header}")
        
        # Get message body
        print("\n=== Email Body ===")
        body = ""
        if 'parts' in msg['payload']:
            body = get_body_from_parts(msg['payload']['parts'])
        elif 'body' in msg['payload'] and 'data' in msg['payload']['body']:
            try:
                body = base64.urlsafe_b64decode(msg['payload']['body']['data']).decode()
            except Exception as e:
                print(f"Error decoding body: {e}")
        
        print(body)
        print("\n=== End of Email ===")

    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        print(traceback.format_exc())

if __name__ == '__main__':
    main() 