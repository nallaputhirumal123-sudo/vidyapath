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
| `dalia.py` | Who the tutor is: the grade-band adapter, the system prompt, and the allowlist of panels she may open. No model call, no network. |
| `craxlearn.py` | Which pool a learner's questions live in, which half of the product an account may reach, and the registry of open sources. Policy, not plumbing. |
| `craxlearn.webmanifest`, `craxlearn-sw.js` | What makes Craxlearn installable on a smart board. The worker caches the shell only — never `/api/`, because a stale mark or fee balance is worse than none. |
| `craxlearn.html` | **Craxlearn**: the institution app. A separate page for schools, colleges and coaching centres, sized for the display at the front of a classroom. No job-board code in it at all. Served at `/craxlearn`. |
| `index.html` | The learner/candidate app. One page, ~300KB, inline CSS and JS. |
| `admin.html` | Admin panel. Separate page, same pattern. |
| `terms.html`, `privacy.html` | Legal. Read them before changing anything that touches personal data. |
| `extension/` | Manifest V3 autofill extension. |
| `tests/` | Six headline suites, plain Python scripts. No pytest. |

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

Six suites, all runnable directly, all must pass before committing:

- `test_sweep.py` — end-to-end pass over every user-facing path
- `test_security.py` — auth boundaries, tampering, injection shapes
- `test_regressions.py` — every bug previously fixed, so it stays fixed
- `test_billing.py` — Stripe checkout and webhooks, against an intercepted call
- `test_free_trial.py` — what the free plan does and does not include
- `test_dalia.py` — the tutor's grade band, the panels she may open, and
  the four network labs, each run through the real packet engine
- `test_craxlearn.py` — the fence between two institutions' cached answers,
  and that every source of answer material is an open one
- `test_craxlearn_only.py` — what an institution and an under-18 cannot
  reach, asserted at the API rather than in the sidebar
- `test_classwork.py` — board → assignment → submission → review, end to end
- `test_office.py` — attendance, fees and notices, and the staff who may not
  touch them
- `test_roll.py` — which learners a teacher may see, and the calculator's
  allowlist
- `test_classcode.py` — code-only login, materials, and the account reset
  (runs against its own database)

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

**`onupdate=now` fires on every write, including yours.** `Submission.updated_at`
means "when the student last handed in", and a teacher marking the work is a
write to that row — so it moved to the marking time, and "waiting again"
(computed from `updated_at > reviewed_at`) fired the instant anything was
reviewed. Assigning the old value back does NOT fix it: an identical value is
not a change, so the column stays out of the UPDATE and `onupdate` applies
anyway. `flag_modified(sub, "updated_at")` is what forces it into the SET
clause. Watch for this on any column with `onupdate`.

**Craxlearn is a separate page, not a mode.** `craxlearn.html` is what a
school buys: a URL to put on a classroom board and hand to a fourteen-year-old.
It contains no job-board code, which is the point — a single app with the job
half hidden behind a flag is one bug away from showing it, and the person who
finds that bug is a child. `tests/test_craxlearn_only.py` greps the served page
for `/api/jobs`, `/api/billing` and friends and fails if any appear.

**The job half is closed by one middleware, not by fifty dependencies.**
`_craxlearn_gate` matches `craxlearn.JOB_SIDE` by path prefix. The matching is
deliberately greedy and there is no exception list: if a teaching route ever
needs a name starting with a job-side prefix, rename the route. A test walks
the live route table and fails if any route belongs to neither half, so the
endpoint somebody adds next month is covered or the build goes red.

**Proof of age is demanded inside institutions, not outside them.** An empty
`dob` blocks the job side for an institution learner and does not for anybody
else — see `craxlearn.age_ok`. Making silence mean "child" everywhere was
tried and it takes the job board, the resume builder and their own billing
page away from every existing account on the day it ships. `REQUIRE_DOB=1`
turns it on for a deployment that has planned the email.

**Craxlearn's spaces: `main()` is not `#main`.** Up to four tools open at
once, and the board modules ask for `#main` by name — so `window.$` answers
that with whichever space is being drawn into. Two traps came out of it and
both are fixed: an inline `flex` in `paintPanes` beat the 2x2 grid rule and
laid four spaces out as four unreadable columns, and an async page function
resolved after `DRAW` had moved on and wrote its result into the wrong space.
Renders are now awaited one at a time so `DRAW` stays put, and a tool already
open elsewhere is not offered — every tool names its fields by id, so two
copies would write into the same boxes.

**External URLs are verified before a class sees them.** PhET sim ids are
candidates in `craxlearn.PHET_SIMS`, and `/api/craxlearn/phet` fetches each
one before offering it. An id we have wrong simply never appears. Never
hardcode an external URL into a lesson surface without a check — the cost of
a wrong one is a 404 on the board mid-lesson with thirty people watching.

**Who may see a learner is one function.** `_may_see_learner` — the rule is
the CLASSROOM, not the school. Everything showing a learner's detail goes
through it, written once, because two copies would drift until one let
somebody through. A subject teacher sees the rooms they hold a subject in; a
head and the office see their school. Lookup by student id searches only
inside that set and answers 404 for a code that exists elsewhere: "exists but
not yours" is still a fact about somebody's child.

**Three school roles, and the split is deliberate.** `teacher` is the class
and nothing else; `head` runs the teaching and creates staff profiles;
`schooladmin` is the office and owns attendance, fees and notices. A head
cannot keep the register and a teacher cannot write off a fee — schools have
separated those duties for a century and copying it is cheaper than explaining
why we did not. A head can *appoint* the office but not appoint themselves to
it: `/api/head/staff` refuses to change the requesting account's own role.

**The cache key IS the question.** `AskCache` is keyed on the normalised
question text and serves one person's stored answer to the next person who
asks the same thing. That is the whole cost model, and it means an unscoped
key is a route from one school's session into another's. Every key is now
built by `craxlearn.key(scope, ...)`, the scope goes first, and the `scope`
column is filled by a `before_insert` listener rather than by the twelve
places that write to the table — because the one that forgets would not
raise, it would quietly serve a school's question to a stranger. Never build
a cache key by hand.

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
| `CRAXLEARN_ONLY` | Serve only the teaching half. The job board 404s for everybody including admins, and `/` serves `craxlearn.html`. For an institution running its own instance |
| `REQUIRE_DOB` | Demand a stated date of birth from everybody, not only institution learners. Off by default: switching it on locks out every existing account until each fills one in |

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

## Further reading

- **`docs/MATCHING.md`** — the scoring model, why each weight and band is the
  number it is, how categorisation and scope decide what reaches the board, and
  the field-extraction traps. Read it before changing anything in `_score_job`,
  `_ROLE_FAMILIES` or `_job_in_scope`.
- **`docs/ADDING-A-JOB-SOURCE.md`** — adding a board or an aggregator, and the
  slug verification step that is not optional.

## Commit history

`git log` is the real documentation. Every non-obvious decision was recorded
with its reasoning, including the bugs above and how they were found. Read it
before assuming something is arbitrary.
