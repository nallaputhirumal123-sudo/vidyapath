# Adding a job source

Everything a new source needs, and the mistakes already made doing this.

There are two kinds of source and they are added differently:

- **A new company on an ATS we already read** (Greenhouse, Lever, Ashby,
  Workable, Recruitee, Workday, SmartRecruiters) — no code, add a token.
- **A new provider** (a job API we do not read yet) — one function.

---

## 1. A new company on an existing ATS

Add its slug to the relevant list in `main.py`: `_GREENHOUSE`, `_LEVER`,
`_ASHBY`, `_WORKABLE`, `_RECRUITEE`, `_WORKDAY`, `_SMARTRECRUITERS`. Each is a
comma-separated string. Every one is also overridable by env var
(`JOB_GREENHOUSE`, `JOB_LEVER`, …) so you can test without deploying.

The slug is whatever appears in the company's own careers URL:

```
boards.greenhouse.io/stripe        -> stripe
jobs.lever.co/palantir             -> palantir
jobs.ashbyhq.com/openai            -> openai
```

Workday is different — it needs `tenant|site|datacentre`, read off the URL
`https://<tenant>.<dc>.myworkdayjobs.com/<site>`:

```
https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite
   -> nvidia|NVIDIAExternalCareerSite|wd5
```

### Verify the slug before adding it

**This is not optional.** ~90 slugs were once added by guessing; 153 turned out
to be 404s and a third of every crawl was wasted on them until a production
report exposed it. A wrong slug fails silently — it just returns nothing.

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  https://boards-api.greenhouse.io/v1/boards/SLUG/jobs
```

`200` means real. Anything else means do not add it.

After deploying, open **admin → Revenue & profit → Refresh jobs now**, wait,
then **Check crawl status**. The per-source report lists every board and what
it returned. Anything showing `HTTPStatusError` or a persistent `0` should come
back out.

---

## 2. A new provider

Write one async function. It takes an `httpx` client and returns a list of
rows from `_job_row()`.

```python
async def _fetch_example(client, _=None):
    """One page of Example's public job feed."""
    r = await client.get("https://api.example.com/jobs",
                         params={"key": EXAMPLE_KEY, "limit": 200})
    r.raise_for_status()
    return [_job_row("example",           # source name, must be unique
                     j.get("id"),         # stable id from THEIR side
                     j.get("title"),
                     j.get("company"),
                     j.get("location"),
                     j.get("url"),
                     j.get("description", ""),
                     _ts(j.get("posted_at")))
            for j in (r.json().get("results") or [])]
```

Then register it:

```python
_FETCHERS = {..., "example": _fetch_example}
```

If it needs a key, read it near the other credentials and skip cleanly when it
is absent — a missing key must never break the crawl:

```python
EXAMPLE_KEY = env("EXAMPLE_KEY")
...
if EXAMPLE_KEY:
    ...
else:
    report["example"] = "skipped (no EXAMPLE_KEY)"
```

That exact wording matters: it is what tells you from the crawl report that a
variable never reached the app, which has already been the difference between
"the integration is broken" and "the env var has a typo".

### Rules the fetcher must follow

**Return `_job_row(...)`, never a raw dict.** It normalises, truncates, builds
the lowercase search blob, extracts skills and assigns the role family. A row
built by hand will be missing `category` and become invisible to the category
filter.

**`external_id` must be stable across crawls.** It is half of the
`(source, external_id)` unique key. If it changes between runs, every crawl
inserts duplicates instead of updating.

**Let exceptions escape.** `_collect_jobs` catches per board and records the
error type in the report. A fetcher that swallows its own errors reports
success and returns nothing, which is worse than failing.

**Do not paginate unboundedly.** Cap it with an env var, as
`ADZUNA_PAGES` and `ARBEITNOW_PAGES` do. One source looping forever holds up
the whole crawl.

**Never scrape LinkedIn, Indeed or Naukri.** No public API, against their
terms, and it gets the crawler blocked. Paid aggregators exist precisely
because that route is closed.

---

## 3. What happens to the rows

Everything below is automatic. Understanding it explains most "why is my
source returning nothing" questions:

1. `_job_in_scope()` drops anything outside `JOB_COUNTRIES` (default `US,CA`)
   or outside `JOB_FAMILIES`. **A blank country is kept**; a title matching no
   role family is dropped.
2. Duplicates within the batch are skipped — a board returning the same posting
   twice used to fail the entire transaction.
3. Existing rows are updated, new ones inserted, and postings that vanished
   from a board that *did* respond are marked closed.
4. Anything not seen for `JOB_RETENTION_DAYS` is deleted — **except** jobs a
   user saved or applied to, which are exempt.

So a source can return thousands of rows and add nothing to the board, simply
because they were all out of scope. The crawl log prints the skipped count.

---

## 4. Sources worth adding

Already written, needs only a key: **Jooble** (`JOOBLE_KEY`).

Free, needs a fetcher: **USAJOBS** (US federal, heavy on cyber and IT),
**Careerjet**, **Reed** (UK).

Paid: **JSearch** on RapidAPI — the broadest non-tech coverage, aggregates
Google for Jobs.

Adzuna and Jooble are the only sources that reach staffing and contract work.
Company ATS boards carry full-time internal hires almost exclusively — the
attempt to reach C2C roles through consulting firms' own boards returned zero
from every single one.

---

## 5. Checklist

- [ ] Slug or endpoint verified with `curl` — a real `200`
- [ ] Uses `_job_row()`; `external_id` stable across crawls
- [ ] Missing key skips with `skipped (no X)` rather than raising
- [ ] Pagination capped by an env var
- [ ] Registered in `_FETCHERS`
- [ ] Crawled locally: `python -c "import asyncio, main; asyncio.run(main._collect_jobs())"`
- [ ] All five suites in `tests/` pass
- [ ] After deploy, checked the per-source report for its line
