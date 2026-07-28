# How matching works

Everything here is deterministic — no model call, no token cost. If you change
a number in this document, change it in `main.py` in the same commit, because
these numbers were each set from a measurement and the measurement is the only
reason they are what they are.

## The score

`_score_job()` returns 0–100 from five weighted factors:

| Factor | Weight | Where it comes from |
|---|---|---|
| Hard skills | 33% | Stated requirements count triple a passing mention |
| Role and seniority | 27% | Family match, title overlap, level, years demanded |
| Evidence of impact | 17% | Numbers in the resume's bullets |
| Domain | 15% | Approximated by role family |
| Readability | 8% | How cleanly the file parses |

Two things then override the arithmetic:

**The relevance veto.** Impact and readability are a quarter of the weight and
identical for every posting in one search — they describe the resume, not the
fit. On a job in the wrong field that floor alone floated scores into the
sixties, which is how a network engineer saw *Head of AI* at 65. If neither the
family nor the title lines up, the whole score comes down rather than the
mismatch being averaged away.

**The years gate.** Four years short of the stated requirement multiplies the
score by 0.78; two years short by 0.92. A year or two is normal and costs
nothing. This exists because "12 Years of exp Required" scored 80 against an
eight-year resume — seniority was read from title words alone and the one
number deciding the application was invisible.

### Bands

`match_tier()` — **72 exceptional / 60 strong / 45 worth applying**. These were
85 / 70 / 55 until v3.34.0. Measured across the live board with four resume
profiles (network, backend, SRE, data), the **highest score any of them reached
was 77**. A band nobody can reach does not set a high standard, it tells good
candidates they are mediocre. If you change scoring, re-measure and move these.

### What the candidate sees

Every card carries `why` — the same arithmetic in words, worst news first.
Other boards show a percentage and leave you to guess; the reasoning already
exists, so showing it costs nothing.

## Skill rarity (IDF)

Weights are measured on the result set itself: a skill three quarters of
postings mention says almost nothing about fit. **Floored at 0.05.** A skill on
more than about four fifths of postings takes `log(n/(1+c))+0.25` negative, and
a negative weight means matching a skill scores *lower* than not matching it.
The live board is nowhere near that; a board on its first day is, which is
exactly when a new deployment's first alerts would be nonsense.

## Resume families

`_resume_families()` weighs evidence rather than presence. One mention of a
hospital client used to make a network engineer's resume read as *healthcare*,
and six claimed families meant the family gate matched nearly every posting and
stopped gating at all. Keeps families with at least 2 hits and 15% of the top
family's count, maximum four.

`_families()` (presence, not weight) is still correct for **job ads**, which
are short and on-topic. Do not swap one for the other.

## Categorisation

A posting's category comes from its title via `_ROLE_FAMILIES`. Three rules
learned the hard way:

1. **Never read the description to categorise.** It filed *Administrative
   Business Partner* under Networking and *Android BSP Engineer* under Driving.
   The exception is `_family_from_text()`, which reads the parsed **skills**
   list — a skill is a fact about the job, a word in a paragraph is not.
2. **Order matters.** First match wins, so Cybersecurity and Data are listed
   before Cloud: *cloud security architect* is a security role that says cloud.
3. **Ordinary word endings must match.** `platform engineer` has to match
   "Platform Engineering Manager", or a role we crawl for is discarded.

Anything still unlabelled becomes `other` — never blank. Blank rows are
invisible to the category filter, which is how 5,852 postings sat on the board
reachable from nowhere while the headline counted them.

**After changing `_ROLE_FAMILIES`, run `/api/admin/jobs/recategorize?dry=0`.**
Stored rows keep the answer they were crawled with.

## Scope

`_job_in_scope()` decides what is allowed on the board at all.

- Country: matched loosely, because sources spell it inconsistently. When the
  field is **blank**, the location text decides — with a US signal winning
  first, so Vienna VA, Dublin OH and Paris TX stay while Hamburg and
  Luxembourg go.
- Family: unrecognised titles are kept only when the posting is technical on
  its own evidence (parsed skills, weak ones like Excel and SQL excluded). A
  technical job title lowers that bar to one real tool, which keeps *Principal
  Engineer — Privacy* without letting *Commercial Counsel* through.

## Field extraction

Salary, years, engagement, visa and job type are parsed **at ingest** and
stored. Never re-derive them at match time: the description column is deferred
on that query and touching it lazy-loads thousands of rows one at a time.

Two traps that cost real bugs:

- **The update path must write every parsed field.** Salary showed on 0% of
  the board for months because `_store_jobs` set fourteen fields and salary was
  not one of them, so any row predating the column stayed NULL forever.
- **Negations invert meaning.** "W2 only, no corp-to-corp" contains both terms
  and means the opposite of both.

Each rule is tested against **four phrasings**. Two bugs were found that way
that no single test case would have caught. Keep that habit.

## Alerts

After every crawl, `_job_alert_sweep()` scores the last 24 hours against each
paid user's saved resume, raises one bell per match and emails a shortlist
once a day.

- `JOB_ALERT_MIN` (90) flags an exceptional match; `JOB_ALERT_FLOOR` (70) is
  the bar for the best of what actually arrived. **A single bar does not
  work** — nothing on the board scores above ~77, so 80+ means silence.
- **Mark every posting you considered, not every one you sent.** A job stays
  "new" for 24 hours and the crawler runs eleven times a day; marking only the
  twelve that went out sent the rest an hour later.
- Scoring must use the same rarity table as the match page, or the percentage
  in the email disagrees with the card it links to.

## When you change any of this

1. Run all five suites in `tests/`.
2. Re-measure the score distribution against the live board — `match_tier`
   bands and both alert thresholds depend on it.
3. Check a match request still answers inside 5s (`test_sweep.py` asserts it).
