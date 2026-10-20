# ==============================================================================
# OpsLens Production Dockerfile
# Hardened, lightweight container image running under an unprivileged user
# ==============================================================================

FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    PORT=5001

# Create unprivileged system group and user (UID/GID 10001)
RUN groupadd --gid 10001 opslens && \
    useradd --uid 10001 --gid 10001 --no-create-home --shell /bin/sh opslens

WORKDIR /app

# Install production dependencies first to maximize Docker layer caching
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY --chown=opslens:opslens . /app

# Ensure instance directory exists with proper ownership and permissions for SQLite
RUN mkdir -p /app/instance && \
    chown -R opslens:opslens /app/instance && \
    chmod 770 /app/instance && \
    chmod +x /app/docker-entrypoint.sh

# Switch to the non-root user
USER opslens:opslens

# Expose internal WSGI port
EXPOSE 5001

# Health check using built-in Python urllib (no external curl/wget required)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://localhost:5001/health').getcode() == 200 else 1)"

# Entrypoint script performs pre-flight checks and safe schema initialization/migrations
ENTRYPOINT ["/app/docker-entrypoint.sh"]

# Production WSGI server command (executed via entrypoint exec "$@")
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "2", "--threads", "2", "--timeout", "60", "app:create_app()"]

