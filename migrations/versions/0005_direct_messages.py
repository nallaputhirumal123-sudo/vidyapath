"""A private line between one child and the teacher of one subject.

The classroom discussion is the group, one thread per subject, in front of
everybody. This is the other half: a child who will not put their hand up,
and will not type the question under their own name in front of thirty
classmates.

Anchored to (class_id, subject) as well as to the two people, because that is
what makes the permission answerable. The same two accounts may be
teacher-and-pupil in Physics and nothing to each other in Maths, and a thread
that had forgotten which one it belonged to could not tell.

There is no student-to-student table here and that is deliberate, not an
omission to fill in later. A school that hands thirty children a private
channel to each other has taken on moderating it, in the evenings, in a
product with no moderators.

Revision ID: 0005_direct_messages
Revises: 0004_teachers_are_pro
"""
import sqlalchemy as sa
from alembic import op

revision = "0005_direct_messages"
down_revision = "0004_teachers_are_pro"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "direct_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("class_id", sa.Integer(),
                  sa.ForeignKey("classes.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("subject", sa.String(length=80), server_default=""),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("from_teacher", sa.Boolean(), server_default=sa.false()),
        sa.Column("body", sa.Text(), server_default=""),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now()),
    )
    op.create_index("ix_direct_messages_class_id", "direct_messages",
                    ["class_id"])
    op.create_index("ix_direct_messages_student_id", "direct_messages",
                    ["student_id"])
    op.create_index("ix_direct_messages_teacher_id", "direct_messages",
                    ["teacher_id"])
    op.create_index("ix_direct_messages_created_at", "direct_messages",
                    ["created_at"])
    # The one query the inbox actually runs: everything for one conversation,
    # in order. Without it that is a scan of every message in the school.
    op.create_index("ix_direct_messages_thread", "direct_messages",
                    ["class_id", "student_id", "teacher_id", "created_at"])


def downgrade():
    op.drop_index("ix_direct_messages_thread", table_name="direct_messages")
    op.drop_index("ix_direct_messages_created_at", table_name="direct_messages")
    op.drop_index("ix_direct_messages_teacher_id", table_name="direct_messages")
    op.drop_index("ix_direct_messages_student_id", table_name="direct_messages")
    op.drop_index("ix_direct_messages_class_id", table_name="direct_messages")
    op.drop_table("direct_messages")
