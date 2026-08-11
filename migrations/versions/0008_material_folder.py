"""Somewhere to put things, inside a subject.

Everything kept for a subject landed in one open list: a term of board
notes, downloaded pictures and uploaded chapters in a single column,
newest first. A teacher looking for last week's worksheet scrolled.

Two folders arrive on their own — what was Saved from the board, and what
was Downloaded — and the rest are whatever the teacher decides to call
them, because only she knows whether her class needs "Chapter 4" or
"Revision" or "Practicals". An empty folder means the subject's top level
rather than a folder named "".

Nullable with an empty default: the table has rows, and ADD COLUMN NOT NULL
without a default fails on every one of them.

Revision ID: 0008_material_folder
Revises: 0007_widen_session_token
"""
import sqlalchemy as sa
from alembic import op

revision = "0008_material_folder"
down_revision = "0007_widen_session_token"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("materials",
                  sa.Column("folder", sa.String(length=80),
                            server_default="", nullable=True))


def downgrade():
    op.drop_column("materials", "folder")
