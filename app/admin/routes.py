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
