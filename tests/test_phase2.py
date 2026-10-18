import pytest
import re
from app import create_app
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


def test_phase2_dashboard_counts_match_database_records(app, client):
    """
    Phase 2: Verify that dashboard metric counts match the exact counts in SQLite database,
    and verify that counts update dynamically when tickets are created and updated.
    """
    with app.app_context():
        db = get_db()
        db_total = db.execute("SELECT COUNT(*) AS count FROM tickets").fetchone()['count']
        db_open = db.execute("SELECT COUNT(*) AS count FROM tickets WHERE status = 'open'").fetchone()['count']
        db_in_progress = db.execute("SELECT COUNT(*) AS count FROM tickets WHERE status = 'in_progress'").fetchone()['count']
        db_resolved = db.execute("SELECT COUNT(*) AS count FROM tickets WHERE status IN ('resolved', 'closed')").fetchone()['count']
        db_critical = db.execute("SELECT COUNT(*) AS count FROM tickets WHERE priority = 'critical' AND status != 'closed'").fetchone()['count']

    res = client.get('/dashboard')
    assert res.status_code == 200
    html = res.data.decode('utf-8')

    # Verify counts appear inside the KPI cards in the rendered HTML
    assert f'<span class="kpi-value">{db_total}</span>' in html
    assert f'<span class="kpi-value">{db_open}</span>' in html
    assert f'<span class="kpi-value">{db_in_progress}</span>' in html
    assert f'<span class="kpi-value">{db_resolved}</span>' in html
    assert f'<span class="kpi-value">{db_critical}</span>' in html

    # Create a new critical ticket and verify dashboard numbers increment
    client.post('/tickets/create', data={
        'title': 'New Critical Outage Incident',
        'description': 'Database server memory exhaustion alert.',
        'category_id': '1',
        'priority': 'critical'
    })

    res2 = client.get('/dashboard')
    html2 = res2.data.decode('utf-8')

    # Total should be db_total + 1, Open should be db_open + 1, Critical should be db_critical + 1
    assert f'<span class="kpi-value">{db_total + 1}</span>' in html2
    assert f'<span class="kpi-value">{db_open + 1}</span>' in html2
    assert f'<span class="kpi-value">{db_critical + 1}</span>' in html2


def test_phase2_invalid_inputs_comprehensive(client):
    """
    Phase 2: Comprehensive validation tests for invalid title length, whitespace,
    invalid category IDs, and invalid status values.
    """
    # 1. Title exceeding 150 chars
    long_title = "A" * 151
    res_long = client.post('/tickets/create', data={
        'title': long_title,
        'description': 'Description',
        'category_id': '1',
        'priority': 'low'
    })
    assert b"Title must be 150 characters or fewer" in res_long.data

    # 2. Whitespace-only title
    res_ws_title = client.post('/tickets/create', data={
        'title': '    ',
        'description': 'Description',
        'category_id': '1',
        'priority': 'low'
    })
    assert b"Ticket title is required" in res_ws_title.data

    # 3. Non-existent category ID
    res_nonexistent_cat = client.post('/tickets/create', data={
        'title': 'Valid Title',
        'description': 'Description',
        'category_id': '99999',
        'priority': 'low'
    })
    assert b"Selected category does not exist" in res_nonexistent_cat.data

    # 4. Non-numeric category ID
    res_alpha_cat = client.post('/tickets/create', data={
        'title': 'Valid Title',
        'description': 'Description',
        'category_id': 'network-category',
        'priority': 'low'
    })
    assert b"A valid category must be selected" in res_alpha_cat.data

    # 5. Invalid status in edit
    res_invalid_status = client.post('/tickets/1/edit', data={
        'title': 'Valid Title',
        'description': 'Valid Description',
        'category_id': '1',
        'priority': 'low',
        'status': 'archived_deleted'
    })
    assert b"Invalid status" in res_invalid_status.data


def test_phase2_search_and_filtering(client):
    """
    Phase 2: Verify multi-facet searching and filtering by title, description,
    priority, and category with SQL injection resilience.
    """
    # 1. Search keyword in description
    res_search_desc = client.get('/tickets/?q=handshake')
    assert res_search_desc.status_code == 200
    assert b"Corporate VPN Gateway Timeout in London Office" in res_search_desc.data

    # 2. Search keyword with SQL wildcard characters
    res_search_wildcard = client.get('/tickets/?q=%25')  # URL-encoded '%'
    assert res_search_wildcard.status_code == 200

    # 3. Filter by category
    res_cat = client.get('/tickets/?category=5')  # Security & Compliance category
    assert res_cat.status_code == 200
    assert b"Suspicious phishing email" in res_cat.data

    # 4. Combined filter: category=1 AND priority=high
    res_combo = client.get('/tickets/?category=1&priority=high')
    assert res_combo.status_code == 200
    assert b"Corporate VPN Gateway Timeout" in res_combo.data


def test_phase2_persistence_across_app_restart(app, client):
    """
    Phase 2: Verify that created and updated tickets persist in SQLite across separate
    database connections and simulated application restarts.
    """
    db_path = app.config['DATABASE']

    # 1. Create a ticket in the first application context
    res = client.post('/tickets/create', data={
        'title': 'Persistence Test Incident 2026',
        'description': 'Must persist after application restart and DB reconnection.',
        'category_id': '1',
        'priority': 'high'
    }, follow_redirects=True)
    assert res.status_code == 200

    # 2. Simulate application restart: create a new app instance pointing to the same SQLite file
    restarted_app = create_app({
        'TESTING': True,
        'DATABASE': db_path,
        'SECRET_KEY': 'test-secret-key-very-secure',
        'TESTING_CSRF_DISABLED': True
    })
    restarted_client = restarted_app.test_client()

    # 3. Query the restarted app to verify data is intact
    res_restart = restarted_client.get('/tickets/?q=Persistence+Test+Incident+2026')
    assert res_restart.status_code == 200
    assert b"Persistence Test Incident 2026" in res_restart.data
    assert b"high" in res_restart.data

    # 4. Direct SQLite verification on disk
    with restarted_app.app_context():
        db = get_db()
        ticket = db.execute(
            "SELECT id, title, priority, status FROM tickets WHERE title = 'Persistence Test Incident 2026'"
        ).fetchone()
        assert ticket is not None
        assert ticket['priority'] == 'high'
        assert ticket['status'] == 'open'
