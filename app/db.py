import sqlite3
import click
from flask import current_app, g
from flask.cli import with_appcontext


def get_db():
    """
    Returns an active database connection for the current application context.
    Connections are stored on Flask's `g` global object to ensure a single connection
    per HTTP request lifecycle.
    """
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'])
        # Allows accessing columns by name (row['title']) as well as index (row[0])
        g.db.row_factory = sqlite3.Row
        # CRITICAL: SQLite does not enforce foreign keys by default.
        # This PRAGMA ensures foreign key constraints and cascading deletes are strictly enforced.
        g.db.execute("PRAGMA foreign_keys = ON;")

    return g.db


def close_db(e=None):
    """
    Closes the database connection at the end of the request.
    """
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db():
    """
    Initializes the database schema using schema.sql.
    """
    db = get_db()
    with current_app.open_resource('schema.sql') as f:
        db.executescript(f.read().decode('utf8'))


def seed_db():
    """
    Populates the database with realistic sample users, roles, categories, tickets, and logs.
    """
    db = get_db()
    with current_app.open_resource('seed.sql') as f:
        db.executescript(f.read().decode('utf8'))

@click.command('init-db')
@with_appcontext
def init_db_command():
    """Clear existing tables and create fresh database schema."""
    init_db()
    click.echo('Initialized the SQLite database schema.')


@click.command('seed-db')
@with_appcontext
def seed_db_command():
    """Populate the database with fictional enterprise seed data."""
    seed_db()
    click.echo('Populated database with realistic seed data.')


def migrate_db():
    """
    Safely migrates the SQLite schema without dropping tables or deleting data.
    Ensures ownership columns exist and handles legacy tickets without owners.
    """
    db = get_db()

    # 1. Inspect existing columns in tickets table
    columns_info = db.execute("PRAGMA table_info(tickets)").fetchall()
    column_names = [col['name'] for col in columns_info]

    # 2. Add requester_id if missing in legacy schemas
    if 'requester_id' not in column_names:
        db.execute("ALTER TABLE tickets ADD COLUMN requester_id INTEGER REFERENCES users(id)")
        db.commit()

    # 3. Handle legacy tickets without owners safely
    # Check if any tickets have null requester_id and assign them to fallback admin/system user
    admin_user = db.execute("SELECT id FROM users WHERE role_id = 1 LIMIT 1").fetchone()
    fallback_id = admin_user['id'] if admin_user else 1

    null_count = db.execute("SELECT COUNT(*) AS cnt FROM tickets WHERE requester_id IS NULL").fetchone()['cnt']
    if null_count > 0:
        db.execute("UPDATE tickets SET requester_id = ? WHERE requester_id IS NULL", (fallback_id,))
        db.commit()

    # 4. Ensure resolved_at column exists for legacy schemas and add index
    if 'resolved_at' not in column_names:
        db.execute("ALTER TABLE tickets ADD COLUMN resolved_at TIMESTAMP")
        db.commit()

    db.execute("CREATE INDEX IF NOT EXISTS idx_tickets_resolved_at ON tickets(resolved_at)")
    db.commit()

    # 5. Composite index for status-based date filtering (covering index)
    if 'status' in column_names and 'created_at' in column_names:
        db.execute("CREATE INDEX IF NOT EXISTS idx_tickets_status_created ON tickets(status, created_at)")
        db.commit()

    return null_count


@click.command('migrate-db')
@with_appcontext
def migrate_db_command():
    """Safely apply database schema updates and patch legacy tickets."""
    patched = migrate_db()
    click.echo(f"Database migration completed successfully. Patched {patched} legacy ticket(s).")


@click.command('create-admin')
@click.option('--username', default=None, help='Admin username')
@click.option('--email', default=None, help='Admin email')
@click.option('--password', default=None, help='Admin password')
@with_appcontext
def create_admin_command(username, email, password):
    """
    Secure local setup command to initialize the first admin account.
    Prompts securely for password without echoing to terminal or exposing credentials.
    """
    from werkzeug.security import generate_password_hash

    db = get_db()

    # Prompt securely if not provided via options
    if not username:
        username = click.prompt('Admin username', default='admin')
    username = username.strip()

    if not email:
        email = click.prompt('Admin email', default='admin@opslens.local')
    email = email.strip()

    if not password:
        password = click.prompt('Admin password', hide_input=True, confirmation_prompt=True)

    if len(password) < 8:
        click.echo('Error: Admin password must be at least 8 characters long.', err=True)
        return

    # Derive work-factored salted hash using scrypt
    password_hash = generate_password_hash(password, method='scrypt')

    # Ensure admin role exists
    admin_role = db.execute("SELECT id FROM roles WHERE name = 'admin'").fetchone()
    if not admin_role:
        cursor = db.execute("INSERT INTO roles (name, description) VALUES ('admin', 'System Administrator')")
        role_id = cursor.lastrowid
    else:
        role_id = admin_role['id']

    # Insert or update admin record
    existing_user = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if existing_user:
        db.execute(
            """
            UPDATE users
            SET email = ?, password_hash = ?, role_id = ?, is_active = 1
            WHERE id = ?
            """,
            (email, password_hash, role_id, existing_user['id'])
        )
        db.commit()
        click.echo(f"Successfully updated user '{username}' and verified Administrator role.")
    else:
        db.execute(
            """
            INSERT INTO users (username, email, password_hash, role_id, is_active)
            VALUES (?, ?, ?, ?, 1)
            """,
            (username, email, password_hash, role_id)
        )
        db.commit()
        click.echo(f"Successfully created Administrator account '{username}'.")


def init_app(app):
    """
    Register database functions and CLI commands with the Flask app instance.
    """
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(seed_db_command)
    app.cli.add_command(migrate_db_command)
    app.cli.add_command(create_admin_command)
