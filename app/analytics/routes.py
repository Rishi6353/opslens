from flask import Blueprint, render_template, jsonify, g, redirect, url_for
from app.db import get_db
from app.auth.decorators import login_required

bp = Blueprint('analytics', __name__)


@bp.route('/')
def home():
    """
    Landing / root route.
    If authenticated, directs to the operational dashboard; otherwise, invites to login.
    """
    if g.user is None:
        return redirect(url_for('auth.login'))
    return redirect(url_for('analytics.dashboard'))


@bp.route('/dashboard')
@login_required
def dashboard():
    """
    Incident Analytics & IT Operations Dashboard.
    Computes key performance indicators (KPIs), Mean Time to Resolution (MTTR),
    priority/status distributions, and recurring incident patterns.
    """
    db = get_db()

    # 1. High-level metric counts
    total_tickets = db.execute("SELECT COUNT(*) AS count FROM tickets").fetchone()['count']
    open_tickets = db.execute("SELECT COUNT(*) AS count FROM tickets WHERE status = 'open'").fetchone()['count']
    in_progress = db.execute("SELECT COUNT(*) AS count FROM tickets WHERE status = 'in_progress'").fetchone()['count']
    resolved_tickets = db.execute("SELECT COUNT(*) AS count FROM tickets WHERE status IN ('resolved', 'closed')").fetchone()['count']
    critical_tickets = db.execute("SELECT COUNT(*) AS count FROM tickets WHERE priority = 'critical' AND status != 'closed'").fetchone()['count']

    # 2. Mean Time To Resolution (MTTR) in hours
    # Using SQLite julianday arithmetic: (julianday(resolved_at) - julianday(created_at)) * 24.0
    mttr_row = db.execute(
        """
        SELECT AVG((julianday(resolved_at) - julianday(created_at)) * 24.0) AS avg_hours
        FROM tickets
        WHERE resolved_at IS NOT NULL
        """
    ).fetchone()

    avg_mttr_hours = round(mttr_row['avg_hours'], 1) if mttr_row['avg_hours'] is not None else 0.0

    # 3. Recurring issues analysis (Pattern recognition by keyword clusters)
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

    # 4. Recent tickets (Last 5)
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

    # 5. Recent audit log trail (Last 6 security events)
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
        recurring_patterns=recurring_patterns,
        recent_tickets=recent_tickets,
        recent_audits=recent_audits
    )


@bp.route('/analytics/api/chart-data')
@login_required
def chart_data():
    """
    Returns aggregated JSON data for rendering Chart.js visualizations.
    Demonstrates backend SQL aggregation (GROUP BY) powering frontend analytics.
    """
    db = get_db()

    # 1. Status breakdown
    status_rows = db.execute(
        """
        SELECT status, COUNT(*) AS count
        FROM tickets
        GROUP BY status
        """
    ).fetchall()
    statuses = {row['status']: row['count'] for row in status_rows}

    # 2. Priority breakdown
    priority_rows = db.execute(
        """
        SELECT priority, COUNT(*) AS count
        FROM tickets
        GROUP BY priority
        """
    ).fetchall()
    priorities = {row['priority']: row['count'] for row in priority_rows}

    # 3. Category breakdown
    category_rows = db.execute(
        """
        SELECT c.name, COUNT(t.id) AS count
        FROM categories c
        LEFT JOIN tickets t ON c.id = t.category_id
        GROUP BY c.id
        ORDER BY count DESC
        """
    ).fetchall()
    category_labels = [row['name'] for row in category_rows]
    category_counts = [row['count'] for row in category_rows]

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
        }
    })
