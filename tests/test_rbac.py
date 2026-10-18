import pytest
from app.db import get_db


def test_requester_can_view_own_ticket(client, auth):
    """Requester John Doe (ID 4) should be able to view his own ticket #1."""
    auth.login('john_requester', 'Password123!')
    response = client.get('/tickets/1')
    assert response.status_code == 200
    assert b"Corporate VPN Gateway Timeout" in response.data


def test_requester_cannot_view_others_ticket(client, auth):
    """Requester John Doe (ID 4) attempting to view Emily's ticket #2 should receive 403 Forbidden."""
    auth.login('john_requester', 'Password123!')
    response = client.get('/tickets/2')
    assert response.status_code == 403
    assert b"Access Forbidden" in response.data


def test_agent_can_view_any_ticket(client, auth):
    """Support Agent Sarah can inspect any user's ticket."""
    auth.login('sarah_agent', 'Password123!')
    response = client.get('/tickets/2')
    assert response.status_code == 200
    assert b"Suspicious phishing email" in response.data


def test_internal_comments_hidden_from_requester(client, auth):
    """Internal support notes (is_internal=1) must not be rendered to the ticket requester."""
    auth.login('john_requester', 'Password123!')
    response = client.get('/tickets/1')
    assert response.status_code == 200
    # Note in seed: 'Investigating gateway memory pressure' was marked is_internal = 1
    assert b"Investigating gateway memory pressure" not in response.data
    # Public note should be visible
    assert b"Thanks Sarah, let me know when we can test again." in response.data


def test_internal_comments_visible_to_agent(client, auth):
    """Support agents and admins must see internal support notes."""
    auth.login('sarah_agent', 'Password123!')
    response = client.get('/tickets/1')
    assert response.status_code == 200
    assert b"Investigating gateway memory pressure" in response.data
    assert b"Confidential Agent Note" in response.data


def test_requester_cannot_arbitrarily_update_status(client, auth):
    """Requesters cannot escalate priority, reassign, or force-resolve tickets."""
    auth.login('john_requester', 'Password123!')
    response = client.post(
        '/tickets/1/status',
        data={'status': 'resolved', 'priority': 'low'},
        follow_redirects=False
    )
    assert response.status_code == 403


def test_requester_can_close_resolved_ticket(client, auth):
    """Requester Emily (ID 5) can close her resolved ticket #4."""
    auth.login('emily_requester', 'Password123!')
    response = client.post(
        '/tickets/4/status',
        data={'status': 'closed'},
        follow_redirects=True
    )
    assert response.status_code == 200
    assert b"Ticket closed" in response.data


def test_agent_can_update_status_and_assignee(app, client, auth):
    """Support agents can update ticket status and reassign tickets."""
    auth.login('sarah_agent', 'Password123!')
    response = client.post(
        '/tickets/3/status',
        data={'status': 'in_progress', 'priority': 'critical', 'assignee_id': '2'},
        follow_redirects=True
    )
    assert response.status_code == 200
    assert b"Ticket #3 updated" in response.data

    with app.app_context():
        db = get_db()
        ticket = db.execute("SELECT status, priority, assignee_id FROM tickets WHERE id = 3").fetchone()
        assert ticket['status'] == 'in_progress'
        assert ticket['priority'] == 'critical'
        assert ticket['assignee_id'] == 2
