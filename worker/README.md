# The auto-apply worker

A second Railway service off this repository. It polls `apply_queue`, opens
the employer's ATS form in a headless Chromium, fills it deterministically,
attaches the resume, holds for a cancellation window, and submits.

    worker/
      run.py          the loop, the browser, the per-host lock
      flow.py         the state machine — no playwright import, on purpose
      resume.py       builds the PDF that gets attached
      filler.js       a byte-identical copy of extension/filler.js
      probe.js        reads what is still unanswered; writes one field
      adapters/       one per ATS; greenhouse is the only one so far

Rows reach the queue two ways: from the matched board
(`POST /api/apply/queue`) and from a link a person pasted into the
Apply-for-me panel (`POST /api/apply/link`). The worker does not know or
care which; a row is a row.

`docs/ADDING-AN-APPLY-ADAPTER.md` has the rules, the rails and the five
adapters still to write. The two things worth knowing before reading any
code:

**No model is called anywhere in this path.** Field matching is the
extension's deterministic label matcher; answer lookup is a dictionary
lookup on a normalised string. A question neither can settle parks the row
and asks a person. Nothing guesses, because the output is submitted to an
employer over somebody's real name.

**flow.py imports nothing from playwright.** It takes a `page` and an
`adapter` and does not care what they are, which is what lets every
decision — the caps, the hold window, the retry ceiling, the kill switch,
the consent recheck — be tested with a stub and no browser at all. Keep it
that way. `tests/test_apply_worker.py` runs that half everywhere and the
real-Chromium half against `tests/fixtures/greenhouse_form.html` over
`file://`.

Run it locally against the fixture rather than against a board:

    python -m worker.run        # needs DATABASE_URL, JWT_SECRET

## Deploying it

A second Railway service from this repository. **Set the service's config
file to `worker/railway.json`.** Without that it inherits the root
`railway.json`, which sets `healthcheckPath: /api/health` — and this service
binds no port and answers nothing, so Railway waits for an endpoint that
will never exist and reports a crash that has nothing to do with the code.

It needs `DATABASE_URL` and `JWT_SECRET`, the same as the app.

Set `APPLY_KILL_SWITCH=1` on it for the first deploy. It boots, idles and
sends nothing until you clear it, which takes effect on the next poll.

Stop every worker everywhere, without a redeploy:

    APPLY_KILL_SWITCH=1
