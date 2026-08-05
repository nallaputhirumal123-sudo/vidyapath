#!/bin/sh
# Craxlearn startup. Runs through a shell so $PORT is a real number.

PORT="${PORT:-8000}"

echo "=============================================="
echo "  Craxlearn starting"
echo "  version : $(cat /app/VERSION 2>/dev/null || echo unknown)"
echo "  port    : $PORT"
echo "  database: $(if [ -n "$DATABASE_URL" ]; then echo "DATABASE_URL is set"; else echo "NOT SET"; fi)"
echo "  admin   : $(if [ -n "$ADMIN_EMAIL" ]; then echo "ADMIN_EMAIL is set"; else echo "NOT SET"; fi)"
echo "  jwt     : $(if [ -n "$JWT_SECRET" ]; then echo "JWT_SECRET is set"; else echo "NOT SET"; fi)"
echo "=============================================="

# Preflight, before anything else.
#
# Migrations are NOT run here, on purpose. Applying them on start puts schema
# changes on the same trigger as a restart: a crash loop would replay them,
# and two instances booting together would race each other through them. They
# are applied deliberately:
#
#     alembic upgrade head
#
# What this does instead is refuse to start when the database is not at the
# revision this code was built against. A release whose migration has not
# been applied must fail as a deploy, not survive as a healthy container
# serving 500s from whichever routes happen to touch a new column first.
python /app/preflight.py || {
    echo ""
    echo "FATAL: preflight failed. The app will not start."
    echo "If a migration is pending, run:  alembic upgrade head"
    exit 1
}

# Fail loudly and immediately if the app cannot even be imported, rather
# than letting the container die silently with an unreadable healthcheck error.
python -c "import main" || {
    echo ""
    echo "FATAL: main.py failed to import. The traceback above is the cause."
    exit 1
}

exec uvicorn main:app --host 0.0.0.0 --port "$PORT"
