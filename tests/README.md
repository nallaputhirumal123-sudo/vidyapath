# Tests

Run these before every deploy. They talk to the app through its real HTTP
routes, so they catch the things unit tests miss — auth, permissions, payment
gating, and whether a page still renders.

```bash
.venv/Scripts/python.exe tests/test_sweep.py        # everything a user touches
.venv/Scripts/python.exe tests/test_security.py     # boundaries and tampering
.venv/Scripts/python.exe tests/test_regressions.py  # bugs that already bit us once
```

They run against `vidyapath.db` (SQLite) and create throwaway accounts. Never
point them at production: `DATABASE_URL` is set at the top of each file and
should stay pointing at the local database.

## What each one covers

**test_sweep.py** — signup, login, the two-device limit, password reset without
leaking whether an account exists, job search and paging, matching speed and
quality, the tracker, plan limits, interview prep, extension pairing, the
curriculum, and that the legal pages carry no leftover placeholders.

**test_security.py** — one user cannot read or clear another's data, forged and
unsigned webhooks are rejected so nobody can grant themselves a plan, expired
and reused reset tokens fail, hostile input never 500s, limits are enforced
rather than suggested, and source files and the database are not served.

**test_dalia.py** — who the tutor thinks she is teaching, and what she is
allowed to put on the screen. The grade band read out of a free-text level
("Class 8", "B.Tech 2nd year", "PhD"), the control tags parsed back out of a
reply, and — the bulk of it — everything that gets DROPPED: a sandbox language
nothing here runs, a network topology nobody built, markup smuggled in as a
topic. The four network labs are each run through the real packet engine and
their verdicts compared with the ones documented beside them, so a lab cannot
quietly start teaching the wrong answer. Ends with the talk endpoint end to
end against a stubbed model, including that a cached reply still opens the
same panels the first asker got.

**test_craxlearn.py** — the boundary between two institutions. Two schools and
a member of the public ask the same question; each pays for it, each gets its
own cache row, and neither can reach the others'. A head teacher sees their own
school's topics as counts and never another school's, and clearing your own
history does not clear the school's. Plus the source registry: every source
used for answers, explanations, 2D, 3D or sandbox material is asserted to be
open, and the one closed dependency is asserted to be listed and marked.

**test_craxlearn_only.py** — the three walls between a classroom and the job
board, asserted at the API rather than in the sidebar, because hiding a menu
item stops nobody who can type a URL. A school that bought Craxlearn is refused
at any age; a coaching centre that bought both is refused for anyone under 18,
which is not the centre's to waive; and `CRAXLEARN_ONLY` refuses everybody
including admins. Also greps the served `/craxlearn` page for job-side strings,
and walks the live route table so a route belonging to neither half fails the
build.

**test_classwork.py** — the loop from the board to the class and back. A
teacher sets what is on the board; it is on the students' home screen with
nothing published. A student hands it in; it is in the teacher's queue with
nothing configured. The teacher marks it; the student sees the verdict. Pins
the two that go wrong in classroom software: work edited after review is
waiting again (a teacher who read version one has not read version two), and
the cross-class review queue never shows another school's children.

**test_classcode.py** — signing in with nothing but a class code, study
material, and the account reset. Runs against its OWN database
(`vidyapath-classcode-test.db`) because its last section deletes every
non-admin account, and doing that to the shared one breaks the other suites
for reasons nobody would connect to it. Most of its length is proving the
reset does NOT fire: a destructive endpoint's tests are mostly about the
times it must do nothing.

**test_office.py** — separated duties. A teacher marking a child absent, a
head teacher writing off a fee, either of them posting a school notice: all
three look like reasonable bugs — everyone involved is staff, signed in, at
the right school — and all three are refused. Also that attendance is computed
from day rows rather than stored, by correcting a wrongly marked day and
watching the percentage move, and that one login means the previous device is
signed out with a reason.

**test_roll.py** — which learners a member of staff may look at. The rule is
the classroom, not the school, and every refusal here is a real teacher at the
right school asking about the wrong child. Includes the one that matters most:
looking up a student id that exists in another teacher's room answers "no
learner of yours has that id", because "exists but not yours" is still a fact
about somebody's child. Also the calculator, against a list of injection
attempts — it is the one input box in a room full of teenagers.

**test_regressions.py** — every bug that has already reached production once.
Matching scoring unrelated roles highly, degrees being read as seniority, dead
listings from a retired source, JSON parsing breaking on a model preamble,
newer AI models spending their whole budget on internal thinking, blocked SMTP
hanging the site, and the substring match that blocked "preferred" fields in
the autofill extension.

## Reading the output

A failing check prints the expectation and what happened. Some failures are
the **test** being out of date rather than the app being broken — for example,
changing the plan structure or the free-tier allowance will fail assertions
that hardcode the old numbers. Confirm which it is before changing code:
run the endpoint by hand and look at the response.

## What is not covered

Be aware of the gaps rather than trusting a green run:

- **Live payments.** Stripe is only exercised as far as rejecting
  forged webhooks. No real charge, refund or cancellation has ever run.
- **Google sign-in.** The OAuth round trip cannot be automated here. A bug that
  rejected every new Google account survived a full green sweep because the
  tests only used email signup.
- **Email delivery.** Sending is stubbed out. That a message was composed does
  not prove it arrives.
- **Real browsers.** Layout and theming were checked in Chromium only; Safari
  and real iOS are untested.
