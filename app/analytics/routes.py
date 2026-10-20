import io
import csv
import statistics
from flask import Blueprint, render_template, jsonify, g, redirect, url_for, request, flash, Response
from app.db import get_db
from app.auth.decorators import login_required
from app.analytics.date_utils import parse_date_range, build_date_where_clause
from app.security.csv_defense import sanitize_csv_cell

bp = Blueprint('analytics', __name__)

# Configurable demo SLA thresholds (in hours)
# These represent demo defaults for educational helpdesk triage and reporting
DEMO_SLA_THRESHOLDS_HOURS = {
    'critical': 24,  # Critical incidents: target response/resolution within 24h
    'high': 48,      # High priority incidents: 48h
    'medium': 72,    # Medium priority incidents: 72h
    'low': 120       # Low priority incidents: 120h (5 days)
}


@bp.route('/')
def home():
    """
    Landing / root route.
    Directs to the operational dashboard.
    """
    return redirect(url_for('analytics.dashboard'))


@bp.route('/dashboard')
def dashboard():
    """
    Incident Analytics & IT Operations Dashboard.
    Supports dynamic date filtering (7d, 30d, 90d, all, custom),
    computes KPIs, Mean & Median Time to Resolution (MTTR),
    overdue SLA breaches, and role-restricted audit telemetry.
    """
    db = get_db()

    # 1. Parse and validate date filter parameters
    preset = request.args.get('range', 'all')
    start_date_param = request.args.get('start_date', '')
    end_date_param = request.args.get('end_date', '')

    date_filter = parse_date_range(preset, start_date_param, end_date_param)
    if date_filter['error']:
        flash(date_filter['error'], 'warning')

    date_where, date_params = build_date_where_clause('created_at', date_filter)

    # 2. High-level metric counts within the selected date range
    total_sql = f"SELECT COUNT(*) AS count FROM tickets WHERE {date_where}"
    total_tickets = db.execute(total_sql, date_params).fetchone()['count']

    open_sql = f"SELECT COUNT(*) AS count FROM tickets WHERE status = 'open' AND {date_where}"
    open_tickets = db.execute(open_sql, date_params).fetchone()['count']

    in_progress_sql = f"SELECT COUNT(*) AS count FROM tickets WHERE status = 'in_progress' AND {date_where}"
    in_progress = db.execute(in_progress_sql, date_params).fetchone()['count']

    resolved_sql = f"SELECT COUNT(*) AS count FROM tickets WHERE status IN ('resolved', 'closed') AND {date_where}"
    resolved_tickets = db.execute(resolved_sql, date_params).fetchone()['count']

    critical_sql = f"SELECT COUNT(*) AS count FROM tickets WHERE priority = 'critical' AND status != 'closed' AND {date_where}"
    critical_tickets = db.execute(critical_sql, date_params).fetchone()['count']

    # 3. Mean Time To Resolution (MTTR) in hours
    # Using SQLite julianday arithmetic: (julianday(resolved_at) - julianday(created_at)) * 24.0
    mttr_sql = f"""
        SELECT AVG((julianday(resolved_at) - julianday(created_at)) * 24.0) AS avg_hours
        FROM tickets
        WHERE resolved_at IS NOT NULL AND {date_where}
    """
    mttr_row = db.execute(mttr_sql, date_params).fetchone()
    avg_mttr_hours = round(mttr_row['avg_hours'], 1) if (mttr_row and mttr_row['avg_hours'] is not None) else 0.0

    # 4. Median Time To Resolution (MTTR) in hours
    # SQLite does not support MEDIAN() as an aggregate function.
    # We query sorted durations for resolved tickets in the period and compute the median in Python.
    durations_sql = f"""
        SELECT (julianday(resolved_at) - julianday(created_at)) * 24.0 AS duration
        FROM tickets
        WHERE resolved_at IS NOT NULL AND {date_where}
        ORDER BY duration ASC
    """
    duration_rows = db.execute(durations_sql, date_params).fetchall()
    durations = [row['duration'] for row in duration_rows if row['duration'] is not None]
    median_mttr_hours = round(statistics.median(durations), 1) if durations else 0.0

    # 5. SLA Overdue Breach Detection
    # 5a. Currently Overdue Open Incidents (Global live backlog requiring operational intervention)
    live_overdue_sql = f"""
        SELECT COUNT(*) AS count FROM tickets
        WHERE status IN ('open', 'in_progress')
          AND (
            (priority = 'critical' AND (julianday('now') - julianday(created_at)) * 24.0 > {DEMO_SLA_THRESHOLDS_HOURS['critical']})
            OR (priority = 'high' AND (julianday('now') - julianday(created_at)) * 24.0 > {DEMO_SLA_THRESHOLDS_HOURS['high']})
            OR (priority = 'medium' AND (julianday('now') - julianday(created_at)) * 24.0 > {DEMO_SLA_THRESHOLDS_HOURS['medium']})
            OR (priority = 'low' AND (julianday('now') - julianday(created_at)) * 24.0 > {DEMO_SLA_THRESHOLDS_HOURS['low']})
          )
    """
    currently_overdue_tickets = db.execute(live_overdue_sql).fetchone()['count']

    # 5b. Overdue Incidents in Filtered Date Range (historical tracking)
    period_overdue_sql = f"""
        SELECT COUNT(*) AS count FROM tickets
        WHERE {date_where}
          AND status IN ('open', 'in_progress')
          AND (
            (priority = 'critical' AND (julianday('now') - julianday(created_at)) * 24.0 > {DEMO_SLA_THRESHOLDS_HOURS['critical']})
            OR (priority = 'high' AND (julianday('now') - julianday(created_at)) * 24.0 > {DEMO_SLA_THRESHOLDS_HOURS['high']})
            OR (priority = 'medium' AND (julianday('now') - julianday(created_at)) * 24.0 > {DEMO_SLA_THRESHOLDS_HOURS['medium']})
            OR (priority = 'low' AND (julianday('now') - julianday(created_at)) * 24.0 > {DEMO_SLA_THRESHOLDS_HOURS['low']})
          )
    """
    period_overdue_tickets = db.execute(period_overdue_sql, date_params).fetchone()['count']

    # 6. Recurring issues analysis (Pattern clusters)
    recurring_patterns = db.execute(
        """
        SELECT 'VPN Gateway Outages' AS issue_name, COUNT(*) AS incident_count, 'Network' AS category, 'High' AS severity
        FROM tickets WHERE title LIKE '%VPN%'
        UNION ALL
        SELECT 'IAM & MFA Desync', COUNT(*), 'Access & IAM', 'Medium'
        FROM tickets WHERE title LIKE '%IAM%' OR title LIKE '%MFA%' OR title LIKE '%Access%'
        UNION ALL
        SELECT 'Suspicious Activity & DLP', COUNT(*), 'Security', 'Critical'
        FROM tickets WHERE title LIKE '%phishing%' OR title LIKE '%USB%' OR title LIKE '%Storage%'
        UNION ALL
        SELECT 'Hardware & Display Freezes', COUNT(*), 'Hardware', 'Medium'
        FROM tickets WHERE title LIKE '%MacBook%' OR title LIKE '%Monitor%' OR title LIKE '%Flicker%'
        ORDER BY incident_count DESC
        """
    ).fetchall()

    # 7. Recent tickets (Last 5)
    recent_tickets = db.execute(
        """
        SELECT t.id, t.title, t.priority, t.status, t.created_at,
               c.name AS category_name,
               req.username AS requester_name
        FROM tickets t
        JOIN categories c ON t.category_id = c.id
        JOIN users req ON t.requester_id = req.id
        ORDER BY t.created_at DESC
        LIMIT 5
        """
    ).fetchall()

    # 8. Recent audit log trail
    # Enforce server-side privacy: Only administrators may view security audit telemetry
    recent_audits = []
    if g.user and g.user['role_name'] == 'admin':
        recent_audits = db.execute(
            """
            SELECT a.action, a.target_type, a.target_id, a.ip_address, a.details, a.created_at,
                   u.username
            FROM audit_logs a
            LEFT JOIN users u ON a.user_id = u.id
            ORDER BY a.created_at DESC
            LIMIT 6
            """
        ).fetchall()

    return render_template(
        'analytics/dashboard.html',
        total_tickets=total_tickets,
        open_tickets=open_tickets,
        in_progress=in_progress,
        resolved_tickets=resolved_tickets,
        critical_tickets=critical_tickets,
        avg_mttr_hours=avg_mttr_hours,
        median_mttr_hours=median_mttr_hours,
        currently_overdue_tickets=currently_overdue_tickets,
        period_overdue_tickets=period_overdue_tickets,
        recurring_patterns=recurring_patterns,
        recent_tickets=recent_tickets,
        recent_audits=recent_audits,
        date_filter=date_filter,
        sla_thresholds=DEMO_SLA_THRESHOLDS_HOURS
    )


@bp.route('/analytics/api/chart-data')
def chart_data():
    """
    Returns aggregated JSON data for rendering Chart.js visualizations.
    Supports date range filtering and provides volume trend time-series.
    """
    db = get_db()

    preset = request.args.get('range', 'all')
    start_date_param = request.args.get('start_date', '')
    end_date_param = request.args.get('end_date', '')

    date_filter = parse_date_range(preset, start_date_param, end_date_param)
    date_where, date_params = build_date_where_clause('t.created_at', date_filter)

    # 1. Status breakdown within date filter
    status_sql = f"""
        SELECT t.status, COUNT(*) AS count
        FROM tickets t
        WHERE {date_where}
        GROUP BY t.status
    """
    status_rows = db.execute(status_sql, date_params).fetchall()
    statuses = {row['status']: row['count'] for row in status_rows}

    # 2. Priority breakdown within date filter
    priority_sql = f"""
        SELECT t.priority, COUNT(*) AS count
        FROM tickets t
        WHERE {date_where}
        GROUP BY t.priority
    """
    priority_rows = db.execute(priority_sql, date_params).fetchall()
    priorities = {row['priority']: row['count'] for row in priority_rows}

    # 3. Category breakdown
    category_sql = f"""
        SELECT c.name, COUNT(t.id) AS count
        FROM categories c
        LEFT JOIN tickets t ON c.id = t.category_id AND {date_where}
        GROUP BY c.id
        ORDER BY count DESC
    """
    category_rows = db.execute(category_sql, date_params).fetchall()
    category_labels = [row['name'] for row in category_rows]
    category_counts = [row['count'] for row in category_rows]

    # 4. Volume Trend Time Series (Daily counts)
    volume_sql = f"""
        SELECT strftime('%Y-%m-%d', t.created_at) AS day_bucket, COUNT(*) AS count
        FROM tickets t
        WHERE {date_where}
        GROUP BY day_bucket
        ORDER BY day_bucket ASC
    """
    volume_rows = db.execute(volume_sql, date_params).fetchall()
    volume_labels = [row['day_bucket'] for row in volume_rows]
    volume_counts = [row['count'] for row in volume_rows]

    return jsonify({
        'status': {
            'labels': ['Open', 'In Progress', 'Resolved', 'Closed'],
            'counts': [
                statuses.get('open', 0),
                statuses.get('in_progress', 0),
                statuses.get('resolved', 0),
                statuses.get('closed', 0)
            ]
        },
        'priority': {
            'labels': ['Low', 'Medium', 'High', 'Critical'],
            'counts': [
                priorities.get('low', 0),
                priorities.get('medium', 0),
                priorities.get('high', 0),
                priorities.get('critical', 0)
            ]
        },
        'category': {
            'labels': category_labels,
            'counts': category_counts
        },
        'volume_trend': {
            'labels': volume_labels,
            'counts': volume_counts
        }
    })


@bp.route('/analytics/export/csv')
@login_required
def export_analytics_summary():
    """
    Exports a high-level incident analytics summary as a CSV file.
    Applies date filtering and hardens all textual cells against CSV formula injection (CWE-1236).
    """
    db = get_db()
    preset = request.args.get('range', 'all')
    start_date_param = request.args.get('start_date', '')
    end_date_param = request.args.get('end_date', '')

    date_filter = parse_date_range(preset, start_date_param, end_date_param)
    date_where, date_params = build_date_where_clause('created_at', date_filter)

    # Requester isolation: Requesters export metrics summarizing only their own tickets
    requester_clause = ""
    extra_params = []
    if g.user and g.user['role_name'] == 'requester':
        requester_clause = " AND requester_id = ?"
        extra_params = [g.user['id']]

    combined_params = date_params + extra_params

    # Fetch metric values
    total = db.execute(f"SELECT COUNT(*) AS c FROM tickets WHERE {date_where}{requester_clause}", combined_params).fetchone()['c']
    open_c = db.execute(f"SELECT COUNT(*) AS c FROM tickets WHERE status = 'open' AND {date_where}{requester_clause}", combined_params).fetchone()['c']
    prog_c = db.execute(f"SELECT COUNT(*) AS c FROM tickets WHERE status = 'in_progress' AND {date_where}{requester_clause}", combined_params).fetchone()['c']
    res_c = db.execute(f"SELECT COUNT(*) AS c FROM tickets WHERE status IN ('resolved', 'closed') AND {date_where}{requester_clause}", combined_params).fetchone()['c']
    crit_c = db.execute(f"SELECT COUNT(*) AS c FROM tickets WHERE priority = 'critical' AND status != 'closed' AND {date_where}{requester_clause}", combined_params).fetchone()['c']

    mttr_row = db.execute(
        f"SELECT AVG((julianday(resolved_at) - julianday(created_at)) * 24.0) AS avg_h FROM tickets WHERE resolved_at IS NOT NULL AND {date_where}{requester_clause}",
        combined_params
    ).fetchone()
    avg_mttr = round(mttr_row['avg_h'], 1) if (mttr_row and mttr_row['avg_h'] is not None) else 0.0

    duration_rows = db.execute(
        f"SELECT (julianday(resolved_at) - julianday(created_at)) * 24.0 AS dur FROM tickets WHERE resolved_at IS NOT NULL AND {date_where}{requester_clause} ORDER BY dur ASC",
        combined_params
    ).fetchall()
    durations = [r['dur'] for r in duration_rows if r['dur'] is not None]
    median_mttr = round(statistics.median(durations), 1) if durations else 0.0

    output = io.StringIO()
    writer = csv.writer(output)

    scope_desc = f"Personal ({g.user['username']})" if g.user['role_name'] == 'requester' else "Global (All Helpdesk)"
    writer.writerow([sanitize_csv_cell("Metric"), sanitize_csv_cell("Value"), sanitize_csv_cell("Notes")])
    writer.writerow([sanitize_csv_cell("Scope"), sanitize_csv_cell(scope_desc), ""])
    writer.writerow([sanitize_csv_cell("Date Filter Preset"), sanitize_csv_cell(date_filter['preset']), ""])
    writer.writerow([sanitize_csv_cell("Start Bound"), sanitize_csv_cell(date_filter['start_bound'] or "All Time"), ""])
    writer.writerow([sanitize_csv_cell("End Bound (Inclusive)"), sanitize_csv_cell(date_filter['end_bound'] or "All Time"), ""])
    writer.writerow([sanitize_csv_cell("Total Incidents"), total, ""])
    writer.writerow([sanitize_csv_cell("Open Incidents"), open_c, ""])
    writer.writerow([sanitize_csv_cell("In Progress Incidents"), prog_c, ""])
    writer.writerow([sanitize_csv_cell("Resolved Incidents"), res_c, ""])
    writer.writerow([sanitize_csv_cell("Critical Incidents"), crit_c, ""])
    writer.writerow([sanitize_csv_cell("Mean MTTR (Hours)"), avg_mttr, "Mean Time to Resolution"])
    writer.writerow([sanitize_csv_cell("Median MTTR (Hours)"), median_mttr, "Median Time to Resolution"])

    csv_data = output.getvalue()
    output.close()

    filename = f"opslens_analytics_summary_{date_filter['preset']}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache, no-store, must-revalidate"
        }
    )
