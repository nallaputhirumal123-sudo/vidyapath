# Adding an apply adapter

The first one was the expensive one. The rest are six methods and a handful
of selectors, and this is what they are.

Read `docs/ADDING-A-JOB-SOURCE.md` first — the rule about what may never be
automated is the same rule, and it matters more here. Crawling the wrong
site gets the crawler blocked. Applying on the wrong site gets the
**candidate** blocked, from a company they wanted to work at.

---

## What may be automated, and what may never be

**Never: LinkedIn, Indeed, Naukri, Dice.** No public apply API, against
their terms, and automating them takes the candidate's account with it when
it is noticed. There is no version of this that is worth it.

**Never: aggregators.** Adzuna, Jooble and JSearch hand back a `redirect_url`
to somebody else's page. They are a discovery source. There is no form at
the other end of that link that is ours to fill.

**Not in this slice: Workday, Taleo, iCIMS.** Each requires creating a
per-tenant candidate account, and creating one means accepting that
employer's terms *as the candidate*. That is not a thing software should do
on somebody's behalf. Those rows are refused at enqueue with a message
saying to apply by hand.

**Yes: the six no-login ATSs.** greenhouse, lever, ashby, workable,
smartrecruiters, recruitee. A public page, a real form, no account. That is
the whole list, and it is `APPLY_SOURCES` in `main.py`.

**And never add fingerprint spoofing, proxy rotation, or any other
detection evasion.** It is not the lever that matters, and the ATSs that do
detect it blacklist the applicant rather than the bot.

---

## Two ways a row gets queued

From the board we crawl (`POST /api/apply/queue`), and from a link somebody
pasted (`POST /api/apply/link`). Same table, same worker, same rails. The
only difference is that a pasted link has to be classified before anything
opens it, and **that decision is made from the URL alone — nothing is
fetched to make it.** A route that followed an arbitrary pasted link to find
out what was on the end of it would be a request-forgery primitive sitting
inside the network the database is on, and it would follow redirects to get
there.

The host match is on the *registrable* domain (the last two labels), not a
substring: `boards.greenhouse.io` and `job-boards.greenhouse.io` both
resolve to `greenhouse.io`, and `greenhouse.io.evil.com` resolves to
`evil.com` and is refused. Adding an ATS means adding its domain to
`APPLY_HOSTS` in `main.py` alongside the adapter.

A pasted link that matches a posting the crawler already has reuses that
`Job` row. That is not cosmetic: the per-company hour counts by employer
name, so a link recorded as "Pastedco" and a crawled row recorded as
"Pasted Co Ltd" would be two employers as far as the cap is concerned.

---

## The six methods

Copy `worker/adapters/greenhouse.py` and change the selectors.

```python
class LeverAdapter(Adapter):
    source = "lever"

    async def open(self, page, url):     # get to the form; raise if it has closed
    async def fill(self, page, profile): # runs filler.js, returns FillResult
    async def answers(self, page, bank): # fills from the bank, returns what it cannot
    async def attach(self, page, path):  # set_input_files on the file input
    async def submit(self, page):        # click, return the employer's confirmation text
```

Then two edits, and the test that stops you forgetting the second:

1. `ADAPTERS` in `worker/adapters/__init__.py`
2. `APPLY_DRIVABLE` in `main.py`

`test_apply_worker` asserts those two agree. `APPLY_SOURCES` is what we are
*allowed* to drive; `APPLY_DRIVABLE` is what we actually *can* today, and
queueing a row for a source with no adapter behind it buys somebody a queue
entry the worker can only fail.

### Selectors go in ordered lists, not single strings

Every ATS serves more than one generation of markup at once — a classic
board, a React embed, an iframe on the company's own careers page. Take the
first selector that resolves:

```python
FORMS = ["#application_form", "form#application-form",
         "form[action*='applications']", "main form", "form"]
```

That covers three generations without branching on a version you cannot
reliably detect.

### `submit` must return the employer's own words

The returned text is the only evidence the application landed. Do not
return a constant, and do not return `""` and let the row be marked
confirmed anyway — `submitted` with invented evidence is the one lie this
feature must never tell.

When the click happened and the response could not be read, raise
`Unconfirmed`. It is a separate exception because the flow must treat it as
the opposite of a failure: a failure is retried, and retrying this applies
to the same job twice under somebody's real name.

### Let errors escape

`flow.run_row` is the only place that catches. An adapter that swallows its
own exception reports success having done nothing — the same failure the job
crawler doc warns about, and worse here, because the row says an application
was sent when none was.

---

## Never test against a live board

`tests/fixtures/greenhouse_form.html` is a form built from a real ATS's
structure and driven over `file://`. Build the equivalent for your ATS and
do the same. A test that posts an application to a real employer is a bug —
not a thorough test — and there is no "just once to check the selectors"
version of it.

The fixture should refuse to confirm when a required field is empty or no
file is attached, exactly as a real board would. Otherwise the test proves
the adapter clicked a button, not that it completed a form.

---

## The rails, and why each one exists

Set in the environment, read live on every pass — none needs a redeploy.

| Variable | Default | What it is for |
|---|---|---|
| `APPLY_KILL_SWITCH` | unset | Set it and every worker halts immediately. Read per call, not at import. |
| `APPLY_HOLD_MINUTES` | 15 | How long a filled form waits where its owner can still stop it. `0` sends at once. |
| `APPLY_MAX_PER_USER_DAY` | 20 | Per candidate. Counts what is queued, not only what was sent. |
| `APPLY_MAX_PER_COMPANY_HOUR` | 2 | Per employer, **across all candidates**. This is the one that matters. |
| `APPLY_POLL_SECONDS` | 20 | Between passes. |
| `APPLY_GAP_MIN` / `APPLY_GAP_MAX` | 6 / 18 | Randomised gap between applications. A fixed sleep makes twenty applications land at exactly even intervals. |
| `APPLY_SHOTS_DIR` | `/tmp/vp-apply-shots` | Where the review screenshots and generated resumes go. |

Twelve applications into one employer in an hour is what gets a whole domain
blocked, for everybody. No individual candidate's limit can prevent that,
which is why `APPLY_MAX_PER_COMPANY_HOUR` counts across all of them and is
read immediately before the click rather than when the row was queued.

A cap that is hit **defers** the row; it never fails it. Failing an
application because the queue was busy would be the tool losing somebody an
opportunity in order to protect a rate limit.

---

## No model, anywhere in this path

Field matching is `extension/filler.js` — deterministic label matching with
exclusion rules. Answer lookup is a dictionary lookup on a normalised
string. A question neither can settle parks the row and asks a person, once,
and the answer goes into `answer_bank` so nothing asks again.

There is no fallback that guesses. The output is submitted to an employer
over somebody's real name, and a plausible invention is worse than a blank.

`worker/filler.js` is a byte-identical copy of `extension/filler.js` and a
test asserts it. Do not fork it. If the matcher needs a change, change the
extension's copy and re-copy — otherwise the two fill the same form
differently and only one of them is the one anybody has tested.

---

## Deploying it

A second Railway service from this repository, pointed at
`worker/Dockerfile`. It serves nothing, so give it no healthcheck path and
no port — it is a worker, not a web target.

It needs `DATABASE_URL` and `JWT_SECRET` like the app. Apply migrations
before deploying either, as always: the app refuses to boot on a revision
mismatch, and the worker reads tables the migration creates.
