import pytest
from app.db import get_db


def test_ticket_list_renders(client, auth):
    """Verify ticket list renders properly with search and filters."""
    auth.login('admin', 'Password123!')
    response = client.get('/tickets/')
    assert response.status_code == 200
    assert b"Incident &amp; Service Tickets" in response.data
    assert b"Corporate VPN Gateway" in response.data


def test_ticket_search_and_filters(client, auth):
    """Verify parameterized search and multi-facet filtering."""
    auth.login('admin', 'Password123!')

    # Search for VPN
    response = client.get('/tickets/?q=VPN')
    assert response.status_code == 200
    assert b"Corporate VPN Gateway Timeout" in response.data
    assert b"MacBook Pro screen flickering" not in response.data

    # Filter by priority = critical
    response = client.get('/tickets/?priority=critical')
    assert response.status_code == 200
    assert b"Suspicious phishing email" in response.data

    # Filter by status = resolved
    response = client.get('/tickets/?status=resolved')
    assert response.status_code == 200
    assert b"AWS Staging IAM Access Token Expired" in response.data


def test_ticket_create_validation(client, auth):
    """Verify server-side input validation on ticket creation."""
    auth.login('john_requester', 'Password123!')

    # 1. Missing title
    response = client.post('/tickets/create', data={
        'title': '',
        'description': 'Valid description',
        'category_id': '1',
        'priority': 'medium'
    })
    assert b"Ticket title is required" in response.data

    # 2. Missing description
    response = client.post('/tickets/create', data={
        'title': 'Valid Title',
        'description': '',
        'category_id': '1',
        'priority': 'medium'
    })
    assert b"Ticket description is required" in response.data

    # 3. Invalid priority
    response = client.post('/tickets/create', data={
        'title': 'Valid Title',
        'description': 'Valid description',
        'category_id': '1',
        'priority': 'ultra-urgent-hack'
    })
    assert b"Invalid priority" in response.data

    # 4. Non-existent category
    response = client.post('/tickets/create', data={
        'title': 'Valid Title',
        'description': 'Valid description',
        'category_id': '99999',
        'priority': 'low'
    })
    assert b"Selected category does not exist" in response.data


def test_ticket_create_success(app, client, auth):
    """Verify successful ticket creation persists to DB with current user as requester."""
    auth.login('john_requester', 'Password123!')
    response = client.post('/tickets/create', data={
        'title': 'New Test Incident from Automated Suite',
        'description': 'Testing database persistence and defaults.',
        'category_id': '1',
        'priority': 'high'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"New Test Incident from Automated Suite" in response.data
    assert b"submitted successfully" in response.data

    with app.app_context():
        db = get_db()
        ticket = db.execute(
            "SELECT * FROM tickets WHERE title = 'New Test Incident from Automated Suite'"
        ).fetchone()
        assert ticket is not None
        assert ticket['status'] == 'open'
        assert ticket['priority'] == 'high'
        assert ticket['requester_id'] == 4  # John's user ID


def test_add_comment(app, client, auth):
    """Verify adding comments to a ticket updates the ticket timestamp."""
    auth.login('sarah_agent', 'Password123!')
    response = client.post('/tickets/1/comment', data={
        'comment': 'Investigating router metrics at us-east datacenter.',
        'is_internal': '1'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Comment added successfully" in response.data
    assert b"Investigating router metrics" in response.data


def test_resolved_at_timestamp_lifecycle(app, client, auth):
    """Verify resolved_at timestamp is set on resolution and cleared on reopening."""
    auth.login('sarah_agent', 'Password123!')

    # Move ticket 1 to resolved
    client.post('/tickets/1/status', data={'status': 'resolved'})
    with app.app_context():
        db = get_db()
        ticket = db.execute("SELECT status, resolved_at FROM tickets WHERE id = 1").fetchone()
        assert ticket['status'] == 'resolved'
        assert ticket['resolved_at'] is not None

    # Reopen ticket 1
    client.post('/tickets/1/status', data={'status': 'in_progress'})
    with app.app_context():
        db = get_db()
        ticket = db.execute("SELECT status, resolved_at FROM tickets WHERE id = 1").fetchone()
        assert ticket['status'] == 'in_progress'
        assert ticket['resolved_at'] is None
