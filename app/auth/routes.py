from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g
from werkzeug.security import check_password_hash
from urllib.parse import urlsplit
from app.db import get_db
from app.audit.logger import log_audit_event
from app.auth.decorators import login_required
from app.security.csrf import generate_csrf_token

bp = Blueprint('auth', __name__, url_prefix='/auth')


@bp.before_app_request
def load_logged_in_user():
    """
    Runs before every request across all blueprints.
    Loads authenticated user record into Flask's `g.user` context.
    """
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        db = get_db()
        user = db.execute(
            """
            SELECT u.id, u.username, u.email, u.role_id, u.is_active, u.created_at,
                   r.name AS role_name, r.description AS role_description
            FROM users u
            JOIN roles r ON u.role_id = r.id
            WHERE u.id = ?
            """,
            (user_id,)
        ).fetchone()

        if user and user['is_active']:
            g.user = user
        else:
            # Inactive or deleted user: terminate session immediately
            session.clear()
            g.user = None


def is_safe_redirect_url(target):
    """
    Prevents Open Redirect vulnerabilities by ensuring target URL is relative.
    """
    if not target:
        return False
    ref_url = urlsplit(request.host_url)
    test_url = urlsplit(target)
    return test_url.scheme in ('', 'http', 'https') and (test_url.netloc == '' or test_url.netloc == ref_url.netloc)


@bp.route('/login', methods=('GET', 'POST'))
def login():
    """
    Handles secure user authentication with password hashing and session fixation prevention.
    """
    if g.user is not None:
        return redirect(url_for('analytics.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        error = None

        if not username:
            error = 'Username is required.'
        elif not password:
            error = 'Password is required.'

        if error is None:
            db = get_db()
            user = db.execute(
                """
                SELECT u.id, u.username, u.password_hash, u.is_active, r.name AS role_name
                FROM users u
                JOIN roles r ON u.role_id = r.id
                WHERE u.username = ?
                """,
                (username,)
            ).fetchone()

            if user is None or not check_password_hash(user['password_hash'], password):
                error = 'Invalid username or password.'
                log_audit_event(
                    action='LOGIN_FAILED',
                    target_type='user',
                    details=f"Failed login attempt for username '{username}'"
                )
            elif not user['is_active']:
                error = 'Your account has been deactivated. Please contact an administrator.'
                log_audit_event(
                    action='LOGIN_DEACTIVATED_ACCOUNT',
                    target_type='user',
                    target_id=user['id'],
                    details=f"Deactivated user '{username}' attempted login"
                )
            else:
                # Defend against Session Fixation: clear old session and re-issue fresh session ID
                session.clear()
                session['user_id'] = user['id']
                generate_csrf_token()

                log_audit_event(
                    action='LOGIN_SUCCESS',
                    target_type='user',
                    target_id=user['id'],
                    details=f"User '{username}' logged in successfully as {user['role_name']}"
                )

                flash(f"Welcome back, {user['username']}! Logged in as {user['role_name'].capitalize()}.", 'success')

                # Open Redirect Defense
                next_url = request.args.get('next')
                if next_url and is_safe_redirect_url(next_url):
                    return redirect(next_url)
                return redirect(url_for('analytics.dashboard'))

        flash(error, 'danger')

    return render_template('auth/login.html')


@bp.route('/logout', methods=('POST',))
@login_required
def logout():
    """
    Terminates the user session. Requires POST to prevent CSRF logout attacks.
    """
    user_id = g.user['id']
    username = g.user['username']
    session.clear()

    log_audit_event(
        action='USER_LOGOUT',
        target_type='user',
        target_id=user_id,
        details=f"User '{username}' logged out"
    )

    flash('You have been logged out securely.', 'info')
    return redirect(url_for('auth.login'))


@bp.route('/profile')
@login_required
def profile():
    """
    Displays the current user profile, role capabilities, and recent audit activity.
    """
    db = get_db()
    recent_activity = db.execute(
        """
        SELECT action, target_type, target_id, ip_address, details, created_at
        FROM audit_logs
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 10
        """,
        (g.user['id'],)
    ).fetchall()

    return render_template('auth/profile.html', user=g.user, activity=recent_activity)
