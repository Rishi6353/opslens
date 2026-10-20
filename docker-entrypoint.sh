#!/bin/sh
set -e

# OpsLens Production Container Entrypoint
# Safeguards database integrity, enforces volume permissions, and avoids automatic data resets.

INSTANCE_DIR="/app/instance"
DB_FILE="${INSTANCE_DIR}/opslens.db"

# 1. Verify instance directory is writable by the running unprivileged user
if [ ! -d "$INSTANCE_DIR" ]; then
    echo "Creating instance directory at ${INSTANCE_DIR}..."
    mkdir -p "$INSTANCE_DIR"
fi

if [ ! -w "$INSTANCE_DIR" ]; then
    echo "CRITICAL ERROR: Instance directory ${INSTANCE_DIR} is not writable by current user (UID $(id -u))." >&2
    echo "Ensure the mounted host directory or Docker named volume has write permissions for UID 10001." >&2
    exit 1
fi

# 2. Safe Database Lifecycle Handling
if [ ! -f "$DB_FILE" ]; then
    echo "[Entrypoint] No existing database detected at ${DB_FILE}."
    echo "[Entrypoint] Initializing fresh database schema DDL..."
    python -m flask --app app:create_app init-db
    echo "[Entrypoint] Schema created successfully. (Notice: Database was NOT seeded to protect production integrity)."
    echo "[Entrypoint] Run 'docker exec -it <container_name> flask create-admin' to provision an admin account."
else
    echo "[Entrypoint] Existing database detected at ${DB_FILE}."
    echo "[Entrypoint] Applying non-destructive database migrations..."
    if ! python -m flask --app app:create_app migrate-db; then
        echo "CRITICAL ERROR: Migration failed against existing database. Aborting startup to prevent corruption." >&2
        exit 1
    fi
    echo "[Entrypoint] Migrations verified successfully."
fi

# 3. Hand over execution to the container CMD (e.g. Gunicorn WSGI server)
echo "[Entrypoint] Launching application server: $@"
exec "$@"

