import pytest
from app.db import get_db


def test_dashboard_metrics(client, auth):
    """Verify dashboard KPI metric cards render with non-zero incident counts."""
    auth.login('admin', 'Password123!')
    response = client.get('/dashboard')
    assert response.status_code == 200
    assert b"IT Operations &amp; Incident Analytics" in response.data
    assert b"Average MTTR" in response.data
    assert b"Total Incidents" in response.data
    assert b"Recurring Incident Clusters" in response.data


def test_chart_data_api(client, auth):
    """Verify /analytics/api/chart-data JSON endpoint provides structured data for Chart.js."""
    auth.login('sarah_agent', 'Password123!')
    response = client.get('/analytics/api/chart-data')
    assert response.status_code == 200
    assert response.is_json

    data = response.get_json()
    assert 'status' in data
    assert 'priority' in data
    assert 'category' in data

    # Check status data
    assert data['status']['labels'] == ['Open', 'In Progress', 'Resolved', 'Closed']
    assert sum(data['status']['counts']) > 0

    # Check priority data
    assert data['priority']['labels'] == ['Low', 'Medium', 'High', 'Critical']
    assert sum(data['priority']['counts']) > 0

    # Check category data
    assert len(data['category']['labels']) == 5


def test_mttr_edge_case_zero_resolved(app, client, auth):
    """Verify MTTR calculates 0.0 when no tickets have been resolved, avoiding ZeroDivisionError."""
    with app.app_context():
        db = get_db()
        db.execute("UPDATE tickets SET resolved_at = NULL, status = 'open'")
        db.commit()

    auth.login('admin', 'Password123!')
    response = client.get('/dashboard')
    assert response.status_code == 200
    assert b"0.0" in response.data
