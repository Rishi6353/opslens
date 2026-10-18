import pytest
from flask import session, g
from app.db import get_db


def test_login_page_renders(client):
    """Verify login page displays properly with accessible form."""
    response = client.get('/auth/login')
    assert response.status_code == 200
    assert b"Ops" in response.data
    assert b"Lens" in response.data
    assert b"Access" in response.data
    assert b"Username" in response.data
    assert b"Password" in response.data


@pytest.mark.parametrize(('username', 'password', 'expected_role'), [
    ('admin', 'Password123!', 'Admin'),
    ('sarah_agent', 'Password123!', 'Agent'),
    ('john_requester', 'Password123!', 'Requester'),
])
def test_login_success(client, auth, username, password, expected_role):
    """Verify authentication succeeds across different roles and establishes session."""
    response = auth.login(username, password)
    assert response.status_code == 200
    assert f"Logged in as {expected_role}".encode() in response.data

    with client.session_transaction() as sess:
        assert sess['user_id'] is not None


def test_login_invalid_password(client, auth):
    """Verify authentication fails on wrong password and flashes error."""
    response = auth.login('admin', 'WrongPassword!')
    assert b"Invalid username or password" in response.data

    with client.session_transaction() as sess:
        assert 'user_id' not in sess


def test_login_nonexistent_user(client, auth):
    """Verify authentication fails gracefully when user does not exist."""
    response = auth.login('ghost_user', 'Password123!')
    assert b"Invalid username or password" in response.data


def test_login_deactivated_user(app, client, auth):
    """Verify deactivated user cannot authenticate even with valid password."""
    with app.app_context():
        db = get_db()
        db.execute("UPDATE users SET is_active = 0 WHERE username = 'john_requester'")
        db.commit()

    response = auth.login('john_requester', 'Password123!')
    assert b"Your account has been deactivated" in response.data


def test_logout(client, auth):
    """Verify logout terminates session securely."""
    auth.login('admin', 'Password123!')
    with client.session_transaction() as sess:
        assert 'user_id' in sess

    response = auth.logout()
    assert b"You have been logged out securely" in response.data

    with client.session_transaction() as sess:
        assert 'user_id' not in sess


def test_open_redirect_defense(client, auth):
    """Verify malicious external redirect targets in ?next= are neutralized."""
    response = client.post(
        '/auth/login?next=https://attacker-phishing.com/steal',
        data={'username': 'admin', 'password': 'Password123!'},
        follow_redirects=False
    )
    # Ensure it redirects to internal dashboard (/dashboard) instead of external URL
    assert response.status_code == 302
    assert response.headers['Location'] == '/dashboard'


def test_unauthenticated_redirect(client):
    """Verify unauthenticated requests to protected endpoints redirect to login."""
    response = client.get('/dashboard', follow_redirects=False)
    assert response.status_code == 302
    assert '/auth/login' in response.headers['Location']
