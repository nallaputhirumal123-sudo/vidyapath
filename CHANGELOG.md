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

## 1.48.0 — craxle.com

- The extension now pairs with **craxle.com**. The old Railway URL is kept as
  a fallback in both `host_permissions` and the pairing call, so an extension
  paired before the move keeps working and pairing still succeeds part-way
  through a DNS change.
- Pairing tries the domain first, then the fallback — except on a 401, where
  the code itself is wrong and trying another host would not help.
- No server change was needed: the Google OAuth redirect already derives from
  `PUBLIC_BASE_URL` or the request host.

## 1.47.1 — My applications is only the tracker

- The **My applications** tab showed the whole careers page underneath it —
  roles to aim for, practice projects, job boards, company career pages, the
  extension card. All of that now stays in **Find jobs**, where it belongs.
  The tracker tab shows the tracker and nothing else.

## 1.47.0 — Autofill browser extension

- **New `extension/` folder: a Chrome/Edge extension that fills a job
  application form in one click.** Name, email, phone, LinkedIn, GitHub,
  portfolio, current role and company, school and degree.
- **It never submits.** No `form.submit()`, no button clicks, no Enter key.
  You check every field and press the employer's own submit button. Verified
  by a test that fails if the form is ever submitted.
- **No AI, no tokens.** Field matching is deterministic label matching. An LLM
  would cost money on every form and would not be better at working out that
  "First Name" means your first name.
- **No session cookie reaches the extension.** The site mints a single-use
  pairing code that expires in 10 minutes; the extension trades it once for a
  read-only profile and stores it in the browser. Nothing that can act as you
  ever leaves the site. Replay of a used code is rejected.
- **It only runs when you click** — `activeTab` injection, no background
  script, no content script registered against any site.
- **It refuses rather than guesses.** Tested against Greenhouse, Lever, Ashby
  and placeholder-only field layouts: 12 fields filled correctly, while
  "Referrer First Name", "Emergency Contact Phone", "Confirm Email" and "Why
  do you want to work here?" were all correctly left empty, and a pre-filled
  field was left untouched. Resume upload boxes are highlighted, not faked —
  browsers do not let an extension attach a file, and pretending otherwise
  would be worse than saying so.
- Careers page gains a **Connect extension** button that generates the code.

## 1.46.0 — Application tracker

- **Two tabs on the careers page: Find jobs and My applications.**
- **Save a job** with ♡ on any result. **Pressing Apply records it
  automatically** — the moment you open the employer's form is when the
  application really starts, so you are not asked to tick a box afterwards.
- **A pipeline you can move things through:** Saved → Applied → Interviewing →
  Offer received → Rejected → Archived, with a count on each stage and a
  dropdown on every row to move it along. Remove anything with ✕.
- **Your history outlives the listing.** The job title, company, location and
  link are copied onto your record when you save it, so pruning old postings
  after 7 days never erases what you applied to.
- **Removed the W2/C2C and work-authorisation filters.** They were built and
  correct, but the free sources carry almost nothing for them (W2 4, C2C 3),
  and a filter that returns nothing is worse than no filter. The parsing stays
  in place, so they can come back the moment a source that carries those
  postings is connected. Job type (full-time / contract / part-time /
  internship) stays — that one has real data behind it.

## 1.45.0 — Terms and Privacy Policy rewritten for paid subscriptions

- **Terms of Use** rewritten for a paid service: who operates VidyaPath,
  subscriptions and auto-renewal through Stripe, a 7-day no-questions refund
  window, price-change notice, cancellation, suspension, liability cap, and
  Indian governing law.
- **A section that says plainly what we do not promise about jobs** — listings
  come from third parties and may be stale, match scores and W2/C2C and visa
  labels are generated automatically and can be wrong, no guaranteed number of
  listings or new listings per day, and no guarantee of a job or an interview.
- **Privacy Policy** rewritten for payments and resumes: a table of exactly
  what we hold and why, an explicit statement that card details never reach our
  servers, and a clear warning that AI features send resume text to Google or
  Groq — so no Aadhaar, passport or bank details belong in a resume.
- Adds legal basis for EU/UK users, a sub-processor table, retention periods
  (including tax records), and how to exercise data rights.

Both documents carry `[PLACEHOLDER]` fields for legal name, address and city
that must be filled in, and both state that they are templates which need a
lawyer's review before taking money.

## 1.44.0 — Job type, W2/C2C and visa filters

- **Job type filter:** full-time, contract, part-time, internship — read from
  the posting text rather than assumed.
- **Engagement filter:** W2, C2C / corp-to-corp, 1099. A posting that says it
  takes either shows under both.
- **Work authorisation filter:** sponsors a visa (H1B / OPT / CPT), no
  sponsorship (citizens / green card only), or security clearance required.
  Knowing a job will *not* sponsor saves an application that was never going
  to land.
- Every one of these dropdowns only offers values we actually hold jobs for,
  with counts, so no option leads to an empty page.
- **Fixed:** the version badge overlapped the tutor button in the bottom-right
  corner. It now sits above it.

**Known limit, stated plainly:** the free sources carry almost no W2/C2C
postings (single digits) and few explicit visa statements. That vocabulary
lives on staffing boards like Dice, which have no free public API. The filters
are correct and will fill up the moment a source that carries those postings
is connected — see `ADZUNA_APP_ID` / `JOOBLE_KEY`.

## 1.43.0 — Apply kit, job categories, type-ahead, wider search

- **Apply kit.** On any open job, one click prepares the whole application: a
  resume summary rewritten for that posting, bullets to lead with, a cover
  note, likely screening questions with answers built from your real
  experience, and anything in the ad you may not meet. Everything is
  copy-ready and the posting opens for you to submit.
  **It never submits on your behalf** — that would put your details into an
  employer's system without you seeing them, breaks every ATS's terms, and
  gets real applicants blacklisted. The keyword lists and checklist work even
  when AI is switched off.
- **Job categories.** 30 of them, well past IT: healthcare, teaching,
  operations, admin, finance, legal, retail, hospitality, driving,
  construction, science, writing. Pick one from the dropdown to browse it.
- **Type-ahead search.** Suggestions appear as you type, drawn from job titles
  actually in the database with their result counts, so nothing you can pick
  leads to an empty page. Scrollable, click or press Enter.
- **Wider net.** Six more free sources added — The Muse, Arbeitnow, Remotive,
  RemoteOK, Jobicy and Himalayas — taking the board past **13,000 jobs**, with
  much better coverage outside tech and outside the US. No key needed.
  Adzuna and Jooble connectors are built in too and switch on by themselves if
  you set `ADZUNA_APP_ID` / `ADZUNA_APP_KEY` or `JOOBLE_KEY`.
- **Match is ~30× faster.** It had slowed to over 30 seconds a search: it was
  re-deriving each job's skills and role family at query time — about 240
  regexes per job across 5,000 jobs. Both are now computed once when the job
  is stored. A search takes ~1 second.
- **Fixed miscategorised jobs.** Keyword matching was on substrings, so
  `cisco` matched "San Fran**cisco**" and `writer` matched "Under**writer**" —
  filing account executives under Networking and credit analysts under
  Writing. Now matched on word boundaries, and a job's category comes from its
  title only; guessing from the description filed Administrative Business
  Partner under Networking.
- The source each job came from is no longer shown.
- **Removed the spelling & grammar check**, front end and endpoint. The job
  match is what actually changes an outcome; the proofreader was a second
  AI call for far less.

## 1.42.0 — Matching made honest, paging, bell moved

- **Fixed the matching. It was badly wrong.** A senior network engineer's
  resume scored **100% on "Legal & Compliance Tech IT Product Manager"**. Two
  causes, both now fixed:
  - The skill vocabulary contained generic words — `support`, `design`,
    `product`, `content`, `automation`, `security`. They appear in almost
    every job ad, so any resume matched almost any job. The vocabulary is now
    named tools, languages and platforms only.
  - Skills were all weighted equally, so matching `git` counted as much as
    matching `bgp`. Skills are now weighted by how rare they are across the
    live postings, measured per search.
- **Jobs now have to be the same kind of work.** A new role-family check
  (network, security, data, ML, backend, devops, QA, product, sales, finance,
  legal…) compares the posting against your resume. Same family scores higher,
  an adjacent one is damped, an unrelated career is heavily damped. Result for
  that same network engineer: the top matches are now Network Operations
  Engineer, Network Engineer II and Manager Networking — and **zero** product,
  legal or sales roles in the top 50.
- **Scores mean something again.** They spread across the range instead of
  everything sitting at 100. A new filter shows only *50%+*, *70%+* or *85%+*
  matches — on the test resume, 4,086 results narrowed to 6 genuine ones.
- **Paging.** Both the matched list and search now page through every result
  with Previous / Next, 20 per page, showing which page you're on.
- **Messages moved out of the sidebar** to a bell beside the dark-mode toggle,
  top-right, with the unread count on it.

## 1.41.0 — Sidebar reorganised and aligned

- **Grouped by how often you use it.** Everyday items stay at the top (Home,
  Messages, Choose a path, Projects, Ask Vidya), followed by a new **Get
  hired** group (Careers & jobs, Resume builder), then your tracks and
  progress. The occasional ones — My class, Coloring fun, Game Studio, All
  resources — now sit under **More** at the bottom, with Teacher dashboard and
  Admin panel under **Manage**.
- **Labels line up.** The icon column was 18px, but emoji advance widths vary
  a lot (🛠️ and 🧑‍🏫 are much wider than 🏠), so labels sat at ragged
  positions. The column is now a fixed 22px flex box — all 28 items start at
  exactly the same x, compound emoji included.

## 1.40.1 — Correct the default Gemini model

- The default `GEMINI_MODEL` was `gemini-3.5-flash-lite`, which is not a real
  model ID. Nothing appeared broken, because a bad ID doesn't fail loudly —
  the provider fallback silently served every request from Groq instead. Now
  `gemini-2.5-flash-lite`, confirmed via `/api/ai/selftest`.
- Check any future model ID at `/api/ai/selftest` (admin only) before shipping
  it: that endpoint returns the raw provider response.

## 1.40.0 — Upload on the jobs page, and one home for resume checks

- **Upload your resume where the jobs are.** The Careers page now takes a PDF,
  DOCX or TXT directly and matches it against every live posting straight
  away — you no longer have to build a resume first.
- **The uploaded resume survives a refresh.** Its text is stored against your
  account instead of only in the browser tab, so matching still works when you
  come back. "Remove" clears it.
- **Resume builder is now just for building.** The job-description match and
  the spelling/grammar check moved to Careers & jobs, next to the jobs they
  are for. The builder keeps the editor, styles, live preview, PDF download
  and saved resumes.
- **Fixed: experienced people were being labelled junior.** Seniority was read
  from the whole resume, so a listed `B.Tech` or "graduate" outvoted a
  "Senior Engineer" job title — which then docked 22 points from exactly the
  senior roles that fit best. It now reads job titles only. A senior data
  engineer's top matches went from ~69 (mixed roles) to 75–80 (senior data
  engineering roles).

## 1.39.0 — Live job board, resume matching, co-pilot removed

- **Live jobs (new):** the Careers page now lists real, current openings —
  around 10,000 of them — instead of only linking out to job sites. They are
  read straight from the public APIs behind companies' own career pages
  (Greenhouse, Lever, Ashby, Workable, Recruitee), so every posting is genuine
  and links to the real application. We do not scrape LinkedIn/Indeed/Naukri:
  that breaks their terms and gets blocked.
- **Refreshed daily, one week of history:** a background task re-crawls every
  board once a day. A posting that comes off a career site is marked **closed**
  with the time it went, rather than vanishing, and rows older than 7 days are
  pruned. Jobs are only closed on boards that actually answered, so one API
  timeout can never wipe an employer's whole listing.
- **Match to your resume — free:** scoring runs in plain Python over the stored
  postings. It costs no AI credits and never touches the daily limit. Each job
  shows a 0–100 match score, the skills you matched, and the gaps. Seniority is
  inferred so juniors aren't shown staff roles.
- **Search anywhere:** filter by country (only countries we actually hold jobs
  for are offered), by city/state, by keyword, or remote-only. Title matches
  rank above description mentions.
- **Removed the resume co-pilot.** The open-ended chat was the most expensive
  thing per answer and the least targeted. The focused checks — job match,
  bullet rewrites, skills, grammar — all remain.
- Admins can force a crawl at `POST /api/admin/jobs/refresh`; the response
  reports every board, so a renamed or dead one is obvious.
- Set `JOBS_ENABLED=0` to switch the crawler off. Extend the company list
  without touching code via `JOB_GREENHOUSE`, `JOB_LEVER`, `JOB_ASHBY`,
  `JOB_WORKABLE`, `JOB_RECRUITEE`.

## 1.38.0 — Flash-Lite model, daily cap, and result caching

- **Cheaper model:** default Gemini model is now `gemini-3.5-flash-lite`
  (3–5× cheaper than Flash, plenty for scoring/grammar). Override with the
  `GEMINI_MODEL` env var if you ever want a different one.
- **Result caching:** a resume match (same resume + same job description) and a
  grammar check (same resume) are now stored — re-running them is instant and
  free, and does NOT count against the daily limit.
- **Daily limit:** 50 AI checks per user per day (match + grammar + rewrites).
  Cache hits don't count; admins are exempt. Hitting it shows a clear message
  and resets the next day. Set the number via `AI_DAILY_LIMIT` in code.

## 1.37.0 — Lighter resume AI calls

- Cut the token footprint of the resume checks (match, grammar, co-pilot) by
  roughly half — smaller resume/JD inputs and tighter output limits — so they
  use far less free quota per click.

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
