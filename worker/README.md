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

A second Railway service from this repository. Everything below can be done
from the CLI; none of it needs the dashboard.

    railway add --service apply-worker --repo <owner>/<repo> --branch main
    railway link -p <project> -s apply-worker
    railway variables --set "RAILWAY_DOCKERFILE_PATH=worker/Dockerfile"
    railway up --service apply-worker --detach

**`RAILWAY_DOCKERFILE_PATH` is not optional.** Without it the service builds
the ROOT Dockerfile — the web app — and you get a second copy of the site
running as a worker, which looks like it deployed fine.

**It answers `/api/health` itself**, which is why `worker/railway.json` is
now belt to that braces rather than a requirement. A service built from this
repo inherits the root `railway.json` and its `healthcheckPath`, and the
first worker deploy was killed for not answering an endpoint it was never
designed to have. It answers now, and reports something worth reading:

    {"ok": true, "halted": false, "prepared": 3, "holding": 1,
     "ever_sent": 128, "live_sessions": 0, "adapters": [...]}

That is the difference between "is the container up" and "is the queue
moving" — and the second is the question you actually have.

**Variables it needs**, beyond `DATABASE_URL` and `JWT_SECRET`:

  APPLY_CRED_KEY    Fernet key for stored employer sign-ins. MUST be the
                    same value as the web service: the app encrypts with it
                    and the worker decrypts with it. Generate with
                    `python -c "from cryptography.fernet import Fernet;
                    print(Fernet.generate_key().decode())"`. With no key the
                    app refuses to store a credential rather than storing it
                    in the clear, so the worker simply never sees one.
  AI_PROVIDER       gemini, matching the web service, for the answer
                    fallback. Without it the worker still applies; it just
                    parks more rows for a person.

**Never pass a secret on a `railway add -v` command line.** That CLI echoes
its prompts, so the value lands in whatever is capturing the terminal. Use
`railway variables --set` with the output redirected, or the dashboard.

Set `APPLY_KILL_SWITCH=1` on it for the first deploy. It boots, idles and
sends nothing until you clear it, which takes effect on the next poll.

Stop every worker everywhere, without a redeploy:

    APPLY_KILL_SWITCH=1
