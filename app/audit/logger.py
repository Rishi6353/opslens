from flask import session, request, has_request_context
from app.db import get_db


def log_audit_event(action, target_type=None, target_id=None, details=None, user_id=None):
    """
    Records an immutable audit event in the database for compliance and security forensics.
    
    Parameters:
    - action: string, e.g., 'USER_LOGIN_SUCCESS', 'TICKET_STATUS_CHANGED', 'UNAUTHORIZED_ACCESS'
    - target_type: string, e.g., 'ticket', 'user', 'security'
    - target_id: integer or None, ID of target entity
    - details: string or None, contextual description
    - user_id: integer or None, actor's user ID (defaults to session['user_id'])
    """
    ip_address = '127.0.0.1'
    if has_request_context():
        if user_id is None:
            user_id = session.get('user_id')
        # Respect X-Forwarded-For if behind a reverse proxy, else request.remote_addr
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr or '127.0.0.1').split(',')[0].strip()

    try:
        db = get_db()
        db.execute(
            """
            INSERT INTO audit_logs (user_id, action, target_type, target_id, ip_address, details)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, action, target_type, target_id, ip_address, details)
        )
        db.commit()
    except Exception as e:
        # Avoid crashing app if audit log fails, but log to stderr/server logs
        print(f"[AUDIT LOG FAILURE] Error writing audit event: {e}")

