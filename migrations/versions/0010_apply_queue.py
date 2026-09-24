"""Applying for the job, without the candidate sitting there doing it.

Matching already works and costs nothing. What happens next is still forty
minutes of retyping the same nine answers into the same nine boxes, on a
form the employer's ATS generated from a template. That is the part people
give up on, and giving up is why a good match never becomes an application.

Three tables, and each exists for a reason worth stating.

**apply_consent** — nothing may be submitted in somebody's name without a
live row here. Not a checkbox in a settings screen: a row with a timestamp
on it, so "did this person agree, and when, and to what" has an answer that
survives a UI rewrite. Revoking writes `revoked_at` rather than deleting,
because the question a complaint asks is "was there consent at the time",
and a deleted row cannot answer it.

**answer_bank** — the other half of the cost. Every ATS asks the same
handful of questions in slightly different words: work authorisation,
sponsorship, notice period, salary, how you heard. Asked once, answered
once, reused forever. `question_norm` is the question with punctuation and
required-field asterisks stripped, whitespace collapsed, lowercased — the
same normalisation `extension/filler.js` does in `clean()`, because the
worker and the bank have to agree on what counts as the same question or
the bank never hits.

There is deliberately no model here. Answer lookup is a dictionary
lookup on a normalised string. A question this cannot resolve parks the
row for a human rather than being guessed at, which is the only honest
behaviour when the output is submitted to an employer under somebody's
real name.

**apply_queue** — one row per attempt. `job_id` is a plain Integer and not
a foreign key, and title/company/url are copied in, for exactly the reason
JobTrack does the same: postings get pruned, and an application history
that disappears when the listing closes is not a history.

`hold_until` is the cancellation window. A row does not go from prepared
straight to submitted; it sits in `holding` with a screenshot of the filled
form, and the candidate can look at it and stop it. Fifteen minutes by
default; zero means submit immediately, which is a choice someone can make
rather than one made for them.

`attempt` caps at three. A form that has failed three times is not going to
work on the fourth, and hammering an employer's ATS is how one bad row gets
a whole domain blocked.

Revision ID: 0010_apply_queue
Revises: 0009_recall
"""
import sqlalchemy as sa
from alembic import op

revision = "0010_apply_queue"
down_revision = "0009_recall"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "apply_consent",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=True),
        # What was agreed to, in the words that were on screen. Kept verbatim
        # rather than as a version number: the wording is the agreement, and
        # a number is only as good as the copy of the text it points at.
        sa.Column("scope", sa.Text(), server_default="", nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "answer_bank",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("question_norm", sa.String(length=300), nullable=False,
                  index=True),
        sa.Column("answer", sa.Text(), server_default="", nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "question_norm",
                            name="uq_answer_user_question"),
    )

    op.create_table(
        "apply_queue",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        # Not a FK, and copied fields beside it: jobs get pruned, and an
        # application that vanishes with the listing is not a record.
        sa.Column("job_id", sa.Integer(), nullable=True, index=True),
        sa.Column("source", sa.String(length=40), server_default="",
                  nullable=True),
        sa.Column("url", sa.Text(), server_default="", nullable=True),
        sa.Column("title", sa.String(length=300), server_default="",
                  nullable=True),
        sa.Column("company", sa.String(length=200), server_default="",
                  nullable=True),
        sa.Column("status", sa.String(length=20), server_default="prepared",
                  nullable=True, index=True),
        sa.Column("score", sa.Integer(), server_default="0", nullable=True),
        # What was answered, and what could not be. missing_json is the list
        # a human is asked to fill; it is what makes needs_answer actionable
        # instead of a dead end.
        sa.Column("answers_json", sa.Text(), server_default="", nullable=True),
        sa.Column("missing_json", sa.Text(), server_default="", nullable=True),
        sa.Column("hold_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("screenshot_path", sa.Text(), server_default="",
                  nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmation", sa.Text(), server_default="", nullable=True),
        sa.Column("error", sa.Text(), server_default="", nullable=True),
        sa.Column("attempt", sa.Integer(), server_default="0", nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    # The two questions ever asked of this table: "what does this person have
    # in flight" for the screen, and "what is ready to run" for the worker.
    op.create_index("ix_applyq_user_status", "apply_queue",
                    ["user_id", "status"])
    op.create_index("ix_applyq_status_hold", "apply_queue",
                    ["status", "hold_until"])
    # The per-company-per-hour brake reads this one. Twelve applications into
    # one employer in an hour is what gets a whole domain blocked, so the
    # count that prevents it must not become a scan.
    op.create_index("ix_applyq_company_sent", "apply_queue",
                    ["company", "submitted_at"])


def downgrade():
    op.drop_index("ix_applyq_company_sent", table_name="apply_queue")
    op.drop_index("ix_applyq_status_hold", table_name="apply_queue")
    op.drop_index("ix_applyq_user_status", table_name="apply_queue")
    op.drop_table("apply_queue")
    op.drop_table("answer_bank")
    op.drop_table("apply_consent")
