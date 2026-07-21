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
from fastapi import FastAPI, Depends, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, JSONResponse
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

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./vidyapath.db")
# Railway hands out postgres:// ; SQLAlchemy 2 needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    # Fine for local dev; on Railway you MUST set this or sessions reset on redeploy.
    JWT_SECRET = "dev-only-insecure-secret-change-me"
    print("WARNING: JWT_SECRET not set — using an insecure development value.")

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "").strip().lower()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "1") != "0"
SESSION_DAYS = 30

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
    for t in tracks:
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
    return len(tracks)


def seed_if_empty():
    """Create tables, load curriculum on first boot, ensure admin exists."""
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        existing = db.query(Track).count()
        files = sorted(p.name for p in BASE_DIR.glob("*.json") if p.name != "railway.json")
        print(f"Startup: {existing} tracks in database | curriculum files found: {files}")

        if existing == 0:
            # One continuous ladder. Position ranges keep the stages in order.
            counts = [
                _seed_file(db, "school.json",     "school",   0),    # Stage 1
                _seed_file(db, "stage2.json",     "stage2",   50),   # Stage 2
                _seed_file(db, "stage3a.json",    "stage3a",  80),   # Stage 3
                _seed_file(db, "stage3b.json",    "stage3b",  90),   # Stage 4
                _seed_file(db, "stage4.json",     "stage4",   95),   # Stage 5
                _seed_file(db, "curriculum.json", "graduate", 120),  # Stage 6
            ]
            db.commit()
            total = sum(counts)
            if total:
                print(f"Seeded {total} tracks across 6 stages: {counts}")
            else:
                print("WARNING: no curriculum files found - content is empty.")

        # Admin bootstrap
        if ADMIN_EMAIL and ADMIN_PASSWORD:
            admin = db.query(User).filter(User.email == ADMIN_EMAIL).first()
            if not admin:
                db.add(User(email=ADMIN_EMAIL, name="Administrator",
                            password_hash=hash_pw(ADMIN_PASSWORD), is_admin=True))
                db.commit()
                print(f"Created admin account: {ADMIN_EMAIL}")
            elif not admin.is_admin:
                admin.is_admin = True
                db.commit()
    finally:
        db.close()


@app.on_event("startup")
def _startup():
    seed_if_empty()


@app.get("/api/health")
def health():
    return {"status": "ok", "time": now().isoformat()}


@app.get("/api/status")
def status(db: Session = Depends(get_db)):
    """Public diagnostic — what content is actually loaded right now."""
    tracks = db.query(Track).order_by(Track.position).all()
    return {
        "tracks": len(tracks),
        "lessons": db.query(func.count(Lesson.id)).scalar(),
        "users": db.query(func.count(User.id)).scalar(),
        "database": "postgres" if DATABASE_URL.startswith("postgres") else "sqlite",
        "curriculum_files_present": sorted(
            p.name for p in BASE_DIR.glob("*.json") if p.name != "railway.json"),
        "loaded": [{"id": t.slug, "name": t.name, "stage": t.audience,
                    "lessons": len(t.lessons)} for t in tracks],
    }


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
    set_session(response, user)
    return {"id": user.id, "name": user.name, "email": user.email, "is_admin": user.is_admin}


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
    return {"id": user.id, "name": user.name, "email": user.email, "is_admin": user.is_admin}


@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie("vp_session", path="/")
    return {"ok": True}


@app.get("/api/auth/me")
def me(user: User = Depends(current_user)):
    return {
        "id": user.id, "name": user.name, "email": user.email,
        "is_admin": user.is_admin, "path": user.path,
        "joined": user.created_at.isoformat() if user.created_at else None,
    }


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
    row.v = body.value[:5000]
    db.commit()
    return {"ok": True}


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
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
