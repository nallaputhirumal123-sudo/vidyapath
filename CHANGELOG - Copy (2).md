# VidyaPath — Changelog

The version number lives in the `VERSION` file. It appears in the app footer,
the admin panel, `/api/status`, and the deployment logs — so you can always
tell which build Railway is actually running.

**Bump it every time you push.** Then compare the number on your live site
with this file. If they differ, Railway has not deployed your latest code.

Format: MAJOR.MINOR.PATCH
- **PATCH** — bug fix, typo, small correction
- **MINOR** — new lessons, new feature
- **MAJOR** — something that breaks or replaces existing behaviour

---

## 1.5.0 — Ask Vidya anything

- **New section: an AI teacher you can ask anything.** Pick a subject
  (Science, Maths, Computers, Medicine, Business, History, and more) and a
  level (Class 1 to Expert), then ask by voice or by typing. Vidya writes the
  answer on a chalkboard, one line at a time, and reads it aloud.
- **Costs stay tiny.** Every answer is cached in the database on a normalized
  key, so a repeated question — even with different spacing or casing — is
  served instantly and free. You only pay for genuinely new questions.
- **Works with a free AI provider.** The teacher is provider-switchable:
  set `GEMINI_API_KEY` (Google's free tier, recommended), `GROQ_API_KEY`
  (also free), or `ANTHROPIC_API_KEY` (paid). It auto-detects from whichever
  key you set; `AI_PROVIDER` can force a choice. Switching later is one
  variable, no code change.
- **The API key never touches the browser.** A server endpoint (`/api/ask`)
  holds the key and talks to the model; the page only talks to your own
  server. Calling the AI directly from the browser would have exposed the
  key and been blocked by CORS.
- **Degrades gracefully.** With no key set, the section shows a friendly
  "not set up yet" note; nothing else on the site is affected.
- `/api/status` now reports `ask_vidya_enabled` so you can confirm it is on.

## 1.4.4 — Copy and layout polish

- Dashboard welcome text updated: it still said "Nine tracks" and "a lab"
  from before the six-stage restructure. Now describes the real structure
  and computes the average exercises-per-lesson from live data.
- Path cards show the first four tracks then "+N more" — the AI Engineer
  path was listing ten chips and dominating the page.

## 1.4.3 — Empty environment variables

- **Fixed the app crashing on import with "Could not parse SQLAlchemy URL
  from string ''".** `os.environ.get(name, default)` only falls back when a
  variable is MISSING. A variable that exists but is EMPTY returns `""` —
  which is exactly how an unresolved Railway reference arrives.
- All environment variables now go through `env()`, which treats empty and
  whitespace-only values as absent.
- An unresolved `${{ ... }}` reference is detected and falls back to SQLite
  with a clear warning, rather than crashing the container.

## 1.4.2 — Line endings fix

- **Fixed the container dying with no log output.** Git on Windows rewrites
  line endings, turning `#!/bin/sh` into `#!/bin/sh\r`. Linux then looks for
  an interpreter literally named `sh\r`, fails, and the container exits
  before printing anything — so the healthcheck had nothing to reach.
- Added `.gitattributes` forcing LF on `.sh`, `Dockerfile` and `VERSION`.
- Dockerfile strips carriage returns and runs `sh /app/start.sh` rather than
  relying on the shebang or the executable bit.

## 1.4.1 — Deployment fix

- **Fixed repeated healthcheck failures.** `railway.json` set a `startCommand`
  that was not run through a shell, so `$PORT` was passed to uvicorn as a
  literal string. Uvicorn crashed before it could answer `/api/health`, and
  every deploy failed with "1/1 replicas never became healthy".
- Startup now goes through `start.sh`, which resolves `$PORT` properly,
  prints which environment variables are set, and reports an import error
  clearly instead of dying silently.
- Startup retries the database five times over 20 seconds, then starts anyway
  so `/api/status` can be read to see what is wrong.
- `/api/status` now survives a broken database and explains the failure.

## 1.4.0 — Vidya presenter

- Full-body animated presenter with gesturing arms, breathing and blinking
- 18-line spoken guided tour of the whole course, using live lesson counts
- Tour buttons on the landing page, dashboard and study guide
- Version tracking added — visible in app, admin, `/api/status` and logs

## 1.3.0 — Mathematics for AI

- New Maths track: linear algebra, statistics, probability, calculus
  (4 lessons, 32 exercises, all computed by hand in runnable code)
- Honest Roadmap page mapping all 80+ requested topics
- Daily challenge on the dashboard — same exercise for everyone each day
- Totals: 45 lessons, 289 exercises, 360 written questions

## 1.2.0 — Themes and admin recovery

- Light and dark themes with a toggle, remembered per device
- Admin bootstrap fixed: `ADMIN_PASSWORD` now resets the password on boot
  (previously it only worked when creating a brand-new account)
- `/api/status` diagnostic endpoint, with emails masked
- One-click "Reload curriculum from files" button in the admin panel
- Static file route added — `tutor.js` was silently returning HTML

## 1.1.0 — Gamification and landing page

- Landing page with hero, features, six-stage outline and FAQ
- XP, levels and streaks — computed from records, never stored
- Per-stage printable certificates
- Mobile drawer navigation, larger touch targets, no input auto-zoom
- Fixed: AI Engineering track was invisible due to a stage key mismatch

## 1.0.0 — Full curriculum and platform

- Six stages, 41 lessons: beginner → Python → SQL → data → ML → AI → career
- Every exercise auto-graded and verified to pass its own grader
- Vidya tutor with browser speech and contextual guidance
- Printable worksheets with teacher answer keys
- FastAPI backend, Postgres, admin panel with drop-off analytics
- Single-file study guide that works offline
