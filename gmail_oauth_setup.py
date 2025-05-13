import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# If modifying these scopes, delete the file gmail_token.json.
SCOPES = [
    'https://mail.google.com/'
]

def main():
    creds = None
    # The file gmail_token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.
    if os.path.exists('gmail_token.json'):
        print("Token file already exists. Please delete it if you want to re-authenticate.")
        return

    if not os.path.exists('credentials.json'):
        print("credentials.json not found. Please download it from Google Cloud Console.")
        return

    flow = InstalledAppFlow.from_client_secrets_file(
        'credentials.json', SCOPES)
    creds = flow.run_local_server(port=0)
    
    # Save the credentials for the next run
    with open('gmail_token.json', 'w') as token:
        token_data = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes
        }
        json.dump(token_data, token)

    print("OAuth2 flow completed. Credentials saved to gmail_token.json")

if __name__ == '__main__':
    main() 