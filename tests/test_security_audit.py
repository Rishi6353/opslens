import os
import tempfile
import pytest
from app import create_app
from app.db import get_db, init_db, seed_db


def test_csrf_protection_blocks_forged_requests():
    """Verify state-changing POST requests lacking a valid CSRF token are blocked with 403."""
    db_fd, db_path = tempfile.mkstemp()
    app = create_app({
        'TESTING': True,
        'DATABASE': db_path,
        'SECRET_KEY': 'csrf-test-key',
        'TESTING_CSRF_DISABLED': False  # CSRF strictly enforced here
    })

    with app.app_context():
        init_db()
        seed_db()

    client = app.test_client()

    # Attempt to POST to login without CSRF token
    response = client.post('/auth/login', data={'username': 'admin', 'password': 'Password123!'})
    assert response.status_code == 403
    assert b"CSRF token validation failed" in response.data

    os.close(db_fd)
    os.unlink(db_path)


def test_csrf_protection_accepts_valid_token():
    """Verify requests with a matching session CSRF token succeed."""
    db_fd, db_path = tempfile.mkstemp()
    app = create_app({
        'TESTING': True,
        'DATABASE': db_path,
        'SECRET_KEY': 'csrf-test-key',
        'TESTING_CSRF_DISABLED': False
    })

    with app.app_context():
        init_db()
        seed_db()

    client = app.test_client()

    # 1. Establish session and get CSRF token by visiting login page (GET)
    get_res = client.get('/auth/login')
    assert get_res.status_code == 200

    with client.session_transaction() as sess:
        valid_csrf_token = sess.get('csrf_token')
    assert valid_csrf_token is not None

    # 2. Submit POST with valid token
    post_res = client.post('/auth/login', data={
        'username': 'admin',
        'password': 'Password123!',
        'csrf_token': valid_csrf_token
    }, follow_redirects=True)

    assert post_res.status_code == 200
    assert b"Logged in as Admin" in post_res.data

    os.close(db_fd)
    os.unlink(db_path)


def test_sql_injection_resilience(client, auth):
    """
    Verify parameterized queries neutralize SQL injection payloads.
    Testing common payloads in login, search, and ticket filter.
    """
    # 1. Classical auth bypass attempt: ' OR 1=1 --
    payload = "' OR 1=1 --"
    res = client.post('/auth/login', data={'username': payload, 'password': 'dummy_password'})
    assert res.status_code == 200
    assert b"Invalid username or password" in res.data

    with client.session_transaction() as sess:
        assert 'user_id' not in sess

    # 2. SQL injection in ticket search
    auth.login('admin', 'Password123!')
    search_payload = "' UNION SELECT id, username, email, 'hacked', 1, 1, 1, 1, 1, 1 FROM users --"
    search_res = client.get(f"/tickets/?q={search_payload}")
    assert search_res.status_code == 200
    # No SQL error, safely handled as literal string


def test_audit_log_telemetry(app, client, auth):
    """Verify security audit logs record login and ticket creation events."""
    auth.login('john_requester', 'Password123!')
    client.post('/tickets/create', data={
        'title': 'Audit Log Verification Ticket',
        'description': 'Testing tamper-evident audit logging.',
        'category_id': '1',
        'priority': 'low'
    })

    with app.app_context():
        db = get_db()
        logs = db.execute(
            "SELECT action, details FROM audit_logs ORDER BY id DESC LIMIT 5"
        ).fetchall()

        actions = [log['action'] for log in logs]
        assert 'LOGIN_SUCCESS' in actions
        assert 'TICKET_CREATED' in actions

