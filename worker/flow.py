"""What happens to one queued application, start to finish.

No playwright import anywhere in this file, on purpose. Everything here
takes a `page` and an `adapter` and does not care what they are, which is
what lets the whole state machine — the caps, the hold window, the retry
ceiling, the kill switch, the consent recheck — be driven in a test with a
stub and no browser at all. The browser lives in run.py.

The path a row takes:

    prepared  --open, fill, answers-->  needs_answer   (a person is asked)
              --attach, screenshot-->   holding        (hold_until set)
    holding   --past hold_until-->      confirmed      (and a JobTrack row)

and out of any of them, `failed` or `cancelled`.

Three things are checked twice, at enqueue and again here immediately before
the click, because the gap between those two is measured in minutes:

**Consent.** Somebody who withdraws permission while a row is holding has
withdrawn it, and a queue that drains anyway has made the word meaningless.

**The kill switch.** It is read on every pass rather than at startup. A
switch that needs a redeploy to take effect is not a switch.

**The per-company hour.** Read at submit time, not at enqueue, because an
hour is a long time in a queue and twelve applications landing on one
employer in one hour is what gets a whole domain blocked for everybody.

A cap that is hit does NOT fail the row. It pushes it back and tries later —
failing an application because the queue was busy would be the tool losing
somebody an opportunity to protect a rate limit.
"""
import json
import os
import traceback
import datetime as dt

from sqlalchemy import func

from .adapters.base import Unconfirmed

# Three, and then stop. A form that has failed three times is not going to
# work on the fourth, and hammering an employer's ATS is exactly how one bad
# row gets a whole domain blocked.
MAX_ATTEMPTS = 3


class Halted(Exception):
    """The kill switch is on. Raised so the loop stops rather than spins."""


def _say(row, msg):
    print(f"[apply {row.id}] {msg}", flush=True)


def aware(when):
    """A stored timestamp, with a timezone on it.

    Postgres gives back an aware datetime for DateTime(timezone=True);
    SQLite gives back a naive one, because SQLite has no such type and
    stores a string. Comparing the two raises, so every read of hold_until
    goes through here. Everything written is UTC, so assuming UTC on a naive
    value is not a guess — it is the only thing it can be.

    It matters beyond the tests: this is what decides whether a hold window
    has expired, and an exception there would leave a row holding forever
    with nothing saying why.
    """
    if when is None:
        return None
    return when if when.tzinfo else when.replace(tzinfo=dt.timezone.utc)


def load_bank(db, m, user_id):
    """This candidate's previous answers, keyed by normalised question."""
    rows = db.query(m.AnswerBank).filter(m.AnswerBank.user_id == user_id).all()
    return {r.question_norm: (r.answer or "") for r in rows if r.question_norm}


def build_profile(db, m, user):
    """The autofill profile, from the same place the extension gets it.

    Reusing apply_profile's shape rather than inventing a second one is not
    tidiness: filler.js matches on these exact keys, and a profile built with
    different names here would fill nothing and report success doing it.
    """
    raw = db.query(m.Note).filter(m.Note.user_id == user.id,
                                  m.Note.k == "resume_data").first()
    try:
        r = json.loads(raw.v) if raw and raw.v else {}
    except Exception:
        r = {}
    links = str(r.get("links") or "")

    def find(*keys):
        import re
        for k in keys:
            hit = re.search(rf"https?://\S*{k}\S*", links, re.I)
            if hit:
                return hit.group(0).rstrip(".,;")
        return ""

    exp = (r.get("exp") or [{}])[0] if r.get("exp") else {}
    edu = (r.get("edu") or [{}])[0] if r.get("edu") else {}
    full = str(r.get("name") or user.name or "").strip()
    first, _, last = full.partition(" ")
    # Address, notice period, salary, work authorisation: the things every
    # form asks and no CV carries. The same stored set the extension reads,
    # so the two fill a form identically. Applied LAST so a detail the
    # person typed wins over anything guessed from the resume.
    typed = m.apply_details(db, user.id)
    out = {
        "first_name": first, "last_name": last.strip(), "full_name": full,
        "middle_name": "", "preferred_first_name": "",
        "preferred_middle_name": "", "preferred_last_name": "",
        "phone_country_code": "",
        "email": str(r.get("email") or user.email or ""),
        "phone": str(r.get("phone") or user.phone or ""),
        "location": str(r.get("location") or user.city or ""),
        "linkedin": find("linkedin"), "github": find("github"),
        "portfolio": find("portfolio", "vercel", "netlify", r"\.dev", r"\.me"),
        "current_title": str(exp.get("role") or r.get("title") or ""),
        "current_company": str(exp.get("company") or ""),
        "school": str(edu.get("school") or user.college or ""),
        "degree": str(edu.get("degree") or user.degree or ""),
        "field_of_study": str(edu.get("degree") or ""),
        "grad_year": str(edu.get("year") or ""),
        "summary": str(r.get("summary") or "")[:1200],
        "city": str(user.city or ""),
    }
    out.update({k: v for k, v in typed.items() if v})
    return out


def _fail(db, m, row, why):
    row.status = "failed"
    row.error = str(why)[:2000]
    row.updated_at = m.now()
    db.commit()
    _say(row, f"failed: {why}")
    return "failed"


def _cancel(db, m, row, why):
    row.status = "cancelled"
    row.error = str(why)[:2000]
    row.updated_at = m.now()
    db.commit()
    _say(row, f"cancelled: {why}")
    return "cancelled"


def _defer(db, m, row, minutes, why):
    """Not now. Try again shortly, still holding, nothing lost."""
    row.hold_until = m.now() + dt.timedelta(minutes=minutes)
    row.error = str(why)[:2000]
    row.updated_at = m.now()
    db.commit()
    _say(row, f"deferred {minutes}m: {why}")
    return "holding"


def _record_applied(db, m, row):
    """Into the tracker, where the rest of a person's history already lives.

    One home for "what have I applied to", not two. The row is updated rather
    than duplicated if the candidate had already saved this job by hand.
    """
    # A pasted link has no job_id, because the posting is not one we crawl.
    # Matching on `job_id == None` would make every such application update
    # the same tracker row — two pasted links, one record — so those are
    # matched on the URL instead, which is the only thing they have.
    if row.job_id:
        track = db.query(m.JobTrack).filter(
            m.JobTrack.user_id == row.user_id,
            m.JobTrack.job_id == row.job_id).first()
    else:
        track = db.query(m.JobTrack).filter(
            m.JobTrack.user_id == row.user_id,
            m.JobTrack.job_id == 0,
            m.JobTrack.url == (row.url or "")).first()
    if track is None:
        # 0, not NULL: the tracker screen keys its controls off this and a
        # null renders as the string "null" in a data attribute.
        track = m.JobTrack(user_id=row.user_id, job_id=row.job_id or 0,
                           created_at=m.now())
        db.add(track)
    track.status = "applied"
    track.applied_at = m.now()
    track.title = row.title or track.title or ""
    track.company = row.company or track.company or ""
    track.url = row.url or track.url or ""
    track.score = row.score or track.score or 0
    track.updated_at = m.now()


async def prepare(db, m, row, adapter, page, shots_dir, resume_path):
    """Open the form, fill it, attach, and stop at the hold window."""
    user = db.get(m.User, row.user_id)
    if user is None:
        return _fail(db, m, row, "The account is gone.")

    await adapter.open(page, row.url)
    got = await adapter.fill(page, build_profile(db, m, user))
    _say(row, f"filled {got.count}: {', '.join(got.filled) or 'nothing'}")

    missing = await adapter.answers(page, load_bank(db, m, user.id))

    # What the deterministic path could not settle goes to the model — once,
    # in one call, for the whole form. It is given this candidate's resume,
    # the details they typed and every answer they have given before, and
    # told to answer FROM THOSE ONLY and return nothing where the documents
    # do not say. It is extracting, not composing.
    #
    # Questions that are legal declarations or protected characteristics
    # never reach it (main.APPLY_NEVER_AI) and park for the person, as they
    # should. Everything it does settle goes into the bank, so it is asked
    # once across every application this account will ever make rather than
    # once per form — which is what keeps a model in this path affordable.
    if missing:
        asked = [{"label": q.label, "norm": q.norm, "kind": q.kind,
                  "options": q.options} for q in missing]
        try:
            got = await m.apply_ai_answers(db, user, asked)
        except Exception as e:
            # Never fatal. A model that is down leaves the row exactly where
            # the deterministic path left it.
            _say(row, f"model unavailable: {type(e).__name__}: {e}")
            got = {}
        if got:
            m.apply_bank_write(db, user.id, got, by_ai=True)
            _say(row, f"model answered {len(got)} of {len(missing)}")
            # Filled by re-running the resolver against the enlarged bank,
            # rather than writing values in here: one place decides how an
            # answer reaches a field, and it already handles selects that
            # refuse a value.
            missing = await adapter.answers(page, load_bank(db, m, user.id))

    if missing:
        # Parked, not failed. The row is one answer away and the answer goes
        # into the bank, so this costs the candidate once and never again.
        row.status = "needs_answer"
        row.missing_json = json.dumps(
            [{"label": q.label, "norm": q.norm, "kind": q.kind,
              "options": q.options} for q in missing])[:20000]
        row.error = ""
        row.updated_at = m.now()
        db.commit()
        _say(row, f"needs {len(missing)} answer(s)")
        return "needs_answer"

    if not resume_path:
        return _fail(
            db, m, row,
            "There is no resume on this account to attach. Upload one and "
            "queue this job again.")
    await adapter.attach(page, resume_path)

    # The screenshot is the point of the hold window. "We are about to send
    # this" with nothing to look at is not a review, it is a countdown.
    os.makedirs(shots_dir, exist_ok=True)
    shot = os.path.join(shots_dir, f"apply-{row.id}.png")
    try:
        await page.screenshot(path=shot, full_page=True)
        row.screenshot_path = shot
    except Exception as e:
        # A missing picture is not a reason to refuse to apply; it is a
        # reason to say the picture is missing.
        _say(row, f"no screenshot: {type(e).__name__}: {e}")
        row.screenshot_path = ""

    row.status = "holding"
    row.hold_until = m.now() + dt.timedelta(minutes=m.apply_hold_minutes())
    row.error = ""
    row.updated_at = m.now()
    db.commit()
    _say(row, f"holding until {row.hold_until.isoformat()}")
    return "holding"


async def send(db, m, row, adapter, page):
    """The click, and everything that has to be true immediately before it."""
    if m.apply_halted():
        raise Halted()
    user = db.get(m.User, row.user_id)
    if user is None:
        return _fail(db, m, row, "The account is gone.")
    if m.live_consent(db, user) is None:
        return _cancel(db, m, row, "Consent was withdrawn.")
    # The paid gate, again. It is checked at enqueue, and a queue built on
    # Tuesday and drained on Friday would otherwise outlive the subscription
    # that bought it — the same hole /api/apply/licence exists to close for
    # the browser extension. Cancelled rather than deferred: a lapsed plan is
    # not a busy queue, and the row can be re-queued after renewing.
    if not getattr(user, "is_admin", False) and m.plan_of(user) == "free":
        return _cancel(db, m, row,
                       "Automatic applications are part of Pro, and this "
                       "account is no longer on it.")

    cap = m.apply_max_per_company_hour()
    if cap and m.company_sent_last_hour(db, row.company) >= cap:
        return _defer(db, m, row, 20,
                      f"{row.company} has had {cap} applications from us in "
                      "the last hour. Waiting.")
    day = m.apply_max_per_user_day()
    if day and m.applied_today(db, row.user_id) >= day:
        return _defer(db, m, row, 90, f"Today's limit of {day} is reached.")

    # Everything above this line is a pre-flight check, and a failure in one
    # of them means nothing was sent. Everything below is the click, where a
    # failure is ambiguous. The two must not share a try block: they did, and
    # a database error while reading the per-company count would have been
    # recorded as a submitted application.
    try:
        confirmation = await adapter.submit(page)
    except Halted:
        raise
    except Exception as e:
        # The click happened, or may have. "I clicked and could not read the
        # response" and "I did not click" are indistinguishable from here,
        # and retrying the first applies to the same job twice under
        # somebody's real name. So: recorded as sent, never retried, and the
        # text kept so a person can check it.
        if isinstance(e, Unconfirmed):
            note = f"Sent, but the page did not confirm it. {e}"
        else:
            note = ("The submit step failed after the form was "
                    f"completed: {type(e).__name__}: {e}")
        row.status = "submitted"
        row.submitted_at = m.now()
        row.confirmation = ""
        row.error = note[:2000]
        _record_applied(db, m, row)
        row.updated_at = m.now()
        db.commit()
        if not isinstance(e, Unconfirmed):
            traceback.print_exc()
        _say(row, "submitted, unconfirmed")
        return "submitted"

    row.status = "confirmed"
    row.submitted_at = m.now()
    row.confirmation = (confirmation or "")[:2000]
    row.error = ""
    _record_applied(db, m, row)
    row.updated_at = m.now()
    db.commit()
    _say(row, f"confirmed: {row.confirmation[:80]}")
    return "confirmed"


async def run_row(db, m, row, adapter, page, shots_dir, resume_path=None):
    """One row, one pass. Returns the status it ended the pass in.

    This is the only place that catches. An adapter that swallowed its own
    exception would report success having done nothing, which is the failure
    mode the job-source doc warns about in the crawler and is worse here —
    there the cost is a missing posting, here it is a row that says an
    application was sent when none was.
    """
    if m.apply_halted():
        raise Halted()

    user = db.get(m.User, row.user_id)
    if user is None:
        return _fail(db, m, row, "The account is gone.")
    if m.live_consent(db, user) is None:
        return _cancel(db, m, row, "Consent was withdrawn.")

    if row.status == "holding":
        if row.hold_until and m.now() < aware(row.hold_until):
            return "holding"        # still inside the window; leave it be
        try:
            return await send(db, m, row, adapter, page)
        except Halted:
            raise
        except Exception as e:
            # send() owns the click and everything ambiguous about it.
            # Anything that escapes to here happened BEFORE the click — a
            # pre-flight check that raised — so nothing was sent and the row
            # is retried like any other failure.
            row.attempt = (row.attempt or 0) + 1
            row.error = f"{type(e).__name__}: {e}"[:2000]
            row.updated_at = m.now()
            db.commit()
            traceback.print_exc()
            if row.attempt >= MAX_ATTEMPTS:
                return _fail(db, m, row,
                             f"Gave up after {MAX_ATTEMPTS} attempts. "
                             f"{row.error}")
            _say(row, f"pre-flight failed, nothing sent: {row.error}")
            return "holding"

    if row.status != "prepared":
        return row.status

    # attempt counts FAILURES, not passes. A row that parks for an answer
    # has not failed at anything — it is waiting on a person — and a
    # candidate asked for two answers on one awkward form should not arrive
    # at the third with no retries left for a real problem.
    if (row.attempt or 0) >= MAX_ATTEMPTS:
        return _fail(db, m, row,
                     f"Gave up after {MAX_ATTEMPTS} attempts. "
                     + (row.error or "The form could not be completed."))

    try:
        status = await prepare(db, m, row, adapter, page, shots_dir,
                               resume_path)
    except Halted:
        raise
    except Exception as e:
        row.attempt = (row.attempt or 0) + 1
        row.error = f"{type(e).__name__}: {e}"[:2000]
        row.updated_at = m.now()
        db.commit()
        traceback.print_exc()
        if row.attempt >= MAX_ATTEMPTS:
            return _fail(db, m, row,
                         f"Gave up after {MAX_ATTEMPTS} attempts. {row.error}")
        _say(row, f"attempt {row.attempt} failed: {row.error}")
        return "prepared"

    # A hold of zero minutes means send it now, in this same pass. Somebody
    # who set it to zero asked for exactly that.
    if status == "holding" and m.apply_hold_minutes() == 0:
        try:
            return await send(db, m, row, adapter, page)
        except Halted:
            raise
        except Exception as e:
            # Same rule as the holding branch above: send() owns the click,
            # so anything reaching here failed before it and nothing was
            # sent. The row stays holding and the next pass tries again.
            row.attempt = (row.attempt or 0) + 1
            row.error = f"{type(e).__name__}: {e}"[:2000]
            row.updated_at = m.now()
            db.commit()
            traceback.print_exc()
            if row.attempt >= MAX_ATTEMPTS:
                return _fail(db, m, row,
                             f"Gave up after {MAX_ATTEMPTS} attempts. "
                             f"{row.error}")
            return "holding"
    return status


def due_rows(db, m, limit=25):
    """What is ready to run: at most one row per person, per pass.

    Fairness matters more than throughput. A person who queued twenty jobs
    must not sit behind somebody who queued a hundred — and the obvious
    implementation does exactly that. Taking the first N rows by id and then
    deduplicating by user in Python looks like it spreads the work, but if
    one account has queued more rows than the prefetch, every row fetched
    belongs to them and nobody else is ever seen. Measured: 120 rows from
    one account and a second account's single row was never offered.

    So the grouping happens in SQL. GROUP BY user_id gives exactly one
    candidate per person however large the backlog is, which is the property
    the Python version only appeared to have.

    Held rows come first: they are already filled, screenshotted and past
    their window, and the work of preparing them has been paid for.
    """
    held = (db.query(m.ApplyQueue.user_id,
                     func.min(m.ApplyQueue.id).label("rid"))
            .filter(m.ApplyQueue.status == "holding",
                    m.ApplyQueue.hold_until.isnot(None),
                    m.ApplyQueue.hold_until <= m.now())
            .group_by(m.ApplyQueue.user_id)
            .order_by(func.min(m.ApplyQueue.id).asc())
            .limit(limit).all())
    ids = [r.rid for r in held]
    seen = {r.user_id for r in held}
    if len(ids) < limit:
        ready = (db.query(m.ApplyQueue.user_id,
                          func.min(m.ApplyQueue.id).label("rid"))
                 .filter(m.ApplyQueue.status == "prepared")
                 .group_by(m.ApplyQueue.user_id)
                 .order_by(func.min(m.ApplyQueue.id).asc())
                 .limit(limit * 2).all())
        for r in ready:
            if r.user_id in seen:
                continue
            seen.add(r.user_id)
            ids.append(r.rid)
            if len(ids) >= limit:
                break
    if not ids:
        return []
    # Fetched in one query, returned in the order decided above — `IN` does
    # not preserve it, and held-before-ready is the whole point of the order.
    rows = {r.id: r for r in db.query(m.ApplyQueue)
            .filter(m.ApplyQueue.id.in_(ids)).all()}
    return [rows[i] for i in ids if i in rows]
