"""
Craxle — backend
FastAPI + SQLAlchemy. Postgres on Railway, SQLite locally.

Run locally:   uvicorn main:app --reload
Then open:     http://localhost:8000
Admin panel:   http://localhost:8000/admin
"""

import os
import re
import json
import math
import calendar
import secrets
import datetime as dt
from pathlib import Path
from functools import lru_cache
from typing import Optional, List

import bcrypt
import jwt
import base64
import io
import hashlib
import hmac
import time
import asyncio
import httpx
from urllib.parse import urlencode
from fastapi import (FastAPI, Depends, HTTPException, Request, Response, status,
                     UploadFile, File, Form, BackgroundTasks)
from fastapi.responses import (FileResponse, JSONResponse, RedirectResponse,
                               Response as RawResponse)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, Boolean, DateTime, Date,
    ForeignKey, UniqueConstraint, func, cast, case, or_, event,
)
from sqlalchemy.orm import (declarative_base, sessionmaker, Session,
                            relationship, defer)
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.exc import IntegrityError

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent

# ---- Version -------------------------------------------------------------
# Single source of truth: the VERSION file. Bump it on every push, then
# check the number shown on the live site to confirm what is deployed.
try:
    VERSION = (BASE_DIR / "VERSION").read_text(encoding="utf-8").strip()
except Exception:
    VERSION = "unknown"

# Railway supplies these automatically; they pin the exact commit deployed.
GIT_SHA = (os.environ.get("RAILWAY_GIT_COMMIT_SHA", "")[:7]
           or os.environ.get("SOURCE_COMMIT", "")[:7] or "local")
BUILT_AT = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

def env(name, default=""):
    """Read an environment variable, treating empty/whitespace as absent.

    os.environ.get(name, default) only falls back when the variable is
    MISSING. A variable that exists but is empty returns "" — which is how
    an unresolved Railway reference arrives, and it crashed the app on
    import with "Could not parse SQLAlchemy URL from string ''".
    """
    return (os.environ.get(name) or "").strip() or default


DATABASE_URL = env("DATABASE_URL", "sqlite:///./vidyapath.db")

# Railway hands out postgres:// ; SQLAlchemy 2 needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# An unresolved Railway reference arrives literally as "${{ ... }}"
if "${{" in DATABASE_URL or not DATABASE_URL.strip():
    print("WARNING: DATABASE_URL is empty or unresolved — falling back to "
          "SQLite. Data will NOT survive a redeploy. In Railway, add "
          "DATABASE_URL via '+ New Variable' > 'Add Reference' > Postgres.")
    DATABASE_URL = "sqlite:///./vidyapath.db"

JWT_SECRET = env("JWT_SECRET")
if not JWT_SECRET:
    # Fine for local dev; on Railway you MUST set this or sessions reset on redeploy.
    JWT_SECRET = "dev-only-insecure-secret-change-me"
    print("WARNING: JWT_SECRET not set — using an insecure development value.")

ADMIN_EMAIL = env("ADMIN_EMAIL").lower()
if "${{" in ADMIN_EMAIL:
    ADMIN_EMAIL = ""
ADMIN_PASSWORD = env("ADMIN_PASSWORD")
COOKIE_SECURE = env("COOKIE_SECURE", "1") != "0"
SESSION_DAYS = 60   # keep users signed in for two months

# ---- Google sign-in (optional) -------------------------------------------
# Switches on automatically when both keys are set, same as the AI provider.
# Create them at https://console.cloud.google.com/apis/credentials
GOOGLE_CLIENT_ID = env("GOOGLE_CLIENT_ID")
if "${{" in GOOGLE_CLIENT_ID:
    GOOGLE_CLIENT_ID = ""
GOOGLE_CLIENT_SECRET = env("GOOGLE_CLIENT_SECRET")
if "${{" in GOOGLE_CLIENT_SECRET:
    GOOGLE_CLIENT_SECRET = ""
GOOGLE_ENABLED = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)
# Optional explicit public URL for the OAuth redirect; else derived per-request.
PUBLIC_BASE_URL = env("PUBLIC_BASE_URL").rstrip("/")

# ---- Ask Axle (the "ask anything" AI teacher) ---------------------------
# The API key lives ONLY on the server. The browser never sees it. Every
# answer is cached in the database, so a repeated question costs nothing and
# returns instantly. Without a key, the feature degrades gracefully: the
# page shows a friendly "not set up yet" message instead of breaking.
#
# The provider is switchable. Set ONE key and it just works:
#   Gemini (free tier, recommended):  GEMINI_API_KEY
#   Groq   (free tier, fast):         GROQ_API_KEY
#   Claude (paid):                    ANTHROPIC_API_KEY
# AI_PROVIDER can force a choice; otherwise it auto-detects from whichever
# key is present, preferring Gemini, then Groq, then Claude.
def _clean_key(name):
    v = env(name)
    return "" if "${{" in v else v

GEMINI_API_KEY = _clean_key("GEMINI_API_KEY")
GROQ_API_KEY = _clean_key("GROQ_API_KEY")
ANTHROPIC_API_KEY = _clean_key("ANTHROPIC_API_KEY")
OPENAI_API_KEY = _clean_key("OPENAI_API_KEY")

# Verified against /api/ai/selftest. Check any new model ID there before
# changing this: a wrong ID does not fail loudly — the provider fallback
# quietly serves every request from Groq instead, at Groq's cost.
# The rolling alias, not a pinned version. "gemini-2.5-flash-lite" was the
# default and it is closed to API keys created after it shipped — a new key
# gets 404 "model not found" for it on every single call. That does not fail
# loudly: the provider chain catches it, moves to the next key, and the user
# sees whatever the SECOND provider says. So a perfectly good Gemini key sat
# there doing nothing while OpenAI's out-of-credit message came back, and the
# obvious conclusion — "Gemini is added, why am I still seeing this" — was
# exactly right.
#
# The alias resolves to whatever the current flash-lite is, for any key.
# Check /api/ai/models before pinning a specific id here again.
GEMINI_MODEL = env("GEMINI_MODEL", "gemini-flash-lite-latest")
# Used only where the writing quality is the product: the apply kit's
# cover note and screening answers. Everything else stays on the cheap
# model, because scoring and classifying do not read any better on a
# stronger one. Check /api/ai/models for what this key can use.
GEMINI_MODEL_BEST = env("GEMINI_MODEL_BEST", GEMINI_MODEL)
GROQ_MODEL = env("GROQ_MODEL", "llama-3.3-70b-versatile")
ANTHROPIC_MODEL = env("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
OPENAI_MODEL = env("OPENAI_MODEL", "gpt-4o-mini")

# Adding a provider widens the fallback; it does not mean asking more than one
# of them anything. Every request still goes to exactly one model, and the
# others exist so that a rate limit or an outage at one is a slower answer
# rather than no answer. Fanning a question out to four providers to compare
# them would multiply the bill by four to produce one answer, and the bill is
# the constraint this whole product is designed around.
_KEYS = {"gemini": GEMINI_API_KEY, "groq": GROQ_API_KEY,
         "claude": ANTHROPIC_API_KEY, "openai": OPENAI_API_KEY}
_MODELS = {"gemini": GEMINI_MODEL, "groq": GROQ_MODEL,
           "claude": ANTHROPIC_MODEL, "openai": OPENAI_MODEL}
# Cheapest capable first: Gemini and Groq have free tiers, the other two bill
# from the first token.
_PREFERRED = ("gemini", "groq", "openai", "claude")

AI_PROVIDER = env("AI_PROVIDER").lower().strip()
if AI_PROVIDER == "anthropic":
    AI_PROVIDER = "claude"
if AI_PROVIDER not in _KEYS:
    AI_PROVIDER = next((p for p in _PREFERRED if _KEYS[p]), "none")

_PROVIDER_KEY = _KEYS.get(AI_PROVIDER, "")
_PROVIDER_MODEL = _MODELS.get(AI_PROVIDER, "")
ASK_ENABLED = bool(_PROVIDER_KEY)
print(f"Ask Axle: provider={AI_PROVIDER} enabled={ASK_ENABLED}"
      + (f" model={_PROVIDER_MODEL}" if ASK_ENABLED else ""))

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def now():
    return dt.datetime.now(dt.timezone.utc)


# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(120), nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    college = Column(String(160), default="")
    city = Column(String(120), default="")
    degree = Column(String(120), default="")
    path = Column(String(40), default="")
    created_at = Column(DateTime(timezone=True), default=now)
    last_seen = Column(DateTime(timezone=True), default=now)
    # Active sessions, newest first, as a comma-separated list capped at
    # MAX_DEVICES. Two devices is deliberate: a phone and a laptop is ordinary
    # use, while sharing an account around a group needs more than that.
    session_token = Column(String(400), default="")
    session_seen_at = Column(DateTime(timezone=True))
    # Billing. `plan` is the source of truth for what someone may use; it is
    # only ever changed by a verified webhook, never by the browser.
    plan = Column(String(20), default="free", index=True)   # free | basic | pro
    plan_provider = Column(String(20), default="")          # stripe
    # Recruiter discovery is opt-in and off by default. Existing users
    # agreed to a policy saying we do not share personal data, so being
    # findable has to be something they actively choose, never a default
    # flipped on beneath them.
    # Nullable on purpose: ADD COLUMN ... NOT NULL fails on a table that
    # already has rows, so existing users would silently miss the column.
    # Read it through open_to_work_on(), which treats NULL as off.
    open_to_work = Column(Boolean, default=False)
    # Date of birth. Nullable, and NULL is not an adult — the job side, a
    # subscription and being shown to an employer all need a proven age,
    # and "we never asked" is not proof. Read it through craxlearn.adult(),
    # never by comparing years here.
    dob = Column(Date)
    # How this account signs in. "" is an ordinary email/Google account and
    # gets the whole product. "classcode" is a learner who typed a class
    # code and nothing else: no email, no password, no way to reach the job
    # half of the site at any age, because there is no adult behind it who
    # agreed to anything.
    #
    # Nullable, and NULL means ordinary — every account that existed before
    # this column was an ordinary one.
    kind = Column(String(16), default="")
    # Employer access is applied for and approved, never self-granted. Anyone
    # who could tick a box at signup could see candidate profiles, and the
    # whole promise to candidates rests on who is on the other side.
    employer_status = Column(String(12), default="")     # "" | pending | approved
    employer_company = Column(String(200), default="")
    employer_site = Column(String(300), default="")
    open_to_work_at = Column(DateTime(timezone=True))
    plan_ref = Column(String(120), default="")              # subscription id
    plan_expires = Column(DateTime(timezone=True))
    plan_started = Column(DateTime(timezone=True))
    plan_cancelled_at = Column(DateTime(timezone=True))
    # Two-factor. Off by default: making it compulsory at signup costs more
    # accounts than it protects, at this size.
    totp_secret = Column(String(64), default="")
    totp_enabled = Column(Boolean, default=False, nullable=False)
    totp_backup = Column(Text, default="")     # hashed single-use codes
    email_verified = Column(Boolean, default=False, nullable=False)
    verified_at = Column(DateTime(timezone=True))


class Track(Base):
    __tablename__ = "tracks"
    id = Column(Integer, primary_key=True)
    slug = Column(String(60), unique=True, nullable=False, index=True)
    icon = Column(String(16), default="")
    name = Column(String(160), nullable=False)
    audience = Column(String(20), default="graduate")   # "school" | "graduate"
    level = Column(String(80), default="")
    color = Column(String(20), default="")
    weeks = Column(Integer, default=1)
    lang = Column(String(40), default="")
    desc = Column(Text, default="")
    outcomes = Column(Text, default="[]")   # JSON list
    quiz = Column(Text, default="[]")       # JSON list
    position = Column(Integer, default=0)
    published = Column(Boolean, default=True, nullable=False)
    lessons = relationship("Lesson", back_populates="track",
                           cascade="all, delete-orphan",
                           order_by="Lesson.position")


class Lesson(Base):
    __tablename__ = "lessons"
    id = Column(Integer, primary_key=True)
    slug = Column(String(60), unique=True, nullable=False, index=True)
    track_id = Column(Integer, ForeignKey("tracks.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(240), nullable=False)
    mins = Column(Integer, default=20)
    lang = Column(String(10), default="read")   # py | js | read
    content = Column(Text, default="")
    videos = Column(Text, default="[]")         # JSON list
    refs = Column(Text, default="[]")           # JSON list
    lab = Column(Text, default="{}")            # JSON object (graduate tracks)
    exercises = Column(Text, default="[]")      # JSON list   (school tracks)
    worksheet = Column(Text, default="[]")      # JSON list   (printable questions)
    position = Column(Integer, default=0)
    published = Column(Boolean, default=True, nullable=False)
    track = relationship("Track", back_populates="lessons")


class Progress(Base):
    __tablename__ = "progress"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    lesson_slug = Column(String(60), nullable=False, index=True)
    completed = Column(Boolean, default=False, nullable=False)
    attempts = Column(Integer, default=0)
    code = Column(Text, default="")             # the student's saved lab work
    completed_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=now, onupdate=now)
    __table_args__ = (UniqueConstraint("user_id", "lesson_slug", name="uq_user_lesson"),)


class QuizResult(Base):
    __tablename__ = "quiz_results"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    track_slug = Column(String(60), nullable=False, index=True)
    score = Column(Integer, default=0)
    total = Column(Integer, default=0)
    passed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=now)


class Note(Base):
    """Free-form key/value per user — project checklists, path choice, etc."""
    __tablename__ = "notes"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    k = Column(String(120), nullable=False)
    v = Column(Text, default="")
    __table_args__ = (UniqueConstraint("user_id", "k", name="uq_user_key"),)


class AskCache(Base):
    """One row per unique (subject, level, normalized question).

    The first time anyone asks, we call the model and store the lesson here.
    Everyone after that — including the same student asking again — is served
    from this table for free. This is what keeps the running cost tiny."""
    __tablename__ = "ask_cache"
    id = Column(Integer, primary_key=True)
    qkey = Column(String(500), unique=True, nullable=False, index=True)
    # Which pool this row belongs to: "public", or "school:<id>". It is
    # already the first field of qkey, so the uniqueness constraint does the
    # real separating; this column exists so a row can be found, counted and
    # deleted by institution without parsing a key. Nullable, and NULL reads
    # as public — every row written before this column existed was written
    # by somebody outside an institution, because institutions could not
    # reach this table separately until now.
    scope = Column(String(40), default="public", index=True)
    subject = Column(String(60), default="")
    level = Column(String(60), default="")
    question = Column(Text, default="")
    lesson = Column(Text, default="{}")     # JSON: {title, steps[], takeaway}
    hits = Column(Integer, default=0)       # how many times served from cache
    created_at = Column(DateTime(timezone=True), default=now)


class SkillUnlock(Base):
    """Something a learner actually finished, kept in the matcher's words.

    The tutor marks a skill as unlocked when the learner has done the thing
    — solved the problem, read the capture, got the query right — and this
    is where those land, so the resume builder and the job matcher can use
    them.

    Two columns rather than one, and that is the whole design. `label` is
    what the learner sees on their resume, in the words a person writes:
    "TCP three-way handshake". `tokens` is what the matcher can act on, in
    the only words it knows: `tcp`. A single column would have to be one or
    the other, and a table full of "Computer Networking Protocols" is a
    table that looks like progress and moves nobody one place up a match
    list.

    `tokens` may be blank, and often is. Plenty of real skills — balancing
    redox equations, reading a balance sheet — have no word on a technology
    job board, and an honest empty column is better than filing them under
    the nearest thing that does.
    """
    __tablename__ = "skill_unlocks"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    label = Column(String(60), default="", index=True)
    tokens = Column(String(120), default="")   # comma-joined, matcher words
    times = Column(Integer, default=1)         # how often it has come up
    created_at = Column(DateTime(timezone=True), default=now)
    last_at = Column(DateTime(timezone=True), default=now)


@event.listens_for(AskCache, "before_insert")
def _ask_cache_scope(mapper, connection, target):
    """Fill the scope column from the key, on every insert, without asking.

    Twelve places in this file write to this table and more will be added.
    Asking each of them to remember a scope is asking for the one that
    forgets — and the row it writes is not a bug that shows up as an error,
    it is a school's question sitting in a pool the public reads.

    So it is taken from the key, which is the field the uniqueness
    constraint already enforces and therefore the only field that can be
    trusted to say which pool a row is really in. There is nothing to
    remember and nothing to get wrong.
    """
    target.scope = _cl.scope_from_key(target.qkey)


class LearnRecord(Base):
    """What one learner searched or asked, kept where their institution is.

    This is the record a school is entitled to: what its students have been
    asking about, so it can see what a class is stuck on. It is also the most
    revealing thing here, which is why `scope` is on the row rather than
    derived at read time — a query that forgets to join through the class
    membership returns everybody's, and that is not a mistake worth leaving
    available.

    Written on every ask, board topic and spoken turn. Never read across a
    scope boundary, and never used to source an answer for anybody.
    """
    __tablename__ = "learn_records"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     index=True)
    scope = Column(String(40), default="public", index=True)
    school_id = Column(Integer, default=0, index=True)
    kind = Column(String(12), default="ask")     # craxlearn.RECORD_KINDS
    text = Column(String(220), default="")       # the question, trimmed
    subject = Column(String(60), default="")
    level = Column(String(60), default="")
    created_at = Column(DateTime(timezone=True), default=now, index=True)


class JobAlert(Base):
    """A background alert about someone's job search.

    Stored rather than computed, because the interesting events are things
    that happened while the user was away — a saved job closing, or a strong
    new match appearing overnight.
    """
    __tablename__ = "job_alerts"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    kind = Column(String(24), default="", index=True)   # closing | newmatch
    icon = Column(String(8), default="")
    text = Column(Text, default="")
    url = Column(Text, default="")
    seen = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=now, index=True)


class EmployerJob(Base):
    """A role an employer is hiring for. Separate from Job, which is a posting
    we crawled — these are written by the employer on Craxle itself."""
    __tablename__ = "employer_jobs"
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer, ForeignKey("users.id"), index=True)
    title = Column(String(200), default="")
    company = Column(String(200), default="")
    location = Column(String(200), default="")
    engagement = Column(String(20), default="")      # c2c / w2 / 1099 / ""
    jd = Column(Text, default="")
    is_open = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=now)
    updated_at = Column(DateTime(timezone=True), default=now, onupdate=now)


class JobInvite(Base):
    """An employer reaching out about one role, and the candidate's answer.

    The score is stored at send time on purpose: the candidate must see the
    same number the employer saw. Recomputing later, after either side edits
    something, would quietly change what was already communicated.
    """
    __tablename__ = "job_invites"
    id = Column(Integer, primary_key=True)
    employer_job_id = Column(Integer, ForeignKey("employer_jobs.id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    score = Column(Integer, default=0)
    state = Column(String(12), default="sent", index=True)   # sent/accepted/declined
    created_at = Column(DateTime(timezone=True), default=now, index=True)
    answered_at = Column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("employer_job_id", "user_id",
                                       name="uq_invite_once"),)


class InviteMessage(Base):
    """One message between an employer and a candidate about one invitation.

    Scoped to the invite, not to the two users: the conversation exists because
    a specific role was accepted, and it should not become a general channel
    to someone who agreed to talk about one job.
    """
    __tablename__ = "invite_messages"
    id = Column(Integer, primary_key=True)
    invite_id = Column(Integer, ForeignKey("job_invites.id"), index=True)
    from_employer = Column(Boolean, default=False)
    body = Column(Text, default="")
    # "text" or "resume". Nullable-safe default so the migration can add it to
    # a table that already has rows.
    kind = Column(String(12), default="text")
    seen = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=now, index=True)


class InviteFile(Base):
    """A file attached to an invite conversation.

    Bytes live in the row, base64, exactly as Assignment.pdf_data does. No
    filesystem: nothing to path-traverse into, nothing orphaned when a row is
    deleted, and it survives a container restart on Railway.
    """
    __tablename__ = "invite_files"
    id = Column(Integer, primary_key=True)
    invite_id = Column(Integer, ForeignKey("job_invites.id"), index=True)
    from_employer = Column(Boolean, default=False)
    filename = Column(String(200), default="")
    kind = Column(String(8), default="pdf")        # pdf | docx
    size = Column(Integer, default=0)
    data = Column(Text, default="")                # base64
    created_at = Column(DateTime(timezone=True), default=now, index=True)


class SysCounter(Base):
    """A system-wide counter, keyed by name. Notes cannot hold these — their
    user_id is NOT NULL — and a paid-API budget belongs to the deployment,
    not to any one person."""
    __tablename__ = "sys_counters"
    k = Column(String(60), primary_key=True)
    v = Column(Integer, default=0)


class JobTrack(Base):
    """A job a user saved or applied to, and where it got to.

    Kept separate from Job so that pruning old postings never destroys
    someone's application history — the title and company are copied in for
    exactly that reason, and the row survives the listing closing.
    """
    __tablename__ = "job_tracks"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    job_id = Column(Integer, index=True)          # not a FK: jobs get pruned
    status = Column(String(20), default="saved", index=True)
    title = Column(String(300), default="")
    company = Column(String(200), default="")
    location = Column(String(200), default="")
    url = Column(Text, default="")
    score = Column(Integer, default=0)
    note = Column(Text, default="")
    applied_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=now)
    updated_at = Column(DateTime(timezone=True), default=now, onupdate=now)


# The order a real application moves through, which the UI shows as tabs.
# "viewed" comes first because opening an employer's form is not applying —
# most people look and close the tab, and recording that as an application
# makes the tracker lie to them.
TRACK_STATUSES = ["viewed", "saved", "applied", "interviewing", "offer",
                  "rejected", "archived"]
TRACK_LABELS = {"viewed": "Recently viewed", "saved": "Saved",
                "applied": "Applied", "interviewing": "Interviewing",
                "offer": "Offer received", "rejected": "Rejected",
                "archived": "Archived"}


class Job(Base):
    """One live job posting, refreshed daily from public career-site APIs.

    A posting is identified by (source, external_id). Each refresh updates
    last_seen; a posting that stops appearing in its source feed is marked
    closed rather than deleted, so users can still see what recently went."""
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True)
    source = Column(String(40), nullable=False, index=True)
    external_id = Column(String(200), nullable=False)
    title = Column(String(300), default="")
    company = Column(String(200), default="", index=True)
    country = Column(String(80), default="", index=True)
    location = Column(String(200), default="")
    remote = Column(Boolean, default=False)
    category = Column(String(30), default="", index=True)   # role family
    job_type = Column(String(20), default="", index=True)   # fulltime/contract/…
    # Pay as the posting states it, verbatim-ish: "$120,000 - $150,000 a year",
    # "$65/hr". Nullable so the migration can add it to a populated table, and
    # blank whenever the ad does not say — a guessed salary is worse than none.
    salary = Column(String(120), default="")
    # Years of experience the posting demands, parsed at ingest. Stored
    # rather than read from the text at match time because the description
    # is deferred on that query — reading it there would lazy-load
    # thousands of rows one at a time. Nullable: existing rows fill on the
    # next crawl or from the backfill endpoint.
    min_years = Column(Integer, default=0)
    # The posting as the employer wrote it. Job.text is lowercased and
    # collapsed for matching, which is correct for an index and unreadable
    # for a human, so the readable copy is kept separately. Nullable: rows
    # crawled before this column existed fill on their next crawl.
    description = Column(Text, default="")
    engagement = Column(String(10), default="", index=True)  # w2 / c2c / 1099
    visa = Column(String(20), default="", index=True)        # sponsors/no/clearance
    url = Column(Text, default="")
    text = Column(Text, default="")          # lowercased title+desc, for search
    # Skills extracted once at ingest. Re-deriving these from `text` at match
    # time meant tokenising 5,000 full descriptions per request, which took
    # over 30 seconds; reading a short CSV column is instant.
    skills = Column(Text, default="")        # comma-joined skill tokens
    # Skills that appeared under Requirements / Qualifications / Responsibilities
    # rather than anywhere in the ad. A skill listed as a requirement means far
    # more than one mentioned in a benefits blurb, and scoring them the same is
    # why matches felt arbitrary.
    req_skills = Column(Text, default="")
    posted_at = Column(DateTime(timezone=True))
    first_seen = Column(DateTime(timezone=True), default=now, index=True)
    last_seen = Column(DateTime(timezone=True), default=now, index=True)
    is_open = Column(Boolean, default=True, index=True)
    closed_at = Column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_job_src"),)


# ---- School / classroom system (all NEW tables, existing ones untouched) --
class School(Base):
    """A school we (the platform admin) enrol. Everything below belongs to a
    school, so two different '6-A' classes never collide."""
    __tablename__ = "schools"
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    city = Column(String(120), default="")
    country = Column(String(120), default="")
    # What this institution bought. "craxlearn" is the teaching product on
    # its own: no job board, no resume builder, no subscription pages, for
    # anybody enrolled here whatever their age. A coaching centre teaching
    # working adults can set "both".
    #
    # Nullable, and NULL reads as craxlearn-only. A school enrolled before
    # this column existed gets the safer half of the product on the next
    # deploy rather than the job board, which is the right way round for a
    # default nobody has looked at yet.
    product = Column(String(16), default="craxlearn")   # craxlearn | both
    created_at = Column(DateTime(timezone=True), default=now)


class TeacherCode(Base):
    """A secret code we hand to a school. Signing up with it grants teacher
    rights. is_head=True codes create the school's head teacher."""
    __tablename__ = "teacher_codes"
    id = Column(Integer, primary_key=True)
    code = Column(String(40), unique=True, nullable=False, index=True)
    school = Column(String(160), default="")
    school_id = Column(Integer, default=0)
    is_head = Column(Boolean, default=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=now)


class TeacherAccess(Base):
    """Presence of a row = this user is a teacher. role is 'head' (runs the
    whole school) or 'teacher' (locked to their subject)."""
    __tablename__ = "teacher_access"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     unique=True, nullable=False, index=True)
    school = Column(String(160), default="")
    school_id = Column(Integer, default=0)
    role = Column(String(12), default="teacher")   # 'head' | 'teacher'
    created_at = Column(DateTime(timezone=True), default=now)


class Klass(Base):
    """A classroom (e.g. 6-A), created by a head teacher. ONE student code."""
    __tablename__ = "classes"
    id = Column(Integer, primary_key=True)
    name = Column(String(160), nullable=False)
    join_code = Column(String(16), unique=True, nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    school = Column(String(160), default="")
    school_id = Column(Integer, default=0)
    schedule = Column(Text, default="")     # legacy; schedule is now a list
    created_at = Column(DateTime(timezone=True), default=now)


class ClassMember(Base):
    __tablename__ = "class_members"
    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"),
                      nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    joined_at = Column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("class_id", "user_id", name="uq_class_user"),)


class ClassroomTeacher(Base):
    """Legacy co-teacher link (v1.11). Superseded by SubjectSlot below, kept
    so old rows and references remain valid."""
    __tablename__ = "classroom_teachers"
    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"),
                      nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    subject = Column(String(80), default="")
    created_at = Column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("class_id", "teacher_id", name="uq_class_teacher"),)


class SubjectSlot(Base):
    """A subject taught in a classroom. The head teacher creates one per
    subject with its own join code; a subject teacher claims it by entering
    that code, which locks them to this classroom + subject. A fresh table
    (no teacher foreign key) so an unclaimed slot can have teacher_id = 0."""
    __tablename__ = "subject_slots"
    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"),
                      nullable=False, index=True)
    subject = Column(String(80), nullable=False)
    code = Column(String(16), unique=True, nullable=False, index=True)
    teacher_id = Column(Integer, default=0, index=True)   # 0 = unclaimed
    status = Column(String(12), default="open")           # 'open' | 'claimed'
    created_at = Column(DateTime(timezone=True), default=now)


class Assignment(Base):
    __tablename__ = "assignments"
    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"),
                      nullable=False, index=True)
    teacher_id = Column(Integer, default=0)        # who set it (for chat routing)
    subject = Column(String(80), default="")       # e.g. Science, Maths
    title = Column(String(240), nullable=False)
    kind = Column(String(12), default="task")      # "task" | "lesson" (legacy)
    lesson_slug = Column(String(60), default="")   # legacy lesson link
    body = Column(Text, default="")                # the questions / instructions
    pdf_data = Column(Text, default="")            # base64 PDF of uploaded pages
    pdf_name = Column(String(160), default="")
    due_date = Column(String(20), default="")      # ISO date string, optional
    # The board topic this was set from, when it was set from the board.
    # Kept so a student who is stuck can have the same lesson taught to them
    # again instead of only being told to do it. Nullable: assignments typed
    # by hand have no topic and that is not a gap.
    board_topic = Column(String(200), default="")
    created_at = Column(DateTime(timezone=True), default=now)


class Submission(Base):
    """A student's typed answer. Its existence = the assignment is done for
    that student. They can update it any time."""
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    response = Column(Text, default="")
    # What the teacher said back, and when. Separate from the chat thread on
    # purpose: a thread is a conversation and this is the verdict, and a
    # student scrolling a conversation to find out whether their work was
    # accepted has been given the wrong shape.
    #
    # reviewed_at is what "waiting for me" is computed from, so it is the
    # one that must be set even when there is nothing to say. All nullable:
    # every submission that existed before this column did is unreviewed,
    # which is exactly what NULL should mean here.
    feedback = Column(Text, default="")
    reviewed_at = Column(DateTime(timezone=True))
    reviewed_by = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=now)
    updated_at = Column(DateTime(timezone=True), default=now, onupdate=now)
    __table_args__ = (UniqueConstraint("assignment_id", "user_id", name="uq_sub_user"),)


class RosterName(Base):
    """One name on a class register, typed by the teacher before the lesson.

    This is what makes a code-only login work. A learner types the class
    code and picks their own name off the list — no email, no password,
    nothing to remember and nothing to lose. The teacher already knows who
    is in the room, so asking them once is cheaper than asking thirty
    children to invent credentials.

    `claimed_by` is what stops two people being the same pupil. Once a name
    is taken it disappears from the list, and the account behind it is the
    only one that name will ever sign in as.
    """
    __tablename__ = "roster_names"
    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"),
                      nullable=False, index=True)
    name = Column(String(80), nullable=False)
    # The school's own identifier for this child, typed by the teacher next
    # to the name. Optional: a class of thirty first-names is fine without
    # one, and a school with two Asha Raos is not. It is what a teacher
    # types to look somebody up, because it is what is already written on
    # everything else in the building.
    student_code = Column(String(40), default="", index=True)
    claimed_by = Column(Integer, default=0, index=True)   # User.id, 0 = free
    claimed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=now)


class SchoolNotice(Base):
    """Something the school office wants everybody to know.

    Fee deadlines, closures, exam timetables, the things a paper letter used
    to carry home in a bag. Written by the office, read by every learner in
    the school — not per class, because a school closure is not a class
    matter and making the office post it thirty times is how it gets posted
    twice and missed everywhere else.
    """
    __tablename__ = "school_notices"
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, default=0, index=True)
    author_id = Column(Integer, default=0)
    title = Column(String(240), nullable=False)
    body = Column(Text, default="")
    # Shown first and in a different colour. For a closure or a deadline,
    # not for the newsletter — a page where everything is urgent has no
    # urgent on it.
    urgent = Column(Boolean, default=False)
    starts_on = Column(String(20), default="")     # ISO date, optional
    ends_on = Column(String(20), default="")       # ISO date, optional
    created_at = Column(DateTime(timezone=True), default=now, index=True)


class Attendance(Base):
    """One learner, one day, present or not.

    A row per day rather than a running percentage, because a percentage
    cannot be corrected. "Marked absent on the 14th, and it was wrong" is
    the single most common thing a parent rings about, and a stored total
    has nothing to correct.

    The percentage the student sees is computed from these rows every time.
    """
    __tablename__ = "attendance"
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, default=0, index=True)
    class_id = Column(Integer, default=0, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    day = Column(String(20), nullable=False, index=True)   # ISO date
    present = Column(Boolean, default=True)
    note = Column(String(200), default="")     # "late", "medical", …
    marked_by = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("user_id", "day", name="uq_att_day"),)


class FeeItem(Base):
    """Something a learner owes, or has paid.

    Amounts are integers in the smallest unit — paise — for the same reason
    the plan prices are: a fee balance that is out by a rounding error is a
    fee balance somebody has to reconcile by hand.

    Nothing here takes a payment. It records what the office already knows,
    so a learner can see their balance without ringing up. The office marks
    it paid when the money arrives, wherever it arrived.
    """
    __tablename__ = "fee_items"
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, default=0, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    title = Column(String(240), nullable=False)     # "Term 2 tuition"
    note = Column(Text, default="")
    amount = Column(Integer, default=0)             # paise, what is owed
    paid = Column(Integer, default=0)               # paise, what has arrived
    currency = Column(String(8), default="INR")
    due_on = Column(String(20), default="")         # ISO date, optional
    # Something the learner has to buy rather than pay the school for — a
    # workbook, a lab coat. Same row, because "what do I still have to sort
    # out" is one question and answering it from two lists is how one half
    # gets forgotten.
    kind = Column(String(12), default="fee")        # fee | buy
    marked_by = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=now, index=True)
    paid_at = Column(DateTime(timezone=True))


class Material(Base):
    """Reference material a teacher puts in front of one class.

    A link, or a file the teacher uploaded. Files are stored base64 in the
    row, the same way an assignment's page scans already are — one fewer
    moving part than object storage, and the sizes involved are a slide deck
    rather than a video.

    Deliberately not attached to an assignment. Material outlives the piece
    of work it was first needed for: the textbook chapter is still the
    textbook chapter next term, and filing it under one homework is how it
    becomes unfindable.
    """
    __tablename__ = "materials"
    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"),
                      nullable=False, index=True)
    teacher_id = Column(Integer, default=0)
    subject = Column(String(80), default="")
    title = Column(String(240), nullable=False)
    note = Column(Text, default="")           # why they should read it
    url = Column(Text, default="")            # a link, when it is a link
    file_data = Column(Text, default="")      # base64, when it is a file
    file_name = Column(String(160), default="")
    mime = Column(String(80), default="")
    size = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=now, index=True)


class AssignmentMessage(Base):
    """Chat thread per (assignment, student). Only that student and the
    teacher who set the assignment take part."""
    __tablename__ = "assignment_messages"
    id = Column(Integer, primary_key=True)
    assignment_id = Column(Integer, ForeignKey("assignments.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    student_id = Column(Integer, nullable=False, index=True)
    sender_id = Column(Integer, nullable=False)
    from_teacher = Column(Boolean, default=False)
    body = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), default=now)


class TeacherRequest(Base):
    """A subject teacher asking the head teacher for something (a new subject,
    a change). Subject teachers cannot create classes/subjects themselves."""
    __tablename__ = "teacher_requests"
    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, default=0, index=True)
    class_id = Column(Integer, default=0)
    teacher_id = Column(Integer, nullable=False)
    message = Column(Text, default="")
    status = Column(String(12), default="open")   # 'open' | 'done'
    created_at = Column(DateTime(timezone=True), default=now)


class ScheduleItem(Base):
    """One row of a class timetable. Editable and deletable."""
    __tablename__ = "schedule_items"
    id = Column(Integer, primary_key=True)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"),
                      nullable=False, index=True)
    day = Column(String(40), default="")
    text = Column(Text, default="")
    position = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=now)


# --------------------------------------------------------------------------
# Auth helpers
# --------------------------------------------------------------------------
def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_pw(pw: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), h.encode())
    except Exception:
        return False


class PasswordReset(Base):
    """A single-use password reset link.

    Only the hash of the token is stored, so a leaked database still cannot
    be used to reset anyone's password.
    """
    __tablename__ = "password_resets"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    token_hash = Column(String(64), unique=True, index=True)
    expires_at = Column(DateTime(timezone=True))
    used_at = Column(DateTime(timezone=True))
    purpose = Column(String(20), default="reset", index=True)   # reset | verify
    created_at = Column(DateTime(timezone=True), default=now)


RESET_TTL = dt.timedelta(hours=1)
VERIFY_TTL = dt.timedelta(days=3)
# Off until email delivery is proven working. Turning this on before
# then locks out every genuine signup, which is worse than the problem
# it solves.
# Whether signup ASKS for confirmation. It deliberately no longer gates paid
# features: a customer who has paid must never be told to check an inbox for
# mail that may not arrive. Verification is a nudge, not a lock.
REQUIRE_EMAIL_VERIFICATION = env("REQUIRE_EMAIL_VERIFICATION", "0") == "1"

# ---- email ---------------------------------------------------------------
# Resend is the preferred sender: it is an HTTPS call on port 443, which no
# host blocks. SMTP stays as a fallback but is a trap on most PaaS providers —
# outbound 587 is blocked, and a blocked port hangs rather than refusing,
# which took this site down once already.
RESEND_API_KEY = env("RESEND_API_KEY")
SMTP_HOST = env("SMTP_HOST")
SMTP_PORT = int(env("SMTP_PORT", "587") or 587)
SMTP_USER = env("SMTP_USER")
SMTP_PASS = env("SMTP_PASS")
# resend.dev only delivers to the address that owns the Resend account. Once
# craxle.com is verified in Resend, set MAIL_FROM to something like
# "Craxle <noreply@craxle.com>" to reach real users.
MAIL_FROM = env("MAIL_FROM") or SMTP_USER or "Craxle <onboarding@resend.dev>"
MAIL_PROVIDER = "resend" if RESEND_API_KEY else ("smtp" if (SMTP_HOST and SMTP_USER and SMTP_PASS) else "")
MAIL_ENABLED = bool(MAIL_PROVIDER)

# Resend can only send from a domain you have verified, so a leftover Gmail
# address in MAIL_FROM rejects every message with a 403. Fall back to their
# shared sender rather than silently failing — it reaches the account owner,
# which is enough to prove the setup works.
_FREE_MAIL = ("gmail.com", "yahoo.com", "outlook.com", "hotmail.com",
              "live.com", "icloud.com", "protonmail.com", "rediffmail.com")
MAIL_FROM_OVERRIDDEN = ""
if MAIL_PROVIDER == "resend" and any(d in MAIL_FROM.lower() for d in _FREE_MAIL):
    MAIL_FROM_OVERRIDDEN = MAIL_FROM
    MAIL_FROM = "Craxle <onboarding@resend.dev>"
    print(f"MAIL_FROM {MAIL_FROM_OVERRIDDEN!r} cannot be used with Resend — "
          f"you can only send from a domain you have verified. Using "
          f"{MAIL_FROM} instead, which only delivers to the address that owns "
          f"the Resend account. Verify craxle.com at resend.com/domains and "
          f"set MAIL_FROM to an address on it.")


# Background email failures are invisible by design — we must not reveal
# through a delay or an error whether an address is registered. That makes
# them impossible to debug, so the last one is kept here for the admin.
LAST_MAIL = {"ok": None, "to": "", "at": None, "error": ""}


def send_email(to: str, subject: str, body: str):
    """Send one plain-text email. Never raises into the request.

    Called from a background task: a slow or broken mail server must not make
    the user wait, and must not reveal — through a timeout — whether an
    account exists.
    """
    LAST_MAIL.update({"to": to, "at": now().isoformat(), "ok": None,
                      "error": "", "via": MAIL_PROVIDER})
    if not MAIL_ENABLED:
        LAST_MAIL.update({"ok": False, "error": "No mail provider configured"})
        print(f"MAIL DISABLED — would have sent to {to}: {subject}")
        return

    if MAIL_PROVIDER == "resend":
        try:
            r = httpx.post("https://api.resend.com/emails", timeout=15,
                           headers={"Authorization": f"Bearer {RESEND_API_KEY}",
                                    "Content-Type": "application/json"},
                           json={"from": MAIL_FROM, "to": [to],
                                 "subject": subject, "text": body})
            if r.status_code < 300:
                LAST_MAIL.update({"ok": True, "id": r.json().get("id", "")})
            else:
                LAST_MAIL.update({"ok": False,
                                  "error": f"HTTP {r.status_code}: {r.text[:300]}"})
                print(f"Resend to {to} failed: {r.status_code} {r.text[:200]}")
        except Exception as e:
            LAST_MAIL.update({"ok": False, "error": f"{type(e).__name__}: {e}"[:300]})
            print(f"Resend to {to} failed: {type(e).__name__}: {e}")
        return

    import smtplib
    from email.message import EmailMessage
    msg = EmailMessage()
    msg["From"] = MAIL_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        # Short timeout on purpose. A blocked outbound SMTP port hangs instead
        # of refusing, and these run in the request threadpool — long hangs
        # exhaust it and take the whole site down with a gateway timeout.
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=8) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        LAST_MAIL.update({"ok": True})
    except Exception as e:
        LAST_MAIL.update({"ok": False, "error": f"{type(e).__name__}: {e}"[:400]})
        print(f"Email to {to} failed: {type(e).__name__}: {e}")


# One login per account, and signing in anywhere else ends the first one.
#
# Was two — a phone and a laptop is ordinary use — but a class account is not
# an ordinary account. Thirty children with one code between them is exactly
# the sharing the limit exists to stop, and two devices makes it twice as
# easy. One means the second person to sign in takes the account and the
# first is told plainly why they were dropped, which is the behaviour a
# teacher can explain in a sentence.
MAX_DEVICES = int(env("MAX_DEVICES", "1") or 1)


def _sessions(user) -> list:
    return [s for s in (user.session_token or "").split(",") if s]


def make_token(user: User, db: Session = None) -> str:
    """Mint a session token and remember it as one of this user's devices.

    Signing in on a third device pushes out the oldest, so an account can be
    used from a phone and a laptop but not passed around a group.
    """
    fresh = secrets.token_urlsafe(18)
    if db is not None:
        keep = ([fresh] + _sessions(user))[:MAX_DEVICES]
        user.session_token = ",".join(keep)
        user.session_seen_at = now()
        db.commit()
    payload = {
        "sub": str(user.id),
        "adm": user.is_admin,
        "st": fresh if db is not None else (_sessions(user)[:1] or [""])[0],
        "exp": now() + dt.timedelta(days=SESSION_DAYS),
        "iat": now(),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("vp_session")
    if not token:
        raise HTTPException(401, "Not signed in")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "Session expired — please sign in again")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(401, "Account not available")
    # One login per account, to stop one subscription covering several people.
    # Admins are exempt: running the site means being signed in on several
    # browsers at once, and locking yourself out of your own admin panel is a
    # cost with no benefit. Accounts created before this existed have no
    # stored token, so they keep working until their next sign-in.
    if (user.session_token and not user.is_admin
            and payload.get("st") not in _sessions(user)):
        raise HTTPException(
            401, ("Signed out because this account was used to sign in "
                  "somewhere else. One device at a time — sign in again "
                  "here to use this one."
                  if MAX_DEVICES == 1 else
                  f"Signed out because this account is in use on more than "
                  f"{MAX_DEVICES} devices. Craxle allows {MAX_DEVICES} at a "
                  f"time — sign in again here to use this one."))
    # touch last_seen at most once a minute
    try:
        last = user.last_seen
        if last is not None and last.tzinfo is None:
            last = last.replace(tzinfo=dt.timezone.utc)
        if last is None or (now() - last).total_seconds() > 60:
            user.last_seen = now()
            db.commit()
    except Exception:
        pass
    return user


def admin_user(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(403, "Admin access required")
    return user


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------
class SignupIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    college: str = ""
    city: str = ""
    degree: str = ""
    school_code: str = ""   # optional; a valid one grants teacher rights


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ProgressIn(BaseModel):
    lesson: str
    completed: Optional[bool] = None
    code: Optional[str] = None
    attempt: bool = False


class QuizIn(BaseModel):
    track: str
    score: int
    total: int


class NoteIn(BaseModel):
    key: str
    value: str


class TrackIn(BaseModel):
    icon: str = ""
    name: str
    level: str = ""
    color: str = ""
    weeks: int = 1
    lang: str = ""
    desc: str = ""
    outcomes: List[str] = []
    quiz: list = []
    published: bool = True
    position: int = 0


class LessonIn(BaseModel):
    title: str
    mins: int = 20
    lang: str = "read"
    content: str = ""
    videos: list = []
    refs: list = []
    lab: dict = {}
    exercises: list = []
    worksheet: list = []
    published: bool = True
    position: int = 0
    track: Optional[str] = None


# --------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------
app = FastAPI(title="Craxle", docs_url="/api/docs", redoc_url=None)

# --------------------------------------------------------------------------
# Craxlearn: the teaching product, on its own
# --------------------------------------------------------------------------
# Set CRAXLEARN_ONLY on a server an institution runs for itself and the job
# half of this product does not exist on it — not hidden, not gated, not
# reachable, for anybody including an admin. That is the difference between
# a school running a learning tool and a school running a job board with the
# job board switched off, and it is the difference an IT department asks
# about.
import craxlearn as _cl_boot                                        # noqa: E402

CRAXLEARN_ONLY = env("CRAXLEARN_ONLY", "0").strip().lower() in (
    "1", "true", "yes", "on")

# Demand a stated date of birth from everybody, not only from institution
# learners. Off by default: switching it on locks out every existing account
# until each one comes back and fills in a date, which is a decision with a
# support queue attached rather than a default.
REQUIRE_DOB = env("REQUIRE_DOB", "0").strip().lower() in (
    "1", "true", "yes", "on")
if CRAXLEARN_ONLY:
    print(f"  {_cl_boot.NAME} only — the job board is not served here")


def _learning_only(db, user):
    """Whether the job half is closed to this person, and why.

    Three reasons, checked hardest first, because the message matters as
    much as the verdict — "your school did not buy this" and "you are not
    old enough" want completely different things from whoever reads them.

    An institution can open the job side for its learners. It cannot open
    it for a learner who is under age: the two conditions are ANDed and the
    age one is never the institution's to waive.
    """
    if CRAXLEARN_ONLY:
        return {"only": True, "why": "deployment",
                "message": f"This is a {_cl_boot.NAME} server. The job "
                           f"board is not part of it."}
    if user is None:
        return {"only": False, "why": "", "message": ""}

    # A class-code account is closed to the job half permanently, before
    # anything else is considered. There is no adult behind it who agreed to
    # anything, no email to reach them at, and no date of birth that could
    # ever open it — so this is checked before the school's own setting,
    # which cannot override it either.
    if (getattr(user, "kind", "") or "") == "classcode":
        return {"only": True, "why": "classcode",
                "message": f"This is a class login. {_cl_boot.NAME} is the "
                           f"whole of it — there is no job board, and "
                           f"nothing here to buy."}

    scope = _scope_of(db, user)
    if _cl_boot.is_institution(scope):
        sid = _cl_boot.school_id_of(scope)
        sc = db.get(School, sid) if sid else None
        if (getattr(sc, "product", None) or "craxlearn") != "both":
            return {"only": True, "why": "institution",
                    "message": f"Your institution uses {_cl_boot.NAME}, "
                               f"the learning half of Craxle. The job board "
                               f"is not part of it."}

    # Admins run the site and need every surface to debug it. They are still
    # subject to the deployment switch above, which is the one an institution
    # is relying on.
    if user.is_admin:
        return {"only": False, "why": "", "message": ""}

    # Proof is demanded where children are: inside an institution, always.
    # Outside one, a stated age is believed in both directions and silence
    # keeps what it had — see craxlearn.age_ok for why that is not a hole
    # left open out of laziness.
    proof = _cl_boot.is_institution(scope) or REQUIRE_DOB
    if not _cl_boot.age_ok(getattr(user, "dob", None), dt.date.today(), proof):
        return {"only": True, "why": "age",
                "message": f"The job board, subscriptions and being seen by "
                           f"employers are for learners aged "
                           f"{_cl_boot.MIN_JOB_AGE} and over. Add your date "
                           f"of birth in your profile to open them."}
    return {"only": False, "why": "", "message": ""}


@app.middleware("http")
async def _craxlearn_gate(request, call_next):
    """Close the job half at the door, on one list, for every route.

    A dependency on each job-side endpoint would be the same check written
    fifty times, and the fifty-first — added next month by somebody who did
    not know — would be open. Here there is one list, it is matched by path
    prefix, and tests/test_craxlearn_only.py walks the live route table and
    fails if a route appears that belongs to neither half.

    Nothing here authenticates. It reads the session only to find out who is
    asking; an invalid or missing one falls through to the endpoint's own
    `Depends(current_user)`, which is still the only thing that decides
    whether somebody is signed in.
    """
    if not _cl_boot.is_job_side(request.url.path):
        return await call_next(request)

    if CRAXLEARN_ONLY:
        return JSONResponse(status_code=404, content={
            "detail": f"This is a {_cl_boot.NAME} server. The job board is "
                      f"not part of it."})

    user, db = None, None
    try:
        token = request.cookies.get("vp_session")
        if token:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            db = SessionLocal()
            user = db.get(User, int(payload["sub"]))
        if user is not None:
            verdict = _learning_only(db, user)
            if verdict["only"]:
                return JSONResponse(status_code=403, content={
                    "detail": verdict["message"], "craxlearn": verdict["why"]})
    except Exception:
        # A bad cookie, an expired token, a database blip. None of them are
        # this function's business — it decides what a known user may reach,
        # and an unknown user is the endpoint's problem, as it always was.
        pass
    finally:
        if db is not None:
            db.close()
    return await call_next(request)


# Tracks replaced by a rewritten version — skipped so nothing appears twice
SUPERSEDED_TRACKS = {"sql", "data", "ml", "llm", "basics", "python"}


def _seed_file(db, filename, audience, position_offset):
    """Load one curriculum file into the database. Returns tracks added."""
    path = BASE_DIR / filename
    if not path.exists():
        print(f"NOTE: {filename} not found, skipping.")
        return 0
    data = json.loads(path.read_text(encoding="utf-8"))
    tracks = [t for t in data["tracks"] if t["id"] not in SUPERSEDED_TRACKS]
    added = 0
    for t in tracks:
        # idempotent: skip a track that is already in the database, so new
        # curriculum files load automatically on deploy without duplicating.
        if db.query(Track).filter(Track.slug == t["id"]).first():
            continue
        added += 1
        track = Track(
            slug=t["id"], icon=t.get("icon", ""), name=t["name"],
            audience=t.get("audience", audience),
            level=t.get("level", ""), color=t.get("color", ""),
            weeks=t.get("weeks", 1), lang=t.get("lang", ""),
            desc=t.get("desc", ""),
            outcomes=json.dumps(t.get("outcomes", [])),
            quiz=json.dumps(t.get("quiz", [])),
            position=position_offset + t.get("position", 0),
        )
        db.add(track)
        db.flush()
        for l in t["lessons"]:
            db.add(Lesson(
                slug=l["id"], track_id=track.id, title=l["title"],
                mins=l.get("mins", 20), lang=l.get("lang", "read"),
                content=l.get("content", ""),
                videos=json.dumps(l.get("videos", [])),
                refs=json.dumps(l.get("refs", [])),
                lab=json.dumps(l.get("lab", {})),
                exercises=json.dumps(l.get("exercises", [])),
                worksheet=json.dumps(l.get("worksheet", [])),
                position=l.get("position", 0),
            ))
    return added


def _count_users():
    db = SessionLocal()
    try:
        return db.query(func.count(User.id)).scalar() or 0
    finally:
        db.close()


def _schema_matches():
    """True if the live tables match the current models. A Postgres database
    left over from an older version can have tables missing newer columns
    (e.g. tracks.audience); create_all() will NOT add them, so we must detect
    the drift and rebuild."""
    db = SessionLocal()
    try:
        db.query(Track).limit(1).all()
        db.query(Lesson).limit(1).all()
        return True
    except Exception as e:
        print(f"Schema drift detected: {type(e).__name__}: {e}")
        return False
    finally:
        db.close()


def _migrate_columns():
    """Add any model columns that are missing from existing tables, without
    touching data. Safe on both SQLite and Postgres for simple ADD COLUMN.
    This is how we evolve the schema without dropping anyone's work."""
    from sqlalchemy import inspect as _inspect, text as _text
    insp = _inspect(engine)
    for table in Base.metadata.sorted_tables:
        if not insp.has_table(table.name):
            continue
        have = {c["name"] for c in insp.get_columns(table.name)}
        for col in table.columns:
            if col.name in have:
                continue
            try:
                coltype = col.type.compile(dialect=engine.dialect)
                with engine.begin() as conn:
                    # ADD COLUMN needs an exclusive lock, and during a deploy
                    # the OLD instance is still crawling and writing to jobs.
                    # Without a timeout the statement queues behind it for as
                    # long as that takes, holding up everything after it. Fail
                    # in five seconds instead and let the next boot do it —
                    # a column that arrives one restart later is nothing, a
                    # deploy that never becomes healthy is everything.
                    if engine.dialect.name == "postgresql":
                        conn.execute(_text("SET LOCAL lock_timeout = '5s'"))
                    conn.execute(_text(
                        f'ALTER TABLE {table.name} ADD COLUMN {col.name} {coltype}'))
                print(f"migrated: added column {table.name}.{col.name}")
            except Exception as e:
                print(f"migrate note ({table.name}.{col.name}): {e}")


# Local SQLite only, and deliberately so.
#
# Test files and admin scripts import this module and query the database
# directly, without going through startup, so they hit tables missing the
# newest column and die on "no such column". Running the migration at import
# fixes that — but on Postgres it means a connection and a round trip per
# table BEFORE the process can serve anything, and if the database is slow or
# not yet reachable during a deploy the worker never finishes importing and
# the health check fails. It did.
#
# In production the migration still runs, from seed_if_empty() at startup,
# where it is allowed to take its time.
if engine.dialect.name == "sqlite":
    try:
        _migrate_columns()
    except Exception as _e:                               # pragma: no cover
        print(f"migrate at import skipped: {type(_e).__name__}: {_e}")


def seed_if_empty():
    """Create tables, load curriculum on first boot, ensure admin exists."""
    Base.metadata.create_all(engine)
    _migrate_columns()   # non-destructive column additions

    # Heal an out-of-date schema from an early, pre-launch database. This ONLY
    # runs when there are no real user accounts yet — once people have signed
    # up, we never drop tables automatically (that would destroy their data).
    if not _schema_matches():
        real_users = 0
        try:
            real_users = _count_users()
        except Exception:
            real_users = 0
        if real_users == 0:
            print("Schema drift on an empty database — rebuilding tables...")
            Base.metadata.drop_all(engine)
            Base.metadata.create_all(engine)
            print("Tables rebuilt.")
        else:
            print(f"WARNING: schema drift detected but {real_users} accounts "
                  "exist — NOT dropping data. A manual migration is needed.")

    db = SessionLocal()
    try:
        existing = db.query(Track).count()
        files = sorted(p.name for p in BASE_DIR.glob("*.json") if p.name != "railway.json")
        print(f"Startup: {existing} tracks in database | curriculum files found: {files}")

        # Always run: _seed_file skips tracks already present, so this both
        # seeds an empty database AND auto-adds any NEW curriculum file on a
        # later deploy — without a manual "reload curriculum" and without
        # touching existing tracks or student progress.
        counts = [
            _seed_file(db, "school.json",     "school",   0),    # Stage 1
            _seed_file(db, "stage2.json",     "stage2",   50),   # Stage 2
            _seed_file(db, "stage3a.json",    "stage3a",  80),   # Stage 3
            _seed_file(db, "stage3b.json",    "stage3b",  90),   # Stage 4
            _seed_file(db, "stage4.json",     "stage4",   95),   # Stage 5
            _seed_file(db, "curriculum.json", "graduate", 120),  # Stage 6
            _seed_file(db, "placement.json",  "graduate", 150),  # DSA + aptitude
            _seed_file(db, "gamedev.json",    "graduate", 160),  # Game development
            _seed_file(db, "cybersec.json",   "graduate", 170),  # Cybersecurity
        ]
        db.commit()
        added = sum(counts)
        if added:
            print(f"Seeded/added {added} new tracks: {counts}")
        else:
            print("Curriculum already up to date — no new tracks to add.")

        # ---- Admin bootstrap -------------------------------------------
        if ADMIN_EMAIL:
            admin = db.query(User).filter(
                func.lower(User.email) == ADMIN_EMAIL).first()

            if admin:
                changed = []
                if not admin.is_admin:
                    admin.is_admin = True
                    changed.append("promoted to admin")
                if not admin.is_active:
                    admin.is_active = True
                    changed.append("reactivated")
                # Setting ADMIN_PASSWORD always resets the admin's password.
                # This is the documented way back in after a lockout.
                if ADMIN_PASSWORD:
                    admin.password_hash = hash_pw(ADMIN_PASSWORD)
                    changed.append("password reset from ADMIN_PASSWORD")
                if changed:
                    db.commit()
                print(f"Admin account {ADMIN_EMAIL}: {', '.join(changed) or 'already correct'}")

            elif ADMIN_PASSWORD:
                db.add(User(email=ADMIN_EMAIL, name="Administrator",
                            password_hash=hash_pw(ADMIN_PASSWORD), is_admin=True))
                db.commit()
                print(f"Created admin account: {ADMIN_EMAIL}")
            else:
                print(f"ADMIN_EMAIL set to {ADMIN_EMAIL} but no account exists "
                      f"and ADMIN_PASSWORD is not set — cannot create one.")
        else:
            print("No ADMIN_EMAIL variable set — nobody will be an administrator.")
    finally:
        db.close()


STARTUP_ERROR = None


@app.on_event("startup")
async def _startup():
    """Boot the app. Database work must NOT hold up serving.

    This used to be a sync handler, which blocks the event loop: nothing —
    including /api/health — could be answered until the database work
    finished. That is fine until an ALTER TABLE waits on a lock the previous
    instance's crawler is holding, at which point the new container never
    answers a health check and the deploy is rolled back with the app itself
    working perfectly. It happened, twice.

    So: print, return, and let the database catch up in a thread. /api/status
    reports whether it worked, which is where you can actually read it.
    """
    print("=" * 56)
    print(f"  Craxle  v{VERSION}  (commit {GIT_SHA})")
    print(f"  started {BUILT_AT}")
    print("=" * 56)
    import asyncio
    asyncio.create_task(asyncio.to_thread(_seed_with_retries))



def _backfill_job_skills():
    """Parse every posting whose skills have never been derived.

    A match request used to derive these from the description and keep the
    answer only for the length of that request, so the work was repeated on
    every match forever — the difference between a cold match at 8.3 seconds
    and one at 2.5.

    Rows with no recognisable skills are stored as "none" rather than left
    empty, because empty means "not looked at yet": leaving them would have
    them re-parsed on every pass, which is the fault being fixed.
    """
    try:
        db = SessionLocal()
    except Exception:
        return
    try:
        rows = db.query(Job).filter(
            (Job.skills == "") | (Job.skills.is_(None))).limit(20000).all()
        if not rows:
            return
        import time as _t
        t0 = _t.monotonic()
        for j in rows:
            found = {w for w in _words(j.text or "") if w in _SKILLS}
            j.skills = ",".join(sorted(found))[:2000] if found else "none"
        db.commit()
        print(f"Startup: parsed skills for {len(rows)} postings in "
              f"{_t.monotonic() - t0:.1f}s — matching no longer reparses them")
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        print(f"Startup: skill backfill skipped ({type(e).__name__}) — "
              f"matching still works, just slower on the first call")
    finally:
        try:
            db.close()
        except Exception:
            pass

def _seed_with_retries():
    """Postgres often is not accepting connections the instant we boot."""
    global STARTUP_ERROR
    import time
    for attempt in range(1, 6):
        try:
            seed_if_empty()
            STARTUP_ERROR = None
            print("database ready")
            _backfill_job_skills()


            return
        except Exception as e:
            STARTUP_ERROR = f"{type(e).__name__}: {e}"
            wait = attempt * 2
            print(f"Startup attempt {attempt}/5 failed: {STARTUP_ERROR}")
            if attempt < 5:
                print(f"  retrying in {wait}s...")
                time.sleep(wait)
    print("WARNING: database setup did not succeed. The app is running so "
          "you can reach /api/status, but content will be unavailable.")


JOBS_ENABLED = env("JOBS_ENABLED", "1") not in ("0", "false", "no")


@app.on_event("startup")
async def _start_jobs():
    """Kick off the daily job crawl in the background.

    Its own handler, and fire-and-forget: a slow or failing career-site API
    must never hold up boot and fail the deploy healthcheck."""
    if not JOBS_ENABLED:
        print("Job board refresh disabled (JOBS_ENABLED=0)")
        return
    import asyncio
    asyncio.create_task(_jobs_loop())


@app.get("/api/health")
def health():
    """Deliberately touches nothing — no database, no files.

    A healthcheck that depends on the database turns a slow database into
    a failed deployment.
    """
    return {"status": "ok", "version": VERSION, "commit": GIT_SHA,
            "time": now().isoformat()}


@app.get("/api/version")
def version():
    """Tiny endpoint for checking what is deployed, without the full status."""
    return {"version": VERSION, "commit": GIT_SHA, "started": BUILT_AT}


@app.get("/api/status")
def status(request: Request, db: Session = Depends(get_db)):
    """Public diagnostic — what is actually configured and loaded right now.

    Deliberately shows no passwords and no full email addresses.
    Survives a broken database so it can report *why* things are broken.
    """
    base = {
        "version": VERSION,
        "commit": GIT_SHA,
        "started": BUILT_AT,
        "startup_error": STARTUP_ERROR,
        "database": "postgres" if DATABASE_URL.startswith("postgres") else "sqlite",
        "admin_email_variable_set": bool(ADMIN_EMAIL),
        "jwt_secret_set": JWT_SECRET != "dev-only-insecure-secret-change-me",
        "ask_vidya_enabled": ASK_ENABLED,
        "ask_vidya_provider": AI_PROVIDER,
        "google_signin_enabled": GOOGLE_ENABLED,
        # Whether password reset can actually deliver. Shows configuration
        # only — never the credentials themselves.
        "mail_enabled": MAIL_ENABLED,
        "mail_provider": MAIL_PROVIDER or "(none)",
        "mail_host": SMTP_HOST or "(unset)",
        "mail_from": MAIL_FROM or "(unset)",
        # The exact string Google must have registered. A redirect_uri_mismatch
        # is almost always this value not being in the Console, so show it
        # rather than making someone reconstruct it by hand. Not a secret —
        # it is sent in the clear on every sign-in.
        "google_redirect_uri": _redirect_uri(request),
        "public_base_url": PUBLIC_BASE_URL or "(unset — derived from the request host)",
        "curriculum_files_present": sorted(
            p.name for p in BASE_DIR.glob("*.json") if p.name != "railway.json"),
    }

    try:
        tracks = db.query(Track).order_by(Track.position).all()
    except Exception as e:
        base["database_error"] = f"{type(e).__name__}: {e}"
        base["hint"] = ("The app is running but cannot reach the database. "
                        "Check that DATABASE_URL is added as a Reference to "
                        "the Postgres service in Railway Variables.")
        return base

    # PRIVACY: this endpoint is public, so it exposes NO account details —
    # no emails, no user list. Only aggregate, non-identifying diagnostics.
    # Account information is available only to signed-in admins via
    # /api/admin/students.
    base.update({
        "tracks": len(tracks),
        "lessons": db.query(func.count(Lesson.id)).scalar(),
        "loaded": [{"id": t.slug, "name": t.name, "stage": t.audience,
                    "lessons": len(t.lessons)} for t in tracks],
    })
    return base


@app.post("/api/admin/reload-curriculum")
def reload_curriculum(user: User = Depends(admin_user), db: Session = Depends(get_db)):
    """Wipe all course content and reload it from the JSON files.

    Student accounts, progress, notes and quiz results are NOT touched —
    progress is keyed on lesson slugs, so it reattaches automatically once
    the same lessons are back.
    """
    db.query(Lesson).delete()
    db.query(Track).delete()
    db.commit()

    counts = [
        _seed_file(db, "school.json",     "school",   0),
        _seed_file(db, "stage2.json",     "stage2",   50),
        _seed_file(db, "stage3a.json",    "stage3a",  80),
        _seed_file(db, "stage3b.json",    "stage3b",  90),
        _seed_file(db, "stage4.json",     "stage4",   95),
        _seed_file(db, "curriculum.json", "graduate", 120),
    ]
    db.commit()

    return {
        "ok": True,
        "tracks": sum(counts),
        "per_file": counts,
        "lessons": db.query(func.count(Lesson.id)).scalar(),
    }


# ---------------------------- auth ----------------------------------------
def set_session(resp: Response, user: User, db: Session = None):
    resp.set_cookie(
        "vp_session", make_token(user, db),
        httponly=True, samesite="lax", secure=COOKIE_SECURE,
        max_age=SESSION_DAYS * 86400, path="/",
    )


@app.post("/api/auth/signup")
def signup(body: SignupIn, response: Response, request: Request,
           db: Session = Depends(get_db)):
    email = body.email.lower().strip()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(400, "An account with that email already exists")
    user = User(
        email=email, name=body.name.strip(), password_hash=hash_pw(body.password),
        college=body.college.strip()[:160], city=body.city.strip()[:120],
        degree=body.degree.strip()[:120],
        is_admin=(email == ADMIN_EMAIL),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # A code entered at signup can make this a head teacher, claim a subject
    # slot (subject teacher), or grant generic teacher access.
    role = apply_school_code(db, user, (body.school_code or "").strip())

    if MAIL_ENABLED:
        try:
            _send_verification(db, user, request)
        except Exception as e:
            print(f"verification email failed: {type(e).__name__}: {e}")
    set_session(response, user, db)
    return {"id": user.id, "name": user.name, "email": user.email,
            "email_verified": bool(user.email_verified),
            # plan has to be here, not only on /api/auth/me. isPro() reads
            # USER.plan, so a Pro subscriber who has just signed in had every
            # paid feature rendered locked until they reloaded the page —
            # tapping Learn with Axle Pro sent them to the plans page they had
            # already paid on.
            "plan": plan_of(user),
            "is_admin": user.is_admin, "is_teacher": role in ("head", "teacher"),
            "role": role}


def apply_school_code(db, user, code):
    """Resolve a code entered at signup / join. Returns '' if it matched
    nothing, or 'head' / 'teacher'."""
    if not code:
        return ""
    low = code.lower()

    # 1) Head-teacher code from the admin panel.
    hc = db.query(TeacherCode).filter(
        func.lower(TeacherCode.code) == low, TeacherCode.active == True,  # noqa: E712
        TeacherCode.is_head == True).first()  # noqa: E712
    if hc:
        _grant_teacher(db, user, hc.school, hc.school_id, "head")
        return "head"

    # 2) Subject-slot code created by a head teacher — claims that slot.
    slot = db.query(SubjectSlot).filter(
        func.upper(SubjectSlot.code) == code.upper()).first()
    if slot:
        k = db.get(Klass, slot.class_id)
        if slot.teacher_id and slot.teacher_id != user.id:
            raise HTTPException(400, "That subject already has a teacher")
        slot.teacher_id = user.id
        slot.status = "claimed"
        _grant_teacher(db, user, (k.school if k else ""), (k.school_id if k else 0), "teacher")
        db.commit()
        return "teacher"

    # 3) Generic (non-head) teacher code.
    tc = db.query(TeacherCode).filter(
        func.lower(TeacherCode.code) == low, TeacherCode.active == True,  # noqa: E712
        TeacherCode.is_head == False).first()  # noqa: E712
    if tc:
        _grant_teacher(db, user, tc.school, tc.school_id, "teacher")
        return "teacher"
    return ""


def _grant_teacher(db, user, school, school_id, role):
    ta = db.query(TeacherAccess).filter(TeacherAccess.user_id == user.id).first()
    if ta:
        # never downgrade a head to teacher
        if role == "head":
            ta.role = "head"
        ta.school = school or ta.school
        ta.school_id = school_id or ta.school_id
    else:
        db.add(TeacherAccess(user_id=user.id, school=school or "",
                             school_id=school_id or 0, role=role))
    db.commit()


@app.post("/api/auth/login")
def login(body: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email.lower().strip()).first()
    if not user or not verify_pw(body.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(403, "This account has been deactivated")
    user.last_seen = now()
    db.commit()
    set_session(response, user, db)
    t = teacher_row(user, db)
    return {"id": user.id, "name": user.name, "email": user.email,
            "plan": plan_of(user),
            "is_admin": user.is_admin, "is_teacher": bool(t) or user.is_admin,
            "is_head": is_head(user, db)}


def _send_verification(db, user, request, background=None):
    """Issue a fresh verification link and email it."""
    db.query(PasswordReset).filter(PasswordReset.user_id == user.id,
                                   PasswordReset.purpose == "verify",
                                   PasswordReset.used_at.is_(None))       .update({"used_at": now()}, synchronize_session=False)
    raw = secrets.token_urlsafe(32)
    db.add(PasswordReset(user_id=user.id, purpose="verify",
                         token_hash=hashlib.sha256(raw.encode()).hexdigest(),
                         expires_at=now() + VERIFY_TTL))
    db.commit()
    base = PUBLIC_BASE_URL or str(request.base_url).rstrip("/")
    link = f"{base}/verify?token={raw}"
    body = "\n".join([
        f"Hello {user.name},",
        "",
        "Confirm this is your email address:",
        "",
        link,
        "",
        "The link works once and expires in 3 days. If you did not create a "
        "Craxle account, ignore this email.",
        "",
        "Craxle",
    ])
    if background is not None:
        background.add_task(send_email, user.email, "Confirm your Craxle email", body)
    else:
        send_email(user.email, "Confirm your Craxle email", body)


@app.post("/api/auth/verify/resend")
def auth_verify_resend(background: BackgroundTasks, request: Request,
                       user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    if user.email_verified:
        return {"ok": True, "already": True, "message": "Your email is already confirmed."}
    if not MAIL_ENABLED:
        raise HTTPException(503, "We can't send email right now. Contact support.")
    _send_verification(db, user, request, background)
    return {"ok": True, "message": f"Sent. Check {user.email}, including spam."}


class VerifyIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)


@app.post("/api/auth/verify")
def auth_verify(body: VerifyIn, db: Session = Depends(get_db)):
    """Confirm an address from the emailed link. Single use."""
    h = hashlib.sha256(body.token.strip().encode()).hexdigest()
    row = db.query(PasswordReset).filter(PasswordReset.token_hash == h,
                                         PasswordReset.purpose == "verify").first()
    if not row or row.used_at is not None:
        raise HTTPException(400, "That link has already been used. "
                                 "Sign in and request a new one.")
    exp = row.expires_at
    if exp is not None and exp.tzinfo is None:
        exp = exp.replace(tzinfo=dt.timezone.utc)
    if exp is None or exp < now():
        raise HTTPException(400, "That link has expired. Sign in and request a new one.")
    u = db.get(User, row.user_id)
    if not u:
        raise HTTPException(400, "That account no longer exists")
    u.email_verified, u.verified_at = True, now()
    row.used_at = now()
    db.commit()
    return {"ok": True, "email": u.email,
            "message": "Email confirmed. You have full access now."}


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(min_length=8, max_length=200)


@app.post("/api/auth/forgot")
def auth_forgot(body: ForgotIn, background: BackgroundTasks,
                request: Request, db: Session = Depends(get_db)):
    """Start a password reset.

    Always returns the same response whether or not the address is
    registered — otherwise this endpoint becomes a way to discover who has an
    account here.
    """
    # Do not promise an email we cannot send. This says nothing about whether
    # the address is registered, so it leaks nothing — it just stops someone
    # waiting for a link that can never arrive.
    if not MAIL_ENABLED:
        return {"ok": False, "mail_disabled": True,
                "message": "Password reset by email isn't available right now. "
                           "If you signed up with Google, use Continue with "
                           "Google. Otherwise email "
                           "support@craxle.com and we'll reset it."}
    email = body.email.lower().strip()
    user = db.query(User).filter(func.lower(User.email) == email).first()
    if user and user.is_active:
        # Retire any earlier link so only the newest one works.
        db.query(PasswordReset).filter(PasswordReset.user_id == user.id,
                                       PasswordReset.used_at.is_(None)) \
          .update({"used_at": now()}, synchronize_session=False)
        raw = secrets.token_urlsafe(32)
        db.add(PasswordReset(
            user_id=user.id,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=now() + RESET_TTL))
        db.commit()
        base = PUBLIC_BASE_URL or str(request.base_url).rstrip("/")
        link = f"{base}/reset?token={raw}"
        background.add_task(
            send_email, user.email, "Reset your Craxle password",
            f"Hello {user.name},\n\n"
            f"Use this link to set a new password. It expires in one hour and "
            f"can be used once:\n\n{link}\n\n"
            f"If you did not ask for this, ignore this email — your password "
            f"has not changed.\n\nCraxle")
    return {"ok": True,
            "message": "If that email has an account, a reset link is on its way."}


@app.post("/api/auth/reset")
def auth_reset(body: ResetIn, response: Response, db: Session = Depends(get_db)):
    """Finish a password reset and sign the user in on this device only."""
    h = hashlib.sha256(body.token.strip().encode()).hexdigest()
    row = db.query(PasswordReset).filter(PasswordReset.token_hash == h,
                                        PasswordReset.purpose == "reset").first()
    if not row or row.used_at is not None:
        raise HTTPException(400, "That reset link has already been used. "
                                 "Request a new one.")
    exp = row.expires_at
    if exp is not None and exp.tzinfo is None:
        exp = exp.replace(tzinfo=dt.timezone.utc)
    if exp is None or exp < now():
        raise HTTPException(400, "That reset link has expired. Request a new one.")
    user = db.get(User, row.user_id)
    if not user or not user.is_active:
        raise HTTPException(400, "That account is no longer available")

    user.password_hash = hash_pw(body.password)
    row.used_at = now()
    db.commit()
    # A reset ends every other session — if someone else knew the old
    # password, this is what removes their access.
    set_session(response, user, db)
    return {"ok": True, "name": user.name, "email": user.email}


@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie("vp_session", path="/")
    return {"ok": True}


# ---- Google sign-in ------------------------------------------------------
@app.get("/api/auth/config")
def auth_config(db: Session = Depends(get_db)):
    """Lets the sign-in page know whether Google shows, plus the list of
    enrolled schools so a student/teacher can pick theirs. Names only — no
    private data — so this is safe to expose publicly."""
    try:
        schools = [{"id": s.id, "name": s.name} for s in
                   db.query(School).order_by(School.name).all()]
    except Exception:
        schools = []
    return {"google_enabled": GOOGLE_ENABLED, "schools": schools}


def _redirect_uri(request: Request) -> str:
    base = PUBLIC_BASE_URL or str(request.base_url).rstrip("/")
    # Railway terminates TLS at the proxy; make sure we advertise https.
    if base.startswith("http://") and "localhost" not in base and "127.0.0.1" not in base:
        base = "https://" + base[len("http://"):]
    return base + "/api/auth/google/callback"


@app.get("/api/auth/google/login")
def google_login(request: Request):
    if not GOOGLE_ENABLED:
        raise HTTPException(404, "Google sign-in is not configured")
    state = secrets.token_urlsafe(16)
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": _redirect_uri(request),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    resp = RedirectResponse(
        "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params))
    # short-lived cookie to defend against CSRF on the callback
    resp.set_cookie("g_state", state, max_age=600, httponly=True,
                    samesite="lax", secure=COOKIE_SECURE, path="/")
    return resp


@app.get("/api/auth/google/callback")
async def google_callback(request: Request, db: Session = Depends(get_db)):
    if not GOOGLE_ENABLED:
        raise HTTPException(404, "Google sign-in is not configured")
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if not code or not state or state != request.cookies.get("g_state"):
        return RedirectResponse("/?error=google_state")

    import httpx
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            tok = await client.post("https://oauth2.googleapis.com/token", data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": _redirect_uri(request),
                "grant_type": "authorization_code",
            })
            tok.raise_for_status()
            access = tok.json().get("access_token")
            info = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access}"})
            info.raise_for_status()
            profile = info.json()
    except Exception as e:
        print(f"Google sign-in failed: {type(e).__name__}: {e}")
        return RedirectResponse("/?error=google_failed")

    email = (profile.get("email") or "").lower().strip()
    if not email or not profile.get("verified_email", True):
        return RedirectResponse("/?error=google_email")
    name = profile.get("name") or email.split("@")[0]

    user = db.query(User).filter(User.email == email).first()
    if not user:
        # New Google user — no password; a random hash blocks password login.
        # is_active is set explicitly: column defaults are applied by SQLAlchemy
        # at INSERT, so on a freshly constructed object it is still None — and
        # the check below then read that as "deactivated" and turned every new
        # Google sign-up away.
        user = User(email=email, name=name[:120],
                    password_hash=hash_pw(secrets.token_urlsafe(24)),
                    is_active=True,
                    is_admin=(email == ADMIN_EMAIL))
        db.add(user)
    else:
        user.last_seen = now()
        if email == ADMIN_EMAIL and not user.is_admin:
            user.is_admin = True
        # Only an existing account can have been deactivated.
        if not user.is_active:
            return RedirectResponse("/?error=account_disabled")
    db.commit()
    db.refresh(user)

    resp = RedirectResponse("/")
    set_session(resp, user, db)
    resp.delete_cookie("g_state", path="/")
    return resp


def teacher_row(user: User, db: Session):
    return db.query(TeacherAccess).filter(TeacherAccess.user_id == user.id).first()


def is_head(user: User, db: Session):
    t = teacher_row(user, db)
    return user.is_admin or (t is not None and t.role == "head")


def teacher_user(user: User = Depends(current_user),
                 db: Session = Depends(get_db)) -> User:
    if not teacher_row(user, db) and not user.is_admin:
        raise HTTPException(403, "Teacher access required")
    return user


def head_user(user: User = Depends(current_user),
              db: Session = Depends(get_db)) -> User:
    if not is_head(user, db):
        raise HTTPException(403, "Head teacher access required")
    return user


# The school office. A third role beside head and teacher, and the split is
# the point rather than an implementation detail:
#
#   teacher       the class and nothing else — assignments, material, marking
#   head          runs the teaching: creates classes, subjects, and profiles
#   schooladmin   runs the school: attendance, fees, notices
#
# A teacher marking a child absent, or a head quietly writing off a fee, is
# the kind of thing a school has separated duties for since long before any
# of this was software. Copying that separation is cheaper than explaining
# why we did not.
#
# The head creates the profiles, including this one, because somebody has to
# and it is the head who knows who works there.
SCHOOL_ROLES = ("teacher", "head", "schooladmin")


def is_school_admin(user: User, db: Session) -> bool:
    t = teacher_row(user, db)
    return user.is_admin or (t is not None and t.role == "schooladmin")


def school_admin_user(user: User = Depends(current_user),
                      db: Session = Depends(get_db)) -> User:
    """Attendance, fees and notices. Not the head, and not a teacher.

    Platform admins pass because they have to be able to fix a school's data
    when it goes wrong, and a support call that cannot be answered without
    asking the customer to do it themselves is not support.
    """
    if not is_school_admin(user, db):
        raise HTTPException(
            403, "School office access required. Attendance, fees and school "
                 "notices are kept by the office, not by teaching staff.")
    return user


def _school_of(user: User, db: Session):
    """Which school this member of staff belongs to, and 0 for a platform admin."""
    t = teacher_row(user, db)
    return (t.school_id if t else 0) or 0


@app.get("/api/auth/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    t = teacher_row(user, db)
    role = "admin" if user.is_admin else (t.role if t else "student")
    gate = _learning_only(db, user)
    _ = SCHOOL_ROLES
    return {
        "id": user.id, "name": user.name, "email": user.email,
        # Carried here so the page can show the Pro badge on first paint.
        # Asking /api/billing/me for it would leave every screen briefly
        # claiming the user is on the free plan.
        "plan": plan_of(user),
        # Needed on first paint so the opt-in toggle renders in the right
        # state rather than flicking from off to on a moment later.
        "open_to_work": bool(getattr(user, "open_to_work", False)),
        # Drives the employer-only sidebar. Admins keep the full interface,
        # so this reports the stored value rather than "approved for admins".
        "employer_status": getattr(user, "employer_status", "") or "",
        "email_verified": bool(user.email_verified),
        "verification_required": REQUIRE_EMAIL_VERIFICATION,
        "is_admin": user.is_admin, "path": user.path,
        "is_teacher": bool(t) or user.is_admin,
        "is_head": is_head(user, db),
        "role": role,
        "school": (t.school if t else ""),
        "joined": user.created_at.isoformat() if user.created_at else None,
        # The job half of the sidebar, or the absence of it. The server
        # refuses those routes either way; this is so the page does not
        # offer a door it knows will not open.
        "craxlearn_only": gate["only"],
        "craxlearn_why": gate["why"],
        "craxlearn_message": gate["message"],
        "hidden_pages": list(_cl.JOB_PAGES) if gate["only"] else [],
        "adult": _cl.adult(getattr(user, "dob", None), dt.date.today()),
        "dob": user.dob.isoformat() if getattr(user, "dob", None) else "",
    }


# ---------------------------- classroom -----------------------------------
class ClassIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    schedule: str = ""   # legacy field, ignored now (schedule is a list)


class JoinIn(BaseModel):
    code: str = Field(min_length=3, max_length=16)


class AssignmentIn(BaseModel):
    subject: str = ""
    title: str = Field(min_length=1, max_length=240)
    body: str = ""            # the questions / instructions the teacher types
    due_date: str = ""


class SubmitIn(BaseModel):
    response: str = Field(default="", max_length=20000)


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    student_id: int = 0       # required when a teacher writes; ignored for students


class HelpIn(BaseModel):
    question: str = Field(min_length=2, max_length=1000)


class ScheduleIn(BaseModel):
    day: str = Field(default="", max_length=40)
    text: str = Field(default="", max_length=2000)


class TeacherCodeIn(BaseModel):
    code: str = Field(min_length=3, max_length=40)
    school: str = ""


def _gen_code(db, prefix, model, field):
    import random
    alpha = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(25):
        code = prefix + "".join(random.choice(alpha) for _ in range(4))
        if not db.query(model).filter(field == code).first():
            return code
    return prefix + secrets.token_hex(3).upper()


def _gen_join_code(db) -> str:
    return _gen_code(db, "VP-", Klass, Klass.join_code)


def _gen_slot_code(db) -> str:
    return _gen_code(db, "T-", SubjectSlot, SubjectSlot.code)


def _my_subjects(db, cid, user):
    """Subjects this user is allowed to manage in a class. Head/admin → all."""
    if is_head(user, db):
        return None   # None = all subjects allowed
    return {s.subject for s in db.query(SubjectSlot).filter(
        SubjectSlot.class_id == cid, SubjectSlot.teacher_id == user.id).all()}


def _submitted_ids(db, assignment_id):
    return {r[0] for r in db.query(Submission.user_id)
            .filter(Submission.assignment_id == assignment_id).all()}


def _asg_json(a, done=None):
    d = {"id": a.id, "subject": a.subject or "", "title": a.title,
         "body": a.body or "", "due_date": a.due_date or "",
         "has_pdf": bool(a.pdf_data), "pdf_name": a.pdf_name or "",
         "teacher_id": a.teacher_id or 0,
         "board_topic": getattr(a, "board_topic", "") or "",
         "kind": a.kind, "lesson_slug": a.lesson_slug or ""}
    if done is not None:
        d["done"] = done
    return d


# ---- teacher side ----
@app.post("/api/teacher/class")
def create_class(body: ClassIn, user: User = Depends(head_user),
                 db: Session = Depends(get_db)):
    """Only a head teacher creates classrooms (in their own school)."""
    t = teacher_row(user, db)
    klass = Klass(name=body.name.strip()[:160], join_code=_gen_join_code(db),
                  teacher_id=user.id, school=(t.school if t else ""),
                  school_id=(t.school_id if t else 0))
    db.add(klass)
    db.commit()
    db.refresh(klass)
    return {"id": klass.id, "name": klass.name, "join_code": klass.join_code}


@app.get("/api/teacher/classes")
def my_classes(user: User = Depends(teacher_user), db: Session = Depends(get_db)):
    t = teacher_row(user, db)
    head = is_head(user, db)
    if head:
        # a head teacher sees every classroom in their school
        sid = t.school_id if t else 0
        q = db.query(Klass)
        classes = (q.filter(Klass.school_id == sid) if sid
                   else q.filter(Klass.teacher_id == user.id)).order_by(Klass.created_at.desc()).all()
        my_ids = {k.id for k in classes}
    else:
        # a subject teacher sees only classrooms where they hold a subject
        ids = {s.class_id for s in db.query(SubjectSlot).filter(
            SubjectSlot.teacher_id == user.id).all()}
        classes = db.query(Klass).filter(Klass.id.in_(ids)).order_by(Klass.created_at.desc()).all() if ids else []
        my_ids = set()
    out = []
    for k in classes:
        n = db.query(func.count(ClassMember.id)).filter(ClassMember.class_id == k.id).scalar()
        a = db.query(func.count(Assignment.id)).filter(Assignment.class_id == k.id).scalar()
        subs = {s.subject for s in db.query(SubjectSlot).filter(
            SubjectSlot.class_id == k.id, SubjectSlot.teacher_id == user.id).all()}
        out.append({"id": k.id, "name": k.name, "join_code": k.join_code,
                    "students": n, "assignments": a,
                    "role": "head" if head else "subject teacher",
                    "my_subjects": sorted(subs)})
    return {"classes": out, "is_head": head}


@app.get("/api/teacher/class/{cid}")
def class_detail(cid: int, user: User = Depends(teacher_user),
                 db: Session = Depends(get_db)):
    k = _own_class(db, cid, user)
    assignments = db.query(Assignment).filter(Assignment.class_id == cid) \
        .order_by(Assignment.created_at.desc()).all()
    members = db.query(ClassMember, User).join(User, User.id == ClassMember.user_id) \
        .filter(ClassMember.class_id == cid).all()
    # submission map: assignment_id -> set(user_id)
    submap = {a.id: _submitted_ids(db, a.id) for a in assignments}
    total = len(assignments) or 1
    roster = []
    for cm, u in members:
        done = sum(1 for a in assignments if u.id in submap.get(a.id, set()))
        roster.append({"id": u.id, "name": u.name, "email": u.email,
                       "done": done, "total": len(assignments),
                       "status": {a.id: (u.id in submap.get(a.id, set())) for a in assignments}})
    roster.sort(key=lambda r: r["name"].lower())
    asg_out = []
    for a in assignments:
        asg_out.append({**_asg_json(a),
                        "submitted": len(submap.get(a.id, set())),
                        "members": len(members)})
    sched = db.query(ScheduleItem).filter(ScheduleItem.class_id == cid) \
        .order_by(ScheduleItem.position, ScheduleItem.id).all()
    # list of teachers in this classroom (head + co-teachers)
    head = db.get(User, k.teacher_id)
    teachers = [{"id": k.teacher_id, "name": head.name if head else "", "role": "head teacher"}]
    for s in db.query(SubjectSlot).filter(SubjectSlot.class_id == cid, SubjectSlot.teacher_id != 0).all():
        tu = db.get(User, s.teacher_id)
        teachers.append({"id": s.teacher_id, "name": tu.name if tu else "",
                         "role": s.subject or "subject teacher"})
    allowed = _my_subjects(db, cid, user)   # None = head/admin
    return {"id": k.id, "name": k.name, "join_code": k.join_code,
            "is_head": is_head(user, db) or k.teacher_id == user.id,
            "my_id": user.id, "teachers": teachers,
            "my_subjects": (None if allowed is None else sorted(allowed)),
            "assignments": asg_out, "roster": roster,
            "schedule": [{"id": s.id, "day": s.day, "text": s.text} for s in sched]}


@app.put("/api/teacher/class/{cid}")
def update_class(cid: int, body: ClassIn, user: User = Depends(teacher_user),
                 db: Session = Depends(get_db)):
    k = _head_or_admin(db, cid, user)
    k.name = body.name.strip()[:160]
    db.commit()
    return {"ok": True}


@app.delete("/api/teacher/class/{cid}")
def delete_class(cid: int, user: User = Depends(teacher_user),
                 db: Session = Depends(get_db)):
    k = _head_or_admin(db, cid, user)
    db.delete(k)
    db.commit()
    return {"ok": True}


def _is_coteacher(db, cid, user):
    # a claimed subject slot, or a legacy co-teacher row
    if db.query(SubjectSlot).filter(SubjectSlot.class_id == cid,
                                    SubjectSlot.teacher_id == user.id).first():
        return True
    return db.query(ClassroomTeacher).filter(
        ClassroomTeacher.class_id == cid,
        ClassroomTeacher.teacher_id == user.id).first() is not None


def _own_class(db, cid, user):
    """Any teacher OF this classroom (head teacher of the school, a subject
    teacher who holds a slot here, or admin)."""
    k = db.get(Klass, cid)
    if not k:
        raise HTTPException(404, "Class not found")
    t = teacher_row(user, db)
    head_of_school = t and t.role == "head" and (t.school_id == k.school_id or k.teacher_id == user.id)
    if k.teacher_id == user.id or user.is_admin or head_of_school or _is_coteacher(db, cid, user):
        return k
    raise HTTPException(404, "Class not found")


def _head_or_admin(db, cid, user):
    """Only the classroom's head teacher (creator/school head) or an admin."""
    k = db.get(Klass, cid)
    if not k:
        raise HTTPException(404, "Class not found")
    t = teacher_row(user, db)
    if k.teacher_id == user.id or user.is_admin or (t and t.role == "head" and t.school_id == k.school_id):
        return k
    raise HTTPException(403, "Only the head teacher can do that")


@app.post("/api/teacher/class/{cid}/assignment")
def add_assignment(cid: int, body: AssignmentIn, user: User = Depends(teacher_user),
                   db: Session = Depends(get_db)):
    _own_class(db, cid, user)
    subject = body.subject.strip()[:80]
    # A subject teacher is LOCKED to the subject(s) they hold in this class.
    allowed = _my_subjects(db, cid, user)   # None = head/admin, any subject
    if allowed is not None:
        if not allowed:
            raise HTTPException(403, "You have no subject in this class yet")
        if subject not in allowed:
            # default to their (only) subject rather than reject if blank
            if not subject and len(allowed) == 1:
                subject = next(iter(allowed))
            else:
                raise HTTPException(403, f"You can only set assignments for: {', '.join(sorted(allowed))}")
    a = Assignment(class_id=cid, teacher_id=user.id, kind="task",
                   subject=subject, title=body.title.strip()[:240],
                   body=body.body.strip()[:20000], due_date=body.due_date.strip()[:20])
    db.add(a)
    db.commit()
    db.refresh(a)
    return _asg_json(a)


@app.put("/api/teacher/assignment/{aid}")
def edit_assignment(aid: int, body: AssignmentIn, user: User = Depends(teacher_user),
                    db: Session = Depends(get_db)):
    a = db.get(Assignment, aid)
    if not a:
        raise HTTPException(404, "Not found")
    _own_class(db, a.class_id, user)
    a.subject = body.subject.strip()[:80]
    a.title = body.title.strip()[:240]
    a.body = body.body.strip()[:20000]
    a.due_date = body.due_date.strip()[:20]
    db.commit()
    return _asg_json(a)


@app.delete("/api/teacher/assignment/{aid}")
def delete_assignment(aid: int, user: User = Depends(teacher_user),
                      db: Session = Depends(get_db)):
    a = db.get(Assignment, aid)
    if not a:
        raise HTTPException(404, "Not found")
    _own_class(db, a.class_id, user)
    db.delete(a)
    db.commit()
    return {"ok": True}


@app.post("/api/teacher/assignment/{aid}/pages")
async def upload_pages(aid: int, files: list[UploadFile] = File(...),
                       user: User = Depends(teacher_user),
                       db: Session = Depends(get_db)):
    """Turn uploaded page photos into a single PDF attached to the assignment."""
    a = db.get(Assignment, aid)
    if not a:
        raise HTTPException(404, "Not found")
    _own_class(db, a.class_id, user)
    try:
        from PIL import Image
    except Exception:
        raise HTTPException(500, "Image support is not available on the server")
    images = []
    for f in files[:30]:
        raw = await f.read()
        if len(raw) > 8_000_000:
            continue
        try:
            im = Image.open(io.BytesIO(raw)).convert("RGB")
            images.append(im)
        except Exception:
            continue
    if not images:
        raise HTTPException(400, "No readable images were uploaded")
    buf = io.BytesIO()
    images[0].save(buf, format="PDF", save_all=True, append_images=images[1:])
    a.pdf_data = base64.b64encode(buf.getvalue()).decode()
    a.pdf_name = f"{(a.title or 'assignment')[:40]}.pdf"
    db.commit()
    return {"ok": True, "pages": len(images), "pdf_name": a.pdf_name}


@app.get("/api/assignment/{aid}/pdf")
def get_assignment_pdf(aid: int, user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    a = db.get(Assignment, aid)
    if not a or not a.pdf_data:
        raise HTTPException(404, "No PDF for this assignment")
    # must be the teacher who owns the class, or a member of it
    k = db.get(Klass, a.class_id)
    is_teacher = k and (k.teacher_id == user.id or user.is_admin)
    is_member = db.query(ClassMember).filter(
        ClassMember.class_id == a.class_id, ClassMember.user_id == user.id).first()
    if not (is_teacher or is_member):
        raise HTTPException(403, "Not allowed")
    data = base64.b64decode(a.pdf_data)
    return RawResponse(content=data, media_type="application/pdf",
                       headers={"Content-Disposition": f'inline; filename="{a.pdf_name or "assignment.pdf"}"'})


# ---- schedule (list, editable, deletable) ----
@app.post("/api/teacher/class/{cid}/schedule")
def add_schedule(cid: int, body: ScheduleIn, user: User = Depends(teacher_user),
                 db: Session = Depends(get_db)):
    _own_class(db, cid, user)
    n = db.query(func.count(ScheduleItem.id)).filter(ScheduleItem.class_id == cid).scalar()
    s = ScheduleItem(class_id=cid, day=body.day.strip()[:40],
                     text=body.text.strip()[:2000], position=n)
    db.add(s)
    db.commit()
    db.refresh(s)
    return {"id": s.id, "day": s.day, "text": s.text}


@app.put("/api/teacher/schedule/{sid}")
def edit_schedule(sid: int, body: ScheduleIn, user: User = Depends(teacher_user),
                  db: Session = Depends(get_db)):
    s = db.get(ScheduleItem, sid)
    if not s:
        raise HTTPException(404, "Not found")
    _own_class(db, s.class_id, user)
    s.day = body.day.strip()[:40]
    s.text = body.text.strip()[:2000]
    db.commit()
    return {"id": s.id, "day": s.day, "text": s.text}


@app.delete("/api/teacher/schedule/{sid}")
def delete_schedule(sid: int, user: User = Depends(teacher_user),
                    db: Session = Depends(get_db)):
    s = db.get(ScheduleItem, sid)
    if s:
        _own_class(db, s.class_id, user)
        db.delete(s)
        db.commit()
    return {"ok": True}


# ---- student side ----
@app.post("/api/class/join")
def join_class(body: JoinIn, user: User = Depends(current_user),
               db: Session = Depends(get_db)):
    """Codes: a subject-slot code (from a head teacher) claims that subject
    and locks the teacher to it; a classroom's student code enrols a student."""
    raw = body.code.strip()
    code = raw.upper()

    # 1) A subject-slot code → the teacher claims that subject.
    slot = db.query(SubjectSlot).filter(func.upper(SubjectSlot.code) == code).first()
    if slot:
        if slot.teacher_id and slot.teacher_id != user.id:
            raise HTTPException(400, "That subject already has a teacher")
        k = db.get(Klass, slot.class_id)
        slot.teacher_id = user.id
        slot.status = "claimed"
        _grant_teacher(db, user, (k.school if k else ""), (k.school_id if k else 0), "teacher")
        db.commit()
        return {"ok": True, "class": (k.name if k else ""), "subject": slot.subject, "role": "teacher"}

    # 2) A classroom student code.
    k = db.query(Klass).filter(func.upper(Klass.join_code) == code).first()
    if not k:
        raise HTTPException(404, "No class or subject found with that code")
    if k.teacher_id == user.id:
        return {"ok": True, "class": k.name, "role": "head teacher"}
    # Head/admin viewing does not need enrolment; everyone else enrols as student.
    exists = db.query(ClassMember).filter(
        ClassMember.class_id == k.id, ClassMember.user_id == user.id).first()
    if not exists:
        db.add(ClassMember(class_id=k.id, user_id=user.id))
        db.commit()
    return {"ok": True, "class": k.name, "role": "student"}


@app.post("/api/class/leave/{cid}")
def leave_class(cid: int, user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    row = db.query(ClassMember).filter(
        ClassMember.class_id == cid, ClassMember.user_id == user.id).first()
    if row:
        db.delete(row)
        db.commit()
    return {"ok": True}


@app.get("/api/class/mine")
def my_enrolled_classes(user: User = Depends(current_user),
                        db: Session = Depends(get_db)):
    """Everything the student needs for the weekly table across all teachers."""
    memberships = db.query(ClassMember, Klass).join(Klass, Klass.id == ClassMember.class_id) \
        .filter(ClassMember.user_id == user.id).all()
    mine = {r.assignment_id: r for r in db.query(Submission)
            .filter(Submission.user_id == user.id).all()}
    my_subs = set(mine)
    classes = []
    for cm, k in memberships:
        teacher = db.get(User, k.teacher_id)
        assignments = db.query(Assignment).filter(Assignment.class_id == k.id) \
            .order_by(Assignment.due_date.asc(), Assignment.created_at.desc()).all()
        sched = db.query(ScheduleItem).filter(ScheduleItem.class_id == k.id) \
            .order_by(ScheduleItem.position, ScheduleItem.id).all()
        classes.append({
            "id": k.id, "name": k.name, "school": k.school,
            "teacher": teacher.name if teacher else "",
            "schedule": [{"day": s.day, "text": s.text} for s in sched],
            "assignments": [
                {**_asg_json(a, a.id in my_subs),
                 "reviewed": bool(mine[a.id].reviewed_at) if a.id in mine else False,
                 "feedback": (mine[a.id].feedback or "") if a.id in mine else ""}
                for a in assignments],
        })
    return {"classes": classes}


@app.get("/api/assignment/{aid}")
def assignment_detail(aid: int, user: User = Depends(current_user),
                      db: Session = Depends(get_db)):
    a = db.get(Assignment, aid)
    if not a:
        raise HTTPException(404, "Not found")
    member = db.query(ClassMember).filter(
        ClassMember.class_id == a.class_id, ClassMember.user_id == user.id).first()
    k = db.get(Klass, a.class_id)
    if not member and not (k and (k.teacher_id == user.id or user.is_admin)):
        raise HTTPException(403, "Not in this class")
    sub = db.query(Submission).filter(
        Submission.assignment_id == aid, Submission.user_id == user.id).first()
    teacher = db.get(User, a.teacher_id)
    return {**_asg_json(a, bool(sub)),
            "class_name": k.name if k else "",
            "teacher_name": teacher.name if teacher else "",
            "my_response": sub.response if sub else "",
            "submitted_at": sub.updated_at.isoformat() if sub and sub.updated_at else None,
            # The verdict, where there is one. A student who has submitted
            # and heard nothing should be able to see that plainly rather
            # than reading it as silence from a teacher.
            "feedback": (sub.feedback or "") if sub else "",
            "reviewed_at": (sub.reviewed_at.isoformat()
                            if sub and sub.reviewed_at else None)}


@app.post("/api/assignment/{aid}/submit")
def submit_assignment(aid: int, body: SubmitIn, user: User = Depends(current_user),
                      db: Session = Depends(get_db)):
    a = db.get(Assignment, aid)
    if not a:
        raise HTTPException(404, "Not found")
    member = db.query(ClassMember).filter(
        ClassMember.class_id == a.class_id, ClassMember.user_id == user.id).first()
    if not member:
        raise HTTPException(403, "Not in this class")
    text = body.response.strip()
    sub = db.query(Submission).filter(
        Submission.assignment_id == aid, Submission.user_id == user.id).first()
    if not text:
        # empty submission = un-submit / mark not done
        if sub:
            db.delete(sub)
            db.commit()
        return {"done": False}
    if sub:
        sub.response = text[:20000]
    else:
        db.add(Submission(assignment_id=aid, user_id=user.id, response=text[:20000]))
    db.commit()
    return {"done": True}


# ---- per-assignment chat (student <-> the teacher who set it) ----
def _asg_and_access(db, aid, user):
    a = db.get(Assignment, aid)
    if not a:
        raise HTTPException(404, "Not found")
    k = db.get(Klass, a.class_id)
    is_teacher = k and (k.teacher_id == user.id or user.is_admin)
    is_member = db.query(ClassMember).filter(
        ClassMember.class_id == a.class_id, ClassMember.user_id == user.id).first()
    if not (is_teacher or is_member):
        raise HTTPException(403, "Not allowed")
    return a, k, bool(is_teacher)


@app.get("/api/assignment/{aid}/messages")
def get_messages(aid: int, student_id: int = 0, user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    a, k, is_teacher = _asg_and_access(db, aid, user)
    sid = student_id if is_teacher else user.id
    if not sid:
        return {"messages": [], "student_id": 0}
    msgs = db.query(AssignmentMessage).filter(
        AssignmentMessage.assignment_id == aid,
        AssignmentMessage.student_id == sid).order_by(AssignmentMessage.created_at).all()
    return {"student_id": sid, "messages": [{
        "from_teacher": m.from_teacher, "body": m.body,
        "at": m.created_at.isoformat() if m.created_at else None} for m in msgs]}


@app.post("/api/assignment/{aid}/message")
def post_message(aid: int, body: MessageIn, user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    a, k, is_teacher = _asg_and_access(db, aid, user)
    sid = body.student_id if is_teacher else user.id
    if not sid:
        raise HTTPException(400, "No student thread specified")
    db.add(AssignmentMessage(assignment_id=aid, student_id=sid, sender_id=user.id,
                             from_teacher=is_teacher, body=body.body.strip()[:4000]))
    db.commit()
    return {"ok": True}


@app.get("/api/teacher/assignment/{aid}/submissions")
def assignment_submissions(aid: int, user: User = Depends(teacher_user),
                           db: Session = Depends(get_db)):
    a = db.get(Assignment, aid)
    if not a:
        raise HTTPException(404, "Not found")
    _own_class(db, a.class_id, user)
    members = db.query(ClassMember, User).join(User, User.id == ClassMember.user_id) \
        .filter(ClassMember.class_id == a.class_id).all()
    subs = {s.user_id: s for s in db.query(Submission)
            .filter(Submission.assignment_id == aid).all()}
    students = []
    for cm, u in members:
        s = subs.get(u.id)
        fresh = bool(s and s.reviewed_at and s.updated_at
                     and s.updated_at > s.reviewed_at)
        students.append({"id": u.id, "name": u.name,
                         "response": s.response if s else "",
                         "submitted": bool(s),
                         "feedback": (s.feedback or "") if s else "",
                         "reviewed": bool(s and s.reviewed_at) and not fresh,
                         "resubmitted": fresh,
                         "at": s.updated_at.isoformat() if s and s.updated_at else None})
    students.sort(key=lambda r: (not r["submitted"], r["reviewed"],
                                 r["name"].lower()))
    return {"id": a.id, "subject": a.subject, "title": a.title, "body": a.body,
            "students": students}


@app.get("/api/teacher/assignment/{aid}/threads")
def assignment_threads(aid: int, user: User = Depends(teacher_user),
                       db: Session = Depends(get_db)):
    """Which students have messaged the teacher about this assignment."""
    a = db.get(Assignment, aid)
    if not a:
        raise HTTPException(404, "Not found")
    _own_class(db, a.class_id, user)
    sids = [r[0] for r in db.query(AssignmentMessage.student_id)
            .filter(AssignmentMessage.assignment_id == aid).distinct().all()]
    out = []
    for sid in sids:
        u = db.get(User, sid)
        last = db.query(AssignmentMessage).filter(
            AssignmentMessage.assignment_id == aid,
            AssignmentMessage.student_id == sid).order_by(
            AssignmentMessage.created_at.desc()).first()
        out.append({"student_id": sid, "name": u.name if u else "student",
                    "last": last.body if last else "",
                    "from_teacher": last.from_teacher if last else False})
    return {"threads": out}


@app.post("/api/assignment/{aid}/help")
async def assignment_help(aid: int, body: HelpIn, user: User = Depends(current_user),
                          db: Session = Depends(get_db)):
    """AI help scoped to this assignment. Guides, does not just hand answers."""
    a, k, _ = _asg_and_access(db, aid, user)
    if not ASK_ENABLED:
        raise HTTPException(503, "The AI helper is not switched on")
    subject = a.subject or "the subject"
    prompt = (
        f"You are a patient tutor helping a student with a school assignment. "
        f"Subject: {subject}. Assignment title: {a.title}. "
        f"The teacher's instructions were: {a.body[:1500]}\n\n"
        f"The student asks: \"{body.question}\"\n\n"
        f"Help them UNDERSTAND and make progress. Explain the idea and give a "
        f"worked hint or example. Do NOT simply write their final answer for "
        f"them to copy. Keep it short, clear, and matched to a school student. "
        f"Reply as plain helpful text (no JSON)."
    )
    try:
        import httpx
        async with httpx.AsyncClient(timeout=45) as client:
            if AI_PROVIDER == "gemini":
                r = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
                    headers={"x-goog-api-key": GEMINI_API_KEY, "content-type": "application/json"},
                    json={"contents": [{"parts": [{"text": prompt}]}],
                          "generationConfig": {"maxOutputTokens": 800, "temperature": 0.5}})
                _upstream_ok(r, "gemini")
                text = "".join(p.get("text", "") for c in r.json().get("candidates", [])
                               for p in c.get("content", {}).get("parts", [])).strip()
            elif AI_PROVIDER == "groq":
                r = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}", "content-type": "application/json"},
                    json={"model": GROQ_MODEL, "max_tokens": 800, "temperature": 0.5,
                          "messages": [{"role": "user", "content": prompt}]})
                _upstream_ok(r, "groq")
                text = r.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            else:
                r = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                             "content-type": "application/json"},
                    json={"model": ANTHROPIC_MODEL, "max_tokens": 800,
                          "messages": [{"role": "user", "content": prompt}]})
                _upstream_ok(r, "claude")
                text = "".join(b.get("text", "") for b in r.json().get("content", [])
                               if b.get("type") == "text").strip()
    except Exception as e:
        print(f"Assignment help failed ({AI_PROVIDER}): {type(e).__name__}: {e}")
        raise HTTPException(503, "The helper could not respond just now. Try again.")
    return {"answer": text or "I could not think of a hint just now — try rephrasing."}


# ---- admin: teacher codes and roles ----
# ============ Head teacher: run a school ============
class SubjectIn(BaseModel):
    subject: str = Field(min_length=1, max_length=80)


class RequestIn(BaseModel):
    class_id: int = 0
    message: str = Field(min_length=2, max_length=2000)


def _slot_json(db, s):
    tu = db.get(User, s.teacher_id) if s.teacher_id else None
    return {"id": s.id, "subject": s.subject, "code": s.code,
            "status": s.status, "teacher": tu.name if tu else "",
            "teacher_id": s.teacher_id or 0}


@app.get("/api/head/overview")
def head_overview(user: User = Depends(head_user), db: Session = Depends(get_db)):
    t = teacher_row(user, db)
    sid = t.school_id if t else 0
    classes = (db.query(Klass).filter(Klass.school_id == sid).all() if sid
               else db.query(Klass).filter(Klass.teacher_id == user.id).all())
    out = []
    for k in classes:
        slots = db.query(SubjectSlot).filter(SubjectSlot.class_id == k.id) \
            .order_by(SubjectSlot.subject).all()
        nstu = db.query(func.count(ClassMember.id)).filter(ClassMember.class_id == k.id).scalar()
        out.append({"id": k.id, "name": k.name, "join_code": k.join_code,
                    "students": nstu,
                    "subjects": [_slot_json(db, s) for s in slots]})
    reqs = db.query(TeacherRequest).filter(
        TeacherRequest.school_id == sid, TeacherRequest.status == "open").all()
    requests = []
    for r in reqs:
        ru = db.get(User, r.teacher_id)
        requests.append({"id": r.id, "teacher": ru.name if ru else "",
                         "message": r.message, "class_id": r.class_id})
    return {"school": (t.school if t else ""), "classrooms": out, "requests": requests}


@app.post("/api/head/class/{cid}/slot")
def head_add_slot(cid: int, body: SubjectIn, user: User = Depends(head_user),
                  db: Session = Depends(get_db)):
    _head_or_admin(db, cid, user)
    s = SubjectSlot(class_id=cid, subject=body.subject.strip()[:80],
                    code=_gen_slot_code(db))
    db.add(s)
    db.commit()
    db.refresh(s)
    return _slot_json(db, s)


@app.post("/api/head/slot/{sid}/rotate")
def head_rotate_slot(sid: int, user: User = Depends(head_user),
                     db: Session = Depends(get_db)):
    s = db.get(SubjectSlot, sid)
    if not s:
        raise HTTPException(404, "Not found")
    _head_or_admin(db, s.class_id, user)
    s.code = _gen_slot_code(db)
    s.teacher_id = 0            # rotating a code unassigns the current teacher
    s.status = "open"
    db.commit()
    return _slot_json(db, s)


@app.delete("/api/head/slot/{sid}")
def head_delete_slot(sid: int, user: User = Depends(head_user),
                     db: Session = Depends(get_db)):
    s = db.get(SubjectSlot, sid)
    if s:
        _head_or_admin(db, s.class_id, user)
        db.delete(s)
        db.commit()
    return {"ok": True}


@app.post("/api/head/class/{cid}/rotate")
def head_rotate_class(cid: int, user: User = Depends(head_user),
                      db: Session = Depends(get_db)):
    k = _head_or_admin(db, cid, user)
    k.join_code = _gen_join_code(db)
    db.commit()
    return {"join_code": k.join_code}


@app.post("/api/teacher/request")
def teacher_request(body: RequestIn, user: User = Depends(teacher_user),
                    db: Session = Depends(get_db)):
    """A subject teacher asks the head for a new subject/class."""
    t = teacher_row(user, db)
    db.add(TeacherRequest(school_id=(t.school_id if t else 0),
                          class_id=body.class_id, teacher_id=user.id,
                          message=body.message.strip()[:2000]))
    db.commit()
    return {"ok": True}


@app.post("/api/head/request/{rid}/done")
def head_close_request(rid: int, user: User = Depends(head_user),
                       db: Session = Depends(get_db)):
    r = db.get(TeacherRequest, rid)
    if r:
        r.status = "done"
        db.commit()
    return {"ok": True}


# ---- notifications / messages inbox ----
def _aware(d):
    if d is None:
        return dt.datetime.min.replace(tzinfo=dt.timezone.utc)
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


@app.get("/api/notifications")
def notifications(user: User = Depends(current_user), db: Session = Depends(get_db)):
    items = []
    # Background job alerts come first: they are time-sensitive in a way that
    # a teacher reply is not.
    for a in db.query(JobAlert).filter(JobAlert.user_id == user.id).order_by(
            JobAlert.created_at.desc()).limit(15).all():
        items.append({"type": a.kind, "icon": a.icon or "\U0001f4bc",
                      "text": a.text, "url": a.url or "",
                      "when": _aware(a.created_at).isoformat(),
                      "unread": not a.seen})
    t = teacher_row(user, db)
    if not t and not user.is_admin:
        # STUDENT: teacher replies to me, and assignments set in my classes
        for m in db.query(AssignmentMessage).filter(
                AssignmentMessage.student_id == user.id,
                AssignmentMessage.from_teacher == True).order_by(  # noqa: E712
                AssignmentMessage.created_at.desc()).limit(20).all():
            a = db.get(Assignment, m.assignment_id)
            if a:
                items.append({"type": "reply", "icon": "💬",
                              "text": f"Teacher replied on “{a.title}”",
                              "when": _aware(m.created_at).isoformat(), "aid": a.id})
        my_cids = [cm.class_id for cm in db.query(ClassMember).filter(
            ClassMember.user_id == user.id).all()]
        if my_cids:
            for a in db.query(Assignment).filter(Assignment.class_id.in_(my_cids)) \
                    .order_by(Assignment.created_at.desc()).limit(20).all():
                items.append({"type": "assignment", "icon": "📌",
                              "text": f"Assignment: {a.subject+' · ' if a.subject else ''}{a.title}",
                              "when": _aware(a.created_at).isoformat(), "aid": a.id})
    else:
        # TEACHER: students messaging me on my assignments
        my_aids = [a.id for a in db.query(Assignment).filter(
            Assignment.teacher_id == user.id).all()]
        if my_aids:
            for m in db.query(AssignmentMessage).filter(
                    AssignmentMessage.assignment_id.in_(my_aids),
                    AssignmentMessage.from_teacher == False).order_by(  # noqa: E712
                    AssignmentMessage.created_at.desc()).limit(25).all():
                a = db.get(Assignment, m.assignment_id)
                su = db.get(User, m.student_id)
                items.append({"type": "msg", "icon": "💬",
                              "text": f"{su.name if su else 'A student'} messaged on “{a.title if a else ''}”",
                              "when": _aware(m.created_at).isoformat(),
                              "aid": (a.id if a else 0), "cid": (a.class_id if a else 0)})
        if t and t.role == "head":
            for r in db.query(TeacherRequest).filter(
                    TeacherRequest.school_id == t.school_id,
                    TeacherRequest.status == "open").order_by(
                    TeacherRequest.created_at.desc()).limit(20).all():
                ru = db.get(User, r.teacher_id)
                items.append({"type": "request", "icon": "🙋",
                              "text": f"{ru.name if ru else 'A teacher'} requests: {r.message[:80]}",
                              "when": _aware(r.created_at).isoformat()})
    items.sort(key=lambda x: x["when"], reverse=True)
    items = items[:40]
    # unread = newer than the last time they opened the inbox
    seen_row = db.query(Note).filter(Note.user_id == user.id, Note.k == "__notif_seen__").first()
    seen = seen_row.v if seen_row else ""
    unread = sum(1 for it in items if it["when"] > seen)
    return {"items": items, "unread": unread}


@app.post("/api/notifications/seen")
def notifications_seen(user: User = Depends(current_user), db: Session = Depends(get_db)):
    stamp = now().isoformat()
    row = db.query(Note).filter(Note.user_id == user.id, Note.k == "__notif_seen__").first()
    if row:
        row.v = stamp
    else:
        db.add(Note(user_id=user.id, k="__notif_seen__", v=stamp))
    db.commit()
    return {"ok": True}


# ============ Admin: enrol schools and head teachers ============
class SchoolIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    city: str = ""
    country: str = ""


@app.post("/api/admin/school")
def admin_create_school(body: SchoolIn, user: User = Depends(admin_user),
                        db: Session = Depends(get_db)):
    sc = School(name=body.name.strip()[:200], city=body.city.strip()[:120],
                country=body.country.strip()[:120])
    db.add(sc)
    db.commit()
    db.refresh(sc)
    # auto-create a head-teacher code for this school
    code = _gen_code(db, "HEAD-", TeacherCode, TeacherCode.code)
    db.add(TeacherCode(code=code, school=sc.name, school_id=sc.id, is_head=True))
    db.commit()
    return {"id": sc.id, "name": sc.name, "head_code": code}


@app.post("/api/admin/school/{sid}/head-code")
def admin_new_head_code(sid: int, user: User = Depends(admin_user),
                        db: Session = Depends(get_db)):
    sc = db.get(School, sid)
    if not sc:
        raise HTTPException(404, "School not found")
    # deactivate old head codes so a former head cannot re-register
    for old in db.query(TeacherCode).filter(TeacherCode.school_id == sid,
                                            TeacherCode.is_head == True).all():  # noqa: E712
        old.active = False
    code = _gen_code(db, "HEAD-", TeacherCode, TeacherCode.code)
    db.add(TeacherCode(code=code, school=sc.name, school_id=sc.id, is_head=True))
    db.commit()
    return {"head_code": code}


@app.delete("/api/admin/school/{sid}")
def admin_delete_school(sid: int, user: User = Depends(admin_user),
                        db: Session = Depends(get_db)):
    sc = db.get(School, sid)
    if sc:
        db.delete(sc)
        db.commit()
    return {"ok": True}


class ResetUsersIn(BaseModel):
    # Typed out in full, by hand, every time. A confirm flag is a checkbox
    # somebody ticks without reading; a sentence they have to type is a
    # sentence they have to read first.
    confirm: str = Field(default="", max_length=80)
    keep_schools: bool = True


RESET_PHRASE = "DELETE ALL NON ADMIN ACCOUNTS"


@app.get("/api/admin/reset-users/preview")
def admin_reset_preview(user: User = Depends(admin_user),
                        db: Session = Depends(get_db)):
    """What deleting every non-admin account would actually destroy.

    Shown before, never after. The counts that matter are the ones somebody
    would regret: paid subscriptions, submitted work, saved resumes. A
    number on the screen is the only thing standing between "start fresh"
    and finding out on Monday what start fresh meant.
    """
    q = db.query(User).filter(User.is_admin == False)          # noqa: E712
    ids = [r[0] for r in q.with_entities(User.id).all()]
    paid = q.filter(User.plan != "free").count()
    return {
        "phrase": RESET_PHRASE,
        "users": len(ids),
        "paying": paid,
        "submissions": (db.query(func.count(Submission.id))
                        .filter(Submission.user_id.in_(ids)).scalar() or 0
                        if ids else 0),
        "resumes": (db.query(func.count(Note.id))
                    .filter(Note.user_id.in_(ids),
                            Note.k.like("resume%")).scalar() or 0
                    if ids else 0),
        "teachers": db.query(func.count(TeacherAccess.id)).scalar() or 0,
        "warning": ("This cannot be undone. Paying subscribers keep being "
                    "billed by the payment provider after their account is "
                    "gone — cancel those first."),
    }


@app.post("/api/admin/reset-users")
def admin_reset_users(body: ResetUsersIn, user: User = Depends(admin_user),
                      db: Session = Depends(get_db)):
    """Delete every non-admin account so everybody signs up again.

    Guarded three ways, because it is the most destructive thing this
    codebase can do and it is one request away from being done by accident:
    admin only, the exact phrase typed out, and a preview endpoint that
    exists to be read first.

    Schools, classes and rosters are kept by default. Deleting those too
    would take the join codes with them, and then nobody can come back in —
    a "start fresh" that also destroys the way back is not a reset, it is
    an outage with extra steps.
    """
    if body.confirm.strip().upper() != RESET_PHRASE:
        raise HTTPException(
            400, f'To confirm, send confirm="{RESET_PHRASE}" exactly. '
                 f"Read /api/admin/reset-users/preview first.")

    ids = [r[0] for r in db.query(User.id)
           .filter(User.is_admin == False).all()]                # noqa: E712
    if not ids:
        return {"ok": True, "deleted": 0}

    # Rosters first, and by hand: claimed_by is a plain integer, not a
    # foreign key, so nothing would cascade and every name would stay
    # claimed by an account that no longer exists — a register where
    # nobody can sign in and the teacher cannot see why.
    freed = (db.query(RosterName).filter(RosterName.claimed_by.in_(ids))
               .update({RosterName.claimed_by: 0, RosterName.claimed_at: None},
                       synchronize_session=False))

    # Everything else hangs off users.id with ON DELETE CASCADE, so the
    # rows go with the account. Deleted in chunks: a single IN clause over
    # tens of thousands of ids is a statement Postgres will refuse to plan.
    gone = 0
    for i in range(0, len(ids), 500):
        chunk = ids[i:i + 500]
        gone += (db.query(User).filter(User.id.in_(chunk))
                   .delete(synchronize_session=False))
        db.commit()

    print(f"ADMIN RESET: {gone} accounts deleted by {user.email}, "
          f"{freed} roster names freed")
    return {"ok": True, "deleted": gone, "roster_names_freed": freed,
            "kept": "admins, schools, classes and class codes"}


@app.get("/api/admin/schools")
def admin_list_schools(user: User = Depends(admin_user), db: Session = Depends(get_db)):
    out = []
    for sc in db.query(School).order_by(School.created_at.desc()).all():
        heads = db.query(TeacherAccess, User).join(User, User.id == TeacherAccess.user_id) \
            .filter(TeacherAccess.school_id == sc.id, TeacherAccess.role == "head").all()
        classes = db.query(Klass).filter(Klass.school_id == sc.id).all()
        active_code = db.query(TeacherCode).filter(
            TeacherCode.school_id == sc.id, TeacherCode.is_head == True,  # noqa: E712
            TeacherCode.active == True).order_by(TeacherCode.created_at.desc()).first()  # noqa: E712
        out.append({
            "id": sc.id, "name": sc.name, "city": sc.city, "country": sc.country,
            "head_code": active_code.code if active_code else None,
            "heads": [{"id": u.id, "name": u.name, "email": u.email} for ta, u in heads],
            "classrooms": [{"id": k.id, "name": k.name, "code": k.join_code} for k in classes],
        })
    return {"schools": out}


@app.get("/api/admin/teacher-codes")
def list_teacher_codes(user: User = Depends(admin_user), db: Session = Depends(get_db)):
    codes = db.query(TeacherCode).order_by(TeacherCode.created_at.desc()).all()
    teachers = db.query(TeacherAccess, User).join(User, User.id == TeacherAccess.user_id).all()
    online_since = now() - dt.timedelta(minutes=10)

    # classrooms with head teacher, code, counts
    classrooms = []
    subjects = set()
    for k in db.query(Klass).order_by(Klass.created_at.desc()).all():
        head = db.get(User, k.teacher_id)
        nstu = db.query(func.count(ClassMember.id)).filter(ClassMember.class_id == k.id).scalar()
        nco = db.query(func.count(ClassroomTeacher.id)).filter(ClassroomTeacher.class_id == k.id).scalar()
        for (s,) in db.query(Assignment.subject).filter(Assignment.class_id == k.id).distinct():
            if s:
                subjects.add(s)
        classrooms.append({"id": k.id, "name": k.name, "code": k.join_code,
                           "school": k.school, "head": head.name if head else "",
                           "students": nstu, "teachers": (nco or 0) + 1})

    return {
        "codes": [{"id": c.id, "code": c.code, "school": c.school, "active": c.active}
                  for c in codes],
        "teachers": [{"id": u.id, "name": u.name, "email": u.email, "school": ta.school,
                      "online": bool(u.last_seen and (u.last_seen if u.last_seen.tzinfo
                                     else u.last_seen.replace(tzinfo=dt.timezone.utc)) >= online_since)}
                     for ta, u in teachers],
        "schools": sorted({(ta.school or "").strip() for ta, u in teachers if (ta.school or "").strip()}),
        "classrooms": classrooms,
        "subjects": sorted(subjects),
    }


@app.post("/api/admin/teacher-code")
def create_teacher_code(body: TeacherCodeIn, user: User = Depends(admin_user),
                        db: Session = Depends(get_db)):
    code = body.code.strip()
    if db.query(TeacherCode).filter(func.lower(TeacherCode.code) == code.lower()).first():
        raise HTTPException(400, "That code already exists")
    tc = TeacherCode(code=code[:40], school=body.school.strip()[:160])
    db.add(tc)
    db.commit()
    return {"id": tc.id, "code": tc.code, "school": tc.school}


@app.delete("/api/admin/teacher-code/{cid}")
def delete_teacher_code(cid: int, user: User = Depends(admin_user),
                        db: Session = Depends(get_db)):
    tc = db.get(TeacherCode, cid)
    if tc:
        db.delete(tc)
        db.commit()
    return {"ok": True}


@app.post("/api/admin/make-teacher/{uid}")
def make_teacher(uid: int, user: User = Depends(admin_user),
                 db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "User not found")
    if not db.query(TeacherAccess).filter(TeacherAccess.user_id == uid).first():
        db.add(TeacherAccess(user_id=uid, school=u.college or ""))
        db.commit()
    return {"ok": True}


@app.delete("/api/admin/make-teacher/{uid}")
def remove_teacher(uid: int, user: User = Depends(admin_user),
                   db: Session = Depends(get_db)):
    row = db.query(TeacherAccess).filter(TeacherAccess.user_id == uid).first()
    if row:
        db.delete(row)
        db.commit()
    return {"ok": True}

# ---------------------------- curriculum ----------------------------------
def serialise_track(t: Track, include_unpublished=False):
    lessons = [l for l in t.lessons if l.published or include_unpublished]
    return {
        "id": t.slug, "icon": t.icon, "name": t.name, "level": t.level,
        "color": t.color, "weeks": t.weeks, "lang": t.lang, "desc": t.desc,
        "audience": t.audience or "graduate",
        "outcomes": json.loads(t.outcomes or "[]"),
        "quiz": json.loads(t.quiz or "[]"),
        "published": t.published,
        "lessons": [{
            "id": l.slug, "title": l.title, "mins": l.mins, "lang": l.lang,
            "content": l.content,
            "videos": json.loads(l.videos or "[]"),
            "refs": json.loads(l.refs or "[]"),
            "lab": json.loads(l.lab or "{}"),
            "exercises": json.loads(l.exercises or "[]"),
            "worksheet": json.loads(l.worksheet or "[]"),
            "published": l.published,
        } for l in lessons],
    }


@app.get("/api/curriculum")
def curriculum(user: User = Depends(current_user), db: Session = Depends(get_db)):
    tracks = db.query(Track).filter(Track.published == True).order_by(Track.position).all()  # noqa: E712
    return {"tracks": [serialise_track(t) for t in tracks]}


XP_PER_EXERCISE = 10
XP_PER_LESSON = 25
XP_PER_QUIZ = 50
XP_PER_LEVEL = 250


def _compute_stats(rows, all_quizzes, notes):
    """XP, level and streak, derived from existing records.

    Derived rather than stored: it can never be double-awarded, and it
    stays correct even if progress rows are edited or deleted.
    """
    lessons_done = sum(1 for r in rows if r.completed)
    ex_passed = sum(1 for n in notes if n.k.startswith("ex_") and n.v == "1")
    quiz_passed = len({q.track_slug for q in all_quizzes if q.passed})

    xp = (ex_passed * XP_PER_EXERCISE
          + lessons_done * XP_PER_LESSON
          + quiz_passed * XP_PER_QUIZ)
    level = 1 + xp // XP_PER_LEVEL

    # Streak: consecutive days (ending today or yesterday) with any activity.
    days = set()
    for r in rows:
        d = r.updated_at or r.completed_at
        if d:
            days.add(d.date())
    for q in all_quizzes:
        if q.created_at:
            days.add(q.created_at.date())

    today = now().date()
    day = today if today in days else today - dt.timedelta(days=1)
    streak = 0
    while day in days:
        streak += 1
        day -= dt.timedelta(days=1)

    return {
        "xp": xp, "level": level, "streak": streak,
        "level_progress": (xp % XP_PER_LEVEL) / XP_PER_LEVEL,
        "next_level_at": (xp // XP_PER_LEVEL + 1) * XP_PER_LEVEL,
    }


@app.get("/api/progress")
def get_progress(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.query(Progress).filter(Progress.user_id == user.id).all()
    all_quizzes = db.query(QuizResult).filter(QuizResult.user_id == user.id).all()
    notes = db.query(Note).filter(Note.user_id == user.id).all()
    return {
        "done": {r.lesson_slug: True for r in rows if r.completed},
        "code": {r.lesson_slug: r.code for r in rows if r.code},
        "quiz": {q.track_slug: True for q in all_quizzes if q.passed},
        "notes": {n.k: n.v for n in notes},
        "path": user.path,
        "stats": _compute_stats(rows, all_quizzes, notes),
    }


@app.post("/api/progress")
def set_progress(body: ProgressIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = db.query(Progress).filter(
        Progress.user_id == user.id, Progress.lesson_slug == body.lesson).first()
    if not row:
        row = Progress(user_id=user.id, lesson_slug=body.lesson)
        db.add(row)
    if body.attempt:
        row.attempts = (row.attempts or 0) + 1
    if body.code is not None:
        row.code = body.code[:20000]
    if body.completed is not None:
        row.completed = body.completed
        row.completed_at = now() if body.completed else None
    db.commit()
    return {"ok": True}


@app.post("/api/quiz")
def post_quiz(body: QuizIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    passed = body.total > 0 and body.score == body.total
    db.add(QuizResult(user_id=user.id, track_slug=body.track,
                      score=body.score, total=body.total, passed=passed))
    db.commit()
    return {"passed": passed}


@app.post("/api/note")
def post_note(body: NoteIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if body.key == "__path__":
        user.path = body.value[:40]
        db.commit()
        return {"ok": True}
    row = db.query(Note).filter(Note.user_id == user.id, Note.k == body.key).first()
    if body.value == "":
        if row:
            db.delete(row)
            db.commit()
        return {"ok": True}
    if not row:
        row = Note(user_id=user.id, k=body.key[:120])
        db.add(row)
    # Resume payloads (which can include a base64 photo and a full positional
    # layout) are much larger than a checklist note, so give resume keys plenty
    # of room; everything else stays modest.
    cap = 600_000 if body.key.startswith("resume") else 5000
    row.v = body.value[:cap]
    db.commit()
    return {"ok": True}


# ---------------------------- Ask Axle -----------------------------------
import re as _re

# Who the tutor is, what grade she is pitching at, and the short list of
# panels she is allowed to open. Kept out of this file because the same
# persona has to reach the board, the voice and the corner bot, and three
# copies of it drifted into three different teachers.
import dalia as _dalia                                              # noqa: E402

# Where a learner's questions are kept, and where answers may be sourced
# from. Both halves of that are policy rather than plumbing, so they live in
# one readable file instead of being spread across the endpoints that
# happen to enforce them.
import craxlearn as _cl                                             # noqa: E402

# The allowlisted arithmetic evaluator. Imported again further down for the
# lesson checks; imported here too so the classroom calculator's dependency
# is visible beside the endpoint that uses it rather than 7,000 lines away.
# The measured-structure sources and the picture search, both used by the
# board further down and by Craxlearn's own structure and search screens.
# Imported here so those endpoints' dependencies are visible beside them.
import scene as _scene                                              # noqa: E402
import lattice as _lattice                                          # noqa: E402
import layers as _layers                                            # noqa: E402
import orbits as _orbits                                            # noqa: E402
import molecule as _molecule                                        # noqa: E402
import protein as _protein                                          # noqa: E402
import images as _images                                            # noqa: E402
import maths as _maths                                              # noqa: E402


def _scope_of(db, user):
    """Which pool this person's questions and answers belong to.

    A teacher's institution is on their access row. A student's comes
    through the class they joined, which is the only link a student has to a
    school at all.

    Read on every cached request, so it is one indexed lookup and then a
    second only for people who are not teachers. Wrong in the safe direction
    on failure: anybody the query cannot resolve who nonetheless has a class
    membership is treated as an institution learner with an unknown school,
    never as a member of the public pool.
    """
    ta = (db.query(TeacherAccess)
            .filter(TeacherAccess.user_id == user.id).first())
    if ta:
        return _cl.scope_of(ta.school_id, in_institution=True)
    row = (db.query(Klass.school_id)
             .join(ClassMember, ClassMember.class_id == Klass.id)
             .filter(ClassMember.user_id == user.id).first())
    if row is None:
        return _cl.PUBLIC
    return _cl.scope_of(row[0], in_institution=True)


def _record_learning(db, user, scope, kind, text, subject="", level=""):
    """Note that this was asked, inside the asker's own institution.

    Fire and forget, exactly like the client-side history it sits beside: an
    answer must never fail because the record did. A learner who gets a 500
    instead of a lesson because a logging table was locked has been failed
    by the part of the system that was supposed to be invisible.
    """
    text = _cl.redact(text)
    if not text or kind not in _cl.RECORD_KINDS:
        return
    try:
        db.add(LearnRecord(user_id=user.id, scope=scope,
                           school_id=_cl.school_id_of(scope), kind=kind,
                           text=text, subject=(subject or "")[:60],
                           level=(level or "")[:60]))
        db.commit()
        # Trimmed here rather than by a sweep, so the table cannot grow
        # unbounded between deploys on a site with no scheduled jobs.
        n = (db.query(func.count(LearnRecord.id))
               .filter(LearnRecord.user_id == user.id).scalar() or 0)
        if n > _cl.KEEP_PER_LEARNER:
            old = (db.query(LearnRecord.id)
                     .filter(LearnRecord.user_id == user.id)
                     .order_by(LearnRecord.created_at.asc())
                     .limit(n - _cl.KEEP_PER_LEARNER).all())
            (db.query(LearnRecord)
               .filter(LearnRecord.id.in_([r[0] for r in old]))
               .delete(synchronize_session=False))
            db.commit()
    except Exception as e:
        db.rollback()
        print(f"Learning record not stored: {type(e).__name__}: {e}")


class AskIn(BaseModel):
    question: str = Field(..., min_length=2, max_length=500)
    subject: str = Field("General", max_length=60)
    level: str = Field("School", max_length=60)


def _cached_json(db, row, what="lesson", need="steps"):
    """A cached row's payload, or None if it cannot be used.

    Reading a cache must not be able to fail. A row that will not parse, or
    that parses into something without the field the caller needs, is treated
    as though it had never been written: dropped, and reported as a miss.

    Deleting it matters. A row that raises on every read but stays in the
    table means the next request regenerates and pays for a model call again,
    which turns a display bug into a recurring cost.
    """
    if row is None:
        return None
    try:
        data = json.loads(row.lesson)
    except Exception as e:
        print(f"Cache row {getattr(row, 'qkey', '?')!r} will not parse "
              f"({type(e).__name__}) — dropping it and rebuilding")
        data = None
    else:
        if not isinstance(data, dict) or (need and not data.get(need)):
            print(f"Cache row {getattr(row, 'qkey', '?')!r} has no {need!r} "
                  f"— dropping it and rebuilding")
            data = None
    if data is None:
        try:
            db.delete(row)
            db.commit()
        except Exception:
            db.rollback()
        return None
    return data


def _norm_q(s: str) -> str:
    """Collapse a question to a stable cache key so trivial differences in
    spacing, case or punctuation all hit the same stored answer."""
    return _re.sub(r"\s+", " ", _re.sub(r"[^a-z0-9\s]", "", s.lower())).strip()


def _fallback_lesson(subject: str, level: str) -> dict:
    return {
        "title": "AI teacher not set up yet",
        "steps": [
            "Axle's ask-anything teacher needs an API key to think.",
            "The site owner adds a free GEMINI_API_KEY in the server settings.",
            "Once it is set, ask any question on any subject.",
            "Answers you get are saved, so asking again is instant and free.",
        ],
        "takeaway": "Everything else on Craxle works without this.",
    }


def _ask_prompt(question: str, subject: str, level: str) -> str:
    return (
        f"You are Axle, a warm, patient teacher in India explaining on a "
        f"blackboard. The subject is: {subject}. The learner's level is: "
        f"{level}. A learner asked: \"{question}\"\n\n"
        'NO GREETING, NO PREAMBLE. The first line is the first real thing you have to say. Never open with "Welcome", "Dear students", "Let us look at this together", "Great question" or any other pleasantry, and never spend a line restating the question back — the learner has it in front of them and the board only shows a few lines at a time, so a line that carries nothing is a line of the lesson thrown away. Begin with the substance and keep going.\n\nANSWER THE QUESTION THAT WAS ASKED. Read it closely enough to notice what it is really asking, then answer that. If it is a problem to solve, solve it and reach the actual answer — do not restate the setup, describe an approach, and stop. Work each step so the reader can follow the arithmetic or the argument, and finish. If the question has no clean answer, or the answer is that no solution exists, say so and show what rules the others out. Every claimed answer gets substituted back into the original problem and checked before you state it.\n\nINDIA FIRST, WHEN AN EXAMPLE IS NEEDED. Set examples here: rupees rather than dollars, Indian cities, Indian firms, the exams and boards people here actually sit, Indian regulations and Indian case law. Use a foreign example only when the subject genuinely is foreign — a US statute in a lesson on US law, a landmark experiment done where it was done. Never reach for another country\'s setting when a local one would serve.\n\n'
        f"Explain it the way a good teacher writes on the board: short lines, "
        f"one idea per line, language matched to the stated level, with a "
        f"small real-life Indian example where natural. Be accurate. If the "
        f"question is not about {subject}, still answer it helpfully. If it "
        f"asks for something unsafe or inappropriate for a student, gently "
        f"redirect to safe learning instead.\n\n"
        f"Respond with ONLY valid JSON, no markdown, no backticks, in exactly "
        f"this shape:\n"
        f'{{"title": "<topic in 2-6 words>", "steps": ["<line 1>", "<line 2>", '
        f'"... use as many short lines as the question needs: a few for a '
        f'simple question, more for a detailed one (up to about 25)"], '
        f'"takeaway": "<one sentence to remember>"}}'
    )


def _parse_lesson(text: str, question: str) -> dict:
    """Every provider returns plain text; turn it into a validated lesson."""
    clean = (text or "").replace("```json", "").replace("```", "").strip()
    try:
        les = json.loads(clean)
    except Exception:
        lines = [
            _re.sub(r"^[-*\d.\s]+", "", ln).strip()
            for ln in _re.split(r"\n+", clean) if ln.strip()
        ]
        les = {"title": question[:40], "steps": lines[:9], "takeaway": ""}
    if not isinstance(les.get("steps"), list) or not les["steps"]:
        raise ValueError("empty lesson")
    return {
        "title": str(les.get("title", question))[:120],
        "steps": [str(s)[:300] for s in les["steps"]][:40],
        # Text only. Drawings — flat or 3D — are the Pro board's, which is
        # where the room and the step structure to hang them on exists.
        "takeaway": str(les.get("takeaway", ""))[:300],
    }


def _upstream_ok(r, provider):
    """Raise a readable error carrying the provider's own message, so a bad
    key or a wrong model name shows up clearly instead of a generic failure."""
    if r.status_code >= 400:
        body = (r.text or "")[:300].replace("\n", " ")
        raise RuntimeError(f"{provider} HTTP {r.status_code}: {body}")


AI_DAILY_LIMIT = 50   # resume AI checks per user per day (admins exempt)

# ---- plans ---------------------------------------------------------------
# Prices in the smallest unit (paise / cents), which is what both gateways
# expect and avoids float rounding on money.
PLANS = {
    "free": {"name": "Free", "ai_total": 0, "kits_total": 0,
             "inr": None, "intl": None},
    # One price worldwide, charged in US dollars through Stripe — Indian cards
    # convert it themselves, the same way foreign cards used to convert the
    # rupee price. Kept as a single tier on purpose: two tiers make people stop
    # and compare instead of deciding. Amounts are in cents.
    "pro": {"name": "Pro", "ai_month": None, "kits_month": None,   # unlimited
            # The longer terms keep the same 10 / 20 / 25% discounts, and the
            # percentages on the plans page are computed from these numbers
            # rather than written next to them — so a price change can never
            # leave the page advertising a saving that is not real.
            "usd_month": 999,         # $9.99    —  $9.99/mo
            "usd_quarter": 2699,      # $26.99   —  $9.00/mo, 10% off
            "usd_half": 4799,         # $47.99   —  $8.00/mo, 20% off
            "usd_year": 8999},        # $89.99   —  $7.50/mo, 25% off
}
PAID_PLANS = ("pro",)

# The free view of the job board: only postings at least this old, and only
# this many of them. Being early is what wins an interview, so freshness is
# the thing Pro actually sells.
# The board is free. All of it, the day it is crawled.
#
# It used to be delayed a week and capped at fifty for free accounts,
# on the theory that being early is what Pro sells. It is not: the
# postings cost nothing to serve once crawled, and a job board that
# hides jobs has nothing to be judged on. What Pro sells is the AI that
# acts on a posting — apply kits, interview prep, the tutor — and a
# crawl run on demand rather than on the hour.
#
# Set either variable above zero to bring the old limits back.
FREE_JOB_DELAY_DAYS = int(env("FREE_JOB_DELAY_DAYS", "0") or 0)
FREE_JOB_CAP = int(env("FREE_JOB_CAP", "0") or 0)

# The billing periods on sale. `days` is the access granted on payment and runs
# a little past the term on purpose — a renewal that lands a day late must not
# lock someone out of the product they have paid for.
BILLING_PERIODS = {
    "month":   {"label": "Monthly",   "months": 1,  "interval": "month",
                "count": 1, "days": 32},
    "quarter": {"label": "3 months",  "months": 3,  "interval": "month",
                "count": 3, "days": 96},
    "half":    {"label": "6 months",  "months": 6,  "interval": "month",
                "count": 6, "days": 187},
    "year":    {"label": "12 months", "months": 12, "interval": "year",
                "count": 1, "days": 372},
}


def _period_from_span(started, expires):
    """Which period a subscriber is on, read back from the access they were
    granted. Used where the period was not recorded — old rows, and renewal
    invoices that carry no metadata."""
    if not started or not expires:
        return "month"
    days = (_aware(expires) - _aware(started)).days
    # Match the closest term rather than using thresholds, so adding a period
    # later does not silently reclassify existing subscribers.
    return min(BILLING_PERIODS,
               key=lambda k: abs(BILLING_PERIODS[k]["days"] - days))


def plan_of(user) -> str:
    """The plan actually in force, expiry included."""
    if getattr(user, "is_admin", False):
        return "pro"
    p = (user.plan or "free").lower()
    if p not in PAID_PLANS:
        return "free"
    exp = user.plan_expires
    if exp is not None and exp.tzinfo is None:
        exp = exp.replace(tzinfo=dt.timezone.utc)
    if exp is not None and exp < now():
        return "free"
    return p


def _ai_used_today(db, user):
    """How many billable AI checks this user has run today (cache hits free)."""
    day = now().strftime("%Y%m%d")
    row = db.query(Note).filter(Note.user_id == user.id, Note.k == f"aiq_{day}").first()
    try:
        return int(row.v) if row else 0
    except Exception:
        return 0


def _ai_used_total(db, user):
    """Lifetime billable AI checks — the free tier is a total, not a daily rate."""
    row = db.query(Note).filter(Note.user_id == user.id, Note.k == "aiq_total").first()
    try:
        return int(row.v) if row else 0
    except Exception:
        return 0


def _ai_used_month(db, user):
    row = db.query(Note).filter(
        Note.user_id == user.id, Note.k == f"aiq_m{now().strftime('%Y%m')}").first()
    try:
        return int(row.v) if row else 0
    except Exception:
        return 0


def ai_quota(db, user):
    """What this user may still use, and on what plan. Cache hits are free and
    never counted, so re-running the same check costs nobody anything."""
    plan = plan_of(user)
    if plan == "pro":
        return {"plan": plan, "limit": None, "used": 0, "left": None}

    used = _ai_used_total(db, user)
    lim = PLANS["free"]["ai_total"]
    applied = db.query(Note).filter(Note.user_id == user.id,
                                    Note.k == "trial_apply_job").first()
    return {"plan": "free", "limit": lim, "used": used,
            "left": max(0, lim - used), "period": "total",
            # so the page can say "1 free upload left" up front, instead of
            # only finding out at the paywall
            "trial": {
                "resume_upload_left": max(
                    0, FREE_TRIAL["resume_upload"]
                    - _trial_used(db, user, "resume_upload")),
                "match_left": max(0, FREE_TRIAL["match"]
                                  - _trial_used(db, user, "match")),
                "extension_left": max(0, FREE_TRIAL["extension"]
                                      - _trial_used(db, user, "extension")),
                # Applying is paid outright now, so there is nothing left to
                # report. Kept in the payload so the page does not have to
                # branch on the key being absent.
                "apply_left": 0,
                "apply_job_id": int(applied.v) if applied
                and str(applied.v or "").isdigit() else None,
            }}


def require_paid(user, feature="This"):
    """Paid features. Browsing job listings stays free — that is what brings
    people here and what search engines index. Everything that acts on a
    resume is part of the paid product."""
    if getattr(user, "is_admin", False):
        return
    if plan_of(user) == "free":
        raise HTTPException(402, f"{feature} is part of a paid plan. "
                                 "Browsing every live job stays free.")


# A free account gets one go at this, once, ever — not per month. The point is
# to let someone see their own resume scored and go through one real
# application before deciding, without giving away the product. The free
# application is handled separately by apply_gate, which tracks a job rather
# than a count.
# Set to 0: the free tier no longer includes a trial of the paid tools. Free
# means the training courses and a limited, delayed view of the job board —
# resume matching, the tracker, apply kits and the extension are all paid.
# The mechanism is left in place because turning a trial back on is a matter
# of changing a number here, and it is covered by tests.
# sql_explain is the only entry with an allowance. Running queries on the SQL
# board is free forever because it costs us nothing — it is a SQLite file in
# memory, not a model call. Only the written explanation of your own mistake
# is paid, and three of those are enough to see whether it is worth paying for.
FREE_TRIAL = {"resume_upload": 0, "match": 0, "extension": 0,
              # Running queries on the SQL board is free forever because it
              # costs us nothing — it is a SQLite file in memory, not a model
              # call. Only the written explanation is metered.
              "sql_explain": 3,
              # The scanner is the way in: three goes is enough to find out
              # whether it reads your handwriting and whether the answer is
              # any good, and not enough to be the product.
              "scan": 3,
              # The course generator gets none. It is the deep explanation —
              # the largest single generation on the site and the thing worth
              # paying for — so it sits with the smart board on the paid side
              # rather than being given away once. It had one free go, which
              # also meant a free account could reach the 3D scenes a course
              # carries; those are Pro, and now they are Pro by every route.
              "course": 0}


def _trial_used(db, user, key):
    row = db.query(Note).filter(Note.user_id == user.id,
                                Note.k == f"trial_{key}").first()
    try:
        return int(row.v) if row else 0
    except Exception:
        return 0


def require_paid_or_trial(db, user, key, feature, spent="free go"):
    """Like require_paid, but lets a free account through a fixed number of
    times. Does NOT consume the allowance — call _trial_consume after the
    work actually succeeded, so a failed upload doesn't burn someone's turn."""
    if getattr(user, "is_admin", False):
        return
    if plan_of(user) != "free":
        return
    limit = FREE_TRIAL.get(key, 0)
    if limit <= 0:
        # No allowance at all, so nothing was ever spent. Telling somebody
        # "you've used your one free course" when they never had one reads as
        # a billing bug, which is the worst thing a paywall can look like —
        # and it is what this said the moment the course allowance went to 0.
        return require_paid(user, feature)
    if _trial_used(db, user, key) >= limit:
        raise HTTPException(402, f"You've used your {spent}. {feature} is part "
                                 "of Pro — browsing every live job stays free.")


def _trial_consume(db, user, key):
    """Count one use against the free allowance. Paid accounts are untouched,
    so nothing has to be reset when someone subscribes."""
    if getattr(user, "is_admin", False) or plan_of(user) != "free":
        return
    k = f"trial_{key}"
    row = db.query(Note).filter(Note.user_id == user.id, Note.k == k).first()
    if row is None:
        row = Note(user_id=user.id, k=k, v="0")
        db.add(row)
    try:
        row.v = str(int(row.v or 0) + 1)
    except Exception:
        row.v = "1"
    db.commit()


def apply_gate(db, user, job_id):
    """Applying to a job. Paid — there is no longer a free application.

    Kept as its own function rather than folded into require_paid because the
    apply kit and marking a job applied are two calls for the same action, and
    a future allowance has to cover both or it strands people mid-application.
    """
    if getattr(user, "is_admin", False):
        return
    if plan_of(user) != "free":
        return
    raise HTTPException(402, "Applying to jobs is part of Pro. The training "
                             "courses stay free.")


def _ai_enforce_limit(db, user):
    if getattr(user, "is_admin", False):
        return
    # Deliberately no email-verification gate here either. Blocking a paying
    # customer behind a confirmation link is only safe if the mail reliably
    # arrives, and it does not yet.
    q = ai_quota(db, user)
    if q["limit"] is None:
        return
    if q["used"] >= q["limit"]:
        if q["plan"] == "free":
            raise HTTPException(
                402, f"You've used your {q['limit']} free AI requests. "
                     "Upgrade to keep generating apply kits and job matches — "
                     "browsing jobs and resume matching stay free.")
        raise HTTPException(
            402, f"You've used this month's {q['limit']} AI requests on Basic. "
                 "Upgrade to Pro for unlimited, or wait for next month.")
    # Also keep a per-day ceiling as an abuse brake, even on Pro.
    if _ai_used_today(db, user) >= AI_DAILY_LIMIT * 4:
        raise HTTPException(429, "That's a lot of requests in one day. "
                                 "Try again tomorrow.")


def _ai_bump(db, user):
    """Count one billable AI call against the day, the month and the lifetime
    total. Three counters because the free tier is a lifetime allowance, Basic
    is monthly, and the daily one is only an abuse brake."""
    if getattr(user, "is_admin", False):
        return
    for key in (f"aiq_{now().strftime('%Y%m%d')}",
                f"aiq_m{now().strftime('%Y%m')}",
                "aiq_total"):
        row = db.query(Note).filter(Note.user_id == user.id, Note.k == key).first()
        if row:
            try:
                row.v = str(int(row.v) + 1)
            except Exception:
                row.v = "1"
        else:
            db.add(Note(user_id=user.id, k=key, v="1"))
    db.commit()


def _ai_cache_key(prefix, *parts, scope=None):
    """A cache key, inside one pool.

    `scope` is keyword-only and defaults to the private side of the fence.
    A caller that forgets it gets an institution-shaped key that simply
    misses the public pool — which costs a model call. Defaulting the other
    way would have cost a learner's resume text landing in a row another
    institution can read, and those two mistakes are not the same size."""
    import hashlib
    h = hashlib.sha256("||".join(p or "" for p in parts).encode("utf-8", "ignore")).hexdigest()
    return _cl.key(scope or _cl.PUBLIC, prefix, h)[:500]


def _ai_cache_get(db, qkey):
    """Return a cached AI result (and count the hit), or None."""
    row = db.query(AskCache).filter(AskCache.qkey == qkey).first()
    if not row:
        return None
    row.hits = (row.hits or 0) + 1
    db.commit()
    try:
        return json.loads(row.lesson)
    except Exception:
        return None


def _ai_cache_put(db, qkey, result):
    try:
        if db.query(AskCache).filter(AskCache.qkey == qkey).first():
            return
        db.add(AskCache(qkey=qkey[:500], subject="resume", level="",
                        question="", lesson=json.dumps(result), hits=0))
        db.commit()
    except Exception:
        db.rollback()


class AIProvidersFailed(Exception):
    """Every provider was tried and every one failed, with the reasons.

    Carrying them all is the point. One provider's message describes one
    provider, and reporting only the last one told people about a service
    they had not configured while staying silent about the one they had.
    """

    def __init__(self, fails):
        self.fails = fails or []
        super().__init__("; ".join(f"{p}: {e}" for p, e in self.fails)[:400])


def _one_provider_reason(prov, e):
    """What went wrong at one provider, in that provider's own dialect."""
    # The class name as well as the message. Every httpx timeout stringifies
    # to "" — so reading only str(e) found nothing to match and fell through
    # to "could not be reached", which describes a network fault at the
    # provider rather than a deadline set on this side.
    m = (type(e).__name__ + " " + str(e)).lower()
    # Google first, because its rate-limit message is "You exceeded your
    # current quota, please check your plan and billing details" — which
    # contains both "quota" and "billing" while meaning neither. Gemini has no
    # out-of-credit state that presents this way; enabling billing there buys
    # a higher limit, it does not unblock a different error. So for Gemini,
    # 429 is always a rate limit.
    if prov == "gemini" and ("quota" in m or "429" in m
                             or "rate limit" in m
                             or "resource_exhausted" in m):
        return ("rate", "Gemini is over its request limit for now — the free "
                        "tier allows only a few calls a minute and a capped "
                        "number per day, and it resets")
    # Only these two are unambiguous. "billing" on its own is not.
    if "insufficient_quota" in m or "credit balance" in m:
        return ("credit", f"{prov} has no credit left — this will not clear "
                          f"by waiting")
    if ("not found" in m and "model" in m) or "is not supported" in m:
        return ("model", f"{prov} does not have the model it was asked for")
    if "api key" in m or "unauthor" in m or "401" in m or "403" in m:
        return ("key", f"the {prov} key was refused")
    if "quota" in m or "429" in m or "rate limit" in m or "resource_exhausted" in m:
        if prov == "gemini":
            return ("rate", "Gemini is over its request limit for now — the "
                            "free tier allows only a few per minute and a "
                            "capped number per day, and it resets")
        return ("rate", f"{prov} is rate-limiting requests for now")
    if "timeout" in m or "timed out" in m or "readtimeout" in m:
        return ("slow", f"{prov} did not answer within the time allowed — a "
                        f"long lesson can genuinely take a while")
    if "connecterror" in m or "connect" in m and "error" in m:
        return ("net", f"{prov} could not be reached from the server")
    if "no text" in m:
        return ("empty", f"{prov} returned nothing usable")
    return ("other", f"{prov} could not be reached")


def _ai_error_message(e):
    """Turn a raw upstream error into words that are true for the reader.

    This used to answer every rate limit with "the free AI limit has been
    reached". For somebody on Pro that is simply false — it is the model
    provider that is out, not their allowance — and it reads as a billing
    fault on their own account, which is the worst thing to be wrong about.

    Two upstream conditions arrive looking similar and need opposite advice.
    Being told to wait when the credit has run out means waiting forever.
    """
    if isinstance(e, AIProvidersFailed) and e.fails:
        reasons = [_one_provider_reason(p, x) for p, x in e.fails]
        body = ". ".join(r[1][0].upper() + r[1][1:] for r in reasons) + "."
        kinds = {r[0] for r in reasons}
        if "credit" in kinds or "key" in kinds or "model" in kinds:
            body += (" Nothing is wrong with your account — this is the "
                     "site's own AI configuration.")
        elif kinds <= {"rate", "slow", "empty", "other", "net"}:
            body += " Nothing has been used up on your account; try again "\
                    "shortly."
        return body

    s = str(e).lower()
    # No bare "402": any number containing it — a token count, a request id —
    # would match and tell somebody their credit had run out when it had not.
    # And no bare "exceeded your current quota": that is OpenAI's phrase for
    # billing and Google's for an ordinary rate limit, so on its own it means
    # nothing.
    dead = ("insufficient_quota", "credit balance", "payment required")
    if any(k in s for k in dead):
        return ("The AI provider's credit has run out, so this will not fix "
                "itself by waiting. Nothing is wrong with your account. If "
                "this is your site, top up the provider or set a second API "
                "key — Craxle falls back automatically to whichever one still "
                "works.")
    if ("not found" in s and "model" in s) or "is not supported" in s             or "unknown model" in s:
        return ("The AI model name in the settings does not exist for this "
                "API key. Nothing is wrong with your account. If this is your "
                "site, check /api/ai/models to see what the key can actually "
                "use and set GEMINI_MODEL or OPENAI_MODEL to one of them.")
    if "429" in s or "rate limit" in s or "tokens per minute" in s:
        return ("The AI provider is rate-limiting requests at the moment. "
                "This clears on its own, usually within a minute. Nothing has "
                "been used up on your account.")
    if "tokens per day" in s or "quota" in s:
        return ("The AI provider's daily allowance is spent and resets "
                "tomorrow. Nothing has been used up on your account.")
    return "The AI could not respond just now. Please try again in a moment."


def _providers_in_order():
    """Providers to try, in order: the configured one first, then any others
    that also have a key — so if one is rate-limited we fall back to the next."""
    order = [AI_PROVIDER] + [p for p in _PREFERRED if p != AI_PROVIDER]
    return [p for p in order if _KEYS.get(p)]


GEMINI_SAFE_MODEL = "gemini-flash-lite-latest"

# Only these two families never had thinking. Everything else — 2.5, 3, and
# every rolling alias, now and later — gets it switched off.
#
# This was a positive match on version digits, which is exactly wrong for a
# setting that is usually an alias: "gemini-flash-lite-latest" has no digits
# after "gemini-", so it fell through, thinking stayed on, and it quietly ate
# the output budget of the largest prompt in the product.
# Models that will not take thinkingConfig.
#
# The old ones because they predate it, and the "-latest" aliases because the
# probe matrix settled it directly: gemini-flash-lite-latest returns 400
# INVALID_ARGUMENT with thinkingConfig and 200 without it, every time. Google
# never says which argument is invalid, so that was worth measuring rather
# than reasoning about.
#
# The retry below still catches anything this misses. Listing the aliases here
# only saves a wasted 400 on the first call after each restart — small, but it
# was the difference between the configured provider working and the whole
# site quietly running on the fallback.
# Both branches are anchored: this is used with .match(), so an unanchored
# "-latest$" would never fire — it has to match from the start of the name.
_NO_THINKING = _re.compile(r"^gemini-(?:1\.|2\.0)|^gemini-.*-latest$")


def _gen_config(model, tokens, temperature, json_mode=False, no_think=False):
    """The generationConfig for one Gemini call."""
    gen = {"maxOutputTokens": tokens, "temperature": temperature}
    if json_mode:
        gen["responseMimeType"] = "application/json"
    if (not no_think and not _thinking_off["gemini"]
            and not _NO_THINKING.match(model or "")):
        gen["thinkingConfig"] = {"thinkingBudget": 0}
    return gen


# Once a model has rejected it, stop offering it for the life of the process.
_thinking_off = {"gemini": False}


def _rejects_thinking(e):
    """Did the model refuse the thinking parameter?

    Google does not say which argument was invalid — the whole message is
    "Request contains an invalid argument." So any 400 is treated as this,
    because thinkingConfig is the only optional field in the payload and
    losing the provider over it is far worse than one wasted retry.
    """
    m = str(e).lower()
    if "thinking" in m and ("not supported" in m or "invalid" in m
                            or "unknown" in m or "unexpected" in m):
        return True
    return "invalid_argument" in m or "invalid argument" in m or "400" in m


def _is_missing_model(e):
    """Did this fail because the model id is wrong, rather than transiently?"""
    m = str(e).lower()
    return (("not found" in m and "model" in m)
            or "is not supported" in m or "unknown model" in m
            or "does not exist" in m)


_gemini_fallback_warned = False


def _gemini_model(best=False):
    """The model to ask for, and the one to fall back to if it is not there."""
    want = GEMINI_MODEL_BEST if best else GEMINI_MODEL
    return want, (GEMINI_SAFE_MODEL if want != GEMINI_SAFE_MODEL else None)


async def _provider_generate(client, provider, prompt, max_tokens, json_mode=False,
                             best=False, _override=None, _no_think=False):
    """One raw generation call to a single provider. Raises on HTTP error."""
    if provider == "gemini":
        model = _override or (GEMINI_MODEL_BEST if best else GEMINI_MODEL)
        # 0.15, not 0.4. A lesson is a reference, not creative writing: at
        # 0.4 the same question produces a different derivation each time and
        # one of those variations is the one that invents a step. Lower is
        # duller, and gives more nearly the same answer twice.
        gen = _gen_config(model, max_tokens, 0.15, json_mode, _no_think)
        r = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={"x-goog-api-key": GEMINI_API_KEY, "content-type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": gen})
        _upstream_ok(r, "gemini")
        return "".join(p.get("text", "") for c in r.json().get("candidates", [])
                       for p in c.get("content", {}).get("parts", [])).strip()
    if provider == "groq":
        # 0.15, not 0.4. A lesson is not creative writing: at 0.4 the
        # same question gives a different derivation each time, and one
        # of those variations is the one that invents a step. Lower is
        # duller and more nearly the same answer twice, which is what a
        # reference is for.
        body = {"model": GROQ_MODEL, "max_tokens": max_tokens, "temperature": 0.15,
                "messages": [{"role": "user", "content": prompt}]}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        r = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "content-type": "application/json"},
            json=body)
        _upstream_ok(r, "groq")
        return r.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    if provider == "openai":
        # Same wire format as Groq — both speak the OpenAI chat API — but kept
        # as its own branch because the model names, the key and the failure
        # messages are all different, and merging them would mean a Groq
        # rate-limit error reported as an OpenAI one.
        body = {"model": OPENAI_MODEL, "max_tokens": max_tokens,
                "temperature": 0.15,
                "messages": [{"role": "user", "content": prompt}]}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        r = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}",
                     "content-type": "application/json"},
            json=body)
        _upstream_ok(r, "openai")
        return r.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    # claude / anthropic
    r = await client.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        json={"model": ANTHROPIC_MODEL, "max_tokens": max_tokens,
              "messages": [{"role": "user", "content": prompt}]})
    _upstream_ok(r, "claude")
    return "".join(b.get("text", "") for b in r.json().get("content", [])
                   if b.get("type") == "text").strip()


async def _provider_vision(client, provider, prompt, raw, mime, max_tokens,
                           _override=None):
    """One generation call that also carries an image.

    Kept apart from _provider_generate because the three wire formats disagree
    about images in a way they do not disagree about text, and folding them
    together would mean a branch per provider inside every other branch.

    Groq is absent on purpose: the configured Groq model is text-only, and a
    fallback that silently drops the image would answer a question nobody
    asked. Better to skip it and try the next provider that can actually see.
    """
    b64 = base64.b64encode(raw).decode()
    if provider == "gemini":
        gen = _gen_config(_override or GEMINI_MODEL, max_tokens, 0.15, True)
        r = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{_override or GEMINI_MODEL}:generateContent",
            headers={"x-goog-api-key": GEMINI_API_KEY,
                     "content-type": "application/json"},
            json={"contents": [{"parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": mime, "data": b64}}]}],
                "generationConfig": gen})
        _upstream_ok(r, "gemini")
        return "".join(p.get("text", "") for c in r.json().get("candidates", [])
                       for p in c.get("content", {}).get("parts", [])).strip()
    if provider == "openai":
        r = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}",
                     "content-type": "application/json"},
            json={"model": OPENAI_MODEL, "max_tokens": max_tokens,
                  "temperature": 0.15,
                  "response_format": {"type": "json_object"},
                  "messages": [{"role": "user", "content": [
                      {"type": "text", "text": prompt},
                      {"type": "image_url", "image_url": {
                          "url": f"data:{mime};base64,{b64}"}}]}]})
        _upstream_ok(r, "openai")
        return r.json().get("choices", [{}])[0].get(
            "message", {}).get("content", "").strip()
    if provider == "claude":
        r = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": ANTHROPIC_API_KEY,
                     "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": ANTHROPIC_MODEL, "max_tokens": max_tokens,
                  "messages": [{"role": "user", "content": [
                      {"type": "image", "source": {
                          "type": "base64", "media_type": mime, "data": b64}},
                      {"type": "text", "text": prompt}]}]})
        _upstream_ok(r, "claude")
        return "".join(b.get("text", "") for b in r.json().get("content", [])
                       if b.get("type") == "text").strip()
    raise RuntimeError(f"{provider} cannot read images")


VISION_PROVIDERS = ("gemini", "openai", "claude")


async def _ai_vision(prompt: str, raw: bytes, mime: str,
                     max_tokens: int = 2000) -> str:
    """Read an image, trying each provider that can, in the usual order."""
    import httpx
    order = [p for p in _providers_in_order() if p in VISION_PROVIDERS]
    if not order:
        raise RuntimeError("No AI provider that can read images is configured")
    last, fails = None, []
    import time as _t
    # A photo has to be uploaded before anything starts reading it, so the
    # floor is higher here than for text. The client allows 120 seconds for
    # an upload, so the chain stays under that.
    per_try = max(40.0, min(75.0, 30.0 + max_tokens / 90.0))
    _deadline = _t.monotonic() + 100
    async with httpx.AsyncClient(timeout=per_try) as client:
        for prov in order:
            if _t.monotonic() > _deadline:
                print(f"AI vision: out of time before trying {prov}")
                break
            try:
                try:
                    txt = await _provider_vision(client, prov, prompt, raw,
                                                 mime, max_tokens)
                except Exception as inner:
                    if prov == "gemini" and _rejects_thinking(inner) \
                            and not _thinking_off["gemini"]:
                        _thinking_off["gemini"] = True
                        print("AI: Gemini refused thinkingBudget on a vision "
                              "call; sending without it from now on.")
                        txt = await _provider_vision(client, prov, prompt, raw,
                                                     mime, max_tokens)
                        if txt:
                            return txt
                    _w, _safe = _gemini_model()
                    if not (prov == "gemini" and _safe
                            and _is_missing_model(inner)):
                        raise
                    txt = await _provider_vision(client, prov, prompt, raw,
                                                 mime, max_tokens,
                                                 _override=_safe)
                if txt:
                    return txt
                last = RuntimeError(f"{prov} returned no text")
                fails.append((prov, last))
            except Exception as e:
                print(f"Vision via {prov} failed: {type(e).__name__}: {e}")
                last = e
                fails.append((prov, e))
    if fails:
        raise AIProvidersFailed(fails)
    raise last or RuntimeError("No provider could read that image")


async def _ai_text(prompt: str, max_tokens: int = 1500, json_mode: bool = False,
                   best: bool = False) -> str:
    """Generate text, trying each available provider in turn. If one is rate-
    limited or errors, automatically fall back to the next configured provider."""
    import httpx
    providers = _providers_in_order()
    if not providers:
        raise RuntimeError("No AI provider key is configured")
    last, fails = None, []
    # Sized to the request rather than flat. A flat 25 seconds is generous for
    # a 1,500-token reply and nowhere near enough for a board lesson, which
    # sends a 15,000-character prompt and wants 8,000 tokens of JSON back —
    # so the board timed out on every single attempt while plain Ask, asking
    # for a fraction as much, looked perfectly healthy.
    #
    # Still bounded, and still under the browser's own 75-second deadline:
    # the client must be the one that gives up last, or it reports a hang for
    # a request the server already abandoned.
    import time as _t
    per_try = max(25.0, min(55.0, 18.0 + max_tokens / 110.0))
    _deadline = _t.monotonic() + 65
    async with httpx.AsyncClient(timeout=per_try) as client:
        for prov in providers:
            if _t.monotonic() > _deadline:
                print(f"AI: out of time before trying {prov}")
                break
            try:
                try:
                    txt = await _provider_generate(client, prov, prompt,
                                                   max_tokens, json_mode, best)
                except Exception as inner:
                    # A model that does not take thinkingConfig at all: send
                    # the same call again without it rather than losing the
                    # provider over one optional field.
                    if prov == "gemini" and _rejects_thinking(inner):
                        txt = await _provider_generate(
                            client, prov, prompt, max_tokens, json_mode, best,
                            _no_think=True)
                        if txt:
                            if not _thinking_off["gemini"]:
                                _thinking_off["gemini"] = True
                                print("AI: this Gemini model will not take "
                                      "thinkingBudget; sending without it "
                                      "from now on.")
                            return txt
                        raise
                    want, safe = _gemini_model(best)
                    if not (prov == "gemini" and safe
                            and _is_missing_model(inner)):
                        raise
                    global _gemini_fallback_warned
                    if not _gemini_fallback_warned:
                        _gemini_fallback_warned = True
                        print(f"AI CONFIG: GEMINI_MODEL is set to '{want}', "
                              f"which this key cannot use. Falling back to "
                              f"'{safe}' for every request. Fix the variable "
                              f"or check /api/ai/models.")
                    txt = await _provider_generate(client, prov, prompt,
                                                   max_tokens, json_mode, best,
                                                   _override=safe)
                if txt:
                    return txt
                last = RuntimeError(f"{prov} returned no text")
                fails.append((prov, last))
            except Exception as e:
                last = e
                fails.append((prov, e))
                print(f"AI provider '{prov}' failed, trying next: {type(e).__name__}: {e}")
                continue
    if fails:
        raise AIProvidersFailed(fails)
    raise last if last else RuntimeError("AI generation failed")


async def _call_model(question: str, subject: str, level: str) -> dict:
    """Build an Ask-Axle lesson, with automatic provider fallback."""
    prompt = _ask_prompt(question, subject, level)
    text = await _ai_text(prompt, 1500, json_mode=True)
    if not text:
        raise RuntimeError("AI returned no text")
    return _parse_lesson(text, question)


def _spoken(text: str) -> str:
    """A reply fit to be read aloud.

    Belt and braces: the prompt says no markdown, but a stray asterisk or
    hash read out as "asterisk" is the kind of thing that makes a voice
    sound broken, and it only takes one.
    """
    text = _re.sub(r"[*#`_]+", "", text or "")
    return _re.sub(r"\s{2,}", " ", text).strip()[:1200]


def _record_skills(db, user, skills):
    """Store what the learner just finished, and hand it back to the page.

    Idempotent on (user, label): a learner who works through the same idea
    twice has one skill, not two, and the count of how often it came up is
    worth more than a second row saying the same thing.

    Never raises. A skill that fails to store is a missing line on a resume;
    a skill that fails to store and takes the answer down with it is a tutor
    that stopped talking. The commit is guarded for exactly that reason.
    """
    out = []
    for sk in skills or []:
        label, tokens = sk["label"], ",".join(sk["tokens"])
        row = (db.query(SkillUnlock)
                 .filter(SkillUnlock.user_id == user.id,
                         SkillUnlock.label == label).first())
        if row:
            row.times = (row.times or 0) + 1
            row.last_at = now()
            # A later lesson may know words the earlier one did not.
            if tokens and not row.tokens:
                row.tokens = tokens
        else:
            db.add(SkillUnlock(user_id=user.id, label=label, tokens=tokens,
                               times=1))
        out.append({"skill": label, "tokens": list(sk["tokens"])})
    if out:
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"Skill unlock not stored: {type(e).__name__}: {e}")
    return out


class DobIn(BaseModel):
    dob: str = Field(default="", max_length=10)   # YYYY-MM-DD, or "" to clear


@app.post("/api/craxlearn/dob")
def craxlearn_set_dob(body: DobIn, user: User = Depends(current_user),
                      db: Session = Depends(get_db)):
    """Record a date of birth, which is what opens the job side.

    Not verification, and not described as it. This is a stated date, the
    same as every other site asks for, and it exists so that the default is
    closed rather than open — a learner who has not said is not shown to
    employers. A school that needs real proof of age has processes for that
    which no web form replaces.
    """
    raw = (body.dob or "").strip()
    if not raw:
        user.dob = None
        db.commit()
        return {"ok": True, "dob": "", "adult": False}
    try:
        got = dt.date.fromisoformat(raw)
    except ValueError:
        raise HTTPException(400, "Give the date as YYYY-MM-DD")
    today = dt.date.today()
    if got > today:
        raise HTTPException(400, "That date is in the future")
    if _cl.age_on(got, today) > 120:
        raise HTTPException(400, "Check that date — it is over 120 years ago")
    user.dob = got
    db.commit()
    return {"ok": True, "dob": got.isoformat(),
            "age": _cl.age_on(got, today), "adult": _cl.adult(got, today)}


@app.get("/api/craxlearn/me")
def craxlearn_me(user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    """Everything the institution app needs to paint itself once.

    A separate boot call from /api/auth/me on purpose. That one answers "who
    is signed in" for the whole of Craxle; this answers "what does this
    institution's app show", which is a different question with a different
    audience — and merging them would put a school's product entitlement
    into the payload every job seeker fetches on every page load.
    """
    scope = _scope_of(db, user)
    sid = _cl.school_id_of(scope)
    sc = db.get(School, sid) if sid else None
    ta = (db.query(TeacherAccess)
            .filter(TeacherAccess.user_id == user.id).first())
    gate = _learning_only(db, user)

    classes = (db.query(Klass)
                 .join(ClassMember, ClassMember.class_id == Klass.id)
                 .filter(ClassMember.user_id == user.id).all())
    if ta:
        classes = (classes + db.query(Klass).filter(
            Klass.teacher_id == user.id).all())

    dob = getattr(user, "dob", None)
    return {
        "product": _cl.NAME,
        "user": {"id": user.id, "name": user.name, "email": user.email},
        "role": ("admin" if user.is_admin
                 else (ta.role if ta else "student")),
        "institution": ({"id": sc.id, "name": sc.name, "city": sc.city or "",
                         "country": sc.country or "",
                         "product": sc.product or "craxlearn"} if sc else None),
        "scope": scope,
        # What this app will and will not show, and why — so the page can
        # say the reason rather than silently missing a menu item.
        "learning_only": gate["only"], "why": gate["why"],
        "message": gate["message"],
        "deployment_only": CRAXLEARN_ONLY,
        "adult": _cl.adult(dob, dt.date.today()),
        "dob": dob.isoformat() if dob else "",
        "classes": [{"id": k.id, "name": k.name,
                     "mine": k.teacher_id == user.id} for k in classes],
        "hidden_pages": list(_cl.JOB_PAGES) if gate["only"] else [],
    }


# --------------------------------------------------------------------------
# The school office: notices, attendance, fees
# --------------------------------------------------------------------------
# Written by the office. Read by everybody. A teacher cannot touch any of it
# and neither can a head teacher — see school_admin_user for why.

class NoticeIn(BaseModel):
    title: str = Field(min_length=2, max_length=240)
    body: str = Field(default="", max_length=8000)
    urgent: bool = False
    starts_on: str = Field(default="", max_length=20)
    ends_on: str = Field(default="", max_length=20)


def _notice_json(n):
    return {"id": n.id, "title": n.title, "body": n.body or "",
            "urgent": bool(n.urgent), "starts_on": n.starts_on or "",
            "ends_on": n.ends_on or "",
            "at": n.created_at.isoformat() if n.created_at else ""}


class StaffIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=5, max_length=255)
    role: str = Field(default="teacher", max_length=16)


@app.post("/api/head/staff")
def head_create_staff(body: StaffIn, user: User = Depends(head_user),
                      db: Session = Depends(get_db)):
    """The head teacher makes a profile for a member of staff.

    Returns a one-time password the head reads out or writes down. Not
    emailed: a school hiring in August has staff whose school address does
    not exist yet, and an invitation nobody receives is a member of staff
    who cannot work on their first morning.

    A head can create a school-office profile — attendance, fees, notices —
    but that does not give the head those powers. Somebody has to be able to
    appoint the office, and it is the head who knows who works there; what
    the head must not have is the ability to appoint themselves to it, so
    this refuses to grant a role to the account making the request.
    """
    role = body.role.strip().lower()
    if role not in SCHOOL_ROLES:
        raise HTTPException(400, f"Role must be one of: "
                                 f"{', '.join(SCHOOL_ROLES)}")
    t = teacher_row(user, db)
    school, sid = (t.school if t else ""), (t.school_id if t else 0)
    if not user.is_admin and not sid:
        raise HTTPException(403, "Your account is not attached to a school")

    email = body.email.lower().strip()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        if existing.id == user.id:
            raise HTTPException(
                400, "You cannot change your own role. Ask the platform "
                     "administrator.")
        _grant_teacher(db, existing, school, sid, role)
        # _grant_teacher never downgrades a head; a head setting somebody to
        # the office must actually move them, so it is set here explicitly.
        ta = (db.query(TeacherAccess)
                .filter(TeacherAccess.user_id == existing.id).first())
        if ta and role != "teacher":
            ta.role = role
            db.commit()
        return {"ok": True, "created": False, "user_id": existing.id,
                "name": existing.name, "role": role,
                "note": "That email already had an account, so it was given "
                        "this role at your school. Their existing password "
                        "still works."}

    temp = secrets.token_urlsafe(9)
    u = User(name=body.name.strip()[:120], email=email,
             password_hash=hash_pw(temp), is_active=True, email_verified=False)
    db.add(u)
    db.commit()
    db.refresh(u)
    _grant_teacher(db, u, school, sid, role)
    ta = db.query(TeacherAccess).filter(TeacherAccess.user_id == u.id).first()
    if ta:
        ta.role = role
        db.commit()
    return {"ok": True, "created": True, "user_id": u.id, "name": u.name,
            "email": u.email, "role": role, "temporary_password": temp,
            "note": "Give them this password. They should change it after "
                    "signing in — it is shown once and not stored readably."}


@app.get("/api/head/staff")
def head_list_staff(user: User = Depends(head_user),
                    db: Session = Depends(get_db)):
    """Who works here, and in what capacity."""
    t = teacher_row(user, db)
    sid = (t.school_id if t else 0)
    q = db.query(TeacherAccess, User).join(User, User.id == TeacherAccess.user_id)
    if not user.is_admin:
        q = q.filter(TeacherAccess.school_id == sid)
    return {"staff": [{"user_id": u.id, "name": u.name, "email": u.email,
                       "role": ta.role or "teacher",
                       "since": ta.created_at.isoformat() if ta.created_at else ""}
                      for ta, u in q.order_by(TeacherAccess.role).limit(500).all()],
            "roles": list(SCHOOL_ROLES)}


@app.delete("/api/head/staff/{uid}")
def head_remove_staff(uid: int, user: User = Depends(head_user),
                      db: Session = Depends(get_db)):
    """Take away a member of staff's access. The account itself is kept."""
    if uid == user.id:
        raise HTTPException(400, "You cannot remove your own access")
    ta = db.query(TeacherAccess).filter(TeacherAccess.user_id == uid).first()
    if not ta:
        raise HTTPException(404, "Not found")
    t = teacher_row(user, db)
    if not user.is_admin and ta.school_id != (t.school_id if t else -1):
        raise HTTPException(403, "They are not at your school")
    db.delete(ta)
    db.commit()
    return {"ok": True}


@app.post("/api/office/notice")
def add_notice(body: NoticeIn, user: User = Depends(school_admin_user),
               db: Session = Depends(get_db)):
    n = SchoolNotice(school_id=_school_of(user, db), author_id=user.id,
                     title=body.title.strip()[:240],
                     body=body.body.strip()[:8000], urgent=bool(body.urgent),
                     starts_on=body.starts_on.strip()[:20],
                     ends_on=body.ends_on.strip()[:20])
    db.add(n)
    db.commit()
    db.refresh(n)
    return {"ok": True, "notice": _notice_json(n)}


@app.delete("/api/office/notice/{nid}")
def drop_notice(nid: int, user: User = Depends(school_admin_user),
                db: Session = Depends(get_db)):
    n = db.get(SchoolNotice, nid)
    if not n:
        raise HTTPException(404, "Not found")
    if not user.is_admin and n.school_id != _school_of(user, db):
        raise HTTPException(403, "That notice belongs to another school")
    db.delete(n)
    db.commit()
    return {"ok": True}


class AttendanceIn(BaseModel):
    class_id: int
    day: str = Field(min_length=8, max_length=20)     # ISO date
    # {user_id: present}. The whole class in one request, because a register
    # is taken in one go and thirty requests is thirty chances to half-finish.
    present: dict = {}
    notes: dict = {}


@app.post("/api/office/attendance")
def mark_attendance(body: AttendanceIn,
                    user: User = Depends(school_admin_user),
                    db: Session = Depends(get_db)):
    """Take the register for one class on one day.

    Idempotent per (learner, day): running it again corrects the day rather
    than adding a second opinion of it. That is what makes "marked absent by
    mistake" a fixable thing, which is the single most common thing a parent
    rings a school about.
    """
    try:
        day = dt.date.fromisoformat(body.day.strip()).isoformat()
    except ValueError:
        raise HTTPException(400, "Give the day as YYYY-MM-DD")
    k = db.get(Klass, body.class_id)
    if not k:
        raise HTTPException(404, "No such class")
    sid = _school_of(user, db)
    if not user.is_admin and k.school_id != sid:
        raise HTTPException(403, "That class belongs to another school")

    members = {m.user_id for m in db.query(ClassMember)
               .filter(ClassMember.class_id == k.id).all()}
    done = 0
    for raw_uid, present in (body.present or {}).items():
        try:
            uid = int(raw_uid)
        except (TypeError, ValueError):
            continue
        # Only children who are actually in this class. A register that will
        # mark anybody whose id you send is a register that can be used to
        # write rows against a learner in another school.
        if uid not in members:
            continue
        row = (db.query(Attendance)
                 .filter(Attendance.user_id == uid, Attendance.day == day)
                 .first())
        if not row:
            row = Attendance(user_id=uid, day=day)
            db.add(row)
        row.school_id = k.school_id or 0
        row.class_id = k.id
        row.present = bool(present)
        row.note = str((body.notes or {}).get(raw_uid, ""))[:200]
        row.marked_by = user.id
        done += 1
    db.commit()
    return {"ok": True, "day": day, "marked": done, "in_class": len(members)}


@app.get("/api/office/attendance")
def read_attendance(class_id: int, day: str = "",
                    user: User = Depends(school_admin_user),
                    db: Session = Depends(get_db)):
    """The register for one class, on one day, with everybody's running total."""
    k = db.get(Klass, class_id)
    if not k:
        raise HTTPException(404, "No such class")
    if not user.is_admin and k.school_id != _school_of(user, db):
        raise HTTPException(403, "That class belongs to another school")
    day = (day or dt.date.today().isoformat()).strip()[:20]
    rows = (db.query(ClassMember, User)
              .join(User, User.id == ClassMember.user_id)
              .filter(ClassMember.class_id == class_id).all())
    today = {a.user_id: a for a in db.query(Attendance)
             .filter(Attendance.class_id == class_id,
                     Attendance.day == day).all()}
    out = []
    for _cm, u in rows:
        a = today.get(u.id)
        out.append({"user_id": u.id, "name": u.name,
                    "present": (None if a is None else bool(a.present)),
                    "note": (a.note if a else ""),
                    **_attendance_totals(db, u.id)})
    out.sort(key=lambda r: r["name"].lower())
    return {"class_id": class_id, "class_name": k.name, "day": day,
            "students": out}


def _attendance_totals(db, uid):
    """Days present, days recorded, and the percentage — computed, never stored.

    A stored percentage cannot be corrected, and correcting a wrongly marked
    day is the whole reason the rows exist.
    """
    total = (db.query(func.count(Attendance.id))
               .filter(Attendance.user_id == uid).scalar() or 0)
    present = (db.query(func.count(Attendance.id))
                 .filter(Attendance.user_id == uid,
                         Attendance.present == True).scalar() or 0)  # noqa: E712
    return {"days_present": present, "days_recorded": total,
            # None rather than 100 when nothing has been recorded. A learner
            # whose school has not started taking the register has not got
            # perfect attendance, and showing 100% is a number somebody will
            # quote back.
            "attendance_pct": (round(present * 100.0 / total, 1)
                               if total else None)}


class FeeIn(BaseModel):
    user_id: int
    title: str = Field(min_length=2, max_length=240)
    amount: int = 0                       # paise
    paid: int = 0                         # paise
    currency: str = Field(default="INR", max_length=8)
    due_on: str = Field(default="", max_length=20)
    note: str = Field(default="", max_length=2000)
    kind: str = Field(default="fee", max_length=12)     # fee | buy


def _fee_json(f):
    return {"id": f.id, "title": f.title, "note": f.note or "",
            "amount": f.amount or 0, "paid": f.paid or 0,
            "outstanding": max((f.amount or 0) - (f.paid or 0), 0),
            "currency": f.currency or "INR", "due_on": f.due_on or "",
            "kind": f.kind or "fee",
            "settled": (f.paid or 0) >= (f.amount or 0),
            "at": f.created_at.isoformat() if f.created_at else "",
            "paid_at": f.paid_at.isoformat() if f.paid_at else ""}


@app.post("/api/office/fee")
def set_fee(body: FeeIn, user: User = Depends(school_admin_user),
            db: Session = Depends(get_db)):
    """Record something a learner owes, or that they have paid.

    This takes no money and is not a payment page. It records what the
    office already knows, so a learner can see their balance without ringing
    up — and so nobody has to be told a number over the phone that neither
    of them can check afterwards.
    """
    target = db.get(User, body.user_id)
    if not target:
        raise HTTPException(404, "No such learner")
    sid = _school_of(user, db)
    if not user.is_admin:
        _same_school_or_403(db, target, sid)
    if body.amount < 0 or body.paid < 0:
        raise HTTPException(400, "Amounts cannot be negative")
    f = FeeItem(school_id=sid, user_id=target.id,
                title=body.title.strip()[:240], note=body.note.strip()[:2000],
                amount=int(body.amount), paid=int(body.paid),
                currency=(body.currency or "INR").upper()[:8],
                due_on=body.due_on.strip()[:20],
                kind="buy" if body.kind == "buy" else "fee",
                marked_by=user.id,
                paid_at=now() if body.paid >= body.amount > 0 else None)
    db.add(f)
    db.commit()
    db.refresh(f)
    return {"ok": True, "item": _fee_json(f)}


class FeePayIn(BaseModel):
    paid: int = 0                          # paise, the new total received


@app.post("/api/office/fee/{fid}/paid")
def mark_fee_paid(fid: int, body: FeePayIn,
                  user: User = Depends(school_admin_user),
                  db: Session = Depends(get_db)):
    f = db.get(FeeItem, fid)
    if not f:
        raise HTTPException(404, "Not found")
    if not user.is_admin and f.school_id != _school_of(user, db):
        raise HTTPException(403, "That belongs to another school")
    if body.paid < 0:
        raise HTTPException(400, "Amounts cannot be negative")
    f.paid = int(body.paid)
    f.marked_by = user.id
    f.paid_at = now() if f.paid >= (f.amount or 0) else None
    db.commit()
    return {"ok": True, "item": _fee_json(f)}


@app.delete("/api/office/fee/{fid}")
def drop_fee(fid: int, user: User = Depends(school_admin_user),
             db: Session = Depends(get_db)):
    f = db.get(FeeItem, fid)
    if not f:
        raise HTTPException(404, "Not found")
    if not user.is_admin and f.school_id != _school_of(user, db):
        raise HTTPException(403, "That belongs to another school")
    db.delete(f)
    db.commit()
    return {"ok": True}


def _same_school_or_403(db, target: User, school_id: int):
    """Is this learner one of ours? Membership through a class is the only link."""
    if not school_id:
        raise HTTPException(403, "Your account is not attached to a school")
    row = (db.query(Klass.school_id)
             .join(ClassMember, ClassMember.class_id == Klass.id)
             .filter(ClassMember.user_id == target.id,
                     Klass.school_id == school_id).first())
    if row is None:
        raise HTTPException(403, "That learner is not at your school")


@app.get("/api/office/learners")
def office_learners(user: User = Depends(school_admin_user),
                    db: Session = Depends(get_db)):
    """Everybody at this school, with their attendance and what they owe."""
    sid = _school_of(user, db)
    q = (db.query(User, Klass)
           .join(ClassMember, ClassMember.user_id == User.id)
           .join(Klass, Klass.id == ClassMember.class_id))
    if not user.is_admin:
        q = q.filter(Klass.school_id == sid)
    out = []
    for u, k in q.limit(2000).all():
        fees = db.query(FeeItem).filter(FeeItem.user_id == u.id).all()
        out.append({"user_id": u.id, "name": u.name,
                    "class_id": k.id, "class_name": k.name,
                    "owed": sum(max((f.amount or 0) - (f.paid or 0), 0)
                                for f in fees),
                    **_attendance_totals(db, u.id)})
    out.sort(key=lambda r: (r["class_name"].lower(), r["name"].lower()))
    return {"learners": out, "school_id": sid}


@app.get("/api/craxlearn/standing")
def my_standing(user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    """What a learner needs to know about themselves that is not schoolwork.

    Attendance, what is owed, what still has to be bought, and whatever the
    office has put up. One call, because it is one glance — a student
    checking four screens to find out whether they are in trouble checks
    none of them.

    Read-only for everybody. Nothing here can be changed from a learner's
    session, and the teacher's session cannot change it either.
    """
    sid = 0
    row = (db.query(Klass.school_id)
             .join(ClassMember, ClassMember.class_id == Klass.id)
             .filter(ClassMember.user_id == user.id).first())
    if row is not None:
        sid = row[0] or 0
    if not sid:
        t = teacher_row(user, db)
        sid = (t.school_id if t else 0) or 0

    fees = (db.query(FeeItem).filter(FeeItem.user_id == user.id)
              .order_by(FeeItem.created_at.desc()).limit(100).all())
    today = dt.date.today().isoformat()
    notices = []
    if sid:
        for n in (db.query(SchoolNotice)
                    .filter(SchoolNotice.school_id == sid)
                    .order_by(SchoolNotice.urgent.desc(),
                              SchoolNotice.created_at.desc()).limit(40).all()):
            # A notice with dates on it is only a notice between them. An
            # exam timetable from last term on a child's home screen is how
            # the whole panel stops being read.
            if n.starts_on and n.starts_on > today:
                continue
            if n.ends_on and n.ends_on < today:
                continue
            notices.append(_notice_json(n))

    return {
        **_attendance_totals(db, user.id),
        "fees": [_fee_json(f) for f in fees if (f.kind or "fee") == "fee"],
        "to_buy": [_fee_json(f) for f in fees if (f.kind or "fee") == "buy"],
        "owed": sum(max((f.amount or 0) - (f.paid or 0), 0) for f in fees),
        "currency": (fees[0].currency if fees else "INR"),
        "notices": notices,
        "school_id": sid,
    }


# --------------------------------------------------------------------------
# The register, and signing in with nothing but a class code
# --------------------------------------------------------------------------
class RosterIn(BaseModel):
    # One name per line, as a teacher would paste them off a register.
    names: str = Field(default="", max_length=8000)


@app.post("/api/teacher/class/{cid}/roster")
def set_roster(cid: int, body: RosterIn, user: User = Depends(teacher_user),
               db: Session = Depends(get_db)):
    """Type the register once, so nobody has to invent a password.

    Adds names; never removes one that a learner has already claimed. A
    teacher retyping the list with a typo fixed must not delete the account
    a child has work in — so a claimed name is left exactly as it is and
    only genuinely new names are added.
    """
    _own_class(db, cid, user)
    have = {r.name.strip().lower(): r for r in db.query(RosterName)
            .filter(RosterName.class_id == cid).all()}
    added = 0
    for line in (body.names or "").splitlines():
        # "Asha Rao, 8A-014" — the name, then the school's own id for them.
        # Comma-separated because that is how a register pastes out of a
        # spreadsheet, which is where every one of these lists comes from.
        parts = [p.strip() for p in line.split(",", 1)]
        name = " ".join(parts[0].split())[:80]
        code = (parts[1] if len(parts) > 1 else "")[:40]
        if len(name) < 2 or name.lower() in have:
            continue
        db.add(RosterName(class_id=cid, name=name, student_code=code))
        have[name.lower()] = True
        added += 1
    db.commit()
    return {"ok": True, "added": added, **_roster_json(db, cid)}


def _roster_json(db, cid):
    rows = (db.query(RosterName).filter(RosterName.class_id == cid)
              .order_by(RosterName.name.asc()).all())
    return {"roster": [{"id": r.id, "name": r.name,
                        "student_code": r.student_code or "",
                        "user_id": r.claimed_by or 0,
                        "claimed": bool(r.claimed_by)} for r in rows],
            "free": sum(1 for r in rows if not r.claimed_by),
            "total": len(rows)}


@app.get("/api/teacher/class/{cid}/roster")
def get_roster(cid: int, user: User = Depends(teacher_user),
               db: Session = Depends(get_db)):
    _own_class(db, cid, user)
    return _roster_json(db, cid)


@app.delete("/api/teacher/roster/{rid}")
def drop_roster_name(rid: int, user: User = Depends(teacher_user),
                     db: Session = Depends(get_db)):
    """Remove a name nobody has claimed. A claimed one is an account."""
    r = db.get(RosterName, rid)
    if not r:
        raise HTTPException(404, "Not found")
    _own_class(db, r.class_id, user)
    if r.claimed_by:
        raise HTTPException(
            400, "That name has been claimed and now has work behind it. "
                 "Remove the student from the class instead.")
    db.delete(r)
    db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------
# Which learners a member of staff may look at
# --------------------------------------------------------------------------
# One function answers it, and everything that shows a learner's detail goes
# through it. Written once on purpose: this is the rule that keeps a teacher
# out of another teacher's pupils' records, and two copies of it would drift
# until one of them let somebody through.
#
# The rule is the classroom, not the school. A teacher may teach in several
# classrooms and sees the learners in those; a head sees their whole school
# because they are responsible for it; the office sees their whole school
# because attendance and fees are theirs to keep. Nobody sees outside it.

def _my_class_ids(db, user) -> set:
    """Every classroom this member of staff may look into."""
    if user.is_admin:
        return None                     # None means "no restriction"
    t = teacher_row(user, db)
    if not t:
        return set()
    if t.role in ("head", "schooladmin"):
        return {k.id for k in db.query(Klass)
                .filter(Klass.school_id == t.school_id).all()} or {
                    k.id for k in db.query(Klass)
                    .filter(Klass.teacher_id == user.id).all()}
    # A subject teacher: the classrooms where they hold a subject, plus any
    # they were made the owning teacher of.
    ids = {s.class_id for s in db.query(SubjectSlot)
           .filter(SubjectSlot.teacher_id == user.id).all()}
    ids |= {k.id for k in db.query(Klass)
            .filter(Klass.teacher_id == user.id).all()}
    return ids


def _may_see_learner(db, user, learner_id) -> bool:
    """Is this learner in one of my classrooms?"""
    mine = _my_class_ids(db, user)
    if mine is None:
        return True
    if not mine:
        return False
    return db.query(ClassMember).filter(
        ClassMember.user_id == learner_id,
        ClassMember.class_id.in_(list(mine))).first() is not None


@app.get("/api/teacher/roll")
def teacher_roll(user: User = Depends(teacher_user),
                 db: Session = Depends(get_db)):
    """My classrooms and who is in them. Nothing outside them.

    A teacher's own first screen: the classes the head put them in, and the
    learners the head enrolled. Not a search over the school — a list of
    exactly what is theirs, which is both the useful thing and the safe one.
    """
    mine = _my_class_ids(db, user)
    q = db.query(Klass)
    if mine is not None:
        if not mine:
            return {"classes": [], "note": "You have not been given a class yet."}
        q = q.filter(Klass.id.in_(list(mine)))
    out = []
    for k in q.order_by(Klass.name.asc()).limit(100).all():
        codes = {r.claimed_by: r.student_code for r in db.query(RosterName)
                 .filter(RosterName.class_id == k.id).all() if r.claimed_by}
        learners = (db.query(User)
                      .join(ClassMember, ClassMember.user_id == User.id)
                      .filter(ClassMember.class_id == k.id)
                      .order_by(User.name.asc()).all())
        subs = sorted({s.subject for s in db.query(SubjectSlot)
                       .filter(SubjectSlot.class_id == k.id,
                               SubjectSlot.teacher_id == user.id).all()})
        out.append({
            "id": k.id, "name": k.name, "school": k.school or "",
            "join_code": k.join_code, "my_subjects": subs,
            "students": [{"user_id": u.id, "name": u.name,
                          "student_code": codes.get(u.id, ""),
                          **_attendance_totals(db, u.id)} for u in learners],
        })
    return {"classes": out}


@app.get("/api/teacher/student/{uid}")
def teacher_student(uid: int, user: User = Depends(teacher_user),
                    db: Session = Depends(get_db)):
    """One learner's progress — but only one of mine.

    What they have finished, what they searched for, what they scored, what
    they have handed in. A teacher asking after a child they teach is the
    ordinary case; the same request for a child in another teacher's class,
    or another school, is refused rather than filtered, so there is no
    version of this that returns a partial record and looks like an answer.
    """
    if not _may_see_learner(db, user, uid):
        raise HTTPException(
            403, "That learner is not in any of your classes.")
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "Not found")

    mine = _my_class_ids(db, user)
    classes = (db.query(Klass)
                 .join(ClassMember, ClassMember.class_id == Klass.id)
                 .filter(ClassMember.user_id == uid).all())
    if mine is not None:
        classes = [k for k in classes if k.id in mine]

    code = (db.query(RosterName.student_code)
              .filter(RosterName.claimed_by == uid).first())

    # What they searched and asked. Only their own records, and only from
    # inside this school's scope — the same rows the aggregate view counts,
    # named here because a teacher asking about one child they teach is a
    # different question from browsing the school.
    asked = (db.query(LearnRecord)
               .filter(LearnRecord.user_id == uid)
               .order_by(LearnRecord.created_at.desc()).limit(60).all())

    quizzes = (db.query(QuizResult).filter(QuizResult.user_id == uid)
                 .order_by(QuizResult.created_at.desc()).limit(60).all())

    done = (db.query(func.count(Progress.id))
              .filter(Progress.user_id == uid,
                      Progress.completed == True).scalar() or 0)  # noqa: E712

    subs = (db.query(Submission, Assignment)
              .join(Assignment, Assignment.id == Submission.assignment_id)
              .filter(Submission.user_id == uid)
              .order_by(Submission.updated_at.desc()).limit(60).all())
    if mine is not None:
        subs = [(s, a) for s, a in subs if a.class_id in mine]

    skills = (db.query(SkillUnlock).filter(SkillUnlock.user_id == uid)
                .order_by(SkillUnlock.last_at.desc()).limit(60).all())

    return {
        "student": {"user_id": u.id, "name": u.name,
                    "student_code": (code[0] if code else "") or "",
                    "class_login": (u.kind or "") == "classcode"},
        "classes": [{"id": k.id, "name": k.name} for k in classes],
        **_attendance_totals(db, uid),
        "lessons_completed": done,
        "learnt": [{"skill": s.label, "times": s.times or 1} for s in skills],
        "searched": [{"text": r.text, "kind": r.kind,
                      "subject": r.subject or "",
                      "at": r.created_at.isoformat() if r.created_at else ""}
                     for r in asked],
        "exams": [{"track": q.track_slug, "score": q.score, "total": q.total,
                   "passed": bool(q.passed),
                   "at": q.created_at.isoformat() if q.created_at else ""}
                  for q in quizzes],
        "handed_in": [{"assignment_id": a.id, "title": a.title,
                       "subject": a.subject or "",
                       "reviewed": bool(s.reviewed_at),
                       "feedback": s.feedback or "",
                       "at": s.updated_at.isoformat() if s.updated_at else ""}
                      for s, a in subs],
    }


@app.get("/api/teacher/student-by-code")
def teacher_student_by_code(code: str, user: User = Depends(teacher_user),
                            db: Session = Depends(get_db)):
    """Look a learner up by the school's own id for them.

    Searched only inside the classrooms this member of staff teaches. A code
    that exists elsewhere in the school comes back as "not found" and not as
    "not allowed" — telling a teacher that a code is real but off limits is
    still telling them something about a child they have no business with.
    """
    code = (code or "").strip()
    if len(code) < 1:
        raise HTTPException(400, "Type a student id")
    mine = _my_class_ids(db, user)
    q = db.query(RosterName).filter(
        func.upper(RosterName.student_code) == code.upper(),
        RosterName.claimed_by != 0)
    if mine is not None:
        if not mine:
            raise HTTPException(404, "No learner of yours has that id")
        q = q.filter(RosterName.class_id.in_(list(mine)))
    r = q.first()
    if not r:
        raise HTTPException(404, "No learner of yours has that id")
    return teacher_student(r.claimed_by, user, db)


class CodeIn(BaseModel):
    code: str = Field(min_length=3, max_length=16)


@app.post("/api/craxlearn/code")
def craxlearn_code(body: CodeIn, db: Session = Depends(get_db)):
    """Step one of signing in with nothing: which class is this, and who is free?

    Unauthenticated, because the whole point is that there is no account yet.
    It returns names and no other detail — no email, no school address, no
    count of anybody's work — so a guessed code leaks a class's first names
    and nothing else. That is the cost of a login a nine-year-old can do,
    and it is why the code is per-class and rotatable.
    """
    code = body.code.strip().upper()
    k = db.query(Klass).filter(func.upper(Klass.join_code) == code).first()
    if not k:
        raise HTTPException(404, "No class has that code")
    free = (db.query(RosterName)
              .filter(RosterName.class_id == k.id, RosterName.claimed_by == 0)
              .order_by(RosterName.name.asc()).all())
    return {"class_id": k.id, "class_name": k.name, "school": k.school or "",
            "names": [{"id": r.id, "name": r.name} for r in free],
            "roster_ready": bool(db.query(RosterName)
                                   .filter(RosterName.class_id == k.id)
                                   .first())}


class ClaimIn(BaseModel):
    code: str = Field(min_length=3, max_length=16)
    roster_id: int


@app.post("/api/craxlearn/claim")
def craxlearn_claim(claim: ClaimIn, response: Response,
                    db: Session = Depends(get_db)):
    """Step two: take that name, and be signed in.

    Creates a real User row so that everything downstream — submissions,
    the review queue, the activity record — works exactly as it does for
    anybody else. What it does not create is a way in from anywhere except
    this class code: the email is synthetic and unroutable, and the password
    hash is random and known to nobody, so there is no credential to phish,
    reuse or leak.

    kind="classcode" is what closes the job half permanently for this
    account. There is no adult behind it who agreed to anything, and no
    date of birth that could ever open it.
    """
    code = claim.code.strip().upper()
    k = db.query(Klass).filter(func.upper(Klass.join_code) == code).first()
    if not k:
        raise HTTPException(404, "No class has that code")
    r = db.get(RosterName, claim.roster_id)
    if not r or r.class_id != k.id:
        raise HTTPException(404, "That name is not on this class register")
    if r.claimed_by:
        raise HTTPException(409, "Somebody has already taken that name. "
                                 "Ask your teacher.")

    u = User(name=r.name[:120],
             # Synthetic and unroutable by design: nothing is ever sent
             # here, and it cannot collide with a real address.
             email=f"roster{r.id}.{secrets.token_hex(4)}@classcode.invalid",
             password_hash=hash_pw(secrets.token_urlsafe(24)),
             kind="classcode", is_active=True, email_verified=False)
    db.add(u)
    db.commit()
    db.refresh(u)

    r.claimed_by = u.id
    r.claimed_at = now()
    db.add(ClassMember(class_id=k.id, user_id=u.id))
    db.commit()

    set_session(response, u, db)
    return {"ok": True, "name": u.name, "class_name": k.name,
            "school": k.school or ""}


# --------------------------------------------------------------------------
# Reference material a class can read
# --------------------------------------------------------------------------
MATERIAL_MAX = 12_000_000          # 12 MB, which is a slide deck, not a film
MATERIAL_MIMES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/vnd.ms-powerpoint": "ppt",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "doc",
    "text/plain": "txt",
    "image/png": "png", "image/jpeg": "jpg", "image/webp": "webp",
}


def _material_json(m, with_url=True):
    d = {"id": m.id, "title": m.title, "note": m.note or "",
         "subject": m.subject or "", "kind": "link" if m.url else "file",
         "file_name": m.file_name or "", "size": m.size or 0,
         "mime": m.mime or "",
         "at": m.created_at.isoformat() if m.created_at else ""}
    if with_url and m.url:
        d["url"] = m.url
    return d


class LinkIn(BaseModel):
    title: str = Field(min_length=2, max_length=240)
    url: str = Field(min_length=4, max_length=2000)
    note: str = Field(default="", max_length=2000)
    subject: str = Field(default="", max_length=80)


@app.post("/api/teacher/class/{cid}/material/link")
def add_material_link(cid: int, body: LinkIn,
                      user: User = Depends(teacher_user),
                      db: Session = Depends(get_db)):
    """Put a reference link in front of a class."""
    _own_class(db, cid, user)
    url = body.url.strip()
    if not url.lower().startswith(("http://", "https://")):
        # A link that is not a link opens nothing and is reported by the
        # student as "it does not work", which costs a lesson to diagnose.
        raise HTTPException(400, "The link must start with http:// or https://")
    m = Material(class_id=cid, teacher_id=user.id,
                 subject=body.subject.strip()[:80],
                 title=body.title.strip()[:240], url=url[:2000],
                 note=body.note.strip()[:2000])
    db.add(m)
    db.commit()
    db.refresh(m)
    return {"ok": True, "material": _material_json(m)}


@app.post("/api/teacher/class/{cid}/material/file")
async def add_material_file(cid: int, file: UploadFile = File(...),
                            title: str = Form(default=""),
                            note: str = Form(default=""),
                            subject: str = Form(default=""),
                            user: User = Depends(teacher_user),
                            db: Session = Depends(get_db)):
    """Upload a PDF, a slide deck or a document for one class.

    Stored in the row rather than on disk: the container's filesystem does
    not survive a deploy, and a study pack that vanishes every time the site
    ships is worse than no study pack.
    """
    _own_class(db, cid, user)
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "That file is empty")
    if len(raw) > MATERIAL_MAX:
        raise HTTPException(
            400, f"That file is {len(raw) // 1_000_000} MB. The limit is "
                 f"{MATERIAL_MAX // 1_000_000} MB — split it, or link to it "
                 f"instead.")
    mime = (file.content_type or "").lower().split(";")[0].strip()
    if mime not in MATERIAL_MIMES:
        raise HTTPException(
            400, "Upload a PDF, a PowerPoint, a Word document, a text file "
                 "or an image.")
    m = Material(class_id=cid, teacher_id=user.id,
                 subject=(subject or "").strip()[:80],
                 title=((title or "").strip()
                        or (file.filename or "Material"))[:240],
                 note=(note or "").strip()[:2000],
                 file_data=base64.b64encode(raw).decode(),
                 file_name=(file.filename or "material")[:160],
                 mime=mime, size=len(raw))
    db.add(m)
    db.commit()
    db.refresh(m)
    return {"ok": True, "material": _material_json(m)}


@app.get("/api/class/{cid}/materials")
def class_materials(cid: int, user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    """Everything the class has been given to read.

    Open to the class and to its teachers, and to nobody else — the same
    membership test the assignments use, because material is exactly as
    private as the work that references it.
    """
    _in_class_or_teaching(db, cid, user)
    rows = (db.query(Material).filter(Material.class_id == cid)
              .order_by(Material.created_at.desc()).limit(200).all())
    return {"materials": [_material_json(m) for m in rows]}


@app.get("/api/material/{mid}/file")
def material_file(mid: int, user: User = Depends(current_user),
                  db: Session = Depends(get_db)):
    """Download one file, if you are in the class it belongs to."""
    m = db.get(Material, mid)
    if not m or not m.file_data:
        raise HTTPException(404, "Not found")
    _in_class_or_teaching(db, m.class_id, user)
    try:
        raw = base64.b64decode(m.file_data)
    except Exception:
        raise HTTPException(500, "That file is stored damaged")
    return Response(
        content=raw, media_type=m.mime or "application/octet-stream",
        headers={"Content-Disposition":
                 f'inline; filename="{(m.file_name or "material")[:80]}"'})


@app.delete("/api/teacher/material/{mid}")
def drop_material(mid: int, user: User = Depends(teacher_user),
                  db: Session = Depends(get_db)):
    m = db.get(Material, mid)
    if not m:
        raise HTTPException(404, "Not found")
    _own_class(db, m.class_id, user)
    db.delete(m)
    db.commit()
    return {"ok": True}


def _in_class_or_teaching(db, cid, user):
    """The one membership test both materials endpoints use.

    Written once because two copies of an access check drift, and the half
    that drifts is the one that lets the wrong person in.
    """
    if user.is_admin:
        return
    member = (db.query(ClassMember)
                .filter(ClassMember.class_id == cid,
                        ClassMember.user_id == user.id).first())
    if member:
        return
    k = db.get(Klass, cid)
    if k and k.teacher_id == user.id:
        return
    if db.query(SubjectSlot).filter(SubjectSlot.class_id == cid,
                                    SubjectSlot.teacher_id == user.id).first():
        return
    t = teacher_row(user, db)
    if t and t.role == "head" and k and t.school_id == k.school_id:
        return
    raise HTTPException(403, "Not in this class")


class BoardAssignIn(BaseModel):
    class_id: int
    topic: str = Field(min_length=2, max_length=200)
    title: str = Field(default="", max_length=240)
    subject: str = Field(default="", max_length=80)
    due_date: str = Field(default="", max_length=20)
    # The lesson as the board built it, so the assignment carries the
    # teaching and not only the instruction. Sent back rather than rebuilt
    # here: the teacher is looking at a specific lesson on the screen and
    # that is the one the class must get, not whatever the board would
    # produce if asked the same question again tomorrow.
    lesson: dict = {}
    task: str = Field(default="", max_length=4000)


def _lesson_to_body(lesson, task):
    """A board lesson as the text of an assignment.

    Flattened to text rather than stored as JSON because that is what
    `Assignment.body` is, what the existing student view renders, and what a
    teacher can edit afterwards. A structured copy would need a renderer on
    both sides and would stop the teacher fixing a line before setting it.
    """
    out = []
    if task:
        out.append(task.strip())
        out.append("")
    for i, st in enumerate(lesson.get("steps") or [], 1):
        text = st.get("t", "") if isinstance(st, dict) else str(st)
        if not text:
            continue
        out.append(f"{i}. {text.strip()}")
        if isinstance(st, dict) and st.get("code"):
            where = st.get("where") or ""
            out.append(f"   [{where}]" if where else "")
            out.append("   " + "\n   ".join(
                str(st["code"]).splitlines()[:20]))
        out.append("")
    if lesson.get("takeaway"):
        out.append(f"Remember: {lesson['takeaway']}")
    return "\n".join(out).strip()[:20000]


@app.post("/api/craxlearn/board/assign")
def craxlearn_board_assign(body: BoardAssignIn,
                           user: User = Depends(teacher_user),
                           db: Session = Depends(get_db)):
    """Set what is on the board as an assignment for one class.

    This is the whole point of teaching on a board that is part of the
    platform: the lesson the class just watched becomes the work they take
    away, without anybody retyping it. It appears in the students' own view
    and in the teacher's the moment it is created — there is nothing to
    publish, because an assignment nobody can see is not a draft, it is a
    mistake waiting to be noticed on the due date.

    Deliberately the same Assignment row that a typed assignment creates.
    A second kind of assignment would mean a second submission flow, a
    second review screen and two ways for a student to be marked, which is
    how a classroom product becomes unusable.
    """
    _own_class(db, body.class_id, user)

    subject = body.subject.strip()[:80]
    # A subject teacher is locked to the subject they hold in this class,
    # the same as when they type one by hand. The board does not become a
    # way round that.
    allowed = _my_subjects(db, body.class_id, user)
    if allowed is not None:
        if not allowed:
            raise HTTPException(403, "You have no subject in this class yet")
        if subject not in allowed:
            if not subject and len(allowed) == 1:
                subject = next(iter(allowed))
            else:
                raise HTTPException(
                    403, "You can only set assignments for: "
                         + ", ".join(sorted(allowed)))

    topic = _cl.redact(body.topic)[:200]
    text = _lesson_to_body(body.lesson if isinstance(body.lesson, dict) else {},
                           body.task)
    if not text:
        raise HTTPException(400, "There is no lesson on the board to set")

    a = Assignment(class_id=body.class_id, teacher_id=user.id, kind="task",
                   subject=subject,
                   title=(body.title.strip() or topic)[:240],
                   body=text, board_topic=topic,
                   due_date=body.due_date.strip()[:20])
    db.add(a)
    db.commit()
    db.refresh(a)

    n = (db.query(func.count(ClassMember.id))
           .filter(ClassMember.class_id == body.class_id).scalar() or 0)
    return {"ok": True, "assignment": _asg_json(a), "students": n}


class ReviewIn(BaseModel):
    feedback: str = Field(default="", max_length=4000)


@app.post("/api/teacher/submission/{aid}/{uid}/review")
def review_submission(aid: int, uid: int, body: ReviewIn,
                      user: User = Depends(teacher_user),
                      db: Session = Depends(get_db)):
    """Mark one student's work as reviewed, with or without a comment.

    Marking it with nothing to say is allowed and is not a gap: "seen, fine"
    is a real outcome and the alternative is a teacher typing "good" forty
    times to clear a list.
    """
    a = db.get(Assignment, aid)
    if not a:
        raise HTTPException(404, "Not found")
    _own_class(db, a.class_id, user)
    sub = (db.query(Submission)
             .filter(Submission.assignment_id == aid,
                     Submission.user_id == uid).first())
    if not sub:
        raise HTTPException(404, "That student has not submitted yet")
    # `updated_at` carries `onupdate=now`, so ANY write to this row moves it
    # — including this one. Two things break if it is left to:
    #
    # 1. The student's "handed in at" jumps to the moment the teacher marked
    #    it, which is not when they handed it in and is visible to them.
    # 2. "Waiting again" is computed from updated_at > reviewed_at, and the
    #    review's own bump lands after reviewed_at — so every piece of work
    #    reappeared in the queue the instant it was marked.
    #
    # Assigning the old value explicitly wins over onupdate, which keeps
    # both meanings intact: updated_at is when the STUDENT last wrote.
    # Assigning the SAME value back is not a change, so SQLAlchemy leaves
    # the column out of the UPDATE and `onupdate` fills it in anyway — which
    # is exactly the bug this is here to stop, wearing the fix's clothes.
    # flag_modified forces it into the SET clause, and a column present
    # there is not touched by onupdate.
    keep = sub.updated_at
    sub.feedback = body.feedback.strip()[:4000]
    sub.reviewed_at = now()
    sub.reviewed_by = user.id
    if keep is not None:
        sub.updated_at = keep
        flag_modified(sub, "updated_at")
    db.commit()
    return {"ok": True, "reviewed_at": sub.reviewed_at.isoformat()}


@app.get("/api/teacher/inbox")
def teacher_inbox(user: User = Depends(teacher_user),
                  db: Session = Depends(get_db)):
    """Every piece of work waiting for this teacher, across every class.

    The thing that makes "review it anywhere" true. Without it a teacher
    walks class, then assignment, then submissions, three taps deep, once
    per class, to find out whether anything arrived — which on a phone
    between lessons means they do not look.

    Scoped by the same rule as everywhere else: a head teacher sees their
    school's classes, a subject teacher sees the classes where they hold a
    subject. Nothing here can reach another school.
    """
    head = is_head(user, db)
    t = teacher_row(user, db)
    if head:
        sid = t.school_id if t else 0
        q = db.query(Klass)
        classes = (q.filter(Klass.school_id == sid) if sid
                   else q.filter(Klass.teacher_id == user.id)).all()
    else:
        ids = {sl.class_id for sl in db.query(SubjectSlot)
               .filter(SubjectSlot.teacher_id == user.id).all()}
        classes = (db.query(Klass).filter(Klass.id.in_(ids)).all()
                   if ids else [])
    by_class = {k.id: k for k in classes}
    if not by_class:
        return {"waiting": [], "classes": 0, "total": 0}

    rows = (db.query(Submission, Assignment, User)
              .join(Assignment, Assignment.id == Submission.assignment_id)
              .join(User, User.id == Submission.user_id)
              .filter(Assignment.class_id.in_(list(by_class)))
              .order_by(Submission.updated_at.desc()).limit(300).all())

    waiting, reviewed = [], 0
    for sub, a, student in rows:
        # Reviewed, then edited again by the student, is waiting once more.
        # A teacher who has read version one has not read version two, and
        # treating it as done is how a resubmission disappears.
        fresh = (sub.reviewed_at is not None and sub.updated_at is not None
                 and sub.updated_at > sub.reviewed_at)
        if sub.reviewed_at is not None and not fresh:
            reviewed += 1
            continue
        waiting.append({
            "assignment_id": a.id, "title": a.title,
            "subject": a.subject or "",
            "class_id": a.class_id,
            "class_name": by_class[a.class_id].name,
            "student_id": student.id, "student": student.name,
            "resubmitted": fresh,
            "at": sub.updated_at.isoformat() if sub.updated_at else "",
        })
    return {"waiting": waiting, "classes": len(by_class),
            "total": len(waiting), "reviewed": reviewed}


async def _resolve_structure(client, name):
    """A real, measured 3D structure for a name — or nothing.

    The same sources, in the same order, as a board lesson uses, and for the
    same reason: most specific first, and nothing invented at any step. A
    name with nothing measured behind it returns nothing, which is the
    honest answer and the one that stops a classroom being shown a plausible
    arrangement of spheres captioned with a real compound's name.

    Factored out of _offer_scene so the board and this share one path. Two
    copies would drift, and the copy that drifted would be the one drawing
    the picture nobody checked.
    """
    name = (name or "").strip()
    if not name:
        return None

    got = _lattice.clean(name)
    if got:
        return _scene.clean(dict(got, kind="lattice", caption=name.title(),
                                 a=2.0, a_angstrom=got["a"], repeat=2))
    got = _layers.clean(name)
    if got:
        return _scene.clean(dict(got, kind="layers", caption=name.title()))
    got = _orbits.clean(name)
    if got:
        return _scene.clean(dict(got, kind="orbit", caption=name.title()))

    try:
        got = await _molecule.find(client, name)
    except Exception:
        got = {}
    if got and 2 <= len(got.get("atoms") or []) <= _scene.MAX_ATOMS:
        formula = got.get("formula") or ""
        return _scene.clean({
            "kind": "molecule",
            "caption": name.title() + (" - " + formula if formula else ""),
            "atoms": [{"el": a["el"], "x": a["x"], "y": a["y"], "z": a["z"]}
                      for a in got["atoms"]],
            "bonds": [list(b) for b in got["bonds"]],
        })

    if _protein.canonical(name):
        try:
            got = await _protein.find(client, name)
        except Exception:
            got = {}
        if got:
            return _scene.clean(dict(got, kind="protein",
                                     caption=(got.get("title")
                                              or name.title())[:110]))
    return None


@app.get("/api/craxlearn/structure")
async def craxlearn_structure(name: str, user: User = Depends(current_user)):
    """Put a real structure on the board, for anything we actually have one of.

    Free — every source behind it is either a table in this repository or a
    public database, and none of it is a model call. So a class can turn
    twenty things around in a lesson and it costs what one does.
    """
    name = _cl.redact(name)[:120]
    if len(name) < 2:
        raise HTTPException(400, "Name the thing you want to see")
    async with httpx.AsyncClient(follow_redirects=True, timeout=12) as c:
        scene = await _resolve_structure(c, name)
    if not scene:
        # Named, and honestly answered. The alternative is a made-up
        # arrangement of spheres with a real compound's name under it.
        raise HTTPException(
            404, f"There is no measured structure here for {name!r}. We only "
                 f"show ones taken from PubChem, the Protein Data Bank or a "
                 f"published table — never a drawing of what it might be.")
    return {"name": name, "scene": scene}


@app.get("/api/craxlearn/search")
async def craxlearn_search(q: str, user: User = Depends(current_user)):
    """Search the open sources for something to show the room.

    A photograph where one exists, a measured structure where one exists,
    and the licence beside each. Nothing here is generated: it is a search
    over the same public catalogues listed at /api/craxlearn/sources, which
    is why the result can carry a credit line that means something.
    """
    q = _cl.redact(q)[:120]
    if len(q) < 2:
        raise HTTPException(400, "Type something to look for")
    async with httpx.AsyncClient(follow_redirects=True, timeout=12) as c:
        try:
            photo = await _images.find(c, q)
        except Exception as e:
            print(f"Source search picture failed: {type(e).__name__}: {e}")
            photo = {}
        try:
            scene = await _resolve_structure(c, q)
        except Exception as e:
            print(f"Source search structure failed: {type(e).__name__}: {e}")
            scene = None
    return {"query": q, "photo": photo or None, "scene": scene,
            "found": bool(photo or scene),
            "sources": [s["name"] for s in _cl.sourcing()]}


# Checked once per process. PhET's catalogue does not change during a
# lesson, and asking them twenty times on every page load would be rude to
# a free service a school depends on.
_PHET_CHECKED = {}


@app.get("/api/craxlearn/phet")
async def craxlearn_phet(subject: str = "", user: User = Depends(current_user)):
    """PhET simulations a class can drive, and only ones that really answer.

    Every candidate is fetched from PhET before it is offered. An id this
    codebase has wrong simply never appears — which is the only honest way
    to ship a list of external URLs into a classroom, where the cost of a
    wrong one is a 404 on the board with thirty people watching.

    Verified once per process and remembered. If PhET cannot be reached at
    all, the list comes back empty with a reason rather than a wall of
    frames that will not load.
    """
    want = _cl.phet_candidates(subject)
    todo = [s for s in want if s["id"] not in _PHET_CHECKED]

    if todo:
        async with httpx.AsyncClient(follow_redirects=True, timeout=8) as c:
            async def look(sim):
                try:
                    # HEAD first: it is the cheap question, and PhET answers
                    # it. Some CDNs do not, so a 405 falls back to a ranged
                    # GET rather than being read as "missing".
                    r = await c.head(sim["url"])
                    if r.status_code == 405:
                        r = await c.get(sim["url"],
                                        headers={"Range": "bytes=0-256"})
                    return sim["id"], r.status_code < 400
                except Exception:
                    return sim["id"], None      # unreachable, not absent
            for sim_id, ok in await asyncio.gather(*[look(s) for s in todo]):
                if ok is not None:
                    _PHET_CHECKED[sim_id] = ok

    live = [s for s in want if _PHET_CHECKED.get(s["id"])]
    unknown = [s["id"] for s in want if s["id"] not in _PHET_CHECKED]
    return {
        "sims": live,
        "subjects": sorted({s["subject"] for s in _cl.phet_candidates()}),
        "licence": "CC BY 4.0 — University of Colorado Boulder",
        "note": ("" if live else
                 "PhET could not be reached from this server, so nothing is "
                 "offered rather than a list of frames that will not load."
                 if unknown else
                 "None of the simulations in this list answered."),
        "unverified": len(unknown),
    }


class CalcIn(BaseModel):
    expression: str = Field(min_length=1, max_length=300)


@app.post("/api/craxlearn/calc")
def craxlearn_calc(body: CalcIn, user: User = Depends(current_user)):
    """A calculator, worked by the same evaluator that checks the lessons.

    Not eval, and not a model. `maths.evaluate` parses to a syntax tree and
    walks it against an allowlist — numbers, arithmetic and a short list of
    functions — so an expression typed on a classroom board by whoever is
    standing at it can contain only arithmetic. That matters more here than
    anywhere else in the product: this is the one input box in a room full
    of teenagers who have just been taught what a sandbox is.

    Signed in, because it is a classroom tool and not a free API to point a
    load generator at.
    """
    expr = body.expression.strip()
    got = _maths.evaluate(expr, {})
    if got is None:
        raise HTTPException(
            400, "That is not arithmetic this can work out. Numbers, "
                 "+ - * / ^, brackets, and sqrt, log, sin, cos, tan.")
    # Trailing zeros off a float that is really an integer: a calculator
    # that answers 12.0 to "6*2" reads as broken to the room.
    if isinstance(got, float) and got.is_integer() and abs(got) < 1e15:
        shown = str(int(got))
    else:
        shown = f"{got:.10g}"
    return {"expression": expr, "result": shown, "value": got}


@app.get("/api/craxlearn/sources")
def craxlearn_sources():
    """Where the answers come from, with licences. Open to anybody.

    Unauthenticated on purpose. "Where does your content come from" is the
    first question an institution asks and it is usually asked before anyone
    has an account — by a procurement officer, a head of department, a
    parent. Making them sign up to read the answer is a bad answer.
    """
    return _cl.public_registry()


@app.get("/api/craxlearn/activity")
def craxlearn_activity(user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    """What has been asked, inside the asker's own institution.

    Two different answers to two different people, and the difference is the
    whole point:

    A **teacher or head** gets their school's activity as topic counts — what
    is being asked and how often, so they can see the class is stuck on
    stoichiometry. Aggregated, with no learner attached to any row. A school
    needs to know what its students are struggling with; it does not need a
    transcript of each child's questions to know that, and building the
    transcript view because it was easy is how a teaching tool becomes a
    surveillance tool. If a school genuinely needs per-student detail for a
    safeguarding reason, that is a deliberate feature with its own consent
    conversation, not a side effect of this endpoint.

    A **learner** gets their own, in full, because it is theirs.

    Neither can see another institution's, and nothing here reads a row
    outside the caller's own scope.
    """
    scope = _scope_of(db, user)
    ta = (db.query(TeacherAccess)
            .filter(TeacherAccess.user_id == user.id).first())

    if ta and _cl.is_institution(scope):
        rows = (db.query(LearnRecord.text, LearnRecord.kind,
                         func.count(LearnRecord.id).label("n"),
                         func.max(LearnRecord.created_at).label("last"))
                  .filter(LearnRecord.scope == scope)
                  .group_by(LearnRecord.text, LearnRecord.kind)
                  .order_by(func.count(LearnRecord.id).desc())
                  .limit(100).all())
        return {
            "view": "school", "school": ta.school or "", "scope": scope,
            "learners": (db.query(func.count(func.distinct(
                LearnRecord.user_id)))
                .filter(LearnRecord.scope == scope).scalar() or 0),
            "topics": [{"text": r[0], "kind": r[1], "asked": r[2],
                        "last": r[3].isoformat() if r[3] else ""}
                       for r in rows],
        }

    rows = (db.query(LearnRecord)
              .filter(LearnRecord.user_id == user.id)
              .order_by(LearnRecord.created_at.desc()).limit(100).all())
    return {
        "view": "mine", "scope": scope,
        "topics": [{"text": r.text, "kind": r.kind, "subject": r.subject,
                    "level": r.level,
                    "at": r.created_at.isoformat() if r.created_at else ""}
                   for r in rows],
    }


@app.delete("/api/craxlearn/activity")
def craxlearn_activity_clear(user: User = Depends(current_user),
                            db: Session = Depends(get_db)):
    """Delete my own record of what I asked. Only ever my own.

    A teacher clearing this clears their own questions, not their school's.
    Giving one account a button that wipes an institution's history is the
    kind of thing that gets pressed once and explained forever.
    """
    n = (db.query(LearnRecord).filter(LearnRecord.user_id == user.id)
           .delete(synchronize_session=False))
    db.commit()
    return {"ok": True, "deleted": n}


@app.get("/api/skills/unlocked")
def skills_unlocked(user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    """Everything this learner has finished, and who is hiring for it.

    The count beside each skill is the argument for having learned it, and
    it is the same count the careers page shows — read from the live board
    rather than from a claim in a syllabus. A skill with no matcher word
    still appears, with no count: the learner earned it, and a résumé line
    is worth having whether or not a job board has a word for it.
    """
    rows = (db.query(SkillUnlock)
              .filter(SkillUnlock.user_id == user.id)
              .order_by(SkillUnlock.last_at.desc()).limit(200).all())
    out = []
    for r in rows:
        tokens = [t for t in (r.tokens or "").split(",") if t]
        jobs = 0
        for t in tokens:
            # The skills column is a comma-joined list written at ingest, so
            # a bare LIKE would match "sql" inside "postgresql". The commas
            # are what make the boundary.
            #
            # Concatenated with Python's + rather than func.concat: that
            # compiles to the || operator, which both SQLite and Postgres
            # have. CONCAT() only arrived in SQLite 3.44, and the local
            # database is whatever the machine happens to ship.
            padded = "," + func.coalesce(Job.skills, "") + ","
            jobs = max(jobs, db.query(func.count(Job.id)).filter(
                Job.is_open == True,                            # noqa: E712
                padded.like(f"%,{t},%")).scalar() or 0)
        out.append({"skill": r.label, "tokens": tokens, "jobs": jobs,
                    "times": r.times or 1,
                    "since": r.created_at.isoformat() if r.created_at else ""})
    return {"skills": out, "total": len(out)}


class TalkIn(BaseModel):
    said: str = Field(min_length=1, max_length=600)
    subject: str = Field(default="General", max_length=60)
    level: str = Field(default="Intermediate", max_length=60)
    # The last few turns, so "why?" means the thing just said rather than
    # nothing at all. Kept short deliberately: a conversation that resends its
    # whole history grows its own bill on every turn.
    history: list[str] = []


@app.post("/api/ask/talk")
async def ask_talk(body: TalkIn, user: User = Depends(current_user),
                   db: Session = Depends(get_db)):
    """One spoken turn of a conversation.

    Deliberately not the board's lesson shape. A lesson is a page — headings,
    steps, code — and reading a page aloud is not a conversation, it is a
    lecture nobody can interrupt. This returns two to five sentences, written
    to be *heard*: no bullet points, no symbols that do not survive being
    said, and an answer that stops so the other person can speak.
    """
    if not ASK_ENABLED:
        raise HTTPException(503, "The AI tutor is not switched on")
    said = body.said.strip()
    level = (body.level or "Intermediate").strip()[:60]

    # Cached on the question plus the immediate context. Everyone asks "what
    # is a JOIN" out loud eventually, and the second person should not cost
    # anything.
    #
    # The key says "dalia" rather than "talk" on purpose. The rows under the
    # old key were written by a different prompt with a different persona and
    # no control tags in it; served under this endpoint they would be a
    # tutor who can never open anything, for as long as the cache lives.
    tail = " | ".join(body.history[-2:])[:300]
    scope = _scope_of(db, user)
    qkey = _cl.key(scope, "dalia", _norm_q(level), _norm_q(tail),
                   _norm_q(said))[:500]
    # Recorded before the cache is consulted, not after. What a learner
    # asked is a fact about them whether or not it cost a model call, and a
    # record that only catches the misses is a record of nothing useful —
    # the popular questions, which is to say the ones a school most wants to
    # see, are exactly the ones that hit.
    _record_learning(db, user, scope, "talk", said, body.subject, level)

    row = db.query(AskCache).filter(AskCache.qkey == qkey).first()
    if row:
        row.hits = (row.hits or 0) + 1
        db.commit()
        # Parsed on the way out rather than stored parsed: the raw reply is
        # what was cached, so a cache hit opens the same panels the first
        # asker got. Storing only the spoken half meant the second person to
        # ask about the handshake heard about a packet capture that never
        # appeared.
        say, controls, skills = _dalia.parse(row.lesson)
        return {"say": _spoken(say), "board": controls,
                "skills": _record_skills(db, user, skills), "cached": True}

    _ai_enforce_limit(db, user)
    prompt = _dalia.talk_prompt(said, body.history, level, body.subject)
    try:
        text = (await _ai_text(prompt, 400)).strip()
    except Exception as e:
        print(f"Talk failed ({AI_PROVIDER}): {type(e).__name__}: {e}")
        raise HTTPException(503, _ai_error_message(e))
    if not text:
        raise HTTPException(502, "Nothing came back — say that again?")

    say, controls, skills = _dalia.parse(text)
    if not say:
        # Every word of it was tags. Nothing to say and nothing to play.
        raise HTTPException(502, "Nothing came back — say that again?")

    _ai_bump(db, user)
    # The raw reply, tags and all. What is spoken is derived from it on
    # every read, so changing how a tag is handled changes every cached
    # answer too instead of only the ones asked after the deploy.
    db.add(AskCache(qkey=qkey, subject=body.subject[:60], level=level,
                    question=said[:2000], lesson=text[:4000], hits=0))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return {"say": _spoken(say), "board": controls,
            "skills": _record_skills(db, user, skills), "cached": False}


@app.post("/api/ask/image")
async def ask_with_image(image: UploadFile = File(...),
                         question: str = Form(default=""),
                         subject: str = Form(default="General"),
                         level: str = Form(default="Intermediate"),
                         user: User = Depends(current_user),
                         db: Session = Depends(get_db)):
    """Ask Axle a question about a picture.

    The scanner reads a problem and solves it. This is the other half: a
    photograph you want to ask something *about* — a diagram you do not
    follow, a graph in a paper, a slide, a specimen, a circuit, a page in a
    language you do not read. The question is yours; the image is context.

    It returns the same lesson shape as a typed question, so the board renders
    it with no idea an image was involved.

    Cached on the image plus the question, because the pairing is what was
    asked. The same photo with a different question is a different question.
    """
    raw = await image.read()
    if not raw:
        raise HTTPException(400, "That photo was empty")
    if len(raw) > _scan.MAX_MB * 1024 * 1024:
        raise HTTPException(400, f"Photos need to be under {_scan.MAX_MB:.0f}MB")
    mime = (image.content_type or "").lower().split(";")[0].strip()
    if mime not in _scan.MIMES:
        raise HTTPException(400, "Send a photo — JPG, PNG or WEBP")
    require_paid_or_trial(db, user, "scan", "Asking about a photo",
                          "three free photo questions")
    if not ASK_ENABLED:
        raise HTTPException(503, "The AI tutor is not switched on")

    q = (question or "").strip()[:400]
    subject = (subject or "General").strip()[:60]
    level = (level or "Intermediate").strip()[:60]
    digest = hashlib.sha256(raw).hexdigest()[:32]
    scope = _scope_of(db, user)
    qkey = _cl.key(scope, "askimg", digest, _norm_q(level), _norm_q(q))[:500]
    row = db.query(AskCache).filter(AskCache.qkey == qkey).first()
    cached = _cached_json(db, row)
    if cached:
        row.hits = (row.hits or 0) + 1
        db.commit()
        return {"lesson": cached, "cached": True}

    _ai_enforce_limit(db, user)
    prompt = _ask_prompt(
        q or "Explain what is in this image, and what it is showing.",
        subject, level) + (
        "\n\nThe user has attached an image. Look at it first. Describe what "
        "is actually in it before explaining anything, so they can tell "
        "immediately whether you are looking at what they meant. If the image "
        "does not show what the question implies, say so plainly rather than "
        "answering the question you were expecting.")
    try:
        lesson = _parse_lesson(
            await _ai_vision(prompt, raw, mime, 1800), q or "this image")
    except Exception as e:
        print(f"Ask with image failed: {type(e).__name__}: {e}")
        raise HTTPException(503, _ai_error_message(e))

    found, verdict = _check_lesson(lesson)
    review = await _review_lesson(q or "this image", lesson)
    if review:
        found = review + found
        if any(r["severity"] == "critical" for r in review):
            verdict = {"cache": False, "confidence": "low", "state": "flagged"}
        elif verdict["confidence"] == "high":
            verdict = dict(verdict, confidence="medium", state="checked")
    if found:
        print(f"Checks on image question: {verdict['state']} — "
              f"{found[0]['problem'][:120]}")
        lesson["findings"] = _note_findings(found)
        lesson["confidence"] = verdict["confidence"]

    _ai_bump(db, user)
    _trial_consume(db, user, "scan")
    if not verdict["cache"]:
        return {"lesson": lesson, "cached": False, "checked": verdict["state"]}
    db.add(AskCache(qkey=qkey, subject=subject, level=level,
                    question=(q or "(about an image)")[:2000],
                    lesson=json.dumps(lesson), hits=0))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return {"lesson": lesson, "cached": False}


class ResumeAIIn(BaseModel):
    resume: dict = {}
    target_role: str = Field(default="", max_length=120)
    jd: str = Field(default="", max_length=8000)


@app.post("/api/resume/ai")
async def resume_ai(body: ResumeAIIn, user: User = Depends(current_user)):
    """Rewrite a resume into strong, ATS-optimized wording — using only the
    facts the student provided (never inventing employers, dates or degrees).
    If a job description is supplied, tailor the wording toward it."""
    if not ASK_ENABLED:
        raise HTTPException(503, "The AI writer is not switched on")
    r = body.resume or {}
    role = (body.target_role or r.get("title") or "the role").strip()[:120]
    jd = (body.jd or "").strip()
    exp = r.get("exp", []) or []
    facts = {
        "name": r.get("name", ""), "title": r.get("title", ""),
        "summary": r.get("summary", ""),
        "skills": r.get("skills", []),
        "experience": [{"role": x.get("role", ""), "company": x.get("company", ""),
                        "dates": x.get("dates", ""), "bullets": x.get("bullets", "")}
                       for x in exp],
        "projects": r.get("proj", []), "education": r.get("edu", []),
    }
    prompt = (
        "You are an expert resume writer optimising for Applicant Tracking "
        f"Systems (ATS). Target role: {role}.\n\n"
        + (f"Tailor the wording toward THIS job description, weaving in its "
           f"keywords where truthful:\n{jd[:3000]}\n\n" if jd else "")
        + "Rewrite the following resume facts into strong, concise, ATS-friendly "
        "content. RULES: use ONLY the facts given — never invent employers, "
        "job titles, dates, degrees or numbers that aren't there. Improve "
        "wording: start experience bullets with strong action verbs, keep each "
        "bullet to one line, weave in keywords a recruiter for this role would "
        "search. If the person has little experience, lean on projects and "
        "skills.\n\n"
        f"FACTS (JSON):\n{json.dumps(facts, ensure_ascii=False)}\n\n"
        "Respond with ONLY valid JSON, no markdown, in exactly this shape:\n"
        '{"summary": "<2-3 line professional summary>", '
        '"skills": [{"label": "<group>", "items": "<comma separated>"}], '
        '"experience": ["<newline-separated improved bullets for job 1>", '
        '"<for job 2>", ...same order and count as the input experience...], '
        '"tips": ["<short actionable tip>", "..."]}'
    )
    try:
        text = await _ai_text(prompt, 1600)
    except Exception as e:
        print(f"Resume AI failed ({AI_PROVIDER}): {type(e).__name__}: {e}")
        raise HTTPException(503, "The AI writer could not respond. Try again.")
    clean = (text or "").replace("```json", "").replace("```", "").strip()
    try:
        data = json.loads(clean)
    except Exception:
        raise HTTPException(502, "The AI returned an unexpected format. Try again.")
    return {
        "summary": str(data.get("summary", ""))[:1200],
        "skills": [{"label": str(s.get("label", ""))[:40], "items": str(s.get("items", ""))[:400]}
                   for s in (data.get("skills") or []) if isinstance(s, dict)][:8],
        "experience": [str(b)[:1500] for b in (data.get("experience") or [])][:len(exp)],
        "tips": [str(t)[:200] for t in (data.get("tips") or [])][:6],
    }


def _ai_json(text):
    """Parse a model's JSON reply, tolerating the ways models wrap it.

    Asking for JSON in the prompt is not a guarantee: models add a preamble,
    fence the block, or append a closing remark. Parsing the whole string and
    hoping meant one stray sentence surfaced to the user as "the AI could not
    respond", which is both wrong and unfixable from their side.
    """
    raw = (text or "").strip()
    clean = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(clean)
    except Exception:
        pass
    # Fall back to the outermost {...} or [...] in the response.
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = clean.find(opener), clean.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(clean[start:end + 1])
            except Exception:
                continue
    # Truncated rather than malformed: the model ran out of room mid-object.
    # Rather than lose the whole lesson, cut back to the last complete element
    # and close what is still open — seven steps of eight is a lesson; a
    # parse error is nothing.
    salvaged = _close_truncated_json(clean)
    if salvaged is not None:
        print("AI: reply was truncated; salvaged the complete part of it")
        return salvaged
    raise ValueError(f"Model did not return JSON. First 200 chars: {raw[:200]!r}")


def _close_truncated_json(text):
    """Repair an object that was cut off part-way, or return None.

    Walks the string tracking string state and nesting, rewinds to the last
    point where a value had just finished, and closes the containers that are
    still open. Deliberately conservative: it never invents a value, so the
    worst case is a lesson with fewer steps than the model intended.
    """
    if not text.startswith("{") and not text.startswith("["):
        i = min([x for x in (text.find("{"), text.find("[")) if x != -1]
                or [-1])
        if i < 0:
            return None
        text = text[i:]

    stack, in_str, esc, safe = [], False, False, -1
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
                safe = i          # a string just closed: a clean place to cut
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]":
            if stack:
                stack.pop()
            safe = i
        elif ch in "0123456789":
            safe = i              # a number may have just finished here

    if not stack or safe < 0:
        return None
    head = text[:safe + 1]
    # Drop a dangling key or comma left over from the cut.
    head = _re.sub(r',\s*"[^"]*"\s*:\s*$', "", head)
    head = head.rstrip().rstrip(",")
    for closer in reversed(stack):
        head += closer
    try:
        return json.loads(head)
    except Exception:
        return None


class BulletsIn(BaseModel):
    role: str = Field(default="", max_length=120)
    company: str = Field(default="", max_length=120)
    context: str = Field(default="", max_length=1000)
    tone: str = Field(default="Professional", max_length=20)


@app.post("/api/resume/bullets")
async def resume_bullets(body: BulletsIn, user: User = Depends(current_user)):
    """AI-written ATS achievement bullets for one job, using the STAR framework."""
    if not ASK_ENABLED:
        raise HTTPException(503, "The AI writer is not switched on")
    role = (body.role or "the role").strip()[:120]
    tone = (body.tone or "Professional").strip()[:20]
    prompt = (
        f"You are an expert resume writer. Write 6 strong, ATS-friendly, "
        f"one-line achievement bullet points for a '{role}'"
        + (f" at {body.company.strip()}" if body.company.strip() else "")
        + f", in a {tone} tone.\n"
        + (f"What the person did: {body.context.strip()}\n" if body.context.strip() else "")
        + "Follow the STAR idea (Situation/Task/Action/Result) compressed into "
        "one line: start with a strong action verb, state what was done, and "
        "end with a measurable result. Use realistic, generic impact phrasing "
        "the person can edit with their own numbers — do NOT fabricate specific "
        "company names or precise false statistics. Keep each to one line.\n\n"
        'Respond with ONLY valid JSON: {"bullets": ["...", "...", "..."]}'
    )
    try:
        data = _ai_json(await _ai_text(prompt, 700, json_mode=True))
    except Exception as e:
        print(f"Resume bullets failed ({AI_PROVIDER}): {type(e).__name__}: {e}")
        raise HTTPException(503, "The AI writer could not respond. Try again.")
    return {"bullets": [str(b)[:300] for b in (data.get("bullets") or [])][:8]}


class RoleIn(BaseModel):
    role: str = Field(default="", max_length=120)


@app.post("/api/resume/skills")
async def resume_skills(body: RoleIn, user: User = Depends(current_user)):
    """AI-suggested, ATS-searchable skills matched to a target role."""
    if not ASK_ENABLED:
        raise HTTPException(503, "The AI writer is not switched on")
    role = (body.role or "").strip()[:120]
    if not role:
        raise HTTPException(400, "Enter a target role first")
    prompt = (
        f"List 16 concrete, ATS-searchable skills that recruiters look for in a "
        f"'{role}'. Include specific tools, technologies, methods and hard "
        f"skills — the exact keywords a job post would use. No sentences, just "
        f"the skill names.\n\n"
        'Respond with ONLY valid JSON: {"skills": ["Python", "SQL", "..."]}'
    )
    try:
        data = _ai_json(await _ai_text(prompt, 500, json_mode=True))
    except Exception as e:
        print(f"Resume skills failed ({AI_PROVIDER}): {type(e).__name__}: {e}")
        raise HTTPException(503, "The AI writer could not respond. Try again.")
    return {"skills": [str(s)[:40] for s in (data.get("skills") or [])][:20]}


class MatchIn(BaseModel):
    resume: dict = {}
    jd: str = Field(default="", max_length=8000)
    resume_text: str = Field(default="", max_length=40000)


def _resume_text(r):
    # If the resume is in "sections" mode (an imported resume), its content
    # lives in the section bodies — use those for matching / advice.
    secs = r.get("sections")
    if isinstance(secs, list) and secs:
        out = []
        for s in secs:
            if isinstance(s, dict):
                if s.get("h"):
                    out.append(str(s.get("h", "")))
                if s.get("body"):
                    out.append(str(s.get("body", "")))
        if out:
            return "\n".join(out).lower()
    parts = [r.get("name", ""), r.get("title", ""), r.get("summary", ""), r.get("certs", "")]
    for s in r.get("skills", []):
        parts += [s.get("label", ""), s.get("items", "")]
    for x in r.get("exp", []):
        parts += [x.get("role", ""), x.get("company", ""), x.get("bullets", "")]
    for x in r.get("proj", []):
        parts += [x.get("name", ""), x.get("tech", ""), x.get("desc", "")]
    for x in r.get("edu", []):
        parts += [x.get("degree", ""), x.get("school", "")]
    return " \n ".join(str(p) for p in parts).lower()


@app.post("/api/resume/match")
async def resume_match(body: MatchIn, user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    """Full AI analysis of the resume against a JD: overall score, sub-scores,
    and gaps categorised as critical / weak / strong."""
    if not ASK_ENABLED:
        raise HTTPException(503, "The AI matcher is not switched on")
    jd = (body.jd or "").strip()
    if len(jd) < 40:
        raise HTTPException(400, "Paste the full job description first")
    rtext = ((body.resume_text or "").strip() or _resume_text(body.resume or {}))[:5000]
    # Same resume + same JD → serve the stored result for free (no quota used).
    ckey = _ai_cache_key("rmatch", rtext, jd[:3500], scope=_scope_of(db, user))
    cached = _ai_cache_get(db, ckey)
    if cached is not None:
        return cached
    _ai_enforce_limit(db, user)
    prompt = (
        "You are an ATS resume analyst. Compare the RESUME to the JOB "
        "DESCRIPTION and score the fit honestly.\n\n"
        f"RESUME:\n{rtext}\n\nJOB DESCRIPTION:\n{jd[:3500]}\n\n"
        "Rules for the lists:\n"
        "- 'critical' / 'weak' / 'strong' items must be SHORT keyword phrases "
        "(1-4 words) taken from the job description — e.g. 'Kubernetes', "
        "'stakeholder management', 'A/B testing'. No sentences.\n"
        "- 'critical' = required in the JD and NOT found in the resume.\n"
        "- 'weak' = present but thin (no detail or metrics vs what the JD wants).\n"
        "- 'strong' = clearly evidenced and matches the JD.\n"
        "- 'advice' = 3-5 clear, specific next steps. Each step names the exact "
        "keyword/section to change and, where useful, gives a short example line "
        "the user could adapt (in quotes). Be concrete, not generic.\n\n"
        "Return ONLY valid JSON in exactly this shape (scores are 0-100 "
        "integers):\n"
        '{"score": <overall>, '
        '"subscores": {"keywords": <n>, "experience": <n>, "readability": <n>}, '
        '"critical": ["<kw>", "..."], "weak": ["<kw>", "..."], '
        '"strong": ["<kw>", "..."], '
        '"advice": ["<specific next step, with example wording>", "..."]}'
    )
    try:
        d = _ai_json(await _ai_text(prompt, 900, json_mode=True))
    except Exception as e:
        print(f"Resume match failed ({AI_PROVIDER}): {type(e).__name__}: {e}")
        raise HTTPException(503, _ai_error_message(e))
    def lst(k, n=12, cap=60):
        return [str(x)[:cap] for x in (d.get(k) or []) if str(x).strip()][:n]
    sub = d.get("subscores") or {}
    def sc(v):
        try:
            return max(0, min(100, int(v)))
        except Exception:
            return 0
    result = {
        "score": sc(d.get("score", 0)),
        "subscores": {"keywords": sc(sub.get("keywords", 0)),
                      "experience": sc(sub.get("experience", 0)),
                      "readability": sc(sub.get("readability", 0))},
        "critical": lst("critical"), "weak": lst("weak"),
        "strong": lst("strong"), "advice": lst("advice", 6, 280),
    }
    _ai_bump(db, user)
    _ai_cache_put(db, ckey, result)
    return result


# ---- repair a .docx whose embedded images are corrupt -------------------
def _tiny_jpeg():
    try:
        from PIL import Image
        b = io.BytesIO()
        Image.new("RGB", (8, 8), (255, 255, 255)).save(b, "JPEG")
        return b.getvalue()
    except Exception:
        return b""  # empty; LibreOffice will just skip a broken image


def _sanitize_docx(raw):
    """Rebuild a .docx, replacing any unreadable member (a corrupt embedded
    image is a common export bug) so LibreOffice can still open it. Returns the
    original bytes unchanged if everything is already fine."""
    import zipfile
    try:
        src = zipfile.ZipFile(io.BytesIO(raw))
    except Exception:
        return raw
    bad = None
    try:
        bad = src.testzip()      # first member that fails its CRC, or None
    except Exception:
        bad = "?"
    if not bad:
        return raw               # nothing to repair
    placeholder = _tiny_jpeg()
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            try:
                data = src.read(info.filename)
            except Exception:
                ext = info.filename.lower().rsplit(".", 1)[-1]
                if ext in ("jpg", "jpeg", "png", "gif", "bmp", "tif", "tiff", "emf", "wmf"):
                    data = placeholder            # swap corrupt image for a clean one
                else:
                    continue                       # drop other unreadable parts
            dst.writestr(info.filename, data)
    return out.getvalue()


# ---- convert an uploaded Word .docx to a PDF (to preserve its layout) ----
def _docx_to_pdf(raw):
    """Render a .docx to PDF with LibreOffice so we can then reproduce its
    exact visual layout. Returns PDF bytes, or None if conversion is
    unavailable/fails (caller then falls back to text-only structured import)."""
    import shutil
    import subprocess
    import tempfile
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return None
    try:
        raw = _sanitize_docx(raw)      # repair corrupt embedded images first
    except Exception:
        pass
    try:
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "in.docx")
            with open(src, "wb") as f:
                f.write(raw)
            # A private profile dir avoids clashes between concurrent requests.
            prof = "-env:UserInstallation=file://" + os.path.join(d, "profile")
            subprocess.run(
                [soffice, "--headless", prof, "--convert-to", "pdf",
                 "--outdir", d, src],
                check=True, capture_output=True, timeout=60,
                env={**os.environ, "HOME": d})
            out = os.path.join(d, "in.pdf")
            if os.path.exists(out):
                with open(out, "rb") as f:
                    return f.read()
    except Exception as e:
        print(f"docx->pdf conversion failed: {type(e).__name__}: {e}")
    return None


# ---- capture the ORIGINAL layout of an uploaded PDF ---------------------
def _font_family(fontname):
    f = (fontname or "").lower()
    if "times" in f or "serif" in f or "georgia" in f or "garamond" in f:
        return "times"
    if "courier" in f or "mono" in f or "consol" in f:
        return "courier"
    return "helvetica"


def _color_hex(c):
    """Convert a pdfplumber colour (grayscale float, RGB/CMYK tuple, or None)
    to a #rrggbb string. Returns None when there is no usable colour."""
    try:
        if c is None:
            return None
        if isinstance(c, (int, float)):
            v = max(0, min(255, int(round(float(c) * 255))))
            return "#%02x%02x%02x" % (v, v, v)
        if isinstance(c, (list, tuple)):
            vals = [float(x) for x in c]
            if len(vals) == 1:
                v = max(0, min(255, int(round(vals[0] * 255))))
                return "#%02x%02x%02x" % (v, v, v)
            if len(vals) == 3:
                r, g, b = [max(0, min(255, int(round(x * 255)))) for x in vals]
                return "#%02x%02x%02x" % (r, g, b)
            if len(vals) == 4:
                cc, m, y, k = vals
                r = int(round(255 * (1 - cc) * (1 - k)))
                g = int(round(255 * (1 - m) * (1 - k)))
                b = int(round(255 * (1 - y) * (1 - k)))
                return "#%02x%02x%02x" % (r, g, b)
    except Exception:
        return None
    return None


def _extract_pdf_layout(raw):
    """Return a positional layout of a PDF so we can rebuild it almost exactly:
    every text line keeps its x, y (from top), font size, weight and family.
    Two-column resumes reproduce naturally because each line keeps its own x.
    Returns None if the PDF has no usable text (e.g. a scanned image)."""
    try:
        import pdfplumber
    except Exception:
        return None
    try:
        pdf = pdfplumber.open(io.BytesIO(raw))
    except Exception:
        return None
    pages = []
    try:
        for page in pdf.pages[:6]:
            try:
                words = page.extract_words(
                    extra_attrs=["size", "fontname"], use_text_flow=False)
            except Exception:
                words = []
            words.sort(key=lambda w: (round(w.get("top", 0), 0), w.get("x0", 0)))
            lines = []
            row = []           # words on the current visual line
            row_top = None
            def flush(row):
                if not row:
                    return
                # split the visual row into segments across big x gaps (columns)
                seg = [row[0]]
                for w in row[1:]:
                    gap = w.get("x0", 0) - seg[-1].get("x1", 0)
                    if gap > 42:
                        _emit(lines, seg)
                        seg = [w]
                    else:
                        seg.append(w)
                _emit(lines, seg)
            for w in words:
                t = w.get("top", 0)
                if row_top is None or abs(t - row_top) <= max(3.0, w.get("size", 10) * 0.5):
                    row.append(w)
                    row_top = t if row_top is None else row_top
                else:
                    flush(row)
                    row = [w]
                    row_top = t
            flush(row)
            lines.sort(key=lambda l: (round(l["y"], 0), l["x"]))

            # Filled rectangles (e.g. coloured section-heading bars). Skip white
            # fills and any near-full-page fill that would cover the text.
            rects = []
            try:
                for r in (page.rects or [])[:80]:
                    fill = _color_hex(r.get("non_stroking_color"))
                    if not fill or fill in ("#ffffff", "#fefefe"):
                        continue
                    x0 = float(r["x0"]); top = float(r["top"])
                    w = float(r["x1"]) - x0; h = float(r["bottom"]) - top
                    if w < 4 or h < 2:
                        continue
                    if w > page.width * 0.98 and h > page.height * 0.9:
                        continue
                    rects.append({"x": round(x0, 1), "y": round(top, 1),
                                  "w": round(w, 1), "h": round(h, 1), "c": fill})
            except Exception:
                rects = []

            # Per-line text colour (captures blue links, coloured headings).
            try:
                chars = page.chars or []
                for ln in lines:
                    for c in chars:
                        if abs(float(c.get("top", 0)) - ln["y"]) <= ln["size"] * 0.7 \
                                and ln["x"] - 2 <= float(c.get("x0", 0)) <= ln["x"] + 300:
                            hx = _color_hex(c.get("non_stroking_color"))
                            if hx and hx != "#000000":
                                ln["color"] = hx
                            break
            except Exception:
                pass

            if lines:
                pages.append({"w": round(float(page.width), 1),
                              "h": round(float(page.height), 1),
                              "lines": lines[:220], "rects": rects[:40]})
    except Exception:
        return None
    if not pages:
        return None
    return {"pages": pages[:4]}


def _emit(lines, seg):
    if not seg:
        return
    text = " ".join(str(w.get("text", "")) for w in seg).strip()
    if not text:
        return
    sizes = [w.get("size", 10) for w in seg if w.get("size")]
    size = round(sorted(sizes)[len(sizes) // 2], 1) if sizes else 10.0
    bold = any("bold" in str(w.get("fontname", "")).lower() for w in seg)
    italic = any(("italic" in str(w.get("fontname", "")).lower()
                  or "oblique" in str(w.get("fontname", "")).lower()) for w in seg)
    lines.append({
        "t": text[:300],
        "x": round(seg[0].get("x0", 0), 1),
        "y": round(seg[0].get("top", 0), 1),
        "size": max(5.0, min(48.0, size)),
        "bold": bold, "italic": italic,
        "font": _font_family(seg[0].get("fontname", "")),
    })


# ---- split extracted resume text into editable sections ------------------
_SECTION_KEYWORDS = {
    "summary", "professional summary", "career summary", "summary of qualifications",
    "objective", "career objective", "profile", "professional profile",
    "skills", "technical skills", "technical expertise", "core competencies",
    "key skills", "areas of expertise",
    "experience", "work experience", "professional experience", "employment",
    "employment history", "work history", "professional background",
    "projects", "key projects", "academic projects",
    "education", "academic qualifications", "qualifications",
    "certification", "certifications", "certificates", "licenses",
    "achievements", "awards", "honors", "accomplishments",
    "languages", "interests", "hobbies", "publications", "references",
    "volunteer experience", "activities",
}


def _clean_field_codes(s):
    """Strip Word field codes like HYPERLINK "mailto:..." that survive text
    extraction, leaving the human-readable text."""
    s = _re.sub(r'HYPERLINK\s+"[^"]*"\s*', "", s)
    s = _re.sub(r"\s{2,}", " ", s)
    return s.strip()


def _is_section_heading(line):
    s = line.strip().rstrip(":").strip()
    if not s or len(s) > 48:
        return False
    if s.lower() in _SECTION_KEYWORDS:
        return True
    # ALL-CAPS short line with no digits is almost always a section header.
    letters = [c for c in s if c.isalpha()]
    if letters and s.upper() == s and len(letters) >= 3 and not any(c.isdigit() for c in s):
        return True
    return False


def _split_sections(text):
    """Group the resume text into {heading, body} sections the user can edit as
    whole blocks. The block before the first heading (name/contact) has h=""."""
    secs = []
    cur = {"h": "", "body": []}
    for raw_line in (text or "").split("\n"):
        line = raw_line.rstrip()
        if _is_section_heading(line):
            if cur["h"] or cur["body"]:
                secs.append(cur)
            cur = {"h": line.strip().rstrip(":").strip(), "body": []}
        else:
            t = _clean_field_codes(line)
            if t:
                cur["body"].append(t)
    if cur["h"] or cur["body"]:
        secs.append(cur)
    out = []
    for s in secs[:24]:
        out.append({"h": s["h"][:60], "body": "\n".join(s["body"])[:20000]})
    return out


# ---- parse an uploaded resume (PDF / DOCX / TXT) into the builder ----
def _extract_resume_text(filename, raw):
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw))
            return "\n".join((p.extract_text() or "") for p in reader.pages)
        except Exception as e:
            raise HTTPException(400, f"Could not read that PDF: {e}")
    if name.endswith(".docx"):
        # Read the text parts via zipfile, so a corrupt embedded image (a common
        # cause of "Bad CRC-32") can never break the import. IMPORTANT: the
        # candidate's name and contact details are very often in the document
        # HEADER (word/header*.xml), not the body — so we must read those too.
        import zipfile
        import re as _re2
        import html as _html

        def _docx_part_text(zf, part):
            try:
                xml = zf.read(part).decode("utf-8", "ignore")
            except Exception:
                return ""
            xml = xml.replace("</w:p>", "\n").replace("<w:tab/>", "  ")
            txt = _html.unescape(_re2.sub(r"<[^>]+>", "", xml))
            # strip leading drawing/anchor digit-noise that can precede a header name
            return _re2.sub(r"^[\d\s]{6,}", "", txt).strip()

        try:
            zf = zipfile.ZipFile(io.BytesIO(raw))
        except Exception as e:
            raise HTTPException(400, f"Could not read that DOCX: {e}")
        names = zf.namelist()
        headers = sorted(n for n in names if _re2.match(r"word/header\d*\.xml$", n))
        footers = sorted(n for n in names if _re2.match(r"word/footer\d*\.xml$", n))
        parts = []
        for h in headers:                       # name + contact usually live here
            t = _docx_part_text(zf, h)
            if t:
                parts.append(t)
        body = _docx_part_text(zf, "word/document.xml")
        if body:
            parts.append(body)
        for f in footers:
            t = _docx_part_text(zf, f)
            if t:
                parts.append(t)
        return "\n".join(parts)
    if name.endswith(".txt"):
        return raw.decode("utf-8", "ignore")
    raise HTTPException(400, "Upload a PDF, DOCX or TXT file")


@app.post("/api/resume/parse")
async def resume_parse(file: UploadFile = File(...),
                       user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    """Read an existing resume file and let the AI structure it into the
    builder's sections — so the student starts from what they already have."""
    # Free: a paywall between someone and their own CV is a paywall in
    # front of the thing that makes matching work at all.
    if not ASK_ENABLED:
        raise HTTPException(503, "The AI parser is not switched on")
    raw = await file.read()
    if len(raw) > 4_000_000:
        raise HTTPException(400, "File too large (max 4 MB)")
    try:
        text = _extract_resume_text(file.filename, raw)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Could not read that file: {e}")
    text = (text or "").strip()
    if len(text) < 30:
        raise HTTPException(400, "No readable text found in that file")
    prompt = (
        "You are extracting a resume into structured JSON for a resume builder. "
        "Read the WHOLE text and capture EVERYTHING — do not summarise, shorten "
        "or drop anything. Use ONLY information present; leave a field empty only "
        "if it is truly absent.\n\n"
        "Critical rules:\n"
        "- NAME and CONTACT are usually on the first lines (from the document "
        "header): capture name, email, phone, city/location and any links.\n"
        "- 'exp' MUST contain EVERY job listed, in order, each as its own object. "
        "Do NOT merge jobs and do NOT put every bullet under the first job. For "
        "each job set role (job title), company, place (city), dates (e.g. "
        "'Jan 2021 - Dec 2023'), and bullets = that job's OWN bullet lines "
        "(newline-separated, one per line, keep them all).\n"
        "- Put professional-summary lines in 'summary' (newline-separated).\n"
        "- Put all skills into 'skills' items.\n"
        "- Capture every 'edu' entry and any certifications in 'certs'.\n\n"
        f"RESUME TEXT:\n{text[:24000]}\n\n"
        "Return ONLY valid JSON in this shape (arrays may have as many items as "
        "needed):\n"
        '{"name":"","title":"","email":"","phone":"","location":"","links":"",'
        '"summary":"","skills":[{"label":"Skills","items":""}],'
        '"exp":[{"role":"","company":"","place":"","dates":"","bullets":""}],'
        '"edu":[{"degree":"","school":"","place":"","year":""}],'
        '"proj":[{"name":"","tech":"","desc":"","link":""}],"certs":""}'
    )
    try:
        d = _ai_json(await _ai_text(prompt, 6000, json_mode=True))
    except Exception as e:
        print(f"Resume parse failed ({AI_PROVIDER}): {type(e).__name__}: {e}")
        raise HTTPException(503, _ai_error_message(e))

    def s0(v, n=400): return str(v or "")[:n]
    s = s0
    out = {
        "name": s(d.get("name"), 120), "title": s(d.get("title"), 120),
        "email": s(d.get("email"), 120), "phone": s(d.get("phone"), 60),
        "location": s(d.get("location"), 120), "links": s(d.get("links"), 300),
        "summary": s(d.get("summary"), 1500),
        "skills": [{"label": s(x.get("label"), 40) or "Skills", "items": s(x.get("items"))}
                   for x in (d.get("skills") or []) if isinstance(x, dict)][:6] or [{"label": "Skills", "items": ""}],
        "exp": [{"role": s(x.get("role"), 120), "company": s(x.get("company"), 120),
                 "place": s(x.get("place"), 80), "dates": s(x.get("dates"), 40),
                 "bullets": s(x.get("bullets"), 4000), "ctx": ""}
                for x in (d.get("exp") or []) if isinstance(x, dict)][:14] or [{"role": "", "company": "", "place": "", "dates": "", "bullets": "", "ctx": ""}],
        "edu": [{"degree": s(x.get("degree"), 120), "school": s(x.get("school"), 120),
                 "place": s(x.get("place"), 80), "year": s(x.get("year"), 20)}
                for x in (d.get("edu") or []) if isinstance(x, dict)][:6] or [{"degree": "", "school": "", "place": "", "year": ""}],
        "proj": [{"name": s(x.get("name"), 120), "tech": s(x.get("tech"), 120),
                  "desc": s(x.get("desc"), 300), "link": s(x.get("link"), 200)}
                 for x in (d.get("proj") or []) if isinstance(x, dict)][:8] or [{"name": "", "tech": "", "desc": "", "link": ""}],
        "certs": s(d.get("certs"), 2000),
    }
    _trial_consume(db, user, "resume_upload")
    return out


@app.post("/api/resume/extract")
async def resume_extract(file: UploadFile = File(...),
                         user: User = Depends(current_user),
                         db: Session = Depends(get_db)):
    """Read an uploaded resume and return its plain text — used only to score it
    against a job description and to suggest changes. It does not build or edit
    anything."""
    # Free: a paywall between someone and their own CV is a paywall in
    # front of the thing that makes matching work at all.
    raw = await file.read()
    if len(raw) > 4_000_000:
        raise HTTPException(400, "File too large (max 4 MB)")
    try:
        text = _extract_resume_text(file.filename, raw)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Could not read that file: {e}")
    text = (text or "").strip()
    if len(text) < 30:
        raise HTTPException(400, "No readable text found in that file")
    _trial_consume(db, user, "resume_upload")
    return {"text": text[:40000], "name": (file.filename or "resume")[:120],
            "trial_left": max(0, FREE_TRIAL["resume_upload"]
                              - _trial_used(db, user, "resume_upload"))
            if plan_of(user) == "free" else None}


@app.get("/api/ask/config")
def ask_config(user: User = Depends(current_user)):
    """Lets the page know whether the AI teacher is switched on."""
    return {"enabled": ASK_ENABLED,
            "provider": AI_PROVIDER if ASK_ENABLED else "",
            "model": _PROVIDER_MODEL if ASK_ENABLED else ""}


@app.get("/api/mail/whoami")
def mail_whoami(email: str = "", user: User = Depends(admin_user),
                db: Session = Depends(get_db)):
    """Admin-only: does this address actually have an account, and can it be
    reset? A reset for an unregistered address sends nothing on purpose, and
    that looks identical to a broken mail server from the outside."""
    e = (email or user.email).lower().strip()
    u = db.query(User).filter(func.lower(User.email) == e).first()
    if not u:
        return {"email": e, "account_exists": False,
                "why_no_email": "No account with that address, so no reset "
                                "email is sent. Check for a typo, or whether "
                                "you signed up with a different address."}
    return {"email": e, "account_exists": True, "active": bool(u.is_active),
            "signed_up_with_google": not bool(u.password_hash),
            "would_send": bool(u.is_active),
            "last_background_email": LAST_MAIL}


@app.get("/api/mail/selftest")
def mail_selftest(user: User = Depends(admin_user)):
    """Admin-only: actually send one email and report the real error.

    Run synchronously and without swallowing the exception, because the whole
    point is to see why it failed. Gmail rejects a normal account password
    here — it needs an App Password — and that is the usual cause.
    """
    info = {"enabled": MAIL_ENABLED, "provider": MAIL_PROVIDER or "(none)",
            "from_overridden_because_unverified": MAIL_FROM_OVERRIDDEN or None,
            "host": SMTP_HOST or "(unset)", "port": SMTP_PORT,
            "user": SMTP_USER or "(unset)",
            "from": MAIL_FROM or "(unset)", "to": user.email,
            "last_background_email": LAST_MAIL}

    if MAIL_PROVIDER == "resend":
        try:
            r = httpx.post("https://api.resend.com/emails", timeout=20,
                           headers={"Authorization": f"Bearer {RESEND_API_KEY}",
                                    "Content-Type": "application/json"},
                           json={"from": MAIL_FROM, "to": [user.email],
                                 "subject": "Craxle mail test",
                                 "text": "If you are reading this, password "
                                         "reset emails will reach your users."})
            ok = r.status_code < 300
            hint = ""
            if not ok and "domain is not verified" in r.text.lower():
                hint = ("Verify craxle.com in Resend, then set MAIL_FROM to an "
                        "address on it. Until then MAIL_FROM must stay "
                        "onboarding@resend.dev, which only delivers to the "
                        "address that owns the Resend account.")
            elif not ok and r.status_code in (401, 403):
                hint = "RESEND_API_KEY looks wrong or was revoked."
            return {**info, "ok": ok,
                    "response": r.json() if r.content else {},
                    "http": r.status_code, "hint": hint,
                    "note": f"Check {user.email}, including spam." if ok else ""}
        except Exception as e:
            return {**info, "ok": False, "error": f"{type(e).__name__}: {e}"[:300]}

    if not MAIL_ENABLED:
        missing = [k for k, v in (("SMTP_HOST", SMTP_HOST), ("SMTP_USER", SMTP_USER),
                                  ("SMTP_PASS", SMTP_PASS)) if not v]
        return {**info, "ok": False,
                "error": "Not configured. Missing: " + ", ".join(missing)}
    # Prove the port is even reachable before opening an SMTP session. Many
    # hosts block outbound 587/465 to stop spam, and a blocked port hangs
    # rather than refusing — which is what took the site down: the request
    # sat open until Cloudflare gave up with a 524.
    import socket
    import smtplib
    from email.message import EmailMessage
    try:
        with socket.create_connection((SMTP_HOST, SMTP_PORT), timeout=5):
            pass
    except Exception as e:
        return {**info, "ok": False,
                "error": f"Cannot reach {SMTP_HOST}:{SMTP_PORT} — "
                         f"{type(e).__name__}: {e}"[:300],
                "hint": "The host is very likely blocking outbound SMTP. "
                        "Railway and most PaaS providers do. Use an HTTP email "
                        "API instead (Resend, Postmark, SendGrid) — they use "
                        "port 443, which is never blocked."}
    msg = EmailMessage()
    msg["From"] = MAIL_FROM
    msg["To"] = user.email
    msg["Subject"] = "Craxle mail test"
    msg.set_content("If you are reading this, password reset emails will "
                    "reach your users.\n\nCraxle")
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=8) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        return {**info, "ok": True, "sent": True,
                "note": f"Check {user.email} — including the spam folder."}
    except Exception as e:
        hint = ""
        text = f"{type(e).__name__}: {e}"
        if "Username and Password not accepted" in text or "5.7.8" in text:
            hint = ("Gmail refused the password. Use a 16-character App "
                    "Password (Google Account > Security > 2-Step "
                    "Verification > App passwords), not your normal password.")
        elif "Connection" in text or "timed out" in text:
            hint = "Could not reach the mail server. Check SMTP_HOST and SMTP_PORT."
        return {**info, "ok": False, "error": text[:400], "hint": hint}


@app.get("/api/ai/models")
async def ai_models(user: User = Depends(admin_user)):
    """Admin-only: ask Google which models this key can actually use.

    Model names change faster than anyone's memory, so this reads the live
    list rather than relying on a hardcoded one. Newest-looking names are
    listed first; set GEMINI_MODEL in Railway to switch.
    """
    if not GEMINI_API_KEY:
        return {"ok": False, "error": "No GEMINI_API_KEY set"}
    try:
        async with httpx.AsyncClient(timeout=25) as c:
            r = await c.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                params={"key": GEMINI_API_KEY, "pageSize": 200})
        r.raise_for_status()
        rows = r.json().get("models") or []
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"[:400]}

    usable = []
    for m in rows:
        name = (m.get("name") or "").replace("models/", "")
        methods = m.get("supportedGenerationMethods") or []
        if "generateContent" not in methods:
            continue          # embedding-only models can't answer prompts
        usable.append({
            "id": name,
            "display": m.get("displayName", ""),
            "input_tokens": m.get("inputTokenLimit"),
            "output_tokens": m.get("outputTokenLimit"),
            "in_use": name == GEMINI_MODEL,
        })
    # Sort by version descending so the newest is at the top, with "lite"
    # variants after their full siblings.
    def keyf(d):
        v = _re.search(r"(\d+)\.(\d+)", d["id"])
        major, minor = (int(v.group(1)), int(v.group(2))) if v else (0, 0)
        return (-major, -minor, "lite" not in d["id"], d["id"])
    usable.sort(key=keyf)
    return {"ok": True, "current": GEMINI_MODEL,
            "current_is_available": any(d["in_use"] for d in usable),
            "count": len(usable), "models": usable}


@app.get("/api/ai/selftest")
async def ai_selftest(user: User = Depends(admin_user),
                      db: Session = Depends(get_db)):
    """Admin-only: make one tiny AI call and return the RAW result or the RAW
    upstream error, so we can see exactly what the provider says (e.g. the real
    Gemini rate-limit/quota reason). Visit /api/ai/selftest while signed in as
    an admin."""
    info = {"provider": AI_PROVIDER, "model": _PROVIDER_MODEL, "enabled": ASK_ENABLED,
            "everyday_model": GEMINI_MODEL, "apply_kit_model": GEMINI_MODEL_BEST,
            "fallback_order": _providers_in_order()}
    if not ASK_ENABLED:
        return {**info, "ok": False, "error": "No AI key configured on the server"}

    # Two calls, because they fail differently. The short one proves the key
    # and model id work at all; the long one is shaped like a real apply kit,
    # which is where an empty response or a token-budget problem shows up.
    async def probe(label, model, tokens, prompt):
        try:
            async with httpx.AsyncClient(timeout=60) as c:
                gen = _gen_config(model, tokens, 0.4)
                r = await c.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    headers={"x-goog-api-key": GEMINI_API_KEY,
                             "content-type": "application/json"},
                    json={"contents": [{"parts": [{"text": prompt}]}],
                          "generationConfig": gen})
            body = r.json()
            cands = body.get("candidates") or []
            text = "".join(p.get("text", "") for c_ in cands
                           for p in c_.get("content", {}).get("parts", [])).strip()
            return {"model": model, "http": r.status_code,
                    "chars_returned": len(text),
                    "finish_reason": (cands[0].get("finishReason") if cands else None),
                    "usage": body.get("usageMetadata"),
                    "sample": text[:160],
                    "error": None if r.status_code < 300 else str(body.get("error"))[:300],
                    "ok": r.status_code < 300 and bool(text)}
        except Exception as e:
            return {"model": model, "ok": False,
                    "error": f"{type(e).__name__}: {e}"[:300]}

    # ---- which argument is invalid? --------------------------------
    # "Request contains an invalid argument" names nothing, so vary one
    # thing at a time and let Google's own answers say which it is. This
    # exists because the alternative — reading the sentence and guessing —
    # has already cost several deploys and been wrong every time.
    async def raw_call(model, gen):
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.post(
                    "https://generativelanguage.googleapis.com/v1beta/"
                    f"models/{model}:generateContent",
                    headers={"x-goog-api-key": GEMINI_API_KEY,
                             "content-type": "application/json"},
                    json={"contents": [{"parts": [{"text": "Reply: OK"}]}],
                          "generationConfig": gen})
            body = r.json()
            if r.status_code >= 300:
                return {"http": r.status_code,
                        "error": str(body.get("error", {}).get("message"))[:160]}
            cands = body.get("candidates") or []
            txt = "".join(p.get("text", "") for c_ in cands
                          for p in c_.get("content", {}).get("parts", []))
            return {"http": 200, "chars": len(txt.strip()),
                    "ok": bool(txt.strip())}
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"[:160]}

    base = {"maxOutputTokens": 20, "temperature": 0.4}
    matrix = {
        # What the site actually builds today, rather than a guess at it. This
        # row is the one to read: the others are controls that explain it.
        "AS THE SITE SENDS IT":
            await raw_call(GEMINI_MODEL, _gen_config(GEMINI_MODEL, 20, 0.4)),
        # Control: thinkingConfig forced back on. Expected to fail — that is
        # the whole finding, and it stays here so a regression is obvious.
        "control: thinkingConfig forced on":
            await raw_call(GEMINI_MODEL,
                           dict(base, thinkingConfig={"thinkingBudget": 0})),
        "without thinkingConfig":
            await raw_call(GEMINI_MODEL, dict(base)),
        "nothing but a prompt":
            await raw_call(GEMINI_MODEL, {}),
        # Pinned ids, to separate a bad model name from a bad field.
        "2.5-flash, no thinking":
            await raw_call("gemini-2.5-flash", dict(base)),
        "2.0-flash, no thinking":
            await raw_call("gemini-2.0-flash", dict(base)),
        "2.5-flash-lite, no thinking":
            await raw_call("gemini-2.5-flash-lite", dict(base)),
    }
    works = [k for k, v in matrix.items() if v.get("ok")]
    live_ok = matrix["AS THE SITE SENDS IT"].get("ok")
    matrix["VERDICT"] = (
        "Every variation failed — the key itself is refused, not the payload."
        if not works else
        "Gemini is answering the request this site actually makes."
        if live_ok else
        f"The live request FAILS. These work instead: "
        f"{[w for w in works if not w.startswith('control')]}."
    )

    short = await probe("short", GEMINI_MODEL, 20, "Reply with exactly: OK")
    long_prompt = ("Return ONLY valid JSON: {\"summary\":\"<two sentences about a "
                   "network engineer>\",\"bullets\":[\"a\",\"b\",\"c\"]}")
    long = await probe("long", GEMINI_MODEL_BEST, 1200, long_prompt)

    # The real thing. A toy prompt proves the key works and proves nothing
    # about the call that actually fails — the board sends 15,000 characters
    # and wants 8,000 tokens back, and every difference between those two
    # requests is a place the failure can live.
    board = {"skipped": "no"}
    try:
        import time as _t
        t0 = _t.monotonic()
        raw = await _ai_text(_board_prompt("photosynthesis", "Intermediate"),
                             8000, json_mode=True)
        took = _t.monotonic() - t0
        parsed, lesson, why = None, None, None
        try:
            parsed = _ai_json(raw)
            lesson = _clean_board(parsed, "photosynthesis")
        except Exception as pe:
            why = f"{type(pe).__name__}: {pe}"[:300]
        board = {
            "prompt_chars": len(_board_prompt("photosynthesis", "Intermediate")),
            "seconds": round(took, 1),
            "chars_returned": len(raw or ""),
            "json_parsed": parsed is not None,
            "parse_error": why,
            "steps": len(lesson["steps"]) if lesson else 0,
            "has_drawing": bool(lesson and any(
                st.get("draw") or st.get("sketch") or st.get("scene")
                for st in lesson["steps"])),
            "tail": (raw or "")[-220:],
            "ok": bool(lesson and lesson["steps"]),
        }
    except Exception as e:
        board = {
            "ok": False,
            "error_type": type(e).__name__,
            "error": str(e)[:600],
            "shown_to_user": _ai_error_message(e),
            "per_provider": [{"provider": p, "type": type(x).__name__,
                              "message": str(x)[:300]}
                             for p, x in getattr(e, "fails", [])],
        }

    # The endpoint has two things the probe above does not — the paywall and
    # the cache — and they are the only places left where the board can differ
    # from Ask Axle, which works. So check both directly rather than infer.
    gate = {}
    try:
        require_paid(user, "The smart board")
        gate["entitled"] = True
    except HTTPException as pe:
        gate["entitled"] = False
        gate["refused_with"] = pe.detail
    gate["is_admin"] = bool(getattr(user, "is_admin", False))
    gate["plan"] = plan_of(user)

    rows = db.query(AskCache).filter(AskCache.qkey.like("board|%")).limit(40).all()
    bad = []
    for r in rows:
        try:
            les = json.loads(r.lesson)
            if not isinstance(les, dict) or not les.get("steps"):
                bad.append({"qkey": r.qkey[:70], "why": "no steps"})
        except Exception as je:
            # An unreadable cached row is fatal on every later request for
            # that topic: the endpoint json.loads it before any try block.
            bad.append({"qkey": r.qkey[:70], "why": f"{type(je).__name__}"})
    gate["cached_board_lessons"] = len(rows)
    gate["unreadable_cached_rows"] = bad

    try:
        gate["ai_quota"] = ai_quota(db, user)
    except Exception as qe:
        gate["ai_quota_error"] = str(qe)[:200]

    return {**info,
            "which_argument_is_invalid": matrix,
            "ok": bool(short.get("ok") and long.get("ok") and board.get("ok")),
            "short_call": short,
            "apply_kit_style_call": long,
            "smart_board_call": board,
            "board_endpoint_gates": gate,
            # What real requests did. Empty means none arrived — which
            # would place the fault in the page, not the server.
            "recent_board_requests": list(reversed(_BOARD_TRACE))}


@app.post("/api/ask")
async def ask_vidya(body: AskIn, user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    subject = (body.subject or "General").strip()[:60]
    # Default matches the picker's middle option. It was "School", left over
    # from the class-based levels, so a request without one was prompted for
    # a level the UI no longer offers.
    level = (body.level or "Intermediate").strip()[:60]
    question = body.question.strip()
    scope = _scope_of(db, user)
    qkey = _cl.key(scope, "ask", _norm_q(subject), _norm_q(level),
                   _norm_q(question))[:500]
    _record_learning(db, user, scope, "ask", question, subject, level)

    # 1) Cache hit — free and instant, and counts a hit for the stats.
    row = db.query(AskCache).filter(AskCache.qkey == qkey).first()
    if row:
        row.hits = (row.hits or 0) + 1
        db.commit()
        try:
            lesson = json.loads(row.lesson)
        except Exception:
            lesson = _fallback_lesson(subject, level)
        return {"lesson": lesson, "cached": True}

    # 2) No key configured — degrade gracefully, do not error.
    if not ASK_ENABLED:
        return {"lesson": _fallback_lesson(subject, level),
                "cached": False, "disabled": True}

    # 3) Cache miss — call the model once, then store for everyone.
    try:
        lesson = await _call_model(question, subject, level)
    except Exception as e:
        print(f"Ask Axle call failed ({AI_PROVIDER}): {type(e).__name__}: {e}")
        raise HTTPException(status_code=503, detail=_ai_error_message(e))

    found, verdict = _check_lesson(lesson)
    # The same second pass the board gets. This is the most-used surface on
    # the site, so guarding only the board would be guarding the wrong one.
    review = await _review_lesson(question, lesson)
    if review:
        found = review + found
        if any(r["severity"] == "critical" for r in review):
            verdict = {"cache": False, "confidence": "low", "state": "flagged"}
        elif verdict["confidence"] == "high":
            verdict = dict(verdict, confidence="medium", state="checked")
    if found:
        print(f"Checks on ask {question[:60]!r}: {verdict['state']} — "
              f"{found[0]['problem'][:120]}")
        lesson["findings"] = _note_findings(found)
        lesson["confidence"] = verdict["confidence"]
    if not verdict["cache"]:
        # Shown once, never served to anybody else.
        return {"lesson": lesson, "cached": False, "checked": verdict["state"]}

    db.add(AskCache(qkey=qkey, subject=subject, level=level,
                    question=question[:2000], lesson=json.dumps(lesson), hits=0))
    try:
        db.commit()
    except IntegrityError:
        # The last unguarded commit on the site. Two people asking the same
        # question in the same second raced, and one of them got a 500 while
        # the answer they wanted sat in memory.
        db.rollback()
    return {"lesson": lesson, "cached": False}


# ---------------------------- live jobs -----------------------------------
# Jobs come from the PUBLIC APIs that companies' own career pages are built
# on (Greenhouse, Lever, Ashby, Workable, Recruitee). They are the real
# postings, straight from the employer, free and without an API key. We never
# scrape LinkedIn/Indeed/Naukri: that breaks their terms and gets blocked.

JOBS_PER_COMPANY = int(env("JOBS_PER_COMPANY", "3") or 3)

# What running this actually costs, in rupees per month. These are your real
# bills — change them here and the admin profit figure follows. Kept as
# settings rather than guesses so the number on screen is yours, not mine.
COST_HOSTING_INR = float(env("COST_HOSTING_INR", "1700") or 1700)   # Railway
COST_DOMAIN_INR = float(env("COST_DOMAIN_INR", "100") or 100)       # amortised
COST_OTHER_INR = float(env("COST_OTHER_INR", "0") or 0)
# Stripe on an Indian account, billing in USD: 4.3% international card rate,
# plus 2% to convert USD to INR at settlement, plus 18% GST on Stripe's fee.
# That is roughly 7.4% all-in — far more than the 2.36% a domestic rupee
# gateway cost, and enough to move the profit line, so it is not rounded down.
# Override with GATEWAY_FEE_PCT once real settlements show the true number.
GATEWAY_FEE_PCT = float(env("GATEWAY_FEE_PCT", "7.4") or 7.4)
GST_RATE_PCT = float(env("GST_RATE_PCT", "18") or 18)
USD_INR = float(env("USD_INR", "88") or 88)
# A month of history. Anything a user saved or applied to is exempt from the
# sweep entirely — see _protected_job_ids.
JOB_RETENTION_DAYS = int(env("JOB_RETENTION_DAYS", "30") or 30)
# Hourly, not daily. Being early is what wins an interview, and it is what Pro
# sells — a board refreshed once a day is up to 24 hours stale at the worst
# moment. Override with JOB_REFRESH_HOURS if the crawl ever gets expensive.
JOB_REFRESH_HOURS = float(env("JOB_REFRESH_HOURS", "1") or 1)

# Crawl only during working hours, in the business's own timezone. Employers
# post during the day, so crawling at 3am buys nothing and — with a metered
# source like JSearch — costs real money for it.
#   JOB_ACTIVE_START / JOB_ACTIVE_END : local hours, END is exclusive
#   JOB_TZ_OFFSET                     : hours from UTC (-5 = US Central, CDT)
# Set JOB_ACTIVE_START == JOB_ACTIVE_END to crawl around the clock.
JOB_ACTIVE_START = int(env("JOB_ACTIVE_START", "6") or 6)
JOB_ACTIVE_END = int(env("JOB_ACTIVE_END", "17") or 17)
JOB_TZ_OFFSET = float(env("JOB_TZ_OFFSET", "-5") or -5)


_CRAWL_MODES = ("window", "always", "off")


def _crawl_mode() -> str:
    """How the crawler should behave: inside its hours, always, or not at all.

    Read from the database on every check rather than cached, so flipping the
    switch takes effect on the next loop rather than on the next deploy.
    Falls back to the configured window if anything goes wrong — a broken
    query should not silently stop the board updating.
    """
    db = SessionLocal()
    try:
        row = db.get(SysCounter, "crawl_mode_v")
        return _CRAWL_MODES[row.v] if row and 0 <= (row.v or 0) < 3 else "window"
    except Exception:
        return "window"
    finally:
        db.close()


def _crawl_window_wait():
    """Seconds to wait before the next crawl.

    Returns 0 when we are inside the window — the caller then sleeps its normal
    interval. Outside it, returns the time until the window opens, so the loop
    parks instead of waking hourly to do nothing.
    """
    # Manual override, set from the admin panel and stored in the database so
    # it survives a restart. Before launch you want to crawl at 8pm because
    # you are working at 8pm; the window exists to stop the board burning API
    # quota overnight once real users are on it.
    mode = _crawl_mode()
    if mode == "off":
        return 3600.0                      # check again in an hour
    if mode == "always":
        return 0.0
    if JOB_ACTIVE_START == JOB_ACTIVE_END:
        return 0.0
    local = now() + dt.timedelta(hours=JOB_TZ_OFFSET)
    h = local.hour
    inside = (JOB_ACTIVE_START <= h < JOB_ACTIVE_END
              if JOB_ACTIVE_START < JOB_ACTIVE_END
              else (h >= JOB_ACTIVE_START or h < JOB_ACTIVE_END))  # window over midnight
    if inside:
        return 0.0
    nxt = local.replace(hour=JOB_ACTIVE_START, minute=0, second=0, microsecond=0)
    if nxt <= local:
        nxt += dt.timedelta(days=1)
    return max(60.0, (nxt - local).total_seconds())

# Board tokens. A company that renames or leaves its ATS simply stops
# returning rows — the fetcher skips it silently and the rest still work.
# Extend without touching code: JOB_GREENHOUSE="stripe,figma,..." etc.
# Every token below was curl-verified against boards-api.greenhouse.io
# before it was added, with the job count it returned. Guessing slugs once
# put 153 dead tokens in this list, so nothing goes in unanswered.
_GREENHOUSE = ("anthropic,block,zscaler,purestorage,netskope,"
               "abnormalsecurity,hightouch,newrelic,fastly,pagerduty,"
               "yugabyte,dremio,netlify,"
               "stripe,figma,databricks,cloudflare,coinbase,robinhood,"
               "dropbox,reddit,discord,brex,instacart,lyft,pinterest,twilio,"
               "asana,samsara,affirm,chime,flexport,gitlab,airtable,"
               "amplitude,mixpanel,vercel,scaleai,duolingo,gusto,carta,"
               "squarespace,fivetran,verkada,checkr,betterment,elastic,"
               "mongodb,postman,airbnb,datadog,okta,starburst,cockroachlabs,"
               "neo4j,planetscale,knock,tailscale,faire,hootsuite,ritual,"
               "tulip,"
               # Checked live before adding: netbrain carries Network
               # Automation Engineer, kentik Network Intelligence
               # Advisor, cribl Site Reliability Engineer.
               "netbrain,kentik,cribl")
_LEVER = ("palantir,cred,meesho,nium,matchgroup,alloy,veeva,shieldai,"
          "relay,d2l,wattpad,knix")
_ASHBY = ("openai,ramp,linear,vanta,replit,clickhouse,supabase,cursor,"
          "elevenlabs,decagon,mercor,sierra,suno,perplexity,zed,harvey,"
          "modal,warp,browserbase,lovable,synthesia,cognition,"
          "fireworksai,baseten,langchain,n8n,runway,character,writer,"
          "deepgram,pinecone,weaviate,llamaindex,crusoe,abridge,"
          "openevidence,hyperbolic")
# No verified public boards seeded for these two, but the fetchers are live —
# add tokens with JOB_WORKABLE / JOB_RECRUITEE and they start working.
_WORKABLE = ""
_RECRUITEE = ""

# Workday tenants as "tenant|site|host". Every one below was verified to
# return postings; the site and host segments differ per company and are not
# guessable, so add new ones only after checking they respond.
_WORKDAY = ",".join([
    "nvidia|NVIDIAExternalCareerSite|wd5",
    "salesforce|External_Career_Site|wd12",
    "adobe|external_experienced|wd5",
    "mastercard|CorporateCareers|wd1",
    "astrazeneca|Careers|wd3",
    "autodesk|Ext|wd1",
    "ebay|apply|wd5",
    "workday|Workday|wd5",
    "paypal|jobs|wd1",
])

# SmartRecruiters slugs are the company's public careers identifier. Large
# US/Canada employers with sizeable IT and cyber organisations — these are
# where the non-startup technical roles live, including plenty of contract and
# W2 postings that never reach the startup ATS boards.
_SMARTRECRUITERS = ("Visa,Experian,NielsenIQ,BoschGroup")


def _job_tokens(name):
    raw = env(f"JOB_{name.upper()}", {"greenhouse": _GREENHOUSE, "lever": _LEVER,
                                      "ashby": _ASHBY, "workable": _WORKABLE,
                                      "recruitee": _RECRUITEE,
                                      "workday": _WORKDAY,
                                      "smartrecruiters": _SMARTRECRUITERS}[name])
    return [t.strip() for t in raw.split(",") if t.strip()]


# Country detection from a free-text location string. ATS feeds write
# locations however they like ("Bengaluru, India", "SF Bay Area", "Remote").
_COUNTRY_ALIASES = {
    "india": "India", "bengaluru": "India", "bangalore": "India",
    "mumbai": "India", "delhi": "India", "gurgaon": "India", "gurugram": "India",
    "hyderabad": "India", "chennai": "India", "pune": "India", "noida": "India",
    "kolkata": "India", "ahmedabad": "India", "jaipur": "India", "kochi": "India",
    "united states": "United States", "usa": "United States", "u.s.": "United States",
    "us": "United States", "new york": "United States", "san francisco": "United States",
    "seattle": "United States", "austin": "United States", "boston": "United States",
    "chicago": "United States", "los angeles": "United States", "denver": "United States",
    "atlanta": "United States", "bay area": "United States",
    "united kingdom": "United Kingdom", "uk": "United Kingdom",
    "london": "United Kingdom", "manchester": "United Kingdom",
    "canada": "Canada", "toronto": "Canada", "vancouver": "Canada",
    "montreal": "Canada", "germany": "Germany", "berlin": "Germany",
    "munich": "Germany", "france": "France", "paris": "France",
    "netherlands": "Netherlands", "amsterdam": "Netherlands",
    "ireland": "Ireland", "dublin": "Ireland", "spain": "Spain",
    "madrid": "Spain", "barcelona": "Spain", "poland": "Poland",
    "warsaw": "Poland", "sweden": "Sweden", "stockholm": "Sweden",
    "switzerland": "Switzerland", "zurich": "Switzerland",
    "australia": "Australia", "sydney": "Australia", "melbourne": "Australia",
    "singapore": "Singapore", "japan": "Japan", "tokyo": "Japan",
    "brazil": "Brazil", "sao paulo": "Brazil", "mexico": "Mexico",
    "israel": "Israel", "tel aviv": "Israel", "uae": "United Arab Emirates",
    "dubai": "United Arab Emirates",
}
# Two-letter US state codes, so "Austin, TX" resolves to the United States.
_US_STATES = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD "
                 "MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC "
                 "SD TN TX UT VT VA WA WV WI WY DC".split())


# Longest alias first, so "united states" wins before "us", and each is
# matched on word boundaries — plain substring matching would read "us" out
# of "Austin" and "Belarus" and label them United States.
_ALIAS_RE = [(_re.compile(rf"(?<![a-z]){_re.escape(a)}(?![a-z])"), c)
             for a, c in sorted(_COUNTRY_ALIASES.items(),
                                key=lambda kv: -len(kv[0]))]


def _country_of(location: str) -> str:
    """Best-effort country from a free-text location. '' when unknown."""
    loc = (location or "").strip()
    if not loc:
        return ""
    low = loc.lower()
    for rx, country in _ALIAS_RE:
        if rx.search(low):
            return country
    tail = loc.replace(",", " ").split()
    if tail and tail[-1].upper() in _US_STATES:
        return "United States"
    return ""


def _is_remote(location: str) -> bool:
    low = (location or "").lower()
    return "remote" in low or "anywhere" in low or "distributed" in low


def _strip_html(s: str) -> str:
    return _re.sub(r"<[^>]+>", " ", s or "").replace("&amp;", "&") \
             .replace("&nbsp;", " ").replace("&#39;", "'")


def _job_type_of(blob: str) -> str:
    """Full-time / contract / part-time / internship, read from the posting."""
    if _re.search(r"\b(intern|internship|co-op|apprentice)\b", blob):
        return "internship"
    if _re.search(r"\b(contract|contractor|contract-to-hire|c2h|freelance|"
                  r"temporary|temp\b|fixed[- ]term|consultant role)\b", blob):
        return "contract"
    if _re.search(r"\bpart[- ]time\b", blob):
        return "parttime"
    if _re.search(r"\b(full[- ]time|permanent|fte)\b", blob):
        return "fulltime"
    return ""


def _engagement_of(blob: str) -> str:
    """US staffing engagement model: W2, corp-to-corp, or 1099.

    Staffing posts say this explicitly ('W2 only', 'C2C welcome') and it
    decides whether a candidate can even take the role, so it is worth
    filtering on separately from the contract/full-time split."""
    c2c = _re.search(r"\b(c2c|corp[- ]to[- ]corp|corp2corp)\b", blob)
    w2 = _re.search(r"\bw-?2\b", blob)
    # "W2 only, no corp-to-corp" contains both terms and means the opposite of
    # both. A posting that says no to C2C was being filed as accepting it,
    # which sends contractors to a role that will not take them.
    if c2c and _re.search(r"\b(no|not?|without|non)[- ]?(c2c|corp[- ]to[- ]corp|"
                          r"corp2corp)\b", blob):
        c2c = None
    # Contract-to-hire is its own thing: a contract that converts. Neither the
    # contract nor the permanent filter finds it, so it needs naming.
    if _re.search(r"\b(c2h|contract[- ]to[- ]hire|temp[- ]to[- ](hire|perm))\b", blob):
        return "c2h"
    if c2c and w2:
        return "w2_c2c"
    if c2c:
        return "c2c"
    if w2:
        return "w2"
    if _re.search(r"\b1099\b", blob):
        return "1099"
    return ""


def _visa_of(blob: str) -> str:
    """Sponsorship stance. 'no' is as useful to a candidate as 'sponsors' —
    it saves them an application that was never going to work."""
    if _re.search(r"\b(security clearance|ts/sci|secret clearance|polygraph)\b", blob):
        return "clearance"
    # Citizenship is a harder gate than sponsorship and was folded in with it,
    # so a role nobody on a visa can take read the same as one that merely
    # will not sponsor. Named separately because it is the difference between
    # "apply anyway" and "do not bother".
    if _re.search(r"(u\.?s\.? citizenship (is )?required|must be a u\.?s\.? citizen|"
                  r"citizenship (is )?required|u\.?s\.? citizens? only|"
                  r"american citizens? only|us citizens? required)", blob):
        return "citizen"
    if _re.search(r"(no (visa )?sponsorship|not able to sponsor|unable to sponsor|"
                  r"without sponsorship|cannot sponsor|no c2c|us citizens? only|"
                  r"green card holders? only|citizens? or green card)", blob):
        return "no_sponsorship"
    if _re.search(r"\b(h-?1b|h1-b|opt\b|cpt\b|ead\b|tn visa|e-?3 visa|"
                  r"visa sponsorship( is)? available|will sponsor|"
                  r"sponsorship (is )?(available|provided|offered))\b", blob):
        return "sponsors"
    return ""


# The headings real job ads use before they list what they actually want.
_REQ_HEADING = _re.compile(
    r"(requirement|qualification|what you.{0,4}ll (need|bring|do)|who you are|"
    r"skills|responsibilit|about you|must have|we.{0,4}re looking for|"
    r"experience with|your profile|what we.{0,4}re looking for)", _re.I)


def _requirement_text(blob: str) -> str:
    """The part of a posting that states what the job needs.

    Everything from the first requirements-ish heading onward, stopping at the
    benefits/EEO boilerplate that follows. Falls back to the whole text when a
    posting has no headings, so nothing is ever scored on an empty string.
    """
    if not blob:
        return ""
    m = _REQ_HEADING.search(blob)
    if not m:
        return blob
    tail = blob[m.start():]
    stop = _re.search(
        r"(equal opportunity|benefits|perks|we offer|compensation|"
        r"about (us|the company)|diversity|accommodation)", tail, _re.I)
    return tail[:stop.start()] if stop and stop.start() > 200 else tail


_SALARY_RES = [
    # "$120,000 - $150,000 a year" / "$120k-$150k"
    _re.compile(r"\$\s?\d{2,3}(?:,\d{3})?(?:\.\d+)?\s?[kK]?\s?(?:-|–|to)\s?"
                r"\$?\s?\d{2,3}(?:,\d{3})?(?:\.\d+)?\s?[kK]?"
                r"(?:\s?(?:per|an|a|/)\s?(?:year|yr|annum|hour|hr))?", _re.I),
    # "$65 per hour" / "$65/hr"
    _re.compile(r"\$\s?\d{2,3}(?:\.\d+)?\s?(?:per\s?hour|/\s?hr|/\s?hour|an hour)", _re.I),
    # "$120,000 per year"
    _re.compile(r"\$\s?\d{2,3},\d{3}(?:\s?(?:per|a)\s?(?:year|yr|annum))?", _re.I),
]


# A number of years, then either a "+" or the word experience within a few
# words. Requiring "experience" immediately after missed "12 Years of exp
# Required" and "5+ years, 10 preferred"; dropping it entirely matched "3
# years ago". The lookbehind stops "100 years" being read as 10.
_YEARS_RE = _re.compile(
    # The upper half of a range only counts when a dash or "to" introduces it.
    # Left optional on its own it swallowed the "00" of "100 years", turning
    # an absurd number into a plausible 10.
    r"(?<!\d)(\d{1,2})\s*(\+)?\s*(?:(?:[-–]|to)\s*\d{1,2}\s*\+?\s*)?"
    r"(?:years?|yrs?)\b(?:[^.\n]{0,28}?\b(experience|exp)\b)?", _re.I)


def _years_matches(text):
    """Every stated year-count that is really about experience."""
    out = []
    for num, plus, word in _YEARS_RE.findall(text or ""):
        if not (plus or word):
            continue                      # "3 years ago" is not a requirement
        n = int(num)
        if 0 < n <= 25:
            out.append(n)
    return out


def _years_required(text):
    """Years of experience a posting asks for, or 0 when it does not say.

    Takes the LOWEST number stated. "8 to 12 years" and "5+ years, 10
    preferred" are both asking for the first one; scoring someone out on the
    upper bound of a range would reject people the employer would interview.
    """
    got = _years_matches(text)
    return min(got) if got else 0


def _salary_from(text):
    """Pull a stated pay range out of a posting, or return blank.

    Only patterns anchored on a currency symbol — plain numbers in a job ad are
    far more often headcount, revenue or a version number than pay. Nothing is
    inferred: if the employer did not say, the field stays empty.
    """
    t = (text or "")[:6000]
    for rx in _SALARY_RES:
        for m in rx.finditer(t):
            got = _re.sub(r"\s+", " ", m.group(0)).strip()[:120]
            # A dollar sign is not a wage. Job ads are full of money that is
            # not pay — sign-on bonuses, equity grants, relocation, 401k
            # matching, and the company's own funding round. "$10,000 signing
            # bonus" was being shown as the salary.
            before = t[max(0, m.start() - 34):m.start()].lower()
            if _re.search(r"(salary|base pay|base compensation|pay range|"
                          r"compensation range|rate of|pay rate|hourly rate)",
                          before):
                return got                      # the ad says what this is
            around = t[max(0, m.start() - 34):m.end() + 26].lower()
            if _re.search(r"(bonus|equity|rsu|stock|option|grant|relocation|"
                          r"401\s?k|match(ing)?|raised|funding|valuation|"
                          r"revenue|budget|scholarship|prize|tuition|"
                          r"reimburse|stipend|allowance)", around):
                continue
            # "$10,000,000 in funding" matched as "$10,000" because the regex
            # stopped at the first group. If digits or another comma follow,
            # we read only part of a larger number.
            tail = t[m.end():m.end() + 2]
            if _re.match(r"[,\d]", tail):
                continue
            # A yearly figure below $20,000 is not a US technical salary, so
            # it is a bonus, a fee or a typo. Hourly and ranges are exempt —
            # "$65 per hour" and "$60 - $70" are both plainly rates.
            if not _re.search(r"(hour|hr|/\s?h|-|\u2013|to)", got.lower()):
                digits = _re.sub(r"[^0-9]", "", got.split("-")[0])
                if digits and int(digits) < 20000:
                    continue
            return got
    return ""


def _job_row(source, ext_id, title, company, location, url, desc="", posted=None):
    """Normalise one posting into the shape the refresh loop stores."""
    title, company = (title or "").strip()[:300], (company or "").strip()[:200]
    location = (location or "").strip()[:200]
    if not title or not url:
        return None
    blob = f"{title} {company} {location} {_strip_html(desc)}".lower()
    blob = _re.sub(r"\s+", " ", blob)[:4000]
    return {
        "source": source, "external_id": str(ext_id)[:200], "title": title,
        "company": company, "location": location,
        "country": _country_of(location), "remote": _is_remote(location),
        "category": _primary_family(title, blob),
        "job_type": _job_type_of(blob), "engagement": _engagement_of(blob),
        "salary": _salary_from(desc) or _salary_from(title),
        "min_years": _years_required(blob),
        # Kept as written, only stripped of markup and capped — an employer's
        # own words are what somebody needs to decide whether to apply.
        "description": _re.sub(r"\n{3,}", "\n\n",
                               _strip_html(desc or "")).strip()[:9000],
        "visa": _visa_of(blob),
        "skills": ",".join(sorted({w for w in _words(blob) if w in _SKILLS})),
        "req_skills": ",".join(sorted(
            {w for w in _words(_requirement_text(blob)) if w in _SKILLS})),
        "url": url[:1000], "text": blob,
        "posted_at": posted,
    }


def _ts(v):
    """Parse the assorted timestamp shapes the ATS feeds use."""
    if not v:
        return None
    try:
        if isinstance(v, (int, float)):
            d = dt.datetime.fromtimestamp(v / (1000 if v > 1e11 else 1), dt.timezone.utc)
        else:
            d = dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except Exception:
        return None
    # A date is only useful if it is plausible. Feeds send epoch values in the
    # wrong unit, placeholder dates and occasional garbage — the board was
    # carrying a posting dated 4,891 days ago, which is not an old job, it is
    # a parse failure being displayed as fact. Anything in the future or more
    # than two years back is discarded, and the card then says "added" with
    # our own timestamp rather than stating something false.
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    n = now()
    if d > n + dt.timedelta(days=2) or d < n - dt.timedelta(days=730):
        return None
    return d


async def _fetch_greenhouse(client, token):
    r = await client.get(
        f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true")
    r.raise_for_status()
    out = []
    for j in (r.json().get("jobs") or []):
        out.append(_job_row("greenhouse", j.get("id"), j.get("title"), token,
                            (j.get("location") or {}).get("name", ""),
                            j.get("absolute_url", ""), j.get("content", ""),
                            _ts(j.get("updated_at"))))
    return out


async def _fetch_lever(client, token):
    r = await client.get(f"https://api.lever.co/v0/postings/{token}?mode=json")
    r.raise_for_status()
    out = []
    for j in r.json():
        cat = j.get("categories") or {}
        out.append(_job_row("lever", j.get("id"), j.get("text"), token,
                            cat.get("location", ""), j.get("hostedUrl", ""),
                            j.get("descriptionPlain", ""), _ts(j.get("createdAt"))))
    return out


async def _fetch_ashby(client, token):
    r = await client.get(
        f"https://api.ashbyhq.com/posting-api/job-board/{token}")
    r.raise_for_status()
    out = []
    for j in (r.json().get("jobs") or []):
        out.append(_job_row("ashby", j.get("id"), j.get("title"), token,
                            j.get("location", ""), j.get("jobUrl", ""),
                            j.get("descriptionPlain", ""), _ts(j.get("publishedAt"))))
    return out


async def _fetch_workable(client, token):
    r = await client.get(
        f"https://apply.workable.com/api/v1/widget/accounts/{token}?details=true")
    r.raise_for_status()
    out = []
    for j in (r.json().get("jobs") or []):
        loc = ", ".join(x for x in [j.get("city", ""), j.get("country", "")] if x)
        out.append(_job_row("workable", j.get("shortcode"), j.get("title"), token,
                            loc, j.get("url", ""), j.get("description", ""),
                            _ts(j.get("published_on"))))
    return out


async def _fetch_recruitee(client, token):
    r = await client.get(f"https://{token}.recruitee.com/api/offers/")
    r.raise_for_status()
    out = []
    for j in (r.json().get("offers") or []):
        loc = ", ".join(x for x in [j.get("city", ""), j.get("country", "")] if x)
        out.append(_job_row("recruitee", j.get("id"), j.get("title"), token,
                            loc, j.get("careers_url", ""), j.get("description", ""),
                            _ts(j.get("published_at"))))
    return out


# 20 postings a page. Every tenant was returning exactly 300 — the cap, not
# the real count. Large US employers list far more than that, and Workday is
# where the non-startup and contract roles are, so this was truncating the
# most valuable source. The fetcher stops early when a page comes back short,
# so a small tenant costs nothing extra.
WORKDAY_PAGES = int(env("WORKDAY_PAGES", "50") or 50)


async def _fetch_workday(client, token):
    """Workday's own public jobs endpoint — the one its career sites call.

    Token is "tenant|site|host", e.g. "nvidia|NVIDIAExternalCareerSite|wd5".
    This is the documented CxS JSON endpoint that every Workday career page
    fetches from, not HTML scraping: no parsing of markup, nothing that
    breaks when they restyle the page.
    """
    tenant, site, host = (token.split("|") + ["wd1"])[:3]
    base = f"https://{tenant}.{host}.myworkdayjobs.com"
    out = []
    for page in range(WORKDAY_PAGES):
        r = await client.post(
            f"{base}/wday/cxs/{tenant}/{site}/jobs",
            json={"appliedFacets": {}, "limit": 20, "offset": page * 20,
                  "searchText": ""})
        r.raise_for_status()
        posts = r.json().get("jobPostings") or []
        if not posts:
            break
        for j in posts:
            path = j.get("externalPath") or ""
            out.append(_job_row(
                "workday", f"{tenant}:{path}",
                j.get("title"), tenant.title(), j.get("locationsText", ""),
                f"{base}/en-US/{site}{path}", j.get("title", ""),
                _ts(j.get("postedOn"))))
    return out


async def _fetch_smartrecruiters(client, company):
    """SmartRecruiters' official public postings API."""
    out = []
    for page in range(5):
        r = await client.get(
            f"https://api.smartrecruiters.com/v1/companies/{company}/postings",
            params={"limit": 100, "offset": page * 100})
        r.raise_for_status()
        items = r.json().get("content") or []
        if not items:
            break
        for j in items:
            loc = j.get("location") or {}
            where = ", ".join(x for x in (loc.get("city"), loc.get("region"),
                                          loc.get("country")) if x)
            out.append(_job_row(
                "smartrecruiters", j.get("id"), j.get("name"),
                (j.get("company") or {}).get("identifier", company),
                where or ("Remote" if loc.get("remote") else ""),
                f"https://jobs.smartrecruiters.com/{company}/{j.get('id')}",
                (j.get("jobAd") or {}).get("sections", {}).get(
                    "jobDescription", {}).get("text", "") or j.get("name", ""),
                _ts(j.get("releasedDate"))))
    return out


_FETCHERS = {"greenhouse": _fetch_greenhouse, "lever": _fetch_lever,
             "ashby": _fetch_ashby, "workable": _fetch_workable,
             "recruitee": _fetch_recruitee, "workday": _fetch_workday,
             "smartrecruiters": _fetch_smartrecruiters}

# ---- aggregators: every sector, every country, but they need a free key ----
# Company ATS boards only ever cover the companies we list, and those skew
# heavily to tech. Adzuna and Jooble are what make this a general job board:
# nursing, teaching, driving, retail, accounting, in dozens of countries.
ADZUNA_APP_ID = env("ADZUNA_APP_ID")
ADZUNA_APP_KEY = env("ADZUNA_APP_KEY")
JOOBLE_KEY = env("JOOBLE_KEY")

# JSearch (RapidAPI) aggregates Google for Jobs, which reaches the staffing and
# contract listings company ATS boards never carry. It is PAID and metered per
# request, so the cost is spelled out here: one request per query per country
# per page. The defaults are 8 queries x 2 countries x 1 page = 16 requests a
# crawl, 64 a day at JOB_REFRESH_HOURS=6. Raise JSEARCH_PAGES only if the plan
# has room — it multiplies everything.
JSEARCH_KEY = env("JSEARCH_KEY") or env("RAPIDAPI_KEY")
# Override if the provider moves or you switch back to the RapidAPI
# listing, which needs X-RapidAPI-Key / X-RapidAPI-Host instead.
JSEARCH_BASE = env("JSEARCH_BASE",
                   "https://api.openwebninja.com/jsearch/search-v2")
# 1-20: the provider's own ceiling. Asking for more is not an error you can
# see — the request simply comes back with what it feels like returning, so a
# typo of 90 quietly costs the same as 20 and looks like a bad day.
JSEARCH_PAGES = max(1, min(20, int(env("JSEARCH_PAGES", "1") or 1)))
JSEARCH_QUERIES = [q.strip() for q in (env(
    "JSEARCH_QUERIES",
    "cloud infrastructure engineer,enterprise architect,cloud solutions"
    " architect,network security engineer,systems administrator,virtual"
    "ization engineer,it infrastructure manager,data center technician,"
    "storage engineer,migration specialist,devops engineer,site reliabi"
    "lity engineer,release manager,build automation engineer,platform e"
    # Networking had five slots and none of them was "network engineer".
    # Everything a posting for this work is actually titled, because the
    # provider matches on the title we send and nothing else.
    "ngineer,network engineer,senior network engineer,junior network en"
    "gineer,network administrator,network architect,network operations "
    "engineer,noc engineer,network support engineer,wireless network en"
    "gineer,data center network engineer,network automation engineer,sd"
    " wan engineer,voip engineer,unified communications engineer,teleco"
    "m network engineer,field network engineer,routing and switching en"
    "gineer,"
    "kubernetes administrator,ci cd pipeline architect,full sta"
    "ck developer,backend engineer,frontend developer,mobile developer,"
    "api integration specialist,embedded systems engineer,game develope"
    "r,cms developer,machine learning engineer,ai prompt engineer,data "
    "scientist,data engineer,database administrator,big data architect,"
    "business intelligence analyst,nlp engineer,cybersecurity analyst,p"
    "enetration tester,soc analyst,identity access management engineer,"
    "information security manager,cloud security architect,it complianc"
    "e auditor,technical product manager,scrum master,agile coach,ui ux"
    " designer,technical writer,systems analyst,business analyst,"
    "qa automation engineer,"
    "it project manager,help desk technician,it support specialist,appl"
    "ication support analyst,desktop support engineer,incident manager,"
    "webmaster,security operations center analyst,"
    # The paid API earns its money on what the free scrapers cannot
    # reach. Stripe, Databricks and OpenAI post permanent staff roles on
    # Greenhouse and Ashby and never post corp-to-corp work at all, so
    # repeating those titles here buys listings we already hold. These go
    # after the staffing market — the half of the board nothing else
    # reaches, and the half this product is for.
    "network engineer contract,c2c network engineer,"
    "corp to corp devops engineer,contract cloud engineer,"
    "c2c data engineer,contract security engineer,"
    "w2 contract systems engineer,contract python developer,"
    "c2c java developer,contract to hire network administrator,"
    "c2c business analyst,contract qa engineer"
    ) or "").split(",") if q.strip()]

# 53 titles is far more than one crawl should pay for, so each crawl takes
# the next slice and the list wraps. Every title is still covered every
# day at JOB_REFRESH_HOURS=6, at a quarter of the request cost — and a
# posting missed this crawl is picked up four hours later, which for a
# job board is no difference at all.
# "auto" spends whatever the plan can still afford this month, which is what
# you want on a board: buying a bigger plan should mean more jobs without
# anyone remembering to retune a number. A plain integer pins it instead.
JSEARCH_PER_CRAWL_RAW = (env("JSEARCH_PER_CRAWL", "auto") or "auto").strip().lower()
JSEARCH_PER_CRAWL = (0 if JSEARCH_PER_CRAWL_RAW in ("auto", "")
                     else int(JSEARCH_PER_CRAWL_RAW))
# A hard monthly ceiling on paid requests, set BELOW the plan so the cap bites
# before the bill does. The RapidAPI Pro tier is 10,000 a month; at 11 crawls
# a day and 14 queries each this uses about 4,600, so 9,000 leaves headroom
# for a manual refresh without ever reaching an overage. Raise it only
# alongside the plan itself.
JSEARCH_MONTHLY_CAP = int(env("JSEARCH_MONTHLY_CAP", "9000") or 9000)
# JSearch runs on every Nth crawl, not every one. The free ATS boards are
# worth reading hourly because they cost nothing; JSearch is metered, and
# page 1 returns the same ten jobs an hour later. Spending the same budget on
# fewer, deeper visits reaches roles that shallow hourly paging never sees:
# 12 crawls x 3 pages and 4 crawls x 9 pages cost about the same, and the
# second reads nine pages deep instead of three.
JSEARCH_EVERY_CRAWLS = max(1, int(env("JSEARCH_EVERY_CRAWLS", "1") or 1))

# How deep each query walks before starting over.
#
# The page number used to be hardcoded to 1, so every crawl bought the same
# first ten results for a role, forever. Results 11 and beyond were never
# reached and the board plateaued around three hundred JSearch rows no matter
# how much of the plan was spent — the requests went out, were paid for, and
# came back with rows already stored.
#
# Now each query remembers where it got to and resumes there next crawl,
# wrapping back to page 1 at the end so genuinely new postings still get
# caught. Depth costs nothing extra: one request is one page either way, so
# this reaches ten times as many distinct jobs for the same monthly spend.
JSEARCH_DEPTH = max(1, min(20, int(env("JSEARCH_DEPTH", "10") or 10)))
# How many JSearch requests are in flight at once. Kept well below the board
# sweep's twelve: this one is metered and paid for, and a provider that
# decides we are hammering it answers 429 for the rest of the crawl.
JSEARCH_CONCURRENCY = max(1, min(12, int(env("JSEARCH_CONCURRENCY", "6") or 6)))
# Seconds to wait for one JSearch response. The provider fetches every
# requested page before replying, so the wait grows with JSEARCH_PAGES.
JSEARCH_TIMEOUT = float(env("JSEARCH_TIMEOUT", "0") or 0) or max(30.0, 12.0 * JSEARCH_PAGES)
# How long the whole board sweep gets. Named rather than computed inline so a
# test can shorten it: the branch worth testing is the one that runs out of
# clock, and that is not testable if the floor is ten minutes.
BOARD_STAGE_CAP = float(env("BOARD_STAGE_CAP", "0") or 0) or max(600.0, JSEARCH_TIMEOUT * 6)
_CRAWL_TICK = 0


def _jsearch_used(db, add=0):
    """Requests made this calendar month, optionally adding to the count."""
    k = f"jsearch_{now().strftime('%Y%m')}"
    row = db.get(SysCounter, k)
    if row is None:
        row = SysCounter(k=k, v=0)
        db.add(row)
        db.commit()
    if add:
        row.v = (row.v or 0) + add
        db.commit()
    return row.v or 0
_JSEARCH_CURSOR = 0
# Decided once per process from how much of the board has parsed skills.
# None means "not measured yet".
_DEFER_TEXT = None


def _jsearch_auto_n(used: int) -> int:
    """How many queries this crawl can afford, from what is left this month.

    A fixed slice either underspends a big plan for the whole month or burns
    a small one by the 20th. This divides what remains by the crawls that
    remain, so the allowance lands evenly on the last day of the month and a
    larger plan turns into more jobs by itself. Every role every crawl is the
    ceiling — past that there is nothing left to ask for.
    """
    left = JSEARCH_MONTHLY_CAP - used
    if left <= 0:
        return 0
    n = now()
    days_in_month = calendar.monthrange(n.year, n.month)[1]
    every = max(0.5, JOB_REFRESH_HOURS)
    active = (JOB_ACTIVE_END - JOB_ACTIVE_START) or 24
    per_day = max(1, int(active / every))
    # Crawls left today, plus every crawl on the days after this one.
    crawls_left = max(1, int(max(0, JOB_ACTIVE_END - n.hour) / every)) \
        + (days_in_month - n.day) * per_day
    budget = left // crawls_left
    return max(1, budget // max(1, JSEARCH_PAGES))


def _jsearch_page(db, query: str) -> int:
    """Where this query got to last time, then move it on one page.

    Per query rather than one global counter: the queries a crawl runs are a
    rotating slice, so a shared counter would give "devops engineer" page 3
    and "soc analyst" page 7 by accident and never cover either properly.

    Stored, because an in-process counter resets on every deploy — which is
    how paging can look implemented and still only ever fetch page 1.
    """
    k = f"jspage:{query[:80]}"
    row = db.get(SysCounter, k)
    if row is None:
        row = SysCounter(k=k, v=0)
        db.add(row)
    row.v = turn = (row.v or 0) + 1
    db.commit()
    # Alternate. A straight walk down ten pages meant each role was asked
    # what went up TODAY once every ten crawls — at four-hourly crawls, a
    # posting could be a day and a half old before we asked the question it
    # would have answered. Odd turns take page 1, which is where today is;
    # even turns take the next page down, so the depth still gets covered.
    if turn % 2:
        return 1
    return 2 + (turn // 2 - 1) % max(1, JSEARCH_DEPTH - 1)


def _jsearch_slice(used: int = 0):
    """The queries this crawl should run, advancing the cursor."""
    global _JSEARCH_CURSOR
    qs = JSEARCH_QUERIES
    if not qs:
        return []
    want = JSEARCH_PER_CRAWL or _jsearch_auto_n(used)
    n = max(1, min(want, len(qs)))
    out = [qs[(_JSEARCH_CURSOR + i) % len(qs)] for i in range(n)]
    _JSEARCH_CURSOR = (_JSEARCH_CURSOR + n) % len(qs)
    return out
# Jooble returns 20 per page and only ever served page 1, which is why it
# contributed 20 rows a country. It is one of only two sources that reach
# staffing and contract work, so it is worth paging properly.
JOOBLE_PAGES = int(env("JOOBLE_PAGES", "10") or 10)

# Adzuna country codes. Override with ADZUNA_COUNTRIES="in,gb,us".
# Default to the countries the board actually keeps. Fetching the other
# fourteen spent free-tier quota on jobs that _job_in_scope discards a
# moment later — and India was fetched FIRST, so the allowance could be
# gone before US or Canada were reached. Widen this only alongside
# JOB_COUNTRIES.
ADZUNA_COUNTRIES = env("ADZUNA_COUNTRIES",
                       "us").split(",")
# 50 results per page. Adzuna is the only source returning contract and
# staffing work, so it is worth pulling deeply — but it is rate limited, so
# the depth has to stay inside the free tier. The arithmetic, at the current
# JOB_REFRESH_HOURS=6 and JOB_COUNTRIES=us,ca:
#     2 countries x 10 pages = 20 calls per crawl
#     4 crawls a day        = 80 calls a day
# comfortably under Adzuna's free allowance. Adding countries or crawling
# more often multiplies this, so raise JOB_REFRESH_HOURS before raising here.
ADZUNA_PAGES = int(env("ADZUNA_PAGES", "10") or 10)

_ADZUNA_CC = {"in": "India", "us": "United States", "gb": "United Kingdom",
              "ca": "Canada", "au": "Australia", "de": "Germany", "fr": "France",
              "nl": "Netherlands", "sg": "Singapore", "za": "South Africa",
              "nz": "New Zealand", "pl": "Poland", "it": "Italy", "es": "Spain",
              "br": "Brazil", "mx": "Mexico", "at": "Austria", "ch": "Switzerland",
              "be": "Belgium", "ru": "Russia"}


async def _fetch_adzuna(client, cc):
    """One country of Adzuna, newest first, across every category."""
    out = []
    for page in range(1, ADZUNA_PAGES + 1):
        r = await client.get(
            f"https://api.adzuna.com/v1/api/jobs/{cc}/search/{page}",
            params={"app_id": ADZUNA_APP_ID, "app_key": ADZUNA_APP_KEY,
                    "results_per_page": 50, "sort_by": "date",
                    "content-type": "application/json"})
        r.raise_for_status()
        results = r.json().get("results") or []
        if not results:
            break
        for j in results:
            loc = (j.get("location") or {}).get("display_name") or _ADZUNA_CC.get(cc, "")
            row = _job_row("adzuna", j.get("id"), j.get("title"),
                           (j.get("company") or {}).get("display_name", ""),
                           loc, j.get("redirect_url", ""),
                           j.get("description", ""), _ts(j.get("created")))
            if row:
                # Adzuna's own location strings are often just a region; fall
                # back to the country we asked for rather than losing it.
                row["country"] = row["country"] or _ADZUNA_CC.get(cc, "")
                out.append(row)
    return out


# ---- free aggregators: no key, no signup, run for everyone ----------------
# These widen the board well beyond the companies we list by name, and beyond
# tech — The Muse and Himalayas carry nursing, teaching, retail and admin.
# These run once a day, so depth is worth the extra minute of crawling.
MUSE_PAGES = int(env("MUSE_PAGES", "120") or 120)      # 20 jobs a page
HIMALAYAS_PAGES = int(env("HIMALAYAS_PAGES", "10") or 10)
ARBEITNOW_PAGES = int(env("ARBEITNOW_PAGES", "30") or 30)


async def _fetch_remotive(client, _=None):
    r = await client.get("https://remotive.com/api/remote-jobs?limit=500")
    r.raise_for_status()
    return [_job_row("remotive", j.get("id"), j.get("title"),
                     j.get("company_name", ""), j.get("candidate_required_location", "Remote"),
                     j.get("url", ""), j.get("description", ""),
                     _ts(j.get("publication_date")))
            for j in (r.json().get("jobs") or [])]


async def _fetch_arbeitnow(client, _=None):
    """Not wired in — see _FREE_AGGREGATORS. Kept because the code is correct;
    the endpoint is what stopped answering."""
    out = []
    for page in range(1, ARBEITNOW_PAGES + 1):
        r = await client.get(f"https://www.arbeitnow.com/api/job-board-api?page={page}")
        r.raise_for_status()
        data = r.json().get("data") or []
        if not data:
            break
        for j in data:
            out.append(_job_row("arbeitnow", j.get("slug"), j.get("title"),
                                j.get("company_name", ""), j.get("location", ""),
                                j.get("url", ""), j.get("description", ""),
                                _ts(j.get("created_at"))))
    return out


async def _fetch_remoteok(client, _=None):
    r = await client.get("https://remoteok.com/api")
    r.raise_for_status()
    out = []
    for j in r.json():
        # The first element is RemoteOK's legal notice, not a job.
        if not isinstance(j, dict) or not j.get("position"):
            continue
        out.append(_job_row("remoteok", j.get("id"), j.get("position"),
                            j.get("company", ""), j.get("location") or "Remote",
                            j.get("url", ""), j.get("description", ""),
                            _ts(j.get("date"))))
    return out


async def _fetch_jobicy(client, _=None):
    r = await client.get("https://jobicy.com/api/v2/remote-jobs?count=100")
    r.raise_for_status()
    return [_job_row("jobicy", j.get("id"), j.get("jobTitle"),
                     j.get("companyName", ""), j.get("jobGeo", "Remote"),
                     j.get("url", ""), j.get("jobExcerpt", ""), _ts(j.get("pubDate")))
            for j in (r.json().get("jobs") or [])]


async def _fetch_himalayas(client, _=None):
    out = []
    for page in range(HIMALAYAS_PAGES):
        r = await client.get(
            f"https://himalayas.app/jobs/api?limit=100&offset={page*100}")
        r.raise_for_status()
        jobs = r.json().get("jobs") or []
        if not jobs:
            break
        for j in jobs:
            locs = j.get("locationRestrictions") or []
            out.append(_job_row("himalayas", j.get("guid") or j.get("title"),
                                j.get("title"), j.get("companyName", ""),
                                ", ".join(locs[:2]) if locs else "Remote",
                                j.get("applicationLink") or j.get("url", ""),
                                j.get("excerpt", ""), _ts(j.get("pubDate"))))
    return out


async def _fetch_themuse(client, _=None):
    """The widest free source we have, and the least tech-only."""
    out = []
    for page in range(1, MUSE_PAGES + 1):
        r = await client.get(
            f"https://www.themuse.com/api/public/jobs?page={page}")
        if r.status_code == 400:            # ran past the last page
            break
        r.raise_for_status()
        results = r.json().get("results") or []
        if not results:
            break
        for j in results:
            locs = [x.get("name", "") for x in (j.get("locations") or [])]
            refs = j.get("refs") or {}
            out.append(_job_row("themuse", j.get("id"), j.get("name"),
                                (j.get("company") or {}).get("name", ""),
                                ", ".join(locs[:2]),
                                refs.get("landing_page", ""),
                                j.get("contents", ""),
                                _ts(j.get("publication_date"))))
    return out


# The Muse is deliberately absent. Its landing_page links 404 about half the
# time — 15 of 30 sampled — because it keeps listings after the employer has
# taken them down. It was 14% of the board and the only source with dead
# links; every other one returned 200 across the board. A job that cannot be
# opened is worse than no job, so the fetcher stays but is not wired in.
_FREE_AGGREGATORS = {
    # arbeitnow removed: it returned HTTPStatusError on every crawl — the
    # endpoint no longer answers as documented. The fetcher is kept below,
    # like themuse's, so re-wiring it is one line if they come back.
    "remotive": _fetch_remotive, "remoteok": _fetch_remoteok,
    "jobicy": _fetch_jobicy, "himalayas": _fetch_himalayas,
}


async def _fetch_jooble(client, country):
    out = []
    for page in range(1, JOOBLE_PAGES + 1):
        r = await client.post(f"https://jooble.org/api/{JOOBLE_KEY}",
                              json={"keywords": "", "location": country,
                                    "page": str(page)})
        r.raise_for_status()
        jobs = r.json().get("jobs") or []
        if not jobs:
            break              # ran out before the page limit
        for j in jobs:
            row = _job_row("jooble", j.get("id") or j.get("link"), j.get("title"),
                           j.get("company", ""), j.get("location", "") or country,
                           j.get("link", ""), j.get("snippet", ""),
                           _ts(j.get("updated")))
            if row:
                row["country"] = row["country"] or country
                out.append(row)
    return out


def _jsearch_window(page: int = 1) -> str:
    """The date range to ask for, paired with how deep we page.

    "today" stops us paying to re-download jobs already stored, but
    there are not ninety roles posted today for one title — asking for
    nine pages of "today" buys seven empty ones. So the window follows
    the depth: shallow means today, deep means the week. Setting
    JSEARCH_WINDOW pins it either way.
    """
    pinned = env("JSEARCH_WINDOW", "").strip().lower()
    # Only what the API actually accepts. A typo here — "weak" for "week" —
    # is not rejected loudly: the request goes out with a value the provider
    # does not understand and comes back with nothing useful, so the source
    # looks broken rather than misconfigured. Fall back and say so.
    ok = ("all", "today", "3days", "week", "month")
    if pinned in ok:
        return pinned
    if pinned:
        print(f"JSEARCH_WINDOW={pinned!r} is not one of {ok} - ignoring it")
    return "today" if page <= 1 and JSEARCH_PAGES <= 2 else "week"


async def _fetch_jsearch(client, query, cc, page=1):
    """One query, one country, one page of results, from JSearch."""
    out = []
    # Open Web Ninja serves JSearch directly. It is the same payload shape as
    # the RapidAPI listing, but a different host and a plain X-API-Key — which
    # is why the RapidAPI headers produced errors while the dashboard still
    # read zero requests: the calls were refused before they were ever metered.
    r = await client.get(
        JSEARCH_BASE,
        # A month rather than a week. The request costs the same either way,
        # and the narrower window was throwing away three quarters of what we
        # had already paid for — postings stay open far longer than seven
        # days, and anything already stored is a cheap update rather than a
        # duplicate.
        params={"query": f"{query} in {cc}", "page": str(page),
                "num_pages": str(JSEARCH_PAGES), "country": cc.lower(),
                # Back to a week. A month was chosen for volume — the request costs
                # the same either way — but it fills the board with postings
                # that are technically open and weeks stale, and being early is
                # the thing this board actually sells. Set JSEARCH_WINDOW=month
                # to trade freshness for depth again.
                "date_posted": _jsearch_window(page)},
        headers={"X-API-Key": JSEARCH_KEY},
        # Its own timeout, well above the client's 25s. num_pages=9 makes the
        # provider fetch nine pages before answering, which takes far longer
        # than a single ATS board — at 9 pages half these queries died on
        # ReadTimeout and the depth we were paying for never arrived. Scales
        # with the depth asked for, so raising JSEARCH_PAGES cannot silently
        # reintroduce this.
        timeout=JSEARCH_TIMEOUT)
    if r.status_code >= 300:
        # RapidAPI says WHY in the body — wrong key, not subscribed, quota
        # gone — and a bare HTTPStatusError threw that away. 401/403/429 need
        # completely different fixes, so the report has to tell them apart.
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:160]}")
    # The payload shape is the provider's to change, and it has changed: what
    # arrives under "data" is a list of jobs on one endpoint and an object
    # wrapping that list on another. Reading it one way turned every query
    # into a bare AttributeError — iterating a dict hands back its keys, and a
    # string has no .get. Take the list wherever it is, and skip anything that
    # is not a job object rather than failing the whole query over one row.
    body = r.json()
    if not isinstance(body, dict):
        raise RuntimeError(f"unexpected payload: {str(body)[:120]}")
    data = body.get("data")
    if isinstance(data, dict):
        for k in ("jobs", "results", "data", "items"):
            if isinstance(data.get(k), list):
                data = data[k]
                break
    if not isinstance(data, list):
        raise RuntimeError(
            f"no job list in response (keys: {list(body)[:6]})")
    for j in data:
        if not isinstance(j, dict):
            continue
        loc = ", ".join(x for x in (j.get("job_city"), j.get("job_state")) if x)               or j.get("job_country") or ""
        row = _job_row("jsearch", j.get("job_id"), j.get("job_title"),
                       j.get("employer_name", ""), loc,
                       j.get("job_apply_link", ""),
                       j.get("job_description", ""),
                       _ts(j.get("job_posted_at_datetime_utc")))
        if row:
            # JSearch reports the country properly, so trust it over whatever
            # the free-text location parser guesses.
            row["country"] = j.get("job_country") or row["country"]
            if j.get("job_is_remote"):
                row["remote"] = True
            def _num(v):
                # Salary arrives as a number, a numeric string, or null
                # depending on the source posting. None of those should cost
                # us the row.
                try:
                    return int(float(v))
                except (TypeError, ValueError):
                    return 0

            lo, hi = _num(j.get("job_min_salary")), _num(j.get("job_max_salary"))
            if lo or hi:
                per = str(j.get("job_salary_period") or "").lower()
                unit = {"year": "a year", "hour": "an hour",
                        "month": "a month"}.get(per, "")
                cur = "$" if (j.get("job_salary_currency") or "USD") == "USD" else ""
                if lo and hi:
                    row["salary"] = f"{cur}{lo:,} - {cur}{hi:,} {unit}".strip()
                else:
                    row["salary"] = f"{cur}{(lo or hi):,} {unit}".strip()
            # One endpoint sends a string, another a list of them.
            et = j.get("job_employment_type") or j.get("job_employment_types") or ""
            if isinstance(et, (list, tuple)):
                et = et[0] if et else ""
            if et:
                row["job_type"] = {"FULLTIME": "fulltime", "PARTTIME": "parttime",
                                   "CONTRACTOR": "contract", "CONTRACT": "contract",
                                   "INTERN": "internship", "INTERNSHIP": "internship"
                                   }.get(str(et).upper(), row.get("job_type", ""))
            out.append(row)
    return out


async def _collect_jobs():
    """Hit every configured board once.

    Returns (rows, report, reached) where `reached` is the set of boards that
    genuinely answered. Closing jobs is driven by `reached`, never by the rows
    alone — otherwise one board timing out would look exactly like that
    employer taking every posting down."""
    import asyncio, httpx
    rows, report, reached = [], {}, set()
    async with httpx.AsyncClient(
            timeout=25, follow_redirects=True,
            headers={"User-Agent": "Craxle/1.0 (job board reader)"}) as client:
        # Concurrent, not serial. One board at a time with a 25s timeout meant
        # ~400 boards could take an hour; the container restarted on the next
        # deploy before the crawl ever finished, so the board silently stopped
        # updating. The semaphore keeps it polite — 12 in flight, not 400 —
        # and the whole stage is bounded so one hung host cannot stall it.
        sem = asyncio.Semaphore(12)

        async def one(source, fetch, token):
            async with sem:
                try:
                    got = [r for r in await fetch(client, token) if r]
                    return source, token, got, len(got)
                except Exception as e:
                    return source, token, [], f"{type(e).__name__}"

        tasks = [one(source, fetch, token)
                 for source, fetch in _FETCHERS.items()
                 for token in _job_tokens(source)]
        # The ceiling has to clear the slowest source, not the average one.
        stage_cap = BOARD_STAGE_CAP
        # wait(), not wait_for(gather()). gather cancels every task when the
        # clock runs out and the except branch then threw away the lot — one
        # slow host meant a crawl that fetched four hundred boards stored
        # nothing from any of them. This keeps whatever finished and drops
        # only what was still in flight.
        # wait() raises on an empty set, which is reachable: switch every
        # board off and the sweep should do nothing, not crash the crawl.
        done, pending = set(), set()
        if tasks:
            done, pending = await asyncio.wait(
                [asyncio.ensure_future(t) for t in tasks], timeout=stage_cap)
        for t in pending:
            t.cancel()
        if pending:
            print(f"jobs: board sweep hit the cap with {len(pending)} still "
                  f"in flight; keeping the {len(done)} that answered")
        results = []
        for t in done:
            try:
                results.append(t.result())
            except Exception:
                pass
        for res in results:
            if isinstance(res, Exception) or not res:
                continue
            source, token, got, outcome = res
            rows += got
            if isinstance(outcome, int):
                reached.add((source, token))
            report[f"{source}:{token}"] = outcome

        # Free aggregators. Each carries its own employers, so `reached` is
        # keyed on the feed itself — if one is down we simply keep what we had
        # rather than closing every job it ever gave us.
        for name, fetch in _FREE_AGGREGATORS.items():
            try:
                got = [r for r in await fetch(client) if r]
                rows += got
                for r in got:
                    reached.add((name, r["company"]))
                report[name] = len(got)
            except Exception as e:
                report[name] = f"{type(e).__name__}"

        # Keyed aggregators, only when the key is configured.
        if ADZUNA_APP_ID and ADZUNA_APP_KEY:
            for cc in [c.strip() for c in ADZUNA_COUNTRIES if c.strip()]:
                try:
                    got = [r for r in await _fetch_adzuna(client, cc) if r]
                    rows += got
                    report[f"adzuna:{cc}"] = len(got)
                except Exception as e:
                    report[f"adzuna:{cc}"] = f"{type(e).__name__}"
        else:
            report["adzuna"] = "skipped (no ADZUNA_APP_ID / ADZUNA_APP_KEY)"

        if JOOBLE_KEY:
            for cname in [_ADZUNA_CC.get(c.strip(), "") for c in ADZUNA_COUNTRIES]:
                if not cname:
                    continue
                try:
                    got = [r for r in await _fetch_jooble(client, cname) if r]
                    rows += got
                    report[f"jooble:{cname}"] = len(got)
                except Exception as e:
                    report[f"jooble:{cname}"] = f"{type(e).__name__}"
        else:
            report["jooble"] = "skipped (no JOOBLE_KEY)"

        global _CRAWL_TICK
        _CRAWL_TICK += 1
        # The FIRST crawl after boot always runs JSearch. Counting from zero
        # meant tick 1 was never its turn, so with EVERY_CRAWLS=4 and a deploy
        # every hour or two the paid source was skipped every single time and
        # the board stopped receiving the only contract jobs it has.
        jsearch_turn = ((_CRAWL_TICK - 1) % JSEARCH_EVERY_CRAWLS) == 0
        if JSEARCH_KEY and not jsearch_turn:
            report["jsearch"] = (f"skipped: runs every {JSEARCH_EVERY_CRAWLS} "
                                 f"crawls (this is {_CRAWL_TICK % JSEARCH_EVERY_CRAWLS}"
                                 f" of {JSEARCH_EVERY_CRAWLS})")
        elif JSEARCH_KEY:
            _db = SessionLocal()
            try:
                used = _jsearch_used(_db)
            finally:
                _db.close()
            if used >= JSEARCH_MONTHLY_CAP:
                report["jsearch"] = (f"skipped: monthly cap reached "
                                     f"({used}/{JSEARCH_MONTHLY_CAP})")
                JSEARCH_QUERIES_THIS_RUN = []
            else:
                JSEARCH_QUERIES_THIS_RUN = None
            # Concurrent, like the boards above. Sixty-eight queries one
            # after another, each allowed thirty seconds, is half an hour of
            # wall clock for a single crawl — long enough that the container
            # restarted or the next crawl came round before the tail of the
            # list was ever asked for. The same queries at the end never ran,
            # every time, which is what "JSearch only pulls a few hundred"
            # actually was. Six at a time: the whole list now fits in about a
            # minute, and every role gets asked for on every crawl.
            plan = [(cc, q)
                    for cc in ([] if used >= JSEARCH_MONTHLY_CAP
                               else [c.strip().upper() for c in ADZUNA_COUNTRIES
                                     if c.strip()])
                    for q in _jsearch_slice(used)]
            # Page cursors in one go: one session for the batch rather than
            # opening a connection inside every request.
            pages = {}
            if plan:
                _db = SessionLocal()
                try:
                    for cc, q in plan:
                        pages[(cc, q)] = _jsearch_page(_db, q)
                finally:
                    _db.close()
            jsem = asyncio.Semaphore(JSEARCH_CONCURRENCY)
            # A paid plan that has run out returns 429. Once one query sees
            # it, the rest stop asking rather than burning what is left of
            # the quota against a wall.
            spent = {"limited": False}

            async def one_query(cc, q):
                page = pages[(cc, q)]
                key = f"jsearch:{cc}:{q} p{page}"
                if spent["limited"]:
                    return key, [], "skipped: rate limited"
                async with jsem:
                    if spent["limited"]:
                        return key, [], "skipped: rate limited"
                    try:
                        got = [r for r in await _fetch_jsearch(client, q, cc, page) if r]
                        return key, got, len(got)
                    except Exception as e:
                        if ("429" in str(e) or "TooManyRequests" in type(e).__name__
                                or "exceeded" in str(e).lower()):
                            spent["limited"] = True
                        # Always carry the message. A report that said only
                        # "AttributeError" for every query named the type of
                        # the bug and nothing about where it was.
                        return key, [], (str(e)[:180] if isinstance(e, RuntimeError)
                                         else f"{type(e).__name__}: {e}"[:180])

            got_all = await asyncio.gather(*[one_query(cc, q) for cc, q in plan],
                                           return_exceptions=True)
            billed = 0
            for res in got_all:
                if isinstance(res, Exception):
                    continue
                key, got, outcome = res
                rows += got
                report[key] = outcome
                if isinstance(outcome, int):
                    billed += JSEARCH_PAGES
            if billed:
                _db = SessionLocal()
                try:
                    _jsearch_used(_db, add=billed)
                finally:
                    _db.close()
            if spent["limited"]:
                report["jsearch"] = "stopped: rate limited"
        else:
            report["jsearch"] = "skipped (no JSEARCH_KEY)"
    return rows, report, reached


# Sources we have switched off. Their rows must be deleted outright: a
# retired source never appears in a crawl, so the "vanished from the board"
# rule never fires and the rows would sit there as open forever.
RETIRED_SOURCES = ("themuse",)

# What the board actually carries. Craxle serves IT and technology job seekers
# in North America, and a board padded with roles nobody here searches for
# makes matching worse, not better: every irrelevant posting is another chance
# for the scorer to surface noise.
#
# "Technical and non-technical" means both sides of a tech company — engineers
# and the product, design, support and QA roles around them — not every job in
# every industry.
ALLOWED_COUNTRIES = {c.strip().upper() for c in
                     (env("JOB_COUNTRIES", "US") or "US").split(",") if c.strip()}
ALLOWED_FAMILIES = {f.strip().lower() for f in
                    (env("JOB_FAMILIES",
                         "network,security,sysadmin,devops,backend,frontend,"
                         "mobile,data,ml,qa,product,design,support,other")
                     or "").split(",") if f.strip()}


# Half the boards leave `country` empty and put it in the location string
# instead, so a Berlin role arrived indistinguishable from a US remote one and
# the blank-is-fine rule let it straight through. If the location names
# somewhere we do not serve, that is an answer — treat it as one.
_NON_US_PLACES = (
    "canada|ontario|toronto|vancouver|montreal|calgary|ottawa|quebec|alberta"
    "|british columbia|mississauga|edmonton|winnipeg"
    "|united kingdom|england|scotland|wales|london, uk|manchester|birmingham"
    "|edinburgh|glasgow|bristol|leeds|dublin|ireland"
    "|germany|deutschland|berlin|munich|münchen|frankfurt|hamburg|cologne"
    "|stuttgart|dusseldorf|düsseldorf"
    "|france|paris|lyon|toulouse|marseille"
    "|spain|madrid|barcelona|valencia|portugal|lisbon|porto"
    "|netherlands|amsterdam|rotterdam|utrecht|eindhoven|belgium|brussels"
    "|switzerland|zurich|zürich|geneva|austria|vienna"
    "|sweden|stockholm|norway|oslo|denmark|copenhagen|finland|helsinki"
    "|poland|warsaw|krakow|kraków|wroclaw|czech|prague|hungary|budapest"
    "|romania|bucharest|bulgaria|sofia|greece|athens|ukraine|kyiv|kiev"
    "|italy|milan|rome|turin"
    "|india|bangalore|bengaluru|hyderabad|pune|chennai|mumbai|delhi|noida"
    "|gurgaon|gurugram|kolkata|ahmedabad|kochi|coimbatore|indore|jaipur"
    "|pakistan|karachi|lahore|bangladesh|dhaka|sri lanka|colombo"
    "|australia|sydney|melbourne|brisbane|perth|adelaide|canberra"
    "|new zealand|auckland|wellington"
    "|singapore|malaysia|kuala lumpur|indonesia|jakarta|thailand|bangkok"
    "|vietnam|hanoi|ho chi minh|philippines|manila|cebu"
    "|japan|tokyo|osaka|korea|seoul|china|beijing|shanghai|shenzhen"
    "|hong kong|taiwan|taipei"
    "|mexico|guadalajara|monterrey|mexico city|brazil|brasil|sao paulo"
    "|são paulo|rio de janeiro|argentina|buenos aires|chile|santiago"
    "|colombia|bogota|bogotá|medellin|medellín|peru|lima|costa rica"
    "|uruguay|montevideo"
    "|israel|tel aviv|turkey|istanbul|ankara|uae|dubai|abu dhabi"
    "|saudi|riyadh|qatar|doha|egypt|cairo|south africa|johannesburg"
    "|cape town|nigeria|lagos|kenya|nairobi|morocco|casablanca"
    "|luxembourg|iceland|reykjavik|malta|cyprus|nicosia"
    "|estonia|tallinn|latvia|riga|lithuania|vilnius|slovakia|bratislava"
    "|slovenia|ljubljana|croatia|zagreb|serbia|belgrade|armenia|yerevan"
    "|moldova|belarus|minsk|kazakhstan|almaty|uzbekistan|tashkent"
    "|nepal|kathmandu|cambodia|phnom penh|myanmar|yangon"
    "|ghana|accra|tanzania|uganda|kampala|ethiopia|addis ababa"
    "|tunisia|algeria|jordan|amman|lebanon, |beirut|kuwait|bahrain|manama"
    "|oman|muscat|ecuador|quito|bolivia|paraguay|asuncion|venezuela|caracas"
    "|panama city|guatemala|san salvador|dominican republic|santo domingo"
    "|emea|apac|latam|anywhere in europe|europe only|uk only|eu only"
)
_NON_US_RE = re.compile(r"(?:^|[\s,/()\-])(?:" + _NON_US_PLACES + r")(?:$|[\s,/()\-])",
                        re.I)

# Several of those city names are also US cities — Vienna VA, Dublin OH,
# Paris TX, Athens GA, Hamburg NY. A US signal anywhere in the location wins,
# so the foreign-city list can stay broad without deleting American jobs.
_US_STATES = (
    "alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware"
    "|florida|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana"
    "|maine|maryland|massachusetts|michigan|minnesota|mississippi|missouri"
    "|montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york"
    "|north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania"
    "|rhode island|south carolina|south dakota|tennessee|texas|utah|vermont"
    "|virginia|washington|west virginia|wisconsin|wyoming|georgia"
    "|district of columbia|puerto rico"
)
_US_HINT_RE = re.compile(
    r"(?:^|[\s,/()\-])(?:united states|usa|u\.s\.a?\.?|"
    + _US_STATES + r"|d\.c\.)(?:$|[\s,/()\-])", re.I)
# State abbreviations only count as uppercase tokens: "IN", "OR" and "ME" are
# ordinary words in a lowercase sentence, and matching those would keep
# everything.
_US_ABBR_RE = re.compile(
    r"(?:^|[\s,/(\-])(?:A[KLRZ]|C[AOT]|D[CE]|FL|GA|HI|I[ADLN]|K[SY]|LA|M[ADEINOST]"
    r"|N[CDEHJMVY]|O[HKR]|PA|RI|S[CD]|T[NX]|UT|V[AT]|W[AIVY])(?:$|[\s,/)\-])")


# Title words that make a posting technical on their own. Deliberately not
# "specialist", "manager" or "consultant" — every industry has those.
_TECH_TITLE_RE = re.compile(
    r"(?<![a-z])(engineer|engineering|developer|architect|administrator|"
    r"programmer|sre|devops|sysadmin|dba)(?:s|ing)?(?![a-z])", re.I)

# Words that make a title technical in one industry and not in another.
# "Certified Veterinary Technician" put a pet hospital on an IT board, and
# "technologist", "scientist" and "analyst" do the same for laboratories,
# hospitals and finance. They only count when the rest of the title agrees.
_AMBIGUOUS_TITLE_RE = re.compile(
    r"(?<![a-z])(technician|technologist|scientist|analyst|specialist)"
    r"(?:s)?(?![a-z])", re.I)
# ...and these say plainly that it is not our industry, whatever the noun.
_NOT_TECH_TITLE_RE = re.compile(
    r"(?<![a-z])(veterinary|vet|dental|nurse|nursing|clinical|medical|"
    r"medicine|sonograph\w*|imaging|oncolog\w*|cardiac|respiratory|"
    r"steuerberater|wirtschaftspr\w*|rechtsanwalt|kaufmann|kauffrau|"
    r"mitarbeiter|gesucht|vertrieb|buchhalt\w*|"
    r"pharmacy|pharmacist|radiolog\w*|surgical|patient|phlebotom\w*|"
    r"laboratory|lab|chemistry|biolog\w*|environmental|hvac|automotive|"
    r"mechanic\w*|electrical|welding|hospital|physician|therapist|"
    r"paralegal|legal|payroll|accounting|tax|audit|insurance|claims|"
    r"culinary|kitchen|retail|warehouse|logistics|driver|maintenance)"
    r"(?![a-z])", re.I)


def _title_is_technical(title: str) -> bool:
    """Whether a job title, on its own, belongs on an IT board.

    Three tiers, because one list cannot do it. "Engineer" and "developer"
    are ours outright. "Technician" and "analyst" belong to every industry
    and only count when nothing else in the title claims them. And a title
    naming veterinary work, nursing or accounting is not ours no matter what
    noun follows it — which is how twenty Certified Veterinary Technicians
    ended up on a board that promises technical roles.
    """
    t = title or ""
    if _NOT_TECH_TITLE_RE.search(t):
        return False
    if _TECH_TITLE_RE.search(t):
        return True
    return bool(_AMBIGUOUS_TITLE_RE.search(t))


def _job_in_scope(r):
    """Whether a crawled posting belongs on the board.

    Country is matched loosely because sources spell it inconsistently — some
    send "United States", some "US", some nothing at all. A blank country
    falls back to the location text, and is kept only when that text does not
    name somewhere outside scope: genuinely remote US listings say "Remote"
    and stay, while "Remote (Germany)" goes.
    """
    # A title naming another industry is out regardless of what family the
    # keywords matched. "Certified Veterinary Technician" parses as sysadmin
    # on the word technician, and no amount of category logic downstream can
    # undo that — it has to be refused here.
    if _NOT_TECH_TITLE_RE.search(r.get("title") or ""):
        return False
    fam = (r.get("category") or "").strip().lower()
    if ALLOWED_FAMILIES and fam and fam not in ALLOWED_FAMILIES:
        return False
    # Only when the caller handed us a whole posting. /api/jobs/filters asks
    # this about a bare country string to decide what to offer in a dropdown,
    # and judging that as "a job with no skills" emptied the list.
    if ALLOWED_FAMILIES and not fam and "skills" in r:
        # No recognised family. Half the board arrived this way — Commercial
        # Counsel, Credit Risk Analyst, Administrative Business Partner: real
        # jobs at tech companies that are not tech jobs, sitting on a board
        # that promises IT roles. An unrecognised title is only kept when the
        # posting itself is technical, which the parsed skills already say.
        # That keeps the genuine misses (Android BSP Engineer) and drops the
        # rest.
        sk = r.get("skills") or ""
        got = [x for x in (sk.split(",") if isinstance(sk, str) else sk) if x]
        # Excel and SQL are on half the postings in every industry, so they
        # cannot be the evidence that a job is technical.
        strong = len([x for x in got if x not in _WEAK_SKILLS])
        # "Engineering Manager — Streaming" and "Principal Engineer, Privacy"
        # name no family we would want to guess at — calling them Backend
        # would poison the category filter — but they are plainly engineering
        # jobs, and dropping them was leaving real roles off the board. A
        # technical job title lowers the bar rather than removing it: the
        # posting still has to name a real tool.
        need = 1 if _title_is_technical(r.get("title") or "") else 3
        if strong < need:
            return False
    c = (r.get("country") or "").strip().upper()
    if not c:
        loc = (r.get("location") or "")
        if _US_HINT_RE.search(loc) or _US_ABBR_RE.search(loc):
            return True
        return not _NON_US_RE.search(loc)
    if c in ALLOWED_COUNTRIES:
        return True
    aliases = {"UNITED STATES": "US", "USA": "US", "U.S.": "US",
               "UNITED STATES OF AMERICA": "US", "CANADA": "CA"}
    return aliases.get(c, c) in ALLOWED_COUNTRIES


def _protected_job_ids(db):
    """Job ids some user has saved, applied to, or otherwise tracked."""
    return {r[0] for r in db.query(JobTrack.job_id).distinct().all() if r[0]}


def _store_jobs(db, rows, reached):
    """Upsert this crawl, close postings that vanished, drop old history."""
    gone = db.query(Job).filter(Job.source.in_(RETIRED_SOURCES)).delete(
        synchronize_session=False)
    if gone:
        db.commit()
        print(f"jobs: removed {gone} rows from retired sources "
              f"({', '.join(RETIRED_SOURCES)})")
    seen, added, updated = set(), 0, 0
    skipped = dupes = 0
    for r in rows:
        if not _job_in_scope(r):
            skipped += 1
            continue
        # It is on the board, so it has to be reachable. A posting with no
        # category is invisible to the category filter — 16% of the board was
        # sitting in that hole. Infer one from the tools it names, and if even
        # that is silent, file it under Other rather than nowhere.
        if not r.get("category"):
            r["category"] = _family_from_text(r.get("text") or "") or "other"
        key = (r["source"], r["external_id"])
        # A board can return the same posting twice in one crawl — Workday
        # paginates with overlap. The row below is added to the session but not
        # flushed, so the duplicate's SELECT finds nothing and inserts a second
        # copy, and the whole transaction dies on the unique constraint at
        # commit. One duplicate therefore discarded every job in the batch.
        if key in seen:
            dupes += 1
            continue
        seen.add(key)
        row = db.query(Job).filter(Job.source == r["source"],
                                   Job.external_id == r["external_id"]).first()
        if row:
            row.title, row.company = r["title"], r["company"]
            row.location, row.country = r["location"], r["country"]
            row.remote, row.url, row.text = r["remote"], r["url"], r["text"]
            row.category, row.skills = r["category"], r["skills"]
            row.req_skills = r["req_skills"]
            row.job_type, row.engagement = r["job_type"], r["engagement"]
            row.visa = r["visa"]
            # Salary and posted date were missing from this list, so a posting
            # first stored before either field existed was found, updated and
            # left NULL on every crawl for the rest of its life. That is why
            # pay showed on 0% of the board while a seventh of the postings
            # stated it in plain text. An empty new parse never overwrites a
            # value we already have — a truncated description should not erase
            # a rate we read last week.
            row.salary = r["salary"] or row.salary
            row.min_years = r.get("min_years") or row.min_years
            row.description = r.get("description") or row.description
            row.posted_at = r.get("posted_at") or row.posted_at
            row.last_seen, row.is_open, row.closed_at = now(), True, None
            updated += 1
        else:
            db.add(Job(**r, first_seen=now(), last_seen=now(), is_open=True))
            added += 1
    db.commit()
    if skipped or dupes:
        print(f"jobs: skipped {skipped} out-of-scope postings "
              f"(countries={sorted(ALLOWED_COUNTRIES)}), {dupes} duplicates")

    # A posting we did not see, on a board we DID reach, has come off that
    # career site — mark it closed so the user can still see it went.
    closed = 0
    for row in db.query(Job).filter(Job.is_open == True).all():  # noqa: E712
        if ((row.source, row.company) in reached
                and (row.source, row.external_id) not in seen):
            row.is_open, row.closed_at = False, now()
            closed += 1
    # A posting someone saved or applied to is theirs, not ours to delete.
    # JobTrack copies the title and company at save time so the tracker still
    # renders, but the Job row itself is what the apply kit and the match score
    # read — deleting it turns a saved job into "no longer listed".
    cutoff = now() - dt.timedelta(days=JOB_RETENTION_DAYS)
    keep = _protected_job_ids(db)
    q = db.query(Job).filter(Job.last_seen < cutoff)
    if keep:
        q = q.filter(~Job.id.in_(keep))
    pruned = q.delete(synchronize_session=False)
    db.commit()
    return {"added": added, "updated": updated, "closed": closed,
            "pruned": pruned, "duplicates": dupes, "out_of_scope": skipped}


# Outcome of the most recent crawl, whoever started it — the hourly loop or
# the admin button. Read by /api/admin/jobs/refresh/status.
_LAST_CRAWL = {"state": "never run"}


# One crawl at a time, process-wide. The hourly loop and the admin button are
# separate callers: when they overlapped, both fetched the same postings and
# both inserted them, because each one's lookup ran before the other's write
# landed. That is a unique-constraint violation on (source, external_id) and it
# fails the WHOLE batch, not the one row.
_CRAWL_LOCK = None


async def _refresh_jobs():
    import asyncio
    global _CRAWL_LOCK
    if _CRAWL_LOCK is None:
        _CRAWL_LOCK = asyncio.Lock()
    if _CRAWL_LOCK.locked():
        print("jobs: a crawl is already running; skipping this one")
        return {"added": 0, "updated": 0, "closed": 0, "pruned": 0,
                "skipped_concurrent": True, "fetched": 0,
                "boards_reached": 0, "sources": {}}
    async with _CRAWL_LOCK:
        # Recorded here rather than in the admin handler, so the hourly loop's
        # crawls show up too. Previously only button-triggered crawls updated
        # this, and the status read "never run" while the loop was working.
        _LAST_CRAWL.clear()
        _LAST_CRAWL.update({"state": "running", "started": now().isoformat()})
        try:
            r = await _refresh_jobs_locked()
        except Exception as e:
            _LAST_CRAWL.update({"state": "failed", "finished": now().isoformat(),
                                "error": f"{type(e).__name__}: {e}"[:600]})
            raise
        _LAST_CRAWL.update({"state": "done", "finished": now().isoformat(), **r})
        return r


async def _refresh_jobs_locked():
    import asyncio
    rows, report, reached = await _collect_jobs()

    def _store():
        db = SessionLocal()
        try:
            return _store_jobs(db, rows, reached)
        finally:
            db.close()

    # Off the event loop. Writing ~16,000 rows is a minute of synchronous
    # database work, and running it inline froze every other request for that
    # whole time — including /api/version, which does nothing at all.
    stats = await asyncio.to_thread(_store)
    print(f"jobs refresh: {stats} from {len(rows)} rows, {len(reached)} boards")
    return {**stats, "fetched": len(rows), "boards_reached": len(reached),
            "sources": report}


# The score a new posting has to reach before it is worth interrupting
# someone.
#
# READ THIS BEFORE CHANGING IT. Scoring was rebalanced in v3.25.0 so a
# wrong-field job can no longer ride a well-written resume into the sixties,
# and every score came down with it. Measured against the live board, a
# near-perfect match — a senior network resume against a senior network role
# naming nine of the same tools — scores 79 to 89. Above 90 is therefore not
# "a very strong match", it is very close to off: it needs a posting that
# matches on skills, requirements, field, seniority AND title at once.
#
# Measured against the live board — 10,680 postings, four resume profiles
# (network, backend, SRE, data) — the highest score any of them achieved was
# 77, and NOTHING reached 80. So a fixed bar at 80 or 90 does not mean "only
# excellent matches", it means silence.
#
# Hence two numbers rather than one. JOB_ALERT_MIN is the bar for an
# exceptional match, flagged as such. JOB_ALERT_FLOOR is the bar for the best
# of what actually came in — if nothing clears MIN, the day's strongest
# matches are still sent, because a job board whose alerts never fire is the
# same as a job board with no alerts.
JOB_ALERT_MIN = int(env("JOB_ALERT_MIN", "90") or 90)
JOB_ALERT_FLOOR = int(env("JOB_ALERT_FLOOR", "70") or 70)
# How many matches one sweep may put in the bell and the email. Everything
# above the threshold is sent, not just the best one — this only stops a
# bumper crawl from burying the list.
JOB_ALERT_MAX = int(env("JOB_ALERT_MAX", "12") or 12)


def _job_alert_sweep():
    """Tell people what changed while they were not looking.

    Two things worth interrupting someone for: a job they saved has closed, and
    a strong new match has appeared. Everything else is noise, and a job board
    that pings constantly gets muted.
    """
    db = SessionLocal()
    made = 0
    emailed = 0
    # Collected and sent AFTER the commit: mail is slow and can fail, and
    # neither should roll back or delay the alerts themselves.
    outbox = []
    try:
        cutoff = now() - dt.timedelta(days=1)
        fresh = db.query(Job).filter(Job.is_open == True,          # noqa: E712
                                     Job.first_seen >= cutoff).limit(1500).all()

        # Rarity weights measured across the open board, exactly as the match
        # page measures them. Passing an empty table here gave every skill a
        # weight of 1.0, so the score in the email did not agree with the
        # score on the card it linked to — the fastest way to make people stop
        # believing both.
        idf = {}
        if fresh:
            df, n = {}, 0
            for j in db.query(Job).filter(Job.is_open == True).all():   # noqa: E712
                n += 1
                for s in _job_skills(j):
                    df[s] = df.get(s, 0) + 1
            n = max(n, 1)
            # Floored. A skill on more than about four fifths of postings
            # takes this expression negative, and a negative weight means
            # matching a skill scores LOWER than not matching it. The live
            # board is nowhere near that, but a board on its first day has
            # few enough postings that everything is "common" — which is
            # exactly when a new deployment's first alerts would be nonsense.
            idf = {s: max(0.05, math.log(n / (1 + c)) + 0.25)
                   for s, c in df.items()}

        users = db.query(User).filter(User.is_active == True).all()  # noqa: E712
        for u in users:
            tracked = db.query(JobTrack).filter(
                JobTrack.user_id == u.id,
                JobTrack.status.in_(("saved", "viewed"))).all()

            # --- a saved job closed: they have missed it, and should know ---
            closed = []
            for t in tracked:
                j = db.get(Job, t.job_id)
                if j is not None and not j.is_open:
                    key = f"closed_{t.job_id}"
                    seen = db.query(Note).filter(Note.user_id == u.id,
                                                 Note.k == key).first()
                    if not seen:
                        closed.append(t)
                        db.add(Note(user_id=u.id, k=key, v="1"))
            if closed:
                first = closed[0]
                extra = f" and {len(closed) - 1} other" + ("s" if len(closed) > 2 else "") \
                        if len(closed) > 1 else ""
                db.add(JobAlert(
                    user_id=u.id, kind="closing", icon="\u23f0",
                    text=f"{first.title} at {first.company} has closed{extra}. "
                         f"Apply sooner next time — saved jobs do not stay open.",
                    url=first.url or ""))
                made += 1

            # --- strong new matches, for people who have a resume on file ---
            if plan_of(u) == "free":
                continue          # matching is a paid feature; do not tease it
            # Off only if they said so. A blank means nobody has expressed a
            # preference, and someone who saved a resume to a job board wants
            # to hear about matching jobs.
            pref = db.query(Note).filter(Note.user_id == u.id,
                                         Note.k == "job_alerts").first()
            if pref is not None and (pref.v or "1") == "0":
                continue
            note = db.query(Note).filter(Note.user_id == u.id,
                                         Note.k == "resume_uptext").first()
            rtext = (note.v if note else "") or ""
            if len(rtext.strip()) < 120 or not fresh:
                continue
            skills, keywords = _profile(rtext)
            if not skills:
                continue
            my_fams = _resume_families(rtext)
            level = _level_of(rtext)
            impact, parsing = _impact_score(rtext), _parsing_score(rtext)
            titles = _title_words(" ".join(rtext.splitlines()[:6]))
            # Already told them about these. A posting stays "new" for 24
            # hours and the crawler runs every hour inside the window, so
            # without this the same job produced an alert on all eleven passes
            # — eleven bells for one job is how a notification bell gets
            # ignored forever.
            told = {r[0] for r in db.query(Note.k).filter(
                Note.user_id == u.id, Note.k.like("alerted_%")).all()}
            best = []
            for j in fresh:
                if f"alerted_{j.id}" in told:
                    continue
                sc = _score_job(j, skills, keywords, level, idf,
                                my_fams, titles, impact, parsing,
                                my_years=_years_of(rtext))[0]
                if sc >= JOB_ALERT_FLOOR:
                    best.append((sc, j))
            # Everything at or above MIN is exceptional and always goes. If
            # nothing is, the strongest of what did arrive goes instead —
            # ranked, so the best is first either way.
            best.sort(key=lambda x: -x[0])
            # Mark everything we CONSIDERED, not everything we sent. Marking
            # only the twelve that went out left the rest unmarked, so the
            # next sweep an hour later found them again and sent those — the
            # duplicate bug, back through a side door. A posting is judged
            # once.
            for _sc, j in best:
                db.add(Note(user_id=u.id, k=f"alerted_{j.id}", v=str(_sc)))
            top_tier = [x for x in best if x[0] >= JOB_ALERT_MIN]
            best = top_tier or best[:JOB_ALERT_MAX]
            if best:
                # One bell per match, not one bell mentioning a match and
                # hiding the rest behind "and 4 more". Each alert carries its
                # own posting and its own link, so every match can be opened
                # and applied to from the bell. Capped so a bumper crawl
                # cannot bury the list; the rest are on the board.
                for sc, jj in best[:JOB_ALERT_MAX]:
                    db.add(JobAlert(
                        user_id=u.id, kind="newmatch", icon="\u2728",
                        text=f"New {sc}% match: {jj.title} at {jj.company}.",
                        url=jj.url or ""))
                    made += 1
                if len(best) > JOB_ALERT_MAX:
                    db.add(JobAlert(
                        user_id=u.id, kind="newmatch", icon="\u2728",
                        text=f"{len(best) - JOB_ALERT_MAX} more new matches are "
                             f"waiting on the board.", url=""))
                    made += 1
                # And by email. An in-app bell only reaches someone who was
                # coming back anyway; the point of an alert is to reach the
                # person who was not. Capped at five so it reads as a
                # shortlist, and at most once a day — a job board that mails
                # twice in a day gets filtered forever.
                if MAIL_ENABLED and (u.email or "").strip():
                    dkey = "alertmail_" + now().strftime("%Y%m%d")
                    if not db.query(Note).filter(Note.user_id == u.id,
                                                 Note.k == dkey).first():
                        db.add(Note(user_id=u.id, k=dkey, v="1"))
                        emailed += 1
                        nl = chr(10)
                        lines = nl.join(
                            "  " + str(sc) + "%  " + (jj.title or "") +
                            " - " + (jj.company or "") + nl +
                            "        " + (jj.url or "")
                            for sc, jj in best[:JOB_ALERT_MAX])
                        n = len(best)
                        plural = "s" if n > 1 else ""
                        first_name = (u.name or "").split(" ")[0] or "there"
                        base = PUBLIC_BASE_URL or "https://craxle.com"
                        outbox.append((
                            u.email,
                            str(n) + " new job" + plural +
                            " matching your resume",
                            "Hello " + first_name + "," + nl + nl +
                            "your " + str(n) + " best new match" + plural +
                            " came in — scored against your resume, "
                            "strongest first:" +
                            nl + nl + lines + nl + nl +
                            "See them all, with the reason behind each score:" +
                            nl + base + "/#careers" + nl + nl +
                            "You are getting this because you have a resume on "
                            "Craxle. Reply to this email to stop these alerts." + nl))
        db.commit()
    except Exception as e:
        print(f"job alert sweep failed: {type(e).__name__}: {e}")
    finally:
        db.close()
    for to, subject, body in outbox:
        try:
            send_email(to, subject, body)
        except Exception as e:
            print(f"alert mail to {to} failed: {type(e).__name__}: {e}")
    if made or emailed:
        print(f"job alerts: {made} created, {emailed} emailed")
    return {"created": made, "emailed": emailed}


@app.post("/api/admin/alerts/run")
def admin_alerts_run(user: User = Depends(admin_user)):
    """Force the alert sweep now, for testing."""
    return _job_alert_sweep()


def _renewal_sweep():
    """Warn people before their plan lapses, and expire the ones that have.

    Runs daily. A subscription ending without warning is the single most common
    cause of an angry support email, and one message two days out costs nothing.
    """
    db = SessionLocal()
    warned = expired = 0
    try:
        soon = now() + dt.timedelta(days=2)
        for u in db.query(User).filter(User.plan.in_(PAID_PLANS)).all():
            exp = u.plan_expires
            if exp is None:
                continue
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=dt.timezone.utc)

            if exp < now():
                # Lapsed. Downgrade rather than delete, so history survives.
                u.plan = "free"
                expired += 1
                continue

            # Two days out, once only.
            key = f"renew_warned_{exp.strftime('%Y%m%d')}"
            if exp <= soon and MAIL_ENABLED:
                seen = db.query(Note).filter(Note.user_id == u.id,
                                             Note.k == key).first()
                if not seen:
                    when = exp.strftime("%d %B %Y")
                    cancelled = bool(u.plan_cancelled_at)
                    body = chr(10).join([
                        f"Hello {u.name},",
                        "",
                        (f"Your Craxle {u.plan.title()} plan ends on {when}."
                         if cancelled else
                         f"Your Craxle {u.plan.title()} plan renews on {when}."),
                        "",
                        ("You cancelled, so it will not renew and you will not be "
                         "charged. After that date you keep free access to the job "
                         "board." if cancelled else
                         "Nothing to do — it renews automatically. If you would "
                         "rather it did not, cancel any time from Plans & billing "
                         "and you keep access until that date."),
                        "",
                        (PUBLIC_BASE_URL or "https://craxle.com") + "/#plans",
                        "",
                        "Craxle",
                    ])
                    subject = ("Your Craxle plan ends in 2 days" if cancelled
                               else "Your Craxle plan renews in 2 days")
                    send_email(u.email, subject, body)
                    db.add(Note(user_id=u.id, k=key, v="1"))
                    warned += 1
        db.commit()
    except Exception as e:
        print(f"renewal sweep failed: {type(e).__name__}: {e}")
    finally:
        db.close()
    if warned or expired:
        print(f"renewals: {warned} warned, {expired} expired to free")
    return {"warned": warned, "expired": expired}


@app.post("/api/admin/renewals/run")
def admin_renewals_run(user: User = Depends(admin_user)):
    """Force the renewal sweep now, for testing."""
    return _renewal_sweep()


async def _jobs_loop():
    """Crawl on the interval, but only inside the active window."""
    import asyncio
    while True:
        wait = _crawl_window_wait()
        if wait:
            print(f"jobs: outside the crawl window, sleeping {wait/3600:.1f}h")
            await asyncio.sleep(wait)
            continue
        try:
            await _refresh_jobs()
        except Exception as e:
            print(f"jobs refresh failed: {type(e).__name__}: {e}")
        # Piggy-backs on the daily loop rather than adding a scheduler. It is
        # cheap, and a plan lapsing without warning is worse than a day's delay.
        try:
            await asyncio.to_thread(_renewal_sweep)
        except Exception as e:
            print(f"renewal sweep failed: {type(e).__name__}: {e}")
        try:
            await asyncio.to_thread(_job_alert_sweep)
        except Exception as e:
            print(f"job alert sweep failed: {type(e).__name__}: {e}")
        await asyncio.sleep(JOB_REFRESH_HOURS * 3600)


# ---- matching: pure keyword work, no AI call and no token cost -------------
# Named tools, languages and platforms ONLY. Words like "support", "design",
# "product", "content" and "automation" were in here and wrecked the scoring:
# they appear in nearly every job ad, so a network engineer's resume matched a
# compliance product manager on six of them and scored 100.
_SKILLS = set("""python java javascript typescript react angular vue node django
flask fastapi spring rails golang rust kotlin swift php ruby scala c++ c#
sql postgres postgresql mysql mongodb redis elasticsearch kafka spark hadoop
airflow snowflake dbt tableau powerbi excel pandas numpy pytorch tensorflow
sklearn keras nlp llm rag opencv aws azure gcp docker kubernetes openshift
terraform ansible puppet chef jenkins gitlab github git linux unix bash
powershell microservices graphql grpc html css sass tailwind bootstrap figma
android ios flutter swiftui xamarin unity unreal godot blender selenium
cypress playwright jest pytest junit testng appium jmeter
cisco juniper aristra fortinet paloalto f5 bgp ospf mpls vlan vpn ipsec
sdwan wireshark netflow snmp tcp udp dns dhcp ldap radius nginx apache
pentesting metasploit burpsuite nessus splunk qradar siem soc iam okta
crowdstrike sentinelone cissp ceh comptia oscp
salesforce sap oracle workday netsuite hubspot marketo zendesk servicenow
jira confluence figma sketch adobe photoshop illustrator
machinelearning deeplearning datascience blockchain solidity ethereum
kubernetes helm istio prometheus grafana datadog splunk elk kibana
sre devops cicd ansible vagrant packer consul vault""".split())

# Rare, specific skills say far more about fit than common ones. Anything on
# this list is treated as near-worthless evidence on its own.
_WEAK_SKILLS = set("""git linux bash sql html css excel jira confluence
agile scrum rest json xml api""".split())

_STOP = set("""a an the and or of to in for with on at by from as is are be we
you your our their this that will can has have who what job role team work
years experience strong good great excellent ability skills required preferred
plus using use used across including etc new all more most other one""".split())


def _words(text: str):
    return _re.findall(r"[a-z][a-z0-9+#.]{1,}", (text or "").lower())


# What kind of job this is. Skill overlap alone can't tell a network engineer
# from a compliance product manager — both mention "security" and "automation".
# The role family can, and it is the difference between a useful list and noise.
_ROLE_FAMILIES = {
    "network": (
                "network automation", "telecom", "noc engineer", "network operations","network engineer", "network administrator", "noc ", "cisco",
                "routing", "switching", "bgp", "ospf", "sd-wan", "f5 ",
                "load balancer", "juniper", "palo alto", "network security",
                "network operations", "lan", "wan", "wireless engineer",
                "voip", "telecom engineer"),
    "security": (
                "soc analyst", "security analyst", "security operations centre","security engineer", "security analyst", "soc analyst",
                 "penetration test", "penetration testing", "penetration tester",
                 "pentest",
                 "pentester", "pen tester", "ethical hack", "red team",
                 "offensive security", "infosec", "appsec", "netsec",
                 "vulnerability", "threat", "cybersecurity", "cyber security",
                 "incident response", "malware", "forensic", "grc analyst",
                 "iam engineer", "identity and access",
                "information security", "security architect",
                 "security operations center", "security engineering",
                 "identity and access management", "iam analyst",
                 "identity access management", "access management engineer",
                 "compliance auditor", "it compliance", "security manager",
                 "security consultant", "security operations"),
    "sysadmin": (
                "citrix", "vmware horizon", "it manager", "endpoint", "desktop engineer","system administrator", "sysadmin", "it engineer",
                 "it support", "help desk", "helpdesk", "desktop support",
                 "it administrator", "windows administrator",
                "systems administrator", "virtualization", "vmware",
                 "it infrastructure", "data center technician",
                 "systems administration", "system administration",
                 "data center engineer", "data centre", "storage engineer",
                 "storage administrator", "migration specialist",
                 "application support", "incident manager", "service desk",
                 "endpoint engineer", "active directory"),
    "devops": ("devops", "sre", "site reliability", "platform engineer",
               "infrastructure engineer", "cloud engineer", "release engineer",
                "enterprise architect", "cloud architect",
               "cloud solutions architect", "kubernetes administrator",
               "kubernetes engineer", "ci/cd", "ci cd", "pipeline architect",
               "release manager", "build engineer", "build and automation",
               "systems engineer", "linux engineer"),
    "backend": (
                "software development", "software engineering", "sde", "development engineer", "engineering manager", "research engineer", "forward deployed", "technical architect", "design engineer", "principal engineer", "staff engineer", "member of technical staff","backend", "back-end", "software engineer", "full stack",
                "fullstack", "api engineer", "server engineer", "golang engineer",
                "api integration", "integration engineer",
                "integration specialist", "embedded systems", "embedded software",
                "embedded engineer", "firmware engineer", "game developer",
                "game engineer", "cms developer", "webmaster",
                "software developer", "java developer", "python developer",
                "php developer", ".net developer", "c++ developer"),
    "frontend": ("frontend", "front-end", "ui engineer", "web developer",
                 "javascript engineer", "react engineer",
                "web engineer", "web designer", "wordpress"),
    "mobile": ("android engineer", "ios engineer", "mobile engineer",
               "android developer", "ios developer",
                "mobile developer", "mobile application", "flutter developer",
               "react native"),
    "data": ("data engineer", "data analyst", "analytics engineer",
             "business intelligence", "etl developer", "data warehouse",
                "database administrator", "dba", "big data", "data architect",
             "data platform", "reporting analyst", "tableau developer",
             "power bi developer"),
    "ml": ("machine learning", "ml engineer", "data scientist", "ai engineer",
           "research scientist", "nlp engineer", "computer vision",
           "applied scientist",
                "ai prompt engineer", "prompt engineer", "llm engineer",
           "generative ai", "ai/ml", "ai engineering"),
    "qa": ("qa engineer", "quality assurance", "test engineer", "sdet",
           "automation engineer", "test automation",
                "qa analyst", "quality engineer", "performance test"),
    "product": (
                "product management", "technical program manager", "program management", "solutions architect","business analyst", "systems analyst",
                "business systems analyst", "it project manager",
                "product manager", "product owner", "program manager",
                "technical program", "product lead",
                "scrum master", "agile coach", "technical writer",
                "documentation specialist", "release train engineer",
                "technical product"),
    "design": ("designer", "ux ", "ui/ux", "product design", "graphic design"),
    "sales": ("account executive", "account manager", "sales ", "business development",
              "sales development", "solutions consultant", "revenue"),
    "marketing": ("marketing", "growth manager", "seo ", "content strategist",
                  "brand ", "demand generation"),
    "support": (
                "reliability engineer", "customer reliability", "field engineer", "implementation engineer", "solutions engineer", "technical account","support engineer", "customer support", "technical support",
                "customer success", "solutions architect"),
    "finance": ("financial analyst", "accountant", "accounting", "controller",
                "fp&a", "auditor", "treasury"),
    "hr": ("recruiter", "recruiting", "talent acquisition", "people operations",
           "human resources"),
    "legal": ("legal counsel", "compliance ", "paralegal", "attorney", "privacy counsel"),
    # Beyond tech — a graduate job board can't only serve engineers.
    "operations": ("operations manager", "operations associate", "business operations",
                   "supply chain", "logistics", "procurement", "warehouse",
                   "inventory", "fulfilment", "fulfillment", "dispatch"),
    "admin": ("administrative assistant", "office manager", "executive assistant",
              "receptionist", "data entry", "office administrator", "coordinator"),
    # "business analyst" lives in "product" now, not here. A BA on a technical
    # team is in scope; leaving the phrase in an out-of-scope family meant
    # every one of them was fetched and then binned at ingestion.
    "consulting": ("consultant", "strategy ", "management associate"),
    "healthcare": ("nurse", "physician", "clinical", "pharmacist", "medical ",
                   "healthcare", "therapist", "radiolog", "dental"),
    "education": ("teacher", "lecturer", "professor", "tutor", "instructor",
                  "trainer", "curriculum", "faculty", "教師"),
    "manufacturing": ("manufacturing", "production engineer", "mechanical engineer",
                      "electrical engineer", "civil engineer", "quality engineer",
                      "maintenance technician", "plant ", "assembly", "machinist"),
    # "architect " deliberately excluded — it files every Solutions Architect
    # and Data Architect under Construction.
    "construction": ("construction", "site engineer", "surveyor",
                     "foreman", "estimator", "civil engineer"),
    "hospitality": ("chef", "barista", "waiter", "server ", "hotel", "restaurant",
                    "housekeep", "front desk", "concierge", "bartender"),
    "retail": ("store manager", "sales associate", "cashier", "retail ",
               "merchandis", "shop assistant"),
    # Not a bare "delivery" — that matches Service Delivery Manager and every
    # "delivery team" in tech.
    "driver": ("driver", "delivery driver", "truck driver", "courier",
               "chauffeur", "delivery rider", "fleet manager"),
    "science": ("research associate", "laboratory", "lab technician", "chemist",
                "biologist", "scientist ", "r&d "),
    "writing": ("writer", "editor", "copywriter", "journalist", "technical writer",
                "content writer", "translator"),
}
# One label per job, so the category filter is unambiguous. The title decides
# where it can — a description mentions many kinds of work in passing.
_FAMILY_ORDER = list(_ROLE_FAMILIES)


# When a title says nothing a family recognises, the tools do. This is
# deliberately read from the parsed skill list and not from free text: reading
# the description itself is what once filed Administrative Business Partner
# under Networking. A skill is a fact about the job; a word in a paragraph is
# not. Order matters — the first family with two or more of its tools wins.
_SKILL_FAMILY = [
    ("network", ("cisco", "bgp", "ospf", "mpls", "vlan", "juniper", "f5",
                 "paloalto", "sdwan", "wireshark", "dhcp", "dns", "tcp")),
    ("security", ("siem", "soc", "splunk", "sentinel", "crowdstrike", "okta",
                  "iam", "burp", "metasploit", "nessus", "owasp", "kali",
                  "pentest", "firewall", "vpn")),
    ("devops", ("kubernetes", "terraform", "docker", "ansible", "jenkins",
                "helm", "prometheus", "grafana", "argocd", "gitops",
                "cloudformation", "openshift")),
    ("ml", ("pytorch", "tensorflow", "llm", "rag", "huggingface", "sklearn",
            "keras", "nlp", "mlflow", "langchain")),
    ("data", ("spark", "airflow", "snowflake", "dbt", "databricks", "kafka",
              "hadoop", "redshift", "bigquery", "tableau", "powerbi")),
    ("mobile", ("android", "ios", "kotlin", "swift", "flutter", "reactnative",
                "xcode")),
    ("frontend", ("react", "vue", "angular", "css", "html", "tailwind",
                  "nextjs", "typescript")),
    ("qa", ("selenium", "cypress", "playwright", "pytest", "junit",
            "appium", "testng")),
    ("backend", ("java", "python", "golang", "rust", "django", "spring",
                 "nodejs", "postgres", "mysql", "redis", "graphql")),
]


def _family_from_text(text: str) -> str:
    """A family from the tools a posting names, when its title gave us none."""
    have = {w for w in _words(text or "") if w in _SKILLS}
    if not have:
        return ""
    for fam, tools in _SKILL_FAMILY:
        if len(have & set(tools)) >= 2:
            return fam
    return ""


def _primary_family(title: str, text: str = "") -> str:
    """The job's category, from the title only.

    Reading the description instead was tried and is not safe: engineering ads
    mention 'routing' and 'delivery' in passing, which filed Administrative
    Business Partner under Networking and Android BSP Engineer under Driving.
    An uncategorised job is fine — it still appears everywhere except the
    category filter. A wrongly categorised one quietly poisons that filter.
    """
    fams = _families(title)
    if not fams:
        return ""
    if len(fams) == 1:
        return next(iter(fams))
    return sorted(fams, key=lambda f: _FAMILY_ORDER.index(f))[0]


# Human labels for the category dropdown.
CATEGORY_LABELS = {
    "network": "Networking", "security": "Cybersecurity", "sysadmin": "IT support & sysadmin",
    "devops": "DevOps & cloud", "backend": "Software engineering", "frontend": "Frontend & web",
    "mobile": "Mobile apps", "data": "Data & analytics", "ml": "AI & machine learning",
    "qa": "QA & testing", "product": "Product & programme", "design": "Design & UX",
    "sales": "Sales & business development", "marketing": "Marketing & growth",
    "support": "Customer support & success", "finance": "Finance & accounting",
    "hr": "HR & recruiting", "legal": "Legal & compliance",
    "operations": "Operations & supply chain", "admin": "Admin & office",
    "consulting": "Consulting & business analysis", "healthcare": "Healthcare & medical",
    "education": "Teaching & training", "manufacturing": "Engineering & manufacturing",
    "construction": "Construction & civil", "hospitality": "Hospitality & food",
    "retail": "Retail & stores", "driver": "Driving & delivery",
    "science": "Science & research", "writing": "Writing & content",
    # Technical, on the board, but its title names no discipline we would
    # stand behind guessing. Better an honest bucket than an invisible job.
    "other": "Other technical roles",
}
# Families close enough that crossing between them is a normal career move.
_ADJACENT = {
    "network": {"sysadmin", "devops", "security"},
    "sysadmin": {"network", "devops", "support", "security"},
    "security": {"network", "sysadmin", "devops"},
    "devops": {"backend", "sysadmin", "network", "security"},
    "backend": {"devops", "frontend", "data", "ml"},
    "frontend": {"backend", "mobile", "design"},
    "mobile": {"frontend", "backend"},
    "data": {"ml", "backend", "product"},
    "ml": {"data", "backend"},
    "qa": {"backend", "devops"},
    "product": {"design", "data", "marketing"},
    "design": {"frontend", "product"},
    "sales": {"marketing", "support"},
    "marketing": {"sales", "product"},
    "support": {"sysadmin", "sales"},
}


# Word-boundary matched, not substring. Plain `in` reads "cisco" out of "San
# Francisco" and "writer" out of "Underwriter", which filed account executives
# under Networking and credit analysts under Writing.
# The trailing guard allows the ordinary word endings: "platform engineer"
# has to match "Platform Engineering Manager", "systems administrator" has to
# match "Systems Administration", or the title reads as no family at all and
# the posting falls off a board that crawled for exactly that role.
# One pattern per family, not one per keyword. Matching ran every keyword's
# regex separately — about 230 scans of the same short string per title —
# which was 3s of a match request once the keyword list grew. The regex
# engine does the alternation far better than a Python loop can: same
# answers, one pass.
_FAMILY_RE = {
    fam: _re.compile(r"(?<![a-z])(?:"
                     + "|".join(_re.escape(k.strip()) for k in keys)
                     + r")(?:s|es|ing)?(?![a-z])")
    for fam, keys in _ROLE_FAMILIES.items()}


def _families(text: str):
    """Which role families this text reads as. Empty when nothing is clear."""
    low = " " + (text or "").lower() + " "
    hit = {fam for fam, rx in _FAMILY_RE.items() if rx.search(low)}
    if hit:
        return hit
    # Nothing matched: try again with brackets, slashes and dashes turned
    # into spaces. Employers write "Security (SOC) Analyst" and "Network
    # Automation / Python Engineer", and both were filed as Other for the
    # sake of a bracket.
    flat = " " + _re.sub(r"[^a-z0-9+#]+", " ", (text or "").lower()).strip() + " "
    if flat != low:
        return {fam for fam, rx in _FAMILY_RE.items() if rx.search(flat)}
    return hit


@lru_cache(maxsize=40000)
def _title_families(title: str):
    """_families for a job title, memoised.

    Called once per posting per match — 12,000 titles against 30 families of
    regexes each — and titles repeat heavily across a board. Uncached it cost
    ~2.5s on a full match, which is most of the request.
    """
    return frozenset(_families(title))


def _family_hits(text: str):
    """How much evidence there is for each family, not merely any."""
    low = " " + (text or "").lower() + " "
    out = {}
    for fam, rx in _FAMILY_RE.items():
        n = len(rx.findall(low))
        if n:
            out[fam] = n
    return out


def _resume_families(text: str):
    """The families a RESUME actually belongs to.

    A job ad is short and on-topic, so one mention means something. A resume
    is not: a network engineer who once supported a hospital, a hotel chain
    and a retail client reads as healthcare, hospitality and retail under a
    presence test — and once a resume claims six families, the family gate in
    scoring matches nearly every posting and stops gating at all. That is why
    a Sr Network Engineer was being shown Head of AI and FinOps roles at 60+.

    So weigh the evidence: keep what the resume is mostly about, drop what it
    mentions in passing.
    """
    hits = _family_hits(text)
    if not hits:
        return set()
    top = max(hits.values())
    floor = max(2, top * 0.15)
    kept = {f for f, n in hits.items() if n >= floor}
    if not kept:                                   # thin resume, one signal
        kept = {max(hits, key=lambda f: hits[f])}
    # Four is already generous for one person's career.
    return set(sorted(kept, key=lambda f: -hits[f])[:4])


def _profile(resume_text: str):
    """Turn a resume into the keyword set we score jobs against."""
    ws = _words(resume_text)
    skills = {w for w in ws if w in _SKILLS}
    low = (resume_text or "").lower()
    # Multi-word skills the token split would lose.
    for phrase, tag in (("machine learning", "machinelearning"),
                        ("deep learning", "deeplearning"),
                        ("data science", "datascience"),
                        ("react native", "reactnative"),
                        ("power bi", "powerbi"),
                        ("palo alto", "paloalto"),
                        ("sd-wan", "sdwan")):
        if phrase in low:
            skills.add(tag)
    keywords = {w for w in ws if len(w) > 3 and w not in _STOP}
    return skills, keywords


_SENIOR = ("senior", "sr.", "staff", "principal", "lead", "head", "director",
           "manager", "architect", "vp")
# Running the function is not the senior version of doing the work. "Head of",
# "Director" and "VP" sat in _SENIOR, so a senior individual contributor was
# scored a perfect seniority match for Head of AI Forward Deployed
# Engineering — a job they cannot get and did not ask for.
_EXEC = ("head of", "director", "vp ", "vp,", "vice president", "chief ",
         "cto", "ciso", "cio", "president", "partner,", "general manager")
_JUNIOR = ("intern", "internship", "graduate", "trainee", "junior", "entry",
           "fresher", "apprentice", "associate", "working student",
           "student ", "co-op", "placement", "level 1", "tier 1")


# ---- resume-level signals -------------------------------------------------
# Computed once per search, not per job: they describe the resume, not the fit.

_ACTION_SENIOR = ("led", "spearheaded", "owned", "drove", "architected", "founded",
                  "directed", "managed", "built", "designed", "launched", "scaled",
                  "negotiated", "mentored", "established", "delivered", "reduced",
                  "increased", "grew", "saved", "migrated", "automated")
_ACTION_JUNIOR = ("assisted", "supported", "helped", "participated", "shadowed",
                  "learned", "attended", "observed", "maintained", "updated")
# A metric is a number doing work: a percentage, money, a multiplier, a count of
# people, or a unit of time or data.
_METRIC_RE = _re.compile(
    r"(\d+\s?%|[$₹€£]\s?\d|\d+\s?(x|k|m|bn|cr|lakh)|"
    r"\d+\s?(people|engineers|members|users|customers|clients|hours|days|"
    r"weeks|months|ms|seconds|tb|gb|qps|rps))", _re.I)


def _impact_score(rtext: str) -> float:
    """How much of the resume shows outcomes rather than duties.

    Recruiters and ATS models both reward "reduced latency by 35%" over
    "responsible for performance". This measures that directly.
    """
    low = (rtext or "").lower()
    lines = [l for l in low.splitlines() if len(l.strip()) > 25]
    if not lines:
        return 0.0
    with_metric = sum(1 for l in lines if _METRIC_RE.search(l))
    strong = sum(1 for v in _ACTION_SENIOR if v in low)
    weak = sum(1 for v in _ACTION_JUNIOR if v in low)
    metric_ratio = min(with_metric / max(len(lines) * 0.4, 1), 1.0)   # ~40% is strong
    verb_ratio = strong / max(strong + weak, 1)
    return round(0.65 * metric_ratio + 0.35 * verb_ratio, 3)


_SECTIONS = ("experience", "education", "skills", "projects", "summary",
             "employment", "work history", "certification")


def _parsing_score(rtext: str) -> float:
    """Whether this resume is machine-readable at all.

    A real ATS drops candidates whose layout it cannot parse. We cannot see
    the layout, but we can see what survived extraction — too little text, or
    no recognisable section headings, means an employer's parser will
    struggle with the same file.
    """
    low = (rtext or "").lower()
    if not low.strip():
        return 0.0
    found = sum(1 for h in _SECTIONS if h in low)
    words = len(low.split())
    length_ok = 1.0 if 200 <= words <= 1200 else (0.6 if words >= 80 else 0.25)
    # Very long unbroken runs usually mean a multi-column layout collapsed.
    longest_line = max((len(l) for l in low.splitlines()), default=0)
    layout_ok = 0.6 if longest_line > 600 else 1.0
    return round(min(found / 4.0, 1.0) * 0.5 + length_ok * 0.35 + layout_ok * 0.15, 3)


def resume_advice(rtext, impact, parsing, skills):
    """Specific, checkable fixes — not "improve your resume".

    Each item names what is wrong, why it is penalised, and what to write
    instead. Ordered so the fix worth the most points comes first.
    """
    low = (rtext or "").lower()
    lines = [l.strip() for l in (rtext or "").splitlines() if len(l.strip()) > 25]
    tips = []

    with_metric = sum(1 for l in lines if _METRIC_RE.search(l))
    if lines and with_metric / len(lines) < 0.3:
        tips.append({
            "area": "Quantified impact", "weight": 17, "severity": "high",
            "problem": "Only %d of your %d bullet points contain a number."
                       % (with_metric, len(lines)),
            "why": "Scoring rewards outcomes over duties. Responsible for "
                   "reporting and cut reporting time from 6h to 20min describe "
                   "the same work; only one is evidence.",
            "fix": "Add a number to at least a third of your bullets — a "
                   "percentage, an amount, a team size, time saved, volume "
                   "handled. Honest estimates are fine.",
            "example": "Before: Improved database performance"
                       + chr(10) +
                       "After:  Cut checkout query time from 3s to 200ms, "
                       "removing timeouts on sale days",
        })

    weak = [v for v in _ACTION_JUNIOR if v in low]
    if weak:
        tips.append({
            "area": "Action verbs", "weight": 27, "severity": "medium",
            "problem": "You use passive verbs: %s." % ", ".join(weak[:4]),
            "why": "Verbs signal seniority. Assisted with reads as support; "
                   "led and owned read as responsibility, and seniority is part "
                   "of role fit.",
            "fix": "Replace them with what you decided or delivered.",
            "example": "Before: Assisted with the migration"
                       + chr(10) +
                       "After:  Migrated 40 sites to BGP with no unplanned downtime",
        })

    missing = [h for h in ("experience", "education", "skills") if h not in low]
    if missing:
        tips.append({
            "area": "Section headings", "weight": 8, "severity": "high",
            "problem": "No clear %s heading found." % ", ".join(missing),
            "why": "Parsers assign content by heading. Without them your jobs "
                   "and qualifications may not be filed as either, and can be "
                   "dropped entirely.",
            "fix": "Use plain headings on their own line: Experience, "
                   "Education, Skills. Avoid names like My Journey.",
            "example": "Experience" + chr(10) +
                       "Senior Network Engineer — Acme (2018-2025)",
        })

    words = len(low.split())
    if words < 200:
        tips.append({
            "area": "Length and parsing", "weight": 8, "severity": "high",
            "problem": "Only about %d words could be extracted." % words,
            "why": "Either the resume is very short, or it is an image or a "
                   "layout the parser could not read — an employer system will "
                   "hit the same wall.",
            "fix": "Export a text-based PDF, single column, no text boxes or "
                   "graphics. Paste it into a plain text editor: what you see "
                   "there is all an ATS sees.",
        })
    elif words > 1200:
        tips.append({
            "area": "Length", "weight": 8, "severity": "low",
            "problem": "About %d words — long for a resume." % words,
            "why": "Detail on old roles dilutes the recent work being assessed.",
            "fix": "Keep the last 10 years detailed; compress older roles to a line.",
        })

    longest = max((len(l) for l in (rtext or "").splitlines()), default=0)
    if longest > 600:
        tips.append({
            "area": "Layout", "weight": 8, "severity": "high",
            "problem": "Text extracted as very long unbroken runs.",
            "why": "That is the signature of a multi-column or table layout "
                   "collapsing, which interleaves columns and destroys meaning.",
            "fix": "Rebuild in a single column. Two-column resumes parse badly "
                   "almost everywhere.",
        })

    if len(skills) < 6:
        tips.append({
            "area": "Skills section", "weight": 33, "severity": "high",
            "problem": "Only %d recognisable tools or technologies found." % len(skills),
            "why": "Hard skills carry the most weight. Skills implied by prose "
                   "but never named are invisible to keyword matching.",
            "fix": "Add a Skills line naming tools explicitly — languages, "
                   "frameworks, cloud, databases — even where your experience "
                   "section already implies them.",
            "example": "Skills: Python, SQL, AWS, Docker, Kubernetes, "
                       "Terraform, PostgreSQL",
        })

    if "summary" not in low and "objective" not in low:
        tips.append({
            "area": "Summary", "weight": 27, "severity": "low",
            "problem": "No summary line at the top.",
            "why": "The first lines are where a target title is looked for, and "
                   "title match is part of role fit.",
            "fix": "Two lines naming the role you want and your strongest "
                   "relevant skills.",
            "example": "Senior Network Engineer — 7 years in enterprise WAN/LAN. "
                       "BGP, OSPF, F5, Palo Alto, Python automation.",
        })

    rank = {"high": 0, "medium": 1, "low": 2}
    tips.sort(key=lambda t: (rank[t["severity"]], -t["weight"]))
    return tips


class AtsCheckIn(BaseModel):
    resume: dict = {}
    resume_text: str = Field(default="", max_length=40000)


@app.post("/api/resume/ats-check")
def resume_ats_check(body: AtsCheckIn, user: User = Depends(current_user)):
    """Score a resume for ATS readiness and say exactly what to change.

    Free and AI-free on purpose: it runs the same checks the matcher runs, so
    the advice always agrees with the score. Nobody should have to pay to be
    told their resume is unreadable.
    """
    rtext = (body.resume_text or "").strip() or _resume_text(body.resume or {})
    if len(rtext.strip()) < 40:
        raise HTTPException(400, "Add some resume details first, or upload a resume.")
    skills, _kw = _profile(rtext)
    impact, parsing = _impact_score(rtext), _parsing_score(rtext)
    overall = round(100 * (0.55 * impact + 0.30 * parsing
                           + 0.15 * min(len(skills) / 12, 1.0)))
    return {
        "ats_score": overall, **match_tier(overall),
        "impact_score": round(impact * 100),
        "readability_score": round(parsing * 100),
        "skills_found": sorted(x for x in skills if x not in _WEAK_SKILLS)[:30],
        "skills_count": len(skills),
        "advice": resume_advice(rtext, impact, parsing, skills),
        "note": "These checks mirror what the job matcher scores, so fixing "
                "them raises your match on every job at once.",
    }


def _posted_label(posted: str) -> str:
    """The date filter, in the words the dropdown uses."""
    return {"1": "roles posted in the past 24 hours",
            "3": "roles posted in the past 3 days",
            "7": "roles posted in the past week",
            "14": "roles posted in the past fortnight",
            "30": "roles posted in the past month"}.get(
        str(posted or "").strip(), "all open roles")


def _ats_view(rtext: str, scored: list, impact: float, parsing: float,
              skills=None, pool_label: str = "") -> dict:
    """How this resume looks to the software that reads it first.

    The score is a property of the resume and nothing else. It used to be
    built mostly from requirement coverage across whatever jobs the current
    filters had left, which meant the same untouched file scored 81 on "past
    week" and 58 on "past 24 hours" — the smaller window simply had weaker
    roles in it to be compared against. A number captioned "how your resume
    reads to the software that screens it" cannot move when somebody changes
    a date dropdown; either it is about the resume or it is not.

    So the three parts are all measured from the document: whether it carries
    the vocabulary a keyword scan looks for, whether it can be parsed at all,
    and whether the claims have evidence. Requirement coverage against live
    roles is still worth knowing and is still returned — as `pool`, labelled
    with the filter it was measured over, because that one genuinely does
    change when you change the filter and should be seen to.
    """
    low = (rtext or "").lower()
    skills = skills or set()
    real = {s for s in skills if s not in _WEAK_SKILLS}

    # An ATS keyword scan happens before any particular job: it is looking for
    # recognised, nameable skills in the document. Twelve is roughly where a
    # resume stops being thin — beyond that, more keywords is padding, not
    # strength, so it saturates rather than rewarding a wall of nouns.
    keyword = min(len(real) / 12.0, 1.0)

    have_sections = sum(1 for w in ("experience", "skills", "education",
                                    "summary", "project") if w in low)
    checks = [
        {"ok": have_sections >= 3,
         "t": "Standard sections an ATS can find" if have_sections >= 3
              else "Add clear Experience / Skills / Education headings"},
        {"ok": parsing >= 0.6,
         "t": "Text extracts cleanly" if parsing >= 0.6
              else "Hard to parse — avoid tables, columns and images"},
        {"ok": impact >= 0.4,
         "t": "Achievements carry numbers" if impact >= 0.4
              else "Add figures to your bullets — %, £, users, uptime"},
        {"ok": keyword >= 0.75,
         "t": f"{len(real)} recognised skills a keyword scan can pick up"
              if keyword >= 0.75
              else f"Only {len(real)} recognised skills — name your tools and "
                   f"technologies explicitly"},
    ]

    score = round(100 * (0.40 * keyword + 0.35 * parsing + 0.25 * impact))
    out = {"score": max(0, min(100, score)),
           "keyword_match": round(keyword * 100),
           "parse_quality": round(parsing * 100),
           "impact_evidence": round(impact * 100),
           "checks": checks,
           "verdict": ("Passes most filters" if score >= 65 else
                       "Gets through some filters" if score >= 45 else
                       "Likely to be screened out")}

    # The twenty best fits, not two hundred. Nobody applies to the two
    # hundredth-best match, so averaging over that tail measures a search
    # nobody runs.
    near = [d for d in scored if d["score"] >= 45][:20]
    if near:
        tot = hit = 0
        for d in near:
            tot += len(d.get("missing") or []) + len(d.get("matched") or [])
            hit += len(d.get("matched") or [])
        cover = (hit / tot) if tot else 0.0
        out["pool"] = {
            "cover": round(cover * 100),
            "roles": len(near),
            "label": pool_label or "the roles you are viewing",
            "note": f"Across the {len(near)} closest of "
                    f"{pool_label or 'the roles you are viewing'}, you meet "
                    f"{round(cover * 100)}% of the stated requirements. This "
                    f"one moves when you change the filters, because it is "
                    f"about the jobs, not about your resume.",
        }
    return out


def match_tier(score: int) -> dict:
    """The band a score falls in, in the language recruiters actually use.

    The bands were 85 / 70 / 55, set when scoring was looser. Measured across
    the live board with four resume profiles, the best score any of them
    reached was 77 — so "Exceptional fit" was unreachable and most real
    matches were being labelled "Average". A band nobody can reach does not
    set a high standard, it tells good candidates they are mediocre. These
    match what the scoring actually produces.
    """
    if score >= 72:
        return {"tier": "S", "label": "Exceptional fit",
                "note": "Strong overlap on skills, seniority and evidence."}
    if score >= 60:
        return {"tier": "A", "label": "Strong candidate",
                "note": "Meets the core requirements with minor gaps."}
    if score >= 45:
        return {"tier": "B", "label": "Worth applying",
                "note": "Real overlap, with gaps you can name and close."}
    return {"tier": "C", "label": "Weak fit",
            "note": "Significant mismatch on skills or experience level."}


def _job_skills(job):
    """The job's skills, from the column filled at ingest.

    Falls back to parsing the text for rows stored before that column
    existed, so an older database still matches until the next crawl.

    Memoised on the instance: a match request asks for the same job's skills
    twice — once to measure rarity across the board, once to score — and the
    fallback path is a regex pass over 4,000 characters. At 11,000 postings
    that second pass was over two seconds of a seven-second request, spent
    recomputing an answer we already had."""
    got = getattr(job, "_skills_memo", None)
    if got is None:
        got = (set(job.skills.split(",")) if job.skills
               else {w for w in _words(job.text or "") if w in _SKILLS})
        try:
            job._skills_memo = got
        except Exception:          # not an ORM row; nothing to cache on
            pass
    return got


def _job_req_skills(job):
    """Skills the posting lists as requirements, not merely mentions.

    Read from the column filled at ingest, and deliberately NOT re-derived
    here when it is empty: parsing 5,000 descriptions per request took ten
    seconds. Rows stored before this column existed simply score without the
    requirement weighting until the next crawl fills them.
    """
    memo = getattr(job, "_req_memo", None)
    if memo is not None:            # filled in bulk by the match endpoint
        return memo
    got = getattr(job, "req_skills", "") or ""
    return set(got.split(",")) if got else set()


# Words in a job title that say what the role IS, so a resume aimed at one
# thing stops matching a title about something else.
_TITLE_STOP = set("""senior junior lead principal staff sr jr i ii iii iv the a an
and or of for with new remote hybrid onsite full time part contract intern
level entry mid experienced years year team group global regional""".split())


def _title_words(t):
    return {w for w in _words(t or "") if w not in _TITLE_STOP and len(w) > 2}


def _score_job(job, skills, keywords, level, idf=None, my_fams=None,
               my_titles=None, impact=0.5, parsing=0.8, my_years=0):
    """0-100 fit score, plus the skills that matched and the ones missing.

    Two things keep this honest. Skills are weighted by how rare they are
    across the live postings, so matching 'kubernetes' counts for far more
    than matching 'git'. And the job's role family must line up with the
    resume's — without that gate, shared buzzwords alone rated a network
    engineer a perfect fit for a compliance product manager.
    """
    my_titles = my_titles or set()
    jskills = _job_skills(job)
    jreq = _job_req_skills(job) or jskills
    jwords = _title_words(job.title)
    idf = idf or {}

    hit = skills & jskills
    miss = jskills - skills
    req_hit = skills & jreq
    req_miss = jreq - skills

    def w(s):
        base = idf.get(s, 1.0)
        # A skill named under Requirements counts triple: that is the job
        # asking for it, rather than the word appearing somewhere in the ad.
        if s in jreq:
            base *= 3.0
        return base * (0.25 if s in _WEAK_SKILLS else 1.0)

    want = sum(w(s) for s in jskills)
    have = sum(w(s) for s in hit)
    coverage = (have / want) if want else 0.0
    depth = min(have / 4.0, 1.0)          # absolute weight of what you matched

    # How many of the stated requirements you actually meet. This is the number
    # a human recruiter is really applying, so it carries the most weight.
    req_cover = (len(req_hit) / len(jreq)) if jreq else 0.0

    # Does the job title describe the same work as the resume's own titles?
    # Without this, anything sharing a toolchain scored alike, which is why
    # results felt like "3 to 8 things they happen to do".
    title_overlap = (len(jwords & my_titles) / len(jwords)) if (jwords and my_titles) else 0.0

    # ---- five weighted factors, the model real ATS products use ----
    # 1. Hard skills (33%) — what you can do, with stated requirements
    #    counted far more heavily than a passing mention.
    f_skills = 0.55 * req_cover + 0.30 * coverage + 0.15 * depth

    # 2. Role fit and seniority (27%) — is this the same job at the same level?
    # The stored category comes from the title alone and is often blank —
    # "Enterprise Solutions Engineer" matches no family. Re-reading the title
    # here catches some of those; what is left genuinely unknown scores below
    # a confirmed same-family match, because "we could not tell" should never
    # outrank "this is your field", which is what a flat 0.5 did.
    # "other" is a shelf, not a discipline — scoring it as a family would tell
    # every resume the job is in the wrong field.
    job_fams = ({job.category} if (job.category and job.category != "other")
                else _title_families(job.title or ""))
    if my_fams and job_fams:
        fam = 1.0 if (job_fams & my_fams) else (
            0.55 if job_fams & {f for m in my_fams for f in _ADJACENT.get(m, set())}
            else 0.10)
    else:
        fam = 0.42                     # unknown family: mild doubt, not a veto
    title = (job.title or "").lower()
    is_exec = any(t in title for t in _EXEC)
    seniority = 0.5
    if level == "senior":
        if any(t in title for t in _JUNIOR):
            seniority = 0.15
        elif is_exec:
            seniority = 0.35        # a step up in kind, not in grade
        elif any(t in title for t in _SENIOR):
            seniority = 1.0
        else:
            seniority = 0.6
    elif level == "junior":
        seniority = 0.10 if is_exec else (
            0.15 if any(t in title for t in _SENIOR) else (
                1.0 if any(t in title for t in _JUNIOR) else 0.6))
    # Years demanded versus years held. Seniority was read from title words
    # alone, so "12 Years of exp Required" against an 8-year resume scored 80:
    # nothing in the model had looked at the sentence doing the rejecting. A
    # year or two short is normal and costs nothing; four years short is the
    # filter a recruiter actually applies.
    need = getattr(job, "min_years", 0) or 0
    short = max(0, need - my_years) if (need and my_years) else 0
    if short >= 4:
        seniority *= 0.35
    elif short >= 2:
        seniority *= 0.65

    f_role = 0.45 * fam + 0.30 * min(title_overlap * 1.5, 1.0) + 0.25 * seniority

    # 3. Evidence of impact (17%) and 5. readability (8%) describe the resume,
    #    so they are the same for every job in one search — passed in rather
    #    than recomputed 6,000 times.
    f_impact = impact
    f_parse = parsing

    # 4. Domain (15%) — same industry beats same toolchain. Approximated by the
    #    role family, which is the only industry signal a posting reliably gives.
    f_domain = fam

    score = 100 * (0.33 * f_skills + 0.27 * f_role + 0.17 * f_impact
                   + 0.15 * f_domain + 0.08 * f_parse)

    # Impact and readability are 25% of the weight and identical for every
    # posting in a search — they describe the resume, not the fit. On a job in
    # the wrong field that floor alone floated scores into the sixties, which
    # is how a network engineer saw Head of AI at 65. Relevance has to be able
    # to veto: if neither the family nor the title lines up, the whole score
    # comes down, rather than the mismatch being averaged away.
    relevance = max(fam, min(title_overlap * 1.5, 1.0))
    if relevance < 0.5:
        score *= 0.55 + 0.9 * relevance     # 0.10 → x0.64, 0.5 → x1.0

    # Years short is a gate, not a nudge. Routed through seniority alone it
    # moved a 12-years-wanted / 8-years-held posting from 74 to 72, which is
    # not what a recruiter's filter does with that CV. Four years short is
    # usually an automatic no; two is worth flagging and still applying for.
    if short >= 4:
        score *= 0.78
    elif short >= 2:
        score *= 0.92

    # A posting too thin to name a few skills cannot support a confident score.
    if len(jskills) < 3:
        score *= 0.7
    if any(s in title for s in skills if s not in _WEAK_SKILLS):
        score += 4

    # Why the number is the number. Every other board shows a percentage and
    # leaves you to guess; this is the same arithmetic said in words, and it
    # costs nothing because the arithmetic already happened. Ordered worst
    # news first — the reason to skip a job is worth more than the reason to
    # like it.
    why = []
    if jreq:
        why.append(("ok" if req_cover >= 0.6 else "no",
                    f"{len(req_hit)} of {len(jreq)} requirements met"))
    if fam >= 1.0:
        why.append(("ok", "your field"))
    elif fam >= 0.55:
        why.append(("mid", "next to your field"))
    elif fam <= 0.15:
        why.append(("no", "different field"))
    if level == "senior":
        if seniority <= 0.2:
            why.append(("no", "below your level"))
        elif is_exec:
            why.append(("mid", "a leadership role"))
        elif seniority >= 1.0:
            why.append(("ok", "your level"))
    elif level == "junior" and seniority <= 0.2:
        why.append(("no", "above your level"))
    if short >= 2:
        why.append(("no", f"wants {need} years, you have {my_years}"))
    elif need and my_years >= need:
        why.append(("ok", f"{need}+ years asked, you have {my_years}"))
    if title_overlap >= 0.5:
        why.append(("ok", "same job title"))
    if req_miss:
        why.append(("mid", "missing " + ", ".join(sorted(req_miss)[:3])))
    return (max(0, min(100, round(score))), sorted(hit)[:12],
            # Every gap, not the first eight. A truncated list looks like the
            # whole list, so someone learns what we showed and applies again
            # still missing things nobody told them about. Requirements first
            # — those are the ones the employer actually asked for — then the
            # rest of what the posting mentions.
            sorted(req_miss) + [s for s in sorted(miss) if s not in req_miss],
            [{"k": k, "t": t} for k, t in why[:5]])


def _years_of(resume_text: str) -> int:
    """Years of experience the resume claims, or 0. Highest figure stated —
    a resume saying "8 years" and "3 years with Kubernetes" has 8."""
    got = _years_matches(resume_text)
    return max(got) if got else 0


def _level_of(resume_text: str):
    """Seniority, from job titles only.

    Held titles are checked first and degrees are ignored on purpose: almost
    every resume lists a B.Tech or a graduation, so treating those as junior
    signals labelled experienced people junior and docked their best matches.
    """
    low = (resume_text or "").lower()
    # "Sr." with the full stop was required, so "Sr Network Engineer" — how
    # most people actually write it, and how it survives a filename — read as
    # no level at all, and every seniority comparison fell back to neutral.
    if re.search(r"(?<![a-z])(senior|sr\.?|lead|principal|staff|head of|"
                 r"manager|architect)(?![a-z])", low):
        return "senior"
    # Failing a title, years of experience say it plainly.
    yrs = [int(x) for x in re.findall(r"(\d{1,2})\s*\+?\s*years?(?:\s+of)?\s+"
                                      r"(?:professional\s+|work\s+|total\s+)?experience",
                                      low)]
    if yrs and max(yrs) >= 6:
        return "senior"
    if any(t in low for t in ("intern", "fresher", "trainee", "recent graduate",
                              "currently studying", "final year")):
        return "junior"
    if yrs and max(yrs) <= 1:
        return "junior"
    return ""


def _job_json(j, extra=None):
    d = {
        "id": j.id, "title": j.title, "company": j.company,
        "location": j.location or ("Remote" if j.remote else ""),
        "country": j.country, "remote": bool(j.remote), "url": j.url,
        "category": j.category or "", "is_open": bool(j.is_open),
        "job_type": j.job_type or "", "engagement": j.engagement or "",
        "salary": j.salary or "",
        "visa": j.visa or "",
        "posted_at": j.posted_at.isoformat() if j.posted_at else None,
        "first_seen": j.first_seen.isoformat() if j.first_seen else None,
        "closed_at": j.closed_at.isoformat() if j.closed_at else None,
    }
    if extra:
        d.update(extra)
    return d


# How recent a posting is. Employers give a posted date when they can; when
# they don't, when we first saw it is the honest stand-in.
POSTED_WINDOWS = [{"id": "1", "label": "Past 24 hours", "days": 1},
                  {"id": "3", "label": "Past 3 days", "days": 3},
                  {"id": "7", "label": "Past week", "days": 7},
                  {"id": "30", "label": "Past month", "days": 30}]


def _jobs_query(db, q="", country="", location="", remote=False, status="open",
                category="", job_type="", engagement="", visa="", posted="",
                wide=False):
    query = db.query(Job)
    if posted:
        try:
            days = int(posted)
        except ValueError:
            days = 0
        if days > 0:
            cut = now() - dt.timedelta(days=days)
            query = query.filter(
                case((Job.posted_at.isnot(None), Job.posted_at),
                     else_=Job.first_seen) >= cut)
    if job_type:
        query = query.filter(Job.job_type == job_type.strip().lower())
    if engagement:
        # "w2_c2c" postings accept either, so they belong in both filters.
        e = engagement.strip().lower()
        query = query.filter(Job.engagement.in_([e, "w2_c2c"])
                             if e in ("w2", "c2c") else Job.engagement == e)
    if visa:
        query = query.filter(Job.visa == visa.strip().lower())
    if status == "open":
        query = query.filter(Job.is_open == True)      # noqa: E712
    elif status == "closed":
        query = query.filter(Job.is_open == False)     # noqa: E712
    if category:
        cat = category.strip().lower()
        if cat == "other":
            # "Other" is the bucket the category list puts everything
            # unlabelled into, so selecting it has to return those rows too —
            # otherwise the dropdown offers a count of five thousand and the
            # page comes back nearly empty, which is the same "the number
            # says one thing, the list says another" bug in a new place.
            query = query.filter(or_(Job.category == "other",
                                     Job.category == "",
                                     Job.category.is_(None)))
        else:
            query = query.filter(Job.category == cat)
    if country:
        query = query.filter(func.lower(Job.country) == country.strip().lower())
    if location:
        query = query.filter(func.lower(Job.location).like(f"%{location.strip().lower()}%"))
    if remote:
        query = query.filter(Job.remote == True)       # noqa: E712
    if q:
        # Every word, not the whole phrase, and never the description.
        #
        # One "%network engineer%" over title, company AND the 4,000-character
        # body did two bad things at once. It missed "Engineer, Network
        # Operations", because the words are not adjacent in that order. And
        # it returned every posting whose body mentions python when someone
        # searched python — a sales role that says "works with our Python
        # team" ranked beside a Python job. That is the noise.
        #
        # Now: split into words, every word must appear, and each may appear
        # in the title, the company or the parsed skills. Skills is what makes
        # a bare "terraform" work without dragging the body in — it is a list
        # of tools the posting actually asks for, not prose about them.
        words = [w for w in _re.split(r"[^a-z0-9+#.]+", q.strip().lower()) if w][:6]
        for w in words:
            like = f"%{w}%"
            # Location is in here because the city box is gone: one box has
            # to find "dallas" and "remote" as readily as it finds "network
            # engineer", or removing the filter removes the capability.
            cond = (func.lower(Job.title).like(like)
                    | func.lower(Job.company).like(like)
                    | func.lower(Job.skills).like(like)
                    | func.lower(Job.location).like(like))
            # Widened only when the precise search found nothing. Someone
            # searching Citrix or ServiceNow is looking for a real thing we
            # simply do not have in the skills vocabulary, and an empty page
            # is a worse answer than a slightly noisy one.
            if wide:
                cond = cond | func.lower(Job.text).like(like)
            query = query.filter(cond)
    return query


@app.get("/api/jobs")
def jobs_search(q: str = "", country: str = "", location: str = "",
                remote: bool = False, status: str = "open", limit: int = 20,
                offset: int = 0, category: str = "", job_type: str = "",
                engagement: str = "", visa: str = "", posted: str = "",
                user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Search the stored postings. Newest first.

    Free accounts see a delayed, capped slice. Fresh postings are the whole
    value of a job board — being early is what gets someone an interview — so
    that is what Pro buys. The free view is real and useful, just behind.
    """
    free = plan_of(user) == "free" and not getattr(user, "is_admin", False)
    query = _jobs_query(db, q, country, location, remote, status, category, job_type, engagement, visa, posted)
    # If a precise search finds nothing, look in the descriptions before
    # giving up. Tools we do not know by name — Citrix, ServiceNow, NetSuite —
    # exist only in the body text, and "no results" for a word that is
    # plainly in the postings reads as a broken search.
    widened = False
    if q and query.order_by(None).count() == 0:
        query = _jobs_query(db, q, country, location, remote, status, category,
                            job_type, engagement, visa, posted, wide=True)
        widened = True
    if free and FREE_JOB_DELAY_DAYS > 0:
        # Anything newer than this is Pro-only. Compared against the employer's
        # posting date where we have it, falling back to when we first saw it.
        cutoff = now() - dt.timedelta(days=FREE_JOB_DELAY_DAYS)
        query = query.filter(
            case((Job.posted_at.isnot(None), Job.posted_at), else_=Job.first_seen) <= cutoff)
    if q:
        # Searching "engineer" must not put a sales role that merely mentions
        # engineers above an actual engineering job. Title hits rank first.
        # Title hits first, then the rest, newest inside each group. Searching
        # "python" should lead with Python Developer, not with a job that
        # happens to list python among nine tools.
        # Four tiers, because "network engineer" should return every network
        # engineer — junior, senior and plain — before it returns a software
        # engineer who touches networking.
        #   0  the exact phrase in the title      Senior Network Engineer
        #   1  every word in the title, any order  Engineer, Network Operations
        #   2  the first word in the title         Network Reliability Engineer
        #   3  matched on skills or company only   anything else
        ql = q.strip().lower()
        words = [w for w in _re.split(r"[^a-z0-9+#.]+", ql) if w][:6]
        all_in_title = None
        for w in words:
            c = func.lower(Job.title).like(f"%{w}%")
            all_in_title = c if all_in_title is None else (all_in_title & c)
        tiers = [(func.lower(Job.title).like(f"%{ql}%"), 0)]
        if all_in_title is not None:
            tiers.append((all_in_title, 1))
        if words:
            tiers.append((func.lower(Job.title).like(f"%{words[0]}%"), 2))
        query = query.order_by(
            case(*tiers, else_=3),
            case((Job.posted_at.isnot(None), Job.posted_at), else_=Job.first_seen).desc())
    else:
        # Order by when the employer posted it, not when we happened to crawl
        # it. Every row is crawled at once, so first_seen is near-identical
        # across the whole table and sorts into meaningless order.
        query = query.order_by(case((Job.posted_at.isnot(None), Job.posted_at), else_=Job.first_seen).desc())
    off, lim = max(offset, 0), min(max(limit, 1), 50)
    total = query.order_by(None).count()
    if free and FREE_JOB_CAP > 0:
        # Cap what can be paged to, not just the page size — otherwise the
        # whole board is reachable a page at a time.
        total = min(total, FREE_JOB_CAP)
        lim = min(lim, FREE_JOB_CAP)
        if off >= FREE_JOB_CAP:
            off = max(0, FREE_JOB_CAP - lim)
        lim = min(lim, max(0, FREE_JOB_CAP - off))
    # Collapse the same posting appearing many times.
    #
    # JSearch returns one role once per board it found it on, each with its
    # own id, so "Security (SOC) Analyst Jobs" at UltraViolet Cyber filled six
    # consecutive slots on the page. The match endpoint has always collapsed
    # these by title and company; browsing never did, and browsing is where
    # it looks worst.
    #
    # Over-fetch, collapse, then take the page. The extra rows are the cost of
    # not knowing how many duplicates are in a window before reading it.
    seen_key, out = set(), []
    if lim:
        want = off + lim
        for j in query.limit(max(want * 4, 120)).all():
            k = ((j.title or "").strip().lower(), (j.company or "").strip().lower())
            if k in seen_key:
                continue
            seen_key.add(k)
            out.append(j)
            if len(out) >= want:
                break
        rows = out[off:off + lim]
    else:
        rows = []
    out = [_job_json(j) for j in rows]
    _mark_tracked(db, user, out)
    return {"jobs": out, "total": total,
            "offset": off, "limit": lim, "has_more": off + lim < total,
            "free_limited": bool(free and (FREE_JOB_CAP > 0 or FREE_JOB_DELAY_DAYS > 0)),
            "free_delay_days": FREE_JOB_DELAY_DAYS if free else 0,
            "free_cap": FREE_JOB_CAP if free else 0}


def _mark_tracked(db, user, items):
    """Tag each result with the user's saved/applied state, so the list can
    show it without a second request per card."""
    ids = [d["id"] for d in items]
    if not ids:
        return
    seen = dict(db.query(JobTrack.job_id, JobTrack.status)
                .filter(JobTrack.user_id == user.id,
                        JobTrack.job_id.in_(ids)).all())
    for d in items:
        d["tracked"] = seen.get(d["id"], "")


@app.get("/api/jobs/categories")
def jobs_categories(country: str = "", user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    """Categories we actually hold open jobs for, largest first."""
    query = db.query(Job.category, func.count(Job.id)).filter(
        Job.is_open == True)                                # noqa: E712
    if country:
        query = query.filter(func.lower(Job.country) == country.strip().lower())
    rows = query.group_by(Job.category).all()
    # Uncategorised rows used to be dropped here, which is how the headline
    # could say 10,713 open roles while the category filter accounted for
    # 4,858 of them: over five thousand postings were on the board and
    # reachable from nowhere. Anything crawled before the family rules
    # improved is folded into Other rather than hidden, so the numbers
    # reconcile and every job has a way in. The backfill moves them into
    # their real category; this makes sure they are never invisible while
    # they wait.
    stray = sum(n for c, n in rows
                if not c or (ALLOWED_FAMILIES and c not in ALLOWED_FAMILIES))
    rows = [(c, n) for c, n in rows
            if c and (not ALLOWED_FAMILIES or c in ALLOWED_FAMILIES)]
    if stray:
        merged = dict(rows)
        merged["other"] = merged.get("other", 0) + stray
        rows = list(merged.items())
    # Only families the board is scoped to. Rows crawled before a scope change
    # keep their old category, so without this the dropdown offers Sales or
    # Manufacturing and returns a handful of stale postings — a filter that
    # looks broken because it is showing the truth about dead data.
    return {"categories": [
        {"id": c, "label": CATEGORY_LABELS.get(c, c.title()), "count": n}
        for c, n in sorted(rows, key=lambda x: -x[1])]}


@app.get("/api/jobs/suggest")
def jobs_suggest(q: str = "", country: str = "", limit: int = 10,
                 user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Type-ahead for the search box: real job titles we actually hold.

    Suggesting titles that return nothing is worse than no suggestions, so
    these come from live rows with their result counts attached."""
    term = (q or "").strip().lower()
    if len(term) < 2:
        return {"suggestions": []}
    query = db.query(Job.title, func.count(Job.id)).filter(
        Job.is_open == True, func.lower(Job.title).like(f"%{term}%"))  # noqa: E712
    if country:
        query = query.filter(func.lower(Job.country) == country.strip().lower())
    rows = query.group_by(Job.title).order_by(func.count(Job.id).desc()) \
                .limit(min(max(limit, 1), 25)).all()
    # Titles that start with what was typed feel more responsive than ones
    # that merely contain it, so lift those to the top.
    out = [{"title": t, "count": n} for t, n in rows if t]
    out.sort(key=lambda d: (0 if d["title"].lower().startswith(term) else 1, -d["count"]))
    return {"suggestions": out}


@app.get("/api/jobs/filters")
def jobs_filters(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Countries we actually hold jobs for, so the filter never offers a dead
    option. Also the freshness stamp the page shows."""
    rows = db.query(Job.country, func.count(Job.id)).filter(
        Job.is_open == True, Job.country != "").group_by(Job.country).all()  # noqa: E712
    newest = db.query(func.max(Job.last_seen)).scalar()

    # The headline count has to be the number of jobs THIS user can open. A
    # free account sees a delayed, capped slice, so reporting the whole board
    # promised thousands and then listed fifty — the count and the list have to
    # come from the same rules or the page is simply lying.
    free = plan_of(user) == "free" and not getattr(user, "is_admin", False)
    open_q = db.query(func.count(Job.id)).filter(Job.is_open == True)  # noqa: E712
    if free and FREE_JOB_DELAY_DAYS > 0:
        cutoff = now() - dt.timedelta(days=FREE_JOB_DELAY_DAYS)
        open_q = open_q.filter(
            case((Job.posted_at.isnot(None), Job.posted_at),
                 else_=Job.first_seen) <= cutoff)
    open_n = open_q.scalar() or 0
    if free and FREE_JOB_CAP > 0:
        open_n = min(open_n, FREE_JOB_CAP)
    return {
        # Same reason as the categories above: a country dropped from
        # JOB_COUNTRIES must stop being offered, even while its old rows sit
        # in the table waiting for the next prune.
        "countries": [{"country": c, "count": n}
                      for c, n in sorted(rows, key=lambda x: -x[1])
                      if _job_in_scope({"country": c, "category": ""})],
        "open": open_n,
        "free_limited": bool(free and (FREE_JOB_CAP > 0 or FREE_JOB_DELAY_DAYS > 0)),
        "closed": db.query(func.count(Job.id)).filter(Job.is_open == False).scalar(),  # noqa: E712
        "updated": newest.isoformat() if newest else None,
        "retention_days": JOB_RETENTION_DAYS,
        "refresh_hours": JOB_REFRESH_HOURS,
        "job_types": _facet(db, Job.job_type, JOB_TYPE_LABELS),
        "engagements": _facet(db, Job.engagement, ENGAGEMENT_LABELS),
        "visas": _facet(db, Job.visa, VISA_LABELS),
        "posted_windows": POSTED_WINDOWS,
        "new_today": db.query(func.count(Job.id)).filter(
            Job.first_seen >= now() - dt.timedelta(days=1)).scalar(),
    }


JOB_TYPE_LABELS = {"fulltime": "Full-time", "contract": "Contract",
                   "parttime": "Part-time", "internship": "Internship"}
ENGAGEMENT_LABELS = {"w2": "W2", "c2c": "C2C / corp-to-corp",
                     "w2_c2c": "W2 or C2C", "1099": "1099"}
VISA_LABELS = {"sponsors": "Sponsors a visa (H1B / OPT / CPT)",
               "no_sponsorship": "No sponsorship — citizens / green card",
               "clearance": "Security clearance required"}


def _facet(db, col, labels):
    """Counts for one filter, so we only ever offer options that return rows."""
    rows = db.query(col, func.count(Job.id)).filter(
        Job.is_open == True, col != "", col.isnot(None)).group_by(col).all()  # noqa: E712
    return [{"id": v, "label": labels.get(v, str(v).title()), "count": n}
            for v, n in sorted(rows, key=lambda x: -x[1])]


class JobMatchIn(BaseModel):
    resume: dict = {}
    resume_text: str = Field(default="", max_length=40000)
    country: str = Field(default="", max_length=80)
    location: str = Field(default="", max_length=120)
    q: str = Field(default="", max_length=120)
    remote: bool = False
    limit: int = 20
    offset: int = 0
    min_score: int = 0
    category: str = Field(default="", max_length=30)
    job_type: str = Field(default="", max_length=20)
    engagement: str = Field(default="", max_length=10)
    visa: str = Field(default="", max_length=20)
    posted: str = Field(default="", max_length=4)


# ---- career board: the roles we actually carry, taught end to end --------
# The role list is JSEARCH_QUERIES rather than a hand-written syllabus index.
# That keeps the teaching honest: every role offered here is one the crawl is
# really pulling postings for, so "learn this" is always followed by "and here
# are the jobs". A curriculum nobody is hiring for is a waste of the learner's
# month.

CAREER_GROUPS = [
    # Order matters: first group whose keyword appears wins. Cybersecurity and
    # AI & data come before Cloud because "cloud security architect" and "big
    # data architect" are security and data roles that merely say cloud and
    # architect. Filing them under infrastructure sends a learner to the wrong
    # syllabus entirely.
    ("Cybersecurity", ("cybersecurity", "cyber security", "penetration", "soc ",
                       "security operations", "identity", "information security",
                       "security engineer", "security architect", "compliance",
                       "security analyst")),
    ("AI & data", ("machine learning", "data scientist", "data engineer",
                   "big data", "business intelligence", "nlp", "prompt engineer",
                   "database administrator")),
    ("Cloud & infrastructure", ("cloud", "infrastructure", "architect", "network",
                                "systems administrator", "virtualization",
                                "data center", "storage", "migration")),
    ("DevOps & reliability", ("devops", "site reliability", "release", "build",
                              "platform", "kubernetes", "ci cd")),
    ("Software engineering", ("full stack", "backend", "frontend", "mobile",
                              "api", "embedded", "game", "cms", "webmaster",
                              "developer", "software engineer")),
    ("Product & delivery", ("product manager", "scrum", "agile", "ui ux",
                            "technical writer", "systems analyst",
                            "business analyst", "qa ", "project manager")),
    ("IT support & operations", ("help desk", "support", "desktop", "incident")),
]


def _career_group(title):
    t = " " + title.lower() + " "
    for name, keys in CAREER_GROUPS:
        if any(k.strip() in t for k in keys):
            return name
    return "Other technical roles"


@app.get("/api/career/roles")
def career_roles(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Every role we teach, grouped, with how many live postings back it.

    The count is the argument for studying the thing. A role with 400 open
    jobs and one with two are not the same investment, and the learner should
    see that before spending a month.
    """
    out = {}
    # The crawl queries are not roles. "Corp To Corp Devops Engineer" and
    # "Contract Qa Engineer" exist to aim the paid API at the staffing
    # market; offering them to a learner as things to become is nonsense —
    # the role is DevOps Engineer, and the engagement is a filter on the job
    # board, not a career.
    _sourcing = re.compile(r"^(c2c|corp to corp|contract|w2)\b", re.I)
    for title in JSEARCH_QUERIES:
        if _sourcing.search(title):
            continue
        n = db.query(func.count(Job.id)).filter(
            Job.is_open == True,                                # noqa: E712
            func.lower(Job.title).like(f"%{title.lower()}%")).scalar() or 0
        out.setdefault(_career_group(title), []).append(
            {"role": title, "label": title.title(), "jobs": n})
    groups = [{"group": g, "roles": sorted(rs, key=lambda r: -r["jobs"])}
              for g, rs in out.items()]
    groups.sort(key=lambda g: -sum(r["jobs"] for r in g["roles"]))
    return {"groups": groups, "total_roles": len(JSEARCH_QUERIES)}


@app.get("/api/career/skills")
def career_skills(role: str = "", user: User = Depends(current_user),
                  db: Session = Depends(get_db)):
    """The skills employers ask for in one role, straight from the postings.

    No model call: this counts what the live ads for that title actually
    name, which is why it can sit in front of the paywall and be pressed
    freely. The lesson behind each skill is what costs something.
    """
    role = (role or "").strip()
    if len(role) < 2:
        return {"role": role, "skills": [], "open_jobs": 0}
    demand, n = {}, 0
    for j in db.query(Job).filter(
            Job.is_open == True,                                # noqa: E712
            func.lower(Job.title).like(f"%{role.lower()}%")).limit(400).all():
        n += 1
        for sk in _job_skills(j):
            demand[sk] = demand.get(sk, 0) + 1
    top = sorted(demand.items(), key=lambda x: -x[1])[:18]
    return {"role": role, "open_jobs": n,
            "skills": [{"skill": k, "jobs": v} for k, v in top]}


class BoardIn(BaseModel):
    topic: str = Field(min_length=2, max_length=200)
    level: str = Field(default="Intermediate", max_length=20)


def _board_prompt(topic: str, level: str) -> str:
    return (
        f"You are Axle, teaching at a board. Topic: {topic}. Learner level: "
        f"{level}.\n\n"
        "This board teaches anything anyone asks it, to whatever depth "
        "they need — medicine, law, pure mathematics, history, "
        "engineering, linguistics, finance, music, a trade, a language, "
        "and computing among them. Do not steer the lesson towards "
        "programming, and do not assume the learner is a programmer "
        "unless the topic itself is.\n\n"
        'NO GREETING, NO PREAMBLE. The first line is the first real thing you have to say. Never open with "Welcome", "Dear students", "Let us look at this together", "Great question" or any other pleasantry, and never spend a line restating the question back — the learner has it in front of them and the board only shows a few lines at a time, so a line that carries nothing is a line of the lesson thrown away. Begin with the substance and keep going.\n\nANSWER THE QUESTION THAT WAS ASKED. Read it closely enough to notice what it is really asking, then answer that. If it is a problem to solve, solve it and reach the actual answer — do not restate the setup, describe an approach, and stop. Work each step so the reader can follow the arithmetic or the argument, and finish. If the question has no clean answer, or the answer is that no solution exists, say so and show what rules the others out. Every claimed answer gets substituted back into the original problem and checked before you state it.\n\nINDIA FIRST, WHEN AN EXAMPLE IS NEEDED. Set examples here: rupees rather than dollars, Indian cities, Indian firms, the exams and boards people here actually sit, Indian regulations and Indian case law. Use a foreign example only when the subject genuinely is foreign — a US statute in a lesson on US law, a landmark experiment done where it was done. Never reach for another country\'s setting when a local one would serve.\n\n'
        "Teach it as a sequence of steps that build on each other, the way a "
        "good teacher works through a board: one idea per step, in order, "
        "nothing assumed that has not already been shown.\n\n"
        # A learner who is shown a Python snippet for a switching topic knows
        # immediately that nobody has done this job. Teach each skill in the
        # place the work actually happens, or the whole lesson reads as fake.
        "ONE SUBJECT, ITS OWN WAY OF THINKING. Work out what field this "
        "belongs to before you write anything, then reason the way that "
        "field reasons and use only its own apparatus. Mathematics argues "
        "from definition and proof; physics from principle, symmetry and "
        "order of magnitude; chemistry from mechanism and the balanced "
        "equation; biology from structure, function and selection; "
        "medicine from presentation, mechanism and differential; law from "
        "authority, facts and the test the court applies; history from "
        "sources and what they can and cannot support; economics from "
        "incentives and constraint; engineering from requirement, "
        "tolerance and failure mode; computing from state, cost and what "
        "breaks under load.\n"
        "Do not borrow an example from another field because it is "
        "familiar. A chemistry lesson does not need a courtroom and a "
        "history lesson does not need a circuit. If an analogy is worth "
        "using, say plainly that it is an analogy and say where it stops "
        "being true — an analogy left unqualified is the thing people "
        "remember instead of the mechanism.\n"
        "Use the notation, units and vocabulary that field actually "
        "writes with, and define each of them once, the first time.\n\n"
        "A SKILL IS PRACTISED, NOT KNOWN. When the topic is something done rather than understood \u2014 presenting, interviewing, teaching, negotiating, running a meeting, writing to be read, handling a difficult conversation \u2014 a list of tips teaches nobody anything. Nobody ever spoke better for having read that eye contact matters.\n"
        "Teach those the way a coach does. Give the actual words: the opening line, the sentence that recovers a lost room, the question that reopens a stalled negotiation \u2014 written out in full, as somebody would really say them. Show the weak version and the strong version of the same moment and say precisely what changed between them. Name what goes wrong and what it feels like from the inside, because that is how somebody recognises it happening to them. Then give one thing to rehearse before the next real occasion, specific enough that they know whether they did it.\n"
        "GET TO THE THEORY. Say why it is true, not only that it is. The "
        "derivation, the mechanism, the reasoning behind the rule — and "
        "the conditions under which it stops holding, because knowing "
        "where a result fails is most of what separates somebody who has "
        "learned it from somebody who has memorised it.\n\n"
        "Leave \"where\" empty when the work has no place. Pure "
        "mathematics happens on paper and nowhere else, and a lesson on "
        "modular arithmetic labelled \"Embedded systems lab bench, "
        "Electronic City, Bangalore\" has invented a setting to satisfy a "
        "rule. An invented place is a fabricated detail like any other, and "
        "the reader cannot tell it from the real ones you give elsewhere.\n"
        "TEACH IT WHERE THE WORK HAPPENS. Every subject lives somewhere "
        "real, and it is only sometimes a screen. Before writing a step, "
        "decide where a person who actually does this would be standing "
        "and what would be in front of them, and put the learner THERE.\n"
        "Outside computing that is a place, not a terminal: a ward round "
        "reading a patient's ECG, a bench with a titration half finished, "
        "a courtroom and the section being argued, a balance sheet on an "
        "auditor's desk, an archive with the actual document, a workshop "
        "with the part in a vice, a score on a music stand, a field site "
        "with the core sample. Name the setting, quote the real numbers, "
        "cite the real case or paper or reaction.\n"
        "In computing it is a screen, and most of them are not Python: "
        "a Cisco IOS console session for switching and "
        "routing, the AWS or Azure portal and its CLI for cloud, kubectl and "
        "YAML manifests for Kubernetes, a Wireshark capture for packet "
        "analysis, a Splunk or Sentinel search for SOC work, a Jenkins or "
        "GitHub Actions pipeline file for CI/CD, Terraform HCL for "
        "infrastructure, SQL in a query tool for data, PowerShell for Windows "
        "administration, a ticket in ServiceNow or Jira for support work. "
        "Python only when the job really is scripting or data.\n\n"
        "Show the environment as it looks in front of a working engineer — "
        "the real prompt, the real command, the real output that comes back, "
        "including the parts that are noisy or unhelpful. Then explain what "
        "each part of that output means and what the engineer does next. "
        "Invented hostnames, IPs and ticket numbers are fine; invented "
        "commands and invented output formats are not.\n\n"
        "Ground it in the job: name the situation the skill is used in — the "
        "outage, the ticket, the migration, the audit finding — so the "
        "learner sees when this comes up at work, not just what it is.\n\n"
        '{"title":"<topic in 2-6 words>",'
        '"steps":[{"t":"<TEACH this step: 120-220 words, written as SEVERAL SHORT LINES separated by newlines, one idea per line. Not a paragraph: a paragraph of six claims run together gives the eye nowhere to rest and no way to find one point again. Each line stands on its own and is a full sentence or two. Say what it is, how '
        'it works underneath, why it is done this way, and what breaks when it '
        'is done wrong. Never one line, never a definition on its own.>",'
        '"where":"<where this step happens — a screen, a bench, a ward, a '
        'courtroom, e.g. \'Console on a Catalyst 9200\' or \'Titration at '
        'the bench\' — or empty if the step has no single place>",'
        '"code":"<what is literally on that screen or page: commands and '
        'their output, the worked calculation, the statute text, the '
        'balanced equation — or empty. Never prose.>",'
        '"lang":"cisco|bash|powershell|python|javascript|sql|yaml|hcl|json|'
        'kql|splunk|text|",'
        '}],'
        '"takeaway":"<one sentence to remember>",'
        '"deeper":["<narrower sub-topic>","<another>"]}\n\n'
        + _depth.instruction(topic) + "\n"
        "ANSWER THE SENTENCE, NOT THE SUBJECT. \"How do I solve a squared "
        "plus b squared\" is a question about a form: say that it does not "
        "factorise over the reals the way a squared minus b squared does, "
        "and what to do instead. It is not a request for a lesson on "
        "modular arithmetic, and answering the wider subject at length is "
        "still not answering what was asked.\n"
        "Before writing anything, decide what the single thing being asked "
        "is, and write the answer to that. Everything else you know about "
        "the area belongs in \"deeper\", which is what that field is for.\n"
        "Each step 120 to 220 words — the same length the "
        "schema asks for above. This said 60 to 110 while the schema "
        "said 120 to 220, and a lesson written to satisfy both came out "
        "as an outline of the topic instead of the topic itself. Long "
        "enough to actually teach the step: what it is, the mechanism "
        "underneath, why it is done this way, and what breaks when it "
        "is not.\n"
        "ONE IDEA PER LINE. Break every step into separate lines with a newline between them \u2014 one claim, one mechanism, one consequence, one number each. Six sentences run together as a block is the same content nobody can scan, and a reader looking for the one line that mattered cannot find it again.\n"
        "Sharp lines. Say the thing and stop: no throat-clearing, no \"it is important to note that\", no sentence whose only job is to introduce the next one.\n"
        "FINISH EVERY STEP. A step that introduces an idea and moves on "
        "before explaining it has taught nothing — the reader is left "
        "holding a heading. If a step needs the whole 220 words, use "
        "them. Never write 'beyond the scope of this lesson', 'as we "
        "will see later', or 'there are several factors' without "
        "naming them: say the thing.\n"
        "A step that reads like a glossary entry has failed — the "
        "learner found the definition before coming here, and what they "
        "lack is why it works that way and what breaks without it. Use "
        "a concrete number, name or scenario in most steps rather than "
        "speaking generally.\n"
        "SHOW IT RATHER THAN DESCRIBE IT. Nobody takes in two thousand words of prose about a thing they cannot see. Every step should carry something to look at where one exists — the real screen or worked calculation in \"code\", or a scene. Cut a sentence before you cut the picture: if a paragraph is explaining what something looks like or how it is arranged, the scene is doing that job and the paragraph should say what it MEANS instead.\n\n"
        "At least half the steps carry a real screen, bench or document "
        "in \"code\" with the matching \"where\" — the actual commands and "
        "the output they return, the worked calculation line by line, the "
        "text of the clause. Never prose in that field.\n\n"
        "THE PICTURE MUST BE OF WHAT THE STEP SAYS. A drawing, sketch "
        "or scene belongs to one step and illustrates THAT step, not "
        "the topic in general. Every label in it must be a term the "
        "step's own sentences use, and every part the step names should "
        "appear in it. Then refer to it in the text — 'the shaded "
        "region', 'the second stage' — so the reader knows which "
        "part to look at while reading which sentence.\n"
        "A picture whose labels are not the words in the paragraph "
        "beside it is a stock illustration of the subject, and the "
        "reader can tell. If a step's content cannot be drawn, leave "
        "that step without a picture rather than attaching a general "
        "one.\n"
        "EVERY LESSON GETS A DRAWING. Put a sketch on the step where seeing "
        "it does the most work, and on any other step where a different one "
        "genuinely earns its place. A lesson that arrives as nothing but "
        "paragraphs has failed a reader who needed to see the shape of the "
        "thing.\n\n"
        "EXPLAIN IN WORDS RATHER THAN IN BOXES. Do not describe a "
        "diagram, do not draw one in characters, and never emit SVG, "
        "HTML or markdown. Where something has parts or an order, say "
        "what each part does, what passes between them, and what breaks "
        "when one is missing — that is the explanation a drawing was only "
        "ever standing in for. Walk the reader through it the way you "
        "would out loud, naming the pieces as you go.\n\n"
        "GIVE THE LESSON A 3D SCENE, on the one step where seeing the thing does the most work — the step where somebody would otherwise ask what it actually looks like. One per lesson: a second is a picture nobody looks at twice. Leave it out only when the topic has genuinely nothing to show, and be honest about that rather than forcing one.\n"
        + _draw.PROMPT + "\n\n" + _sketch.PROMPT + "\n\n" + _scene.PROMPT
    )


_BOARD_LANGS = {
    "cisco", "ios", "junos", "bash", "shell", "powershell", "cmd",
    "python", "javascript", "typescript", "go", "java", "sql",
    "yaml", "hcl", "terraform", "json", "xml", "ini", "dockerfile",
    "kubectl", "kql", "splunk", "spl", "regex", "text", "log",
}


async def _offer_scene(client, lesson, topic):
    """Attach a 3D scene when a measured one exists and the lesson has none.

    A scene only ever appeared if the model asked for one, so whether a
    lesson on caffeine showed the molecule depended on how the prompt read
    that day rather than on whether the structure exists. If a real one is
    available the lesson should have it; the model leaving it out is an
    omission, not a decision about the subject.

    Sources are tried most specific first, and the order is the whole
    correctness of this function. The three tables in this repo only match
    what they actually contain. PubChem checks the name against its canonical
    title. The Protein Data Bank comes last and only for names on the curated
    list, because its full-text search returns a chitinase for "caffeine" —
    a real structure that happens to contain it — and a protein called SPA-2
    for "git". Correct search results, entirely wrong pictures.

    Nothing is invented: a topic with nothing measured behind it still gets
    no scene.
    """
    if not isinstance(lesson, dict):
        return False
    steps = [st for st in (lesson.get("steps") or []) if isinstance(st, dict)]
    if not steps or any(st.get("scene") for st in steps):
        return False

    name = _depth.subject_of(topic)
    if not name:
        return False
    scene_out = None

    # 1. Tables: no request, no waiting, no failure mode.
    got = _lattice.clean(name)
    if got:
        scene_out = dict(got, kind="lattice", caption=name.title(),
                         a=2.0, a_angstrom=got["a"], repeat=2)
    if scene_out is None:
        got = _layers.clean(name)
        if got:
            scene_out = dict(got, kind="layers", caption=name.title())
    if scene_out is None:
        got = _orbits.clean(name)
        if got:
            scene_out = dict(got, kind="orbit", caption=name.title())

    # 2. A compound, verified against PubChem's own canonical name.
    if scene_out is None:
        try:
            got = await _molecule.find(client, name)
        except Exception:
            got = {}
        if got and 2 <= len(got.get("atoms") or []) <= _scene.MAX_ATOMS:
            formula = got.get("formula") or ""
            scene_out = {
                "kind": "molecule",
                "caption": (name.title() + (" - " + formula if formula else "")),
                "atoms": [{"el": a["el"], "x": a["x"], "y": a["y"],
                           "z": a["z"]} for a in got["atoms"]],
                "bonds": [list(b) for b in got["bonds"]],
            }

    # 3. A macromolecule, and only one we have chosen deliberately.
    if scene_out is None and _protein.canonical(name):
        try:
            got = await _protein.find(client, name)
        except Exception:
            got = {}
        if got:
            scene_out = dict(got, kind="protein",
                             caption=(got.get("title") or name.title())[:110])

    if scene_out is None:
        return False
    cleaned = _scene.clean(scene_out)
    if not cleaned:
        return False
    # Onto the step with the most to say, which is where a picture is most
    # likely to have belonged.
    host = max(steps, key=lambda st: len(st.get("t") or ""))
    host["scene"] = cleaned
    print(f"Offered a {cleaned['kind']} scene for {name!r}, which the lesson "
          f"did not ask for")
    return True


async def _real_molecules(client, lesson, topic):
    """Swap guessed atomic coordinates for measured ones, where they exist.

    The name to look up is the scene's own caption first, then the lesson
    topic — a caption like "Caffeine molecule" resolves, and if it does not,
    a lesson called "caffeine" still might.

    Never raises and never removes a scene. A molecule PubChem does not have
    keeps the one the model drew, because a diagram is still better than a
    gap; only the geometry is upgraded, never downgraded.
    """
    if not isinstance(lesson, dict):
        return 0
    swapped = 0
    for st in (lesson.get("steps") or []):
        if not isinstance(st, dict):
            continue
        sc = st.get("scene")
        if not isinstance(sc, dict):
            continue

        # A layer stack: the thicknesses are measured. A gate oxide and a
        # wafer differ by a factor of a quarter of a million, and a stack
        # drawn without that says a MOSFET is a sandwich of comparable
        # slices — the opposite of what makes one work.
        if sc.get("kind") == "layers":
            for name in (sc.get("caption"), topic):
                real = _layers.clean(name)
                if not real:
                    continue
                sc.update(real)
                swapped += 1
                break
            continue

        # An orbit: the distances and periods are measured. Spacing bodies
        # by index made every system evenly spread, and the solar system is
        # the opposite of evenly spread — the four inner planets fit inside
        # 1.6 AU and Neptune is at 30. That emptiness is the most surprising
        # true thing about it, and an even diagram teaches it away.
        if sc.get("kind") == "orbit":
            for name in (sc.get("caption"), topic):
                real = _orbits.clean(name)
                if not real:
                    continue
                sc.update(real)
                swapped += 1
                break
            continue

        # A crystal: the lattice constant and the basis are measured, and
        # they are in a table rather than behind a request, because the
        # structures that get taught are a short list and a table cannot be
        # slow or down.
        if sc.get("kind") == "lattice":
            for name in (sc.get("caption"), topic):
                real = _lattice.clean(name)
                if not real:
                    continue
                sc.update(real)
                # A cell edge in angstrom is 5.6, and the renderer draws in
                # its own units where 5.6 would fill the screen with one
                # cell. Keep the measured value for the label and give the
                # drawing a size it can show.
                sc["a_angstrom"] = real["a"]
                sc["a"] = 2.0
                swapped += 1
                break
            continue

        # A macromolecule: the backbone comes from the Protein Data Bank,
        # measured by crystallography. The model names the structure; it
        # does not place the atoms.
        if sc.get("kind") == "protein":
            for name in (_protein_name(sc.get("caption")), topic):
                if not name:
                    continue
                try:
                    got = await _protein.find(client, name)
                except Exception as e:
                    print(f"Protein lookup failed: {type(e).__name__}: {e}")
                    got = {}
                if not got:
                    continue
                sc.update(got)
                if got.get("pdb") and got["pdb"] not in (sc.get("caption") or ""):
                    sc["caption"] = (f"{sc.get('caption') or got.get('title')}"
                                     f" — PDB {got['pdb']}").strip(" —")
                swapped += 1
                break
            continue

        if sc.get("kind") != "molecule":
            continue
        for name in (_molecule_name(sc.get("caption")), topic):
            if not name:
                continue
            try:
                real = await _molecule.find(client, name)
            except Exception as e:
                print(f"Molecule lookup failed: {type(e).__name__}: {e}")
                real = {}
            if not real or len(real.get("atoms") or []) < 2:
                continue
            # scene.clean caps the payload; anything past it is a protein and
            # belongs to a different renderer.
            if len(real["atoms"]) > _scene.MAX_ATOMS:
                continue
            sc["atoms"] = [{"el": a["el"], "x": a["x"], "y": a["y"],
                            "z": a["z"]} for a in real["atoms"]]
            sc["bonds"] = [list(b) for b in real["bonds"]]
            if real.get("formula"):
                base = sc.get("caption") or real.get("name") or ""
                if real["formula"] not in base:
                    sc["caption"] = (f"{base} — {real['formula']}").strip(" —")
            swapped += 1
            break
    return swapped


# Captions read like "Caffeine molecule (ball and stick)". PubChem wants the
# substance, so the scaffolding words come off.
_MOL_NOISE = _re.compile(
    r"\b(molecule|molecular|structure|model|ball[\s-]and[\s-]stick|"
    r"space[\s-]filling|3d|three[\s-]dimensional|diagram|showing|shown|"
    r"view|rendered|representation|atoms?|bonds?|"
    r"of|the|a|an|in|on|at|with|and|for|its|this|that|is|are|as)\b", _re.I)


def _protein_name(caption):
    """The structure a scene caption names, if it names one.

    The scaffolding comes off first. "Haemoglobin ribbon" is not in the
    curated list of taught structures, so it fell through to full-text
    search and returned a real haemoglobin that is not the one anybody
    teaches; "Haemoglobin" resolves to 1HHO, which is.
    """
    t = _re.sub(r"\(.*?\)", " ", str(caption or ""))
    t = _re.sub(r"\b(3d|structure|model|backbone|ribbon|cartoon|fold|"
               r"of|the|a|an|in|with|and|shown|showing|diagram|"
               r"molecule|protein)\b", " ", t, flags=_re.I)
    t = " ".join(t.replace(",", " ").split()).strip(" -—")
    return t if _protein.wanted(t) else ""


def _molecule_name(caption):
    """The substance a scene caption is about, if it names one."""
    t = _re.sub(r"\(.*?\)", " ", str(caption or ""))
    t = _MOL_NOISE.sub(" ", t)
    t = " ".join(t.replace(",", " ").split()).strip(" -\u2014")
    return t if _molecule.wanted(t) else ""


_REVIEW_MAX = 2200


def _review_prompt(question, lesson):
    """Ask for the errors, not for an opinion of the lesson."""
    body = []
    for i, st in enumerate(lesson.get("steps") or [], 1):
        if isinstance(st, dict):
            body.append(f"[{i}] {st.get('t', '')}")
            if st.get("code"):
                body.append(f"    {st['code'][:400]}")
        else:
            body.append(f"[{i}] {st}")
    if lesson.get("takeaway"):
        body.append(f"[takeaway] {lesson['takeaway']}")
    text = "\n".join(body)[:9000]

    return (
        "You are checking a lesson another tutor wrote, before it is shown to "
        "a student. Your only job is to find what is WRONG in it.\n\n"
        f"THE QUESTION ASKED: {question}\n\n"
        f"THE LESSON:\n{text}\n\n"
        "Look for, in this order of importance:\n"
        "- A statement that is factually false, or a mechanism described "
        "wrongly. Confusing two related things counts: a dipole treated as a "
        "monopole, an enzyme for its substrate, a necessary condition for a "
        "sufficient one.\n"
        "- A formula that is dimensionally wrong. Check the units on both "
        "sides. An angular momentum in kg/s is wrong however tidy it looks.\n"
        "- Arithmetic or algebra that does not follow.\n"
        "- A claim stated with more certainty than it deserves, or a "
        "condition left off a result that needs one.\n"
        "- An answer to a different question from the one asked.\n\n"
        "RULES.\n"
        "- Report only what you are SURE of. A list of debatable phrasings "
        "gets ignored, and the one real error goes with it. If the lesson is "
        "sound, say so and stop.\n"
        "- Do not rewrite it, do not suggest improvements, do not comment on "
        "style, length or what it might also have covered.\n"
        "- Quote the words that are wrong so they can be found.\n\n"
        "Reply with ONLY this JSON:\n"
        '{"sound": true|false, "errors": [{"quote": "<the wrong words, '
        'verbatim, under 20 words>", "wrong": "<what is false about it, one '
        'sentence>", "correct": "<what it should say, one sentence>", '
        '"severity": "critical"|"minor"}]}'
    )


async def _review_lesson(question, lesson):
    """Read a finished lesson back and return the errors found.

    Never raises and never blocks a lesson. If the review fails, times out or
    comes back unparseable, the lesson is shown as it was — an unavailable
    checker must not cost somebody their answer.
    """
    if not ASK_ENABLED or not isinstance(lesson, dict):
        return []
    if not (lesson.get("steps") or []):
        return []
    try:
        raw = await _ai_text(_review_prompt(question, lesson),
                             _REVIEW_MAX, json_mode=True)
        d = _ai_json(raw)
    except Exception as e:
        print(f"Review skipped: {type(e).__name__}: {e}")
        return []
    if not isinstance(d, dict) or d.get("sound") is True:
        return []

    out = []
    for e in (d.get("errors") or [])[:5]:
        if not isinstance(e, dict):
            continue
        wrong = str(e.get("wrong") or "").strip()
        if not wrong:
            continue
        sev = "critical" if str(e.get("severity")) == "critical" else "minor"
        quote = str(e.get("quote") or "").strip()[:120]
        fix = str(e.get("correct") or "").strip()[:300]
        out.append({
            "severity": sev,
            "kind": "review",
            "problem": (f"\u201c{quote}\u201d \u2014 {wrong}" if quote
                        else wrong)[:400],
            "correction": fix,
        })
    return out


def _check_lesson(lesson, extra_lines=()):
    """Every automatic check, over one finished lesson.

    Returns (findings, verdict). The verdict decides whether this is fit to
    cache — which is the decision that actually matters, because caching is
    what turns one wrong answer into everybody's wrong answer.

    Never raises. A checker that can break a lesson is worse than no checker,
    since the lesson is the thing the reader came for and the check is not.
    """
    try:
        found = _verify.run(lesson)
    except Exception as e:
        print(f"Verify skipped: {type(e).__name__}: {e}")
        found = []
    try:
        found = found + _maths_gate(list(extra_lines) + _lesson_prose(lesson))
    except Exception as e:
        print(f"Maths check skipped: {type(e).__name__}: {e}")
    # Units. The constants checker knows CODATA values and the arithmetic
    # checker does sums; neither reads a symbolic formula, which is how an
    # angular momentum in kg/s reached a lesson. This is exponent arithmetic
    # on the seven SI base units — no model, no network, no judgement.
    try:
        text = "\n".join(list(extra_lines) + _lesson_prose(lesson))
        found = found + _dimensions.check(text)
    except Exception as e:
        print(f"Dimension check skipped: {type(e).__name__}: {e}")
    try:
        v = _verify.verdict(found)
    except Exception:
        v = {"cache": True, "confidence": "medium", "state": "checked"}
    return found, v


def _lesson_prose(lesson):
    """Every line of a lesson that could carry a claim, as plain strings."""
    out = []
    if not isinstance(lesson, dict):
        return out
    for st in (lesson.get("steps") or []):
        if isinstance(st, dict):
            out += [str(st.get(k) or "") for k in ("t", "code")]
        else:
            out.append(str(st or ""))
    out.append(str(lesson.get("takeaway") or ""))
    return out


def _note_findings(found):
    """The findings a reader should see, with the correction attached.

    The correction is the useful half. "That is wrong" leaves somebody
    holding a lesson they now distrust and no way to repair it; "that is
    wrong, and here is what it should say" leaves them with the answer.
    """
    # Four checkers can now see the same fault. The reviewer reads the
    # argument, the dimension checker reads the units, the maths gate
    # substitutes the answer and verify.py reads the constants — a formula in
    # the wrong units is exactly the kind of thing two of them catch at once,
    # and telling somebody twice makes both reports look automated.
    #
    # Deduplicated on the words rather than the kind, because the same fault
    # described by two checkers is still one fault, and the deterministic
    # checkers are kept over the model when both found it: they can say what
    # is wrong exactly, where the reviewer can only say it in a sentence.
    ordered = sorted(found, key=lambda f: f.get("kind") == "review")
    out, seen = [], []
    for f in ordered:
        if f.get("severity") not in ("critical", "major"):
            continue
        key = set(_re.findall(r"[a-z0-9]{4,}",
                              str(f.get("problem") or "").lower()))
        if any(key and len(key & prev) >= max(2, len(key) // 2)
               for prev in seen):
            continue
        seen.append(key)
        problem = str(f.get("problem") or "").strip()
        if not problem:
            continue
        line = problem[0].upper() + problem[1:]
        fix = str(f.get("correction") or "").strip()
        if fix and fix.lower() not in line.lower():
            line += " — " + fix
        out.append(line[:400])
    return out[:3]


def _maths_gate(lines):
    """Claimed solutions in these lines that do not satisfy their equations.

    Deliberately quiet. It only speaks when an equation and a claimed answer
    are both present, both parse, and the mismatch is far bigger than
    rounding — a checker that cries wolf gets switched off, and one that
    fires on a lesson the reader can see is fine costs more trust than it
    buys.
    """
    try:
        text = "\n".join(str(x or "") for x in lines)
        if "=" not in text:
            return []
        return _maths.check_solutions(text)
    except Exception as e:                        # never break a lesson
        print(f"Maths check skipped: {type(e).__name__}: {e}")
        return []


def _trim_to_depth(lesson, topic):
    """Cut a lesson back to the number of steps the question asked for.

    The prompt carries that number, and a number in a prompt is a request.
    This is the part that makes it true.

    Trimmed rather than regenerated: steps are written in order and build on
    each other, so the first N are a coherent lesson and the tail is the part
    that answered a wider question than the one asked. Regenerating would pay
    for a second model call to produce something the first one already
    contains.

    A picture on a step that goes is moved to the last step that stays. It
    was drawn for this lesson and it still illustrates it, and losing the
    only diagram to a length rule would be a poor trade.
    """
    if not isinstance(lesson, dict):
        return lesson
    steps = lesson.get("steps") or []
    try:
        _lo, hi, why = _depth.measure(topic)
    except Exception as e:
        print(f"Depth check skipped: {type(e).__name__}: {e}")
        return lesson
    if len(steps) <= hi:
        return lesson

    kept, dropped = steps[:hi], steps[hi:]
    for key in ("draw", "sketch", "scene"):
        if any(isinstance(st, dict) and st.get(key) for st in kept):
            continue
        moved = next((st[key] for st in dropped
                      if isinstance(st, dict) and st.get(key)), None)
        if moved and isinstance(kept[-1], dict):
            kept[-1][key] = moved
    print(f"Board on {str(topic)[:50]!r}: {len(steps)} steps trimmed to "
          f"{hi} ({why})")
    lesson["steps"] = kept
    return lesson


def _clean_board(d, topic):
    """Validate the model's lesson into something safe to render.

    Diagrams arrive as plain labels and index pairs, never as markup: the
    board renders them itself. A model that returns SVG or HTML here would be
    handing us a stored-XSS payload to inject into another user's page.
    """
    def txt(v, n=1200):
        return str(v or "").strip()[:n]

    steps = []
    for raw in (d.get("steps") or [])[:14]:
        if not isinstance(raw, dict):
            continue
        lang = txt(raw.get("lang"), 12).lower()
        steps.append({
            "scene": _scene.clean(raw.get("scene")),
            "sketch": _sketch.clean(raw.get("sketch")),
            "draw": _draw.clean(raw.get("draw")),
            "t": txt(raw.get("t")),
            # Where this step happens — the console, the portal, the query
            # tool. Shown as a caption above the screen so nobody has to guess
            # whether they are looking at a shell or a router.
            "where": txt(raw.get("where"), 70),
            "code": txt(raw.get("code"), 2000),
            # This list used to be python/javascript/sql/bash, so a Cisco IOS
            # session or a Terraform file came back labelled as nothing at
            # all. The label is a caption, not an execution target: anything
            # outside the list is dropped, but the list has to cover the work.
            "lang": lang if lang in _BOARD_LANGS else "",
        })
    steps = [x for x in steps if x["t"] or x["code"]]

    # A picture sent beside "steps" rather than inside one. The reply that
    # prompted this ended with a complete, valid flow scene that nothing ever
    # looked at, so a lesson plainly containing a drawing reported none.
    # Three drawing systems offered in one prompt is a lot to keep straight;
    # putting it in the wrong place is a reasonable mistake to absorb.
    for key, cleaner in (("draw", _draw.clean), ("sketch", _sketch.clean),
                         ("scene", _scene.clean)):
        stray = cleaner(d.get(key))
        if not stray or not steps:
            continue
        if any(st.get(key) for st in steps):
            continue
        # Onto the step that already has the most to say, which is where a
        # picture is most likely to have belonged.
        host = max(steps, key=lambda st: len(st.get("t") or ""))
        host[key] = stray
    # One scene per lesson. Models hand the same model to every step, and a
    # thing you have already turned around teaches nothing the second time —
    # it just costs another WebGL context on someone's phone.
    seen_scene = False
    for st in steps:
        # A scene and a sketch are alternatives. Given both, the flat drawing
        # wins: anything a model wanted to plot or annotate is a thing you
        # read values off, and reading values off a perspective view is what
        # the sketches exist to avoid.
        # One picture per step. The composed drawing wins over both: it can
        # show anything the named kinds can and a great deal they cannot, so
        # a step that sent two is a step that should have sent this one.
        if st.get("draw"):
            st["sketch"] = None
            st["scene"] = None
        elif st.get("sketch") and st.get("scene"):
            st["scene"] = None
        if not st.get("scene"):
            continue
        if seen_scene:
            st["scene"] = None
        else:
            seen_scene = True
    deeper, seen = [], {_norm_q(topic)}
    for x in (d.get("deeper") or [])[:9]:
        t = txt(x, 70)
        k = _norm_q(t)
        if not t or k in seen:
            continue
        seen.add(k)
        deeper.append(t)
    return {"title": txt(d.get("title"), 80) or topic[:80],
            "steps": steps,
            "takeaway": txt(d.get("takeaway"), 300),
            "deeper": deeper[:7]}


@app.post("/api/board/lesson")
async def board_lesson(body: BoardIn, user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    """A step-by-step lesson on any topic, for the smart board.

    Paid: it is a per-request model call on an arbitrary topic, which is
    exactly the kind of cost that cannot be given away.
    """
    require_paid(user, "The smart board")
    if not ASK_ENABLED:
        raise HTTPException(503, "The AI tutor is not switched on")
    topic = body.topic.strip()
    level = body.level.strip() or "Intermediate"
    # Every request leaves a trace. The selftest builds a lesson in five
    # seconds while the browser waits forever, and only a record of what the
    # real endpoint did can say which phase the real request stops at.
    _tr = _Trace(topic, level)

    # Cached like Ask Axle: the same topic at the same level is the same
    # lesson, and the second person to ask should not cost anything.
    scope = _scope_of(db, user)
    qkey = _cl.key(scope, "board", _norm_q(level), _norm_q(topic))[:500]
    _record_learning(db, user, scope, "board", topic, "board", level)
    row = db.query(AskCache).filter(AskCache.qkey == qkey).first()
    _tr.phase("cache lookup")
    if row:
        # Read defensively. This was a bare json.loads outside any try block,
        # so one unreadable or outdated cached row produced a 500 on every
        # later request for that topic — permanently broken for one question
        # and fine for the next, which is a very good impression of "the board
        # is not responding". A row we cannot use is a cache miss, not a
        # failure, so it is dropped and the lesson is built again.
        try:
            cached = json.loads(row.lesson)
            if not isinstance(cached, dict) or not cached.get("steps"):
                raise ValueError("cached lesson has no steps")
            row.hits = (row.hits or 0) + 1
            db.commit()
            _tr.done("served from cache")
            return {"lesson": cached, "cached": True}
        except Exception as ce:
            print(f"Board cache row unusable ({qkey}): "
                  f"{type(ce).__name__}: {ce} — regenerating")
            try:
                db.delete(row)
                db.commit()
            except Exception:
                db.rollback()

    _ai_enforce_limit(db, user)
    try:
        # 8000, not 2600. A lesson is now steps plus a scene plus a sketch,
        # and the old cap cut the JSON off mid-object — which surfaces as a
        # parse failure, not as "too long", so it looked like the board was
        # broken rather than short of room.
        # The picture search runs beside the model call rather than after
        # it. The topic is known before either starts, the search is the far
        # quicker of the two, and it finishes well inside the model's shadow
        # — so a real photograph costs no waiting at all.
        async with httpx.AsyncClient(follow_redirects=True) as _pic_client:
            # Send the computation to something that computes. Models are
            # fluent about arithmetic and poor at it, which is the worst
            # combination — a derivation that reads correctly and is wrong in
            # the third line is harder to catch than one that reads badly.
            # Wolfram returns the result from a computer algebra system and
            # the model is left explaining what it means.
            computed = await _wolfram.result(_pic_client, topic)
            text, photo = await asyncio.gather(
                _ai_text(_board_prompt(topic, level)
                         + _wolfram.note(topic, computed),
                         _depth.tokens(topic),
                        json_mode=True),
                _images.find(_pic_client, topic),
            )
            _tr.phase("model+picture")
            lesson = _trim_to_depth(_clean_board(_ai_json(text), topic), topic)
            if photo:
                lesson["photo"] = photo
            # Inside the same client, because the molecule can only be looked
            # up once the lesson says which one it wants.
            swapped = await _real_molecules(_pic_client, lesson, topic)
            try:
                if await _offer_scene(_pic_client, lesson, topic):
                    swapped += 1
            except Exception as e:
                print(f"Scene offer skipped: {type(e).__name__}: {e}")
            if swapped:
                print(f"Molecules on {topic!r}: {swapped} given real "
                      f"coordinates from PubChem")
        _tr.phase("parse")
    except Exception as e:
        print(f"Smart board failed ({AI_PROVIDER}): {type(e).__name__}: {e}")
        _tr.done(f"failed: {type(e).__name__}: {str(e)[:120]}")
        raise HTTPException(503, _ai_error_message(e))
    if not lesson["steps"]:
        _tr.done("came back empty")
        raise HTTPException(502, "That came back empty — try naming the topic "
                                 "more specifically.")

    # Everything the machine can settle without asking anybody: the physical
    # constants, the arithmetic, the units, and any answer that can be
    # substituted back into its own equation.
    found, verdict = _check_lesson(lesson)
    # The deterministic checks read the numbers. This reads the argument —
    # the dipole treated as a monopole, the formula in the wrong units — which
    # nothing else here can see. One extra call per new topic, cached with the
    # lesson, so only the first person to ask pays for it.
    review = await _review_lesson(topic, lesson)
    if review:
        found = review + found
        if any(r["severity"] == "critical" for r in review):
            verdict = {"cache": False, "confidence": "low", "state": "flagged"}
        elif verdict["confidence"] == "high":
            verdict = dict(verdict, confidence="medium", state="checked")
    _tr.phase("checks+review")
    if found:
        print(f"Checks on {topic!r}: {verdict['state']} "
              f"({len(found)} finding(s)) — {found[0]['problem'][:120]}")
        lesson["findings"] = _note_findings(found)
        lesson["confidence"] = verdict["confidence"]

    _ai_bump(db, user)
    if not verdict["cache"]:
        _tr.done("built, not cached (failed a check)")
        # Shown, but never stored. Caching a lesson with a wrong constant or
        # arithmetic that does not add up serves that error to everybody who
        # asks the same question from then on, and it is free to do so, which
        # is what makes it worse than showing it once.
        print(f"Not caching {topic!r}: it failed a check that matters.")
        return {"lesson": lesson, "cached": False, "checked": verdict["state"]}

    db.add(AskCache(qkey=qkey, subject="board", level=level,
                    question=topic[:2000], lesson=json.dumps(lesson), hits=0))
    try:
        db.commit()
    except IntegrityError:
        # Two people asked the same thing in the same second. The lesson in
        # hand is perfectly good; only the bookkeeping raced. Unguarded, this
        # was the other way the board could return a 500 while holding a
        # complete answer.
        db.rollback()
    _tr.done("built and cached")
    return {"lesson": lesson, "cached": False}


# ==========================================================================
# The SQL smart board
# ==========================================================================
# The general smart board explains any topic and costs a model call to do it.
# This one is different in kind: SQL is the one subject on the site where the
# machine can check the work itself, because a query either returns the right
# rows or it does not. So the whole loop — run, mark, say what went wrong,
# choose what comes next — is arithmetic, and arithmetic is free.
#
# That is what makes it free to use. Running queries has no per-student cost,
# so there is no reason to put it behind the paywall, and every reason not to:
# it is the best demonstration of the product we have.
import sqlboard as _sqlb                                            # noqa: E402
import sqlcourse as _sqlc                                           # noqa: E402


class SqlRunIn(BaseModel):
    sql: str = Field(default="", max_length=4000)
    exercise: str = Field(default="", max_length=20)


# A query is capped at a few milliseconds by the engine's own step budget, so
# this is not protecting the CPU — it is stopping a script from filling the
# logs and the trial counters at machine speed.
_SQL_HITS: dict = {}
_SQL_PER_MIN = 90


def _sql_throttle(user):
    import time as _t
    now_s = _t.monotonic()
    seen = [t for t in _SQL_HITS.get(user.id, []) if now_s - t < 60]
    if len(seen) >= _SQL_PER_MIN:
        raise HTTPException(429, "That is a lot of queries in one minute. "
                                 "Give it a moment.")
    seen.append(now_s)
    _SQL_HITS[user.id] = seen
    if len(_SQL_HITS) > 4000:                      # crude, bounded, adequate
        for k in list(_SQL_HITS)[:2000]:
            _SQL_HITS.pop(k, None)


def _sql_history(db, user):
    """This student's attempts, keyed by exercise id.

    Stored in the existing progress table rather than a new one: an attempt at
    a SQL exercise is the same fact as an attempt at any other lab, and a
    second table would mean a second migration and two places to delete from
    when somebody asks for their data to be erased.
    """
    rows = db.query(Progress).filter(
        Progress.user_id == user.id,
        Progress.lesson_slug.like("sqlboard:%")).all()
    return {r.lesson_slug.split(":", 1)[1]:
            {"tries": r.attempts or 0, "solved": bool(r.completed),
             "code": r.code or ""}
            for r in rows}


@app.get("/api/sql/board")
def sql_board(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Everything the board needs to open: the schema, where you are, what next."""
    hist = _sql_history(db, user)
    nxt = _sqlc.next_up(hist)
    done = sum(1 for v in hist.values() if v["solved"])
    return {
        "schema": _sqlb.schema(),
        "skills": _sqlc.progress(hist),
        "exercises": [_sqlc.public(x) for x in _sqlc.EXERCISES],
        "history": {k: {"tries": v["tries"], "solved": v["solved"]}
                    for k, v in hist.items()},
        "next": _sqlc.public(nxt) if nxt else None,
        "done": done, "total": len(_sqlc.EXERCISES),
        "explain_left": (None if plan_of(user) != "free"
                         else max(0, FREE_TRIAL["sql_explain"]
                                  - _trial_used(db, user, "sql_explain"))),
    }


@app.post("/api/sql/run")
def sql_run(body: SqlRunIn, user: User = Depends(current_user)):
    """Run a query and hand back the rows, plus what the query actually did.

    Free — it costs nothing to serve. The walkthrough rides along with every
    run rather than waiting to be asked for: the order SQL executes in is the
    thing that makes the rest of it make sense, and it is worked out from the
    text, so there is no reason to make anyone click for it.
    """
    _sql_throttle(user)
    r = _sqlb.run(body.sql)
    r["walk"] = _sqlb.walkthrough(body.sql, r)
    return r


@app.post("/api/sql/plan")
def sql_plan(body: SqlRunIn, user: User = Depends(current_user)):
    """SQLite's own plan for the query, so an index stops being a metaphor."""
    _sql_throttle(user)
    return _sqlb.plan(body.sql)


@app.get("/api/sql/join/{exercise}")
def sql_join(exercise: str, user: User = Depends(current_user)):
    """The row-by-row pairing behind a JOIN exercise, for the picture."""
    ex = _sqlc.BY_ID.get(exercise)
    if not ex or not ex.get("visual"):
        raise HTTPException(404, "That exercise has no join diagram")
    return _sqlb.join_trace(**ex["visual"])


@app.post("/api/sql/check")
def sql_check(body: SqlRunIn, user: User = Depends(current_user),
              db: Session = Depends(get_db)):
    """Mark an attempt by running it, and record that it happened.

    Free, like running. The marking is a row comparison, and a row comparison
    is not something anybody should have to pay for.
    """
    _sql_throttle(user)
    ex = _sqlc.BY_ID.get(body.exercise)
    if not ex:
        raise HTTPException(404, "No such exercise")
    verdict = _sqlc.mark(ex, body.sql)

    slug = f"sqlboard:{ex['id']}"
    row = db.query(Progress).filter(Progress.user_id == user.id,
                                    Progress.lesson_slug == slug).first()
    if row is None:
        row = Progress(user_id=user.id, lesson_slug=slug, attempts=0)
        db.add(row)
    row.attempts = (row.attempts or 0) + 1
    row.code = (body.sql or "")[:4000]
    if verdict["correct"] and not row.completed:
        row.completed = True
        row.completed_at = now()
    try:
        db.commit()
    except IntegrityError:
        # Two tabs, same exercise, same second. The mark is still valid; only
        # the bookkeeping raced.
        db.rollback()

    hist = _sql_history(db, user)
    nxt = _sqlc.next_up(hist)
    verdict["next"] = _sqlc.public(nxt) if nxt else None
    verdict["skills"] = _sqlc.progress(hist)
    verdict["done"] = sum(1 for v in hist.values() if v["solved"])
    verdict["walk"] = _sqlb.walkthrough(body.sql, verdict.get("result"))
    return verdict


# The written explanations come back in the same shape as the main smart
# board's lessons, so they go through _clean_board and inherit its validation:
# the model's output is rebuilt field by field, and markup in any of them is
# dropped rather than rendered into another user's page.
#
# No diagram field. The pictures on this board are the student's own rows at
# each stage of their own query, which the server computes for free — a
# model-invented diagram of a pipeline would be a worse illustration of a
# thing we can show for real, and would cost tokens to be worse.
_SQL_SHAPE = (
    'Reply with JSON only: {"title": str, "steps": [{"t": str, "where": str, '
    '"code": str, "lang": "sql"}], "takeaway": str, "deeper": [str]}\n'
    "Rules for every reply:\n"
    "- 3 to 5 steps. Each `t` is 2 to 4 plain sentences, spoken aloud well: "
    "this gets read out by a voice, so no bullet characters and no symbols "
    "that do not survive being said.\n"
    "- `where` is a 2-4 word label for what that step is about.\n"
    "- Use `code` for a runnable SQL fragment where one helps. Leave it empty "
    "otherwise. Never put prose in `code`.\n"
    "- Talk about rows: what goes in, what survives, what comes out. Name the "
    "actual customers, products and totals from the tables above rather than "
    "speaking generally.\n"
    "- Be concrete about where this bites in real work — a report that "
    "double-counts, a dashboard that silently drops customers, a query that "
    "is fine on ten rows and times out on ten million.\n"
    "- Never write SVG, HTML or markdown anywhere.\n"
    '- `deeper` is 3 short follow-up questions the learner might ask next.\n'
)

_SQL_TABLES = (
    "The database on screen: customers(id, name, city, joined); "
    "products(id, title, category, price); "
    "orders(id, customer_id, ordered_at, status); "
    "order_items(id, order_id, product_id, qty). "
    "Three customers have never ordered, and two orders are cancelled."
)


def _sql_explain_prompt(ex, sql, verdict):
    return (
        "You are a SQL tutor sitting beside a learner at a practice board. "
        "They are about 16 and have written a query that is not right yet.\n"
        f"{_SQL_TABLES}\n"
        f"THE QUESTION THEY WERE ASKED: {ex['ask']}\n"
        f"THEIR QUERY:\n{sql}\n"
        f"WHAT THE MARKER SAID: {verdict}\n\n"
        "Walk them through what their query actually does to the rows, step by "
        "step, and show where that stops matching the question. Do NOT hand "
        "them the finished query — take them to the next thing to try.\n"
        + _SQL_SHAPE)


def _sql_ask_prompt(ex, sql, question):
    return (
        "You are a SQL tutor at a practice board, answering the learner's own "
        "question. They are about 16.\n"
        f"{_SQL_TABLES}\n"
        f"THE EXERCISE ON SCREEN: {ex['ask'] if ex else '(none)'}\n"
        f"WHAT THEY HAVE WRITTEN SO FAR:\n{sql or '(nothing yet)'}\n"
        f"THEIR QUESTION: {question}\n\n"
        "Answer that question. Ground it in the tables above and in what they "
        "have written — a general definition they could have read anywhere is "
        "a wasted answer. If the question is vague, answer the most useful "
        "reading of it rather than asking them to clarify.\n"
        + _SQL_SHAPE)


async def _sql_lesson(db, user, prompt, qkey, question, level):
    """Generate, validate and cache one structured explanation.

    Shared by explain and ask because they differ only in the prompt, and the
    caching, the spend accounting and the validation must not drift apart
    between two copies.
    """
    row = db.query(AskCache).filter(AskCache.qkey == qkey).first()
    if row:
        row.hits = (row.hits or 0) + 1
        db.commit()
        try:
            return json.loads(row.lesson), True
        except Exception:
            # A row from before the shape changed. Drop it and regenerate
            # rather than serving something the page cannot draw.
            db.delete(row)
            db.commit()

    _ai_enforce_limit(db, user)
    try:
        text = await _ai_text(prompt, 2200, json_mode=True)
        lesson = _clean_board(_ai_json(text), question[:80])
    except Exception as e:
        print(f"SQL board AI failed ({AI_PROVIDER}): {type(e).__name__}: {e}")
        raise HTTPException(503, _ai_error_message(e))
    if not lesson["steps"]:
        raise HTTPException(502, "That came back empty — try asking it a "
                                 "different way.")

    _ai_bump(db, user)
    _trial_consume(db, user, "sql_explain")
    db.add(AskCache(qkey=qkey, subject="sqlboard", level=level,
                    question=question[:2000], lesson=json.dumps(lesson),
                    hits=0))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return lesson, False


@app.post("/api/sql/explain")
async def sql_explain(body: SqlRunIn, user: User = Depends(current_user),
                      db: Session = Depends(get_db)):
    """A stepped, drawn explanation of this particular attempt.

    The only paid part of the board, because it is the only part that costs
    anything. Cached on the exercise plus the normalised query: wrong answers
    are not original — a hundred students write the same missing GROUP BY, and
    the second one onwards is served from the row the first one paid for.
    """
    ex = _sqlc.BY_ID.get(body.exercise)
    if not ex:
        raise HTTPException(404, "No such exercise")
    require_paid_or_trial(db, user, "sql_explain",
                          "Written explanations", "three free explanations")
    if not ASK_ENABLED:
        raise HTTPException(503, "The AI tutor is not switched on")

    sql = (body.sql or "").strip()
    if not sql:
        raise HTTPException(400, "Write a query first")
    verdict = _sqlc.mark(ex, sql)
    lesson, cached = await _sql_lesson(
        db, user, _sql_explain_prompt(ex, sql, verdict["why"]),
        _cl.key(_scope_of(db, user), "sqlx2", ex["id"],
                _norm_q(sql))[:500], sql, ex["skill"])
    return {"lesson": lesson, "short": verdict["why"], "cached": cached}


class SqlAskIn(BaseModel):
    question: str = Field(min_length=2, max_length=300)
    sql: str = Field(default="", max_length=4000)
    exercise: str = Field(default="", max_length=20)


@app.post("/api/sql/ask")
async def sql_ask(body: SqlAskIn, user: User = Depends(current_user),
                  db: Session = Depends(get_db)):
    """Ask the board anything, by typing or by speaking.

    Cached on the question plus the exercise, not on the student's draft
    query: "why is my total too high" is asked by everyone on the same
    exercise and deserves to be paid for once.
    """
    require_paid_or_trial(db, user, "sql_explain",
                          "Asking the board", "three free questions")
    if not ASK_ENABLED:
        raise HTTPException(503, "The AI tutor is not switched on")
    ex = _sqlc.BY_ID.get(body.exercise)
    q = body.question.strip()
    lesson, cached = await _sql_lesson(
        db, user, _sql_ask_prompt(ex, body.sql, q),
        _cl.key(_scope_of(db, user), "sqlq", body.exercise,
                _norm_q(q))[:500], q,
        ex["skill"] if ex else "ask")
    return {"lesson": lesson, "cached": cached}


# ==========================================================================
# The scanner: photograph anything, get it taught
# ==========================================================================
import scanner as _scan                                             # noqa: E402
import scene as _scene                                              # noqa: E402
import sketch as _sketch                                            # noqa: E402
import draw as _draw                                                # noqa: E402
import maths as _maths                                              # noqa: E402
import verify as _verify                                            # noqa: E402
import dimensions as _dimensions                                    # noqa: E402
import wolfram as _wolfram                                          # noqa: E402
import depth as _depth                                              # noqa: E402
import lattice as _lattice                                          # noqa: E402
import orbits as _orbits                                            # noqa: E402
import layers as _layers                                            # noqa: E402
import images as _images                                            # noqa: E402
import molecule as _molecule                                        # noqa: E402
import protein as _protein                                          # noqa: E402


@app.post("/api/scan")
async def scan(image: UploadFile = File(...),
               user: User = Depends(current_user),
               db: Session = Depends(get_db)):
    """Read a photographed problem and teach it.

    Cached on the bytes of the image. Two hundred people photographing the
    same page of the same textbook is one generation, not two hundred, which
    is the difference between this being affordable and not.
    """
    raw = await image.read()
    if not raw:
        raise HTTPException(400, "That photo was empty")
    if len(raw) > _scan.MAX_MB * 1024 * 1024:
        raise HTTPException(400, f"Photos need to be under "
                                 f"{_scan.MAX_MB:.0f}MB")
    mime = (image.content_type or "").lower().split(";")[0].strip()
    if mime not in _scan.MIMES:
        raise HTTPException(400, "Send a photo — JPG, PNG or WEBP")
    require_paid_or_trial(db, user, "scan", "The scanner", "three free scans")
    if not ASK_ENABLED:
        raise HTTPException(503, "The AI tutor is not switched on")

    digest = hashlib.sha256(raw).hexdigest()
    qkey = _cl.key(_scope_of(db, user), "scan", digest)[:500]
    row = db.query(AskCache).filter(AskCache.qkey == qkey).first()
    out = _cached_json(db, row, need=None)
    if out:
        row.hits = (row.hits or 0) + 1
        db.commit()
        _scan_remember(db, user, digest, out)
        return {"scan": out, "cached": True, "key": digest[:16]}

    _ai_enforce_limit(db, user)
    try:
        out = _scan.clean(_ai_json(
            await _ai_vision(_scan.prompt(), raw, mime, 2400)))
    except Exception as e:
        print(f"Scan failed: {type(e).__name__}: {e}")
        raise HTTPException(503, _ai_error_message(e))

    if not out["readable"]:
        # Not cached, and not charged for. A blurred photo is a photo to take
        # again, and storing the failure would serve it straight back to the
        # person who retakes it.
        return {"scan": out, "cached": False}

    # The fault that prompted all of this was a scanned maths problem
    # answered with a triple that satisfies one equation and not the other.
    # A photographed problem is as likely to come back with a wrong constant
    # as with a wrong answer, so it gets the whole battery, not just the
    # substitution check that started this.
    lines = ([out.get("read", "")]
             + [part
                for st in (out.get("steps") or []) if isinstance(st, dict)
                for part in (st.get("teach", ""), st.get("working", ""))]
             + [out.get("answer", "")])
    as_lesson = {"title": "", "steps": lines,
                 "takeaway": out.get("answer", "")}
    found, verdict = _check_lesson(as_lesson)
    # The scanner most of all. This is where somebody photographs a problem
    # they are stuck on and copies the answer into their book — the wrong
    # answer here is the one that reaches an exam.
    review = await _review_lesson(out.get("read") or "this problem", as_lesson)
    if review:
        found = review + found
        if any(r["severity"] == "critical" for r in review):
            verdict = {"cache": False, "confidence": "low", "state": "flagged"}
        elif verdict["confidence"] == "high":
            verdict = dict(verdict, confidence="medium", state="checked")
    if found:
        print(f"Checks on a scan: {verdict['state']} — "
              f"{found[0]['problem'][:120]}")
        out["findings"] = _note_findings(found)
        out["confidence"] = verdict["confidence"]

    _ai_bump(db, user)
    _trial_consume(db, user, "scan")
    if not verdict["cache"]:
        _scan_remember(db, user, digest, out)
        return {"scan": out, "cached": False, "key": digest[:16]}
    db.add(AskCache(qkey=qkey, subject="scan", level=out["kind"],
                    question=_scan.title(out)[:2000],
                    lesson=json.dumps(out), hits=0))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    _scan_remember(db, user, digest, out)
    return {"scan": out, "cached": False, "key": digest[:16]}


def _scan_remember(db, user, digest, out):
    """Keep it in this person's recent list.

    In the existing per-user notes table rather than a new one: a saved scan
    is a key and a blob, which is exactly what that table is, and a second
    table would be a second migration and a second place to forget when
    somebody asks to be erased.
    """
    k = f"scan:{digest[:16]}"
    row = db.query(Note).filter(Note.user_id == user.id, Note.k == k).first()
    body = json.dumps({"title": _scan.title(out), "kind": out["kind"],
                       "subject": out.get("subject", ""),
                       "at": now().isoformat()})
    if row:
        row.v = body
    else:
        db.add(Note(user_id=user.id, k=k, v=body))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()


@app.get("/api/scan/recent")
def scan_recent(user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    """This person's recent scans, newest first."""
    rows = db.query(Note).filter(Note.user_id == user.id,
                                 Note.k.like("scan:%")).all()
    out = []
    for r in rows:
        try:
            d = json.loads(r.v)
        except Exception:
            continue
        d["key"] = r.k.split(":", 1)[1]
        out.append(d)
    out.sort(key=lambda x: x.get("at", ""), reverse=True)
    return {"recent": out[:30]}


@app.get("/api/scan/{key}")
def scan_one(key: str, user: User = Depends(current_user),
             db: Session = Depends(get_db)):
    """Reopen a saved scan.

    Checked against this user's own notes first, so the cache — which is
    shared by everyone and keyed on the image — cannot be walked by guessing
    digests.
    """
    k = f"scan:{key[:16]}"
    mine = db.query(Note).filter(Note.user_id == user.id, Note.k == k).first()
    if not mine:
        raise HTTPException(404, "Not one of yours")
    row = db.query(AskCache).filter(
        AskCache.qkey.like(f"scan|{key[:16]}%")).first()
    out = _cached_json(db, row, need=None)
    if not out:
        raise HTTPException(404, "That answer is no longer stored")
    return {"scan": out, "key": key[:16]}


@app.delete("/api/scan/recent")
def scan_clear(user: User = Depends(current_user),
               db: Session = Depends(get_db)):
    """Clear the list. Removes this person's history, not the shared cache —
    the cache holds answers keyed on images, not on who asked."""
    n = db.query(Note).filter(Note.user_id == user.id,
                              Note.k.like("scan:%")).delete(
        synchronize_session=False)
    db.commit()
    return {"cleared": n}


# ==========================================================================
# "Should I teach you this properly?"
# ==========================================================================
# An answer solves today's problem and is forgotten by Thursday. The offer
# under every answer is the actual product: turn the thing you were stuck on
# into a course that takes you from where you are to competent.
#
# Cached on the topic, so the tenth person who gets stuck on the same thing
# pays nothing for the course the first one generated.
class CourseIn(BaseModel):
    topic: str = Field(min_length=2, max_length=200)
    level: str = Field(default="", max_length=40)
    context: str = Field(default="", max_length=1200)


# Depth is the only dimension this product fixes. There is no subject list,
# because any list would be missing somebody's subject — a course on Ottoman
# tax law and a course on tensor calculus are the same product here. What does
# have to be pinned down is how far to go: the same topic is a different
# course for someone meeting it in second year and someone who needs it for a
# thesis, and getting that wrong wastes the whole thing in either direction.
_DEPTH = {
    "curious": "an interested adult with no background in this. Assume "
               "nothing, define everything, and aim for real understanding "
               "rather than a simplified story they will have to unlearn.",
    "undergrad": "an undergraduate studying this formally. Standard notation "
                 "and terminology, worked examples like the ones in their "
                 "problem sets, and the derivations rather than just results.",
    "masters": "a master's student. They have the undergraduate material. Go "
               "to the level of a graduate course: proper treatment, the "
               "assumptions behind the standard results, and where those "
               "assumptions break.",
    "phd": "a doctoral researcher. Assume full command of the fundamentals. "
           "Cover the current state of the question, the competing "
           "approaches, what is genuinely unsettled, and name the key papers "
           "or results by author and year where you are confident of them.",
    "applied": "someone who needs to use this at work rather than be examined "
               "on it. Lead with the decisions they will actually have to "
               "make and the ways this goes wrong in practice; keep the "
               "theory to what changes those decisions.",
}


def _norm_opt(t):
    """An option reduced to what it says, for comparing."""
    return " ".join(str(t or "").lower().split()).strip(" .;:\u2014-")


def _match_option(value, opts, inside=False):
    """Which option is this text? None if it is not exactly one of them.

    Exact when matching a stated answer. When scanning an explanation, an
    option counts only if it appears in full and no other option does —
    "border-box" inside "box-sizing: border-box" would otherwise match two.
    """
    want = _norm_opt(value)
    if not want:
        return None
    norm = [_norm_opt(o) for o in opts]
    hits = [i for i, o in enumerate(norm) if o and o == want]
    if len(hits) == 1:
        return hits[0]
    if not inside:
        return None
    # Longest first, so the most specific option wins its own substring.
    hits = [i for i, o in enumerate(norm)
            if o and len(o) >= 6 and o in want]
    if len(hits) == 1:
        return hits[0]
    return None


# Where an explanation stops teaching and starts thinking aloud.
_ALOUD = _re.compile(
    r"\b(wait|hold on|let me (?:check|re-?add|recount|think)|let's (?:check|"
    r"re-?add|recount|see)|actually,|hmm|oops|scratch that|on second thought|"
    r"i mean|correction:|ah,|so index|index \d|option \d|"
    r"\(index|is index)\b", _re.I)


def _plain_reason(why, cap):
    """An explanation with the model's deliberation cut off.

    One course told a student: "equalling 450px. Wait, let's re-add: 400 + 40
    + 10 = 450. Option 3 is 450px (index 2? Let's check: 0=400 ...)". The
    reason was the first sentence; the rest was the model working, and it
    should never have been on the page.
    """
    t = " ".join(str(why or "").split())
    m = _ALOUD.search(t)
    if m:
        t = t[:m.start()].strip()
    t = t.rstrip(" ,;:\u2014-")
    # If cutting left nothing usable, say nothing rather than a fragment.
    return t[:cap] if len(t) >= 15 else ""


# The last few board requests, for diagnosis. Bounded and in memory: this
# must not cost a database write per lesson, and it is not a record anybody
# needs tomorrow.
_BOARD_TRACE = []
_BOARD_TRACE_MAX = 20


class _Trace:
    """Phase timings for one board request.

    Used as a context manager so an exception is recorded rather than
    swallowed — a request that dies is exactly the one worth seeing.
    """

    def __init__(self, topic, level):
        import time as _t
        self._t = _t
        self.row = {"topic": str(topic)[:70], "level": str(level)[:30],
                    "at": now().isoformat(timespec="seconds"),
                    "phases": [], "ended": "in flight"}
        self._start = _t.monotonic()
        self._mark = self._start
        _BOARD_TRACE.append(self.row)
        del _BOARD_TRACE[:-_BOARD_TRACE_MAX]

    def phase(self, name):
        t = self._t.monotonic()
        self.row["phases"].append(f"{name} {t - self._mark:.2f}s")
        self._mark = t

    def done(self, how):
        self.row["ended"] = how
        self.row["total"] = round(self._t.monotonic() - self._start, 2)


def _course_prompt(topic, level, context):
    who = _DEPTH.get((level or "").strip().lower(),
                     "an adult studying this at their own level")
    return f"""Build a complete course that takes someone from where they are
now to genuinely competent at this. They arrived here because they got stuck
on something specific.

This can be any subject at all — medicine, law, pure mathematics, history,
engineering, linguistics, finance, a language. Do not steer it towards
programming, and do not assume any technical background beyond what the level
below implies.

Teach it the way its own field teaches it. Mathematics argues from definition
and proof, physics from principle and order of magnitude, chemistry from
mechanism, medicine from presentation and differential, law from authority and
the test the court applies, history from what the sources can support,
engineering from requirement and failure mode. Use that field's notation,
units and canonical examples, and do not borrow an illustration from an
unrelated subject because it is familiar. Where you do use an analogy, say it
is one and say where it breaks.

Go to the theory, not only the recipe: why the result is true, what it rests
on, and the conditions under which it stops holding.

THE TOPIC: {topic}
WHO THEY ARE: {who}
WHAT THEY WERE STUCK ON: {context or "(not given)"}

This is not a summary and not a reading list. It is the actual teaching, in
order, so that someone who works through it can do the thing afterwards.

Return JSON only:
{{"title": "the course name",
  "why": "2-3 sentences on what they will be able to do at the end, concretely",
  "hours": 6,
  "prereq": ["anything they must already know, or an empty list"],
  "modules": [
    {{"name": "module name",
      "goal": "one sentence on what this module gets them to",
      "lessons": [
        {{"name": "lesson name",
          "teach": "4-8 sentences of the actual explanation, not a description
                    of what would be explained",
          "example": "a worked example, or the code, in full",
          "practice": "one thing for them to do, specific enough to check",
          "trap": "the mistake almost everyone makes here",
          "visual": {{"want": "3d"|"none",
                      "of": "the exact thing to show, e.g. human heart,
                             four chambers",
                      "look_for": "what they should notice when they look
                                   at it"}},
          "check": {{"q": "one question testing THIS lesson",
                     "options": ["four options"],
                     "correct": "the correct option, copied out in full,
                                 exactly as it appears in options",
                     "why": "why that is right and the near-miss is wrong"}}}}],
      "exam": [{{"q": "...", "options": ["four options"],
                 "correct": "the correct option, copied out word for word",
                 "why": "..."}}]}}],
  "after": "what to learn next once this is solid"}}

Rules:
- "correct" is the winning option copied out in full, not a number and not
  a letter. Never write "option 3", "the third one", or an index. Copy the
  text. Counting positions while writing prose is how questions end up
  marked against their own explanations.
- "why" is for the student. Give the reason and stop. Never show your
  working-out, never correct yourself mid-sentence, never mention options
  by position, and never write "wait", "let me check" or "actually" — the
  reader wants the reason, not the search for it.
- 3 to 5 modules, 2 to 4 lessons each. Build strictly on what came before.
- `teach` is the teaching itself. A lesson whose teach says "this lesson
  covers X" has failed and is worth nothing to the reader.
- Every lesson ends with a `check`: one question, four options, `answer` is
  the 0-based index of the right one. Test whether they understood the
  lesson, not whether they remember a word from it. Make the wrong options
  plausible — an option nobody would pick tests nothing.
- Every module ends with an `exam` of 3 to 5 questions in the same shape,
  drawing on the whole module rather than one lesson.
- `visual.want` is "3d" only where rotating and zooming a real object would
  genuinely teach something — anatomy, molecules, mechanisms, astronomy,
  geology. For anything flat, send a `sketch` instead — that is what they are
  for. Use "none" where a picture would be decoration, which is most lessons.
- Plain text. No markdown, no backticks, no HTML.
- Define every term the first time it appears.
- Be concrete. Real numbers, real names, real code, real cases.
- EVERY lesson says where this actually turns up. Not "this is important" —
  name the job, the machine, the court, the ward, the factory, the paper.
  Where is a matrix multiplication happening as you read this? Who is being
  paid to know this today, and to do what with it? An integral that is never
  connected to the thing it measures is the reason people believe maths is
  pointless, and the same is true of every other subject.

{_draw.PROMPT}

{_sketch.PROMPT}

{_scene.PROMPT}"""


def _clean_course(d):
    """Rebuild the course field by field, same discipline as everything else."""
    def txt(v, n):
        s = str(v or "")
        s = "".join(c for c in s if c in "\n\t" or ord(c) >= 32)
        return s.strip()[:n]

    def quiz(q):
        """One multiple-choice question, or None.

        The right answer travels to the browser with the question, because
        these are self-tests: grading happens instantly, offline and free.
        Anyone determined enough to read it out of the network tab is cheating
        at a test they set themselves, which is their business. A real exam
        would need the answer kept back and a marking round-trip; this is not
        one, and pretending otherwise would cost a request per question to
        protect nothing.
        """
        if not isinstance(q, dict):
            return None
        opts = [txt(o, 200) for o in (q.get("options") or [])[:4] if txt(o, 200)]
        if len(opts) < 2 or not txt(q.get("q"), 300):
            return None

        # The answer is matched by text, not taken as a number. Asked for an
        # index, the model counted wrong often enough to mark right answers
        # wrong while explaining, in the same sentence, why they were right.
        a = _match_option(q.get("correct"), opts)
        if a is None:
            try:
                a = int(q.get("answer"))
            except Exception:
                return None
            if not (0 <= a < len(opts)):
                return None

        why = _plain_reason(q.get("why"), 500)
        # The explanation is the part written for a human. If it quotes one
        # option and the index disagrees, believe the explanation.
        named = _match_option(why, opts, inside=True)
        if named is not None and named != a:
            print(f"Quiz answer corrected by its own explanation: "
                  f"{opts[a][:40]!r} -> {opts[named][:40]!r}")
            a = named
        return {"q": txt(q.get("q"), 300), "options": opts, "answer": a,
                "why": why}

    def visual(v):
        if not isinstance(v, dict):
            return None
        want = str(v.get("want") or "").strip().lower()
        # "diagram" used to be accepted here and was never drawn by
        # anything: a value the schema allowed and the page ignored. Flat
        # pictures are sketches now, and they have their own field.
        if want != "3d":
            return None
        return {"want": want, "of": txt(v.get("of"), 120),
                "look_for": txt(v.get("look_for"), 300)}

    mods = []
    for m in (d.get("modules") or [])[:5]:
        if not isinstance(m, dict):
            continue
        lessons = []
        for l in (m.get("lessons") or [])[:4]:
            if not isinstance(l, dict):
                continue
            lesson = {"name": txt(l.get("name"), 120),
                      "teach": txt(l.get("teach"), 2200),
                      "example": txt(l.get("example"), 1600),
                      "practice": txt(l.get("practice"), 600),
                      "trap": txt(l.get("trap"), 500),
                      "visual": visual(l.get("visual")),
                      "scene": _scene.clean(l.get("scene")),
                      "sketch": _sketch.clean(l.get("sketch")),
                      "draw": _draw.clean(l.get("draw")),
                      "check": quiz(l.get("check"))}
            if lesson["teach"]:
                lessons.append(lesson)
        if lessons:
            exam = [q for q in (quiz(x) for x in (m.get("exam") or [])[:5]) if q]
            mods.append({"name": txt(m.get("name"), 120),
                         "goal": txt(m.get("goal"), 300),
                         "lessons": lessons, "exam": exam})
    try:
        hours = max(1, min(200, int(d.get("hours") or 6)))
    except Exception:
        hours = 6
    return {"title": txt(d.get("title"), 120),
            "why": txt(d.get("why"), 600),
            "hours": hours,
            "prereq": [txt(x, 90) for x in (d.get("prereq") or [])[:5]
                       if txt(x, 90)],
            "modules": mods,
            "after": txt(d.get("after"), 300)}


@app.post("/api/course")
async def build_course(body: CourseIn, user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    """Generate a full course on one topic. Paid — it is the largest single
    generation on the site, and the one worth paying for."""
    require_paid_or_trial(db, user, "course", "Personalised courses",
                          "one free course")
    if not ASK_ENABLED:
        raise HTTPException(503, "The AI tutor is not switched on")
    topic = body.topic.strip()
    qkey = _cl.key(_scope_of(db, user), "course", _norm_q(body.level),
                   _norm_q(topic))[:500]
    row = db.query(AskCache).filter(AskCache.qkey == qkey).first()
    course = _cached_json(db, row, need=None)
    if course:
        row.hits = (row.hits or 0) + 1
        db.commit()
        return {"course": course, "cached": True}

    _ai_enforce_limit(db, user)
    try:
        course = _clean_course(_ai_json(await _ai_text(
            _course_prompt(topic, body.level, body.context), 9000,
            json_mode=True, best=True)))
    except Exception as e:
        print(f"Course failed: {type(e).__name__}: {e}")
        raise HTTPException(503, _ai_error_message(e))
    if not course["modules"]:
        raise HTTPException(502, "That came back empty — try naming the topic "
                                 "more specifically.")

    _ai_bump(db, user)
    _trial_consume(db, user, "course")
    db.add(AskCache(qkey=qkey, subject="course", level=body.level or "any",
                    question=topic[:2000], lesson=json.dumps(course), hits=0))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return {"course": course, "cached": False}


# ==========================================================================
# Coming back to it
# ==========================================================================
# Everything anyone asks here is answered and then gone. That is fine for a
# lookup and wrong for learning: people study in twenty-minute pieces, close
# the tab, and come back not remembering what they were halfway through.
#
# So two things are kept per person. What they asked, so a session can be
# picked up where it stopped; and which self-tests they have actually
# answered, because that — not how many lessons scrolled past — is the only
# honest measure of progress.
class RecentIn(BaseModel):
    q: str = Field(min_length=1, max_length=300)
    kind: str = Field(default="ask", max_length=12)


RECENT_KINDS = ("ask", "board", "talk", "scan", "sql", "course")
RECENT_KEEP = 40


@app.post("/api/recent")
def recent_add(body: RecentIn, user: User = Depends(current_user),
               db: Session = Depends(get_db)):
    """Remember that this person asked this."""
    kind = body.kind if body.kind in RECENT_KINDS else "ask"
    q = body.q.strip()
    if not q:
        raise HTTPException(400, "Nothing to remember")
    # Keyed on the question, so asking the same thing twice moves it up the
    # list rather than filling the list with itself.
    k = f"recent:{hashlib.sha256(_norm_q(q).encode()).hexdigest()[:16]}"
    row = db.query(Note).filter(Note.user_id == user.id, Note.k == k).first()
    body_json = json.dumps({"q": q[:300], "kind": kind,
                            "at": now().isoformat()})
    if row:
        row.v = body_json
    else:
        db.add(Note(user_id=user.id, k=k, v=body_json))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()

    # Trim. Without this the notes table grows for the life of the account,
    # and nobody scrolls to their four hundredth question anyway.
    rows = db.query(Note).filter(Note.user_id == user.id,
                                 Note.k.like("recent:%")).all()
    if len(rows) > RECENT_KEEP:
        def when(r):
            try:
                return json.loads(r.v).get("at", "")
            except Exception:
                return ""
        for old in sorted(rows, key=when)[:len(rows) - RECENT_KEEP]:
            db.delete(old)
        db.commit()
    return {"ok": True}


@app.get("/api/recent")
def recent_list(user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    """What this person was working on, newest first."""
    out = []
    for r in db.query(Note).filter(Note.user_id == user.id,
                                   Note.k.like("recent:%")).all():
        try:
            d = json.loads(r.v)
        except Exception:
            continue
        d["key"] = r.k.split(":", 1)[1]
        out.append(d)
    out.sort(key=lambda x: x.get("at", ""), reverse=True)
    return {"recent": out[:RECENT_KEEP]}


@app.delete("/api/recent")
def recent_clear(user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    n = db.query(Note).filter(Note.user_id == user.id,
                              Note.k.like("recent:%")).delete(
        synchronize_session=False)
    db.commit()
    return {"cleared": n}


class CourseMarkIn(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    lesson: str = Field(min_length=1, max_length=40)   # "m0l1" or "m0e2"
    correct: bool = False


@app.post("/api/course/progress")
def course_mark(body: CourseMarkIn, user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    """Record one answered self-test.

    Progress moves here and nowhere else. Scrolling past a lesson is not
    learning it, and a bar that fills as you scroll is a bar that lies — so
    completion is counted from questions actually answered, and only the ones
    answered correctly count as done.
    """
    slug = f"course:{_norm_q(body.topic)[:30]}:{body.lesson}"[:60]
    row = db.query(Progress).filter(Progress.user_id == user.id,
                                    Progress.lesson_slug == slug).first()
    if row is None:
        row = Progress(user_id=user.id, lesson_slug=slug, attempts=0)
        db.add(row)
    row.attempts = (row.attempts or 0) + 1
    if body.correct and not row.completed:
        row.completed = True
        row.completed_at = now()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return course_progress(body.topic, user, db)


@app.get("/api/course/progress")
def course_progress(topic: str = "", user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    """Which of this course's questions this person has answered."""
    pre = f"course:{_norm_q(topic)[:30]}:"
    rows = db.query(Progress).filter(
        Progress.user_id == user.id,
        Progress.lesson_slug.like(pre + "%")).all()
    done = {}
    for r in rows:
        done[r.lesson_slug[len(pre):]] = {"tries": r.attempts or 0,
                                          "correct": bool(r.completed)}
    return {"answered": done,
            "right": sum(1 for v in done.values() if v["correct"]),
            "attempted": len(done)}


# ==========================================================================
# The lab
# ==========================================================================
# Free, and free forever, for the same reason the SQL board is: none of it
# costs a model call. The chemistry is a table of real reactions and the
# physics is closed-form, so a thousand students running a thousand
# experiments costs exactly what one does.
#
# It is also the one place on the site where a model must not be involved.
# Asked what happens when two reagents meet, a language model produces a
# fluent answer whether or not it knows — and a confidently invented reaction
# is not a wrong answer like a wrong date is a wrong answer. Somebody acts on
# it. So a pair that is not in the table returns "not simulated" rather than
# a guess.
import lab as _lab                                                  # noqa: E402


class MixIn(BaseModel):
    a: str = Field(min_length=1, max_length=20)
    b: str = Field(min_length=1, max_length=20)
    grams_a: float = 10.0
    grams_b: float = 10.0


class SimIn(BaseModel):
    kind: str = Field(min_length=1, max_length=20)
    # Loose on purpose: each simulation reads the numbers it needs and the
    # engine clamps every one of them.
    values: dict = {}


import net as _net                                                  # noqa: E402


class PacketIn(BaseModel):
    src: str = Field(default="", max_length=40)
    dst: str = Field(default="", max_length=40)
    proto: str = Field(default="tcp", max_length=8)
    dport: int = Field(default=443, ge=0, le=65535)
    established: bool = False
    routes: list = []
    rules: list = []


# What a firewall lesson starts from, so nobody faces an empty form. The
# order is the point: a permissive rule above a restrictive one makes the
# restrictive one dead, and this list demonstrates it.
NET_PRESET = {
    "routes": [
        {"network": "192.168.1.0/24", "via": "", "dev": "eth1"},
        {"network": "10.0.0.0/8", "via": "192.168.1.1", "dev": "eth1"},
        {"network": "0.0.0.0/0", "via": "203.0.113.1", "dev": "eth0"},
    ],
    "rules": [
        {"action": "accept", "proto": "tcp", "src": "any",
         "dst": "10.0.0.5", "port": 443},
        {"action": "drop", "proto": "tcp", "src": "203.0.113.0/24",
         "dst": "any", "port": "any"},
        {"action": "accept", "proto": "tcp", "src": "192.168.1.0/24",
         "dst": "any", "port": 22},
    ],
    "packet": {"src": "203.0.113.7", "dst": "10.0.0.5",
               "proto": "tcp", "dport": 443},
}


@app.get("/api/net")
def net_index(user: User = Depends(current_user)):
    """A network to start from."""
    return NET_PRESET


@app.post("/api/net/trace")
def net_trace(body: PacketIn, user: User = Depends(current_user)):
    """Walk one packet through the routes and the rules.

    No model call, so it is free, instant and the same for everybody — and
    incapable of inventing a firewall decision, which is the point. A model
    asked why a packet was dropped gives a fluent and plausible reason; this
    gives the actual one.
    """
    try:
        _net.ip_to_int(body.src)
        _net.ip_to_int(body.dst)
    except _net.BadAddress as e:
        raise HTTPException(400, str(e))

    pkt = {"src": body.src, "dst": body.dst,
           "proto": (body.proto or "tcp").lower()[:8],
           "dport": int(body.dport)}

    routes = [r for r in (body.routes or []) if isinstance(r, dict)]
    rules = [r for r in (body.rules or []) if isinstance(r, dict)]

    best, others = _net.route_for(body.dst, routes)
    verdict, trace, matched = _net.evaluate(rules, pkt, body.established)

    steps = []
    # 1. Is the destination on this wire, or does it need a router?
    local = best is not None and not best.get("via")
    steps.append({
        "stage": "Where does this go?",
        "detail": (f"{body.dst} is on the directly connected network "
                   f"{best['network']}, so it goes straight out "
                   f"{best.get('dev') or 'the interface'} \u2014 no router "
                   f"involved." if local and best else
                   (f"{body.dst} is not on any directly connected network, "
                    f"so it is sent to the gateway {best['via']} via "
                    f"{best.get('dev') or 'the interface'}."
                    if best else
                    f"No route matches {body.dst}. The packet is dropped "
                    f"here with 'network unreachable' \u2014 nothing "
                    f"downstream ever sees it.")),
        "ok": best is not None,
    })

    # 2. Why that route and not another.
    if best:
        steps.append({
            "stage": "Which route won, and why",
            "detail": (f"{best['network']} was chosen because it is the "
                       f"longest prefix that matches. Longest prefix wins \u2014 "
                       f"not first listed, not most recently added."),
            "beaten": [f"{o['network']} (/{o['bits']})" for o in others],
            "ok": True,
        })

    # 3. ARP, but only when the next hop is on this wire.
    if best:
        nexthop = best.get("via") or body.dst
        steps.append({
            "stage": "Who has that address?",
            "detail": (f"The packet needs a MAC address for {nexthop}, not "
                       f"an IP. If it is not in the ARP cache the host "
                       f"broadcasts 'who has {nexthop}?' and waits for the "
                       f"reply before anything is sent."),
            "ok": True,
        })

    # 4. The firewall, rule by rule.
    steps.append({
        "stage": "The firewall",
        "detail": ("This packet belongs to a connection already established, "
                   "so the rule list is never read. That is why a firewall "
                   "with only outbound rules still lets replies back in."
                   if body.established else
                   f"Rules are read in order and the first match wins. "
                   f"Rule {matched['n']} decided it."
                   if matched.get("n") else
                   "No rule matched, so the default policy applied."),
        "rules": trace,
        "verdict": verdict,
        "ok": verdict == "ACCEPT",
    })

    return {"verdict": verdict, "steps": steps, "packet": pkt,
            "route": best, "matched": matched}


@app.get("/api/lab")
def lab_index(user: User = Depends(current_user)):
    """The shelf and the bench."""
    return {"experiments": _lab.EXPERIMENTS,
            "reagents": [{"sym": k, "name": n, "kind": t}
                         for k, n, t in _lab.REAGENTS],
            "pairs": [sorted(r["pair"]) for r in _lab.REACTIONS]}


@app.post("/api/lab/mix")
def lab_mix(body: MixIn, user: User = Depends(current_user)):
    """Mix two reagents and report exactly what comes back."""
    return _lab.react(body.a, body.b, body.grams_a, body.grams_b)


class MixAskIn(BaseModel):
    # Either a pair of reagents, or an experiment described in words. One
    # endpoint, because both are the same request: something the deterministic
    # benches cannot compute, explained instead.
    a: str = Field(default="", max_length=60)
    b: str = Field(default="", max_length=60)
    what: str = Field(default="", max_length=300)
    subject: str = Field(default="", max_length=40)


@app.post("/api/lab/explain")
async def lab_explain(body: MixAskIn, user: User = Depends(current_user),
                      db: Session = Depends(get_db)):
    """Anything the bench cannot simulate, explained rather than simulated.

    The shelf holds seventeen reagents because those are the ones with a
    verified reaction table behind them. People want to mix other things, and
    telling them "no" is a bad answer to a good instinct — so this exists, and
    it is careful about two things.

    It is labelled. The response says `simulated: false`, and the page prints
    it as an explanation, because a number computed from a balanced equation
    and a paragraph written by a language model are different kinds of thing
    and must never look alike on a chemistry bench.

    And it leads with the hazard. A model asked "what happens if I mix X and
    Y" will cheerfully describe the products of something that produces
    chlorine gas in a domestic bathroom. The prompt puts danger first and
    forbids anything resembling a procedure, because the honest answer to some
    of these questions is "do not, and here is why".
    """
    a, b = body.a.strip(), body.b.strip()
    what = body.what.strip()
    if not what and (not a or not b):
        raise HTTPException(400, "Name two things, or describe the experiment")
    if not ASK_ENABLED:
        raise HTTPException(503, "The AI tutor is not switched on")
    require_paid_or_trial(db, user, "scan", "Explaining a mixture",
                          "three free explanations")

    # Cached on the unordered pair: mixing A with B is the same question as
    # mixing B with A, and the first person to ask pays for both.
    if what:
        qkey = _cl.key(_scope_of(db, user), "labany", _norm_q(body.subject),
                       _norm_q(what))[:500]
    else:
        # Two reagents off a fixed shelf, in a fixed order. Nobody's words
        # are in this key, so it pools for everybody and the first person
        # to mix them pays for the whole site.
        pair = " + ".join(sorted([_norm_q(a), _norm_q(b)]))
        qkey = _cl.key(_cl.PUBLIC, "labmix", pair)[:500]
    row = db.query(AskCache).filter(AskCache.qkey == qkey).first()
    if row:
        row.hits = (row.hits or 0) + 1
        db.commit()
        return {"ok": True, "simulated": False, "text": row.lesson,
                "cached": True}

    _ai_enforce_limit(db, user)
    prompt = (
        (f"Someone is working through an experiment and asks what would "
         f"happen. They are an adult, studying at their own level.\n"
         f"SUBJECT: {body.subject or 'work it out from the description'}\n"
         f"THE EXPERIMENT: {what}\n\n"
         "Say what would actually be observed and why — the mechanism or the "
         "principle, not just the outcome. Give the numbers where the "
         "physics or the arithmetic fixes them, and say plainly when a "
         "result depends on conditions you have not been told.\n"
         if what else
         f"Someone learning chemistry asks what happens if {a} and {b} are "
         f"mixed. They are an adult. Answer as a chemistry teacher would.\n\n")
        +
        "START WITH THE DANGER if there is any — toxic gas, violent reaction, "
        "heat, pressure, explosion — and say plainly if this is something "
        "nobody should do outside a fume hood, or at all. Do not soften it.\n"
        "Then say what actually happens: whether they react at all, what "
        "forms, and what you would see. Give the balanced equation if there "
        "is one.\n"
        "If they do not react, say so — that is a real answer and people "
        "assume everything reacts with everything.\n"
        "If you are not certain, say you are not certain rather than "
        "producing a plausible equation. A wrong reaction here is not a wrong "
        "answer, it is somebody in an emergency room.\n\n"
        "Never give quantities, a procedure, or steps to carry it out. "
        "Explain the chemistry, do not instruct the experiment.\n"
        "Plain text. No markdown, no headings, no bullet characters. "
        "Under 160 words.")
    try:
        text = (await _ai_text(prompt, 420)).strip()
    except Exception as e:
        print(f"Lab explain failed ({AI_PROVIDER}): {type(e).__name__}: {e}")
        raise HTTPException(503, _ai_error_message(e))
    if not text:
        raise HTTPException(502, "Nothing came back — try naming them "
                                 "differently.")
    text = _re.sub(r"[*#`_]+", "", text)[:1400]

    _ai_bump(db, user)
    _trial_consume(db, user, "scan")
    db.add(AskCache(qkey=qkey, subject="lab", level="any" if what else "mix",
                    question=(what or f"{a} + {b}")[:2000], lesson=text,
                    hits=0))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return {"ok": True, "simulated": False, "text": text, "cached": False}


@app.post("/api/lab/sim")
def lab_sim(body: SimIn, user: User = Depends(current_user)):
    """Run one of the physics benches."""
    v = body.values or {}
    k = body.kind
    if k == "projectile":
        return _lab.projectile(v.get("speed", 20), v.get("angle", 45),
                               v.get("height", 0))
    if k == "circuit":
        return _lab.circuit(v.get("resistances") or [100, 220],
                            v.get("volts", 12),
                            bool(v.get("series", True)))
    if k == "pendulum":
        return _lab.pendulum(v.get("length", 1.0), v.get("angle", 10.0))
    if k == "lens":
        return _lab.lens(v.get("focal", 50.0), v.get("object", 150.0))
    if k == "spring":
        return _lab.spring(v.get("k", 200), v.get("mass", 0.5),
                           v.get("x", 0.1))
    if k == "collision":
        return _lab.collision(v.get("m1", 2), v.get("u1", 3),
                              v.get("m2", 1), v.get("u2", 0),
                              bool(v.get("elastic", True)))
    if k == "gas":
        return _lab.gas(v.get("p1", 100), v.get("v1", 1), v.get("t1", 300),
                        v.get("p2"), v.get("v2"), v.get("t2"))
    if k == "calorimetry":
        return _lab.calorimetry(v.get("mass_a", 0.1), v.get("temp_a", 80),
                                v.get("mass_b", 0.1), v.get("temp_b", 20))
    if k == "wave":
        return _lab.wave(v.get("freq", 170), v.get("wavelength"),
                         v.get("speed"), v.get("length"))
    if k == "punnett":
        return _lab.punnett(v.get("a", "Aa"), v.get("b", "Aa"))
    if k == "population":
        return _lab.population(v.get("n0", 100), v.get("rate", 0.1),
                               v.get("steps", 12), v.get("capacity"))
    if k == "ph":
        return _lab.ph(v.get("conc", 0.01), v.get("kind", "acid"))
    raise HTTPException(404, "No such experiment")


@app.post("/api/lab/photo")
async def lab_photo(image: UploadFile = File(...),
                    question: str = Form(default=""),
                    user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    """Photograph an apparatus, a setup, or a reaction in progress.

    The scanner reads a written problem. This is for the bench itself: a
    titration mid-way, a circuit somebody has built, a plate of colonies, a
    reading on a meter. What you get back is an explanation of what is set up
    and what it is doing — labelled as an explanation, like everything else
    on this page that is not computed from a formula.
    """
    raw = await image.read()
    if not raw:
        raise HTTPException(400, "That photo was empty")
    if len(raw) > _scan.MAX_MB * 1024 * 1024:
        raise HTTPException(400, f"Photos need to be under {_scan.MAX_MB:.0f}MB")
    mime = (image.content_type or "").lower().split(";")[0].strip()
    if mime not in _scan.MIMES:
        raise HTTPException(400, "Send a photo — JPG, PNG or WEBP")
    require_paid_or_trial(db, user, "scan", "Explaining a photo of a setup",
                          "three free photo explanations")
    if not ASK_ENABLED:
        raise HTTPException(503, "The AI tutor is not switched on")

    q = (question or "").strip()[:200]
    digest = hashlib.sha256(raw).hexdigest()[:32]
    qkey = _cl.key(_scope_of(db, user), "labpic", digest, _norm_q(q))[:500]
    row = db.query(AskCache).filter(AskCache.qkey == qkey).first()
    if row:
        row.hits = (row.hits or 0) + 1
        db.commit()
        return {"ok": True, "simulated": False, "text": row.lesson,
                "cached": True}

    _ai_enforce_limit(db, user)
    prompt = (
        "Someone has photographed a laboratory or workshop setup and wants to "
        "understand it. They are an adult learner.\n"
        + (f"THEY ASK: {q}\n" if q else "")
        + "\nSay what the apparatus in the photo actually is and what it is "
        "for, then what is happening or about to happen, then what the "
        "result would tell them.\n"
        "LEAD WITH ANY DANGER you can see — an unstoppered reaction that "
        "should be vented, a flame near something flammable, missing eye "
        "protection, a setup that will boil over.\n"
        "If the photo does not show what the question implies, or you cannot "
        "make it out, say so rather than describing a plausible experiment.\n"
        "Never give quantities or a procedure to carry it out. Explain the "
        "setup, do not instruct the experiment.\n"
        "Plain text. No markdown, no headings, no bullet characters. Under "
        "170 words.")
    try:
        text = (await _ai_vision(prompt, raw, mime, 500)).strip()
    except Exception as e:
        print(f"Lab photo failed ({AI_PROVIDER}): {type(e).__name__}: {e}")
        raise HTTPException(503, _ai_error_message(e))
    if not text:
        raise HTTPException(502, "Nothing came back — try a clearer photo.")
    text = _re.sub(r"[*#`_]+", "", text)[:1400]

    _ai_bump(db, user)
    _trial_consume(db, user, "scan")
    db.add(AskCache(qkey=qkey, subject="lab", level="photo",
                    question=(q or "a photographed setup")[:2000],
                    lesson=text, hits=0))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return {"ok": True, "simulated": False, "text": text, "cached": False}


# /detail/ and not /api/jobs/{job_id}: FastAPI matches in definition
# order, so a bare id segment swallows every static /api/jobs/<word>
# route declared below it — "filters" and "tracked" were being read as
# job ids and those endpoints stopped existing. Ordering would fix it
# today and break again the next time somebody adds a route here.
@app.get("/api/jobs/detail/{job_id}")
def job_detail(job_id: int, user: User = Depends(current_user),
               db: Session = Depends(get_db)):
    """One posting, in full, so it can be read without leaving the site.

    Free: a job board that will not show you the job is not a job board. The
    apply kit and the tailored prep are what cost.
    """
    j = db.get(Job, job_id)
    if j is None:
        raise HTTPException(404, "That posting is no longer listed")
    d = _job_json(j)
    # Falls back to the matching blob for rows crawled before the readable
    # copy existed — lowercase, but a lowercase description beats none.
    d["description"] = (j.description or "").strip() or (j.text or "")[:4000]
    d["skills"] = sorted(_job_skills(j))[:24]
    d["requirements"] = sorted(_job_req_skills(j))[:24]
    d["min_years"] = j.min_years or 0
    # Other places the same role is open, which is what the duplicates the
    # list collapses were actually telling us.
    d["also_at"] = [x[0] for x in db.query(Job.location).filter(
        func.lower(Job.title) == (j.title or "").lower(),
        func.lower(Job.company) == (j.company or "").lower(),
        Job.is_open == True,                                    # noqa: E712
        Job.id != j.id).distinct().limit(6).all() if x[0]]
    return d


@app.post("/api/jobs/match")
def jobs_match(body: JobMatchIn, user: User = Depends(current_user),
               db: Session = Depends(get_db)):
    """Rank open jobs against the user's resume.

    Deliberately AI-free: scoring runs in Python over the stored postings, so
    it is instant, costs nothing, and never touches the daily AI limit."""
    import math
    # Free, for everyone, permanently.
    #
    # The two strongest moments in this product — the ATS score and
    # "python: wanted by 6 roles you nearly match" — used to sit behind
    # the paywall, so nobody could see it was any good before paying.
    # Scoring is deterministic Python over stored rows: no AI call, no
    # third-party request, about two seconds of CPU. It costs little
    # enough to give away and it is the best argument for the paid
    # tier, which is the AI that acts on the result — apply kits,
    # tutoring, the tracker, the extension, alerts.
    #
    # Free accounts still match against the delayed, capped view of the
    # board (see FREE_JOB_DELAY_DAYS). You can see how you score; being
    # early is what Pro sells.
    rtext = (body.resume_text or "").strip() or _resume_text(body.resume or {})
    if len(rtext.strip()) < 40:
        raise HTTPException(400, "Add some resume details first, or upload a resume.")
    skills, keywords = _profile(rtext)
    if not skills:
        raise HTTPException(
            400, "We couldn't find recognisable skills in your resume. Add a "
                 "skills section (languages, tools, frameworks) and try again.")
    level = _level_of(rtext)
    my_fams = _resume_families(rtext)
    # The titles this person has actually held, plus their stated target role.
    # Matching title-to-title is what stops "shares a toolchain" being treated
    # as "does the same job".
    impact = _impact_score(rtext)
    my_years = _years_of(rtext)
    parsing = _parsing_score(rtext)
    my_titles = set()
    for e in (body.resume.get("exp") or [])[:6]:
        my_titles |= _title_words(str(e.get("role", "")))
    my_titles |= _title_words(str(body.resume.get("title", "")))
    if not my_titles:
        # Uploaded resumes have no structure, so take the strongest role words
        # from the first few lines, where a title almost always sits.
        my_titles = _title_words(" ".join(rtext.splitlines()[:6]))
    # The description is 27 MB across the board and matching does not read it
    # — scoring works from the skills columns. Deferring it was tried before
    # and made things worse, because rows stored without those columns then
    # lazy-loaded one at a time, thousands of times. So defer it AND fetch
    # what is genuinely still needed in a single extra query below: bounded,
    # and empty once the backfill has run.
    #
    # Whether that is a win depends entirely on how many rows still lack the
    # skills column: measured here, deferring with 56% of the board unfilled
    # was SLOWER (6.3s against 4.9s), because the text has to be fetched for
    # those rows regardless and the second query is pure overhead. So decide
    # from the data rather than guessing — one COUNT, cached for the process.
    global _DEFER_TEXT
    if _DEFER_TEXT is None:
        try:
            total = db.query(func.count(Job.id)).filter(
                Job.is_open == True).scalar() or 0          # noqa: E712
            bare = db.query(func.count(Job.id)).filter(
                Job.is_open == True,                        # noqa: E712
                or_(Job.skills == "", Job.skills.is_(None))).scalar() or 0
            _DEFER_TEXT = total > 0 and (bare / total) < 0.15
            print(f"jobs match: {bare}/{total} postings without parsed skills — "
                  f"{'deferring' if _DEFER_TEXT else 'loading'} descriptions")
        except Exception:
            _DEFER_TEXT = False

    q = _jobs_query(db, body.q, body.country, body.location, body.remote,
                    "open", body.category, body.job_type, body.engagement,
                    body.visa, body.posted)
    if _DEFER_TEXT:
        q = q.options(defer(Job.text))
    rows = q.order_by(
        case((Job.posted_at.isnot(None), Job.posted_at), else_=Job.first_seen).desc()
    ).limit(12000).all()

    need_text = [j for j in rows if _DEFER_TEXT and not (j.skills or "")]
    if need_text:
        texts = {}
        ids = [j.id for j in need_text]
        for i in range(0, len(ids), 900):        # SQLite caps parameters
            for jid, txt in db.query(Job.id, Job.text).filter(
                    Job.id.in_(ids[i:i + 900])).all():
                texts[jid] = txt or ""
        for j in need_text:
            t = texts.get(j.id, "")
            j._skills_memo = {w for w in _words(t) if w in _SKILLS}
            j._req_memo = {w for w in _words(_requirement_text(t)) if w in _SKILLS}

        # Keep it. This was computed into an attribute on a transient ORM
        # object and thrown away when the request ended, so every match
        # re-read and re-scanned several thousand descriptions — the whole
        # difference between two seconds and nine.
        #
        # Written separately from anything the caller sees, and wrapped: a
        # caching write must never be able to fail somebody's search. If it
        # does not commit, the result is exactly what it is today — right,
        # and slow again next time.
        try:
            for j in need_text:
                j.skills = ",".join(sorted(j._skills_memo))[:2000]
            db.commit()
            print(f"jobs match: parsed and stored skills for "
                  f"{len(need_text)} postings; later matches skip this")
        except Exception as e:
            db.rollback()
            print(f"jobs match: could not store parsed skills "
                  f"({type(e).__name__}) — matching is unaffected")

    # Rarity weights, measured on this very result set: a skill three quarters
    # of postings mention tells us almost nothing about fit.
    df, n = {}, max(len(rows), 1)
    parsed_now = []
    for j in rows:
        got = _job_skills(j)
        # Empty in the column means this was derived from the description
        # just now. _job_skills memoises it on the instance, which lasts one
        # request — so without this the same thousands of descriptions are
        # scanned again on the next match, and every match after that.
        if got and not (j.skills or ""):
            parsed_now.append(j)
        for s in got:
            df[s] = df.get(s, 0) + 1

    if parsed_now:
        try:
            for j in parsed_now:
                j.skills = ",".join(sorted(_job_skills(j)))[:2000]
            db.commit()
            print(f"jobs match: stored parsed skills for {len(parsed_now)} "
                  f"postings; later matches will not reparse them")
        except Exception as e:
            db.rollback()
            print(f"jobs match: could not store parsed skills "
                  f"({type(e).__name__}) — results are unaffected")
    # Floored for the same reason as the alert sweep: a weight below zero
    # would make a matched skill count against the job.
    idf = {s: max(0.05, math.log(n / (1 + c)) + 0.25) for s, c in df.items()}

    # One role open in three cities is three postings. Show it once, keeping
    # the best-scoring copy and listing the other places it is open.
    best = {}
    for j in rows:
        score, hit, miss, why = _score_job(j, skills, keywords, level, idf,
                                           my_fams, my_titles, impact, parsing,
                                           my_years=my_years)
        key = ((j.title or "").strip().lower(), (j.company or "").strip().lower())
        item = _job_json(j, {"score": score, "matched": hit, "missing": miss,
                             "why": why, **match_tier(score)})
        prev = best.get(key)
        if prev is None or score > prev["score"]:
            item["also_in"] = prev["also_in"] + [prev["location"]] if prev else []
            best[key] = item
        elif j.location and j.location not in prev["also_in"]:
            prev["also_in"].append(j.location)
    scored = sorted(best.values(), key=lambda d: -d["score"])
    for it in scored:
        it["also_in"] = [x for x in it["also_in"] if x and x != it["location"]][:4]
    if body.min_score > 0:
        scored = [d for d in scored if d["score"] >= body.min_score]

    # The gaps, added up. One posting's missing list tells you what one
    # employer wanted; the same skill across four hundred of them tells you
    # what to study on Sunday. Counted over the roles that are actually a
    # near miss — the ones worth closing a gap for — rather than the whole
    # board, where a gap on a job you would never get is not a gap.
    near = [d for d in scored if d["score"] >= 45][:400]
    gap_n, gap_best = {}, {}
    for d in near:
        for s in d.get("missing") or []:
            gap_n[s] = gap_n.get(s, 0) + 1
            if d["score"] > gap_best.get(s, 0):
                gap_best[s] = d["score"]
    top_gaps = [{"skill": s, "jobs": c, "best_score": gap_best.get(s, 0)}
                for s, c in sorted(gap_n.items(), key=lambda x: -x[1])[:14]]

    # No more than a few roles from any one employer near the top. One company
    # with 400 open jobs would otherwise fill the entire first page, which is
    # what made results look like "mostly the same company".
    per_company, spread, overflow = {}, [], []
    for d in scored:
        c = (d.get("company") or "").lower()
        per_company[c] = per_company.get(c, 0) + 1
        (spread if per_company[c] <= JOBS_PER_COMPANY else overflow).append(d)
    scored = spread + overflow

    off = max(body.offset, 0)
    lim = min(max(body.limit, 1), 50)
    page = scored[off:off + lim]
    _mark_tracked(db, user, page)
    # One request, not one page: allowing off>0 through after the allowance is
    # spent would be unlimited matching behind a query parameter. The free go
    # returns a full page of ranked jobs, which is the thing worth seeing.
    _trial_consume(db, user, "match")
    return {"jobs": page, "scanned": len(rows), "total": len(scored),
            "top_gaps": top_gaps,
            # What the score is made of, so a user can see why it moved.
            "scoring": {
                "weights": {"hard_skills": 33, "role_and_seniority": 27,
                            "impact_evidence": 17, "domain": 15, "readability": 8},
                "your_impact_score": round(impact * 100),
                "your_readability_score": round(parsing * 100),
                # Kept in step with match_tier — these were still quoting the
                # old 85/70/55 bands after the scoring was rebalanced.
                "tiers": {"S": "72-100 exceptional", "A": "60-71 strong",
                          "B": "45-59 worth applying", "C": "below 45 weak"},
            },
            # skills goes in so the score can be measured from the document
            # rather than from whatever the filters happened to leave behind;
            # the label names the pool the coverage figure is about, so the
            # one number that does move says what it moved with.
            "ats": _ats_view(rtext, scored, impact, parsing, skills,
                             _posted_label(body.posted)),
            "offset": off, "limit": lim, "has_more": off + lim < len(scored),
            "level": level, "families": sorted(my_fams),
            "your_skills": sorted(s for s in skills if s not in _WEAK_SKILLS)[:30]}


class TrackIn2(BaseModel):
    job_id: int
    status: str = Field(default="saved", max_length=20)
    note: str = Field(default="", max_length=2000)


def _track_json(t):
    return {"id": t.id, "job_id": t.job_id, "status": t.status,
            "title": t.title, "company": t.company, "location": t.location,
            "url": t.url, "score": t.score or 0, "note": t.note or "",
            "applied_at": t.applied_at.isoformat() if t.applied_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None}


@app.post("/api/jobs/track")
def job_track(body: TrackIn2, user: User = Depends(current_user),
              db: Session = Depends(get_db)):
    """Save a job, or move it along the pipeline. One row per user per job."""
    status = (body.status or "saved").strip().lower()
    if status not in TRACK_STATUSES:
        raise HTTPException(400, f"Unknown status. Use one of: {', '.join(TRACK_STATUSES)}")
    # Recording an application is the one tracker action a free account gets,
    # so someone can go through a real application end to end before paying.
    if status == "applied":
        apply_gate(db, user, body.job_id)
    else:
        require_paid(user, "The application tracker")
    row = db.query(JobTrack).filter(JobTrack.user_id == user.id,
                                    JobTrack.job_id == body.job_id).first()
    if not row:
        job = db.get(Job, body.job_id)
        if not job:
            raise HTTPException(404, "That job is no longer listed")
        # Copy the details in — the posting may be pruned later, but the user's
        # record of having applied to it should outlive the listing.
        row = JobTrack(user_id=user.id, job_id=job.id, title=job.title,
                       company=job.company, location=job.location, url=job.url)
        db.add(row)
    row.status = status
    if body.note:
        row.note = body.note
    if status == "applied" and not row.applied_at:
        row.applied_at = now()
    db.commit()
    db.refresh(row)
    return {"ok": True, "track": _track_json(row)}


# ---------------------------- hiring side ---------------------------------
# Employers search candidates by pasting a job description. Two rules shape
# everything here:
#   1. Nobody appears unless they switched it on. Consent is explicit.
#   2. Results are anonymous. Skills, seniority, location and a match score —
#      never a name, email or phone. An employer asks for an introduction and
#      the candidate decides. That protects the user and is worth more to the
#      employer than a list they could have scraped.

def employer_user(user: User = Depends(current_user)) -> User:
    """Whoever may search candidates: an approved employer, or an admin.

    Deliberately separate from admin_user — an employer must never inherit
    admin powers just because both can reach the hiring endpoints.
    """
    if getattr(user, "is_admin", False):
        return user
    if (getattr(user, "employer_status", "") or "") == "approved":
        return user
    raise HTTPException(403, "Employer access is needed for this. Apply from "
                             "your account and we will review it.")


def open_to_work_on(u) -> bool:
    return bool(getattr(u, "open_to_work", False))


class HireSearchIn(BaseModel):
    jd: str = Field(min_length=40, max_length=20000)
    engagement: str = Field(default="", max_length=20)   # c2c / w2 / 1099
    limit: int = 25


def _candidate_score(jd_skills, jd_fams, jd_level, r_skills, r_fams, r_level):
    """How well one resume answers a job description.

    Deliberately the mirror of _score_job so a candidate and an employer see
    the same number for the same pair — a match that reads 80% to the employer
    must not read 60% to the candidate.
    """
    if not jd_skills:
        return 0
    hit = jd_skills & r_skills
    skill = len(hit) / max(len(jd_skills), 1)
    fam = 1.0 if (jd_fams & r_fams) else (0.35 if not jd_fams else 0.0)
    order = ["junior", "mid", "senior", "lead"]
    try:
        gap = abs(order.index(r_level) - order.index(jd_level))
        lvl = {0: 1.0, 1: 0.7}.get(gap, 0.4)
    except ValueError:
        lvl = 0.7
    return round(100 * (0.60 * skill + 0.28 * fam + 0.12 * lvl))


@app.post("/api/hire/search")
def hire_search(body: HireSearchIn, user: User = Depends(employer_user),
                db: Session = Depends(get_db)):
    """Rank opted-in candidates against a job description.

    Admin-only for now: employer accounts and billing are the next step, and
    an unauthenticated version of this would be a candidate-data leak.
    """
    jd = body.jd.strip()
    jd_skills, _kw = _profile(jd)
    if not jd_skills:
        raise HTTPException(400, "No recognisable skills in that job "
                                 "description — add the tools and technologies.")
    jd_fams, jd_level = _families(jd), _level_of(jd)
    want = (body.engagement or "").strip().lower()

    out = []
    for u in db.query(User).filter(User.open_to_work == True).all():   # noqa: E712
        note = db.query(Note).filter(Note.user_id == u.id,
                                     Note.k == "resume_uptext").first()
        rtext = (note.v if note else "") or ""
        if len(rtext.strip()) < 120:
            continue           # no resume on file — nothing to match against
        r_skills, _ = _profile(rtext)
        if not r_skills:
            continue
        score = _candidate_score(jd_skills, jd_fams, jd_level,
                                 r_skills, _families(rtext), _level_of(rtext))
        if score < 40:
            continue
        pref = db.query(Note).filter(Note.user_id == u.id,
                                     Note.k == "work_engagement").first()
        their = (pref.v if pref else "").strip().lower()
        if want and their and want != their:
            continue
        out.append({
            # An opaque handle, not the user id: an employer must not be able
            # to enumerate accounts or correlate one across searches.
            "ref": _licence_ref(u.id),
            "score": score,
            "matched_skills": sorted(jd_skills & r_skills)[:12],
            "missing_skills": sorted(jd_skills - r_skills)[:8],
            "level": _level_of(rtext),
            "families": sorted(_families(rtext))[:3],
            "engagement": their,
            "open_since": _aware(u.open_to_work_at).date().isoformat()
                          if u.open_to_work_at else None,
        })
    out.sort(key=lambda x: -x["score"])
    return {"candidates": out[:max(1, min(body.limit, 100))],
            "total": len(out),
            "jd_skills": sorted(jd_skills)[:20],
            "note": "Anonymous by design. Request an introduction and the "
                    "candidate chooses whether to share their details."}


class EmployerJobIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    company: str = Field(default="", max_length=200)
    location: str = Field(default="", max_length=200)
    engagement: str = Field(default="", max_length=20)
    jd: str = Field(min_length=40, max_length=20000)
    invite_above: int = 60


def _match_candidates(db, jd, engagement=""):
    """Every opted-in candidate scored against a JD, best first."""
    jd_skills, _ = _profile(jd)
    if not jd_skills:
        return None, []
    jd_fams, jd_level = _families(jd), _level_of(jd)
    want = (engagement or "").strip().lower()
    out = []
    for u in db.query(User).filter(User.open_to_work == True).all():   # noqa: E712
        note = db.query(Note).filter(Note.user_id == u.id,
                                     Note.k == "resume_uptext").first()
        rtext = (note.v if note else "") or ""
        if len(rtext.strip()) < 120:
            continue
        r_skills, _ = _profile(rtext)
        if not r_skills:
            continue
        pref = db.query(Note).filter(Note.user_id == u.id,
                                     Note.k == "work_engagement").first()
        their = (pref.v if pref else "").strip().lower()
        if want and their and want != their:
            continue
        out.append((u, _candidate_score(jd_skills, jd_fams, jd_level, r_skills,
                                        _families(rtext), _level_of(rtext)),
                    sorted(jd_skills & r_skills), sorted(jd_skills - r_skills),
                    _level_of(rtext), their))
    out.sort(key=lambda x: -x[1])
    return jd_skills, out


@app.post("/api/hire/jobs")
def hire_create_job(body: EmployerJobIn, user: User = Depends(employer_user),
                    db: Session = Depends(get_db)):
    """Post a role and invite the candidates who match it.

    Invites go out only when the job description is saved — that is the point
    at which the employer has said what they actually want. Pinging people
    before that would mean interrupting them on behalf of a blank form.
    """
    job = EmployerJob(owner_id=user.id, title=body.title.strip(),
                      company=body.company.strip(), location=body.location.strip(),
                      engagement=(body.engagement or "").strip().lower(),
                      jd=body.jd.strip())
    db.add(job)
    db.commit()
    db.refresh(job)

    jd_skills, matches = _match_candidates(db, job.jd, job.engagement)
    if jd_skills is None:
        db.delete(job)
        db.commit()
        raise HTTPException(400, "No recognisable skills in that job "
                                 "description — add the tools and technologies.")
    floor = max(0, min(int(body.invite_above), 100))
    sent = 0
    for u, score, hit, miss, lvl, eng in matches:
        if score < floor:
            continue
        # One invite per candidate per role, enforced in the database too. An
        # employer editing a JD must not be able to ping the same person twice.
        if db.query(JobInvite).filter(JobInvite.employer_job_id == job.id,
                                      JobInvite.user_id == u.id).first():
            continue
        db.add(JobInvite(employer_job_id=job.id, user_id=u.id, score=score))
        db.add(JobAlert(user_id=u.id, kind="invite", icon="💼",
                        text=f"{job.company or 'An employer'} is hiring a "
                             f"{job.title} — you match {score}%.",
                        url="/#invites"))
        sent += 1
    db.commit()
    return {"job_id": job.id, "invited": sent, "matched": len(matches),
            "jd_skills": sorted(jd_skills)[:20],
            "message": f"{sent} candidate(s) invited. They see the role and "
                       f"their match score; you see them only if they accept."}


@app.get("/api/hire/jobs/{job_id}/candidates")
def hire_job_candidates(job_id: int, user: User = Depends(employer_user),
                        db: Session = Depends(get_db)):
    """Who was invited, and who said yes. Contact details appear only for
    candidates who accepted — that is the whole bargain."""
    job = db.get(EmployerJob, job_id)
    if not job or job.owner_id != user.id:
        raise HTTPException(404, "No such role")
    out = []
    for inv in db.query(JobInvite).filter(
            JobInvite.employer_job_id == job.id).order_by(
            JobInvite.score.desc()).all():
        u = db.get(User, inv.user_id)
        if not u:
            continue
        row = {"ref": hashlib.sha256(f"cand{u.id}{JWT_SECRET}".encode()).hexdigest()[:16],
               # The employer needs the invite id to open the conversation.
               # Harmless on its own: every endpoint that takes it re-checks
               # that the caller owns the job.
               "invite_id": inv.id,
               "score": inv.score, "state": inv.state,
               "invited_at": _aware(inv.created_at).isoformat() if inv.created_at else None}
        if inv.state == "accepted":
            row.update({"name": u.name, "email": u.email})
        out.append(row)
    return {"job": {"id": job.id, "title": job.title, "company": job.company,
                    "engagement": job.engagement, "is_open": job.is_open},
            "candidates": out,
            "accepted": sum(1 for x in out if x["state"] == "accepted"),
            "invited": len(out)}


@app.get("/api/me/invites")
def my_invites(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Roles an employer has invited this candidate to, with the match score."""
    out = []
    for inv in db.query(JobInvite).filter(JobInvite.user_id == user.id).order_by(
            JobInvite.created_at.desc()).limit(100).all():
        job = db.get(EmployerJob, inv.employer_job_id)
        if not job:
            continue
        out.append({"id": inv.id, "score": inv.score, "state": inv.state,
                    "title": job.title, "company": job.company,
                    "location": job.location, "engagement": job.engagement,
                    "jd": job.jd[:1500],
                    "when": _aware(inv.created_at).isoformat() if inv.created_at else None})
    return {"invites": out, "pending": sum(1 for x in out if x["state"] == "sent")}


class InviteAnswerIn(BaseModel):
    accept: bool


@app.post("/api/me/invites/{invite_id}")
def answer_invite(invite_id: int, body: InviteAnswerIn,
                  user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Accept or decline. Accepting is what releases your name and email to
    that employer, and nothing else does."""
    inv = db.get(JobInvite, invite_id)
    if not inv or inv.user_id != user.id:
        raise HTTPException(404, "No such invitation")
    if inv.state != "sent":
        raise HTTPException(400, "You have already answered this one.")
    inv.state = "accepted" if body.accept else "declined"
    inv.answered_at = now()
    db.commit()
    return {"ok": True, "state": inv.state,
            "message": "Your name and email have been shared with this "
                       "employer for this role only."
                       if body.accept else
                       "Declined. The employer is not told who declined."}


def _invite_parties(db, invite_id, user):
    """Resolve an invite and check this user is one of its two sides.

    Returns (invite, job, is_employer). Anyone else gets a 404 rather than a
    403 — a stranger should not be able to learn that an invitation exists.
    """
    inv = db.get(JobInvite, invite_id)
    if not inv:
        raise HTTPException(404, "No such conversation")
    job = db.get(EmployerJob, inv.employer_job_id)
    if not job:
        raise HTTPException(404, "No such conversation")
    if inv.user_id == user.id:
        return inv, job, False
    if job.owner_id == user.id or getattr(user, "is_admin", False):
        return inv, job, True
    raise HTTPException(404, "No such conversation")


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


@app.get("/api/invites/{invite_id}/messages")
def invite_messages(invite_id: int, user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    inv, job, is_emp = _invite_parties(db, invite_id, user)
    if inv.state != "accepted":
        raise HTTPException(403, "This conversation opens once the candidate "
                                 "accepts the invitation.")
    rows = db.query(InviteMessage).filter(
        InviteMessage.invite_id == inv.id).order_by(InviteMessage.created_at).all()
    # Mark the other side's messages read for whoever is looking.
    for m in rows:
        if m.from_employer != is_emp and not m.seen:
            m.seen = True
    db.commit()
    files = {f.filename: f for f in db.query(InviteFile).filter(
        InviteFile.invite_id == inv.id).all()}
    who = db.get(User, inv.user_id)
    return {"invite_id": inv.id,
            "job": {"title": job.title, "company": job.company},
            "with": (job.company or "The employer") if not is_emp
                    else (who.name if who else "Candidate"),
            "messages": [{"id": m.id, "mine": m.from_employer == is_emp,
                          "kind": m.kind or "text", "body": m.body,
                          "file_id": (files[m.body].id
                                      if m.kind == "file" and m.body in files else None),
                          "size": (files[m.body].size
                                   if m.kind == "file" and m.body in files else None),
                          "when": _aware(m.created_at).isoformat()} for m in rows]}


@app.post("/api/invites/{invite_id}/messages")
def invite_send(invite_id: int, body: MessageIn,
                user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Send one message. Only after acceptance, and only to the other side."""
    inv, job, is_emp = _invite_parties(db, invite_id, user)
    if inv.state != "accepted":
        raise HTTPException(403, "You can message once the invitation is accepted.")
    msg = InviteMessage(invite_id=inv.id, from_employer=is_emp,
                        body=body.body.strip()[:4000])
    db.add(msg)

    # Notify the OTHER side, in the bell they already watch. Without this a
    # reply sits unread and the conversation dies after one message.
    if is_emp:
        db.add(JobAlert(user_id=inv.user_id, kind="invite_msg", icon="💬",
                        text=f"{job.company or 'An employer'} replied about "
                             f"{job.title}.",
                        url="/#invites"))
    db.commit()
    db.refresh(msg)
    return {"ok": True, "id": msg.id,
            "when": _aware(msg.created_at).isoformat()}


@app.post("/api/invites/{invite_id}/resume")
def invite_send_resume(invite_id: int, user: User = Depends(current_user),
                       db: Session = Depends(get_db)):
    """Send your resume into an accepted conversation.

    Candidate-only, and it sends the resume already on file rather than taking
    an upload: the text is what the employer needs, and accepting a file here
    would mean storing and serving arbitrary uploads to another user.
    """
    inv, job, is_emp = _invite_parties(db, invite_id, user)
    if is_emp:
        raise HTTPException(403, "Only the candidate can send a resume.")
    if inv.state != "accepted":
        raise HTTPException(403, "Accept the invitation first.")
    note = db.query(Note).filter(Note.user_id == user.id,
                                 Note.k == "resume_uptext").first()
    text = ((note.v if note else "") or "").strip()
    if len(text) < 120:
        raise HTTPException(400, "Upload a resume on the Careers page first.")
    db.add(InviteMessage(invite_id=inv.id, from_employer=False, kind="resume",
                         body=text[:20000]))
    db.commit()
    return {"ok": True, "message": "Resume sent."}


# Only these two, and only when the bytes agree with the extension. Anything
# a browser might render — SVG, HTML, XML — is refused outright: serving one of
# those back from our own domain is stored XSS against whoever opens it.
ATTACH_MAX = 4_000_000
ATTACH_TYPES = {
    "pdf":  (b"%PDF", "application/pdf"),
    "docx": (b"PK",
             "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
}


@app.post("/api/invites/{invite_id}/files")
async def invite_upload(invite_id: int, file: UploadFile = File(...),
                        user: User = Depends(current_user),
                        db: Session = Depends(get_db)):
    """Attach a PDF or DOCX to an accepted conversation."""
    inv, job, is_emp = _invite_parties(db, invite_id, user)
    if inv.state != "accepted":
        raise HTTPException(403, "You can share files once the invitation is accepted.")

    name = (file.filename or "file")[:200]
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ATTACH_TYPES:
        raise HTTPException(400, "Only PDF and DOCX files can be shared.")
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "That file is empty.")
    if len(raw) > ATTACH_MAX:
        raise HTTPException(400, "File too large (max 4 MB)")
    # The extension is a claim; the first bytes are evidence. Both must agree,
    # so "resume.pdf" containing HTML is refused rather than stored.
    magic, _mime = ATTACH_TYPES[ext]
    if not raw.startswith(magic):
        raise HTTPException(400, "That file does not look like a real "
                                 f"{ext.upper()}. Re-export it and try again.")

    row = InviteFile(invite_id=inv.id, from_employer=is_emp, filename=name,
                     kind=ext, size=len(raw),
                     data=base64.b64encode(raw).decode())
    db.add(row)
    db.add(InviteMessage(invite_id=inv.id, from_employer=is_emp, kind="file",
                         body=name))
    if is_emp:
        db.add(JobAlert(user_id=inv.user_id, kind="invite_msg", icon="📎",
                        text=f"{job.company or 'An employer'} sent a file about "
                             f"{job.title}.", url="/#invites"))
    db.commit()
    db.refresh(row)
    return {"ok": True, "id": row.id, "filename": row.filename, "size": row.size}


@app.get("/api/invites/{invite_id}/files/{file_id}")
def invite_download(invite_id: int, file_id: int,
                    user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    """Download an attachment. Both parties, nobody else."""
    inv, _job, _is_emp = _invite_parties(db, invite_id, user)
    row = db.get(InviteFile, file_id)
    if not row or row.invite_id != inv.id:
        raise HTTPException(404, "No such file")
    _magic, mime = ATTACH_TYPES.get(row.kind or "pdf", ATTACH_TYPES["pdf"])
    # Always as an attachment, always our own content type — never the one the
    # uploader claimed, and never inline. An inline render of user-supplied
    # bytes on our own origin is the whole risk here.
    safe = _re.sub(r'[^A-Za-z0-9._ -]', "_", row.filename or "file")[:120]
    return RawResponse(
        content=base64.b64decode(row.data or ""),
        media_type=mime,
        headers={"Content-Disposition": f'attachment; filename="{safe}"',
                 "X-Content-Type-Options": "nosniff",
                 "Content-Security-Policy": "default-src 'none'"})


@app.get("/api/invites/unread")
def invites_unread(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Unread count across every conversation this user is part of."""
    mine = {i.id: False for i in
            db.query(JobInvite).filter(JobInvite.user_id == user.id,
                                       JobInvite.state == "accepted").all()}
    for j in db.query(EmployerJob).filter(EmployerJob.owner_id == user.id).all():
        for i in db.query(JobInvite).filter(JobInvite.employer_job_id == j.id,
                                            JobInvite.state == "accepted").all():
            mine[i.id] = True
    if not mine:
        return {"unread": 0}
    n = 0
    for iid, is_emp in mine.items():
        n += db.query(func.count(InviteMessage.id)).filter(
            InviteMessage.invite_id == iid,
            InviteMessage.from_employer != is_emp,
            InviteMessage.seen == False).scalar() or 0   # noqa: E712
    return {"unread": n}


class EmployerApplyIn(BaseModel):
    company: str = Field(min_length=2, max_length=200)
    site: str = Field(default="", max_length=300)


@app.post("/api/employer/apply")
def employer_apply(body: EmployerApplyIn, user: User = Depends(current_user),
                   db: Session = Depends(get_db)):
    """Ask for employer access. Approval is manual and that is the point."""
    u = db.get(User, user.id)
    if (u.employer_status or "") == "approved":
        return {"ok": True, "status": "approved",
                "message": "You already have employer access."}
    u.employer_status = "pending"
    u.employer_company = body.company.strip()
    u.employer_site = body.site.strip()
    db.commit()
    return {"ok": True, "status": "pending",
            "message": "Thanks — we review every employer by hand before "
                       "granting access to candidate profiles. We will email "
                       "you when it is done."}


@app.get("/api/employer/me")
def employer_me(user: User = Depends(current_user)):
    return {"status": ("approved" if getattr(user, "is_admin", False)
                       else (user.employer_status or "")),
            "company": user.employer_company or "",
            "site": user.employer_site or ""}


@app.get("/api/admin/employers")
def admin_employers(user: User = Depends(admin_user), db: Session = Depends(get_db)):
    rows = db.query(User).filter(User.employer_status.in_(("pending", "approved"))).all()
    return {"employers": [{"id": u.id, "name": u.name, "email": u.email,
                           "company": u.employer_company or "",
                           "site": u.employer_site or "",
                           "status": u.employer_status or ""} for u in rows]}


class EmployerDecideIn(BaseModel):
    approve: bool


@app.post("/api/admin/employers/{user_id}")
def admin_decide_employer(user_id: int, body: EmployerDecideIn,
                          user: User = Depends(admin_user),
                          db: Session = Depends(get_db)):
    """Approve or refuse employer access. Refusing clears it entirely rather
    than leaving a rejected flag around, so re-applying is possible."""
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "No such user")
    u.employer_status = "approved" if body.approve else ""
    db.commit()
    return {"ok": True, "status": u.employer_status or "none"}


class OpenToWorkIn(BaseModel):
    on: bool
    engagement: str = Field(default="", max_length=20)


@app.post("/api/me/open-to-work")
def set_open_to_work(body: OpenToWorkIn, user: User = Depends(current_user),
                     db: Session = Depends(get_db)):
    """Opt in or out of being found by employers. Off until chosen."""
    u = db.get(User, user.id)
    u.open_to_work = bool(body.on)
    u.open_to_work_at = now() if body.on else None
    if body.engagement:
        row = db.query(Note).filter(Note.user_id == u.id,
                                    Note.k == "work_engagement").first()
        if row is None:
            row = Note(user_id=u.id, k="work_engagement", v="")
            db.add(row)
        row.v = body.engagement.strip().lower()[:20]
    db.commit()
    return {"ok": True, "open_to_work": bool(u.open_to_work),
            "message": "Employers matching your resume can now find you — "
                       "anonymously, until you accept an introduction."
                       if body.on else
                       "You are hidden from employer searches."}


@app.get("/api/jobs/tracked")
def jobs_tracked(status: str = "", user: User = Depends(current_user),
                 db: Session = Depends(get_db)):
    """Everything the user saved or applied to, plus a count per stage."""
    q = db.query(JobTrack).filter(JobTrack.user_id == user.id)
    if status:
        q = q.filter(JobTrack.status == status.strip().lower())
    rows = q.order_by(JobTrack.updated_at.desc()).limit(500).all()
    counts = dict(db.query(JobTrack.status, func.count(JobTrack.id))
                  .filter(JobTrack.user_id == user.id)
                  .group_by(JobTrack.status).all())
    return {"tracks": [_track_json(t) for t in rows],
            "counts": {s: counts.get(s, 0) for s in TRACK_STATUSES},
            "total": sum(counts.values()),
            "statuses": [{"id": s, "label": TRACK_LABELS[s]} for s in TRACK_STATUSES]}


@app.delete("/api/jobs/tracked")
def jobs_untrack_many(status: str = "", user: User = Depends(current_user),
                      db: Session = Depends(get_db)):
    """Clear one stage, or the whole tracker when no status is given."""
    q = db.query(JobTrack).filter(JobTrack.user_id == user.id)
    st = (status or "").strip().lower()
    if st:
        if st not in TRACK_STATUSES:
            raise HTTPException(400, "Unknown status")
        q = q.filter(JobTrack.status == st)
    removed = q.delete(synchronize_session=False)
    db.commit()
    return {"ok": True, "removed": removed, "status": st or "all"}


@app.delete("/api/jobs/track/{job_id}")
def job_untrack(job_id: int, user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    """Remove a job from the tracker entirely."""
    row = db.query(JobTrack).filter(JobTrack.user_id == user.id,
                                    JobTrack.job_id == job_id).first()
    if row:
        db.delete(row)
        db.commit()
    return {"ok": True}


# ---- browser extension: one-time pairing, then everything stays local ------
# The extension never receives a session cookie. The site mints a short-lived
# single-use code, the extension trades it once for the profile, and stores it
# in the browser. That way a compromised extension cannot act as the user, and
# the resume never travels on later form fills.
_PAIR_CODES = {}                      # code -> (user_id, expires_at)
PAIR_TTL = dt.timedelta(minutes=10)


def _prune_pair_codes():
    t = now()
    for c in [c for c, (_, exp) in _PAIR_CODES.items() if exp < t]:
        _PAIR_CODES.pop(c, None)


@app.post("/api/apply/pair-code")
def apply_pair_code(user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    """Mint a pairing code to type into the extension. Expires in 10 minutes.

    Minting is free while the trial autofill is unspent, and deliberately does
    not consume it: a code expires after 10 minutes, and burning someone's one
    free autofill because they were slow typing it in would be indefensible.
    The allowance is spent in apply_profile, when data is actually handed over.
    """
    require_paid_or_trial(db, user, "extension", "The browser extension",
                          spent="one free autofill")
    _prune_pair_codes()
    code = "-".join(secrets.token_hex(2).upper() for _ in range(3))
    _PAIR_CODES[code] = (user.id, now() + PAIR_TTL)
    return {"code": code, "expires_in": int(PAIR_TTL.total_seconds())}


def _licence_ref(uid: int) -> str:
    """A stable, non-reversible reference for one account.

    The same construction the hiring side already uses for candidate refs:
    a salted hash, sixteen characters, useless to anyone who intercepts it.
    Defined once here so the extension and the employer view cannot drift.
    """
    return hashlib.sha256(f"cand{uid}{JWT_SECRET}".encode()).hexdigest()[:16]


@app.get("/api/apply/licence")
def apply_licence(ref: str = "", db: Session = Depends(get_db)):
    """Is this paired extension still entitled to autofill?

    The extension pairs once and then works offline, which is right for
    privacy — the resume never travels again — but it also meant a lapsed
    subscriber kept autofill forever. This is the smallest thing that closes
    that: a reference the extension already holds, in, a yes or no out.

    Deliberately NOT authenticated and deliberately returns no personal data.
    The reference is the salted hash we already use for candidate refs, so a
    stolen one reveals nothing and cannot be turned into a session. A missing
    or unknown reference answers "no" without saying which.
    """
    ref = (ref or "").strip()
    if not ref:
        return {"ok": False}
    for u in db.query(User).filter(User.is_active == True).all():   # noqa: E712
        if _licence_ref(u.id) == ref:
            return {"ok": plan_of(u) != "free"}
    return {"ok": False}


@app.get("/api/apply/profile")
def apply_profile(code: str = "", db: Session = Depends(get_db)):
    """Trade a pairing code for the autofill profile. Single use.

    Returns only what a job application form actually asks for. No password,
    no session, nothing that would let the caller act as the user.
    """
    _prune_pair_codes()
    entry = _PAIR_CODES.pop((code or "").strip().upper(), None)
    if not entry:
        raise HTTPException(401, "That code is wrong or has expired. Generate a new one.")
    user = db.get(User, entry[0])
    if not user:
        raise HTTPException(401, "Account not found")
    # Re-checked here, not just at pairing: this is where the profile actually
    # leaves the server, and the code may have been minted before the allowance
    # ran out.
    require_paid_or_trial(db, user, "extension", "The browser extension",
                          spent="one free autofill")
    _trial_consume(db, user, "extension")

    raw = db.query(Note).filter(Note.user_id == user.id,
                                Note.k == "resume_data").first()
    try:
        r = json.loads(raw.v) if raw and raw.v else {}
    except Exception:
        r = {}
    links = str(r.get("links") or "")

    def find(*keys):
        for k in keys:
            m = _re.search(rf"https?://\S*{k}\S*", links, _re.I)
            if m:
                return m.group(0).rstrip(".,;")
        return ""

    # The extension keeps this and asks /api/apply/licence with it every few
    # days. It is a salted hash of the user id, not the id: it identifies the
    # licence without identifying the person, and it cannot be used to log in.
    ref = _licence_ref(user.id)
    exp = (r.get("exp") or [{}])[0] if r.get("exp") else {}
    edu = (r.get("edu") or [{}])[0] if r.get("edu") else {}
    full = str(r.get("name") or user.name or "").strip()
    first, _, last = full.partition(" ")
    return {
        "licence_ref": ref,
        "first_name": first, "last_name": last.strip(), "full_name": full,
        # Blank on purpose: a resume rarely carries these, and the person
        # fills them once in the extension rather than on every form.
        "middle_name": "", "preferred_first_name": "",
        "preferred_middle_name": "", "preferred_last_name": "",
        "phone_country_code": "",
        "email": str(r.get("email") or user.email or ""),
        "phone": str(r.get("phone") or ""),
        "location": str(r.get("location") or user.city or ""),
        "linkedin": find("linkedin"), "github": find("github"),
        "portfolio": find("portfolio", "vercel", "netlify", "\\.dev", "\\.me"),
        "current_title": str(exp.get("role") or r.get("title") or ""),
        "current_company": str(exp.get("company") or ""),
        "school": str(edu.get("school") or user.college or ""),
        "degree": str(edu.get("degree") or user.degree or ""),
        "field_of_study": str(edu.get("degree") or ""),
        "grad_year": str(edu.get("year") or ""),
        "summary": str(r.get("summary") or "")[:1200],
        # Fields a resume rarely carries but application forms almost always
        # ask for. Blank here on purpose — the person fills them in the
        # extension once and they are reused on every form after that.
        "address": "", "city": str(user.city or ""), "state": "",
        "postcode": "", "country": "",
        "years_experience": "", "notice_period": "", "desired_salary": "",
        "work_authorized": "", "needs_sponsorship": "",
        "willing_to_relocate": "", "how_heard": "",
        "synced_at": now().isoformat(),
    }


# ---- interview preparation ------------------------------------------------
# Written per role family rather than generated, so it costs nothing, is the
# same for everyone, and cannot invent a stage that does not exist. The AI
# layer on top tailors it to one specific posting when asked.
INTERVIEW_GUIDES = {
    "network": {
        "stages": ["Recruiter screen", "Technical phone screen",
                   "Hands-on / lab or troubleshooting", "Design & scenarios",
                   "Manager and team fit"],
        "topics": ["OSI layers and what actually breaks at each",
                   "TCP handshake, MTU, MSS, fragmentation",
                   "BGP path selection and route filtering",
                   "OSPF areas, LSA types, convergence",
                   "VLANs, STP, trunking, port-channels",
                   "NAT, ACLs, firewall rule order",
                   "Load balancing: L4 vs L7, health checks, persistence",
                   "DNS and DHCP failure modes",
                   "Packet capture: reading a trace and proving where loss is"],
        "questions": [
            "Walk me through what happens when a user says 'the site is slow'.",
            "A BGP session is flapping. How do you find out why?",
            "How do you decide between OSPF and BGP inside a data centre?",
            "Describe a change you made that caused an outage. What did you change afterwards?",
            "How would you migrate a core switch pair with minimal downtime?"],
        "do": ["Bring a real topology you designed or fixed, and be ready to draw it",
               "Know your own incident stories cold: symptom, diagnosis, fix, prevention",
               "Practise reading a packet capture out loud"],
    },
    "backend": {
        "stages": ["Recruiter screen", "Coding screen (DSA or practical)",
                   "System design", "Code review / take-home discussion",
                   "Manager and values"],
        "topics": ["Data structures and complexity you can actually justify",
                   "SQL: joins, indexes, query plans, N+1",
                   "Caching layers and invalidation",
                   "Concurrency, idempotency, retries",
                   "API design, versioning, pagination",
                   "Queues and event-driven flow",
                   "Observability: logs, metrics, traces",
                   "Testing strategy and what you choose not to test"],
        "questions": [
            "Design a URL shortener that survives 100x growth.",
            "How would you make this endpoint idempotent?",
            "A query got slow overnight. Walk me through diagnosis.",
            "When would you not use a microservice?",
            "Tell me about a piece of code you regret writing."],
        "do": ["Practise talking while coding — silence reads as being stuck",
               "Have one project you can discuss to arbitrary depth",
               "Ask what the on-call rotation is really like"],
    },
    "data": {
        "stages": ["Recruiter screen", "SQL screen", "Data modelling / pipeline design",
                   "Case study or take-home", "Stakeholder and team fit"],
        "topics": ["Window functions, CTEs, and query tuning",
                   "Star vs snowflake schemas, slowly changing dimensions",
                   "Batch vs streaming, and when each is wrong",
                   "Orchestration, retries, backfills, idempotency",
                   "Data quality tests and freshness SLAs",
                   "Partitioning, clustering, file formats"],
        "questions": [
            "Write a query for month-over-month growth per customer.",
            "A dashboard number changed and nobody knows why. What do you do?",
            "How do you backfill two years of data without breaking production?",
            "How do you decide what to model in the warehouse versus in the BI tool?"],
        "do": ["Practise SQL out loud against a real schema, not just LeetCode",
               "Be ready to defend a modelling decision you disagreed with"],
    },
    "ml": {
        "stages": ["Recruiter screen", "ML fundamentals", "Coding / applied ML",
                   "System design for ML", "Research or product depth"],
        "topics": ["Bias-variance, regularisation, leakage",
                   "Evaluation metrics and why accuracy is usually wrong",
                   "Feature engineering and train/serve skew",
                   "Model deployment, monitoring, drift",
                   "Transformers and attention if the role is LLM-facing",
                   "Retrieval, chunking, and evaluation for RAG systems"],
        "questions": [
            "Your model does well offline and badly in production. Why?",
            "How would you evaluate a system with no labelled data?",
            "When is a simpler model the right answer?",
            "How do you detect and handle drift?"],
        "do": ["Know the metric your last project moved, and by how much",
               "Be honest about what did not work — it reads as senior"],
    },
    "security": {
        "stages": ["Recruiter screen", "Security fundamentals",
                   "Hands-on / scenario", "Incident response walkthrough",
                   "Team fit"],
        "topics": ["OWASP Top 10 with real examples",
                   "Authentication vs authorisation, session handling",
                   "TLS, certificates, key management",
                   "Threat modelling, blast radius, least privilege",
                   "Detection engineering and log sources",
                   "Incident response phases and evidence handling"],
        "questions": [
            "Walk me through triaging a suspected credential compromise.",
            "How would you threat-model this application?",
            "What would you fix first with limited budget, and why?",
            "How do you get engineers to actually adopt a control?"],
        "do": ["Frame everything as risk and trade-off, not absolutes",
               "Have one story where you were overruled and what you did"],
    },
    "sales": {
        "stages": ["Recruiter screen", "Hiring manager", "Mock discovery call",
                   "Mock demo or pitch", "Leadership"],
        "topics": ["Your numbers: quota, attainment, deal size, cycle length",
                   "Discovery frameworks and qualification",
                   "Handling objections without discounting",
                   "Multi-threading and champion building",
                   "Forecasting honestly"],
        "questions": [
            "Sell me this product in five minutes.",
            "Walk me through your largest lost deal.",
            "How do you qualify out early?",
            "What is your process when a champion leaves mid-cycle?"],
        "do": ["Bring exact numbers, not ranges — vague figures read as invented",
               "Research the buyer persona before the mock call"],
    },
}
INTERVIEW_GENERIC = {
    "stages": ["Recruiter screen", "Hiring manager", "Skills or task assessment",
               "Team fit", "Final / offer"],
    "topics": ["The exact responsibilities in the posting",
               "The company's product, customers and competitors",
               "Your own three strongest, most relevant stories",
               "Tools named in the job description"],
    "questions": [
        "Tell me about yourself.",
        "Why this role and why us?",
        "Tell me about a time you handled conflict.",
        "Describe a failure and what changed afterwards.",
        "Where do you want to be in three years?"],
    "do": ["Prepare three stories in STAR form that can be reshaped to many questions",
           "Write down two questions for them that a website could not answer"],
}


def _round_prompt(job, rtext, round_name, missing):
    """Everything about one round of one interview."""
    return (
        f"You are coaching a candidate through the {round_name} round of a "
        f"specific interview. Depth, not breadth — this is the only round "
        f"you are covering.\n\n"
        f"POSTING: {job.title} at {job.company}\n{(job.text or '')[:2400]}\n\n"
        f"RESUME:\n{(rtext or '')[:2000]}\n\n"
        f"THEY WANT, THE RESUME DOES NOT SHOW: {', '.join(missing[:8]) or 'nothing obvious'}\n\n"
        "Respond with ONLY valid JSON, no markdown fences:\n"
        '{"round":"<the round>",'
        '"who":"<who is in the room and what they personally care about>",'
        '"shape":"<how the 30-45 minutes usually run, in order>",'
        '"prepare":["<something to do BEFORE this round - look up, rehearse, '
        'bring>"],'
        '"questions":[{"q":"<a question>",'
        '"why":"<what they are really testing>",'
        '"answer":"<a full answer in the candidate\'s own voice, 60-110 words, '
        'using their real projects and numbers from the resume>",'
        '"followup":"<the follow-up they will ask, and the one line that '
        'answers it>"}],'
        '"red_flags":["<something that loses this round>"],'
        '"closing":"<what to say in the last two minutes of this round>"}\n\n'
        "6 to 9 questions, all specific to this posting — if it names "
        "Terraform, on-call and a migration, ask about those. The answers are "
        "written out in full, not described: the candidate should be able to "
        "read one aloud and have it be true, which means using what the "
        "resume actually says and never inventing a project. Where they lack "
        "the experience, write the honest answer that still keeps the room."
    )


def _clean_round(d, name):
    """Validate one round. Text only, same rule as everywhere else."""
    def txt(v, n=1200):
        return str(v or "").strip()[:n]

    qs = []
    for q in (d.get("questions") or [])[:10]:
        if isinstance(q, dict) and txt(q.get("q"), 300):
            qs.append({"q": txt(q.get("q"), 300), "why": txt(q.get("why"), 300),
                       "answer": txt(q.get("answer"), 1400),
                       "followup": txt(q.get("followup"), 600)})
    return {"round": txt(d.get("round"), 60) or name[:60],
            "who": txt(d.get("who"), 400), "shape": txt(d.get("shape"), 700),
            "prepare": [txt(x, 300) for x in (d.get("prepare") or [])[:8] if txt(x, 300)],
            "questions": qs,
            "red_flags": [txt(x, 300) for x in (d.get("red_flags") or [])[:6] if txt(x, 300)],
            "closing": txt(d.get("closing"), 600)}


def _interview_prompt(job, rtext, missing):
    """Prep for one posting, read against one resume."""
    jd = (job.text or "")[:2600]
    return (
        "You are preparing a candidate for a specific interview. Use ONLY "
        "what the posting and the resume say — no generic advice.\n\n"
        f"POSTING: {job.title} at {job.company}\n{jd}\n\n"
        f"RESUME:\n{(rtext or '')[:2200]}\n\n"
        f"SKILLS THE POSTING WANTS AND THE RESUME DOES NOT SHOW: "
        f"{', '.join(missing[:10]) or 'none obvious'}\n\n"
        "Respond with ONLY valid JSON, no markdown fences:\n"
        '{"role":"<the role in 2-5 words>",'
        '"opening":"<2 sentences: what this employer is really hiring for, '
        'read from the posting>",'
        '"rounds":[{"name":"<round, e.g. Recruiter screen / Technical / '
        'System design / Manager>",'
        '"what_they_test":"<one sentence>",'
        '"questions":[{"q":"<a question THIS employer would ask, drawn from '
        'the posting>",'
        '"why":"<what they are checking>",'
        '"answer_with":"<what to say, naming the candidate\'s OWN experience '
        'from the resume where it fits — a project, a number, a tool they '
        'have actually used>"}]}],'
        '"gaps":[{"skill":"<a skill they are missing>",'
        '"say":"<how to answer honestly about it without losing the room>"}],'
        '"ask_them":["<a question worth asking the interviewer, specific to '
        'this company or posting>"]}\n\n'
        "3 to 4 rounds, 3 to 5 questions each. Every question must be "
        "answerable from the posting — if the posting says Terraform and "
        "on-call, ask about Terraform and on-call. A question that would fit "
        "any job in the industry is a failure. Where the resume already has "
        "the evidence, say which line to use; where it does not, say so "
        "plainly rather than inventing experience."
    )


def _clean_interview(d, role):
    """Validate the generated prep. Text only — nothing here is rendered as
    markup, and the board's rule applies equally: what a model wrote never
    reaches another user's page as HTML."""
    def txt(v, n=700):
        return str(v or "").strip()[:n]

    rounds = []
    for r in (d.get("rounds") or [])[:5]:
        if not isinstance(r, dict):
            continue
        qs = []
        for q in (r.get("questions") or [])[:6]:
            if not isinstance(q, dict):
                continue
            if txt(q.get("q"), 300):
                qs.append({"q": txt(q.get("q"), 300),
                           "why": txt(q.get("why"), 300),
                           "answer_with": txt(q.get("answer_with"), 900)})
        if qs:
            rounds.append({"name": txt(r.get("name"), 60) or "Interview",
                           "what_they_test": txt(r.get("what_they_test"), 300),
                           "questions": qs})
    gaps = [{"skill": txt(g.get("skill"), 40), "say": txt(g.get("say"), 600)}
            for g in (d.get("gaps") or [])[:6]
            if isinstance(g, dict) and txt(g.get("skill"), 40)]
    return {"role": txt(d.get("role"), 80) or role[:80],
            "opening": txt(d.get("opening"), 600),
            "rounds": rounds, "gaps": gaps,
            "ask_them": [txt(a, 220) for a in (d.get("ask_them") or [])[:5] if txt(a, 220)],
            "tailored": True}


@app.get("/api/interview/guide")
async def interview_guide(category: str = "", job_id: int = 0,
                          round: str = "",
                    user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    """Interview prep for a role family, optionally anchored to one posting."""
    # General prep is free: the canned guide per role family costs nothing to
    # serve and helps anyone. Prep for a SPECIFIC posting is not — it reads
    # the job description against the resume and writes questions this
    # employer would ask, which is a model call per application and the
    # thing worth paying for.
    if job_id:
        require_paid(user, "Interview prep for a specific job")
    cat = (category or "").strip().lower()
    job = db.get(Job, job_id) if job_id else None

    # Prep for THIS posting, read against THIS resume. The canned guide below
    # is the same twelve questions for everyone in a category, which is why
    # it reads as random: it never mentions the job. When we have a posting
    # and a resume we can do the thing a coach actually does — ask what this
    # employer will ask, and point at the candidate's own evidence.
    if job is not None and round and ASK_ENABLED:
        # One round, in depth. A separate call and a separate cache entry:
        # somebody opening the technical round is asking a different question
        # from somebody skimming the whole process, and answering both from
        # one generation is how you get four shallow rounds instead of one
        # useful one.
        require_paid(user, "Interview prep for a specific job")
        note = db.query(Note).filter(Note.user_id == user.id,
                                     Note.k == "resume_uptext").first()
        rtext = (note.v if note else "") or ""
        if len(rtext.strip()) >= 120:
            rn = round.strip()[:60]
            key = ("ivr|" + str(job.id) + "|"
                   + hashlib.sha256(rtext.encode("utf-8", "ignore")).hexdigest()[:12]
                   + "|" + _norm_q(rn))
            row = db.query(AskCache).filter(AskCache.qkey == key).first()
            got = _cached_json(db, row, need=None)
            if got:
                row.hits = (row.hits or 0) + 1
                db.commit()
                return {"round": got, "cached": True}
            skills, _kw = _profile(rtext)
            missing = sorted(_job_req_skills(job) - skills) or \
                sorted(_job_skills(job) - skills)
            _ai_enforce_limit(db, user)
            try:
                text = await _ai_text(_round_prompt(job, rtext, rn, missing),
                                      2800, json_mode=True)
                deep = _clean_round(_ai_json(text), rn)
            except Exception as e:
                print(f"Round prep failed ({AI_PROVIDER}): {type(e).__name__}: {e}")
                raise HTTPException(503, _ai_error_message(e))
            if not deep["questions"]:
                raise HTTPException(502, "That came back empty — try again.")
            _ai_bump(db, user)
            db.add(AskCache(qkey=key, subject="interview", level="",
                            question=(rn + " · " + (job.title or ""))[:2000],
                            lesson=json.dumps(deep), hits=0))
            db.commit()
            return {"round": deep, "cached": False}

    if job is not None and ASK_ENABLED:
        note = db.query(Note).filter(Note.user_id == user.id,
                                     Note.k == "resume_uptext").first()
        rtext = (note.v if note else "") or ""
        if len(rtext.strip()) >= 120:
            key = ("iv|" + str(job.id) + "|"
                   + hashlib.sha256(rtext.encode("utf-8", "ignore")).hexdigest()[:16])
            row = db.query(AskCache).filter(AskCache.qkey == key).first()
            got = _cached_json(db, row, need=None)
            if got:
                row.hits = (row.hits or 0) + 1
                db.commit()
                return {"guide": got, "cached": True}
            skills, _kw = _profile(rtext)
            missing = sorted(_job_req_skills(job) - skills) or \
                sorted(_job_skills(job) - skills)
            _ai_enforce_limit(db, user)
            try:
                text = await _ai_text(_interview_prompt(job, rtext, missing),
                                      2600, json_mode=True)
                guide = _clean_interview(_ai_json(text), job.title or "")
            except Exception as e:
                print(f"Interview prep failed ({AI_PROVIDER}): {type(e).__name__}: {e}")
                guide = None
            if guide and guide["rounds"]:
                _ai_bump(db, user)
                db.add(AskCache(qkey=key, subject="interview", level="",
                                question=(job.title or "")[:2000],
                                lesson=json.dumps(guide), hits=0))
                db.commit()
                return {"guide": guide, "cached": False}
    if job and not cat:
        cat = job.category or ""
    guide = INTERVIEW_GUIDES.get(cat) or INTERVIEW_GENERIC
    return {
        "category": cat, "label": CATEGORY_LABELS.get(cat, "This role"),
        "tailored": bool(INTERVIEW_GUIDES.get(cat)),
        "job": _job_json(job) if job else None,
        **guide,
        "categories": [{"id": k, "label": CATEGORY_LABELS.get(k, k.title())}
                       for k in INTERVIEW_GUIDES],
    }


class ApplyKitIn(BaseModel):
    job_id: int
    resume: dict = {}
    resume_text: str = Field(default="", max_length=40000)


@app.post("/api/jobs/apply-kit")
async def apply_kit(body: ApplyKitIn, user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    """Everything needed to apply for one job, in one place.

    It prepares the material and the user submits it themselves on the
    employer's own site. It deliberately does NOT auto-submit: that would put
    someone's personal data into an employer's system without them seeing it,
    breaks every ATS's terms, and gets real applicants blacklisted.
    """
    apply_gate(db, user, body.job_id)
    job = db.get(Job, body.job_id)
    if not job:
        raise HTTPException(404, "That job is no longer listed")
    rtext = ((body.resume_text or "").strip() or _resume_text(body.resume or {}))[:4000]
    if len(rtext.strip()) < 40:
        raise HTTPException(400, "Add your resume first, or upload one.")

    skills, keywords = _profile(rtext)
    jskills = _job_skills(job)
    have, gaps = sorted(skills & jskills), sorted(jskills - skills)

    # The free half: no AI, always available, useful on its own.
    kit = {
        "job": _job_json(job),
        "matched": have[:14],
        "gaps": gaps[:10],
        "checklist": [
            "Open the posting and apply on the employer's own site — direct "
            "applications are read before aggregator ones.",
            f"Put these words in your resume where they are true: {', '.join(have[:6]) or 'the tools named in the ad'}.",
            "Name the company and the role in your first line — generic notes read as spam.",
            "Attach a PDF, not a DOCX, unless the form asks otherwise.",
            "If there is a 'why this company' box, write two specific sentences. Leave nothing blank.",
        ],
    }
    if not ASK_ENABLED:
        kit["note"] = ("AI tailoring is switched off on this server, so the "
                       "checklist and keyword lists above are all we can give you.")
        return kit

    ckey = _ai_cache_key("akit", rtext[:2500], str(job.id),
                         scope=_scope_of(db, user))
    cached = _ai_cache_get(db, ckey)
    if cached is not None:
        return {**kit, **cached, "cached": True}
    _ai_enforce_limit(db, user)

    prompt = (
        "You are helping someone apply for one specific job. Use ONLY facts "
        "present in their resume — never invent an employer, a date, a degree "
        "or a number.\n\n"
        f"JOB TITLE: {job.title}\nCOMPANY: {job.company}\n"
        f"LOCATION: {job.location}\n"
        f"JOB POSTING:\n{(job.text or '')[:2200]}\n\n"
        f"THEIR RESUME:\n{rtext[:2200]}\n\n"
        "Return ONLY valid JSON in exactly this shape:\n"
        '{"summary": "<a 2-3 sentence resume summary rewritten for THIS job, '
        'first person implied, no fluff>", '
        '"bullets": ["<3-5 resume bullets from their real experience, reworded '
        'to lead with what this posting asks for>"], '
        '"cover_note": "<a short cover note, 90-130 words, addressed to the '
        'hiring team, naming the company and role, concrete not gushing>", '
        '"questions": [{"q": "<a screening question this employer is likely to '
        'ask>", "a": "<a strong answer built from their real experience>"}], '
        '"flags": ["<anything in the posting they may not meet, stated plainly>"]}'
    )
    try:
        d = _ai_json(await _ai_text(prompt, 2500, json_mode=True, best=True))
    except Exception as e:
        print(f"Apply kit failed ({AI_PROVIDER}): {type(e).__name__}: {e}")
        raise HTTPException(503, _ai_error_message(e))

    def s(v, n):
        return str(v or "").strip()[:n]
    out = {
        "summary": s(d.get("summary"), 700),
        "bullets": [s(x, 300) for x in (d.get("bullets") or []) if str(x).strip()][:6],
        "cover_note": s(d.get("cover_note"), 1400),
        "questions": [{"q": s(x.get("q"), 200), "a": s(x.get("a"), 700)}
                      for x in (d.get("questions") or []) if isinstance(x, dict)][:4],
        "flags": [s(x, 200) for x in (d.get("flags") or []) if str(x).strip()][:4],
    }
    _ai_bump(db, user)
    _ai_cache_put(db, ckey, out)
    return {**kit, **out, "cached": False}


# ============================ billing =====================================
# Stripe is the only gateway, worldwide, in US dollars. The user's `plan` is
# only ever written by a signature-verified webhook — never by the browser,
# which could otherwise simply ask to be upgraded.
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET")
STRIPE_ENABLED = bool(STRIPE_SECRET_KEY)

# Stripe Price IDs, created in the Stripe dashboard.
STRIPE_PRICES = {
    ("pro", "month"): env("STRIPE_PRICE_PRO_MONTH"),
    ("pro", "year"): env("STRIPE_PRICE_PRO_YEAR"),
}


@app.get("/api/billing/plans")
def billing_plans(request: Request, user: User = Depends(current_user),
                  db: Session = Depends(get_db)):
    """What this user can buy. One price worldwide, in US dollars."""

    def money(v):
        return None if v is None else f"${v/100:,.2f}"

    out = []
    for pid in ("free", "pro"):
        p = PLANS[pid]
        out.append({
            "id": pid, "name": p["name"],
            "month": money(p.get("usd_month")),
            "year": money(p.get("usd_year")),
            # Every term on sale, cheapest-per-month last, with the saving
            # worked out here so the page never has to do arithmetic.
            "periods": [
                {"id": k, "label": spec["label"], "months": spec["months"],
                 "price": money(p.get(f"usd_{k}")),
                 "per_month": money(p[f"usd_{k}"] / spec["months"]),
                 "save_pct": round(100 * (1 - (p[f"usd_{k}"] / spec["months"])
                                          / p["usd_month"]))}
                for k, spec in BILLING_PERIODS.items()
                if p.get(f"usd_{k}") and p.get("usd_month")
            ] if pid != "free" else [],
            "ai": ("Unlimited" if pid == "pro"
                   else f"{p.get('ai_total') or p.get('ai_month')} AI requests"
                        + (" to start" if pid == "free" else " a month")),
            "kits": ("Unlimited" if pid == "pro"
                     else f"{p.get('kits_total') or p.get('kits_month')} apply kits"
                          + (" to start" if pid == "free" else " a month")),
        })
    return {
        "plans": out, "currency": "USD",
        "gateway": "stripe",
        "available": {"stripe": STRIPE_ENABLED},
        "current": plan_of(user),
        "cancelled": bool(user.plan_cancelled_at),
        "access_until": user.plan_expires.isoformat() if user.plan_expires else None,
        "quota": ai_quota(db, user),
        # Always say plainly that this renews. Silent auto-renewal is the
        # single biggest source of chargebacks and complaints.
        "renews": True,
    }


@app.get("/api/billing/me")
def billing_me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    exp = user.plan_expires
    return {"plan": plan_of(user), "stored_plan": user.plan or "free",
            "provider": user.plan_provider or "",
            "cancelled": bool(user.plan_cancelled_at),
            "expires": exp.isoformat() if exp else None,
            "quota": ai_quota(db, user)}


@app.post("/api/billing/cancel")
async def billing_cancel(user: User = Depends(current_user),
                         db: Session = Depends(get_db)):
    """Stop the subscription renewing, keeping access until the paid period ends.

    Cutting access immediately would take away something already paid for, so
    the plan simply stops renewing. The Terms promise this can be done from the
    account, so it must not require emailing us.
    """
    if plan_of(user) == "free":
        raise HTTPException(400, "You are not on a paid plan.")
    note = ""
    if user.plan_provider == "stripe" and STRIPE_ENABLED and user.plan_ref:
        try:
            async with httpx.AsyncClient(timeout=20) as c:
                r = await c.post(
                    f"https://api.stripe.com/v1/subscriptions/{user.plan_ref}",
                    headers={"Authorization": f"Bearer {STRIPE_SECRET_KEY}"},
                    data={"cancel_at_period_end": "true"})
            if r.status_code >= 300:
                print("Stripe cancel failed:", r.status_code, r.text[:200])
                note = ("We recorded your cancellation, but could not reach the "
                        "payment provider. Email us if you are charged again.")
        except Exception as e:
            print(f"Stripe cancel error: {type(e).__name__}: {e}")
            note = ("We recorded your cancellation, but could not reach the "
                    "payment provider. Email us if you are charged again.")
    user.plan_cancelled_at = now()
    db.commit()
    exp = user.plan_expires
    return {"ok": True, "cancelled": True,
            "access_until": exp.isoformat() if exp else None,
            "note": note,
            "message": "Cancelled. You keep full access until "
                       + (exp.strftime("%d %B %Y") if exp else "the end of the period")
                       + ", and you will not be charged again."}


class CheckoutIn(BaseModel):
    plan: str = Field(max_length=10)
    period: str = Field(default="month", max_length=10)


@app.post("/api/billing/checkout")
async def billing_checkout(body: CheckoutIn, request: Request,
                           user: User = Depends(current_user)):
    """Start a subscription. Returns whatever the gateway needs the page to do."""
    plan, period = body.plan.lower(), body.period.lower()
    if plan not in PAID_PLANS:
        raise HTTPException(400, "Unknown plan")
    if period not in BILLING_PERIODS:
        raise HTTPException(400, "Unknown billing period")
    if not STRIPE_ENABLED:
        raise HTTPException(503, "Payments are not switched on yet.")
    base = PUBLIC_BASE_URL or str(request.base_url).rstrip("/")

    # Two ways to price this. A Price ID created in the Stripe dashboard wins
    # if one is configured; otherwise the amount is sent inline from PLANS.
    # Inline is the default on purpose: it needs nothing set up in Stripe
    # beyond an API key, and it cannot drift from the price the site quotes —
    # a stale dashboard Price ID would charge a number nobody advertised.
    price = STRIPE_PRICES.get((plan, period))
    if price:
        line = {"line_items[0][price]": price}
    else:
        amount = PLANS[plan].get(f"usd_{period}")
        if not amount:
            raise HTTPException(400, "That plan is not sold for that period")
        spec = BILLING_PERIODS[period]
        line = {
            "line_items[0][price_data][currency]": "usd",
            "line_items[0][price_data][unit_amount]": str(int(amount)),
            # Stripe has no "quarter": 3- and 6-month terms are a monthly
            # interval with a count, not an interval of their own.
            "line_items[0][price_data][recurring][interval]": spec["interval"],
            "line_items[0][price_data][recurring][interval_count]": str(spec["count"]),
            "line_items[0][price_data][product_data][name]":
                f"Craxle {PLANS[plan]['name']}",
            "line_items[0][price_data][product_data][description]":
                "Resume matching, application tracking, apply kits and the "
                "autofill extension.",
        }

    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(
            "https://api.stripe.com/v1/checkout/sessions",
            headers={"Authorization": f"Bearer {STRIPE_SECRET_KEY}"},
            data={"mode": "subscription", **line,
                  "line_items[0][quantity]": "1",
                  "customer_email": user.email,
                  "client_reference_id": str(user.id),
                  "metadata[user_id]": str(user.id),
                  "metadata[plan]": plan,
                  "metadata[period]": period,
                  # Also stamped on the subscription itself: renewal invoices
                  # carry the subscription's metadata, not the checkout
                  # session's, and without the period a yearly renewal would
                  # be granted 32 days of access.
                  "subscription_data[metadata][user_id]": str(user.id),
                  "subscription_data[metadata][plan]": plan,
                  "subscription_data[metadata][period]": period,
                  "success_url": f"{base}/?upgraded=1",
                  "cancel_url": f"{base}/?upgrade_cancelled=1"})
    if r.status_code >= 300:
        print("Stripe session failed:", r.status_code, r.text[:300])
        raise HTTPException(502, "Could not start the payment. Try again.")
    return {"gateway": "stripe", "url": r.json()["url"]}


def _activate(db, user_id, plan, provider, ref, period="month"):
    u = db.get(User, int(user_id))
    if not u:
        print(f"webhook: unknown user {user_id}")
        return
    days = BILLING_PERIODS.get(period, BILLING_PERIODS["month"])["days"]
    u.plan, u.plan_provider, u.plan_ref = plan, provider, str(ref or "")[:120]
    u.plan_started = now()
    u.plan_expires = now() + dt.timedelta(days=days)
    db.commit()
    print(f"billing: user {u.id} -> {plan} via {provider} until {u.plan_expires}")


@app.post("/api/billing/webhook/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Stripe calls this. Verifies the timestamped signature header."""
    raw = await request.body()
    header = request.headers.get("stripe-signature", "")
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(503, "Webhook secret not configured")
    parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
    t, v1 = parts.get("t", ""), parts.get("v1", "")
    expected = hmac.new(STRIPE_WEBHOOK_SECRET.encode(),
                        f"{t}.".encode() + raw, hashlib.sha256).hexdigest()
    if not (v1 and hmac.compare_digest(expected, v1)):
        raise HTTPException(400, "Bad signature")
    # Reject anything older than five minutes, so a captured request cannot be
    # replayed later to extend a subscription.
    try:
        if abs(time.time() - int(t)) > 300:
            raise HTTPException(400, "Stale webhook")
    except ValueError:
        raise HTTPException(400, "Bad timestamp")

    ev = json.loads(raw or b"{}")
    obj = (ev.get("data") or {}).get("object") or {}
    kind = ev.get("type", "")
    md = obj.get("metadata") or {}
    if kind in ("checkout.session.completed", "invoice.payment_succeeded"):
        uid = md.get("user_id") or obj.get("client_reference_id")
        period = md.get("period") or ""
        sub = obj.get("subscription") or obj.get("id")
        # A renewal invoice may carry neither: fall back to the subscription we
        # already recorded, and to the length of the term they are currently on.
        if (not uid or not period) and sub:
            u = db.query(User).filter(User.plan_ref == str(sub)).first()
            if u:
                uid = uid or u.id
                if not period:
                    period = _period_from_span(u.plan_started, u.plan_expires)
        if uid:
            _activate(db, uid, "pro", "stripe", sub, period or "month")
    elif kind in ("customer.subscription.deleted", "invoice.payment_failed"):
        sub = obj.get("subscription") or obj.get("id")
        u = db.query(User).filter(User.plan_ref == str(sub)).first()
        if u:
            # Do not cut access mid-period; let it lapse at expiry.
            # _aware() matters here: SQLite hands back naive datetimes, and
            # comparing one against an aware now() raises, which would 500 the
            # webhook — and Stripe retries a failing webhook for days.
            u.plan_expires = min(_aware(u.plan_expires) if u.plan_expires
                                 else now(), now())
            db.commit()
    return {"ok": True}


@app.post("/api/admin/jobs/prune")
def admin_jobs_prune(dry: int = 1, user: User = Depends(admin_user),
                     db: Session = Depends(get_db)):
    """Delete stored postings that fall outside the board's scope.

    An endpoint rather than a migration because the scope is configurable:
    widen JOB_COUNTRIES or JOB_FAMILIES later and this needs running again.
    Defaults to a dry run — pass ?dry=0 to actually delete, so nobody wipes
    the board by clicking a button they were curious about.
    """
    rows = db.query(Job).all()
    keep = _protected_job_ids(db)
    # Location matters here as much as country: the rows that survived the
    # last prune are precisely the ones whose country field was empty and
    # whose location said Hamburg.
    doomed = [j for j in rows
              if j.id not in keep
              and not _job_in_scope({"category": j.category, "country": j.country,
                                     "location": j.location, "skills": j.skills,
                                     "title": j.title})]
    by_country, by_family = {}, {}
    for j in doomed:
        label = j.country or (f"(blank) {j.location or '?'}"[:40])
        by_country[label] = by_country.get(label, 0) + 1
        by_family[(j.category or "(none)")] = by_family.get(j.category or "(none)", 0) + 1
    if not dry:
        for j in doomed:
            db.delete(j)
        db.commit()
    return {"dry_run": bool(dry),
            "total_stored": len(rows),
            "out_of_scope": len(doomed),
            "would_keep" if dry else "kept": len(rows) - len(doomed),
            "by_country": dict(sorted(by_country.items(), key=lambda x: -x[1])[:15]),
            "by_family": dict(sorted(by_family.items(), key=lambda x: -x[1])[:15]),
            "scope": {"countries": sorted(ALLOWED_COUNTRIES),
                      "families": sorted(ALLOWED_FAMILIES)}}


@app.post("/api/admin/board/cache/clear")
def admin_board_cache_clear(dry: int = 1, kind: str = "board",
                            user: User = Depends(admin_user),
                            db: Session = Depends(get_db)):
    """Throw away cached lessons so they are taught again with today's prompt.

    Lessons are cached forever on purpose — one model call per topic, served
    free to everyone after. The cost of that is that improving how the board
    teaches does nothing for any topic already in the table: a lesson written
    when a step was "one short paragraph" keeps its one line and its pointless
    two-box diagram for good.

    kind=board clears smart-board lessons, career clears role paths, all
    clears both. Dry by default, because every row deleted is a model call
    someone will pay for again.
    """
    kinds = {"board": ["board"], "career": ["career"],
             "all": ["board", "career"]}.get(kind.strip().lower())
    if not kinds:
        raise HTTPException(400, "kind must be board, career or all")
    q = db.query(AskCache).filter(AskCache.subject.in_(kinds))
    n = q.count()
    if not dry:
        q.delete(synchronize_session=False)
        db.commit()
    return {"dry_run": bool(dry), "kind": kind, "cached_lessons": n,
            "deleted": 0 if dry else n,
            "note": "each one is re-taught, and re-charged, the next time "
                    "someone asks for it"}


@app.post("/api/admin/jobs/recategorize")
def admin_jobs_recategorize(dry: int = 1, user: User = Depends(admin_user),
                            db: Session = Depends(get_db)):
    """Re-label stored postings with today's family rules.

    A posting's category is decided once, when it is crawled. Every time the
    family keywords improve, the rows already on the board keep the old
    answer — which is how half the board ended up uncategorised, invisible to
    the category filter, and at risk of being pruned as non-technical. Run
    this after any change to _ROLE_FAMILIES. Dry by default; ?dry=0 writes.
    """
    rows = db.query(Job).all()
    changed, filled, cleared, paid, skilled, yrs = [], 0, 0, 0, 0, 0
    for j in rows:
        # Pay, from the text we already stored. Nothing is inferred: if the
        # employer did not state a figure, the field stays empty.
        if not (j.salary or "").strip():
            s = _salary_from(j.text or "")
            if s:
                paid += 1
                if not dry:
                    j.salary = s
        # Skills, for rows stored before the column existed. Over half the
        # board is in that state, and every one of them makes matching parse
        # 4,000 characters of description at request time instead of reading
        # a comma-separated list — which is also what stops the query from
        # being able to leave the description behind entirely.
        if not j.min_years and (j.text or ""):
            y = _years_required(j.text)
            if y:
                yrs += 1
                if not dry:
                    j.min_years = y
        if not (j.skills or "").strip() and (j.text or ""):
            sk = sorted({w for w in _words(j.text) if w in _SKILLS})
            rq = sorted({w for w in _words(_requirement_text(j.text))
                         if w in _SKILLS})
            if sk:
                skilled += 1
                if not dry:
                    j.skills = ",".join(sk)
                    j.req_skills = ",".join(rq)
        new = _primary_family(j.title or "", j.text or "")
        if not new:
            # Same rule ingestion uses, so a backfilled row and a freshly
            # crawled one end up with the same answer.
            in_scope = _job_in_scope({"category": "", "country": j.country,
                                      "location": j.location, "skills": j.skills,
                                      "title": j.title})
            if in_scope:
                new = _family_from_text(j.text or "") or "other"
        if new != (j.category or ""):
            if not j.category:
                filled += 1
            elif not new:
                cleared += 1
            changed.append((j.title or "")[:60] + f"  {j.category or '(none)'} -> {new or '(none)'}")
            if not dry:
                j.category = new
    if not dry:
        db.commit()
    return {"dry_run": bool(dry), "total": len(rows), "changed": len(changed),
            "newly_categorised": filled, "label_removed": cleared,
            "salary_filled": paid, "skills_filled": skilled,
            "years_filled": yrs,
            "examples": changed[:25]}


async def _refresh_jobs_bg():
    """_refresh_jobs records its own outcome, so this only has to not die."""
    try:
        await _refresh_jobs()
    except Exception as e:
        print(f"background crawl failed: {type(e).__name__}: {e}")


@app.post("/api/admin/jobs/schedule")
def admin_jobs_schedule(mode: str = "", start: int = -1, end: int = -1,
                        user: User = Depends(admin_user),
                        db: Session = Depends(get_db)):
    """Turn the crawler on, off, or back onto its hours — and set those hours.

    Before launch you are working at 8pm and want the board to fill now. Once
    real users are on it, the window is what stops the API quota being spent
    overnight on postings nobody is reading. Both are right at different
    times, so this is a switch rather than a redeploy.

    Stored in the database, read on every loop, so a change takes effect
    within the interval rather than at the next deploy. The hours are process
    globals — they reset to the environment values on restart, which is why
    the response says so.
    """
    global JOB_ACTIVE_START, JOB_ACTIVE_END
    changed = []
    if mode:
        m = mode.strip().lower()
        if m not in _CRAWL_MODES:
            raise HTTPException(400, f"mode must be one of {list(_CRAWL_MODES)}")
        row = db.get(SysCounter, "crawl_mode_v")
        if row is None:
            row = SysCounter(k="crawl_mode_v", v=0)
            db.add(row)
        row.v = _CRAWL_MODES.index(m)
        db.commit()
        changed.append(f"mode={m}")
    if 0 <= start <= 23:
        JOB_ACTIVE_START = start
        changed.append(f"start={start}")
    if 0 <= end <= 23:
        JOB_ACTIVE_END = end
        changed.append(f"end={end}")

    local = now() + dt.timedelta(hours=JOB_TZ_OFFSET)
    wait = _crawl_window_wait()
    return {"mode": _crawl_mode(),
            "hours": f"{JOB_ACTIVE_START:02d}:00-{JOB_ACTIVE_END:02d}:00 local",
            "local_time_now": local.strftime("%H:%M"),
            "crawling_now": wait == 0,
            "next_crawl_in_minutes": round(wait / 60),
            "changed": changed or ["nothing — this is the current state"],
            "note": "mode survives restarts; changed hours do not — set "
                    "JOB_ACTIVE_START / JOB_ACTIVE_END to make those permanent"}


@app.post("/api/admin/jobs/refresh")
async def admin_jobs_refresh(user: User = Depends(admin_user)):
    """Start a crawl and return immediately.

    It cannot run inline: Cloudflare closes any request after 100 seconds and
    a full sweep of 263 boards takes minutes, so the button always returned a
    524 while the crawl kept going invisibly behind it. Poll
    /api/admin/jobs/refresh/status for the report.
    """
    import asyncio
    if _LAST_CRAWL.get("state") == "running":
        return {"started": False, "already_running": True, **_LAST_CRAWL}
    asyncio.create_task(_refresh_jobs_bg())
    return {"started": True,
            "note": "Crawling in the background — this takes a few minutes. "
                    "Press Check status for the per-source report."}


@app.get("/api/admin/jobs/refresh/status")
def admin_jobs_refresh_status(user: User = Depends(admin_user)):
    return _LAST_CRAWL


# ---------------------------- admin ---------------------------------------
@app.get("/api/admin/stats")
def admin_stats(user: User = Depends(admin_user), db: Session = Depends(get_db)):
    total_users = db.query(func.count(User.id)).scalar()
    total_lessons = db.query(func.count(Lesson.id)).filter(Lesson.published == True).scalar()  # noqa: E712
    completions = db.query(func.count(Progress.id)).filter(Progress.completed == True).scalar()  # noqa: E712

    week_ago = now() - dt.timedelta(days=7)
    active_7d = db.query(func.count(User.id)).filter(User.last_seen >= week_ago).scalar()
    new_7d = db.query(func.count(User.id)).filter(User.created_at >= week_ago).scalar()

    # What the job board is actually producing. "Applied" counts the later
    # pipeline stages too — someone interviewing obviously applied first, and
    # counting only the "applied" status would undercount the further along
    # somebody gets, which is exactly backwards.
    APPLIED_STAGES = ("applied", "interviewing", "offer", "rejected")
    applied_q = db.query(JobTrack).filter(JobTrack.status.in_(APPLIED_STAGES))
    applications = applied_q.count()
    applicants = db.query(func.count(func.distinct(JobTrack.user_id)))         .filter(JobTrack.status.in_(APPLIED_STAGES)).scalar() or 0
    jobs_applied_to = db.query(func.count(func.distinct(JobTrack.job_id)))         .filter(JobTrack.status.in_(APPLIED_STAGES)).scalar() or 0
    applications_7d = applied_q.filter(JobTrack.applied_at >= week_ago).count()
    saved_total = db.query(func.count(JobTrack.id))         .filter(JobTrack.status == "saved").scalar() or 0
    jobs_live = db.query(func.count(Job.id)).filter(Job.is_open == True).scalar() or 0  # noqa: E712
    # Where the board's coverage actually is. Without this, tuning
    # JOB_COUNTRIES / JOB_FAMILIES is guesswork — you widen the scope and have
    # no idea whether it brought anything in.
    jobs_by_country = [{"name": (c or "(unknown)"), "count": n} for c, n in
                       db.query(Job.country, func.count(Job.id))
                       .filter(Job.is_open == True)          # noqa: E712
                       .group_by(Job.country)
                       .order_by(func.count(Job.id).desc()).limit(12).all()]
    jobs_by_family = [{"name": (f or "(uncategorised)"), "count": n} for f, n in
                      db.query(Job.category, func.count(Job.id))
                      .filter(Job.is_open == True)           # noqa: E712
                      .group_by(Job.category)
                      .order_by(func.count(Job.id).desc()).limit(12).all()]

    # signups per day, last 30 days (cast works on both SQLite and Postgres)
    day = cast(User.created_at, Date).label("d")
    signups = db.query(day, func.count(User.id)) \
        .filter(User.created_at >= now() - dt.timedelta(days=30)) \
        .group_by(day).all()

    # lesson completion counts, to find drop-off
    counts = dict(db.query(Progress.lesson_slug, func.count(Progress.id))
                  .filter(Progress.completed == True)  # noqa: E712
                  .group_by(Progress.lesson_slug).all())

    lessons = (db.query(Lesson, Track)
               .join(Track, Lesson.track_id == Track.id)
               .filter(Lesson.published == True)  # noqa: E712
               .order_by(Track.position, Lesson.position).all())
    funnel = [{
        "lesson": l.slug, "title": l.title, "track": t.name, "icon": t.icon,
        "completions": counts.get(l.slug, 0),
        "rate": round(counts.get(l.slug, 0) / total_users * 100, 1) if total_users else 0,
    } for l, t in lessons]

    # biggest drop-off: largest fall between consecutive lessons
    drop = None
    for i in range(1, len(funnel)):
        d = funnel[i - 1]["completions"] - funnel[i]["completions"]
        if d > 0 and (drop is None or d > drop["lost"]):
            drop = {"lost": d, "after": funnel[i - 1]["title"], "before": funnel[i]["title"]}

    quiz_rows = db.query(QuizResult.track_slug,
                         func.count(QuizResult.id),
                         func.sum(cast(QuizResult.passed, Integer))
                         ).group_by(QuizResult.track_slug).all()

    return {
        "total_users": total_users,
        "active_7d": active_7d,
        "new_7d": new_7d,
        # The job board's actual output, not just its size.
        "jobs_live": jobs_live,
        "jobs_by_country": jobs_by_country,
        "jobs_by_family": jobs_by_family,
        "applications": applications,
        "applications_7d": applications_7d,
        "applicants": applicants,
        "jobs_applied_to": jobs_applied_to,
        "saved_total": saved_total,
        "applications_per_applicant": round(applications / applicants, 1) if applicants else 0,
        "total_lessons": total_lessons,
        "completions": completions,
        "avg_per_user": round(completions / total_users, 1) if total_users else 0,
        "signups": [{"date": str(d), "count": c} for d, c in signups],
        "funnel": funnel,
        "biggest_drop": drop,
        "quiz": [{"track": t, "attempts": a, "passed": int(p or 0)} for t, a, p in quiz_rows],
    }


@app.get("/api/admin/revenue")
def admin_revenue(user: User = Depends(admin_user), db: Session = Depends(get_db)):
    """What the paid side is actually doing.

    Revenue is derived from the plan each user is on, not from a payments
    ledger — we do not store one. Treat these as indicative and reconcile
    against Stripe before relying on a number for tax or accounting.
    """
    users = db.query(User).all()
    total = len(users)
    now_ = now()

    def live(u):
        exp = u.plan_expires
        if exp is not None and exp.tzinfo is None:
            exp = exp.replace(tzinfo=dt.timezone.utc)
        return (u.plan or "free") in PAID_PLANS and (exp is None or exp >= now_)

    paying = [u for u in users if live(u)]
    # Prices are charged in USD through Stripe, but everything below — GST,
    # hosting, the profit line — is rupee accounting, so convert once here.
    by_plan, mrr_usd_cents = {}, 0
    for u in paying:
        by_plan[u.plan] = by_plan.get(u.plan, 0) + 1
        p = PLANS.get(u.plan, {})
        # Every term is normalised to a month, so a 3-month and a 12-month
        # subscriber are comparable in the same MRR figure.
        per = _period_from_span(u.plan_started, u.plan_expires)
        amt, months = p.get(f"usd_{per}"), BILLING_PERIODS[per]["months"]
        if amt:
            mrr_usd_cents += amt / months
        elif p.get("usd_month"):
            mrr_usd_cents += p["usd_month"]
    mrr_inr = mrr_usd_cents * USD_INR

    cancelled = sum(1 for u in users if u.plan_cancelled_at)
    week = now_ - dt.timedelta(days=7)
    new_paid = sum(1 for u in paying if u.plan_started and
                   (u.plan_started.replace(tzinfo=dt.timezone.utc)
                    if u.plan_started.tzinfo is None else u.plan_started) >= week)
    verified = sum(1 for u in users if u.email_verified)

    ai_calls = 0
    for row in db.query(Note).filter(Note.k == "aiq_total").all():
        try:
            ai_calls += int(row.v)
        except Exception:
            pass
    # Gemini Flash-Lite pricing, order-of-magnitude only.
    ai_cost_usd = round(ai_calls * 0.0005, 2)

    gross_inr = mrr_inr / 100
    gst_inr = gross_inr - (gross_inr / (1 + GST_RATE_PCT / 100)) if GST_RATE_PCT else 0
    net_of_gst = gross_inr - gst_inr
    gateway_inr = net_of_gst * GATEWAY_FEE_PCT / 100
    ai_inr = ai_cost_usd * USD_INR
    fixed_inr = COST_HOSTING_INR + COST_DOMAIN_INR + COST_OTHER_INR
    costs_inr = round(gateway_inr + ai_inr + fixed_inr, 2)
    profit_inr = round(net_of_gst - costs_inr, 2)
    break_even = None
    if paying:
        per_user = net_of_gst / len(paying)
        if per_user > 0:
            break_even = max(1, round(fixed_inr / (per_user * (1 - GATEWAY_FEE_PCT / 100))))

    return {
        "users_total": total,
        "users_verified": verified,
        "money": {
            "gross_inr": round(gross_inr, 2),
            "gst_owed_inr": round(gst_inr, 2),
            "net_of_gst_inr": round(net_of_gst, 2),
            "costs": {
                "hosting_inr": COST_HOSTING_INR,
                "domain_inr": COST_DOMAIN_INR,
                "other_inr": COST_OTHER_INR,
                "gateway_fees_inr": round(gateway_inr, 2),
                "ai_inr": round(ai_inr, 2),
                "total_inr": costs_inr,
            },
            "profit_inr": profit_inr,
            "margin_pct": round(profit_inr / net_of_gst * 100, 1) if net_of_gst else 0,
            "break_even_subscribers": break_even,
        },
        "paying_now": len(paying),
        "by_plan": by_plan,
        "conversion_pct": round(len(paying) / total * 100, 1) if total else 0,
        "mrr_inr": round(mrr_inr / 100, 2),
        "arr_inr": round(mrr_inr * 12 / 100, 2),
        "arpu_inr": round(mrr_inr / 100 / len(paying), 2) if paying else 0,
        "new_paid_7d": new_paid,
        "cancellations_total": cancelled,
        "ai_requests_total": ai_calls,
        "ai_cost_usd_estimate": ai_cost_usd,
        "note": "Derived from plan state, not a payments ledger. "
                "Reconcile against Stripe before using for accounting.",
    }


@app.get("/api/admin/students")
def admin_students(q: str = "", limit: int = 200,
                   user: User = Depends(admin_user), db: Session = Depends(get_db)):
    query = db.query(User)
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(func.lower(User.name).like(like) | func.lower(User.email).like(like))
    users = query.order_by(User.created_at.desc()).limit(min(limit, 1000)).all()
    total_lessons = db.query(func.count(Lesson.id)).filter(Lesson.published == True).scalar() or 1  # noqa: E712
    counts = dict(db.query(Progress.user_id, func.count(Progress.id))
                  .filter(Progress.completed == True)  # noqa: E712
                  .group_by(Progress.user_id).all())
    return {"students": [{
        "id": u.id, "name": u.name, "email": u.email, "college": u.college,
        "city": u.city, "degree": u.degree, "path": u.path,
        "is_admin": u.is_admin, "is_active": u.is_active,
        "joined": u.created_at.isoformat() if u.created_at else None,
        "last_seen": u.last_seen.isoformat() if u.last_seen else None,
        "done": counts.get(u.id, 0),
        "pct": round(counts.get(u.id, 0) / total_lessons * 100),
    } for u in users], "total_lessons": total_lessons}


def _sort_key(row):
    """Sort progress rows newest-first, tolerating naive/aware datetime mixes."""
    d = row.updated_at
    if d is None:
        return dt.datetime.min.replace(tzinfo=dt.timezone.utc)
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


@app.get("/api/admin/student/{uid}")
def admin_student(uid: int, user: User = Depends(admin_user), db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "Student not found")
    rows = db.query(Progress).filter(Progress.user_id == uid).all()
    quizzes = db.query(QuizResult).filter(QuizResult.user_id == uid)\
                .order_by(QuizResult.created_at.desc()).all()
    lessons = {l.slug: l for l in db.query(Lesson).all()}
    return {
        "student": {
            "id": u.id, "name": u.name, "email": u.email, "college": u.college,
            "city": u.city, "degree": u.degree, "path": u.path,
            "is_active": u.is_active, "is_admin": u.is_admin,
            "joined": u.created_at.isoformat() if u.created_at else None,
            "last_seen": u.last_seen.isoformat() if u.last_seen else None,
        },
        "progress": [{
            "lesson": r.lesson_slug,
            "title": lessons[r.lesson_slug].title if r.lesson_slug in lessons else r.lesson_slug,
            "completed": r.completed, "attempts": r.attempts,
            "has_code": bool(r.code),
            "code": r.code or "",
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        } for r in sorted(rows, key=_sort_key, reverse=True)],
        "quizzes": [{"track": q.track_slug, "score": q.score, "total": q.total,
                     "passed": q.passed,
                     "at": q.created_at.isoformat() if q.created_at else None} for q in quizzes],
    }


@app.post("/api/admin/student/{uid}/toggle")
def admin_toggle(uid: int, user: User = Depends(admin_user), db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "Student not found")
    if u.id == user.id:
        raise HTTPException(400, "You cannot deactivate your own account")
    u.is_active = not u.is_active
    db.commit()
    return {"is_active": u.is_active}


class PwResetIn(BaseModel):
    password: str = Field(min_length=8, max_length=200)


@app.post("/api/admin/student/{uid}/reset-password")
def admin_reset_password(uid: int, body: PwResetIn,
                         user: User = Depends(admin_user), db: Session = Depends(get_db)):
    """Admin/teacher-driven password reset — the recovery path for a school
    where students can't do self-service email resets."""
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "Student not found")
    u.password_hash = hash_pw(body.password)
    db.commit()
    return {"ok": True}


@app.delete("/api/admin/student/{uid}")
def admin_delete_student(uid: int, user: User = Depends(admin_user), db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "Student not found")
    if u.id == user.id:
        raise HTTPException(400, "You cannot delete your own account")
    # Everything the account owns, explicitly.
    #
    # Five of these tables reference users.id with no ON DELETE CASCADE —
    # job_tracks, job_alerts, job_invites, employer_jobs, password_resets —
    # all added after this endpoint was written. Postgres refuses the delete
    # with a foreign key violation the moment a student has saved a single
    # job, which is every student. Clearing them here works on both engines
    # and does not require altering constraints on a live table.
    #
    # Anything added later that belongs to a user belongs in this list.
    inv_ids = [r[0] for r in db.query(JobInvite.id).filter(
        JobInvite.user_id == uid).all()]
    if inv_ids:
        db.query(InviteMessage).filter(
            InviteMessage.invite_id.in_(inv_ids)).delete(synchronize_session=False)
        db.query(InviteFile).filter(
            InviteFile.invite_id.in_(inv_ids)).delete(synchronize_session=False)
    for model, col in ((Progress, Progress.user_id),
                       (QuizResult, QuizResult.user_id),
                       (Note, Note.user_id),
                       (JobTrack, JobTrack.user_id),
                       (JobAlert, JobAlert.user_id),
                       (JobInvite, JobInvite.user_id),
                       (EmployerJob, EmployerJob.owner_id),
                       (PasswordReset, PasswordReset.user_id)):
        db.query(model).filter(col == uid).delete(synchronize_session=False)
    db.delete(u)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        # Surface what actually blocked it rather than a bare 500 — the next
        # table someone adds will land here and the message names it.
        raise HTTPException(409, f"Could not delete: {type(e).__name__}: "
                                 f"{str(e)[:200]}")
    return {"ok": True}


@app.get("/api/admin/export.csv")
def admin_export(user: User = Depends(admin_user), db: Session = Depends(get_db)):
    import csv, io
    total_lessons = db.query(func.count(Lesson.id)).filter(Lesson.published == True).scalar() or 1  # noqa: E712
    counts = dict(db.query(Progress.user_id, func.count(Progress.id))
                  .filter(Progress.completed == True).group_by(Progress.user_id).all())  # noqa: E712
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "name", "email", "college", "city", "degree", "path",
                "lessons_done", "percent", "joined", "last_seen", "active"])
    for u in db.query(User).order_by(User.created_at).all():
        d = counts.get(u.id, 0)
        w.writerow([u.id, u.name, u.email, u.college, u.city, u.degree, u.path, d,
                    round(d / total_lessons * 100), u.created_at, u.last_seen, u.is_active])
    return Response(content=buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=craxle-students.csv"})


# ---------------------------- admin: content ------------------------------
@app.get("/api/admin/content")
def admin_content(user: User = Depends(admin_user), db: Session = Depends(get_db)):
    tracks = db.query(Track).order_by(Track.position).all()
    return {"tracks": [serialise_track(t, include_unpublished=True) for t in tracks]}


@app.put("/api/admin/track/{slug}")
def admin_update_track(slug: str, body: TrackIn,
                       user: User = Depends(admin_user), db: Session = Depends(get_db)):
    t = db.query(Track).filter(Track.slug == slug).first()
    if not t:
        raise HTTPException(404, "Track not found")
    t.icon, t.name, t.level = body.icon, body.name, body.level
    t.color, t.weeks, t.lang, t.desc = body.color, body.weeks, body.lang, body.desc
    t.outcomes = json.dumps(body.outcomes)
    t.quiz = json.dumps(body.quiz)
    t.published, t.position = body.published, body.position
    db.commit()
    return {"ok": True}


@app.put("/api/admin/lesson/{slug}")
def admin_update_lesson(slug: str, body: LessonIn,
                        user: User = Depends(admin_user), db: Session = Depends(get_db)):
    l = db.query(Lesson).filter(Lesson.slug == slug).first()
    if not l:
        raise HTTPException(404, "Lesson not found")
    l.title, l.mins, l.lang = body.title, body.mins, body.lang
    l.content = body.content
    l.videos = json.dumps(body.videos)
    l.refs = json.dumps(body.refs)
    l.lab = json.dumps(body.lab)
    l.exercises = json.dumps(body.exercises)
    l.worksheet = json.dumps(body.worksheet)
    l.published, l.position = body.published, body.position
    db.commit()
    return {"ok": True}


@app.post("/api/admin/lesson")
def admin_create_lesson(body: LessonIn, user: User = Depends(admin_user),
                        db: Session = Depends(get_db)):
    if not body.track:
        raise HTTPException(400, "A track is required")
    t = db.query(Track).filter(Track.slug == body.track).first()
    if not t:
        raise HTTPException(404, "Track not found")
    slug = f"{body.track}-{secrets.token_hex(3)}"
    pos = body.position or (max([l.position for l in t.lessons], default=-1) + 1)
    db.add(Lesson(slug=slug, track_id=t.id, title=body.title, mins=body.mins,
                  lang=body.lang, content=body.content,
                  videos=json.dumps(body.videos), refs=json.dumps(body.refs),
                  lab=json.dumps(body.lab),
                  exercises=json.dumps(body.exercises),
                  worksheet=json.dumps(body.worksheet),
                  position=pos, published=body.published))
    db.commit()
    return {"slug": slug}


@app.delete("/api/admin/lesson/{slug}")
def admin_delete_lesson(slug: str, user: User = Depends(admin_user),
                        db: Session = Depends(get_db)):
    l = db.query(Lesson).filter(Lesson.slug == slug).first()
    if not l:
        raise HTTPException(404, "Lesson not found")
    db.delete(l)
    db.commit()
    return {"ok": True}


@app.post("/api/admin/track")
def admin_create_track(body: TrackIn, user: User = Depends(admin_user),
                       db: Session = Depends(get_db)):
    slug = "track-" + secrets.token_hex(3)
    pos = body.position or ((db.query(func.max(Track.position)).scalar() or 0) + 1)
    db.add(Track(slug=slug, icon=body.icon, name=body.name, level=body.level,
                 color=body.color, weeks=body.weeks, lang=body.lang, desc=body.desc,
                 outcomes=json.dumps(body.outcomes), quiz=json.dumps(body.quiz),
                 position=pos, published=body.published))
    db.commit()
    return {"slug": slug}


@app.delete("/api/admin/track/{slug}")
def admin_delete_track(slug: str, user: User = Depends(admin_user),
                       db: Session = Depends(get_db)):
    t = db.query(Track).filter(Track.slug == slug).first()
    if not t:
        raise HTTPException(404, "Track not found")
    db.delete(t)
    db.commit()
    return {"ok": True}


# ---------------------------- worksheets ----------------------------------
WORKSHEET_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Georgia,'Times New Roman',serif;font-size:12pt;line-height:1.65;
     color:#111;background:#fff;max-width:800px;margin:0 auto;padding:30px 34px}
.head{border-bottom:3px solid #111;padding-bottom:14px;margin-bottom:8px}
.head h1{font-size:20pt;letter-spacing:-.5px}
.head .sub{font-size:10pt;color:#555;margin-top:3px}
.meta{display:flex;gap:26px;font-size:10pt;margin:16px 0 24px;
      border-bottom:1px solid #bbb;padding-bottom:14px}
.meta span{flex:1}
.meta b{font-weight:normal;color:#666}
.q{margin-bottom:20px;page-break-inside:avoid}
.q .n{font-weight:bold;float:left;width:26px}
.q .t{margin-left:26px}
.q .t p{white-space:pre-wrap}
.lines{margin:8px 0 0 26px}
.lines div{border-bottom:1px solid #ccc;height:24px}
.ans{margin-left:26px;margin-top:6px;padding:9px 12px;background:#f4f4f4;
     border-left:3px solid #888;font-size:10.5pt;white-space:pre-wrap;font-family:monospace}
.key{page-break-before:always;border-top:3px solid #111;padding-top:16px;margin-top:26px}
.key h2{font-size:15pt;margin-bottom:14px}
.foot{margin-top:34px;padding-top:12px;border-top:1px solid #bbb;
      font-size:9pt;color:#777;text-align:center}
.bar{background:#f0f0f0;border:1px solid #ccc;padding:11px 15px;margin-bottom:20px;
     font-size:10.5pt;border-radius:5px}
.bar a{color:#0645ad;margin-right:14px}
@media print{ .bar{display:none} body{padding:0} @page{margin:16mm} }
"""


def _worksheet_html(lesson: Lesson, track: Track, with_answers: bool, lines: int = 4):
    qs = json.loads(lesson.worksheet or "[]")
    if not qs:
        return "<p>This lesson has no worksheet.</p>"

    def esc(s):
        return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    body = []
    for i, item in enumerate(qs, 1):
        block = [f'<div class="q"><span class="n">{i}.</span><div class="t">'
                 f'<p>{esc(item.get("q", ""))}</p></div>']
        if with_answers:
            block.append(f'<div class="ans">{esc(item.get("a", ""))}</div>')
        else:
            block.append('<div class="lines">' + ('<div></div>' * lines) + '</div>')
        block.append('</div>')
        body.append("".join(block))

    title = "ANSWER KEY - " + lesson.title if with_answers else lesson.title
    other = ("worksheet" if with_answers else "answers")
    other_label = ("Student version" if with_answers else "Answer key (teachers)")

    meta = ("" if with_answers else
            '<div class="meta"><span><b>Name:</b> ________________________</span>'
            '<span><b>Class:</b> ____________</span>'
            '<span><b>Date:</b> ____________</span></div>')

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>{esc(title)}</title><style>{WORKSHEET_CSS}</style></head><body>
<div class="bar">
  <a href="javascript:window.print()">Print / Save as PDF</a>
  <a href="/worksheet/{lesson.slug}?{other}=1">{other_label}</a>
  <a href="/">Back to Craxle</a>
</div>
<div class="head">
  <h1>{esc(title)}</h1>
  <div class="sub">{esc(track.icon)} {esc(track.name)} &middot; {len(qs)} questions
    &middot; Craxle</div>
</div>
{meta}
{"".join(body)}
<div class="foot">Craxle &middot; Free to print and photocopy for classroom use</div>
</body></html>"""


@app.get("/worksheet/{slug}")
def worksheet(slug: str, answers: int = 0, worksheet: int = 0,
              db: Session = Depends(get_db)):
    """Printable worksheet. Public so teachers can print without signing in."""
    l = db.query(Lesson).filter(Lesson.slug == slug).first()
    if not l:
        raise HTTPException(404, "Lesson not found")
    t = db.get(Track, l.track_id)
    show_answers = bool(answers) and not worksheet
    return Response(content=_worksheet_html(l, t, show_answers),
                    media_type="text/html")


# ---------------------------- certificates --------------------------------
STAGE_NAMES = {
    "school":  "Stage 1 — Absolute Beginner",
    "stage2":  "Stage 2 — Getting Fluent in Python",
    "stage3a": "Stage 3 — Databases & SQL",
    "stage3b": "Stage 4 — Data Analysis",
    "stage4":  "Stage 5 — Machine Learning & AI Engineering",
    "graduate": "Stage 6 — Languages & Career",
}

CERT_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Georgia,'Times New Roman',serif;background:#efece6;
     display:grid;place-items:center;min-height:100vh;padding:24px}
.cert{background:#fffdf8;width:100%;max-width:880px;border:3px solid #b4530a;
      box-shadow:0 20px 60px rgba(0,0,0,.15);padding:26px;text-align:center}
.inner{border:1px solid #d9b48a;padding:48px 40px}
.brand{font-size:13px;letter-spacing:5px;color:#b4530a;font-weight:700}
h1{font-size:32px;margin:20px 0 4px;letter-spacing:1px;font-weight:600}
.sub{color:#8a8a86;font-size:11.5px;letter-spacing:2.5px;text-transform:uppercase}
.name{font-size:38px;margin:30px 0 6px;font-style:italic}
.rule{width:320px;max-width:80%;border-top:1px solid #aaa;margin:0 auto 22px}
.body{font-size:15px;color:#4a4a46;max-width:560px;margin:0 auto;line-height:1.75}
.stagename{font-size:20px;font-weight:700;color:#b4530a;margin:16px 0 4px}
.detail{font-size:13px;color:#8a8a86}
.meta{display:flex;justify-content:space-between;margin-top:48px;
      font-size:12px;color:#6b6b66;padding:0 20px}
.meta b{display:block;font-size:13px;color:#333;font-weight:600;margin-bottom:2px;
        border-top:1px solid #999;padding-top:7px;min-width:150px}
.btnp{position:fixed;top:18px;right:18px;padding:10px 20px;background:#b4530a;
      color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:14px;
      font-family:inherit}
@media print{.btnp{display:none}body{background:#fff;padding:0}
  .cert{box-shadow:none;border-width:3px}@page{size:landscape;margin:10mm}}
"""


def _esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


@app.get("/certificate/{stage_key}")
def certificate(stage_key: str, user: User = Depends(current_user),
                db: Session = Depends(get_db)):
    if stage_key not in STAGE_NAMES:
        raise HTTPException(404, "Unknown stage")

    tracks = db.query(Track).filter(
        Track.audience == stage_key, Track.published == True).all()  # noqa: E712
    slugs = [l.slug for t in tracks for l in t.lessons if l.published]
    if not slugs:
        raise HTTPException(404, "This stage has no lessons")

    done = {r.lesson_slug for r in db.query(Progress).filter(
        Progress.user_id == user.id, Progress.completed == True)}  # noqa: E712
    remaining = [s for s in slugs if s not in done]

    if remaining:
        return Response(content=f"""<!DOCTYPE html><html><head>
<meta charset="utf-8"><title>Not yet</title><style>{CERT_CSS}</style></head>
<body><div class="cert"><div class="inner">
<div class="brand">VIDYAPATH</div>
<h1>Almost there</h1>
<p class="body" style="margin-top:18px">
You have completed <b>{len(slugs) - len(remaining)} of {len(slugs)}</b> lessons in
<b>{_esc(STAGE_NAMES[stage_key])}</b>.<br><br>
Finish the remaining {len(remaining)} and this page becomes your certificate.</p>
<p style="margin-top:26px"><a href="/" style="color:#b4530a">Back to lessons</a></p>
</div></div></body></html>""", media_type="text/html")

    n_ex = 0
    for t in tracks:
        for l in t.lessons:
            n_ex += len(json.loads(l.exercises or "[]"))

    date_str = now().strftime("%d %B %Y")
    return Response(content=f"""<!DOCTYPE html><html><head>
<meta charset="utf-8"><title>Certificate — {_esc(user.name)}</title>
<style>{CERT_CSS}</style></head><body>
<button class="btnp" onclick="window.print()">Print / Save as PDF</button>
<div class="cert"><div class="inner">
<div class="brand">VIDYAPATH</div>
<h1>Certificate of Completion</h1>
<div class="sub">This certifies that</div>
<div class="name">{_esc(user.name)}</div>
<div class="rule"></div>
<p class="body">has successfully completed every lesson and exercise in</p>
<div class="stagename">{_esc(STAGE_NAMES[stage_key])}</div>
<div class="detail">{len(slugs)} lessons &middot; {n_ex} hands-on exercises
&middot; all auto-graded work passed</div>
<div class="meta">
  <div><b>{date_str}</b>Date of completion</div>
  <div><b>Craxle</b>Learn to code, then build with AI</div>
</div>
</div></div></body></html>""", media_type="text/html")


# ---------------------------- static files --------------------------------
# Served explicitly. Without these, requests fall through to the catch-all
# 404 handler and get index.html back, which breaks silently in the browser.
STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js":   "application/javascript",
    ".css":  "text/css",
    ".json": "application/json",
    ".svg":  "image/svg+xml",
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".ico":  "image/x-icon",
    # A browser will not treat a page as installable if its manifest comes
    # back as anything else, and the failure is silent — the install button
    # simply never appears, which on a smart board is the whole feature.
    ".webmanifest": "application/manifest+json",
}


@app.get("/{filename}.{ext}")
def static_file(filename: str, ext: str):
    suffix = "." + ext.lower()
    if suffix not in STATIC_TYPES:
        raise HTTPException(404, "Not found")

    # Resolve and confirm the file really sits in our own directory,
    # so a crafted name cannot reach outside it.
    path = (BASE_DIR / f"{filename}{suffix}").resolve()
    if path.parent != BASE_DIR.resolve() or not path.is_file():
        raise HTTPException(404, "Not found")

    return FileResponse(path, media_type=STATIC_TYPES[suffix])


# ---------------------------- static pages --------------------------------
@app.get("/")
def index():
    # An institution running its own server gets its own app at the root.
    # Anything else would mean the first thing a classroom sees is the job
    # board it did not buy.
    if CRAXLEARN_ONLY:
        return FileResponse(BASE_DIR / "craxlearn.html")
    return FileResponse(BASE_DIR / "index.html")


@app.get("/terms")
def terms_page():
    """Extensionless alias. Without this the catch-all served index.html here,
    so the URL returned 200 while showing the app instead of the document —
    which is what a payment processor sees when it reviews the policy."""
    return FileResponse(BASE_DIR / "terms.html")


@app.get("/privacy")
def privacy_page():
    return FileResponse(BASE_DIR / "privacy.html")


@app.get("/reset")
def reset_page():
    """The reset link lands here; the page reads ?token= and calls the API."""
    return FileResponse(BASE_DIR / "index.html")


@app.get("/admin")
def admin_page():
    return FileResponse(BASE_DIR / "admin.html")


@app.get("/craxlearn")
def craxlearn_page():
    """The institution app. A separate page, like the admin panel.

    Separate rather than a mode of the main app, because that is what a
    school is actually buying: a URL you can put on the board at the front
    of a classroom and hand to a fourteen-year-old, with nothing on it that
    is not teaching. A single app with the job half hidden is one bug away
    from showing it, and the person who finds that bug is a child.
    """
    return FileResponse(BASE_DIR / "craxlearn.html")


@app.exception_handler(404)
def not_found(request: Request, exc):
    if request.url.path.startswith("/api/"):
        # An endpoint that raised HTTPException(404, "...") wrote that
        # sentence on purpose, and this handler used to throw all of them
        # away and answer "Not found" — so "no learner of yours has that id"
        # and "there is no measured structure for that" both arrived as two
        # useless words. The generic text is for a path that matched no
        # route at all, which is the only case that has nothing to say.
        detail = getattr(exc, "detail", None)
        return JSONResponse({"detail": detail or "Not found"}, status_code=404)
    # On a Craxlearn-only server the main app is not what anybody typing a
    # wrong URL wanted, and serving it would put a job board in front of a
    # classroom by way of a typo.
    if CRAXLEARN_ONLY:
        return FileResponse(BASE_DIR / "craxlearn.html")
    return FileResponse(BASE_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(env("PORT", "8000")))
