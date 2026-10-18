import os
import tempfile
import pytest
from app import create_app
from app.db import get_db, init_db, seed_db


class AuthActions:
    """Helper client to simulate user login and session states in tests."""
    def __init__(self, client):
        self._client = client

    def login(self, username='admin', password='Password123!'):
        return self._client.post(
            '/auth/login',
            data={'username': username, 'password': password},
            follow_redirects=True
        )

    def logout(self):
        return self._client.post('/auth/logout', follow_redirects=True)


@pytest.fixture
def app():
    """Create and configure a clean application instance for testing."""
    db_fd, db_path = tempfile.mkstemp()

    app = create_app({
        'TESTING': True,
        'DATABASE': db_path,
        'SECRET_KEY': 'test-secret-key-very-secure',
        'TESTING_CSRF_DISABLED': True,  # Disabled by default in tests; dedicated tests verify CSRF
        'WTF_CSRF_ENABLED': False
    })

    with app.app_context():
        init_db()
        seed_db()

    yield app

    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """A test runner for the app's Click commands."""
    return app.test_cli_runner()


@pytest.fixture
def auth(client):
    """Authentication helper fixture."""
    return AuthActions(client)
