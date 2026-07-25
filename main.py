"""
VidyaPath — backend
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
from urllib.parse import urlencode
from fastapi import (FastAPI, Depends, HTTPException, Request, Response, status,
                     UploadFile, File)
from fastapi.responses import (FileResponse, JSONResponse, RedirectResponse,
                               Response as RawResponse)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import (
    create_engine, Column, Integer, String, Text, Boolean, DateTime, Date,
    ForeignKey, UniqueConstraint, func, cast,
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

# ---- Ask Vidya (the "ask anything" AI teacher) ---------------------------
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

GEMINI_MODEL = env("GEMINI_MODEL", "gemini-2.0-flash")
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
print(f"Ask Vidya: provider={AI_PROVIDER} enabled={ASK_ENABLED}"
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


def make_token(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "adm": user.is_admin,
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
app = FastAPI(title="VidyaPath", docs_url="/api/docs", redoc_url=None)


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
    print(f"  VidyaPath  v{VERSION}  (commit {GIT_SHA})")
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
def status(db: Session = Depends(get_db)):
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
def set_session(resp: Response, user: User):
    resp.set_cookie(
        "vp_session", make_token(user),
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

    set_session(response, user)
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
    set_session(response, user)
    t = teacher_row(user, db)
    return {"id": user.id, "name": user.name, "email": user.email,
            "is_admin": user.is_admin, "is_teacher": bool(t) or user.is_admin,
            "is_head": is_head(user, db)}


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
    set_session(resp, user)
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


# ---------------------------- Ask Vidya -----------------------------------
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
            "Vidya's ask-anything teacher needs an API key to think.",
            "The site owner adds a free GEMINI_API_KEY in the server settings.",
            "Once it is set, ask any question on any subject.",
            "Answers you get are saved, so asking again is instant and free.",
        ],
        "takeaway": "Everything else on VidyaPath works without this.",
    }


def _ask_prompt(question: str, subject: str, level: str) -> str:
    return (
        f"You are Vidya, a warm, patient teacher in India explaining on a "
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


async def _call_model(question: str, subject: str, level: str) -> dict:
    """Dispatch to whichever provider is configured. Server-side only.
    The API key never leaves this process."""
    import httpx  # imported lazily so the app boots even before it installs
    prompt = _ask_prompt(question, subject, level)

    async with httpx.AsyncClient(timeout=45) as client:
        if AI_PROVIDER == "gemini":
            url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                   f"{GEMINI_MODEL}:generateContent")
            gen = {"maxOutputTokens": 2048, "temperature": 0.5,
                   "responseMimeType": "application/json"}
            # 2.5-family models "think" and can spend the whole budget before
            # emitting text; turning that off keeps answers reliable.
            if "2.5" in GEMINI_MODEL:
                gen["thinkingConfig"] = {"thinkingBudget": 0}
            r = await client.post(
                url,
                headers={"x-goog-api-key": GEMINI_API_KEY,
                         "content-type": "application/json"},
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": gen},
            )
            _upstream_ok(r, "gemini")
            data = r.json()
            text = "".join(
                p.get("text", "")
                for c in data.get("candidates", [])
                for p in c.get("content", {}).get("parts", [])
            ).strip()

        elif AI_PROVIDER == "groq":
            r = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                         "content-type": "application/json"},
                json={
                    "model": GROQ_MODEL,
                    "max_tokens": 1200,
                    "temperature": 0.5,
                    "response_format": {"type": "json_object"},
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            _upstream_ok(r, "groq")
            data = r.json()
            text = (data.get("choices", [{}])[0]
                        .get("message", {}).get("content", "")).strip()

        else:  # claude / anthropic
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": ANTHROPIC_API_KEY,
                         "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={
                    "model": ANTHROPIC_MODEL,
                    "max_tokens": 1200,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            _upstream_ok(r, "claude")
            data = r.json()
            text = "".join(
                b.get("text", "") for b in data.get("content", [])
                if b.get("type") == "text"
            ).strip()

    if not text:
        raise RuntimeError(f"{AI_PROVIDER} returned no text (model={_PROVIDER_MODEL})")
    return _parse_lesson(text, question)


async def _ai_text(prompt: str, max_tokens: int = 1500) -> str:
    """Generic single-prompt call to the configured provider; returns raw text."""
    import httpx
    async with httpx.AsyncClient(timeout=60) as client:
        if AI_PROVIDER == "gemini":
            gen = {"maxOutputTokens": max_tokens, "temperature": 0.4}
            if "2.5" in GEMINI_MODEL:
                gen["thinkingConfig"] = {"thinkingBudget": 0}
            r = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
                headers={"x-goog-api-key": GEMINI_API_KEY, "content-type": "application/json"},
                json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": gen})
            _upstream_ok(r, "gemini")
            return "".join(p.get("text", "") for c in r.json().get("candidates", [])
                           for p in c.get("content", {}).get("parts", [])).strip()
        elif AI_PROVIDER == "groq":
            r = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "content-type": "application/json"},
                json={"model": GROQ_MODEL, "max_tokens": max_tokens, "temperature": 0.4,
                      "messages": [{"role": "user", "content": prompt}]})
            _upstream_ok(r, "groq")
            return r.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        else:
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                         "content-type": "application/json"},
                json={"model": ANTHROPIC_MODEL, "max_tokens": max_tokens,
                      "messages": [{"role": "user", "content": prompt}]})
            _upstream_ok(r, "claude")
            return "".join(b.get("text", "") for b in r.json().get("content", [])
                           if b.get("type") == "text").strip()


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
    clean = (text or "").replace("```json", "").replace("```", "").strip()
    return json.loads(clean)


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
        data = _ai_json(await _ai_text(prompt, 700))
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
        data = _ai_json(await _ai_text(prompt, 500))
    except Exception as e:
        print(f"Resume skills failed ({AI_PROVIDER}): {type(e).__name__}: {e}")
        raise HTTPException(503, "The AI writer could not respond. Try again.")
    return {"skills": [str(s)[:40] for s in (data.get("skills") or [])][:20]}


class MatchIn(BaseModel):
    resume: dict = {}
    jd: str = Field(default="", max_length=8000)


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
async def resume_match(body: MatchIn, user: User = Depends(current_user)):
    """Full AI analysis of the resume against a JD: overall score, sub-scores,
    and gaps categorised as critical / weak / strong."""
    if not ASK_ENABLED:
        raise HTTPException(503, "The AI matcher is not switched on")
    jd = (body.jd or "").strip()
    if len(jd) < 40:
        raise HTTPException(400, "Paste the full job description first")
    rtext = _resume_text(body.resume or {})[:6000]
    prompt = (
        "You are an ATS resume analyst. Compare the RESUME to the JOB "
        "DESCRIPTION and score the fit honestly.\n\n"
        f"RESUME:\n{rtext}\n\nJOB DESCRIPTION:\n{jd[:6000]}\n\n"
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
        d = _ai_json(await _ai_text(prompt, 900))
    except Exception as e:
        print(f"Resume match failed ({AI_PROVIDER}): {type(e).__name__}: {e}")
        raise HTTPException(503, "The AI matcher could not respond. Try again.")
    def lst(k, n=12, cap=60):
        return [str(x)[:cap] for x in (d.get(k) or []) if str(x).strip()][:n]
    sub = d.get("subscores") or {}
    def sc(v):
        try:
            return max(0, min(100, int(v)))
        except Exception:
            return 0
    return {
        "score": sc(d.get("score", 0)),
        "subscores": {"keywords": sc(sub.get("keywords", 0)),
                      "experience": sc(sub.get("experience", 0)),
                      "readability": sc(sub.get("readability", 0))},
        "critical": lst("critical"), "weak": lst("weak"),
        "strong": lst("strong"), "advice": lst("advice", 6, 280),
    }


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
    # Group the resume into editable sections (heading + whole-section body),
    # keeping the original wording and the order of the document.
    sections = _split_sections(text)
    prompt = (
        "Parse this resume text into structured JSON. Use ONLY information "
        "present; leave fields empty if absent. The candidate's NAME and CONTACT "
        "details often appear on the very first lines (from the document header) "
        "— capture them. Capture EVERY job in 'exp' (do not skip any) and keep "
        "each job's 'bullets' as newline-separated lines.\n\n"
        f"RESUME TEXT:\n{text[:16000]}\n\n"
        "Return ONLY valid JSON in this shape:\n"
        '{"name":"","title":"","email":"","phone":"","location":"","links":"",'
        '"summary":"","skills":[{"label":"Skills","items":""}],'
        '"exp":[{"role":"","company":"","place":"","dates":"","bullets":""}],'
        '"edu":[{"degree":"","school":"","place":"","year":""}],'
        '"proj":[{"name":"","tech":"","desc":"","link":""}],"certs":""}'
    )
    try:
        d = _ai_json(await _ai_text(prompt, 3600))
    except Exception as e:
        print(f"Resume parse failed ({AI_PROVIDER}): {type(e).__name__}: {e}")
        raise HTTPException(503, "The AI could not structure that resume. Try again.")

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
                 "bullets": s(x.get("bullets"), 2000), "ctx": ""}
                for x in (d.get("exp") or []) if isinstance(x, dict)][:8] or [{"role": "", "company": "", "place": "", "dates": "", "bullets": "", "ctx": ""}],
        "edu": [{"degree": s(x.get("degree"), 120), "school": s(x.get("school"), 120),
                 "place": s(x.get("place"), 80), "year": s(x.get("year"), 20)}
                for x in (d.get("edu") or []) if isinstance(x, dict)][:6] or [{"degree": "", "school": "", "place": "", "year": ""}],
        "proj": [{"name": s(x.get("name"), 120), "tech": s(x.get("tech"), 120),
                  "desc": s(x.get("desc"), 300), "link": s(x.get("link"), 200)}
                 for x in (d.get("proj") or []) if isinstance(x, dict)][:8] or [{"name": "", "tech": "", "desc": "", "link": ""}],
        "certs": s(d.get("certs"), 1000),
    }
    if sections:
        out["sections"] = sections
    return out


class ProofreadIn(BaseModel):
    resume: dict = {}


@app.post("/api/resume/proofread")
async def resume_proofread(body: ProofreadIn, user: User = Depends(current_user)):
    """Flag spelling and grammar issues in the resume text so the user can fix
    them. Returns a list of {wrong, right, why} — it does not auto-edit."""
    if not ASK_ENABLED:
        raise HTTPException(503, "The proofreader is not switched on")
    rtext = _resume_text(body.resume or {})[:6000]
    if len(rtext.strip()) < 20:
        raise HTTPException(400, "Add some resume content first")
    prompt = (
        "You are a meticulous proofreader for resumes. Find SPELLING and GRAMMAR "
        "mistakes in the text below. For each mistake, give the exact wrong text, "
        "the correction, and a 2-4 word reason. Ignore names, companies, "
        "technologies and acronyms (e.g. Kubernetes, OWASP, VMware) — those are "
        "not misspellings. If there are no real mistakes, return an empty list.\n\n"
        f"RESUME TEXT:\n{rtext}\n\n"
        'Respond with ONLY valid JSON: {"issues":[{"wrong":"<text>",'
        '"right":"<correction>","why":"<short reason>"}]}'
    )
    try:
        d = _ai_json(await _ai_text(prompt, 1200))
    except Exception as e:
        print(f"Resume proofread failed ({AI_PROVIDER}): {type(e).__name__}: {e}")
        raise HTTPException(503, "The proofreader could not respond. Try again.")
    issues = []
    for it in (d.get("issues") or [])[:40]:
        if not isinstance(it, dict):
            continue
        w = str(it.get("wrong", "")).strip()[:80]
        r = str(it.get("right", "")).strip()[:80]
        if w and r and w.lower() != r.lower():
            issues.append({"wrong": w, "right": r, "why": str(it.get("why", "")).strip()[:60]})
    return {"issues": issues}


class ChatIn(BaseModel):
    resume: dict = {}
    message: str = Field(min_length=1, max_length=1000)
    history: list = []


@app.post("/api/resume/chat")
async def resume_chat(body: ChatIn, user: User = Depends(current_user)):
    """Advice-only resume co-pilot. It gives clear, specific suggestions the
    user reads and applies themselves — it never edits the resume directly."""
    if not ASK_ENABLED:
        raise HTTPException(503, "The AI co-pilot is not switched on")
    rtext = _resume_text(body.resume or {})[:4500]
    hist = ""
    for m in (body.history or [])[-6:]:
        who = "User" if str(m.get("role")) == "user" else "Coach"
        hist += f"{who}: {str(m.get('content',''))[:300]}\n"
    prompt = (
        "You are the Vidya Resume Coach — a warm, practical career advisor "
        "inside a resume builder. The user will ask for help. Give clear, "
        "specific, actionable advice they can apply themselves. When you "
        "suggest better wording, show the exact rewritten line(s) in quotes so "
        "they can copy it. Be concise. Use ONLY the user's real facts — never "
        "invent employers, dates, degrees or numbers.\n\n"
        + (f"Conversation so far:\n{hist}\n" if hist else "")
        + f"Their resume (text):\n{rtext}\n\n"
        + f"User asks: \"{body.message.strip()}\"\n\n"
        "Reply in plain text: 2-5 short sentences of advice, and where useful a "
        "few concrete example lines. Do NOT return JSON, code fences or lists of "
        "actions — just your helpful written answer."
    )
    try:
        reply = await _ai_text(prompt, 900)
    except Exception as e:
        print(f"Resume chat failed ({AI_PROVIDER}): {type(e).__name__}: {e}")
        raise HTTPException(503, "The co-pilot could not respond. Try again.")
    reply = (reply or "").replace("```", "").strip()
    return {"reply": reply[:2000]}


@app.get("/api/ask/config")
def ask_config(user: User = Depends(current_user)):
    """Lets the page know whether the AI teacher is switched on."""
    return {"enabled": ASK_ENABLED,
            "provider": AI_PROVIDER if ASK_ENABLED else "",
            "model": _PROVIDER_MODEL if ASK_ENABLED else ""}


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
        reason = f"{type(e).__name__}: {e}"
        print(f"Ask Vidya call failed ({AI_PROVIDER}): {reason}")
        # DIAGNOSTIC: show the real upstream reason to every logged-in user
        # while we get the AI teacher working. Lock back to admins-only later.
        raise HTTPException(status_code=503,
                            detail=f"Vidya could not reach the board. Reason: {reason}"[:400])

    db.add(AskCache(qkey=qkey, subject=subject, level=level,
                    question=question[:2000], lesson=json.dumps(lesson), hits=0))
    db.commit()
    return {"lesson": lesson, "cached": False}


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
                    headers={"Content-Disposition": "attachment; filename=vidyapath-students.csv"})


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
  <a href="/">Back to VidyaPath</a>
</div>
<div class="head">
  <h1>{esc(title)}</h1>
  <div class="sub">{esc(track.icon)} {esc(track.name)} &middot; {len(qs)} questions
    &middot; VidyaPath</div>
</div>
{meta}
{"".join(body)}
<div class="foot">VidyaPath &middot; Free to print and photocopy for classroom use</div>
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
  <div><b>VidyaPath</b>Learn to code, then build with AI</div>
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
