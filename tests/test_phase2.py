import pytest
from app.db import get_db


def test_phase2_dashboard_loads_without_login(client):
    """Phase 2: Dashboard at / and /dashboard renders directly with ticket counts."""
    # 1. Root redirect
    res_root = client.get('/', follow_redirects=True)
    assert res_root.status_code == 200
    assert b"IT Operations &amp; Incident Analytics" in res_root.data
    assert b"Total Incidents" in res_root.data
    assert b"Open / Unresolved" in res_root.data

    # 2. Direct /dashboard
    res_dash = client.get('/dashboard')
    assert res_dash.status_code == 200
    assert b"Total Incidents" in res_dash.data


def test_phase2_ticket_list_renders(client):
    """Phase 2: Ticket list renders with sample tickets."""
    res = client.get('/tickets/')
    assert res.status_code == 200
    assert b"Incident &amp; Service Tickets" in res.data
    assert b"Corporate VPN Gateway" in res.data
    assert b"MacBook Pro screen flickering" in res.data


def test_phase2_ticket_create_validation(client):
    """Phase 2: Ticket creation validates required title, description, category, and priority."""
    # 1. Empty title
    res_empty_title = client.post('/tickets/create', data={
        'title': '',
        'description': 'Description here',
        'category_id': '1',
        'priority': 'medium'
    })
    assert b"Ticket title is required" in res_empty_title.data

    # 2. Empty description
    res_empty_desc = client.post('/tickets/create', data={
        'title': 'Test Title',
        'description': '',
        'category_id': '1',
        'priority': 'medium'
    })
    assert b"Ticket description is required" in res_empty_desc.data

    # 3. Invalid priority
    res_invalid_priority = client.post('/tickets/create', data={
        'title': 'Test Title',
        'description': 'Valid description',
        'category_id': '1',
        'priority': 'super-mega-urgent'
    })
    assert b"Invalid priority" in res_invalid_priority.data


def test_phase2_ticket_create_success(app, client):
    """Phase 2: Creating a ticket persists it in SQLite and redirects to detail view."""
    res = client.post('/tickets/create', data={
        'title': 'Phase 2 Test Support Ticket',
        'description': 'Verifying ticket persistence and initial open status.',
        'category_id': '2',
        'priority': 'high'
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b"Phase 2 Test Support Ticket" in res.data
    assert b"submitted successfully" in res.data

    with app.app_context():
        db = get_db()
        ticket = db.execute(
            "SELECT * FROM tickets WHERE title = 'Phase 2 Test Support Ticket'"
        ).fetchone()
        assert ticket is not None
        assert ticket['priority'] == 'high'
        assert ticket['status'] == 'open'


def test_phase2_ticket_view(client):
    """Phase 2: Viewing an existing ticket displays details, priority, and status badges."""
    res = client.get('/tickets/1')
    assert res.status_code == 200
    assert b"Corporate VPN Gateway Timeout during peak hours" in res.data
    assert b"high" in res.data
    assert b"in progress" in res.data.lower()


def test_phase2_ticket_view_404_handling(client):
    """Phase 2: Requesting non-existent ticket ID triggers 404 error page gracefully."""
    res = client.get('/tickets/999999')
    assert res.status_code == 404
    assert b"Page or Ticket Not Found" in res.data


def test_phase2_ticket_edit_success(app, client):
    """Phase 2: Editing an existing ticket updates title, priority, status, and description."""
    # 1. Edit form page renders with prefilled values
    get_res = client.get('/tickets/3/edit')
    assert get_res.status_code == 200
    assert b"Edit Ticket #3" in get_res.data
    assert b"MacBook Pro screen flickering and freezing" in get_res.data

    # 2. Submit edit POST
    post_res = client.post('/tickets/3/edit', data={
        'title': 'MacBook Pro screen flickering - UPDATED',
        'description': 'Updated description after hardware diagnostics.',
        'category_id': '2',
        'priority': 'critical',
        'status': 'in_progress'
    }, follow_redirects=True)

    assert post_res.status_code == 200
    assert b"Ticket #3 updated successfully" in post_res.data
    assert b"MacBook Pro screen flickering - UPDATED" in post_res.data

    with app.app_context():
        db = get_db()
        ticket = db.execute("SELECT title, priority, status FROM tickets WHERE id = 3").fetchone()
        assert ticket['title'] == 'MacBook Pro screen flickering - UPDATED'
        assert ticket['priority'] == 'critical'
        assert ticket['status'] == 'in_progress'


def test_phase2_ticket_status_update(app, client):
    """Phase 2: Updating ticket status transitions lifecycle."""
    res = client.post('/tickets/5/status', data={
        'status': 'resolved',
        'priority': 'medium'
    }, follow_redirects=True)

    assert res.status_code == 200
    assert b"Ticket #5 updated" in res.data

    with app.app_context():
        db = get_db()
        ticket = db.execute("SELECT status, priority, resolved_at FROM tickets WHERE id = 5").fetchone()
        assert ticket['status'] == 'resolved'
        assert ticket['priority'] == 'medium'
        assert ticket['resolved_at'] is not None
