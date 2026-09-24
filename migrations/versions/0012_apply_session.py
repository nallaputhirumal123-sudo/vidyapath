"""Watching the worker's browser, and reaching into it, from inside Craxle.

An iframe cannot do this. Measured on the boards we drive: Ashby and
Workday both send `X-Frame-Options: DENY`, so a browser refuses to render
them inside our page whatever we do — and Workday is precisely the one
where a person has to sign in. That is their header, not our choice.

What is not blocked is a picture. The worker already runs a real Chromium
server-side; this streams that page in as PNG frames and sends clicks and
keystrokes back to it. No iframe, so no header applies, and the candidate
never leaves Craxle.

The shape, and why:

**A session belongs to one queued row.** It exists to unstick that row —
a sign-in the employer wants, a question nothing could answer — and it
closes when the row moves on. It is not a general-purpose browser, and
making it one would be handing out a server-side proxy to the internet.

**The worker holds the page, not the web app.** The web image has no
Chromium and should not grow one. So this table is the channel between
them: the app writes what the person did, the worker applies it and
writes back what the page looks like now. About a second of latency,
which is the cost of not having a socket between two Railway services.

**It expires.** A held browser context is memory in the worker and an open
session on somebody's employer account. `expires_at` is short and the
worker closes anything past it, so a person who walks away does not leave
a browser logged into their Workday account for a day.

`shot` is a base64 PNG rather than a file: it is one frame, overwritten
every poll, and a file per frame is a disk to clean up. `acts` is a JSON
queue the worker drains — a list rather than a single value, because two
clicks in quick succession must not lose the first.

Revision ID: 0012_apply_session
Revises: 0011_ats_account
"""
import sqlalchemy as sa
from alembic import op

revision = "0012_apply_session"
down_revision = "0011_ats_account"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "apply_session",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        # The row this exists to unstick. Not a FK for the same reason
        # apply_queue.job_id is not one: rows are pruned and a session that
        # outlives its row should die quietly, not block a delete.
        sa.Column("queue_id", sa.Integer(), nullable=True, index=True),
        # asked -> live -> closed. "asked" is the person pressing the button;
        # the worker moves it to live when it has a page open.
        sa.Column("status", sa.String(length=20), server_default="asked",
                  nullable=True, index=True),
        sa.Column("url", sa.Text(), server_default="", nullable=True),
        # One frame, base64 PNG, overwritten on every poll.
        sa.Column("shot", sa.Text(), server_default="", nullable=True),
        sa.Column("shot_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("width", sa.Integer(), server_default="1100", nullable=True),
        sa.Column("height", sa.Integer(), server_default="760", nullable=True),
        # A JSON list the worker drains: clicks, typing, keys, scrolls. A
        # list and not one value, because two clicks in quick succession
        # must not lose the first.
        sa.Column("acts", sa.Text(), server_default="", nullable=True),
        sa.Column("note", sa.Text(), server_default="", nullable=True),
        # Short. A held context is memory in the worker and an open session
        # on somebody's employer account; a person who walks away must not
        # leave either lying around.
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_applysess_live", "apply_session",
                    ["status", "expires_at"])


def downgrade():
    op.drop_index("ix_applysess_live", table_name="apply_session")
    op.drop_table("apply_session")
