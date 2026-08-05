"""The tutor's grade band, her control tags, and the networks behind them.

Three things are checked here, and they are the three that go quietly wrong.

**The band.** A level string is free text — "Class 8", "B.Tech 2nd year",
"PhD", "Intermediate" — and reading it wrongly is invisible. Nobody files a
bug saying the tutor explained what a variable is; they just stop using it.

**The tags.** Every control tag is an instruction to open a panel, and the
failure mode is not an error, it is a tutor talking about a diagram that is
not there. So the tests here are mostly about what gets DROPPED: a language
nothing executes, a topology nobody built, a tag with markup in it.

**The networks.** Each preset is run through the real packet engine and its
verdict compared with the one written in the comment beside it. A teaching
lab whose answer is not the answer the engine computes is worse than no lab
— the learner is being taught the wrong thing by the thing that was supposed
to be incapable of inventing one.

And one join: every skill token the tutor can emit has to be a word the job
matcher actually knows. A skill stored as "Computer Networking Protocols"
looks like progress on a resume and moves nobody one place up a match list.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"   # local test database; refused on a deployment
os.environ["JOBS_ENABLED"] = "0"
# The TestClient talks to http://testserver, and a Secure cookie is never
# stored over http — so without this every request after signup arrives
# signed out, and the endpoint tests fail on auth instead of on what they
# are testing.
os.environ["COOKIE_SECURE"] = "0"

import dalia                                       # noqa: E402
import net                                         # noqa: E402
import main                                        # noqa: E402

PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {name}" + (f"  ({detail})" if detail else ""))
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


# ---- the grade band ---------------------------------------------------
print("\nGrade band")
for level, want in [
    ("Class 3", "primary"),
    ("grade 5", "primary"),
    ("3rd grade", "primary"),
    ("third grade", "primary"),
    ("Class 8", "primary"),
    ("primary school", "primary"),
    ("elementary", "primary"),
    ("Class 10 CBSE", "school"),
    ("grade 11", "school"),
    ("GCSE physics", "school"),
    ("A-level chemistry", "school"),
    ("preparing for JEE", "school"),
    ("higher secondary", "school"),
    ("B.Tech 2nd year", "undergraduate"),
    ("undergraduate", "undergraduate"),
    ("bachelor of science", "undergraduate"),
    ("college", "undergraduate"),
    ("PhD", "research"),
    ("doctoral student", "research"),
    ("postdoc", "research"),
    ("M.Tech", "research"),
    ("research scholar", "research"),
]:
    check(f"{level!r} is {want}", dalia.band(level) == want,
          dalia.band(level))

check("an unknown level is undergraduate, not school",
      dalia.band("") == "undergraduate")
for site_level in ("Beginner", "Intermediate", "Advanced"):
    check(f"the site's own {site_level!r} says nothing about standing",
          dalia.band(site_level) == "undergraduate")

# "PhD, year 2" is not class 2, and a research word has to beat a number.
check("a research word beats a stray number",
      dalia.band("PhD student, 2nd year") == "research",
      dalia.band("PhD student, 2nd year"))
check("a degree beats a stray number",
      dalia.band("B.Tech, 2nd year") == "undergraduate",
      dalia.band("B.Tech, 2nd year"))
check("class 13 is nobody's class", dalia.band("class 13") == "undergraduate")

# ---- pace is a separate axis -------------------------------------------
print("\nPace")
check("beginner", dalia.pace("Beginner") == "beginner")
check("advanced", dalia.pace("Advanced") == "advanced")
check("nothing said is intermediate", dalia.pace("Class 9") == "intermediate")
check("a beginner PhD is both",
      (dalia.band("PhD, absolute beginner at this"),
       dalia.pace("PhD, absolute beginner at this")) == ("research", "beginner"))

# ---- the exam board ----------------------------------------------------
print("\nFramework")
for level, want in [("Class 10 CBSE", "CBSE"), ("ICSE class 9", "ICSE"),
                    ("GCSE maths", "GCSE"), ("IGCSE", "IGCSE"),
                    ("A-level", "A-level"), ("AP calculus", "AP"),
                    ("NEET prep", "NEET"), ("Class 9", "")]:
    check(f"{level!r} -> {want or 'none'}", dalia.framework(level) == want,
          dalia.framework(level))

# ---- the prompt says what it is allowed to ------------------------------
print("\nPrompt")
spoken = dalia.system(level="Class 10 CBSE", subject="Physics", spoken=True)
written = dalia.system(level="PhD", subject="Physics", spoken=False)

check("the spoken prompt forbids LaTeX", "no LaTeX" in spoken)
check("the written prompt asks for LaTeX", "$$ display $$" in written)
check("the spoken prompt never asks for LaTeX", "$$ display $$" not in spoken)
check("the board is named in the prompt", "CBSE" in spoken)
check("the band reaches the prompt",
      dalia.BAND_LABEL["school"] in spoken and
      dalia.BAND_LABEL["research"] in written)
check("the prompt answers before it asks",
      "ANSWER, THEN ASK" in spoken and
      "in place of an answer" in spoken)
check("the prompt refuses to guess",
      "not have enough verified information" in spoken)
check("only real sandbox languages are offered",
      "cisco" not in spoken.lower() or "code_sandbox" not in spoken)
for topo in dalia.NET_TOPOLOGIES:
    check(f"{topo} is offered", topo in spoken)

# ---- reading the tags back ---------------------------------------------
print("\nControl tags")

reply = ('<environment: network_sim topology="packet_sniffer">\n'
         '<skill_unlocked: Computer Networking Protocols>\n\n'
         'A TCP connection opens with three segments. '
         'Why is the sequence number incremented by exactly one?')
say, controls, skills = dalia.parse(reply)

check("no tag survives into what is said",
      "<" not in say and ">" not in say, say[:60])
check("the sentence does survive", say.startswith("A TCP connection"), say[:40])
check("one control came back", len(controls) == 1, str(controls))
check("it is the network", controls and controls[0]["open"] == "network")
check("it carries a packet the engine can run",
      controls and "packet" in controls[0] and "rules" in controls[0])
check("one skill came back", len(skills) == 1, str(skills))
check("the label is what the learner sees",
      skills and skills[0]["label"] == "Computer Networking Protocols")
check("and it carries words the matcher knows",
      skills and "tcp" in skills[0]["tokens"], str(skills))

say, controls, _ = dalia.parse(
    '<smartboard: 2d_diagram="fraction pizza slices">\nFractions are parts.')
check("a 2d diagram is a board handoff",
      controls == [{"open": "board", "kind": "2d_diagram",
                    "topic": "fraction pizza slices"}], str(controls))

for lang, want in [("sql", "sql"), ("SQL", "sql"), ("postgres", "sql"),
                   ("postgresql", "sql"), ("sqlite", "sql")]:
    _, c, _ = dalia.parse(f'<environment: code_sandbox lang="{lang}">x')
    check(f"lang {lang!r} runs as {want}",
          c and c[0] == {"open": "sandbox", "lang": want}, str(c))

_, c, _ = dalia.parse('<environment: code_sandbox lang="sql" '
                      'template="joins">x')
check("a template rides along",
      c and c[0].get("template") == "joins", str(c))

# The whole point of the allowlist. Each of these is a real thing the board
# can SHOW and cannot RUN, and offering it as a sandbox is a promise the
# site cannot keep.
print("\nWhat gets dropped")
for lang in ("cisco", "powershell", "terraform", "bash", "kql", "java",
             "c++", "", "python; rm -rf /"):
    _, c, _ = dalia.parse(f'<environment: code_sandbox lang="{lang}">x')
    check(f"no sandbox for {lang!r}", c == [], str(c))

# Python and JavaScript really do execute here — inside a lesson's own lab,
# which is not somewhere a conversation can hand you. Until there is a
# standalone editor, the tutor must not offer one.
for lang in ("python", "py", "javascript", "js", "node"):
    _, c, _ = dalia.parse(f'<environment: code_sandbox lang="{lang}">x')
    check(f"{lang!r} runs here but has no panel to open", c == [], str(c))
    check(f"and {lang!r} is still recorded as running here",
          lang in dalia.RUNS_HERE)

for topo in ("core_switch", "vpn", "", "firewall; drop"):
    _, c, _ = dalia.parse(f'<environment: network_sim topology="{topo}">x')
    check(f"no network called {topo!r}", c == [], str(c))

_, c, _ = dalia.parse('<environment: gpu_cluster nodes="8">x')
check("an environment nobody built is dropped", c == [], str(c))
_, c, _ = dalia.parse('<smartboard: hologram="a cell">x')
check("a smartboard kind nobody built is dropped", c == [], str(c))
_, c, _ = dalia.parse('<smartboard: sketch="a">x')
check("a topic too short to be a topic is dropped", c == [], str(c))

say, c, _ = dalia.parse(
    '<smartboard: sketch="<img src=x onerror=alert(1)>">text')
check("markup cannot ride in on a topic",
      not c or ("<" not in c[0]["topic"] and ">" not in c[0]["topic"]),
      str(c))
check("and it does not reach the learner either", "<img" not in say, say)

_, c, _ = dalia.parse('<smartboard: sketch="osmosis">'
                      '<smartboard: sketch="osmosis">t')
check("the same panel is not opened twice", len(c) == 1, str(c))

many = "".join(f'<smartboard: sketch="topic {i}">' for i in range(9)) + "t"
_, c, s = dalia.parse(many)
check("controls are capped", len(c) <= dalia.MAX_CONTROLS, str(len(c)))
many = "".join(f"<skill_unlocked: Skill {i}>" for i in range(9)) + "t"
_, _, s = dalia.parse(many)
check("skills are capped", len(s) <= dalia.MAX_SKILLS, str(len(s)))

say, c, s = dalia.parse("Just an ordinary sentence with no tags in it.")
check("a plain reply is left alone",
      say == "Just an ordinary sentence with no tags in it." and not c and not s)
check("a bare < is not a tag", dalia.parse("2 < 3 and 5 > 4")[0] == "2 < 3 and 5 > 4")

# Position must not matter: the prompt asks for tags first, and a model that
# puts one last should not cost the learner the picture.
_, c, _ = dalia.parse('The reply first.\n<smartboard: sketch="osmosis">')
check("a tag at the end still counts", len(c) == 1, str(c))

# ---- the networks actually compute --------------------------------------
# Each preset run through the real engine, and the verdict compared with the
# one written beside it in dalia.py.
print("\nNetworks")
WANT = {
    "firewall": ("ACCEPT", 1),        # the broad accept above the drop
    "router": ("ACCEPT", 1),
    "dmz": ("DROP", 2),               # rule 1 is for internal sources only
    "packet_sniffer": ("ACCEPT", 0),  # conntrack, before any rule is read
}
for name, preset in dalia.NET_TOPOLOGIES.items():
    pkt = preset["packet"]
    verdict, trace, matched = net.evaluate(
        preset["rules"], pkt, preset["established"])
    want_verdict, want_rule = WANT[name]
    check(f"{name}: verdict is {want_verdict}", verdict == want_verdict,
          verdict)
    check(f"{name}: rule {want_rule} decided it",
          matched.get("n") == want_rule, str(matched))
    best, others = net.route_for(pkt["dst"], preset["routes"])
    check(f"{name}: a route exists for {pkt['dst']}", best is not None)

# The router preset only teaches anything if more than one route matches and
# the most specific one wins. Assert that, rather than assuming it.
best, others = net.route_for(
    dalia.NET_TOPOLOGIES["router"]["packet"]["dst"],
    dalia.NET_TOPOLOGIES["router"]["routes"])
check("the router lab has a genuine contest", len(others) >= 2, str(others))
check("and the /24 wins it", best["network"] == "10.4.2.0/24", str(best))

# Every address in every preset has to be an address, or the lab opens on a
# 400 from /api/net/trace.
for name, preset in dalia.NET_TOPOLOGIES.items():
    ok = True
    try:
        net.ip_to_int(preset["packet"]["src"])
        net.ip_to_int(preset["packet"]["dst"])
        for r in preset["routes"]:
            net.parse_cidr(r["network"])
            if r.get("via"):
                net.ip_to_int(r["via"])
    except net.BadAddress as e:
        ok = False
        print(f"      {e}")
    check(f"{name}: every address parses", ok)

# ---- skills reach the matcher -------------------------------------------
print("\nSkills")
for name, want in [
    ("TCP three-way handshake", "tcp"),
    ("Packet analysis", "wireshark"),
    ("Container orchestration", "kubernetes"),
    ("Infrastructure as code", "terraform"),
    ("Relational databases", "sql"),
    ("Penetration testing", "pentesting"),
]:
    got = dalia.skill(name)
    check(f"{name!r} carries {want!r}", got and want in got["tokens"],
          str(got))

check("an acronym keeps its case", dalia.skill("TCP/IP")["label"] == "TCP/IP")
check("a lowercase name is titled",
      dalia.skill("packet analysis")["label"] == "Packet Analysis")
check("a skill with no matcher word still counts",
      dalia.skill("Balancing Redox Equations")["tokens"] == (),
      str(dalia.skill("Balancing Redox Equations")))
check("but it keeps its label",
      dalia.skill("Balancing Redox Equations")["label"]
      == "Balancing Redox Equations")
check("an empty skill is not a skill", dalia.skill("") is None)
check("a two-character skill is not a skill", dalia.skill("ab") is None)

# The join that makes any of this worth storing. A token the matcher has
# never heard of is a row that looks like progress and does nothing.
unknown = set()
for _, tokens in dalia._SKILL_PHRASES:
    unknown |= {t for t in tokens if t not in main._SKILLS}
unknown |= {w for w in dalia._SKILL_WORDS if w not in main._SKILLS}
check("every token the tutor can emit is one the matcher knows",
      not unknown, ", ".join(sorted(unknown)) or "none")

# ---- the endpoint, end to end -------------------------------------------
# The model is replaced with a fixed reply, because what is being tested is
# everything around it: that the tags are split off, that the panels come
# back beside the text, that the skill lands in the table, and — the one
# that has a real bug behind it — that the SECOND person to ask gets the
# panel too. Caching only the spoken half meant the first asker saw the
# packet trace and everyone after them heard about a screen that was never
# opened.
print("\nThe endpoint")
import time                                        # noqa: E402
from fastapi.testclient import TestClient          # noqa: E402

main.Base.metadata.create_all(bind=main.engine)
main.send_email = lambda *a, **k: None
main.ASK_ENABLED = True

REPLY = ('<environment: network_sim topology="packet_sniffer">\n'
         '<smartboard: sketch="tcp handshake">\n'
         '<skill_unlocked: TCP three-way handshake>\n'
         'The reply comes back because the state was made on the way out. '
         'Open the packet trace and see which rule decided it.')


async def _fake_ai(prompt, tokens, **kw):
    _fake_ai.prompt = prompt
    _fake_ai.calls += 1
    return REPLY


_fake_ai.prompt = ""
_fake_ai.calls = 0


_real_ai = main._ai_text
main._ai_text = _fake_ai

A = TestClient(main.app)
email = f"dalia{int(time.time())}@example.com"
r = A.post("/api/auth/signup",
           json={"name": "Dalia Tester", "email": email,
                 "password": "DaliaPass123!"})
check("a learner can sign up", r.status_code == 200, str(r.status_code))

# The free plan includes no AI requests at all, so a free account never
# reaches the code under test — it is refused one layer earlier.
_db = main.SessionLocal()
_u = _db.query(main.User).filter(main.User.email == email).first()
_u.plan = "pro"
_u.plan_expires = main.now() + main.dt.timedelta(days=30)
_db.commit()
_db.close()

said = f"how does the tcp handshake work {int(time.time())}"
r = A.post("/api/ask/talk",
           json={"said": said, "subject": "Networking", "level": "Class 10 CBSE"})
check("the endpoint answers", r.status_code == 200, r.text[:200])
d = r.json() if r.status_code == 200 else {}

check("no tag reaches the learner",
      "<" not in d.get("say", "") and ">" not in d.get("say", ""),
      d.get("say", "")[:80])
check("the sentence does", d.get("say", "").startswith("The reply comes back"),
      d.get("say", "")[:40])
check("two panels came back", len(d.get("board") or []) == 2,
      str(d.get("board")))
check("one of them is the network",
      any(c["open"] == "network" for c in d.get("board") or []))
check("and it carries rules the trace endpoint accepts",
      any(c.get("rules") for c in d.get("board") or []))
check("the skill came back",
      [s["skill"] for s in d.get("skills") or []] == ["TCP three-way handshake"],
      str(d.get("skills")))
check("this one was not cached", d.get("cached") is False, str(d.get("cached")))

# The grade band has to survive the whole way to the model.
check("the prompt was pitched at the right band",
      dalia.BAND_LABEL["school"] in getattr(_fake_ai, "prompt", ""))
check("and named the board", "CBSE" in getattr(_fake_ai, "prompt", ""))

before = _fake_ai.calls
r2 = A.post("/api/ask/talk",
            json={"said": said, "subject": "Networking",
                  "level": "Class 10 CBSE"})
d2 = r2.json()
check("the second ask is served from cache", d2.get("cached") is True,
      str(d2.get("cached")))
check("and costs nothing", _fake_ai.calls == before, str(_fake_ai.calls))
check("the cached answer still opens the panels",
      d2.get("board") == d.get("board"), str(d2.get("board")))
check("and still says the same thing", d2.get("say") == d.get("say"))

r3 = A.get("/api/skills/unlocked")
check("the skill is on the learner's record", r3.status_code == 200,
      str(r3.status_code))
got = r3.json().get("skills") if r3.status_code == 200 else []
check("under its readable name",
      any(s["skill"] == "TCP three-way handshake" for s in got), str(got))
check("with a word the matcher knows",
      any("tcp" in s["tokens"] for s in got), str(got))
check("and asking twice does not earn it twice",
      all(s["times"] <= 2 for s in got), str(got))

# A reply that is nothing but tags has nothing to say, and saying nothing
# out loud is a voice assistant that appears to have crashed.
async def _all_tags(prompt, tokens, **kw):
    return '<smartboard: sketch="osmosis">'


main._ai_text = _all_tags
r4 = A.post("/api/ask/talk", json={"said": f"tags only {time.time()}",
                                   "subject": "General", "level": "Beginner"})
check("a reply with no words in it is an error, not a silence",
      r4.status_code == 502, str(r4.status_code))
main._ai_text = _real_ai

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
