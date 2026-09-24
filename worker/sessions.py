"""Holding one page open so a person can see it and reach into it.

The rest of the worker is fire-and-forget: open a row, drive it, close the
context. This is the opposite — a context that stays alive across passes
because somebody is looking at it, sending a frame out and taking clicks
back in.

Why it exists at all: an iframe cannot show these sites. Ashby and Workday
both send `X-Frame-Options: DENY`, and Workday is exactly the one where a
candidate has to sign in. A picture is not an iframe, so no header of theirs
applies to it.

Three things this is deliberately not:

**It is not a browser.** A session is bound to one queued row and opens that
row's URL. Letting it go anywhere would be handing out a server-side proxy
to the whole internet, from our IP, to anyone with an account.

**It is not long-lived.** A held context is memory here and an open session
on somebody's employer account. Anything past `expires_at` is closed, and
the app only extends that while a person is actually doing something.

**It does not type on its own.** Every action in the queue came from a
person clicking or typing in their own browser. Nothing in this file
decides what to put in a field.
"""
import base64
import json
import traceback
import datetime as dt

# The page is kept between passes, keyed by session id. This is the only
# state the worker holds in memory, and it is bounded by the one-session-per-
# person rule the API enforces plus the expiry swept below.
_LIVE = {}


def _now(m):
    return m.now()


def _aware(when):
    if when is None:
        return None
    return when if when.tzinfo else when.replace(tzinfo=dt.timezone.utc)


async def _frame(page):
    """One PNG of the page, base64, or "" if it cannot be taken."""
    try:
        raw = await page.screenshot(type="png", full_page=False)
        return base64.b64encode(raw).decode()
    except Exception:
        return ""


async def _apply(page, acts):
    """Do what the person did, in the order they did it.

    Coordinates arrive in frame pixels — the same pixels the screenshot was
    taken in — so they can be used directly. The scaling back from whatever
    size the image is displayed at happens in the browser, where the display
    size is actually known.
    """
    for a in acts:
        kind = (a.get("kind") or "").lower()
        x, y = int(a.get("x") or 0), int(a.get("y") or 0)
        text = a.get("text") or ""
        try:
            if kind == "click":
                await page.mouse.click(x, y)
                await page.wait_for_timeout(120)
            elif kind == "type":
                # Typed into whatever has focus, which is what the click
                # before it selected. keyboard.type rather than fill,
                # because a React field wants the keystrokes.
                await page.keyboard.type(text, delay=18)
            elif kind == "key":
                await page.keyboard.press(text or "Enter")
                await page.wait_for_timeout(150)
            elif kind == "scroll":
                await page.mouse.wheel(0, y or 300)
                await page.wait_for_timeout(120)
        except Exception as e:
            print(f"[session] {kind} failed: {type(e).__name__}: {e}",
                  flush=True)


async def serve(browser, db, m):
    """One pass over the sessions: open what was asked for, update what is
    live, and close what has expired or been finished with.

    Called from the worker's main loop alongside the queue, so a person
    watching a page does not have to wait for a queue of applications to
    drain before their next frame arrives.
    """
    rows = db.query(m.ApplySession).filter(
        m.ApplySession.status.in_(["asked", "live"])).limit(12).all()
    seen = set()

    for s in rows:
        seen.add(s.id)
        exp = _aware(s.expires_at)
        if exp and m.now() > exp:
            await drop(s.id)
            s.status = "closed"
            s.note = ("Closed after a spell of no activity. Open it again "
                      "whenever you are ready.")
            s.updated_at = m.now()
            db.commit()
            continue

        try:
            if s.id not in _LIVE:
                # A session is bound to its row's URL and opens nothing else.
                ctx = await browser.new_context(
                    viewport={"width": s.width or 1100,
                              "height": s.height or 760},
                    accept_downloads=False)
                page = await ctx.new_page()
                await page.goto(s.url, wait_until="domcontentloaded",
                                timeout=60000)
                await page.wait_for_timeout(1200)
                _LIVE[s.id] = (ctx, page)
                s.status = "live"
                s.note = ("This is the employer's own page, running here. "
                          "Click and type as you would normally.")

            ctx, page = _LIVE[s.id]

            if s.acts:
                try:
                    acts = json.loads(s.acts)
                except Exception:
                    acts = []
                s.acts = ""
                db.commit()
                if isinstance(acts, list) and acts:
                    await _apply(page, acts)

            shot = await _frame(page)
            if shot:
                s.shot = shot
                s.shot_at = m.now()
                s.url = page.url
            s.updated_at = m.now()
            db.commit()
        except Exception as e:
            traceback.print_exc()
            await drop(s.id)
            s.status = "closed"
            s.note = f"The page could not be kept open: {type(e).__name__}"
            s.updated_at = m.now()
            db.commit()

    # Contexts whose row is gone or closed. Without this the worker holds a
    # browser per session it ever opened, which is the slow leak that turns
    # into "the worker fell over" three days later.
    for sid in [k for k in _LIVE if k not in seen]:
        await drop(sid)


async def drop(sid):
    """Close and forget one session's context. Safe to call twice."""
    got = _LIVE.pop(sid, None)
    if not got:
        return
    ctx, _page = got
    try:
        await ctx.close()
    except Exception:
        pass


async def drop_all():
    for sid in list(_LIVE):
        await drop(sid)
