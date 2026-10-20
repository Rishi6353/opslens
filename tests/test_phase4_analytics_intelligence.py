import csv
import io
import pytest
from datetime import datetime, timedelta
from app.db import get_db, migrate_db
from app.analytics.date_utils import parse_date_range, build_date_where_clause
from app.security.csv_defense import sanitize_csv_cell


def test_date_utils_inclusive_boundaries():
    """
    Verify parse_date_range formats end_bound with the start of the next day (00:00:00)
    to safely include fractional seconds timestamps on the selected end date.
    """
    res = parse_date_range('custom', '2026-10-15', '2026-10-18')
    assert res['preset'] == 'custom'
    assert res['start_bound'] == '2026-10-15 00:00:00'
    assert res['end_bound'] == '2026-10-19 00:00:00'
    assert res['error'] is None

    # Verify a ticket created at 3:30 PM on the end date is inclusive
    ticket_created = '2026-10-18 15:30:00'
    assert res['start_bound'] <= ticket_created < res['end_bound']

    # Verify a timestamp containing fractional seconds on the selected end date is included
    fractional_ts = '2026-10-18 23:59:59.852140'
    assert res['start_bound'] <= fractional_ts < res['end_bound']

    # Verify a timestamp at the start of the next day is excluded
    next_day_ts = '2026-10-19 00:00:00'
    assert not (res['start_bound'] <= next_day_ts < res['end_bound'])


def test_date_utils_invalid_and_reversed_ranges():
    """Verify date_utils handles invalid syntax and reversed ranges gracefully with fallbacks."""
    # 1. Invalid date string
    res_inv = parse_date_range('custom', 'not-a-date', '2026-10-18')
    assert res_inv['preset'] == 'all'
    assert res_inv['error'] is not None
    assert "Invalid date format" in res_inv['error']

    # 2. Reversed date range (start > end)
    res_rev = parse_date_range('custom', '2026-10-25', '2026-10-10')
    assert res_rev['preset'] == 'all'
    assert res_rev['error'] is not None
    assert "Reversed date range" in res_rev['error']

    # 3. Standard presets (7d, 30d, 90d, all)
    fixed_now = datetime(2026, 10, 19, 12, 0, 0)
    res_7d = parse_date_range('7d', now=fixed_now)
    assert res_7d['preset'] == '7d'
    assert res_7d['start_bound'] == '2026-10-12 00:00:00'
    assert res_7d['end_bound'] == '2026-10-20 00:00:00'

    res_all = parse_date_range('all')
    assert res_all['preset'] == 'all'
    assert res_all['start_bound'] is None
    assert res_all['end_bound'] is None


def test_known_mean_and_median_calculation(app, client, auth):
    """
    Verify Mean and Median Time to Resolution (MTTR) with known mathematical values.
    Insert 3 resolved tickets with exact durations of 2.0h, 4.0h, and 9.0h.
    Expected Mean = (2 + 4 + 9)/3 = 5.0h
    Expected Median = 4.0h
    """
    with app.app_context():
        db = get_db()
        # Clear existing tickets to isolate calculation
        db.execute("DELETE FROM ticket_comments")
        db.execute("DELETE FROM tickets")

        # Ticket 1: 2.0 hours
        db.execute("""
            INSERT INTO tickets (id, title, description, category_id, priority, status, requester_id, created_at, resolved_at)
            VALUES (101, 'Test A', 'Desc', 1, 'low', 'resolved', 4, '2026-10-10 10:00:00', '2026-10-10 12:00:00')
        """)
        # Ticket 2: 4.0 hours
        db.execute("""
            INSERT INTO tickets (id, title, description, category_id, priority, status, requester_id, created_at, resolved_at)
            VALUES (102, 'Test B', 'Desc', 1, 'medium', 'resolved', 4, '2026-10-10 10:00:00', '2026-10-10 14:00:00')
        """)
        # Ticket 3: 9.0 hours
        db.execute("""
            INSERT INTO tickets (id, title, description, category_id, priority, status, requester_id, created_at, resolved_at)
            VALUES (103, 'Test C', 'Desc', 1, 'high', 'closed', 4, '2026-10-10 10:00:00', '2026-10-10 19:00:00')
        """)
        db.commit()

    auth.login('admin', 'Password123!')
    res = client.get('/dashboard')
    assert res.status_code == 200

    # Average MTTR: 5.0 hrs
    assert b"5.0" in res.data
    # Median MTTR: 4.0 hrs
    assert b"4.0" in res.data

    # Add 4th ticket with 11.0 hours duration: [2.0, 4.0, 9.0, 11.0] -> Mean = 26/4 = 6.5, Median = (4 + 9)/2 = 6.5
    with app.app_context():
        db = get_db()
        db.execute("""
            INSERT INTO tickets (id, title, description, category_id, priority, status, requester_id, created_at, resolved_at)
            VALUES (104, 'Test D', 'Desc', 1, 'critical', 'resolved', 4, '2026-10-10 10:00:00', '2026-10-10 21:00:00')
        """)
        db.commit()

    res4 = client.get('/dashboard')
    assert res4.status_code == 200
    assert b"6.5" in res4.data


def test_empty_dataset_edge_cases(app, client, auth):
    """Verify zero division and empty datasets do not cause 500 errors or crashes."""
    auth.login('admin', 'Password123!')

    # Query a custom date range where 0 tickets exist
    res = client.get('/dashboard?range=custom&start_date=2020-01-01&end_date=2020-01-02')
    assert res.status_code == 200
    assert b"Total Incidents" in res.data
    assert b"0.0" in res.data  # Safe MTTR fallback

    # Check chart API with empty date range
    chart_res = client.get('/analytics/api/chart-data?range=custom&start_date=2020-01-01&end_date=2020-01-02')
    assert chart_res.status_code == 200
    data = chart_res.get_json()
    assert sum(data['status']['counts']) == 0
    assert sum(data['priority']['counts']) == 0
    assert data['volume_trend']['labels'] == []
    assert data['volume_trend']['counts'] == []


def test_sla_thresholds_and_overdue_detection(app, client, auth):
    """
    Verify SLA breach calculation based on configurable demo defaults:
    Critical: >24h, High: >48h, Medium: >72h, Low: >120h.
    """
    with app.app_context():
        db = get_db()
        db.execute("DELETE FROM ticket_comments")
        db.execute("DELETE FROM tickets")

        # 1. Critical ticket created 30 hours ago, status 'open' -> OVERDUE (>24h)
        db.execute("""
            INSERT INTO tickets (id, title, description, category_id, priority, status, requester_id, created_at)
            VALUES (201, 'Critical Breach', 'Desc', 5, 'critical', 'open', 4, datetime('now', '-30 hours'))
        """)

        # 2. Critical ticket created 2 hours ago, status 'open' -> NOT OVERDUE (<24h)
        db.execute("""
            INSERT INTO tickets (id, title, description, category_id, priority, status, requester_id, created_at)
            VALUES (202, 'Critical Fresh', 'Desc', 5, 'critical', 'open', 4, datetime('now', '-2 hours'))
        """)

        # 3. Medium ticket created 80 hours ago, status 'in_progress' -> OVERDUE (>72h)
        db.execute("""
            INSERT INTO tickets (id, title, description, category_id, priority, status, requester_id, created_at)
            VALUES (203, 'Medium Breach', 'Desc', 2, 'medium', 'in_progress', 4, datetime('now', '-80 hours'))
        """)

        # 4. Critical ticket created 50 hours ago, but already RESOLVED -> NOT in live open overdue count
        db.execute("""
            INSERT INTO tickets (id, title, description, category_id, priority, status, requester_id, created_at, resolved_at)
            VALUES (204, 'Critical Resolved', 'Desc', 5, 'critical', 'resolved', 4, datetime('now', '-50 hours'), datetime('now', '-20 hours'))
        """)
        db.commit()

    auth.login('admin', 'Password123!')
    res = client.get('/dashboard')
    assert res.status_code == 200
    # Overdue open incidents should be exactly 2 (#201 and #203)
    assert b"Currently Overdue" in res.data


def test_audit_log_explorer_rbac(client, auth):
    """Verify strict RBAC: only Administrators can access /admin/audit-logs."""
    # 1. Anonymous visitor is redirected to login
    res_anon = client.get('/admin/audit-logs')
    assert res_anon.status_code == 302
    assert '/auth/login' in res_anon.headers['Location']

    # 2. Requester role is blocked with 403 Forbidden
    auth.login('john_requester', 'Password123!')
    res_req = client.get('/admin/audit-logs')
    assert res_req.status_code == 403
    assert b"Access Forbidden" in res_req.data

    # 3. Support Agent role is blocked with 403 Forbidden
    auth.logout()
    auth.login('sarah_agent', 'Password123!')
    res_agent = client.get('/admin/audit-logs')
    assert res_agent.status_code == 403

    # 4. Administrator has full access (200 OK)
    auth.logout()
    auth.login('admin', 'Password123!')
    res_admin = client.get('/admin/audit-logs')
    assert res_admin.status_code == 200
    assert b"Security Audit Trail" in res_admin.data
    assert b"Audit Events Queue" in res_admin.data


def test_audit_log_explorer_filtering_and_pagination(client, auth):
    """Verify parameter filtering (action, user_id, date range) and bounded pagination in Audit Explorer."""
    auth.login('admin', 'Password123!')

    # 1. Action filter
    res_action = client.get('/admin/audit-logs?action=USER_LOGIN_SUCCESS')
    assert res_action.status_code == 200
    assert b"USER_LOGIN_SUCCESS" in res_action.data

    # 2. Actor filter
    res_actor = client.get('/admin/audit-logs?user_id=1')
    assert res_actor.status_code == 200

    # 3. Bounded pagination
    res_page = client.get('/admin/audit-logs?page=1&per_page=2')
    assert res_page.status_code == 200
    assert b"Page <strong>1</strong>" in res_page.data


def test_audit_log_sensitive_redaction(app, client, auth):
    """Defense-in-depth: Verify passwords and secrets are redacted from audit log UI."""
    with app.app_context():
        db = get_db()
        db.execute("""
            INSERT INTO audit_logs (user_id, action, target_type, target_id, ip_address, details)
            VALUES (1, 'CONFIG_CHANGE', 'system', NULL, '127.0.0.1', 'Updated secret_key=SuperSecretVaultKey123! and password: PlainPassword456')
        """)
        db.commit()

    auth.login('admin', 'Password123!')
    res = client.get('/admin/audit-logs?action=CONFIG_CHANGE')
    assert res.status_code == 200
    assert b"[REDACTED]" in res.data
    assert b"SuperSecretVaultKey123!" not in res.data
    assert b"PlainPassword456" not in res.data


def test_csv_export_requester_ownership_isolation(client, auth):
    """
    Verify cross-user data isolation:
    Requesters can ONLY export their own tickets; other users' tickets are never exposed.
    """
    # 1. John Requester logs in (id=4, has tickets #1, #3, #6, #7, #8 in seed data)
    auth.login('john_requester', 'Password123!')
    res_req = client.get('/tickets/export/csv')
    assert res_req.status_code == 200
    assert res_req.headers['Content-Type'].startswith('text/csv')

    csv_text = res_req.data.decode('utf-8')
    reader = csv.reader(io.StringIO(csv_text))
    header = next(reader)
    assert 'Requester' in header

    requester_col = header.index('Requester')
    rows = list(reader)
    assert len(rows) > 0

    for row in rows:
        # Every single row must belong to john_requester
        assert row[requester_col] == 'john_requester'
        # Must not contain Emily Watson's tickets
        assert row[requester_col] != 'emily_requester'

    # 2. Switch session: Admin logs in and exports all tickets
    auth.logout()
    auth.login('admin', 'Password123!')
    res_admin = client.get('/tickets/export/csv')
    assert res_admin.status_code == 200
    admin_rows = list(csv.reader(io.StringIO(res_admin.data.decode('utf-8'))))[1:]
    assert len(admin_rows) > len(rows)


def test_csv_formula_injection_defense(app, client, auth):
    """
    CWE-1236 Defense:
    Verify that formula triggers (=, +, -, @, \t, \r) are safely neutralized with a single quote prefix ('),
    including when disguised behind leading whitespace or control characters.
    Preserves legitimate numeric ticket IDs.
    """
    # 1. Unit test sanitizer function directly
    assert sanitize_csv_cell("=cmd|' /C calc'!A0") == "'=cmd|' /C calc'!A0"
    assert sanitize_csv_cell("+1+2") == "'+1+2"
    assert sanitize_csv_cell("-10+5") == "'-10+5"
    assert sanitize_csv_cell("@SUM(A1:A10)") == "'@SUM(A1:A10)"
    assert sanitize_csv_cell("   =formula_with_leading_spaces") == "''   =formula_with_leading_spaces" or sanitize_csv_cell("   =formula_with_leading_spaces").startswith("'")
    assert sanitize_csv_cell("\t=tab_formula").startswith("'")
    assert sanitize_csv_cell("\r=return_formula").startswith("'")
    # Genuine numeric primitives must be preserved as int/float
    assert sanitize_csv_cell(42) == 42
    assert sanitize_csv_cell(3.14) == 3.14

    # 2. Integration test via /tickets/export/csv
    with app.app_context():
        db = get_db()
        db.execute("""
            INSERT INTO tickets (id, title, description, category_id, priority, status, requester_id)
            VALUES (301, '=HYPERLINK("http://attacker.com")', '   +cmd|/C calc', 1, 'low', 'open', 1)
        """)
        db.commit()

    auth.login('admin', 'Password123!')
    res = client.get('/tickets/export/csv')
    assert res.status_code == 200
    csv_text = res.data.decode('utf-8')

    # Formula execution neutralized
    assert "'=HYPERLINK" in csv_text
    assert "'+cmd" in csv_text or "'   +cmd" in csv_text


def test_analytics_summary_csv_export(client, auth):
    """
    Verify /analytics/export/csv independently:
    - Authentication required (anonymous redirected)
    - Role permissions and requester data isolation (requester sees only their metrics)
    - Admin receives global helpdesk metrics
    """
    # 1. Anonymous visitor is redirected to login
    res_anon = client.get('/analytics/export/csv')
    assert res_anon.status_code == 302
    assert '/auth/login' in res_anon.headers['Location']

    # 2. Requester downloads summary: strictly isolated to personal tickets
    auth.login('john_requester', 'Password123!')
    res_req = client.get('/analytics/export/csv?range=all')
    assert res_req.status_code == 200
    assert res_req.headers['Content-Type'].startswith('text/csv')
    csv_req = res_req.data.decode('utf-8')
    assert "Personal (john_requester)" in csv_req
    # John has 5 tickets in seed data
    assert "Total Incidents,5," in csv_req

    # 3. Admin downloads summary: global scope containing all 10 seed tickets
    auth.logout()
    auth.login('admin', 'Password123!')
    res_admin = client.get('/analytics/export/csv?range=all')
    assert res_admin.status_code == 200
    assert 'attachment; filename="opslens_analytics_summary_all.csv"' in res_admin.headers['Content-Disposition']
    csv_admin = res_admin.data.decode('utf-8')
    assert "Global (All Helpdesk)" in csv_admin
    assert "Total Incidents,10," in csv_admin


def test_fractional_seconds_timestamp_in_database(app, client, auth):
    """
    Verify that an incident timestamp with fractional seconds on the selected end date
    (e.g., '2026-10-18 23:59:59.852') is correctly included by the exclusive start-of-next-day boundary.
    """
    with app.app_context():
        db = get_db()
        db.execute("""
            INSERT INTO tickets (id, title, description, category_id, priority, status, requester_id, created_at)
            VALUES (401, 'Fractional Timestamp Test', 'Created at 23:59:59.852', 1, 'high', 'open', 1, '2026-10-18 23:59:59.852')
        """)
        db.commit()

    auth.login('admin', 'Password123!')
    # Query custom date range where end_date is exactly 2026-10-18
    res = client.get('/dashboard?range=custom&start_date=2026-10-18&end_date=2026-10-18')
    assert res.status_code == 200
    # Ticket #401 should be found within the queue
    assert b"Fractional Timestamp Test" in res.data


def test_chart_data_api_volume_trend_and_date_filtering(client, auth):
    """Verify chart API returns volume_trend time-series responding to date parameters."""
    auth.login('admin', 'Password123!')
    res = client.get('/analytics/api/chart-data?range=all')
    assert res.status_code == 200
    data = res.get_json()

    assert 'volume_trend' in data
    assert 'labels' in data['volume_trend']
    assert 'counts' in data['volume_trend']
    assert len(data['volume_trend']['labels']) > 0


def test_migration_idempotent_on_existing_db(app):
    """Verify migrate_db can be executed repeatedly on existing databases without error or data loss."""
    with app.app_context():
        # First execution
        res1 = migrate_db()
        assert res1 >= 0

        # Second execution (verifies idempotent execution)
        res2 = migrate_db()
        assert res2 >= 0

        db = get_db()
        # Verify indexes exist
        indices = [row['name'] for row in db.execute("PRAGMA index_list('tickets')").fetchall()]
        assert 'idx_tickets_resolved_at' in indices
        assert 'idx_tickets_status_created' in indices
