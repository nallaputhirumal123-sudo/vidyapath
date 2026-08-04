# Tests

Run these before every deploy. They talk to the app through its real HTTP
routes, so they catch the things unit tests miss — auth, permissions, payment
gating, and whether a page still renders.

```bash
.venv/Scripts/python.exe tests/test_sweep.py        # everything a user touches
.venv/Scripts/python.exe tests/test_security.py     # boundaries and tampering
.venv/Scripts/python.exe tests/test_regressions.py  # bugs that already bit us once
```

They run against `vidyapath.db` (SQLite) and create throwaway accounts. Never
point them at production: `DATABASE_URL` is set at the top of each file and
should stay pointing at the local database.

## What each one covers

**test_sweep.py** — signup, login, the two-device limit, password reset without
leaking whether an account exists, job search and paging, matching speed and
quality, the tracker, plan limits, interview prep, extension pairing, the
curriculum, and that the legal pages carry no leftover placeholders.

**test_security.py** — one user cannot read or clear another's data, forged and
unsigned webhooks are rejected so nobody can grant themselves a plan, expired
and reused reset tokens fail, hostile input never 500s, limits are enforced
rather than suggested, and source files and the database are not served.

**test_dalia.py** — who the tutor thinks she is teaching, and what she is
allowed to put on the screen. The grade band read out of a free-text level
("Class 8", "B.Tech 2nd year", "PhD"), the control tags parsed back out of a
reply, and — the bulk of it — everything that gets DROPPED: a sandbox language
nothing here runs, a network topology nobody built, markup smuggled in as a
topic. The four network labs are each run through the real packet engine and
their verdicts compared with the ones documented beside them, so a lab cannot
quietly start teaching the wrong answer. Ends with the talk endpoint end to
end against a stubbed model, including that a cached reply still opens the
same panels the first asker got.

**test_regressions.py** — every bug that has already reached production once.
Matching scoring unrelated roles highly, degrees being read as seniority, dead
listings from a retired source, JSON parsing breaking on a model preamble,
newer AI models spending their whole budget on internal thinking, blocked SMTP
hanging the site, and the substring match that blocked "preferred" fields in
the autofill extension.

## Reading the output

A failing check prints the expectation and what happened. Some failures are
the **test** being out of date rather than the app being broken — for example,
changing the plan structure or the free-tier allowance will fail assertions
that hardcode the old numbers. Confirm which it is before changing code:
run the endpoint by hand and look at the response.

## What is not covered

Be aware of the gaps rather than trusting a green run:

- **Live payments.** Stripe is only exercised as far as rejecting
  forged webhooks. No real charge, refund or cancellation has ever run.
- **Google sign-in.** The OAuth round trip cannot be automated here. A bug that
  rejected every new Google account survived a full green sweep because the
  tests only used email signup.
- **Email delivery.** Sending is stubbed out. That a message was composed does
  not prove it arrives.
- **Real browsers.** Layout and theming were checked in Chromium only; Safari
  and real iOS are untested.
