# The auto-apply worker. A second Railway service from the same repository.
#
# Its own Dockerfile rather than a flag on the app's, because this image has
# to carry Chromium and its font and codec libraries — around 400 MB the web
# service would otherwise pay for on every deploy and never use.
#
# Built on the same python:3.11-slim the app uses, with the browsers pulled
# in by `playwright install --with-deps`, rather than on a prebuilt
# mcr.microsoft.com/playwright image. That image has to be tagged with the
# exact Playwright release, so the version would live in two places and a
# bump that missed one gives "the driver and the browsers disagree" on a
# Tuesday for no reason anybody changed. Here the pin in
# worker/requirements.txt is the only version there is.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Two COPY lines, not one. `COPY a b ./dir/` flattens both into dir/, both
# files are named requirements.txt, and one silently overwrites the other.
#
# Shared first, worker second. The root file pins SQLAlchemy and the rest,
# and both services must agree on those — this one reads the tables the web
# app writes.
COPY requirements.txt /app/requirements.txt
COPY worker/requirements.txt /app/worker-requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && pip install --no-cache-dir -r /app/worker-requirements.txt \
    && playwright install --with-deps chromium

COPY . .

# Strip Windows carriage returns, for the same reason the app's Dockerfile
# does: a CRLF in a shell script breaks its shebang and the container exits
# with no log output at all.
RUN find /app -maxdepth 2 -name "*.sh" -exec sed -i 's/\r$//' {} \;

# No EXPOSE and no healthcheck port: this service answers nothing. Railway
# should run it as a worker, not wait for a web target that never binds.
CMD ["python", "-m", "worker.run"]
