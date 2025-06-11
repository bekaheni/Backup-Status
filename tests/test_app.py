import unittest
from app import app, db, BackupStatus
from datetime import datetime

class TestApp(unittest.TestCase):
    def setUp(self):
        """Set up test environment before each test."""
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True,
            'pool_recycle': 300,
        }
        self.client = app.test_client()
        with app.app_context():
            # Drop all tables and recreate them
            db.drop_all()
            db.create_all()

    def tearDown(self):
        """Clean up after each test."""
        with app.app_context():
            db.session.close()
            db.drop_all()

    def test_index_route(self):
        """Test the main index route."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)

    def test_nas_route(self):
        """Test the NAS view route."""
        response = self.client.get('/nas')
        self.assertEqual(response.status_code, 200)

    def test_clear_database(self):
        """Test clearing the database."""
        with app.app_context():
            # Add a test record
            test_status = BackupStatus(
                server='test_server',
                status='successful',
                timestamp=datetime.now(),
                subject='Test Subject',
                body='Test Body',
                email_type='server'
            )
            db.session.add(test_status)
            db.session.commit()

            # Verify record was added
            self.assertEqual(BackupStatus.query.count(), 1)

            # Clear database
            response = self.client.post('/clear-database', json={'email_type': 'server'})
            self.assertEqual(response.status_code, 200)
            
            # Verify database is empty
            self.assertEqual(BackupStatus.query.count(), 0)

if __name__ == '__main__':
    unittest.main() 