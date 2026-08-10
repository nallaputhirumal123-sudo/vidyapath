"""A phone number on an account.

The account screen — name, phone, password, plan — had nowhere to keep a
number. A school office rings a teacher; a parent gives one when a password
has gone. It was the one thing on that screen with no column behind it.

Nullable with an empty default, not NOT NULL. The table has rows already,
and ADD COLUMN ... NOT NULL without a default fails on every one of them.

It is deliberately NOT part of signing in. An SMS second factor on a shared
classroom device is a lockout waiting for the first day the phone is at
home, in a building where the person who could fix it is teaching until
half past three.

Revision ID: 0006_user_phone
Revises: 0005_direct_messages
"""
import sqlalchemy as sa
from alembic import op

revision = "0006_user_phone"
down_revision = "0005_direct_messages"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users",
                  sa.Column("phone", sa.String(length=32),
                            server_default="", nullable=True))


def downgrade():
    op.drop_column("users", "phone")
