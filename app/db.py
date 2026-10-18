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


def init_app(app):
    """
    Register database functions with the Flask app instance.
    """
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(seed_db_command)
