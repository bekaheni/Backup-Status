import unittest
from app import parse_backup_status
from datetime import datetime

class TestEmailParsing(unittest.TestCase):
    def test_parse_backup_status_success(self):
        """Test parsing a successful backup status email."""
        test_body = """
        ServerName (ServerID)
        Success
        10 Jun 2025 22:00
        """
        results = parse_backup_status(test_body)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['server'], 'ServerName (ServerID)')
        self.assertEqual(results[0]['status'], 'successful')
        self.assertIsInstance(results[0]['timestamp'], datetime)

    def test_parse_backup_status_failure(self):
        """Test parsing a failed backup status email."""
        test_body = """
        ServerName (ServerID)
        Failed
        10 Jun 2025 22:00
        """
        results = parse_backup_status(test_body)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['server'], 'ServerName (ServerID)')
        self.assertEqual(results[0]['status'], 'unsuccessful')
        self.assertIsInstance(results[0]['timestamp'], datetime)

    def test_parse_backup_status_invalid_format(self):
        """Test parsing an email with invalid format."""
        test_body = "Invalid format email"
        results = parse_backup_status(test_body)
        self.assertEqual(len(results), 0)

    def test_parse_backup_status_multiple_entries(self):
        """Test parsing an email with multiple backup status entries."""
        test_body = """
        Server1 (ID1)
        Success
        10 Jun 2025 22:00

        Server2 (ID2)
        Failed
        10 Jun 2025 22:30
        """
        results = parse_backup_status(test_body)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['server'], 'Server1 (ID1)')
        self.assertEqual(results[1]['server'], 'Server2 (ID2)')

if __name__ == '__main__':
    unittest.main() 