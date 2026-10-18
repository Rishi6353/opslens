import functools
from flask import g, redirect, url_for, abort, request
from app.audit.logger import log_audit_event


def login_required(view):
    """
    Decorator requiring an active authenticated user session.
    Redirects unauthenticated visitors to the login view with a 'next' redirect URL.
    """
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login', next=request.path))
        return view(**kwargs)
    return wrapped_view


def roles_required(*allowed_roles):
    """
    Server-side Role-Based Access Control (RBAC) decorator.
    
    Usage:
        @roles_required('admin')
        @roles_required('admin', 'agent')
        
    Enforces authorization on the backend, preventing privilege escalation.
    """
    def decorator(view):
        @functools.wraps(view)
        def wrapped_view(**kwargs):
            if g.user is None:
                return redirect(url_for('auth.login', next=request.path))

            user_role = g.user['role_name']
            if user_role not in allowed_roles:
                log_audit_event(
                    action='UNAUTHORIZED_ACCESS_ATTEMPT',
                    target_type='route',
                    target_id=None,
                    details=f"User {g.user['username']} ({user_role}) attempted unauthorized access to {request.path}. Allowed roles: {allowed_roles}"
                )
                abort(403, description="Access Forbidden: You do not possess the required role permissions.")

            return view(**kwargs)
        return wrapped_view
    return decorator

