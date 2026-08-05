"""Mark accounts a school already issued as school staff.

Everyone who arrives through a school code gets the Pro board — the pupil,
the teacher and the office — because the school has paid for its people and a
lesson on a classroom wall must not stop to advertise a subscription to a room
of children.

That is decided from users.kind, which is cheap enough to read on every
request. Accounts created from now on are marked when they are granted access.
Accounts that already existed were made before the mark did, so they carry an
empty kind and would have been quietly left on the free plan at the school
that employs them.

Data only: no column is added or changed. It sets kind = 'schoolstaff' for
every account holding a teacher_access row and no kind of its own.

Deliberately narrow. It never touches an account that already has a kind — a
pupil's 'classcode' or an administrator's 'schoolcode' both mean something and
neither is staff — and it never touches an account with no school role, which
is every ordinary learner on the site.

Revision ID: 0003_mark_school_staff
Revises: 0002_admin_code_identity
"""
from alembic import op

revision = "0003_mark_school_staff"
down_revision = "0002_admin_code_identity"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        UPDATE users
           SET kind = 'schoolstaff'
         WHERE (kind IS NULL OR kind = '')
           AND id IN (SELECT user_id FROM teacher_access)
    """)


def downgrade():
    # Only the ones this migration could have set. An account that was made
    # as school staff after this ran is left alone, because clearing it would
    # take away a board the school is entitled to.
    op.execute("""
        UPDATE users
           SET kind = ''
         WHERE kind = 'schoolstaff'
           AND id IN (SELECT user_id FROM teacher_access)
    """)
