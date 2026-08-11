"""Every route a person is meant to use has something that calls it.

Four times in one session I shipped a tested endpoint with nothing pointing at
it: the packet walkthrough, the PDF upload, the notice composer and fee book,
and study material. The shape was identical every time — the server was built
and tested, the UI was treated as follow-up, and the follow-up was forgotten.
Tests all passed, because the tests called the route directly.

The worst of them was /api/my/notices. The whole targeted-update system —
audiences, attachments, teacher scoping, thirty passing checks — delivered into
an inbox that did not exist. Nobody could read what they had been sent.

So this fails the build instead of waiting for somebody to notice. It is a
crude check: does the path appear anywhere in a file the browser loads. A route
can still be called from dead code and pass. But every one of the four would
have been caught the day it was written, which is the whole ask.

ALLOWED holds the routes that are legitimately callerless — probes, webhooks,
redirect targets, links out of emails, and operator tools run with curl. Adding
to it should feel like a decision, so each one says why.
"""
import io
import os
import re
import sys
import glob

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


# Callerless on purpose. Each line is a reason, not a suppression.
ALLOWED = {
    "/api/health": "load balancer probe",
    "/api/status": "operator diagnostics, read with curl",
    "/api/ai/selftest": "operator diagnostics",
    "/api/ai/models": "operator diagnostics",
    "/api/mail/selftest": "operator diagnostics",
    # Why the last Google sign-in failed, in Google's own words. Typed into
    # the address bar while signed in as an admin, like the two above — the
    # user-facing message covers four unrelated causes and names none.
    "/api/auth/google/selftest": "operator diagnostics",
    "/api/admin/last-error": "operator diagnostics — the last 500",
    "/api/mail/whoami": "operator diagnostics",
    "/api/billing/webhook/stripe": "Stripe calls this, not us",
    "/api/auth/google/callback": "Google redirects here",
    "/api/auth/verify": "opened from a link in an email",
    "/api/auth/verify/resend": "opened from a link in an email",
    "/api/admin/jobs/out-of-scope": "operator dry run before pruning",
    "/api/admin/jobs/prune": "operator tool, deliberately not a button",
    "/api/admin/jobs/schedule": "operator tool",
    "/api/admin/corpus/build": "operator tool: a two-and-a-half hour NCERT "
                               "ingestion, started with curl on the server "
                               "that has the volume, not from a button",
    "/api/admin/corpus": "operator tool: watching that build",
    "/api/admin/alerts/run": "operator tool",
    "/api/admin/reports": "operator tool",
    "/api/hire/search": "employer surface, not built yet",
    "/api/apply/licence": "employer surface, not built yet",
    "/api/apply/profile": "employer surface, not built yet",
    "/api/class/leave/{cid}": "no way to leave a class in the UI yet",
    "/api/craxlearn/dob": "age gate is collected at signup instead",
    "/api/invites/unread": "redundant: the Employer invites tab already "
                           "shows a pending count and the bell carries "
                           "invite notifications. A third counter nobody "
                           "reads is worse than none",
    "/api/jobs/categories": "filters endpoint carries these instead",
    "/api/jobs/detail/{job_id}": "the list carries the detail already",
    "/api/lab/photo": "not wired into the lab yet",
    "/api/resume/parse": "the upload path parses inline instead",
    "/api/skills/unlocked": "not surfaced anywhere yet",
    "/api/craxlearn/me": "the board stopped asking who is signed in. It used "
                         "to read the craxle.com session, so whatever account "
                         "was signed in on a classroom machine became the "
                         "board — with their classes on a screen the whole "
                         "room can see. The route still answers 'what am I' "
                         "for anything that needs it; the board is not one of "
                         "them any more, and that is the point",
}

main = io.open("main.py", encoding="utf-8").read()
routes = re.findall(r'@app\.(get|post|delete|patch|put)\("([^"]+)"', main)
files = sorted(glob.glob("*.html") + glob.glob("*.js"))
clients = ""
for f in files:
    clients += io.open(f, encoding="utf-8", errors="replace").read()

api_routes = [(v, p) for v, p in routes if p.startswith("/api/")]
print(f"\n{len(api_routes)} API routes, {len(files)} client files")

unreachable = []
for verb, path in api_routes:
    if path in ALLOWED:
        continue
    stem = re.split(r"\{", path)[0].rstrip("/")
    if len(stem) < 8:
        continue
    if stem not in clients:
        unreachable.append(f"{verb.upper()} {path}")

print("\nroutes a person is meant to reach")
check("every one has a caller in something the browser loads",
      not unreachable,
      "; ".join(sorted(unreachable)) if unreachable else "")

print("\nthe inbox that was missing")
check("/api/my/notices is called from the page",
      "/api/my/notices" in clients,
      "the whole targeting system delivered nowhere a person could read")
check("and the Updates screen is not staff-only",
      'nav("notices"' in clients
      and "if(USER.is_teacher) h+=nav(\"notices\"" not in clients,
      "everybody who can be sent an update needs somewhere to read one")

print("\nthe allowlist stays honest")
stale = [p for p in ALLOWED if not any(p == r[1] for r in api_routes)]
check("nothing in it has been deleted from main.py", not stale,
      "; ".join(stale) if stale else "an entry for a route that no longer "
      "exists is a reason nobody will ever re-read")

print(f"\nPASSED {PASS}   FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
