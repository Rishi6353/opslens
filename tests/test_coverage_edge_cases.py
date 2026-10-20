import pytest
from app.auth.decorators import roles_required
from app.db import get_db


def test_home_redirects_unauthenticated(client):
    """Visiting / redirects to /dashboard directly in Phase 2."""
    res = client.get('/', follow_redirects=False)
    assert res.status_code == 302
    assert '/dashboard' in res.headers['Location']


def test_home_redirects_authenticated(client, auth):
    """Visiting / when logged in redirects to /dashboard."""
    auth.login('admin', 'Password123!')
    res = client.get('/', follow_redirects=False)
    assert res.status_code == 302
    assert '/dashboard' in res.headers['Location']


def test_user_profile_view(client, auth):
    """Logged in user can view their profile and recent activity."""
    auth.login('admin', 'Password123!')
    res = client.get('/auth/profile')
    assert res.status_code == 200
    assert b"User Profile" in res.data
    assert b"admin@opslens.local" in res.data


def test_roles_required_decorator_blocks_unauthorized(app, client, auth):
    """Test custom route decorated with @roles_required('admin') rejects agents and requesters."""
    @app.route('/test-admin-only')
    @roles_required('admin')
    def admin_only_endpoint():
        return "Secret Admin Data"

    # 1. Unauthenticated -> redirects to login
    res = client.get('/test-admin-only', follow_redirects=False)
    assert res.status_code == 302

    # 2. Requester -> 403 Forbidden
    auth.login('john_requester', 'Password123!')
    res = client.get('/test-admin-only')
    assert res.status_code == 403
    auth.logout()

    # 3. Agent -> 403 Forbidden
    auth.login('sarah_agent', 'Password123!')
    res = client.get('/test-admin-only')
    assert res.status_code == 403
    auth.logout()

    # 4. Admin -> 200 OK
    auth.login('admin', 'Password123!')
    res = client.get('/test-admin-only')
    assert res.status_code == 200
    assert b"Secret Admin Data" in res.data


def test_nonexistent_ticket_returns_404(client, auth):
    """Requesting non-existent ticket ID returns 404 Not Found."""
    auth.login('admin', 'Password123!')
    res = client.get('/tickets/99999')
    assert res.status_code == 404
    assert b"Page or Ticket Not Found" in res.data


def test_comment_on_nonexistent_ticket_returns_404(client, auth):
    """Commenting on non-existent ticket ID returns 404."""
    auth.login('admin', 'Password123!')
    res = client.post('/tickets/99999/comment', data={'comment': 'hello'})
    assert res.status_code == 404


def test_empty_comment_validation(client, auth):
    """Submitting empty comment triggers validation alert."""
    auth.login('admin', 'Password123!')
    res = client.post('/tickets/1/comment', data={'comment': '   '}, follow_redirects=True)
    assert res.status_code == 200
    assert b"Comment cannot be empty" in res.data


def test_requester_sees_only_own_tickets_in_index(client, auth):
    """Requester John Doe (ID 4) should only see tickets he raised in the index."""
    auth.login('john_requester', 'Password123!')
    res = client.get('/tickets/')
    assert res.status_code == 200
    # John's tickets should be in the HTML
    assert b"Corporate VPN Gateway Timeout during peak hours" in res.data
    # Emily's ticket (Ticket #2: Suspicious phishing email) must not appear
    assert b"Suspicious phishing email reporting payroll update" not in res.data


def test_status_update_invalid_status(client, auth):
    """Updating ticket with an invalid status is rejected."""
    auth.login('admin', 'Password123!')
    res = client.post('/tickets/1/status', data={'status': 'invalid_hacked_status'}, follow_redirects=True)
    assert res.status_code == 200
    assert b"Invalid status" in res.data


def test_cli_init_and_seed_commands(runner):
    """Verify Flask CLI commands init-db and seed-db execute successfully."""
    init_res = runner.invoke(args=['init-db'])
    assert 'Initialized the SQLite database schema.' in init_res.output

    seed_res = runner.invoke(args=['seed-db'])
    assert 'Populated database with realistic seed data.' in seed_res.output


def test_health_check_healthy(client):
    """GET /health probe returns 200 and json status without leaking info."""
    res = client.get('/health')
    assert res.status_code == 200
    assert res.is_json
    assert res.get_json() == {"status": "healthy", "database": "connected"}
    assert b"Traceback" not in res.data
    assert b"SECRET_KEY" not in res.data


def test_health_check_unhealthy(client, monkeypatch):
    """GET /health probe returns 503 when database fails without leaking tracebacks."""
    from app import db
    def broken_db():
        raise RuntimeError("Database connection timed out or disk error")

    monkeypatch.setattr(db, 'get_db', broken_db)
    res = client.get('/health')
    assert res.status_code == 503
    assert res.is_json
    assert res.get_json() == {"status": "unhealthy", "database": "disconnected"}
    # Leak prevention checks
    assert b"Traceback" not in res.data
    assert b"Database connection timed out" not in res.data


def test_production_secret_key_guard(monkeypatch):
    """Production mode must raise RuntimeError if SECRET_KEY is default or weak."""
    from app import create_app

    monkeypatch.setenv('FLASK_ENV', 'production')
    monkeypatch.delenv('SECRET_KEY', raising=False)

    # Insecure fallback secret in production
    with pytest.raises(RuntimeError, match="Insecure configuration"):
        create_app({'SECRET_KEY': 'dev-secret-fallback-key-do-not-use-in-prod'})

    # Short secret (<32 chars) in production
    with pytest.raises(RuntimeError, match="Insecure configuration"):
        create_app({'SECRET_KEY': 'too-short-secret'})

    # Strong secret in production succeeds
    app = create_app({
        'SECRET_KEY': 'a' * 32,
        'TESTING': True
    })
    assert app is not None

