"""Open real postings, fill them, and report — WITHOUT EVER SUBMITTING.

What this is for: the adapters are written from each ATS's documented markup
and tested against fixtures. Fixtures prove the logic; they cannot tell you
that a board quietly renamed its file input last month. This opens real
listings and reports what the deterministic filler managed and what it could
not, which is the only way to find out whether the selectors still match the
web as it is today.

WHAT IT WILL NOT DO
-------------------
It never attaches a file and never clicks submit. That is not a promise in a
comment, it is the structure: this module calls `open`, `fill` and `answers`
and there is no code path from here to `attach` or `submit`. The adapter is
also wrapped so that calling either one raises, in case a future edit adds a
call by accident.

So no application is ever sent by this tool, to anybody. Everything it does
to a page happens in a headless browser on this machine: filler.js writes
into DOM nodes, nothing is posted anywhere.

WHAT IT COSTS THE EMPLOYER
--------------------------
One page load each, with a pause between, which is less than a person
browsing the same listings. It is the same traffic the crawler already makes
against these boards' APIs.

    python tools/apply_dryrun.py --limit 20
    python tools/apply_dryrun.py --limit 5 --source lever
"""
import argparse
import asyncio
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main as m                                          # noqa: E402
from worker import flow                                   # noqa: E402
from worker.adapters import adapter_for                   # noqa: E402


class ReadOnly:
    """An adapter with its two sending methods removed.

    Wrapping rather than trusting: if somebody later adds an `attach` call to
    the walk below, this turns it into a loud failure instead of an
    application arriving at an employer during a diagnostic run.
    """

    def __init__(self, inner):
        self._inner = inner
        self.source = inner.source

    async def open(self, page, url):
        return await self._inner.open(page, url)

    async def fill(self, page, profile):
        return await self._inner.fill(page, profile)

    async def answers(self, page, bank):
        return await self._inner.answers(page, bank)

    async def attach(self, *a, **k):
        raise RuntimeError("dry run: attach is not available")

    async def submit(self, *a, **k):
        raise RuntimeError("dry run: submit is not available")


def pick(db, limit, source):
    """Real open postings we hold a drivable form URL for, spread thin.

    One per employer, deliberately: twenty listings from one company is
    twenty page loads at one domain and tells you about one board's markup.
    Twenty employers tells you whether the adapter works.
    """
    # Real crawled postings only.
    #
    # The first run of this opened twenty of the test suite's own fixtures —
    # "Alpha 1790224960", "Example Co" — because those are Job rows the tests
    # write into the shared development database and they sort newest first.
    # Every one 404'd and the report said the adapters were broken, which was
    # a lie about the adapters and the truth about the picker.
    #
    # A crawled row carries the employer's description; a fixture never does.
    # That is the cheap, reliable difference, and ascending order puts the
    # real crawl first.
    q = db.query(m.Job).filter(m.Job.is_open.is_(True),
                               m.Job.source != "test",
                               m.Job.description != "",
                               m.Job.description.isnot(None))
    if source:
        q = q.filter(m.Job.source == source)
    seen, out = set(), []
    for j in q.order_by(m.Job.id.asc()).limit(6000).all():
        src = (j.source or "").lower()
        if src not in m.APPLY_DRIVABLE:
            continue
        url = m.apply_url_for(j)
        if not url:
            continue
        key = (src, (j.company or "").lower())
        if key in seen:
            continue
        seen.add(key)
        out.append((j, url))
        if len(out) >= limit:
            break
    return out


async def walk(rows, profile, bank, gap):
    from playwright.async_api import async_playwright

    report = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(args=["--no-sandbox"])
        for i, (job, url) in enumerate(rows, 1):
            src = (job.source or "").lower()
            ad = ReadOnly(adapter_for(src))
            ctx = await browser.new_context(viewport={"width": 1366,
                                                      "height": 900})
            page = await ctx.new_page()
            line = {"n": i, "source": src, "company": job.company,
                    "title": (job.title or "")[:46], "url": url,
                    "opened": False, "filled": [], "asks": [], "error": ""}
            try:
                await ad.open(page, url)
                line["opened"] = True
                got = await ad.fill(page, profile)
                line["filled"] = got.filled
                asks = await ad.answers(page, bank)
                line["asks"] = [q.label[:60] for q in asks]
            except Exception as e:
                line["error"] = f"{type(e).__name__}: {e}"[:150]
            finally:
                try:
                    await ctx.close()
                except Exception:
                    pass
            report.append(line)
            print(f"  [{i:>2}/{len(rows)}] {src:<16} {str(job.company)[:18]:<18} "
                  f"{'opened' if line['opened'] else 'FAILED':<7} "
                  f"filled={len(line['filled']):<2} asks={len(line['asks'])}"
                  + (f"  {line['error'][:60]}" if line["error"] else ""),
                  flush=True)
            if i < len(rows):
                await asyncio.sleep(random.uniform(*gap))
        await browser.close()
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--source", default="")
    ap.add_argument("--email", default="", help="whose profile to fill with")
    ap.add_argument("--gap", default="2,5")
    a = ap.parse_args()
    lo, hi = [float(x) for x in a.gap.split(",")]

    db = m.SessionLocal()
    user = (db.query(m.User).filter(m.User.email == a.email).first()
            if a.email else db.query(m.User).filter(m.User.plan != "free")
            .order_by(m.User.id.desc()).first())
    if user is None:
        print("No account to build a profile from. Pass --email.")
        return 2
    profile = flow.build_profile(db, m, user)
    bank = flow.load_bank(db, m, user.id)
    rows = pick(db, a.limit, a.source.lower())
    if not rows:
        print("No postings with a drivable form URL.")
        return 1

    print(f"\nDRY RUN — opens and fills, never attaches, never submits")
    print(f"profile from : {user.email}")
    print(f"bank answers : {len(bank)}")
    print(f"postings     : {len(rows)}\n")
    report = asyncio.run(walk(rows, profile, bank, (lo, hi)))

    ok = [r for r in report if r["opened"]]
    print(f"\n{'-' * 62}")
    print(f"opened {len(ok)} of {len(report)}")
    if ok:
        avg = sum(len(r["filled"]) for r in ok) / len(ok)
        print(f"fields filled, average: {avg:.1f}")
    by_src = {}
    for r in report:
        s = by_src.setdefault(r["source"], {"n": 0, "ok": 0, "asks": 0})
        s["n"] += 1
        s["ok"] += 1 if r["opened"] else 0
        s["asks"] += len(r["asks"])
    print(f"\n{'source':<18}{'opened':>8}{'of':>4}{'questions left':>16}")
    for s, v in sorted(by_src.items()):
        print(f"{s:<18}{v['ok']:>8}{v['n']:>4}{v['asks']:>16}")

    asks = {}
    for r in report:
        for q in r["asks"]:
            asks[q] = asks.get(q, 0) + 1
    if asks:
        print("\nquestions the bank could not answer, most common first:")
        for q, n in sorted(asks.items(), key=lambda x: -x[1])[:12]:
            print(f"  {n:>3}x  {q}")
    fails = [r for r in report if r["error"]]
    if fails:
        print("\nwhat failed:")
        for r in fails[:10]:
            print(f"  {r['source']:<16} {r['error'][:80]}")
            print(f"  {'':<16} {r['url'][:80]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
