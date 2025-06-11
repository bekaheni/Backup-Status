import getpass
from app import app, db, User
from werkzeug.security import generate_password_hash

def main():
    with app.app_context():
        # Prompt for new password securely
        new_password = getpass.getpass("Enter new password for user 'Nick': ")
        confirm_password = getpass.getpass("Confirm new password for user 'Nick': ")
        if new_password != confirm_password:
            print("Passwords do not match! Aborting.")
            return

        # Create or update 'Nick'
        user = User.query.filter_by(username='Nick').first()
        if not user:
            user = User(username='Nick', is_admin=True)
            db.session.add(user)
            print("Created new user 'Nick'.")
        else:
            print("Updating password for existing user 'Nick'.")
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        print("Password for user 'Nick' has been set/updated successfully.")

if __name__ == "__main__":
    main() 