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

## 1.36.0 — Automatic AI provider fallback

- If the primary AI provider is rate-limited or errors, the app now
  automatically tries the next configured provider (Gemini → Groq → Claude, in
  whatever order keys exist). One provider being tapped out no longer blocks the
  AI features — it uses whichever still has free quota.
- Self-test now reports the fallback order it will try.

## 1.35.0 — Admin AI self-test

- Added `/api/ai/selftest` (admin only): makes one tiny AI call and returns the
  raw provider result or the raw upstream error, so the exact reason (e.g. a
  Gemini quota/rate-limit message) is visible for debugging.

## 1.34.0 — Friendly AI rate-limit messages

- When the AI provider's free daily/rate limit is hit, users now see a clear,
  calm message ("The free AI limit has been reached for now — it refreshes
  shortly; try again in a little while") instead of a raw provider error.
- Applied across Ask Vidya and all resume checks (match, grammar, co-pilot).

## 1.33.0 — Resume redesign + 2 styles; careers with startups by country

- **Resume page redesigned.** The old wide "Completeness" bar is now a compact
  circular % meter, and the "Your resume" card now holds everything up top:
  load (check-only), save, new blank. Order below: match score → grammar →
  co-pilot → the builder itself.
- **Two ATS styles** — "Classic (left)" and "Centered" — both rendered by the
  same engine, so the live preview still equals the downloaded PDF exactly.
- Only the built resume is previewed; a loaded resume is used just for checks.
- **Careers: far more companies + a startups section per country.** India ~75
  and the US ~50 entries, plus every country now has a Startups list with
  founding years. Startups automatically graduate into the main company list as
  they mature (cutoff currently 8 years), so it re-sorts itself over time.

## 1.32.0 — Resume: build-only + check-an-existing; careers by country

- **Resume builder is build-from-scratch only.** Removed the import-into-builder
  flow and the "Target role & AI" auto-rewrite section. You build your resume in
  one clean ATS style; the live preview is exactly what downloads.
- **New "Check an existing resume" (analysis only).** Load a PDF/DOCX/TXT to get
  its job-match score, the exact changes to make, and a grammar check — it never
  edits or builds anything. The match, co-pilot and grammar tools all run on the
  loaded resume when one is present, otherwise on your built resume.
- **Careers: company career pages + job sites by country.** Pick your country
  (India, US, UK, Canada, Australia, UAE/Gulf, Singapore/SE Asia, Germany/Europe,
  Remote/Global) to see direct company careers links and the top job boards there.

## 1.31.0 — One clean ATS style; preview = download; all jobs imported

- **Back to the structured builder as the single path.** Uploading a resume now
  fills the builder fields (name, title, contact, summary, every job with its
  dates and bullets, skills, education) — no more separate "by section" mode.
- **Imports capture EVERY job, not just the first.** Rewrote the extraction to
  keep each job as its own entry with its own bullets, and raised all limits so
  nothing is dropped.
- **One ATS style, and the preview now equals the download.** Both are rendered
  from the same spec: navy headings with an underline and a clear gap before the
  body (headings no longer touch the text), dates right-aligned, real bullets.
- Removed the multi-style picker and the photo from the ATS output (ATS parsers
  can't read photos).

## 1.30.0 — Section-based resume editing (clean, not messy)

- **Uploaded resumes now open by SECTION, not by line.** We detect the real
  headings (Professional Summary, Skills, Experience, Education…) and give you
  one text box for each whole section — click a heading to open it. No more one
  box per wrapped line.
- **Bullet points and flow are preserved.** Content comes from clean text
  extraction (works for both PDF and DOCX), so no more broken □ symbols; each
  point stays on its own line and renders as a real bullet.
- **Preview and download are clean and identical** — name, navy section
  headings with underline, proper bullets, comfortable spacing (no touching
  lines). What you see is what you download.
- **Add / remove sections**, edit any heading, and edit the whole section body
  in place. Field-code junk (Word HYPERLINK tags) is stripped automatically.
- Dropped the pixel-exact layout approach (and the LibreOffice dependency, so
  builds are fast again) — it produced messy, fragmented results on real
  resumes. Section editing is cleaner and fully ATS-friendly.

## 1.29.0 — Word resumes keep their exact look; multi-page; spell-check

- **Word (.docx) uploads now keep their original design.** The server renders
  your Word file to PDF (LibreOffice) and reproduces it exactly — same fonts,
  spacing, and the coloured section-heading bars — instead of reformatting it
  into a template. Tested on a real 4-page resume: all 4 pages, every section.
- **Corrupt embedded images no longer block import.** A common export bug (a
  broken image inside the .docx) used to make the whole file fail to load; we
  now repair it automatically before converting.
- **All pages are shown and editable** — no more single-page cut-off, nothing
  silently dropped.
- **Preview matches the download**, including the coloured heading bars and text
  colours, all rebuilt from the original's real positions.
- **Uploaded resumes keep their own style;** the style picker now only appears
  when you start a brand-new resume.
- **New: spelling & grammar check.** Scans your resume and lists exactly what to
  fix (it never changes anything without you).

## 1.28.0 — DOCX import now captures your name, contact and all jobs

- **Fixed the big DOCX gap:** a name and contact details placed in the Word
  document's *header* (very common in resume templates) were being skipped
  entirely — the import came back with no name and no contact. We now read the
  header and footer parts too, so the name/email/phone come through.
- **Long resumes no longer truncated on import.** The parser reads far more of
  the document (up to ~16k characters) and returns more, so every job in your
  employment history is captured instead of stopping partway.

## 1.27.0 — Always-visible version badge + robust resume preview

- **Version badge on every page.** A small "VidyaPath v1.27.0" pill is now fixed
  to the bottom-right corner of every screen, so you can always tell exactly
  which build is live. After you deploy, it should read v1.27.0 — if it doesn't,
  the push didn't land.
- **Resume preview is now SVG** — it scales to fit the preview panel at any
  width and can't be clipped or appear blank in a narrow column.
- **PDF scanning limits raised** (up to 6 pages / 220 lines) so longer resumes
  are captured in full.

## 1.26.0 — Resume: keep your original layout, download an exact copy

- **Upload a PDF and keep its exact look.** We now scan every line's position,
  font size, weight and column, so what you download matches your uploaded file
  — headings, two-column layouts and all. Verified to reproduce positions to
  within half a point. Edit any line in place; the download stays identical.
- **Switch modes anytime:** "Keep my original layout" (exact reproduction) or
  "Rebuild in ATS template" (clean structured builder). Your original is never
  lost when you switch.
- **Auto-edit removed.** The co-pilot no longer changes your resume behind your
  back. It gives clear, specific advice and example wording you copy in yourself.
- **Job-match suggestions are clearer** — short keyword gaps (🔴 missing / 🟡
  weak / 🟢 strong) plus concrete next steps with example lines to adapt.
- **Saved resumes open reliably.** Root cause fixed: resume data was being
  truncated on save (5 KB cap) into invalid JSON. Resume payloads now get room
  to store the full content, photo and layout.

## 1.25.0 — Resume co-pilot fixed + auto-edit experience

- **AI co-pilot works again.** Fixed a fatal JS error (duplicate `RZ_CHAT`)
  that silently killed the whole resume page after the co-pilot loaded.
- **Backend `/api/resume/chat`** returns `{reply, actions}`. Actions can
  rewrite the summary, change the title, add a skill, replace one bullet, or
  **replace an entire experience block's bullets** (`setbullets`) — the
  "auto-edit" the co-pilot suggests, applied on click, then re-exported to PDF.
- **Create vs. saved resumes are separate.** A "Your resumes" card up top:
  Import (PDF/DOCX/TXT), Save this resume, New blank, and a list to load/delete.
- **DOCX import no longer crashes** on embedded images (reads only
  `word/document.xml`, skips the corrupt-CRC media parts).
- **Photo control moved** into Personal details; match-to-JD scoring sits above
  the co-pilot so it's clear which resume it's scoring.

## 1.7.0 — Ask Vidya board: no flicker, slides, save, PDF

- **The board no longer redraws on every line.** The whole answer appears at
  once and stays put; the voice moves through it with a highlight on the line
  being read. Much calmer to watch.
- **Long answers become slides.** Anything over five lines is paginated, with
  ‹ › controls, and the slides turn by themselves as Vidya reads.
- **Save for reference.** Keep any answer to your account; a "Saved answers"
  list appears under the board, and you can re-open or remove them anytime.
- **Download as PDF.** Any answer — live or saved — exports to a clean PDF.
- Re-open a saved answer and press "Read aloud" to hear it again.

## 1.6.2 — Show the real Ask error (diagnostic)

- Temporarily surface the exact upstream reason (bad key, disabled API,
  quota, wrong model) to any logged-in user on the board, so the AI teacher
  can be debugged without hunting for the admin login. To be locked back to
  admins-only once it is confirmed working.

## 1.6.1 — Ask Vidya reliability

- **Default Gemini model is now `gemini-2.0-flash`** — the 2.5 models spend
  their token budget "thinking" and can return empty, which showed as
  "Vidya could not reach the board". 2.0-flash answers reliably. (If you set
  `GEMINI_MODEL` to a 2.5 model, thinking is now switched off automatically.)
- **Real errors are surfaced to admins.** A failed call now shows the actual
  upstream reason (bad key, wrong model, quota) on the board for admin
  accounts, and is always printed to the logs — instead of a generic message.
- Output token budget raised so long answers are not cut off.

## 1.6.0 — Projects become a real workspace

- **Projects is now hands-on, not a reading list.** Each of the four
  portfolio projects has a live progress bar, checkable steps, and — next to
  every step — a box to record what you did and why. This is the "record
  every decision" habit interviewers actually look for.
- **Deliverable fields per project:** paste your dataset/corpus, GitHub repo
  and live URL. They save to your account as you type.
- **"Mark project complete"** only unlocks once every step is ticked and a
  live URL is filled in — so completion means the work is genuinely done.
- Overall progress ("2/4 projects done") shown at the top. Everything
  persists, so students can leave and pick up exactly where they stopped.

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
