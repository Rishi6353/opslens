import secrets
from flask import session, request, abort, g
from app.audit.logger import log_audit_event


def generate_csrf_token():
    """
    Generates a cryptographically strong CSRF token and stores it in the user's session.
    Synchronizer Token Pattern ensures requests originate from our own pages.
    """
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(32)
    return session['csrf_token']


def validate_csrf():
    """
    Validates CSRF token on all state-changing HTTP requests.
    Exempts safe read-only methods (GET, HEAD, OPTIONS).
    """
    if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
        # Allow checking either form field or custom HTTP header (for AJAX/fetch)
        token = request.form.get('csrf_token') or request.headers.get('X-CSRFToken')
        session_token = session.get('csrf_token')

        if not token or not session_token or not secrets.compare_digest(token, session_token):
            user_id = session.get('user_id')
            log_audit_event(
                action='CSRF_VALIDATION_FAILED',
                target_type='security',
                target_id=None,
                details=f"Invalid CSRF token on {request.path} from IP {request.remote_addr}",
                user_id=user_id
            )
            abort(403, description="CSRF token validation failed. Possible Cross-Site Request Forgery detected.")
