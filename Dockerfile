FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first, so Docker caches this layer between code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# start.sh resolves $PORT properly and prints diagnostics before booting.
# Do NOT set a startCommand in railway.json — it bypasses the shell, so
# "$PORT" arrives as a literal string and uvicorn cannot parse it.
RUN chmod +x /app/start.sh
CMD ["/app/start.sh"]
