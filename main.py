"""
Craxle — backend
FastAPI + SQLAlchemy. Postgres on Railway, SQLite locally.

Run locally:   uvicorn main:app --reload
Then open:     http://localhost:8000
Admin panel:   http://localhost:8000/admin
"""

import os
import json
import secrets
import datetime as dt
from pathlib import Path
from typing import Optional, List

import bcrypt
import jwt
import base64
import io
import hashlib
import hmac
import time
import httpx
from urllib.parse import urlencode
from fastapi import (FastAPI, Depends, HTTPException, Request, Response, status,
                     UploadFile, File, BackgroundTasks)
from fastapi.responses import (FileResponse, JSONResponse, RedirectResponse,
                               Response as RawResponse)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, Boolean, DateTime, Date,
    ForeignKey, UniqueConstraint, func, cast, case,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship

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

# Verified against /api/ai/selftest. Check any new model ID there before
# changing this: a wrong ID does not fail loudly — the provider fallback
# quietly serves every request from Groq instead, at Groq's cost.
GEMINI_MODEL = env("GEMINI_MODEL", "gemini-2.5-flash-lite")
# Used only where the writing quality is the product: the apply kit's
# cover note and screening answers. Everything else stays on the cheap
# model, because scoring and classifying do not read any better on a
# stronger one. Check /api/ai/models for what this key can use.
GEMINI_MODEL_BEST = env("GEMINI_MODEL_BEST", GEMINI_MODEL)
GROQ_MODEL = env("GROQ_MODEL", "llama-3.3-70b-versatile")
ANTHROPIC_MODEL = env("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")

AI_PROVIDER = env("AI_PROVIDER").lower().strip()
if AI_PROVIDER not in ("gemini", "groq", "claude", "anthropic"):
    if GEMINI_API_KEY:
        AI_PROVIDER = "gemini"
    elif GROQ_API_KEY:
        AI_PROVIDER = "groq"
    elif ANTHROPIC_API_KEY:
        AI_PROVIDER = "claude"
    else:
        AI_PROVIDER = "none"
if AI_PROVIDER == "anthropic":
    AI_PROVIDER = "claude"

_PROVIDER_KEY = {"gemini": GEMINI_API_KEY, "groq": GROQ_API_KEY,
                 "claude": ANTHROPIC_API_KEY}.get(AI_PROVIDER, "")
_PROVIDER_MODEL = {"gemini": GEMINI_MODEL, "groq": GROQ_MODEL,
                   "claude": ANTHROPIC_MODEL}.get(AI_PROVIDER, "")
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
    plan_provider = Column(String(20), default="")          # razorpay | stripe
    plan_ref = Column(String(120), default="")              # subscription id
    plan_expires = Column(DateTime(timezone=True))
    plan_started = Column(DateTime(timezone=True))
    # Two-factor. Off by default: making it compulsory at signup costs more
    # accounts than it protects, at this size.
    totp_secret = Column(String(64), default="")
    totp_enabled = Column(Boolean, default=False, nullable=False)
    totp_backup = Column(Text, default="")     # hashed single-use codes


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
    subject = Column(String(60), default="")
    level = Column(String(60), default="")
    question = Column(Text, default="")
    lesson = Column(Text, default="{}")     # JSON: {title, steps[], takeaway}
    hits = Column(Integer, default=0)       # how many times served from cache
    created_at = Column(DateTime(timezone=True), default=now)


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
TRACK_STATUSES = ["saved", "applied", "interviewing", "offer", "rejected", "archived"]
TRACK_LABELS = {"saved": "Saved", "applied": "Applied", "interviewing": "Interviewing",
                "offer": "Offer received", "rejected": "Rejected", "archived": "Archived"}


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
    engagement = Column(String(10), default="", index=True)  # w2 / c2c / 1099
    visa = Column(String(20), default="", index=True)        # sponsors/no/clearance
    url = Column(Text, default="")
    text = Column(Text, default="")          # lowercased title+desc, for search
    # Skills extracted once at ingest. Re-deriving these from `text` at match
    # time meant tokenising 5,000 full descriptions per request, which took
    # over 30 seconds; reading a short CSV column is instant.
    skills = Column(Text, default="")        # comma-joined skill tokens
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
    created_at = Column(DateTime(timezone=True), default=now)
    updated_at = Column(DateTime(timezone=True), default=now, onupdate=now)
    __table_args__ = (UniqueConstraint("assignment_id", "user_id", name="uq_sub_user"),)


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
    created_at = Column(DateTime(timezone=True), default=now)


RESET_TTL = dt.timedelta(hours=1)

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


MAX_DEVICES = int(env("MAX_DEVICES", "2") or 2)


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
            401, f"Signed out because this account is in use on more than "
                 f"{MAX_DEVICES} devices. Craxle allows {MAX_DEVICES} at a "
                 f"time — sign in again here to use this one.")
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
                    conn.execute(_text(
                        f'ALTER TABLE {table.name} ADD COLUMN {col.name} {coltype}'))
                print(f"migrated: added column {table.name}.{col.name}")
            except Exception as e:
                print(f"migrate note ({table.name}.{col.name}): {e}")


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
def _startup():
    """Boot the app. Database problems must NOT prevent startup.

    If the app fails to start, the platform's healthcheck has nothing to
    reach and the whole deploy is marked failed — with no way to see the
    error. Better to start, serve /api/health, and report the problem
    through /api/status where it can actually be read.
    """
    global STARTUP_ERROR
    print("=" * 56)
    print(f"  Craxle  v{VERSION}  (commit {GIT_SHA})")
    print(f"  started {BUILT_AT}")
    print("=" * 56)

    # Postgres often is not accepting connections the instant we boot.
    import time
    for attempt in range(1, 6):
        try:
            seed_if_empty()
            STARTUP_ERROR = None
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
def signup(body: SignupIn, response: Response, db: Session = Depends(get_db)):
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

    set_session(response, user, db)
    return {"id": user.id, "name": user.name, "email": user.email,
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
            "is_admin": user.is_admin, "is_teacher": bool(t) or user.is_admin,
            "is_head": is_head(user, db)}


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
                           "nallaputhirumal123@gmail.com and we'll reset it."}
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
    row = db.query(PasswordReset).filter(PasswordReset.token_hash == h).first()
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
        user = User(email=email, name=name[:120],
                    password_hash=hash_pw(secrets.token_urlsafe(24)),
                    is_admin=(email == ADMIN_EMAIL))
        db.add(user)
    else:
        user.last_seen = now()
        if email == ADMIN_EMAIL and not user.is_admin:
            user.is_admin = True
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


@app.get("/api/auth/me")
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    t = teacher_row(user, db)
    role = "admin" if user.is_admin else (t.role if t else "student")
    return {
        "id": user.id, "name": user.name, "email": user.email,
        "is_admin": user.is_admin, "path": user.path,
        "is_teacher": bool(t) or user.is_admin,
        "is_head": is_head(user, db),
        "role": role,
        "school": (t.school if t else ""),
        "joined": user.created_at.isoformat() if user.created_at else None,
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
    my_subs = {r[0] for r in db.query(Submission.assignment_id)
               .filter(Submission.user_id == user.id).all()}
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
            "assignments": [{**_asg_json(a, a.id in my_subs)} for a in assignments],
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
            "submitted_at": sub.updated_at.isoformat() if sub and sub.updated_at else None}


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
        students.append({"id": u.id, "name": u.name,
                         "response": s.response if s else "",
                         "submitted": bool(s),
                         "at": s.updated_at.isoformat() if s and s.updated_at else None})
    students.sort(key=lambda r: (not r["submitted"], r["name"].lower()))
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


class AskIn(BaseModel):
    question: str = Field(..., min_length=2, max_length=500)
    subject: str = Field("General", max_length=60)
    level: str = Field("School", max_length=60)


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
    "free": {"name": "Free", "ai_total": 10, "kits_total": 3,
             "inr": None, "usd": None},
    "basic": {"name": "Basic", "ai_month": 100, "kits_month": 30,
              "inr_month": 44900, "usd_month": 1099,
              "inr_year": None, "usd_year": None},
    # Pro must cost more than Basic in both currencies, or nobody has a reason
    # to choose it. The annual price is deliberately below 12x monthly: a
    # job-seeker subscription usually churns at 2-3 months, and annual is the
    # only thing that changes that.
    "pro": {"name": "Pro", "ai_month": None, "kits_month": None,   # None = unlimited
            "inr_month": 74900, "usd_month": 1599,
            "inr_year": 349900, "usd_year": 10000},
}
# Free-tier allowances are lifetime totals, not daily: someone must be able to
# try the product properly once, not a little every day forever.
PAID_PLANS = ("basic", "pro")


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
    if plan == "basic":
        used = _ai_used_month(db, user)
        lim = PLANS["basic"]["ai_month"]
        return {"plan": plan, "limit": lim, "used": used,
                "left": max(0, lim - used), "period": "month"}
    used = _ai_used_total(db, user)
    lim = PLANS["free"]["ai_total"]
    return {"plan": "free", "limit": lim, "used": used,
            "left": max(0, lim - used), "period": "total"}


def _ai_enforce_limit(db, user):
    if getattr(user, "is_admin", False):
        return
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


def _ai_cache_key(prefix, *parts):
    import hashlib
    h = hashlib.sha256("||".join(p or "" for p in parts).encode("utf-8", "ignore")).hexdigest()
    return f"{prefix}:{h}"


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


def _ai_error_message(e):
    """Turn a raw upstream error into a friendly message for the user. Rate
    limits (very common on free AI tiers) get their own clear explanation."""
    s = str(e).lower()
    if "429" in s or "rate limit" in s or "tokens per day" in s or "quota" in s:
        return ("The free AI limit has been reached for now. It refreshes shortly "
                "(short bursts free up in about a minute; the daily pool resets "
                "each day). Please try again in a little while.")
    return "The AI could not respond just now. Please try again in a moment."


def _providers_in_order():
    """Providers to try, in order: the configured one first, then any others
    that also have a key — so if one is rate-limited we fall back to the next."""
    keyed = {"gemini": GEMINI_API_KEY, "groq": GROQ_API_KEY, "claude": ANTHROPIC_API_KEY}
    order = [AI_PROVIDER] + [p for p in ("gemini", "groq", "claude") if p != AI_PROVIDER]
    return [p for p in order if keyed.get(p)]


async def _provider_generate(client, provider, prompt, max_tokens, json_mode=False,
                             best=False):
    """One raw generation call to a single provider. Raises on HTTP error."""
    if provider == "gemini":
        gen = {"maxOutputTokens": max_tokens, "temperature": 0.4}
        if json_mode:
            gen["responseMimeType"] = "application/json"
        model = GEMINI_MODEL_BEST if best else GEMINI_MODEL
        # Gemini models from 2.5 onwards do internal "thinking" that is billed
        # against the same output budget. Left on, it can consume the whole
        # allowance and return no visible text at all — which reaches the user
        # as "the AI could not respond". None of these tasks benefit from it.
        if _re.match(r"gemini-(2\.5|[3-9]|\d{2})", model):
            gen["thinkingConfig"] = {"thinkingBudget": 0}
        r = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            headers={"x-goog-api-key": GEMINI_API_KEY, "content-type": "application/json"},
            json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": gen})
        _upstream_ok(r, "gemini")
        return "".join(p.get("text", "") for c in r.json().get("candidates", [])
                       for p in c.get("content", {}).get("parts", [])).strip()
    if provider == "groq":
        body = {"model": GROQ_MODEL, "max_tokens": max_tokens, "temperature": 0.4,
                "messages": [{"role": "user", "content": prompt}]}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        r = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "content-type": "application/json"},
            json=body)
        _upstream_ok(r, "groq")
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


async def _ai_text(prompt: str, max_tokens: int = 1500, json_mode: bool = False,
                   best: bool = False) -> str:
    """Generate text, trying each available provider in turn. If one is rate-
    limited or errors, automatically fall back to the next configured provider."""
    import httpx
    providers = _providers_in_order()
    if not providers:
        raise RuntimeError("No AI provider key is configured")
    last = None
    async with httpx.AsyncClient(timeout=60) as client:
        for prov in providers:
            try:
                txt = await _provider_generate(client, prov, prompt, max_tokens,
                                               json_mode, best)
                if txt:
                    return txt
                last = RuntimeError(f"{prov} returned no text")
            except Exception as e:
                last = e
                print(f"AI provider '{prov}' failed, trying next: {type(e).__name__}: {e}")
                continue
    raise last if last else RuntimeError("AI generation failed")


async def _call_model(question: str, subject: str, level: str) -> dict:
    """Build an Ask-Axle lesson, with automatic provider fallback."""
    prompt = _ask_prompt(question, subject, level)
    text = await _ai_text(prompt, 1500, json_mode=True)
    if not text:
        raise RuntimeError("AI returned no text")
    return _parse_lesson(text, question)


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
    raise ValueError(f"Model did not return JSON. First 200 chars: {raw[:200]!r}")


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
    ckey = _ai_cache_key("rmatch", rtext, jd[:3500])
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
                       user: User = Depends(current_user)):
    """Read an existing resume file and let the AI structure it into the
    builder's sections — so the student starts from what they already have."""
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
    return out


@app.post("/api/resume/extract")
async def resume_extract(file: UploadFile = File(...),
                         user: User = Depends(current_user)):
    """Read an uploaded resume and return its plain text — used only to score it
    against a job description and to suggest changes. It does not build or edit
    anything."""
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
    return {"text": text[:40000], "name": (file.filename or "resume")[:120]}


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
async def ai_selftest(user: User = Depends(admin_user)):
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
                gen = {"maxOutputTokens": tokens, "temperature": 0.4}
                if model.startswith("gemini-2.5"):
                    gen["thinkingConfig"] = {"thinkingBudget": 0}
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

    short = await probe("short", GEMINI_MODEL, 20, "Reply with exactly: OK")
    long_prompt = ("Return ONLY valid JSON: {\"summary\":\"<two sentences about a "
                   "network engineer>\",\"bullets\":[\"a\",\"b\",\"c\"]}")
    long = await probe("long", GEMINI_MODEL_BEST, 1200, long_prompt)
    return {**info, "ok": bool(short.get("ok") and long.get("ok")),
            "short_call": short, "apply_kit_style_call": long}


@app.post("/api/ask")
async def ask_vidya(body: AskIn, user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    subject = (body.subject or "General").strip()[:60]
    level = (body.level or "School").strip()[:60]
    question = body.question.strip()
    qkey = f"{_norm_q(subject)}|{_norm_q(level)}|{_norm_q(question)}"[:500]

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

    db.add(AskCache(qkey=qkey, subject=subject, level=level,
                    question=question[:2000], lesson=json.dumps(lesson), hits=0))
    db.commit()
    return {"lesson": lesson, "cached": False}


# ---------------------------- live jobs -----------------------------------
# Jobs come from the PUBLIC APIs that companies' own career pages are built
# on (Greenhouse, Lever, Ashby, Workable, Recruitee). They are the real
# postings, straight from the employer, free and without an API key. We never
# scrape LinkedIn/Indeed/Naukri: that breaks their terms and gets blocked.

JOB_RETENTION_DAYS = 7          # how much history we keep, per the spec
JOB_REFRESH_HOURS = 24          # daily refresh

# Board tokens. A company that renames or leaves its ATS simply stops
# returning rows — the fetcher skips it silently and the rest still work.
# Extend without touching code: JOB_GREENHOUSE="stripe,figma,..." etc.
_GREENHOUSE = ("stripe,figma,databricks,cloudflare,coinbase,robinhood,dropbox,"
               "reddit,discord,brex,instacart,lyft,pinterest,twilio,asana,"
               "samsara,affirm,chime,flexport,gitlab,airtable,amplitude,"
               "mixpanel,vercel,scaleai,duolingo,gusto,carta,squarespace,"
               "fivetran,verkada,checkr,betterment,elastic,mongodb,postman,"
               "airbnb,datadog")
_LEVER = "palantir,cred,meesho,nium,matchgroup"
_ASHBY = ("openai,ramp,linear,vanta,replit,clickhouse,supabase,cursor,"
          "elevenlabs,decagon,mercor,sierra,suno,perplexity,zed,harvey,modal,"
          "warp,browserbase,lovable,synthesia,cognition,fireworksai,baseten,"
          "langchain,n8n")
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

_SMARTRECRUITERS = "Visa"


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
    if _re.search(r"(no (visa )?sponsorship|not able to sponsor|unable to sponsor|"
                  r"without sponsorship|cannot sponsor|no c2c|us citizens? only|"
                  r"green card holders? only|citizens? or green card)", blob):
        return "no_sponsorship"
    if _re.search(r"\b(h-?1b|h1-b|opt\b|cpt\b|ead\b|tn visa|e-?3 visa|"
                  r"visa sponsorship( is)? available|will sponsor|"
                  r"sponsorship (is )?(available|provided|offered))\b", blob):
        return "sponsors"
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
        "visa": _visa_of(blob),
        "skills": ",".join(sorted({w for w in _words(blob) if w in _SKILLS})),
        "url": url[:1000], "text": blob,
        "posted_at": posted,
    }


def _ts(v):
    """Parse the assorted timestamp shapes the ATS feeds use."""
    if not v:
        return None
    try:
        if isinstance(v, (int, float)):
            return dt.datetime.fromtimestamp(v / (1000 if v > 1e11 else 1), dt.timezone.utc)
        return dt.datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except Exception:
        return None


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


WORKDAY_PAGES = int(env("WORKDAY_PAGES", "15") or 15)   # 20 postings a page


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

# Adzuna country codes. Override with ADZUNA_COUNTRIES="in,gb,us".
ADZUNA_COUNTRIES = env("ADZUNA_COUNTRIES",
                       "in,us,gb,ca,au,de,fr,nl,sg,za,nz,pl,it,es,br,mx").split(",")
ADZUNA_PAGES = int(env("ADZUNA_PAGES", "3") or 3)     # 50 results per page

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
    "arbeitnow": _fetch_arbeitnow,
    "remotive": _fetch_remotive, "remoteok": _fetch_remoteok,
    "jobicy": _fetch_jobicy, "himalayas": _fetch_himalayas,
}


async def _fetch_jooble(client, country):
    r = await client.post(f"https://jooble.org/api/{JOOBLE_KEY}",
                          json={"keywords": "", "location": country, "page": "1"})
    r.raise_for_status()
    out = []
    for j in (r.json().get("jobs") or []):
        row = _job_row("jooble", j.get("id") or j.get("link"), j.get("title"),
                       j.get("company", ""), j.get("location", "") or country,
                       j.get("link", ""), j.get("snippet", ""), _ts(j.get("updated")))
        if row:
            row["country"] = row["country"] or country
            out.append(row)
    return out


async def _collect_jobs():
    """Hit every configured board once.

    Returns (rows, report, reached) where `reached` is the set of boards that
    genuinely answered. Closing jobs is driven by `reached`, never by the rows
    alone — otherwise one board timing out would look exactly like that
    employer taking every posting down."""
    import httpx
    rows, report, reached = [], {}, set()
    async with httpx.AsyncClient(
            timeout=25, follow_redirects=True,
            headers={"User-Agent": "Craxle/1.0 (job board reader)"}) as client:
        for source, fetch in _FETCHERS.items():
            for token in _job_tokens(source):
                try:
                    got = [r for r in await fetch(client, token) if r]
                    rows += got
                    reached.add((source, token))
                    report[f"{source}:{token}"] = len(got)
                except Exception as e:
                    report[f"{source}:{token}"] = f"{type(e).__name__}"

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
    return rows, report, reached


# Sources we have switched off. Their rows must be deleted outright: a
# retired source never appears in a crawl, so the "vanished from the board"
# rule never fires and the rows would sit there as open forever.
RETIRED_SOURCES = ("themuse",)


def _store_jobs(db, rows, reached):
    """Upsert this crawl, close postings that vanished, drop old history."""
    gone = db.query(Job).filter(Job.source.in_(RETIRED_SOURCES)).delete(
        synchronize_session=False)
    if gone:
        db.commit()
        print(f"jobs: removed {gone} rows from retired sources "
              f"({', '.join(RETIRED_SOURCES)})")
    seen, added, updated = set(), 0, 0
    for r in rows:
        seen.add((r["source"], r["external_id"]))
        row = db.query(Job).filter(Job.source == r["source"],
                                   Job.external_id == r["external_id"]).first()
        if row:
            row.title, row.company = r["title"], r["company"]
            row.location, row.country = r["location"], r["country"]
            row.remote, row.url, row.text = r["remote"], r["url"], r["text"]
            row.category, row.skills = r["category"], r["skills"]
            row.job_type, row.engagement = r["job_type"], r["engagement"]
            row.visa = r["visa"]
            row.last_seen, row.is_open, row.closed_at = now(), True, None
            updated += 1
        else:
            db.add(Job(**r, first_seen=now(), last_seen=now(), is_open=True))
            added += 1
    db.commit()

    # A posting we did not see, on a board we DID reach, has come off that
    # career site — mark it closed so the user can still see it went.
    closed = 0
    for row in db.query(Job).filter(Job.is_open == True).all():  # noqa: E712
        if ((row.source, row.company) in reached
                and (row.source, row.external_id) not in seen):
            row.is_open, row.closed_at = False, now()
            closed += 1
    cutoff = now() - dt.timedelta(days=JOB_RETENTION_DAYS)
    pruned = db.query(Job).filter(Job.last_seen < cutoff).delete(
        synchronize_session=False)
    db.commit()
    return {"added": added, "updated": updated, "closed": closed, "pruned": pruned}


async def _refresh_jobs():
    rows, report, reached = await _collect_jobs()
    db = SessionLocal()
    try:
        stats = _store_jobs(db, rows, reached)
    finally:
        db.close()
    print(f"jobs refresh: {stats} from {len(rows)} rows, {len(reached)} boards")
    return {**stats, "fetched": len(rows), "boards_reached": len(reached),
            "sources": report}


async def _jobs_loop():
    """Refresh on boot, then once a day. One instance, no extra dependency."""
    import asyncio
    while True:
        try:
            await _refresh_jobs()
        except Exception as e:
            print(f"jobs refresh failed: {type(e).__name__}: {e}")
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
    "network": ("network engineer", "network administrator", "noc ", "cisco",
                "routing", "switching", "bgp", "ospf", "sd-wan", "f5 ",
                "load balancer", "juniper", "palo alto", "network security"),
    "security": ("security engineer", "security analyst", "soc analyst",
                 "penetration test", "pentest", "infosec", "appsec",
                 "vulnerability", "threat", "cybersecurity"),
    "sysadmin": ("system administrator", "sysadmin", "it engineer",
                 "it support", "help desk", "helpdesk", "desktop support",
                 "it administrator", "windows administrator"),
    "devops": ("devops", "sre", "site reliability", "platform engineer",
               "infrastructure engineer", "cloud engineer", "release engineer"),
    "backend": ("backend", "back-end", "software engineer", "full stack",
                "fullstack", "api engineer", "server engineer", "golang engineer"),
    "frontend": ("frontend", "front-end", "ui engineer", "web developer",
                 "javascript engineer", "react engineer"),
    "mobile": ("android engineer", "ios engineer", "mobile engineer",
               "android developer", "ios developer"),
    "data": ("data engineer", "data analyst", "analytics engineer",
             "business intelligence", "etl developer", "data warehouse"),
    "ml": ("machine learning", "ml engineer", "data scientist", "ai engineer",
           "research scientist", "nlp engineer", "computer vision",
           "applied scientist"),
    "qa": ("qa engineer", "quality assurance", "test engineer", "sdet",
           "automation engineer", "test automation"),
    "product": ("product manager", "product owner", "program manager",
                "technical program", "product lead"),
    "design": ("designer", "ux ", "ui/ux", "product design", "graphic design"),
    "sales": ("account executive", "account manager", "sales ", "business development",
              "sales development", "solutions consultant", "revenue"),
    "marketing": ("marketing", "growth manager", "seo ", "content strategist",
                  "brand ", "demand generation"),
    "support": ("support engineer", "customer support", "technical support",
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
    "consulting": ("consultant", "business analyst", "strategy ", "management associate"),
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
_FAMILY_RE = {fam: [_re.compile(rf"(?<![a-z]){_re.escape(k.strip())}(?![a-z])")
                    for k in keys]
              for fam, keys in _ROLE_FAMILIES.items()}


def _families(text: str):
    """Which role families this text reads as. Empty when nothing is clear."""
    low = " " + (text or "").lower() + " "
    return {fam for fam, rxs in _FAMILY_RE.items()
            if any(rx.search(low) for rx in rxs)}


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
_JUNIOR = ("intern", "internship", "graduate", "trainee", "junior", "entry",
           "fresher", "apprentice", "associate")


def _job_skills(job):
    """The job's skills, from the column filled at ingest.

    Falls back to parsing the text for rows stored before that column
    existed, so an older database still matches until the next crawl."""
    if job.skills:
        return set(job.skills.split(","))
    return {w for w in _words(job.text or "") if w in _SKILLS}


def _score_job(job, skills, keywords, level, idf=None, my_fams=None):
    """0-100 fit score, plus the skills that matched and the ones missing.

    Two things keep this honest. Skills are weighted by how rare they are
    across the live postings, so matching 'kubernetes' counts for far more
    than matching 'git'. And the job's role family must line up with the
    resume's — without that gate, shared buzzwords alone rated a network
    engineer a perfect fit for a compliance product manager.
    """
    jskills = _job_skills(job)
    # Title words only. Scanning whole descriptions here cost 30s a request,
    # and the title is where the signal actually is.
    jwords = set(_words(job.title or ""))
    idf = idf or {}

    hit = skills & jskills
    miss = jskills - skills

    def w(s):
        base = idf.get(s, 1.0)
        return base * (0.25 if s in _WEAK_SKILLS else 1.0)

    want = sum(w(s) for s in jskills)
    have = sum(w(s) for s in hit)
    coverage = (have / want) if want else 0.0
    depth = min(have / 4.0, 1.0)          # absolute weight of what you matched
    kw_pct = len(keywords & jwords) / max(len(jwords), 1)

    score = 100 * (0.45 * coverage + 0.35 * depth + 0.20 * min(kw_pct * 1.6, 1.0))

    # A posting too thin to name a few skills can't support a confident score.
    if len(jskills) < 3:
        score *= 0.5

    title = (job.title or "").lower()
    # Read the family off the stored column. Re-deriving it here ran ~240
    # regexes per job, which was 26 of the 30 seconds a match took.
    job_fams = {job.category} if job.category else set()
    if my_fams and job_fams:
        if job_fams & my_fams:
            score += 10                                   # same line of work
        elif job_fams & {f for m in my_fams for f in _ADJACENT.get(m, set())}:
            score *= 0.80                                 # a sideways step
        else:
            score *= 0.35                                 # a different career

    if any(s in title for s in skills if s not in _WEAK_SKILLS):
        score += 6
    if level == "junior" and any(t in title for t in _SENIOR):
        score -= 22
    elif level == "senior" and any(t in title for t in _JUNIOR):
        score -= 18
    elif level == "junior" and any(t in title for t in _JUNIOR):
        score += 8
    elif level == "senior" and any(t in title for t in _SENIOR):
        score += 8
    return (max(0, min(100, round(score))), sorted(hit)[:12], sorted(miss)[:8])


def _level_of(resume_text: str):
    """Seniority, from job titles only.

    Held titles are checked first and degrees are ignored on purpose: almost
    every resume lists a B.Tech or a graduation, so treating those as junior
    signals labelled experienced people junior and docked their best matches.
    """
    low = (resume_text or "").lower()
    if any(t in low for t in ("senior ", "sr. ", "lead ", "principal ", "staff ",
                              "head of ", "manager", "architect")):
        return "senior"
    if any(t in low for t in ("intern", "fresher", "trainee", "recent graduate",
                              "currently studying", "final year")):
        return "junior"
    return ""


def _job_json(j, extra=None):
    d = {
        "id": j.id, "title": j.title, "company": j.company,
        "location": j.location or ("Remote" if j.remote else ""),
        "country": j.country, "remote": bool(j.remote), "url": j.url,
        "category": j.category or "", "is_open": bool(j.is_open),
        "job_type": j.job_type or "", "engagement": j.engagement or "",
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
                category="", job_type="", engagement="", visa="", posted=""):
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
        query = query.filter(Job.category == category.strip().lower())
    if country:
        query = query.filter(func.lower(Job.country) == country.strip().lower())
    if location:
        query = query.filter(func.lower(Job.location).like(f"%{location.strip().lower()}%"))
    if remote:
        query = query.filter(Job.remote == True)       # noqa: E712
    if q:
        like = f"%{q.strip().lower()}%"
        query = query.filter(func.lower(Job.title).like(like)
                             | func.lower(Job.company).like(like)
                             | func.lower(Job.text).like(like))
    return query


@app.get("/api/jobs")
def jobs_search(q: str = "", country: str = "", location: str = "",
                remote: bool = False, status: str = "open", limit: int = 20,
                offset: int = 0, category: str = "", job_type: str = "",
                engagement: str = "", visa: str = "", posted: str = "",
                user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Search the stored postings. Newest first."""
    query = _jobs_query(db, q, country, location, remote, status, category, job_type, engagement, visa, posted)
    if q:
        # Searching "engineer" must not put a sales role that merely mentions
        # engineers above an actual engineering job. Title hits rank first.
        query = query.order_by(
            case((func.lower(Job.title).like(f"%{q.strip().lower()}%"), 0), else_=1),
            Job.first_seen.desc())
    else:
        query = query.order_by(Job.first_seen.desc())
    off, lim = max(offset, 0), min(max(limit, 1), 50)
    total = _jobs_query(db, q, country, location, remote, status, category, job_type, engagement, visa, posted).count()
    rows = query.offset(off).limit(lim).all()
    out = [_job_json(j) for j in rows]
    _mark_tracked(db, user, out)
    return {"jobs": out, "total": total,
            "offset": off, "limit": lim, "has_more": off + lim < total}


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
        Job.is_open == True, Job.category != "")            # noqa: E712
    if country:
        query = query.filter(func.lower(Job.country) == country.strip().lower())
    rows = query.group_by(Job.category).all()
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
    return {
        "countries": [{"country": c, "count": n}
                      for c, n in sorted(rows, key=lambda x: -x[1])],
        "open": db.query(func.count(Job.id)).filter(Job.is_open == True).scalar(),  # noqa: E712
        "closed": db.query(func.count(Job.id)).filter(Job.is_open == False).scalar(),  # noqa: E712
        "updated": newest.isoformat() if newest else None,
        "retention_days": JOB_RETENTION_DAYS,
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


@app.post("/api/jobs/match")
def jobs_match(body: JobMatchIn, user: User = Depends(current_user),
               db: Session = Depends(get_db)):
    """Rank open jobs against the user's resume.

    Deliberately AI-free: scoring runs in Python over the stored postings, so
    it is instant, costs nothing, and never touches the daily AI limit."""
    import math
    rtext = (body.resume_text or "").strip() or _resume_text(body.resume or {})
    if len(rtext.strip()) < 40:
        raise HTTPException(400, "Add some resume details first, or upload a resume.")
    skills, keywords = _profile(rtext)
    if not skills:
        raise HTTPException(
            400, "We couldn't find recognisable skills in your resume. Add a "
                 "skills section (languages, tools, frameworks) and try again.")
    level = _level_of(rtext)
    my_fams = _families(rtext)
    rows = _jobs_query(db, body.q, body.country, body.location, body.remote,
                       "open", body.category, body.job_type, body.engagement,
                       body.visa, body.posted).order_by(Job.first_seen.desc()).limit(6000).all()

    # Rarity weights, measured on this very result set: a skill three quarters
    # of postings mention tells us almost nothing about fit.
    df, n = {}, max(len(rows), 1)
    for j in rows:
        for s in _job_skills(j):
            df[s] = df.get(s, 0) + 1
    idf = {s: math.log(n / (1 + c)) + 0.25 for s, c in df.items()}

    # One role open in three cities is three postings. Show it once, keeping
    # the best-scoring copy and listing the other places it is open.
    best = {}
    for j in rows:
        score, hit, miss = _score_job(j, skills, keywords, level, idf, my_fams)
        key = ((j.title or "").strip().lower(), (j.company or "").strip().lower())
        item = _job_json(j, {"score": score, "matched": hit, "missing": miss})
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

    off = max(body.offset, 0)
    lim = min(max(body.limit, 1), 50)
    page = scored[off:off + lim]
    _mark_tracked(db, user, page)
    return {"jobs": page, "scanned": len(rows), "total": len(scored),
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
def apply_pair_code(user: User = Depends(current_user)):
    """Mint a pairing code to type into the extension. Expires in 10 minutes."""
    _prune_pair_codes()
    code = "-".join(secrets.token_hex(2).upper() for _ in range(3))
    _PAIR_CODES[code] = (user.id, now() + PAIR_TTL)
    return {"code": code, "expires_in": int(PAIR_TTL.total_seconds())}


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

    exp = (r.get("exp") or [{}])[0] if r.get("exp") else {}
    edu = (r.get("edu") or [{}])[0] if r.get("edu") else {}
    full = str(r.get("name") or user.name or "").strip()
    first, _, last = full.partition(" ")
    return {
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


@app.get("/api/interview/guide")
def interview_guide(category: str = "", job_id: int = 0,
                    user: User = Depends(current_user),
                    db: Session = Depends(get_db)):
    """Interview prep for a role family, optionally anchored to one posting."""
    cat = (category or "").strip().lower()
    job = db.get(Job, job_id) if job_id else None
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

    ckey = _ai_cache_key("akit", rtext[:2500], str(job.id))
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
# Two gateways, one subscription state. Razorpay covers India, where UPI costs
# almost nothing to accept; Stripe covers everywhere else. The user's `plan` is
# only ever written by a signature-verified webhook — never by the browser,
# which could otherwise simply ask to be upgraded.
RAZORPAY_KEY_ID = env("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = env("RAZORPAY_KEY_SECRET")
RAZORPAY_WEBHOOK_SECRET = env("RAZORPAY_WEBHOOK_SECRET")
RAZORPAY_ENABLED = bool(RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET)

STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET")
STRIPE_ENABLED = bool(STRIPE_SECRET_KEY)

# Stripe Price IDs, created in the Stripe dashboard.
STRIPE_PRICES = {
    ("basic", "month"): env("STRIPE_PRICE_BASIC_MONTH"),
    ("pro", "month"): env("STRIPE_PRICE_PRO_MONTH"),
    ("pro", "year"): env("STRIPE_PRICE_PRO_YEAR"),
}


def _is_india(request: Request) -> bool:
    """Cloudflare tells us the country; fall back to India-off when it can't."""
    return (request.headers.get("cf-ipcountry") or "").upper() == "IN"


@app.get("/api/billing/plans")
def billing_plans(request: Request, user: User = Depends(current_user),
                  db: Session = Depends(get_db)):
    """What this user can buy, priced for where they are."""
    india = _is_india(request)
    cur = "inr" if india else "usd"
    sym = "₹" if india else "$"

    def money(v):
        return None if v is None else f"{sym}{v/100:,.0f}" if india else f"{sym}{v/100:,.2f}"

    out = []
    for pid in ("free", "basic", "pro"):
        p = PLANS[pid]
        out.append({
            "id": pid, "name": p["name"],
            "month": money(p.get(f"{cur}_month")),
            "year": money(p.get(f"{cur}_year")),
            "ai": ("Unlimited" if pid == "pro"
                   else f"{p.get('ai_total') or p.get('ai_month')} AI requests"
                        + (" to start" if pid == "free" else " a month")),
            "kits": ("Unlimited" if pid == "pro"
                     else f"{p.get('kits_total') or p.get('kits_month')} apply kits"
                          + (" to start" if pid == "free" else " a month")),
        })
    return {
        "plans": out, "currency": cur.upper(), "region": "IN" if india else "INTL",
        "gateway": "razorpay" if india else "stripe",
        "available": {"razorpay": RAZORPAY_ENABLED, "stripe": STRIPE_ENABLED},
        "current": plan_of(user),
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
            "expires": exp.isoformat() if exp else None,
            "quota": ai_quota(db, user)}


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
    if period not in ("month", "year"):
        raise HTTPException(400, "Unknown billing period")
    india = _is_india(request)

    if india:
        if not RAZORPAY_ENABLED:
            raise HTTPException(503, "Payments are not switched on yet.")
        amount = PLANS[plan].get(f"inr_{period}")
        if not amount:
            raise HTTPException(400, "That plan is not sold for that period")
        auth = base64.b64encode(
            f"{RAZORPAY_KEY_ID}:{RAZORPAY_KEY_SECRET}".encode()).decode()
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post("https://api.razorpay.com/v1/orders",
                             headers={"Authorization": f"Basic {auth}"},
                             json={"amount": amount, "currency": "INR",
                                   "notes": {"user_id": str(user.id),
                                             "plan": plan, "period": period}})
        if r.status_code >= 300:
            print("Razorpay order failed:", r.status_code, r.text[:300])
            raise HTTPException(502, "Could not start the payment. Try again.")
        o = r.json()
        return {"gateway": "razorpay", "key_id": RAZORPAY_KEY_ID,
                "order_id": o["id"], "amount": o["amount"], "currency": "INR",
                "name": "Craxle", "plan": plan, "period": period,
                "prefill": {"name": user.name, "email": user.email}}

    if not STRIPE_ENABLED:
        raise HTTPException(503, "Payments are not switched on yet.")
    price = STRIPE_PRICES.get((plan, period))
    if not price:
        raise HTTPException(400, "That plan is not sold for that period")
    base = PUBLIC_BASE_URL or str(request.base_url).rstrip("/")
    async with httpx.AsyncClient(timeout=20) as c:
        r = await c.post(
            "https://api.stripe.com/v1/checkout/sessions",
            headers={"Authorization": f"Bearer {STRIPE_SECRET_KEY}"},
            data={"mode": "subscription", "line_items[0][price]": price,
                  "line_items[0][quantity]": "1",
                  "customer_email": user.email,
                  "client_reference_id": str(user.id),
                  "metadata[user_id]": str(user.id),
                  "metadata[plan]": plan,
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
    days = 372 if period == "year" else 32     # a few days' grace over the term
    u.plan, u.plan_provider, u.plan_ref = plan, provider, str(ref or "")[:120]
    u.plan_started = now()
    u.plan_expires = now() + dt.timedelta(days=days)
    db.commit()
    print(f"billing: user {u.id} -> {plan} via {provider} until {u.plan_expires}")


@app.post("/api/billing/webhook/razorpay")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    """Razorpay calls this. The signature is what makes it trustworthy."""
    raw = await request.body()
    sig = request.headers.get("x-razorpay-signature", "")
    if not RAZORPAY_WEBHOOK_SECRET:
        raise HTTPException(503, "Webhook secret not configured")
    expected = hmac.new(RAZORPAY_WEBHOOK_SECRET.encode(), raw,
                        hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, sig):
        raise HTTPException(400, "Bad signature")
    ev = json.loads(raw or b"{}")
    kind = ev.get("event", "")
    ent = (ev.get("payload") or {}).get("payment", {}).get("entity") \
        or (ev.get("payload") or {}).get("order", {}).get("entity") or {}
    notes = ent.get("notes") or {}
    if kind in ("payment.captured", "order.paid"):
        uid, plan = notes.get("user_id"), (notes.get("plan") or "basic")
        if uid:
            _activate(db, uid, plan, "razorpay", ent.get("id"),
                      notes.get("period", "month"))
    return {"ok": True}


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
        if uid:
            _activate(db, uid, md.get("plan") or "basic", "stripe",
                      obj.get("subscription") or obj.get("id"))
    elif kind in ("customer.subscription.deleted", "invoice.payment_failed"):
        sub = obj.get("subscription") or obj.get("id")
        u = db.query(User).filter(User.plan_ref == str(sub)).first()
        if u:
            # Do not cut access mid-period; let it lapse at expiry.
            u.plan_expires = min(u.plan_expires or now(), now())
            db.commit()
    return {"ok": True}


@app.post("/api/admin/jobs/refresh")
async def admin_jobs_refresh(user: User = Depends(admin_user)):
    """Force a crawl now. The per-source report shows which boards responded,
    so a renamed or dead board token is obvious immediately."""
    return await _refresh_jobs()


# ---------------------------- admin ---------------------------------------
@app.get("/api/admin/stats")
def admin_stats(user: User = Depends(admin_user), db: Session = Depends(get_db)):
    total_users = db.query(func.count(User.id)).scalar()
    total_lessons = db.query(func.count(Lesson.id)).filter(Lesson.published == True).scalar()  # noqa: E712
    completions = db.query(func.count(Progress.id)).filter(Progress.completed == True).scalar()  # noqa: E712

    week_ago = now() - dt.timedelta(days=7)
    active_7d = db.query(func.count(User.id)).filter(User.last_seen >= week_ago).scalar()
    new_7d = db.query(func.count(User.id)).filter(User.created_at >= week_ago).scalar()

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
        "total_lessons": total_lessons,
        "completions": completions,
        "avg_per_user": round(completions / total_users, 1) if total_users else 0,
        "signups": [{"date": str(d), "count": c} for d, c in signups],
        "funnel": funnel,
        "biggest_drop": drop,
        "quiz": [{"track": t, "attempts": a, "passed": int(p or 0)} for t, a, p in quiz_rows],
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
    db.query(Progress).filter(Progress.user_id == uid).delete()
    db.query(QuizResult).filter(QuizResult.user_id == uid).delete()
    db.query(Note).filter(Note.user_id == uid).delete()
    db.delete(u)
    db.commit()
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
    return FileResponse(BASE_DIR / "index.html")


@app.get("/reset")
def reset_page():
    """The reset link lands here; the page reads ?token= and calls the API."""
    return FileResponse(BASE_DIR / "index.html")


@app.get("/admin")
def admin_page():
    return FileResponse(BASE_DIR / "admin.html")


@app.exception_handler(404)
def not_found(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    return FileResponse(BASE_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(env("PORT", "8000")))
