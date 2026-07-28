# Craxle — architecture and working notes

For whoever picks this up next. It covers how the thing is laid out, how to run
and test it, and — most usefully — the traps that have already cost time.

## What it is

A job board and learning platform. Two products in one codebase:

- **Job seekers** pay for resume matching, an application tracker, apply kits
  and a browser extension. Browsing jobs and the courses are free.
- **Employers** post a role and reach opted-in candidates whose resume matches,
  anonymously until the candidate accepts.

## Layout

| Path | What it is |
|---|---|
| `main.py` | The entire backend. ~7,000 lines, FastAPI + SQLAlchemy. |
| `index.html` | The learner/candidate app. One page, ~300KB, inline CSS and JS. |
| `admin.html` | Admin panel. Separate page, same pattern. |
| `terms.html`, `privacy.html` | Legal. Read them before changing anything that touches personal data. |
| `extension/` | Manifest V3 autofill extension. |
| `tests/` | Five suites, plain Python scripts. No pytest. |

`main.py` is one file on purpose. It is a single deployable with no import
graph to reason about, and everything is greppable. If you split it, split it
along the section banners already in the file.

## Running it

```bash
.venv/Scripts/python.exe -m uvicorn main:app --reload --port 8011
```

Local uses SQLite (`vidyapath.db`, gitignored). Production is Postgres on
Railway via `DATABASE_URL`. Schema changes are applied by `_migrate_columns()`
at startup — plain `ADD COLUMN`, non-destructive, no migration tool.

**New columns must be nullable.** `ADD COLUMN ... NOT NULL` fails on a table
that already has rows, and the migration swallows the error, so the column
silently never appears in production. Add it nullable and treat NULL as the
default in code.

## Tests

```bash
.venv/Scripts/python.exe -X utf8 tests/test_sweep.py
```

Five suites, all runnable directly, all must pass before committing:

- `test_sweep.py` — end-to-end pass over every user-facing path
- `test_security.py` — auth boundaries, tampering, injection shapes
- `test_regressions.py` — every bug previously fixed, so it stays fixed
- `test_billing.py` — Stripe checkout and webhooks, against an intercepted call
- `test_free_trial.py` — what the free plan does and does not include

They run against the local SQLite database and create real rows. That is
deliberate: matching quality is only meaningful against real job data.

## Traps

**`index.html` cannot be syntax-checked with `node --check`.** The file
contains the literal `<script` inside a JS string, so extracting the main block
truncates it and the check fails even on a known-good commit. Verify instead by
comparing brace/paren deltas against HEAD and loading the page in a browser.
`admin.html` has no such string, so `node --check` *does* work there — use it.

**Escapes get eaten.** Writing `\n` into a file through a shell heredoc has
collapsed into a literal newline more than once, producing an unterminated
string. In `admin.html` the newline constant is `String.fromCharCode(10)` for
exactly this reason. Prefer Python scripts over heredocs for edits.

**One inline script per HTML file.** A syntax error anywhere in `index.html`'s
script takes down the whole app, not one feature. There is no module boundary.

**Nothing is deployed until it is pushed.** Railway auto-deploys `main`.
Check `https://craxle.com/api/version` — it reports version and commit.

## Things that look wrong but are not

- **`defer(Job.text)` is not used in matching.** It was tried; it made matching
  *slower* (2.7s to 6.5s) because of N+1 lazy loads. The comment in the code
  says so.
- **`_families()` is not called per job when scoring.** The role family is
  computed once at ingest and stored on `Job.category`. Re-deriving it per job
  took matching from 0.3s to over 30s.
- **Invites store the score rather than recomputing it.** The candidate must
  see the number the employer saw; recalculating later would silently change
  what was already communicated.
- **A blank `country` is kept, not dropped.** Sources spell country
  inconsistently and remote listings often omit it entirely.

## The crawl

Runs every `JOB_REFRESH_HOURS` (default 1, production 6), on boot and then on a
loop. Sources are public ATS endpoints — Greenhouse, Lever, Ashby, Workable,
Recruitee, Workday, SmartRecruiters — plus free aggregators and Adzuna/Jooble
where keys are set.

Three failures cost a day of debugging and are all now fixed. Read them before
touching `_collect_jobs` or `_store_jobs`:

1. **Serial fetching.** 263 boards at 25s timeout each never finished before
   the container restarted. Now concurrent behind a semaphore of 12, capped at
   10 minutes total.
2. **Duplicates within one batch.** Workday paginates with overlap. The first
   copy sat pending in the session, the duplicate's lookup found nothing and
   inserted again, and the unique constraint failed the whole batch — 17,000
   rows discarded because of 102 repeats.
3. **Concurrent crawls.** The hourly loop and the admin button could run at
   once and collide on insert. `_refresh_jobs` now takes a process-wide lock.

**Verify board tokens before adding them.** ~90 company slugs were added by
guessing and 153 turned out to be 404s, wasting a third of every crawl. The
per-source report from *Check crawl status* in admin shows what each board
actually returned.

## Environment

Set in Railway. None have secrets in code.

| Variable | Notes |
|---|---|
| `DATABASE_URL` | Postgres in production |
| `JWT_SECRET` | Required; sessions break if it changes |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | Live and test are separate; mixing them takes payments and fails every webhook |
| `MAIL_FROM`, `RESEND_API_KEY` | SMTP is blocked on Railway; mail goes over Resend's HTTP API |
| `JOB_COUNTRIES`, `JOB_FAMILIES` | Board scope, enforced at ingestion |
| `JOB_REFRESH_HOURS`, `JOB_RETENTION_DAYS` | Crawl cadence and history |
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `ADZUNA_COUNTRIES`, `ADZUNA_PAGES` | Widen countries only alongside `JOB_COUNTRIES` — fetching a country the board discards wastes quota |
| `JOOBLE_KEY` | Optional |
| `JSEARCH_KEY`, `JSEARCH_BASE` | Open Web Ninja, **not** RapidAPI — plain `X-API-Key` header. RapidAPI headers are refused before the call is metered, so the dashboard reads zero while every query errors |
| `JSEARCH_MONTHLY_CAP` | Hard ceiling on paid requests, set BELOW the plan. Raise it when you buy more and the crawler widens by itself |
| `JSEARCH_PER_CRAWL` | `auto` (default) spends what is left of the month divided by the crawls left in it. A number pins it instead |
| `JSEARCH_PAGES`, `JSEARCH_WINDOW` | Pages per query; `date_posted` window, default `month` — a week threw away most of what each request had already paid for |
| `JOB_ALERT_MIN` / `JOB_ALERT_FLOOR` | 90 / 70. MIN flags an exceptional match; FLOOR is the bar for the best of what actually arrived. Measured on the live board, nothing scores above ~77, so a single bar at 80+ means silence — see v3.32.0 |
| `JOB_ALERT_MAX` | Matches one sweep may send. Everything above the bar goes, one alert each |
| `GEMINI_API_KEY` / `GROQ_API_KEY` | AI features; the app runs without them |

## Colour and contrast

Status colours are tokens — `--ok`, `--warn`, `--bad` and their `-bg` / `-bd`
variants — declared once for dark and again under `[data-theme="light"]`.
**Never write a status hex inline.** A pale mint reads beautifully on
near-black and disappears on white, which is exactly what happened: light mode
inherited greens chosen for the dark theme and the text went to nothing. 33
hardcoded values were converted in v3.39.0.

The one deliberate exception is the smart board's chalkboard (`#8fe3b0` and
friends): that surface is dark green in **both** themes, so it needs colours
picked for dark and must not be tokenised.

Anything a candidate reads to decide whether to apply sits at 12.5px or above.
Measured against the card in both themes, everything on a match card is past
4.5:1.

## Personal data

The hiring feature shares candidate data with third parties. Three rules, all
load-bearing:

1. **Consent is opt-in.** `open_to_work` defaults off and only the candidate
   can set it.
2. **Employers see an anonymous profile** — skills, seniority, score. The
   candidate reference is a salted hash, not the user id, so employers cannot
   enumerate accounts or correlate someone across searches.
3. **Contact details are released by acceptance and nothing else.**

`terms.html` and `privacy.html` describe this, and `test_sweep.py` fails if
either stops saying so. If you change what employers can see, change the
documents in the same commit — the code being right does not help if the
contract the user agreed to says otherwise.

## Commit history

`git log` is the real documentation. Every non-obvious decision was recorded
with its reasoning, including the bugs above and how they were found. Read it
before assuming something is arbitrary.
