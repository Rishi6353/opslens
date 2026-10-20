from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, g
from app.db import get_db
from app.auth.decorators import roles_required
from app.audit.logger import log_audit_event

bp = Blueprint('admin', __name__, url_prefix='/admin')


@bp.route('/users')
@roles_required('admin')
def users():
    """
    Administrative user management view.
    Only accessible by users with the 'admin' role.
    """
    db = get_db()
    users_list = db.execute(
        """
        SELECT u.id, u.username, u.email, u.role_id, u.is_active, u.created_at,
               r.name AS role_name, r.description AS role_description
        FROM users u
        JOIN roles r ON u.role_id = r.id
        ORDER BY u.id ASC
        """
    ).fetchall()

    roles_list = db.execute("SELECT id, name FROM roles ORDER BY id ASC").fetchall()

    return render_template('admin/users.html', users=users_list, roles=roles_list)


@bp.route('/users/<int:user_id>/toggle-status', methods=('POST',))
@roles_required('admin')
def toggle_user_status(user_id):
    """
    Toggles user active/deactivated state.
    Protects against self-lockout: an admin cannot deactivate themselves.
    """
    if user_id == g.user['id']:
        flash('Security Alert: You cannot deactivate your own administrative account.', 'danger')
        return redirect(url_for('admin.users'))

    db = get_db()
    user = db.execute("SELECT id, username, is_active FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        abort(404, description=f"User #{user_id} not found.")

    new_status = 0 if user['is_active'] == 1 else 1
    db.execute("UPDATE users SET is_active = ? WHERE id = ?", (new_status, user_id))
    db.commit()

    action_label = 'deactivated' if new_status == 0 else 'reactivated'
    log_audit_event(
        action=f"USER_STATUS_{action_label.upper()}",
        target_type='user',
        target_id=user_id,
        details=f"Admin '{g.user['username']}' {action_label} account for '{user['username']}'"
    )

    flash(f"User '{user['username']}' has been {action_label} successfully.", 'success')
    return redirect(url_for('admin.users'))


@bp.route('/users/<int:user_id>/change-role', methods=('POST',))
@roles_required('admin')
def change_user_role(user_id):
    """
    Updates the RBAC role for a user.
    Protects against demoting the currently logged-in administrator.
    """
    if user_id == g.user['id']:
        flash('Security Alert: You cannot modify your own administrative role.', 'danger')
        return redirect(url_for('admin.users'))

    new_role_id = request.form.get('role_id', '').strip()
    if not new_role_id or not new_role_id.isdigit():
        flash('Invalid role selected.', 'danger')
        return redirect(url_for('admin.users'))

    db = get_db()
    role_row = db.execute("SELECT id, name FROM roles WHERE id = ?", (int(new_role_id),)).fetchone()
    if not role_row:
        flash('Selected role does not exist.', 'danger')
        return redirect(url_for('admin.users'))

    user = db.execute("SELECT id, username, role_id FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        abort(404, description=f"User #{user_id} not found.")

    db.execute("UPDATE users SET role_id = ? WHERE id = ?", (int(new_role_id), user_id))
    db.commit()

    log_audit_event(
        action='USER_ROLE_CHANGED',
        target_type='user',
        target_id=user_id,
        details=f"Admin '{g.user['username']}' changed role for '{user['username']}' to '{role_row['name']}'"
    )

    flash(f"Role for user '{user['username']}' updated to {role_row['name'].capitalize()}.", 'success')
    return redirect(url_for('admin.users'))


import math
import re
from app.analytics.date_utils import parse_date_range, build_date_where_clause

SENSITIVE_PATTERNS = [
    re.compile(r'([\w-]*(?:password|passwd|pwd|secret|token|api_key|hash)[\w-]*)\s*[:=]\s*[^\s,;&]+', re.IGNORECASE),
    re.compile(r'(scrypt|pbkdf2|bcrypt):[^\s,;&]+', re.IGNORECASE)
]


def redact_sensitive_details(text):
    """
    Defense-in-depth: Scans audit log contextual text and redacts any residual secrets,
    passwords, hashes, or tokens prior to presentation in the administrative UI.
    """
    if not text:
        return ""
    redacted = str(text)
    for pattern in SENSITIVE_PATTERNS:
        redacted = pattern.sub(r'\1: [REDACTED]', redacted)
    return redacted


@bp.route('/audit-logs')
@roles_required('admin')
def audit_logs():
    """
    Administrative Audit Log Explorer.
    Restricted strictly to administrators for security compliance and incident investigation.
    Features parameterized filtering, bounded pagination, and sensitive data redaction.
    """
    db = get_db()

    action_filter = request.args.get('action', '').strip()
    user_filter = request.args.get('user_id', '').strip()
    preset = request.args.get('range', 'all').strip()
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()

    # Bounded pagination (protects database from excessive memory consumption)
    try:
        page = max(1, int(request.args.get('page', 1)))
    except (ValueError, TypeError):
        page = 1

    try:
        per_page = max(5, min(100, int(request.args.get('per_page', 20))))
    except (ValueError, TypeError):
        per_page = 20

    where_clauses = []
    params = []

    # 1. Action filter
    if action_filter:
        where_clauses.append("a.action = ?")
        params.append(action_filter)

    # 2. Actor / User ID filter
    if user_filter and user_filter.isdigit():
        where_clauses.append("a.user_id = ?")
        params.append(int(user_filter))

    # 3. Date range filter with inclusive end date
    date_filter = parse_date_range(preset, start_date, end_date)
    if date_filter['error']:
        flash(date_filter['error'], 'warning')

    date_where, date_params = build_date_where_clause('a.created_at', date_filter)
    if date_where != "1=1":
        where_clauses.append(date_where)
        params.extend(date_params)

    base_where = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    # Total count query for pagination
    count_sql = f"""
        SELECT COUNT(*) AS total
        FROM audit_logs a
        LEFT JOIN users u ON a.user_id = u.id
        {base_where}
    """
    total_count = db.execute(count_sql, params).fetchone()['total']
    total_pages = max(1, math.ceil(total_count / per_page))

    # Enforce page bound
    if page > total_pages:
        page = total_pages

    offset = (page - 1) * per_page

    # Query page records
    data_sql = f"""
        SELECT a.id, a.action, a.target_type, a.target_id, a.ip_address, a.details, a.created_at,
               u.username
        FROM audit_logs a
        LEFT JOIN users u ON a.user_id = u.id
        {base_where}
        ORDER BY a.created_at DESC, a.id DESC
        LIMIT ? OFFSET ?
    """
    page_params = list(params) + [per_page, offset]
    raw_logs = db.execute(data_sql, page_params).fetchall()

    # Redact sensitive details before passing to template
    logs = []
    for row in raw_logs:
        log_dict = dict(row)
        log_dict['details'] = redact_sensitive_details(row['details'])
        logs.append(log_dict)

    # Fetch filter options for dropdowns
    available_actions = [r['action'] for r in db.execute("SELECT DISTINCT action FROM audit_logs ORDER BY action ASC").fetchall()]
    available_users = db.execute("SELECT id, username FROM users ORDER BY username ASC").fetchall()

    return render_template(
        'admin/audit_logs.html',
        logs=logs,
        page=page,
        per_page=per_page,
        total_count=total_count,
        total_pages=total_pages,
        action_filter=action_filter,
        user_filter=user_filter,
        date_filter=date_filter,
        available_actions=available_actions,
        available_users=available_users
    )


