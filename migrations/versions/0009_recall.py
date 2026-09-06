"""What you could not do yet, and when to ask you again.

The platform recorded that a lesson was finished and what a quiz scored.
Neither of those is learning: finishing is a timestamp, and a score is a
photograph of one afternoon. Nothing anywhere remembered the thing somebody
got WRONG, and nothing ever brought it back.

That is the whole gap between this and asking a chat assistant. An assistant
explains beautifully, you nod, and it is gone by Thursday -- it has no idea
what you failed at on Monday and no reason to ask you again. Recall does:
one row per thing you could not produce, with the date it should be put in
front of you next.

The schedule is the boring, proven one. Right and the gap widens; wrong and
it comes back tomorrow. Strength is 0-5 and indexes the interval table in
main.py, so the arithmetic lives in one place and this table just stores
where somebody got to.

Notes on the columns:

  due_at is indexed WITH user_id, because the only question ever asked of
  this table is "what does this person owe today", and on a table that grows
  by a row every time anybody gets anything wrong that query must not become
  a scan.

  prompt_key is a hash of the question, not the question. It exists so the
  same thing failed twice is one row that got harder rather than two rows
  that both come back -- and a unique index on (user_id, prompt_key) is what
  enforces that, rather than a read-then-write that races itself.

Revision ID: 0009_recall
Revises: 0008_material_folder
"""
import sqlalchemy as sa
from alembic import op

revision = "0009_recall"
down_revision = "0008_material_folder"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "recall",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        # quiz | sql | code | interview | ask — what kind of thing this is,
        # which decides how an attempt at it is marked.
        sa.Column("kind", sa.String(length=20), server_default="ask",
                  nullable=True),
        sa.Column("topic", sa.String(length=160), server_default="",
                  nullable=True),
        sa.Column("prompt", sa.Text(), server_default="", nullable=True),
        sa.Column("prompt_key", sa.String(length=64), nullable=False),
        # What a right answer has to contain or produce. For a quiz that is
        # the option; for SQL it is the expected result set; for a written
        # answer it is the points that had to appear.
        sa.Column("expect", sa.Text(), server_default="", nullable=True),
        sa.Column("source", sa.String(length=160), server_default="",
                  nullable=True),
        sa.Column("strength", sa.Integer(), server_default="0", nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("seen", sa.Integer(), server_default="0", nullable=True),
        sa.Column("right", sa.Integer(), server_default="0", nullable=True),
        sa.Column("wrong", sa.Integer(), server_default="0", nullable=True),
        sa.Column("last_attempt", sa.Text(), server_default="", nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "prompt_key", name="uq_recall_user_prompt"),
    )
    # The only query this table serves.
    op.create_index("ix_recall_due", "recall", ["user_id", "due_at"])


def downgrade():
    op.drop_index("ix_recall_due", table_name="recall")
    op.drop_table("recall")
