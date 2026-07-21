#!/bin/sh
# VidyaPath startup. Runs through a shell so $PORT is a real number.

PORT="${PORT:-8000}"

echo "=============================================="
echo "  VidyaPath starting"
echo "  version : $(cat /app/VERSION 2>/dev/null || echo unknown)"
echo "  port    : $PORT"
echo "  database: $(if [ -n "$DATABASE_URL" ]; then echo "DATABASE_URL is set"; else echo "NOT SET - will use SQLite"; fi)"
echo "  admin   : $(if [ -n "$ADMIN_EMAIL" ]; then echo "ADMIN_EMAIL is set"; else echo "NOT SET"; fi)"
echo "  jwt     : $(if [ -n "$JWT_SECRET" ]; then echo "JWT_SECRET is set"; else echo "NOT SET - sessions reset on deploy"; fi)"
echo "=============================================="

# Fail loudly and immediately if the app cannot even be imported, rather
# than letting the container die silently with an unreadable healthcheck error.
python -c "import main" || {
    echo ""
    echo "FATAL: main.py failed to import. The traceback above is the cause."
    exit 1
}

exec uvicorn main:app --host 0.0.0.0 --port "$PORT"
