import pytest
from app import app, db

@pytest.fixture
def test_app():
    """Create a test Flask application."""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    return app

@pytest.fixture
def test_client(test_app):
    """Create a test client."""
    return test_app.test_client()

@pytest.fixture
def test_db(test_app):
    """Create a test database."""
    with test_app.app_context():
        db.create_all()
        yield db
        db.session.remove()
        db.drop_all() 