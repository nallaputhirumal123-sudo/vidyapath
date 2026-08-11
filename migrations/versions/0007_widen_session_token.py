"""Make users.session_token as wide as the model has long claimed.

The model says String(400). The frozen DDL in 0001 says VARCHAR(400).
Neither is evidence about a database that existed before either was written,
because nothing in this codebase has ever widened a column — `_migrate_columns`
only ever ADDs one, and no migration until this one has issued an ALTER.

What that cost: session_token holds active session tokens comma-separated,
24 characters each. When staff were given four devices instead of one, the
third sign-in wrote 74 characters. Against a column built narrower than 400
Postgres refuses that with 22001, the old value stays in the row, and every
later attempt writes the same too-long string — so the account is locked out
for good rather than recovering. It struck the administrator first because
that is the account that signs in most, and nobody else because everyone
else still holds one device.

It could not be reproduced anywhere: SQLite ignores VARCHAR widths entirely,
so every local run and all 107 suites passed while production refused the
identical write.

ALTER ... TYPE VARCHAR(400) only ever widens here, so no value can be
truncated by it and it is safe to run on a table already at 400 — Postgres
rewrites nothing when the type is unchanged.

Revision ID: 0007_widen_session_token
Revises: 0006_user_phone
"""
import sqlalchemy as sa
from alembic import op

revision = "0007_widen_session_token"
down_revision = "0006_user_phone"
branch_labels = None
depends_on = None


def upgrade():
    # Measured, not assumed: the database reports VARCHAR(64) here while the
    # model has claimed 400 for a long time. 64 characters holds exactly two
    # 24-character tokens, so the third sign-in writes 74 and is refused.
    #
    # existing_type is stated as what is actually there. Naming 400 on both
    # sides would describe a change that is not the one being made.
    op.alter_column("users", "session_token",
                    existing_type=sa.String(length=64),
                    type_=sa.String(length=400),
                    existing_nullable=True)


def downgrade():
    # Deliberately nothing. Narrowing it again would truncate live sessions
    # and sign people out, to restore a width that was the bug.
    pass
