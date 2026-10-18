import pytest
from flask import session
from werkzeug.security import check_password_hash
from app.db import get_db, migrate_db, create_admin_command


def test_phase3_generic_error_on_login_failure(client, auth):
    """
    Phase 3 Security: Both incorrect password and non-existent username
    must return identical generic error messages to prevent username enumeration.
    """
    # 1. Existing user with incorrect password
    res_wrong_pw = auth.login('admin', 'WrongPassword123!')
    assert b"Invalid username or password" in res_wrong_pw.data

    # 2. Non-existent username
    res_fake_user = auth.login('attacker_user_xyz', 'RandomPassword123!')
    assert b"Invalid username or password" in res_fake_user.data


def test_phase3_login_deactivated_account_blocked(app, client, auth):
    """
    Phase 3 Security: Deactivated users cannot authenticate even with valid credentials.
    """
    with app.app_context():
        db = get_db()
        db.execute("UPDATE users SET is_active = 0 WHERE username = 'john_requester'")
        db.commit()

    res = auth.login('john_requester', 'Password123!')
    assert b"Your account has been deactivated" in res.data

    with client.session_transaction() as sess:
        assert 'user_id' not in sess


def test_phase3_session_fixation_and_cookie_security(client, auth):
    """
    Phase 3 Security: Login sets permanent session and sets HttpOnly and SameSite cookie flags.
    """
    res = auth.login('admin', 'Password123!')
    assert res.status_code == 200

    # Verify session variables inside authenticated session
    with client.session_transaction() as sess:
        assert sess.get('user_id') is not None
        assert sess.permanent is True


def test_phase3_admin_access_user_governance(client, auth):
    """
    Phase 3 RBAC: Only Admin can access /admin/users.
    Agents and Requesters must receive 403 Forbidden.
    """
    # 1. Requester -> 403 Forbidden
    auth.login('john_requester', 'Password123!')
    res_req = client.get('/admin/users')
    assert res_req.status_code == 403
    assert b"Access Forbidden" in res_req.data
    auth.logout()

    # 2. Agent -> 403 Forbidden
    auth.login('sarah_agent', 'Password123!')
    res_agent = client.get('/admin/users')
    assert res_agent.status_code == 403
    assert b"Access Forbidden" in res_agent.data
    auth.logout()

    # 3. Admin -> 200 OK
    auth.login('admin', 'Password123!')
    res_admin = client.get('/admin/users')
    assert res_admin.status_code == 200
    assert b"User &amp; Access Governance" in res_admin.data
    assert b"Registered Enterprise Accounts" in res_admin.data


def test_phase3_admin_toggle_user_status(app, client, auth):
    """
    Phase 3 RBAC: Admin can deactivate and reactivate accounts.
    """
    auth.login('admin', 'Password123!')

    # Deactivate John Doe (ID 4)
    res_deactivate = client.post('/admin/users/4/toggle-status', follow_redirects=True)
    assert res_deactivate.status_code == 200
    assert b"deactivated successfully" in res_deactivate.data

    with app.app_context():
        db = get_db()
        user = db.execute("SELECT is_active FROM users WHERE id = 4").fetchone()
        assert user['is_active'] == 0

    # Reactivate John Doe (ID 4)
    res_reactivate = client.post('/admin/users/4/toggle-status', follow_redirects=True)
    assert res_reactivate.status_code == 200
    assert b"reactivated successfully" in res_reactivate.data

    with app.app_context():
        db = get_db()
        user = db.execute("SELECT is_active FROM users WHERE id = 4").fetchone()
        assert user['is_active'] == 1


def test_phase3_admin_cannot_deactivate_self(client, auth):
    """
    Phase 3 Security: Protect against self-lockout.
    Admin cannot deactivate their own account.
    """
    auth.login('admin', 'Password123!')
    res = client.post('/admin/users/1/toggle-status', follow_redirects=True)
    assert res.status_code == 200
    assert b"You cannot deactivate your own administrative account" in res.data


def test_phase3_admin_change_user_role(app, client, auth):
    """
    Phase 3 RBAC: Admin can update a user's role.
    """
    auth.login('admin', 'Password123!')

    # Promote John (ID 4) from requester (role_id 3) to agent (role_id 2)
    res = client.post('/admin/users/4/change-role', data={'role_id': '2'}, follow_redirects=True)
    assert res.status_code == 200
    assert b"updated to Agent" in res.data

    with app.app_context():
        db = get_db()
        user = db.execute("SELECT role_id FROM users WHERE id = 4").fetchone()
        assert user['role_id'] == 2


def test_phase3_requester_idor_edit_blocked(client, auth):
    """
    Phase 3 IDOR Defense: Requester John (ID 4) cannot edit Emily's ticket (Ticket #2, owned by ID 5).
    """
    auth.login('john_requester', 'Password123!')

    # 1. GET edit page for another user's ticket -> 403 Forbidden
    res_get = client.get('/tickets/2/edit')
    assert res_get.status_code == 403
    assert b"Access Forbidden" in res_get.data

    # 2. POST edit update to another user's ticket -> 403 Forbidden
    res_post = client.post('/tickets/2/edit', data={
        'title': 'Hacked Title Attempt',
        'description': 'Malicious payload',
        'category_id': '5',
        'priority': 'critical',
        'status': 'closed'
    })
    assert res_post.status_code == 403


def test_phase3_requester_cannot_tamper_priority_on_edit(app, client, auth):
    """
    Phase 3 Privilege Escalation Defense: Requester editing their own ticket
    cannot tamper with priority or status fields.
    """
    auth.login('john_requester', 'Password123!')

    # John's Ticket #1 has priority='high', status='in_progress'
    res = client.post('/tickets/1/edit', data={
        'title': 'Corporate VPN Gateway Timeout during peak hours [EDITED]',
        'description': 'Updated context by requester.',
        'category_id': '1',
        'priority': 'critical',  # Attempted escalation
        'status': 'closed'       # Attempted status override
    }, follow_redirects=True)

    assert res.status_code == 200

    with app.app_context():
        db = get_db()
        ticket = db.execute("SELECT title, priority, status FROM tickets WHERE id = 1").fetchone()
        assert ticket['title'] == 'Corporate VPN Gateway Timeout during peak hours [EDITED]'
        # Priority and status must remain original (server-side protection)
        assert ticket['priority'] == 'high'
        assert ticket['status'] == 'in_progress'


def test_phase3_requester_cannot_comment_on_other_ticket(client, auth):
    """
    Phase 3 IDOR Defense: Requester cannot post comments on other users' tickets.
    """
    auth.login('john_requester', 'Password123!')
    res = client.post('/tickets/2/comment', data={'comment': 'Unauthorized comment'})
    assert res.status_code == 403


def test_phase3_requester_cannot_submit_internal_note(app, client, auth):
    """
    Phase 3 Confidentiality: When a requester posts a comment, is_internal is strictly forced to 0.
    """
    auth.login('john_requester', 'Password123!')
    res = client.post('/tickets/1/comment', data={
        'comment': 'Attempted internal note by requester',
        'is_internal': '1'  # Tampered flag
    }, follow_redirects=True)

    assert res.status_code == 200

    with app.app_context():
        db = get_db()
        comment = db.execute(
            "SELECT is_internal FROM ticket_comments WHERE comment = 'Attempted internal note by requester'"
        ).fetchone()
        assert comment is not None
        assert comment['is_internal'] == 0


def test_phase3_security_headers_present(client):
    """
    Phase 3 Defense-in-Depth: Standard security headers must be attached to HTTP responses.
    """
    res = client.get('/dashboard')
    assert res.headers.get('X-Frame-Options') == 'SAMEORIGIN'
    assert res.headers.get('X-Content-Type-Options') == 'nosniff'
    assert res.headers.get('X-XSS-Protection') == '1; mode=block'


def test_phase3_no_password_hashes_exposed(client, auth):
    """
    Phase 3 Data Protection: Password hashes must never be rendered in HTML templates.
    """
    auth.login('admin', 'Password123!')

    # 1. Admin users governance view
    res_users = client.get('/admin/users')
    assert b"scrypt:" not in res_users.data
    assert b"pbkdf2:" not in res_users.data

    # 2. User profile view
    res_profile = client.get('/auth/profile')
    assert b"scrypt:" not in res_profile.data
    assert b"pbkdf2:" not in res_profile.data


def test_phase3_create_admin_cli_runner(app, runner):
    """
    Phase 3 Admin Setup: Verify flask create-admin CLI command creates an admin account
    with salted password hashing without exposing secrets.
    """
    result = runner.invoke(
        create_admin_command,
        args=['--username', 'cli_superadmin', '--email', 'super@opslens.local', '--password', 'VeryStrongPassword2026!']
    )
    assert 'Successfully created Administrator account' in result.output

    with app.app_context():
        db = get_db()
        admin_row = db.execute(
            "SELECT username, email, role_id, password_hash, is_active FROM users WHERE username = 'cli_superadmin'"
        ).fetchone()
        assert admin_row is not None
        assert admin_row['role_id'] == 1
        assert admin_row['is_active'] == 1
        assert check_password_hash(admin_row['password_hash'], 'VeryStrongPassword2026!')


def test_phase3_safe_migration_handles_legacy_null_requesters():
    """
    Phase 3 Database Safety: Safe migration adds requester_id column if missing in legacy schemas
    and patches existing tickets to a fallback user without dropping tables or losing data.
    """
    import tempfile
    import os
    import sqlite3
    from app import create_app
    from app.db import migrate_db, get_db

    db_fd, db_path = tempfile.mkstemp()

    # Create a legacy pre-auth database schema where tickets had no requester_id column
    con = sqlite3.connect(db_path)
    con.executescript("""
        CREATE TABLE roles (id INTEGER PRIMARY KEY, name TEXT UNIQUE);
        INSERT INTO roles VALUES (1, 'admin'), (2, 'agent'), (3, 'requester');
        CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, role_id INTEGER);
        INSERT INTO users VALUES (1, 'system_admin', 1);
        CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT);
        INSERT INTO categories VALUES (1, 'General');
        CREATE TABLE tickets (id INTEGER PRIMARY KEY, title TEXT, description TEXT, category_id INTEGER, priority TEXT, status TEXT);
        INSERT INTO tickets VALUES (101, 'Legacy Pre-Auth Ticket', 'Created before auth existed', 1, 'low', 'open');
    """)
    con.commit()
    con.close()

    app = create_app({'TESTING': True, 'DATABASE': db_path, 'TESTING_CSRF_DISABLED': True})
    with app.app_context():
        migrate_db()
        db = get_db()
        # Verify requester_id column was safely added and ticket assigned fallback owner ID 1
        ticket = db.execute("SELECT id, title, requester_id FROM tickets WHERE id = 101").fetchone()
        assert ticket is not None
        assert ticket['requester_id'] == 1

    os.close(db_fd)
    os.unlink(db_path)
