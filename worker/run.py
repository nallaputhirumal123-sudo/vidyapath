"""The loop. A second Railway service off the same repo, nothing else.

It polls apply_queue, dispatches each row to the adapter for its source, and
runs the state machine in flow.py. Everything that needs a browser is here;
everything that needs a decision is there, which is what lets the decisions
be tested without Chromium.

Why it imports main rather than redeclaring the models: there is one
definition of ApplyQueue, one of question_norm, one set of caps. Two copies
that drift by one column is how a worker starts writing rows the web app
cannot read. The cost is that this image carries the web dependencies too,
which is fine — the constraint is the other direction, that the web image
must not carry Chromium.

Rails, all on by default:

  APPLY_KILL_SWITCH       set to anything and every worker stops, now
  APPLY_HOLD_MINUTES      15; 0 sends immediately
  APPLY_MAX_PER_USER_DAY  20
  APPLY_MAX_PER_COMPANY_HOUR  2, across all candidates
  APPLY_POLL_SECONDS      20 between passes
  APPLY_SHOTS_DIR         where the review screenshots go

One session per ATS host, and a randomised gap between applications. Neither
is bot-detection evasion and neither should become it: there is deliberately
no fingerprint spoofing and no proxy rotation here, because the ATSs that
detect those blacklist the applicant rather than the bot, and the applicant
is the person we are supposed to be helping.
"""
import asyncio
import os
import random
import sys
import traceback
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main as m                                          # noqa: E402
from worker import flow                                   # noqa: E402
from worker import sessions                                # noqa: E402
from worker.adapters import adapter_for                   # noqa: E402
from worker.resume import resume_file_for                 # noqa: E402

POLL_SECONDS = max(5, int(m.env("APPLY_POLL_SECONDS", "20") or 20))
SHOTS_DIR = m.env("APPLY_SHOTS_DIR", "/tmp/vp-apply-shots")
# Between two applications. A range and not a constant: a fixed sleep makes a
# queue of twenty land on a board at exactly twenty-second intervals, which
# is a pattern no human produces and no rate limiter likes.
GAP_SECONDS = (float(m.env("APPLY_GAP_MIN", "6") or 6),
               float(m.env("APPLY_GAP_MAX", "18") or 18))

# One concurrent session per ATS host. Two browser tabs filling two forms on
# one board at the same moment is both rude and the fastest way to be
# throttled — and the rows are not in a hurry.
_HOST_LOCKS = {}


def host_of(url):
    try:
        return (urlparse(url or "").netloc or "unknown").lower()
    except Exception:
        return "unknown"


def lock_for(url):
    host = host_of(url)
    if host not in _HOST_LOCKS:
        _HOST_LOCKS[host] = asyncio.Lock()
    return _HOST_LOCKS[host]


async def run_one(browser, db, row):
    """One row, in its own browser context.

    A fresh context per application, not a shared one. Cookies from the last
    employer's board have no business on the next employer's form, and a
    context that has accumulated six sites' state is a context that behaves
    differently from a person's.
    """
    adapter = adapter_for(row.source)
    if adapter is None:
        # Should not reach here — enqueue refuses unknown sources — but a row
        # can outlive the list it was queued against.
        return flow._fail(
            db, m, row,
            f"We do not drive {row.source or 'that'} application forms. "
            "Open it and apply manually.")

    resume_path = None
    if row.status == "prepared":
        resume_path = resume_file_for(db, row.user_id, m,
                                      os.path.join(SHOTS_DIR, "resumes"))

    async with lock_for(row.url):
        ctx = await browser.new_context(
            viewport={"width": 1366, "height": 900},
            accept_downloads=False)
        page = await ctx.new_page()
        try:
            return await flow.run_row(db, m, row, adapter, page, SHOTS_DIR,
                                      resume_path)
        finally:
            try:
                await ctx.close()
            except Exception:
                pass


async def pass_once(browser, db):
    """One sweep of everything that is due. Returns how many rows moved."""
    rows = flow.due_rows(db, m)
    if not rows:
        return 0
    moved = 0
    for row in rows:
        if m.apply_halted():
            raise flow.Halted()
        try:
            await run_one(browser, db, row)
            moved += 1
        except flow.Halted:
            raise
        except Exception:
            # run_row already records against the row; this is the last net,
            # for something that broke outside it — launching a context, for
            # instance. It must not take the loop down with it.
            traceback.print_exc()
        await asyncio.sleep(random.uniform(*GAP_SECONDS))
    return moved


async def main_loop():
    from playwright.async_api import async_playwright

    print(f"apply worker up; poll {POLL_SECONDS}s, "
          f"hold {m.apply_hold_minutes()}m, "
          f"{m.apply_max_per_user_day()}/user/day, "
          f"{m.apply_max_per_company_hour()}/company/hour", flush=True)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(args=["--no-sandbox"])
        try:
            while True:
                if m.apply_halted():
                    # Not an exit. The switch is meant to be turned back off
                    # without a redeploy, so the process stays alive and idle
                    # and picks up again the moment it is.
                    print("APPLY_KILL_SWITCH is set — halted.", flush=True)
                    await asyncio.sleep(POLL_SECONDS)
                    continue
                db = m.SessionLocal()
                try:
                    # Live sessions first, and every pass. Somebody watching
                    # a page must not wait for a queue of applications to
                    # drain before their next frame arrives — a second of
                    # lag is a channel, ten is a broken feature.
                    try:
                        await sessions.serve(browser, db, m)
                    except Exception:
                        traceback.print_exc()
                    moved = await pass_once(browser, db)
                except flow.Halted:
                    print("APPLY_KILL_SWITCH set mid-pass — stopping here.",
                          flush=True)
                    moved = 0
                finally:
                    db.close()
                # A live session needs frames, not a twenty-second poll. The
                # loop tightens to a second while anybody is watching and
                # goes back to its normal pace when nobody is.
                watching = bool(sessions._LIVE)
                await asyncio.sleep(
                    1 if (moved or watching) else POLL_SECONDS)
        finally:
            # Held session contexts go before the browser does, or their
            # close() races a browser that has already gone.
            await sessions.drop_all()
            await browser.close()


if __name__ == "__main__":
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print("apply worker stopped", flush=True)
