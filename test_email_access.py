import os
import imaplib
import email
from dotenv import load_dotenv

load_dotenv()

EMAIL = os.getenv('EMAIL')
PASSWORD = os.getenv('EMAIL_PASSWORD')
IMAP_SERVER = os.getenv('IMAP_SERVER', 'imap.gmail.com')

try:
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL, PASSWORD)
    mail.select('inbox')

    # Fetch the latest 5 emails
    _, message_numbers = mail.search(None, 'ALL')
    message_ids = message_numbers[0].split()[-5:]

    print(f"Found {len(message_ids)} emails. Showing latest 5:")
    for num in reversed(message_ids):
        _, msg_data = mail.fetch(num, '(RFC822)')
        email_body = msg_data[0][1]
        email_message = email.message_from_bytes(email_body)
        subject = email_message['subject']
        from_ = email_message['from']
        print(f"From: {from_} | Subject: {subject}")

    mail.logout()
except Exception as e:
    print(f"Error accessing email: {e}") 