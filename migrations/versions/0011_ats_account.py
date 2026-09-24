"""The employer sites that need an account before they will take an application.

Workday is 872 of the open postings on this board across 39 employers, and
none of them could be applied to at all. Every Workday tenant is a separate
site with its own login: applying to Mastercard and to Adobe means two
accounts, not one.

The shape that works, and why it is this one:

**The candidate makes the account, not us.** Registering means accepting that
employer's terms, and a person has to do that themselves — it is a legal act
in their name. It also means a verification email, which goes to their inbox
and is theirs to open. So the worker stops at the door, says which employer
needs an account, and waits.

**And then it never stops again.** They do it once per employer; the
credentials are kept here, and every later posting from that employer goes
through without them. Mastercard alone is 367 of those 872 — one setup, and
the rest are automatic. That ratio is the whole reason this is worth a table.

The password is encrypted at rest with Fernet, keyed from APPLY_CRED_KEY.
Not hashed — a hash cannot be replayed into a login form, which is the entire
point of storing it. That means this column is genuinely dangerous if the
database leaks and the key does too, so:

  * the key lives in the environment, never in the database or the repo
  * with no key configured, credentials cannot be saved at all, rather than
    being saved in the clear
  * `verified_at` records that the person confirmed the account works, so the
    worker never sits in a login loop against a half-made one

`site` is the registrable host, not the full URL: one account serves every
posting on `mastercard.wd1.myworkdayjobs.com` and that is how it is looked
up. Unique per (user, site), because a second row for the same site is two
answers to "how do I sign in here" and no way to choose.

Revision ID: 0011_ats_account
Revises: 0010_apply_queue
"""
import sqlalchemy as sa
from alembic import op

revision = "0011_ats_account"
down_revision = "0010_apply_queue"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ats_account",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        # The registrable host: mastercard.wd1.myworkdayjobs.com serves every
        # Mastercard posting, and one account covers all of them.
        sa.Column("site", sa.String(length=200), nullable=False, index=True),
        # Shown on screen so somebody can tell which account is which.
        sa.Column("label", sa.String(length=200), server_default="",
                  nullable=True),
        sa.Column("username", sa.String(length=320), server_default="",
                  nullable=True),
        # Fernet, keyed from APPLY_CRED_KEY. Not a hash: a hash cannot be
        # typed into a login form, which is the only reason this exists.
        sa.Column("password_enc", sa.Text(), server_default="", nullable=True),
        # Set when the person says the account is made and verified. Until
        # then the worker will not try it, so it never loops on a half-made
        # account waiting for an email nobody has opened.
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        # What happened last time we signed in with it, so a password that
        # has been changed on the employer's side says so rather than failing
        # every application silently.
        sa.Column("last_used", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), server_default="", nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "site", name="uq_ats_user_site"),
    )


def downgrade():
    op.drop_table("ats_account")
