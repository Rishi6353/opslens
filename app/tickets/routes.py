from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, g
from app.db import get_db
from app.auth.decorators import login_required, roles_required
from app.audit.logger import log_audit_event

bp = Blueprint('tickets', __name__, url_prefix='/tickets')

VALID_PRIORITIES = ('low', 'medium', 'high', 'critical')
VALID_STATUSES = ('open', 'in_progress', 'resolved', 'closed')


@bp.route('/')
@login_required
def index():
    """
    List tickets with search keyword and multi-facet filtering.
    Enforces authorization:
    - Requesters can only view tickets they created.
    - Agents & Admins can view all enterprise tickets.
    """
    db = get_db()
    search = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()
    priority_filter = request.args.get('priority', '').strip()
    category_filter = request.args.get('category', '').strip()

    # Dynamic parameterized query construction
    where_clauses = []
    params = []

    # Requester isolation
    if g.user['role_name'] == 'requester':
        where_clauses.append("t.requester_id = ?")
        params.append(g.user['id'])

    # Keyword search across title and description
    if search:
        where_clauses.append("(t.title LIKE ? OR t.description LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    # Status filter
    if status_filter and status_filter in VALID_STATUSES:
        where_clauses.append("t.status = ?")
        params.append(status_filter)

    # Priority filter
    if priority_filter and priority_filter in VALID_PRIORITIES:
        where_clauses.append("t.priority = ?")
        params.append(priority_filter)

    # Category filter
    if category_filter and category_filter.isdigit():
        where_clauses.append("t.category_id = ?")
        params.append(int(category_filter))

    sql = """
        SELECT t.id, t.title, t.priority, t.status, t.created_at, t.updated_at, t.resolved_at,
               c.name AS category_name,
               req.username AS requester_name,
               assignee.username AS assignee_name
        FROM tickets t
        JOIN categories c ON t.category_id = c.id
        JOIN users req ON t.requester_id = req.id
        LEFT JOIN users assignee ON t.assignee_id = assignee.id
    """

    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)

    sql += " ORDER BY t.created_at DESC"

    tickets = db.execute(sql, params).fetchall()
    categories = db.execute("SELECT id, name FROM categories ORDER BY name ASC").fetchall()

    return render_template(
        'tickets/index.html',
        tickets=tickets,
        categories=categories,
        search=search,
        selected_status=status_filter,
        selected_priority=priority_filter,
        selected_category=category_filter
    )


@bp.route('/create', methods=('GET', 'POST'))
@login_required
def create():
    """
    Create a new incident ticket.
    Validates input parameters and logs creation event.
    """
    db = get_db()
    categories = db.execute("SELECT id, name, description FROM categories ORDER BY name ASC").fetchall()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category_id = request.form.get('category_id', '').strip()
        priority = request.form.get('priority', '').strip()
        error = None

        if not title:
            error = 'Ticket title is required.'
        elif len(title) > 150:
            error = 'Title must be 150 characters or fewer.'
        elif not description:
            error = 'Ticket description is required.'
        elif not category_id or not category_id.isdigit():
            error = 'A valid category must be selected.'
        elif priority not in VALID_PRIORITIES:
            error = f"Invalid priority. Choose from: {', '.join(VALID_PRIORITIES)}."

        # Verify category exists
        if error is None:
            cat_row = db.execute("SELECT id FROM categories WHERE id = ?", (int(category_id),)).fetchone()
            if not cat_row:
                error = 'Selected category does not exist.'

        if error is None:
            cursor = db.execute(
                """
                INSERT INTO tickets (title, description, category_id, priority, status, requester_id)
                VALUES (?, ?, ?, ?, 'open', ?)
                """,
                (title, description, int(category_id), priority, g.user['id'])
            )
            ticket_id = cursor.lastrowid
            db.commit()

            log_audit_event(
                action='TICKET_CREATED',
                target_type='ticket',
                target_id=ticket_id,
                details=f"Created ticket '{title}' with priority '{priority}'"
            )

            flash(f"Ticket #{ticket_id} submitted successfully.", 'success')
            return redirect(url_for('tickets.detail', ticket_id=ticket_id))

        flash(error, 'danger')

    return render_template('tickets/create.html', categories=categories, priorities=VALID_PRIORITIES)


@bp.route('/<int:ticket_id>')
@login_required
def detail(ticket_id):
    """
    View ticket details, comments, and change history.
    Enforces authorization:
    - Requesters can only view tickets they filed.
    - Internal comments are hidden from requesters.
    """
    db = get_db()
    ticket = db.execute(
        """
        SELECT t.id, t.title, t.description, t.priority, t.status, t.created_at, t.updated_at, t.resolved_at,
               t.category_id, t.requester_id, t.assignee_id,
               c.name AS category_name,
               req.username AS requester_name, req.email AS requester_email,
               assignee.username AS assignee_name
        FROM tickets t
        JOIN categories c ON t.category_id = c.id
        JOIN users req ON t.requester_id = req.id
        LEFT JOIN users assignee ON t.assignee_id = assignee.id
        WHERE t.id = ?
        """,
        (ticket_id,)
    ).fetchone()

    if ticket is None:
        abort(404, description=f"Ticket #{ticket_id} not found.")

    # Authorization check for Requesters
    if g.user['role_name'] == 'requester' and ticket['requester_id'] != g.user['id']:
        log_audit_event(
            action='UNAUTHORIZED_TICKET_INSPECTION',
            target_type='ticket',
            target_id=ticket_id,
            details=f"Requester {g.user['username']} attempted to view ticket #{ticket_id} owned by requester ID {ticket['requester_id']}"
        )
        abort(403, description="Access Forbidden: You do not have permission to view this ticket.")

    # Fetch comments (Hide internal notes from requesters)
    if g.user['role_name'] == 'requester':
        comments = db.execute(
            """
            SELECT c.id, c.comment, c.is_internal, c.created_at, u.username, r.name AS role_name
            FROM ticket_comments c
            JOIN users u ON c.user_id = u.id
            JOIN roles r ON u.role_id = r.id
            WHERE c.ticket_id = ? AND c.is_internal = 0
            ORDER BY c.created_at ASC
            """,
            (ticket_id,)
        ).fetchall()
    else:
        comments = db.execute(
            """
            SELECT c.id, c.comment, c.is_internal, c.created_at, u.username, r.name AS role_name
            FROM ticket_comments c
            JOIN users u ON c.user_id = u.id
            JOIN roles r ON u.role_id = r.id
            WHERE c.ticket_id = ?
            ORDER BY c.created_at ASC
            """,
            (ticket_id,)
        ).fetchall()

    # Fetch available agents for reassignment (only for Admin/Agent)
    agents = []
    if g.user['role_name'] in ('admin', 'agent'):
        agents = db.execute(
            """
            SELECT u.id, u.username
            FROM users u
            JOIN roles r ON u.role_id = r.id
            WHERE r.name IN ('admin', 'agent') AND u.is_active = 1
            ORDER BY u.username ASC
            """
        ).fetchall()

    # Fetch ticket audit logs (timeline)
    audit_trail = db.execute(
        """
        SELECT a.action, a.details, a.created_at, u.username
        FROM audit_logs a
        LEFT JOIN users u ON a.user_id = u.id
        WHERE a.target_type = 'ticket' AND a.target_id = ?
        ORDER BY a.created_at DESC
        LIMIT 10
        """,
        (ticket_id,)
    ).fetchall()

    return render_template(
        'tickets/detail.html',
        ticket=ticket,
        comments=comments,
        agents=agents,
        audit_trail=audit_trail,
        valid_statuses=VALID_STATUSES,
        valid_priorities=VALID_PRIORITIES
    )


@bp.route('/<int:ticket_id>/comment', methods=('POST',))
@login_required
def add_comment(ticket_id):
    """
    Add a comment or internal agent note to a ticket.
    Requesters can never submit internal notes (server-side enforcement).
    """
    db = get_db()
    ticket = db.execute("SELECT id, requester_id FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if ticket is None:
        abort(404, description=f"Ticket #{ticket_id} not found.")

    if g.user['role_name'] == 'requester' and ticket['requester_id'] != g.user['id']:
        abort(403)

    comment_text = request.form.get('comment', '').strip()
    is_internal = 1 if request.form.get('is_internal') and g.user['role_name'] in ('admin', 'agent') else 0

    if not comment_text:
        flash('Comment cannot be empty.', 'danger')
        return redirect(url_for('tickets.detail', ticket_id=ticket_id))

    db.execute(
        """
        INSERT INTO ticket_comments (ticket_id, user_id, comment, is_internal)
        VALUES (?, ?, ?, ?)
        """,
        (ticket_id, g.user['id'], comment_text, is_internal)
    )
    # Touch updated_at on ticket
    db.execute("UPDATE tickets SET updated_at = CURRENT_TIMESTAMP WHERE id = ?", (ticket_id,))
    db.commit()

    log_audit_event(
        action='COMMENT_ADDED',
        target_type='ticket',
        target_id=ticket_id,
        details=f"Added {'internal note' if is_internal else 'public comment'}"
    )

    flash('Comment added successfully.', 'success')
    return redirect(url_for('tickets.detail', ticket_id=ticket_id))


@bp.route('/<int:ticket_id>/status', methods=('POST',))
@login_required
def update_status(ticket_id):
    """
    Update ticket status, priority, or assignee.
    - Admins and Agents can update all fields.
    - Requesters can only close their own ticket if it is already resolved.
    """
    db = get_db()
    ticket = db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if ticket is None:
        abort(404, description=f"Ticket #{ticket_id} not found.")

    new_status = request.form.get('status', '').strip()
    new_priority = request.form.get('priority', '').strip()
    new_assignee = request.form.get('assignee_id', '').strip()

    # Requester permissions
    if g.user['role_name'] == 'requester':
        if ticket['requester_id'] != g.user['id']:
            abort(403)
        if new_status == 'closed' and ticket['status'] == 'resolved':
            db.execute("UPDATE tickets SET status = 'closed', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (ticket_id,))
            db.commit()
            log_audit_event(
                action='TICKET_CLOSED_BY_REQUESTER',
                target_type='ticket',
                target_id=ticket_id,
                details="Requester verified and closed resolved ticket"
            )
            flash('Ticket closed.', 'success')
            return redirect(url_for('tickets.detail', ticket_id=ticket_id))
        else:
            abort(403, description="Requesters can only close resolved tickets.")

    # Agent / Admin permissions
    if new_status not in VALID_STATUSES:
        flash(f"Invalid status '{new_status}'.", 'danger')
        return redirect(url_for('tickets.detail', ticket_id=ticket_id))

    if new_priority and new_priority not in VALID_PRIORITIES:
        flash(f"Invalid priority '{new_priority}'.", 'danger')
        return redirect(url_for('tickets.detail', ticket_id=ticket_id))

    assignee_id = None
    if new_assignee and new_assignee.isdigit():
        assignee_id = int(new_assignee)

    # Calculate resolved_at timestamp
    resolved_at_sql = ""
    if new_status in ('resolved', 'closed') and ticket['status'] not in ('resolved', 'closed'):
        resolved_at_sql = ", resolved_at = CURRENT_TIMESTAMP"
    elif new_status in ('open', 'in_progress'):
        resolved_at_sql = ", resolved_at = NULL"

    priority_to_set = new_priority if new_priority else ticket['priority']

    db.execute(
        f"""
        UPDATE tickets
        SET status = ?, priority = ?, assignee_id = ?, updated_at = CURRENT_TIMESTAMP {resolved_at_sql}
        WHERE id = ?
        """,
        (new_status, priority_to_set, assignee_id, ticket_id)
    )
    db.commit()

    changes = []
    if new_status != ticket['status']:
        changes.append(f"status: {ticket['status']} -> {new_status}")
    if priority_to_set != ticket['priority']:
        changes.append(f"priority: {ticket['priority']} -> {priority_to_set}")
    if assignee_id != ticket['assignee_id']:
        changes.append(f"assignee: {ticket['assignee_id']} -> {assignee_id}")

    change_desc = ", ".join(changes) if changes else "Updated metadata"

    log_audit_event(
        action='TICKET_UPDATED',
        target_type='ticket',
        target_id=ticket_id,
        details=f"Updated ticket #{ticket_id}: {change_desc}"
    )

    flash(f"Ticket #{ticket_id} updated: {change_desc}.", 'success')
    return redirect(url_for('tickets.detail', ticket_id=ticket_id))
