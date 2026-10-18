import os
from flask import Flask, render_template
from app.security.csrf import generate_csrf_token, validate_csrf


def create_app(test_config=None):
    """
    Application Factory for OpsLens.
    
    Why Application Factory?
    1. Allows creating multiple app instances with distinct configurations (e.g. testing vs production).
    2. Isolates database connections and settings per instance.
    3. Prevents circular import issues between models, blueprints, and extensions.
    """
    app = Flask(__name__, instance_relative_config=True)

    # Default configuration
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-secret-fallback-key-do-not-use-in-prod'),
        DATABASE=os.path.join(app.instance_path, 'opslens.db'),
        SESSION_COOKIE_HTTPONLY=True,    # Mitigate XSS stealing session cookies
        SESSION_COOKIE_SAMESITE='Lax',   # Mitigate CSRF on top-level navigations
    )

    if test_config is None:
        # Load the instance config, if it exists, when not testing
        app.config.from_pyfile('config.py', silent=True)
    else:
        # Load the test config if passed in
        app.config.from_mapping(test_config)

    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass

    # Initialize Database management
    from app import db
    db.init_app(app)

    # Security Headers Hook (Defense-in-Depth against Clickjacking and MIME sniffing)
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        return response

    # CSRF Protection: Context processor to make csrf_token() available in all templates
    @app.context_processor
    def inject_csrf_token():
        return dict(csrf_token=generate_csrf_token)

    # CSRF Protection: Synchronizer Token validation on state-changing requests
    @app.before_request
    def enforce_csrf_protection():
        # Testing configuration can disable CSRF if specified
        if not app.config.get('TESTING_CSRF_DISABLED', False):
            validate_csrf()

    # Register blueprints
    from app.auth.routes import bp as auth_bp
    app.register_blueprint(auth_bp)

    from app.tickets.routes import bp as tickets_bp
    app.register_blueprint(tickets_bp)

    from app.analytics.routes import bp as analytics_bp
    app.register_blueprint(analytics_bp)

    # Register error handlers
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html', error=e), 403

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html', error=e), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html', error=e), 500

    return app
