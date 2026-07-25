FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies first, so Docker caches this layer between code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Strip any Windows carriage returns. Git on Windows can rewrite line
# endings, and a CRLF in a shell script breaks its shebang so the container
# exits immediately with no log output at all.
RUN sed -i 's/\r$//' /app/start.sh && chmod +x /app/start.sh

EXPOSE 8000

# Invoked as "sh /app/start.sh" rather than relying on the executable bit
# or the shebang — one less thing that can silently fail.
# Do NOT add a startCommand to railway.json: it bypasses the shell, so
# "$PORT" arrives as a literal string and uvicorn cannot parse it.
CMD ["sh", "/app/start.sh"]
