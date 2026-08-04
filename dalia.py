"""Dalia — who the tutor is, and what she is allowed to open.

The tutor prompts on this site grew one endpoint at a time, and each one
carries its own idea of who is being taught. The board assumes somebody
studying a job skill, the ask endpoint assumes a school subject, and the
corner bot assumes neither. A learner who moves between them meets three
different teachers, and only one of them knows what grade they are in.

This is the single answer to that: one persona, one set of rules, and one
place where the grade band, the exam board and the depth are worked out
before a word of the prompt is written.

The other half of the file is the part that matters more. The prompt lets
Dalia open things — a 3D scene on the board, a packet through the firewall
engine, a code sandbox — by emitting a control tag. A model that can name a
UI it wants opened will name UIs that do not exist, confidently, and the
learner gets an empty panel and a tutor talking about the diagram in front
of them. So nothing here is taken on trust:

- Every control tag is rebuilt from an allowlist rather than filtered. A key
  nobody anticipated does not survive into the payload.
- Every value is checked against something the site really renders: a
  language that really executes, a topology the packet engine really
  computes, a board handoff that really exists.
- A tag naming anything else is dropped, silently, and the sentence stays.
  A tutor who says nothing about a picture is fine. A tutor who talks about
  a picture that never appeared is broken.

The network presets are here rather than in `net.py` for the same reason
`net.py` has no model in it: they are teaching material with a correct
answer, and each one is a network whose verdict the engine computes. They
are not illustrations of a firewall — they are firewalls.

Nothing in this file makes a network request or a model call, so all of it
is free, instant, identical for everybody, and testable without a key.
"""
import re

NAME = "Dalia"

# --------------------------------------------------------------------------
# Where the learner is standing
# --------------------------------------------------------------------------
# Two separate axes, because the site has always had two and conflating them
# is what produced a beginner being handed theorem proofs. A grade band is
# an academic standing — what apparatus the learner has met. A pace is how
# hard to push inside it. "Class 9, advanced" and "PhD, beginner" are both
# real people and neither is served by a single slider.

BANDS = ("primary", "school", "undergraduate", "research")
PACES = ("beginner", "intermediate", "advanced")

BAND_LABEL = {
    "primary": "Primary / middle school",
    "school": "High school / board exams",
    "undergraduate": "University / undergraduate",
    "research": "Postgraduate / research",
}

# How each band is taught. This is the whole of the grade adapter: everything
# else in the prompt is the same for everybody.
BAND_RULE = {
    "primary": (
        "Foundational mechanics and visual intuition. Short sentences, "
        "everyday words, one new term at a time and defined the moment it "
        "appears. Reach for something they can picture — sharing food, "
        "walking to school, cricket scores — before reaching for notation. "
        "Arithmetic, not algebra, unless they used algebra first. Warm and "
        "encouraging: at this age being wrong out loud has to stay cheap."),
    "school": (
        "The board's own framing and the board's own words. Use the standard "
        "textbook phrasing for definitions, because that is what the answer "
        "script is marked against, and say which step earns which mark when "
        "the question is an exam question. Full working, in the order the "
        "examiner expects it. Notation is fair game and units are compulsory."),
    "undergraduate": (
        "Formal treatment. State the theorem or the principle, then argue it "
        "— derivation, mechanism, proof sketch — and say what its conditions "
        "are. Standard academic nomenclature, defined once. Where the subject "
        "has a canonical architecture or a canonical result, name it and use "
        "it rather than paraphrasing it."),
    "research": (
        "Assume the standard treatment is already known and do not restate "
        "it. Go to the edge cases, the assumptions the standard result "
        "quietly makes, and where the current methodology actually sits. "
        "Cite primary literature by author and year only when you are certain "
        "of it — an invented citation is the single worst thing you can hand "
        "a researcher, because it is the one thing they will pass on."),
}

PACE_RULE = {
    "beginner": "They have not met this before. Nothing is assumed.",
    "intermediate": "They know the surrounding material. Skip the basics.",
    "advanced": "They know this. Go to the hard part, the exception, the "
                "case that breaks the rule.",
}

# Ordered, and the order is the whole of the detection. Research words beat
# a grade number because "PhD, year 2" is not class 2.
_BAND_WORDS = (
    ("research", r"\b(ph\.?d|d\.?phil|doctoral|doctorate|post[\s-]?doc|"
                 r"researcher|research scholar|thesis|dissertation|"
                 r"m\.?tech|m\.?sc|m\.?s\.?c|masters?|postgrad\w*|"
                 r"pg\b|mphil)\b"),
    ("undergraduate", r"\b(under[\s-]?grad\w*|bachelor\w*|b\.?tech|b\.?e\b|"
                      r"b\.?sc|b\.?c\.?a|bba|b\.?com|b\.?a\b|degree|"
                      r"university|college|freshman|sophomore|semester|"
                      r"diploma|polytechnic)\b"),
    ("school", r"\b(high school|higher secondary|senior secondary|secondary|"
               r"sixth form|c\.?b\.?s\.?e|i\.?c\.?s\.?e|"
               r"i?gcse|a[\s-]?levels?|as[\s-]?levels?|"
               r"advanced placement|\bap\b|\bib\b|board exam\w*|boards\b|"
               r"h\.?s\.?c|s\.?s\.?c|state board|matric\w*|"
               r"jee|neet|\bsat\b|plus two|\+2)\b"),
    ("primary", r"\b(primary|elementary|middle school|junior school|"
                r"kindergarten|\bkg\b|nursery|montessori)\b"),
)

# "Class 8", "grade 3", "3rd standard". Deliberately not "year 8": on an
# India-first site "second year" is a degree far more often than it is a
# seven-year-old, and reading it as a school year put an engineering student
# in the primary band.
_GRADE_NUM = re.compile(
    r"\b(?:grade|class|std|standard)\s*\.?\s*(\d{1,2})\b|"
    r"\b(\d{1,2})\s*(?:st|nd|rd|th)?\s+(?:grade|class|std|standard)\b", re.I)

_ORDINALS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5, "sixth": 6,
    "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10, "eleventh": 11,
    "twelfth": 12,
}
_GRADE_WORD = re.compile(
    r"\b(" + "|".join(_ORDINALS) + r")\s+(?:grade|class|std|standard)\b", re.I)

_PACE_WORDS = (
    ("advanced", r"\b(advanced|expert|experienced|hard|deep dive)\b"),
    ("beginner", r"\b(beginner|basic|novice|new to|starting|first time|"
                 r"absolute beginner|from scratch)\b"),
    ("intermediate", r"\b(intermediate|some experience|refresher)\b"),
)

# Exam frameworks worth naming back to the learner. The value is what goes
# in the prompt, so it is spelled the way the board spells itself.
_FRAMEWORKS = (
    (r"\bc\.?b\.?s\.?e\b", "CBSE"),
    (r"\bi\.?c\.?s\.?e\b", "ICSE"),
    (r"\bigcse\b", "IGCSE"),
    (r"\bgcse\b", "GCSE"),
    (r"\ba[\s-]?levels?\b|\bas[\s-]?levels?\b", "A-level"),
    (r"\badvanced placement\b|\bap\b", "AP"),
    (r"\bib\b|international baccalaureate", "IB"),
    (r"\bjee\b", "JEE"),
    (r"\bneet\b", "NEET"),
    (r"\bgate\b", "GATE"),
    (r"\bupsc\b", "UPSC"),
    (r"\bsat\b", "SAT"),
    (r"\bstate board\b", "State board"),
    (r"\bh\.?s\.?c\b", "HSC"),
    (r"\bs\.?s\.?c\b", "SSC"),
)


def band(level):
    """The learner's academic standing, from whatever they told us.

    Defaults to undergraduate rather than to school. The site's own three
    levels — Beginner, Intermediate, Advanced — say nothing about standing,
    and most people typing them are adults learning a job skill. Guessing
    school for them produces a tutor that explains what a variable is to a
    network engineer.
    """
    t = " " + str(level or "").lower().strip() + " "

    m = _GRADE_NUM.search(t) or _GRADE_WORD.search(t)
    if m:
        if m.re is _GRADE_WORD:
            n = _ORDINALS[m.group(1).lower()]
        else:
            n = int(m.group(1) or m.group(2))
        if 1 <= n <= 8:
            return "primary"
        if 9 <= n <= 12:
            return "school"

    for name, pattern in _BAND_WORDS:
        if re.search(pattern, t, re.I):
            return name
    return "undergraduate"


def pace(level):
    """How hard to push, inside whatever band they are in."""
    t = " " + str(level or "").lower().strip() + " "
    for name, pattern in _PACE_WORDS:
        if re.search(pattern, t, re.I):
            return name
    return "intermediate"


def framework(level):
    """The exam board named, if one was. Empty when none was."""
    t = " " + str(level or "").lower().strip() + " "
    for pattern, label in _FRAMEWORKS:
        if re.search(pattern, t, re.I):
            return label
    return ""


# --------------------------------------------------------------------------
# What she is allowed to open
# --------------------------------------------------------------------------
# Every value below is something this site really does. A language that
# really executes, a topology the packet engine really computes, a board
# that really builds a scene. Adding a name here without building the thing
# behind it is how a tutor ends up describing an empty panel.

# Three languages really execute on this site. Python and JavaScript run in
# the browser through Pyodide; SQL runs on the server against the practice
# database. Everything else the board can show — Cisco IOS, PowerShell,
# Terraform, KQL — is a screen to read, not a box to type in, and calling
# one a sandbox is a promise the site cannot keep.
RUNS_HERE = {
    "python": "py", "py": "py", "python3": "py", "pyodide": "py",
    "javascript": "js", "js": "js", "node": "js", "nodejs": "js",
    "sql": "sql", "postgres": "sql", "postgresql": "sql", "sqlite": "sql",
    "mysql": "sql",
}

# Of those three, only SQL has somewhere to be opened.
#
# Python and JavaScript run inside a lesson's own lab — a specific exercise
# with a specific starter file — and there is no standalone editor to hand
# somebody mid-conversation. So the tutor is told about the SQL board and
# not about the other two, because a tag she can emit and nobody can open is
# the exact failure this file exists to stop: a tutor saying "try it in the
# sandbox below" above a sandbox that is not below.
#
# Adding a standalone Python panel is what changes this line, in that order.
# The prompt follows the interface; it has never worked the other way round.
SANDBOX_LANGS = {k: v for k, v in RUNS_HERE.items() if v == "sql"}

# The three ways a picture reaches the board. All of them hand the topic to
# the board, which builds the real thing through the pipeline that already
# checks it — measured coordinates from PubChem, a lattice constant from a
# table, a plot from points rather than from a formula. Dalia says what is
# worth seeing; she does not place the atoms.
SMARTBOARD_KINDS = ("3d_model", "2d_diagram", "sketch")

MAX_CONTROLS = 3
MAX_SKILLS = 3


def _clean_topic(text, limit=80):
    """A topic as a topic: words, digits and the punctuation a title needs.

    Rebuilt from what is allowed rather than stripped of what is not, which
    is the same discipline the scene and sketch schemas use. There is then
    no field here that can carry markup, so there is nothing to sanitise.
    """
    t = re.sub(r"[^A-Za-z0-9 .,'()/+&-]", " ", str(text or ""))
    t = re.sub(r"\s{2,}", " ", t).strip(" -.,")
    return t[:limit]


# --------------------------------------------------------------------------
# Networks that compute
# --------------------------------------------------------------------------
# Four topologies, each a real set of routes and rules that `net.evaluate`
# and `net.route_for` walk to a verdict. They are ordinary starting points
# with one thing each that people get wrong, because a lab whose answer is
# obvious teaches nobody anything:
#
#   firewall        a permissive rule above a restrictive one makes the
#                   restrictive one dead, and the list still reads as
#                   though it does something
#   router          longest prefix wins, not first listed and not most
#                   recently added
#   dmz             the same host is reachable on one port and not another,
#                   from outside and not from in
#   packet_sniffer  the reply comes back through a firewall that has no
#                   inbound rule at all, because the connection is already
#                   established
#
# Every packet here has been run through the engine in tests/test_dalia.py,
# so the verdict in the comment is the verdict the learner gets.

NET_TOPOLOGIES = {
    "firewall": {
        "title": "Rule order decides everything",
        "teaches": "The first matching rule wins, so a broad accept above a "
                   "narrow drop makes the drop unreachable.",
        "routes": [
            {"network": "192.168.1.0/24", "via": "", "dev": "eth1"},
            {"network": "0.0.0.0/0", "via": "203.0.113.1", "dev": "eth0"},
        ],
        "rules": [
            {"action": "accept", "proto": "tcp", "src": "any",
             "dst": "192.168.1.10", "port": 443},
            {"action": "drop", "proto": "tcp", "src": "203.0.113.0/24",
             "dst": "any", "port": "any"},
        ],
        # ACCEPT: rule 1 matched first, so the drop written for this exact
        # source never gets read.
        "packet": {"src": "203.0.113.7", "dst": "192.168.1.10",
                   "proto": "tcp", "dport": 443},
        "established": False,
    },
    "router": {
        "title": "Longest prefix wins",
        "teaches": "Three routes match this destination. The most specific "
                   "one is chosen, whatever order they are listed in.",
        "routes": [
            {"network": "0.0.0.0/0", "via": "203.0.113.1", "dev": "eth0"},
            {"network": "10.0.0.0/8", "via": "192.168.1.1", "dev": "eth1"},
            {"network": "10.4.2.0/24", "via": "192.168.1.9", "dev": "eth1"},
        ],
        "rules": [
            {"action": "accept", "proto": "any", "src": "any",
             "dst": "any", "port": "any"},
        ],
        # The /24 wins over the /8 and the default, both of which also match.
        "packet": {"src": "192.168.1.50", "dst": "10.4.2.30",
                   "proto": "tcp", "dport": 22},
        "established": False,
    },
    "dmz": {
        "title": "A public server that is not publicly administered",
        "teaches": "One host, two ports, two different answers — and SSH "
                   "from the internal network is a third.",
        "routes": [
            {"network": "172.16.0.0/24", "via": "", "dev": "dmz0"},
            {"network": "192.168.1.0/24", "via": "", "dev": "lan0"},
            {"network": "0.0.0.0/0", "via": "203.0.113.1", "dev": "wan0"},
        ],
        "rules": [
            {"action": "accept", "proto": "tcp", "src": "192.168.1.0/24",
             "dst": "172.16.0.10", "port": 22},
            {"action": "drop", "proto": "tcp", "src": "any",
             "dst": "172.16.0.10", "port": 22},
            {"action": "accept", "proto": "tcp", "src": "any",
             "dst": "172.16.0.10", "port": 443},
        ],
        # DROP: rule 1 does not match an internet source, rule 2 does.
        "packet": {"src": "198.51.100.20", "dst": "172.16.0.10",
                   "proto": "tcp", "dport": 22},
        "established": False,
    },
    "packet_sniffer": {
        "title": "Why the reply came back",
        "teaches": "There is no inbound rule for this packet and it is "
                   "accepted anyway, because the connection state was "
                   "created on the way out.",
        "routes": [
            {"network": "192.168.1.0/24", "via": "", "dev": "eth1"},
            {"network": "0.0.0.0/0", "via": "203.0.113.1", "dev": "eth0"},
        ],
        "rules": [
            {"action": "accept", "proto": "tcp", "src": "192.168.1.0/24",
             "dst": "any", "port": 443},
        ],
        # ACCEPT before a rule is read at all — the conntrack entry decides.
        "packet": {"src": "93.184.216.34", "dst": "192.168.1.50",
                   "proto": "tcp", "dport": 443},
        "established": True,
    },
}


# --------------------------------------------------------------------------
# Skills, in the words the matcher actually uses
# --------------------------------------------------------------------------
# A finished lesson is supposed to reach the resume builder and the job
# matcher. Those run on a fixed vocabulary of named tools and protocols —
# `tcp`, `wireshark`, `bgp` — and "Computer Networking Protocols" matches
# nothing in it. An unlock stored under its lesson name is a row that looks
# like progress and moves no candidate one place up a match list.
#
# So an unlock carries two things: the label the learner sees on their
# resume, and the tokens the matcher can use. The tokens can be empty —
# plenty of real skills have no token, and an honest zero is better than
# a nearest-guess that files a chemistry lesson under Kubernetes.
#
# Only tokens in main.py's `_SKILLS` are worth emitting. tests/test_dalia.py
# asserts that every token this table can produce is in that set, so the two
# cannot drift apart without a test going red.
_SKILL_PHRASES = (
    # networking
    ("tcp three-way handshake", ("tcp", "wireshark")),
    ("three-way handshake", ("tcp",)),
    ("computer networking protocols", ("tcp", "dns")),
    ("networking protocols", ("tcp", "dns")),
    ("packet analysis", ("wireshark", "tcp")),
    ("packet capture", ("wireshark",)),
    ("subnetting", ("tcp",)),
    ("routing protocols", ("bgp", "ospf")),
    ("network routing", ("bgp", "ospf")),
    ("switching and vlans", ("vlan", "cisco")),
    ("dns resolution", ("dns",)),
    ("name resolution", ("dns",)),
    # security
    ("firewall configuration", ("vpn", "fortinet")),
    ("firewall rules", ("vpn", "fortinet")),
    ("penetration testing", ("pentesting", "metasploit")),
    ("vulnerability assessment", ("nessus", "pentesting")),
    ("security operations", ("siem", "soc")),
    ("log analysis", ("splunk", "siem")),
    ("identity and access management", ("iam", "okta")),
    # cloud and platform
    ("container orchestration", ("kubernetes", "docker")),
    ("containerisation", ("docker",)),
    ("containerization", ("docker",)),
    ("infrastructure as code", ("terraform", "ansible")),
    ("continuous integration", ("jenkins", "cicd")),
    ("continuous delivery", ("jenkins", "cicd")),
    ("configuration management", ("ansible",)),
    # data and code
    ("relational databases", ("sql", "postgres")),
    ("database design", ("sql",)),
    ("query optimisation", ("sql",)),
    ("query optimization", ("sql",)),
    ("data pipelines", ("airflow", "spark")),
    ("machine learning", ("machinelearning", "sklearn")),
    ("deep learning", ("deeplearning", "pytorch")),
    ("natural language processing", ("nlp",)),
    ("web development", ("html", "css")),
    ("version control", ("git",)),
    ("unit testing", ("pytest",)),
)

# Sorted longest first so "tcp three-way handshake" is found before
# "three-way handshake" and both before a bare word scan.
_SKILL_PHRASES = tuple(sorted(_SKILL_PHRASES, key=lambda p: -len(p[0])))

# Single words that are already the matcher's own. Kept short and specific
# on purpose: the matcher's vocabulary contains "excel" and "git", and a
# lesson that mentions either in passing should not unlock it.
_SKILL_WORDS = frozenset("""
python javascript typescript java sql postgres mysql mongodb redis kafka
spark airflow pandas numpy pytorch tensorflow sklearn nlp llm rag
aws azure gcp docker kubernetes terraform ansible jenkins linux bash
powershell graphql cisco juniper fortinet bgp ospf mpls vlan vpn ipsec
wireshark snmp tcp udp dns dhcp ldap radius nginx apache pentesting
metasploit nessus splunk siem soc iam okta react angular vue django
flask fastapi spring selenium cypress pytest git helm prometheus grafana
""".split())


def skill(name):
    """One unlocked skill: what the learner sees, and what the matcher gets.

    Returns None when the name is not a skill at all — empty, or so long it
    is a sentence. A label with no tokens is still returned: the learner
    earned it, and the resume can carry it even when the job board has no
    word for it.
    """
    label = _clean_topic(name, 60)
    if len(label) < 3:
        return None
    low = " " + re.sub(r"[^a-z0-9+#. ]", " ", label.lower()) + " "
    low = re.sub(r"\s{2,}", " ", low)

    tokens = []
    for phrase, mapped in _SKILL_PHRASES:
        if " " + phrase + " " in low:
            tokens.extend(mapped)
            break
    if not tokens:
        for w in low.split():
            if w in _SKILL_WORDS and w not in tokens:
                tokens.append(w)

    # Title case, but never on something already capitalised deliberately —
    # "TCP/IP" must not come back as "Tcp/Ip".
    if label.islower():
        label = label.title()
    return {"label": label, "tokens": tuple(tokens[:4])}


# --------------------------------------------------------------------------
# Reading the tags back out
# --------------------------------------------------------------------------
# The model is asked to put its control tags on their own lines before the
# text. It will sometimes put them after it, or inline, or twice. All three
# are read the same way, because a tutor whose picture depends on where the
# model happened to put a tag is a tutor whose picture is a coin toss.

_TAG = re.compile(
    r"<\s*(smartboard|environment|skill_unlocked)\s*:\s*([^<>]{0,200}?)\s*>",
    re.I)
# The key may start with a digit — `3d_model`, `2d_diagram` — which an
# identifier-shaped pattern quietly refuses, and the tag then parses as
# having no key at all and is dropped. Every 3D scene the tutor asked for
# disappeared that way, silently, which is the exact failure this file
# exists to prevent.
_ATTR = re.compile(r"""([a-z0-9_]{2,20})\s*=\s*["']([^"']{0,120})["']""", re.I)

# A malformed tag — markup inside a topic, a missing quote — never matches
# _TAG, because _TAG's body cannot contain an angle bracket. Left alone it
# reaches the learner as literal `<smartboard: ...>` in the middle of a
# sentence, or gets read out by the voice. This sweeps up what is left.
#
# It runs only AFTER every well-formed tag has been removed, and it takes
# the rest of the line, because the rest of a broken tag's line is part of
# the broken tag. Running it first would eat "osmosis is when 3 > 2".
_TAG_RESIDUE = re.compile(
    r"<\s*(?:smartboard|environment|skill_unlocked)\b[^\n]*", re.I)


def _smartboard(body):
    """A picture request, as a handoff to the board.

    The board is what owns the pipeline that builds a real scene: measured
    coordinates, a lattice constant from a table, a plot drawn from points.
    So a smartboard tag does not carry geometry and is not asked to. It
    carries the topic and which kind of picture would help, and the board
    does the part that has to be right.
    """
    attrs = dict((k.lower(), v) for k, v in _ATTR.findall(body))
    for kind in SMARTBOARD_KINDS:
        if kind in attrs:
            topic = _clean_topic(attrs[kind])
            if len(topic) < 3:
                return None
            return {"open": "board", "kind": kind, "topic": topic}
    return None


def _environment(body):
    """A sandbox or a network, if it is one this site really has."""
    head = body.split()[0].lower().strip(":") if body.split() else ""
    attrs = dict((k.lower(), v) for k, v in _ATTR.findall(body))

    if head == "code_sandbox":
        lang = SANDBOX_LANGS.get((attrs.get("lang") or "").strip().lower())
        if not lang:
            # A language nothing here executes. Dropped rather than opened
            # empty: "type your Cisco config in the sandbox" is a sandbox
            # that does not exist, and the learner finds that out by typing.
            return None
        out = {"open": "sandbox", "lang": lang}
        template = _clean_topic(attrs.get("template", ""), 40)
        if template:
            out["template"] = template
        return out

    if head == "network_sim":
        name = re.sub(r"[^a-z_]", "", (attrs.get("topology") or "").lower())
        preset = NET_TOPOLOGIES.get(name)
        if not preset:
            return None
        return {"open": "network", "topology": name,
                "title": preset["title"], "teaches": preset["teaches"],
                "routes": [dict(r) for r in preset["routes"]],
                "rules": [dict(r) for r in preset["rules"]],
                "packet": dict(preset["packet"]),
                "established": preset["established"]}
    return None


def parse(text):
    """Split a reply into what is said, what is opened, and what was earned.

    Returns (spoken, controls, skills). The tags never reach the learner —
    they are an instruction to the interface, and read aloud they are noise.
    """
    controls, skills, seen = [], [], set()

    for tag, body in _TAG.findall(text or ""):
        tag = tag.lower()
        got = None
        if tag == "smartboard":
            got = _smartboard(body)
        elif tag == "environment":
            got = _environment(body)
        elif tag == "skill_unlocked":
            got = None
            sk = skill(body)
            if sk and sk["label"].lower() not in seen:
                seen.add(sk["label"].lower())
                skills.append(sk)
            continue
        if not got:
            continue
        key = (got["open"], got.get("kind", ""), got.get("topic", ""),
               got.get("lang", ""), got.get("topology", ""))
        if key in seen:
            continue
        seen.add(key)
        controls.append(got)

    spoken = _TAG_RESIDUE.sub(" ", _TAG.sub(" ", text or ""))
    spoken = re.sub(r"[ \t]{2,}", " ", spoken)
    spoken = re.sub(r"\n{3,}", "\n\n", spoken).strip()
    return spoken, controls[:MAX_CONTROLS], skills[:MAX_SKILLS]


# --------------------------------------------------------------------------
# The prompt
# --------------------------------------------------------------------------

_PERSONA = (
    f"You are {NAME}, the tutor on Craxle. You teach any subject at any "
    "level, from a child's first fractions to a researcher's edge case, and "
    "you can put things on the learner's screen while you do it.\n"
)

# Answer first, then one question. Both halves of that are load-bearing and
# both were learned the hard way.
#
# Socratic questioning that withholds the answer reads as helpful and is
# not: somebody who asked how to solve a squared plus b squared and got a
# question back has been charged for a delay. The site already carries the
# scar — the corner bot's prompt had to be told, in as many words, not to
# ask what two times two is on the way to a result.
#
# But a turn that ends flat also ends the lesson, and on a voice interface
# there is nothing on screen inviting the next thing. So: the answer is
# never withheld, and the question comes after it, once, and checks that it
# landed or opens what comes next.
_SOCRATIC = (
    "ANSWER, THEN ASK. Give the answer to what was actually asked, in full, "
    "and reach it — do not describe an approach and stop, and do not ask a "
    "question in place of an answer. Then close with exactly one question, "
    "and make it earn its place: check that the step just taught has landed, "
    "or open the next one. Never two questions. Never a question that asks "
    "them to do the work they came here for, and never one that asks for a "
    "value you do not need — pick a sensible one, say you are picking it, "
    "and carry on.\n"
)

_HONESTY = (
    "SAY WHEN YOU DO NOT KNOW. If you are not sure of a fact, a number, a "
    "citation or a command, say \"I do not have enough verified information "
    "to answer this completely\" and say which part you are unsure of. Do "
    "not fill the gap. An invented command, an invented case citation or an "
    "invented paper is worse than silence, because the learner cannot tell "
    "it from the parts you got right.\n"
)


def _controls_rule(spoken):
    """What she may open, written out with only the values that exist."""
    langs = ", ".join(sorted({v for v in SANDBOX_LANGS.values()}))
    topos = ", ".join(sorted(NET_TOPOLOGIES))
    return (
        "WHAT YOU CAN OPEN. You may put something on the learner's screen by "
        "writing a control tag on its own line BEFORE your text. Use one "
        "only when seeing the thing does real work; a picture nobody needs "
        "is a picture nobody looks at.\n"
        "  <smartboard: 3d_model=\"[subject]\"> — something with structure "
        "worth turning around: a molecule, a crystal, a layer stack, an "
        "orbit.\n"
        "  <smartboard: 2d_diagram=\"[topic]\"> — something that lives on a "
        "plane: a graph, a bar chart, a timeline.\n"
        "  <smartboard: sketch=\"[topic]\"> — a drawing of how parts relate.\n"
        f"  <environment: code_sandbox lang=\"[{langs.replace(', ', '|')}]\" "
        "template=\"[optional]\"> — a box the learner types real code into "
        f"and runs. Only these languages run here: {langs}. Do not name any "
        "other language in this tag; for anything else, show the screen in "
        "your text and say what the output means.\n"
        f"  <environment: network_sim topology=\"[{topos.replace(', ', '|')}]\">"
        " — a real network the packet engine walks, hop by hop, to a real "
        f"verdict. Only these exist: {topos}.\n"
        "  <skill_unlocked: [Skill name]> — hidden from the learner. Emit it "
        "when they have actually finished something: solved the problem, "
        "read the capture, got the query right. Not for a topic you merely "
        "mentioned, because it lands on their resume and in front of an "
        "employer.\n"
        "A tag becomes a button the learner presses, not a panel that "
        "appears over them — nobody wants the page to jump while they are "
        "still reading. So write as though it is about to be opened, not as "
        "though it already is: \"open the packet trace and look at what rule "
        "two does\", never \"as you can see on the screen\".\n"
        "A tag naming anything not listed above is dropped before the "
        "learner sees it, and your text is then pointing at a button that "
        "is not there. Never mention a panel you have not tagged, and never "
        "tag one you do not then use"
        + (" out loud.\n" if spoken else ".\n"))


def _format_rule(spoken):
    if spoken:
        # A voice reading "$\frac{1}{4}$" says "dollar frac one four dollar".
        return (
            "THIS IS SPEECH, NOT WRITING. It is read aloud, so:\n"
            "- Two to five sentences. Then stop, so they can answer.\n"
            "- No lists, no headings, no markdown, no asterisks, no code "
            "blocks, and no LaTeX. A voice reads a backslash as a word.\n"
            "- Say symbols as words: \"x squared\", \"one quarter\", "
            "\"ten to the minus three\".\n")
    return (
        "HOW IT IS WRITTEN. Short lines, one idea per line, no wall of "
        "prose. Use LaTeX for formal mathematics and physics and nowhere "
        "else: $ inline $ for a symbol in a sentence, $$ display $$ for an "
        "equation that stands alone. Prose is not mathematics — do not "
        "wrap a sentence in dollar signs.\n")


def system(level="", subject="", spoken=False):
    """The whole of who Dalia is, for one learner at one moment.

    `spoken` is not decoration: it decides between LaTeX and words for the
    same equation, and getting it wrong is the difference between a legible
    board and a voice saying "backslash frac".
    """
    b, p = band(level), pace(level)
    fw = framework(level)
    subject = _clean_topic(subject, 60)

    out = [_PERSONA, "\n"]
    out.append(f"WHO YOU ARE TEACHING: {BAND_LABEL[b]}.\n")
    out.append(BAND_RULE[b] + "\n")
    out.append(PACE_RULE[p] + "\n")
    if fw:
        out.append(
            f"They are working to {fw}. Use its syllabus framing, its "
            f"terminology and its marking conventions, and say when "
            f"something is outside it.\n")
    if subject:
        out.append(f"The subject in front of them is {subject}.\n")
    out.append("\n")
    out.append(_SOCRATIC)
    out.append(_HONESTY)
    out.append(_format_rule(spoken))
    out.append(_controls_rule(spoken))
    out.append(
        "No greeting and no preamble. Do not open with \"Great question\", "
        "do not restate what they asked, and do not summarise what you are "
        "about to say. The first thing you say is the first real thing you "
        "have to say.\n")
    return "".join(out)


def talk_prompt(said, history=(), level="", subject=""):
    """One turn of the spoken conversation, system rules and all."""
    hist = ("\n".join(f"- {h}" for h in list(history)[-4:])
            if history else "(this is the first thing they said)")
    return (
        system(level=level, subject=subject, spoken=True)
        + f"\nWHAT HAS BEEN SAID SO FAR:\n{hist}\n"
        + f"\nTHEY JUST SAID: {said}\n")
