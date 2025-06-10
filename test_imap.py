import os
import imaplib
import socket
from dotenv import load_dotenv

def test_imap_connection(email_type='server'):
    load_dotenv()
    
    if email_type == 'server':
        email = os.getenv('EMAIL')
        password = os.getenv('EMAIL_PASSWORD')
        imap_server = os.getenv('IMAP_SERVER', 'mail.remoteone.uk')
        inbox_name = os.getenv('INBOX_NAME', 'INBOX')
    else:
        email = os.getenv('NAS_EMAIL')
        password = os.getenv('NAS_EMAIL_PASSWORD')
        imap_server = os.getenv('NAS_IMAP_SERVER', 'mail.remoteone.uk')
        inbox_name = os.getenv('NAS_INBOX_NAME', 'INBOX')

    print(f"\nTesting {email_type} connection:")
    print(f"IMAP Server: {imap_server}")
    print(f"Email: {email}")
    print(f"Inbox: {inbox_name}")
    print(f"Password length: {len(password) if password else 0}")

    try:
        # First test basic socket connection
        print(f"\nTesting basic socket connection to {imap_server}...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((imap_server, 993))
        print("Basic socket connection successful!")
        sock.close()

        print(f"\nAttempting SSL connection to {imap_server}...")
        mail = imaplib.IMAP4_SSL(imap_server, timeout=10)
        print("SSL connection successful!")
        
        print("\nAttempting login...")
        mail.login(email, password)
        print("Login successful!")
        
        print("\nAttempting to select inbox...")
        mail.select(inbox_name)
        print("Inbox selection successful!")
        
        print("\nConnection test completed successfully!")
        return True
    except socket.gaierror as e:
        print(f"\nDNS Resolution Error: {str(e)}")
        print("This means the server hostname could not be resolved.")
        return False
    except socket.timeout as e:
        print(f"\nConnection Timeout: {str(e)}")
        print("The server did not respond within the timeout period.")
        return False
    except socket.error as e:
        print(f"\nSocket Error: {str(e)}")
        print("There was a problem with the network connection.")
        return False
    except imaplib.IMAP4.error as e:
        print(f"\nIMAP4 Error: {str(e)}")
        print("This is an authentication or protocol error.")
        return False
    except Exception as e:
        print(f"\nUnexpected Error: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        return False

if __name__ == "__main__":
    print("Testing server email connection...")
    server_result = test_imap_connection('server')
    
    print("\nTesting NAS email connection...")
    nas_result = test_imap_connection('nas')
    
    print("\nTest Results:")
    print(f"Server connection: {'Success' if server_result else 'Failed'}")
    print(f"NAS connection: {'Success' if nas_result else 'Failed'}") 