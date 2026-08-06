"""Axle Pro is free for teachers, including the ones who were learners first.

0003 marked staff accounts that had no kind at all, which covered everybody a
school had created. It missed the other way in: somebody who signed up to
Craxle as an ordinary learner, was given a subject code by a school months
later, and redeemed it. That account already had a kind — 'learner', or
whatever the signup wrote — so 0003 stepped over it by design, and `plan_of`
reads kind, so the teacher stayed on the free plan at the school employing
them.

It shows up as the worst possible thing: a lesson on a classroom wall
stopping to offer the teacher a personal subscription for a tool the school
has already paid for, in front of the class.

Data only, and still narrow. It marks an account as school staff when it
holds a teacher_access row and is NOT already one of the school kinds — and
never touches 'classcode', which is a child's sign-in and must not be
confused with staff at any price.

Revision ID: 0004_teachers_are_pro
Revises: 0003_mark_school_staff
"""
from alembic import op

revision = "0004_teachers_are_pro"
down_revision = "0003_mark_school_staff"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        UPDATE users
           SET kind = 'schoolstaff'
         WHERE COALESCE(kind, '') NOT IN
               ('classcode', 'schoolcode', 'schoolstaff')
           AND id IN (SELECT user_id FROM teacher_access)
    """)


def downgrade():
    # Not reversible in the sense that matters: the previous value is not
    # recorded anywhere, and guessing it wrong takes a board away from a
    # school that is entitled to it. Left alone on purpose.
    pass
