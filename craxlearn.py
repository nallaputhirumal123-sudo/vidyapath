"""Craxlearn — where a learner's questions are kept, and where answers come from.

Two rules, and they point in opposite directions on purpose.

**What a learner did stays inside their institution.** What was searched and
what was asked is the most revealing thing this product holds. A class of
fourteen-year-olds asking about a topic they are failing is a record of who
is struggling with what, by name, and a school that hands us its students is
entitled to have that stay theirs. So it is stored scoped to the institution
and it never leaves: not into another school, not into the public pool, and
not into anybody else's answer.

**What is taught comes from open sources.** The other half of the same
promise. If institution data is never a source, then everything the tutor
sources has to come from somewhere public — and it does: PubChem, the
Protein Data Bank, NASA, Wikimedia, and the measured tables in this repo.
Every one is listed below with its licence, because "where does your content
come from" is the first question an institution asks and the answer should
be a list rather than a reassurance.

The two rules together are the product: private about people, open about
knowledge. The cache is where they meet, and where getting it wrong would be
invisible. `AskCache` serves one person's stored answer to the next person
who asks something similar — which is the whole cost model, and which, left
unscoped, is a machine for moving one school's questions into another
school's session. `scope_of` is what stops that, and `tests/test_craxlearn.py`
is what proves it stayed stopped.

Nothing here makes a network request or a model call.
"""

NAME = "Craxlearn"

# --------------------------------------------------------------------------
# Where a stored answer may be served
# --------------------------------------------------------------------------
# Every cached answer carries a scope, and a lookup only ever sees its own.
# Two scopes exist:
#
#   public          somebody learning on their own account. Their questions
#                   pool, which is what makes the site cheap to run: the
#                   first person to ask what a foreign key is pays for it
#                   and everybody after them does not.
#
#   school:<id>     somebody who joined through an institution. Their
#                   questions pool only with the rest of that institution.
#                   It costs more model calls — the same question gets paid
#                   for once per school instead of once ever — and that is
#                   the price of the promise, paid knowingly.
#
# The default is the private one. A user whose institution cannot be
# determined gets `school:0` rather than `public`, because the failure that
# matters here is a school's data landing in the public pool, and it should
# take a positive answer to put anything there.

PUBLIC = "public"


def scope_of(school_id=None, in_institution=False):
    """The scope a person's questions and answers live in.

    `in_institution` is the deciding fact, not `school_id`. A learner enrolled
    in a class whose school row has gone missing is still an institution
    learner, and reading that as "no school, therefore public" is exactly the
    wrong way round — it would put the one record that must not pool into the
    pool that everybody reads.
    """
    if not in_institution:
        return PUBLIC
    try:
        sid = int(school_id or 0)
    except (TypeError, ValueError):
        sid = 0
    return f"school:{max(sid, 0)}"


def is_institution(scope):
    return str(scope or PUBLIC) != PUBLIC


def school_id_of(scope):
    """The institution a scope belongs to, or 0 for the public pool."""
    s = str(scope or PUBLIC)
    if not s.startswith("school:"):
        return 0
    try:
        return max(int(s.split(":", 1)[1]), 0)
    except (TypeError, ValueError):
        return 0


def key(scope, *parts):
    """A cache key that cannot be reached from another scope.

    The scope goes first and is not optional. Appending it, or leaving it off
    when it happens to be public, is how two keys end up colliding across a
    boundary — and a collision here is not a wrong answer, it is one school
    reading another school's question.
    """
    return "|".join([str(scope or PUBLIC)] + [str(p) for p in parts])


def scope_from_key(k):
    """The scope a key was built in, read back out of it.

    The key is the thing the uniqueness constraint enforces, so it is the
    authority on which pool a row belongs to. Reading the column back off it
    means the two can never disagree — and a row whose key predates all of
    this has no leading scope, which reads as public, which is what those
    rows were.
    """
    head = str(k or "").split("|", 1)[0]
    if head == PUBLIC or head.startswith("school:"):
        return head
    return PUBLIC


# --------------------------------------------------------------------------
# Craxlearn on its own: the learning half, without the job board
# --------------------------------------------------------------------------
# A school does not want a job board in front of its fourteen-year-olds, and
# a fourteen-year-old cannot lawfully be sold a subscription or shown to an
# employer. Both are true at once and they need different mechanisms, because
# they fail in different directions.
#
# The INSTITUTION switch is about what a place has bought. A school running
# Craxlearn on the board at the front of a classroom is running a teaching
# tool; the job board is not part of it and should not be reachable, by
# anybody there, at any age. Default off, because a default that has to be
# turned off is a default that will be found switched on somewhere.
#
# The AGE gate is about the individual and it is not negotiable by the
# institution. A coaching centre for working adults can turn the job side on
# for its learners; that still does not make it visible to a sixteen-year-old
# sitting in the room. The two are ANDed and the age gate is the harder of
# the two, always.
#
# And a deployment switch above both, for an institution running its own
# instance: with CRAXLEARN_ONLY set, the job half of the product does not
# exist on that server for anybody, including its admins.

MIN_JOB_AGE = 18

# Every route that belongs to the job board rather than to the learning
# product. Matched by prefix on the path, which is why this can be one list
# instead of a decorator on fifty endpoints — the endpoint that gets added
# next week is covered by being named like its neighbours, and the test that
# walks the live route table catches it if it is not.
JOB_SIDE = (
    "/api/jobs",       # the board itself: search, detail, categories
    "/api/job/",
    "/api/career",     # roles and their skills, counted from live postings
    "/api/resume",     # the builder, the parser, the ATS check
    "/api/apply",      # the autofill extension's pairing and profile
    "/api/interview",  # interview preparation for a role
    "/api/billing",    # a subscription is a thing sold to an adult
    "/api/employer",   # applying to become an employer
    "/api/hire",       # the hiring side: posting, searching candidates
    "/api/invites",    # employer introductions
    "/api/me/invites",
    "/api/me/open-to-work",
)

# Pages in the single-page app that belong to the same half. The server is
# what actually enforces this — hiding a sidebar item stops nobody who can
# type — but the client needs the same list so it does not offer a door that
# will not open.
JOB_PAGES = ("careers", "resume", "plans", "hiring", "track", "interview")


def is_job_side(path):
    """Is this request for the job board rather than for the learning tool?

    A plain prefix match, which is deliberately greedy: "/api/career" also
    catches a hypothetical "/api/careers-advice". That is the safe direction
    and the only one worth defaulting to. Over-matching closes something a
    school was never promised and somebody complains; under-matching opens
    the job board to a fourteen-year-old and nobody complains until it has
    been happening for a term.

    If a teaching route ever genuinely needs a name starting with one of
    these, rename the route. Do not add an exception here — an exception
    list is a second thing to keep right, and it will be wrong first.
    """
    p = str(path or "")
    return any(p.startswith(pre) for pre in JOB_SIDE)


def age_on(dob, today):
    """Whole years, counted the way an age is counted.

    A birthday that has not happened yet this year has not happened. Doing
    this with (today - dob).days / 365.25 puts somebody over the line up to
    a day early, which is a day of being shown to employers before it is
    lawful — small, and not the kind of small that is fine.
    """
    if dob is None or today is None:
        return None
    years = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        years -= 1
    return years


def adult(dob, today):
    """Old enough for the job side, and PROVEN so.

    An unknown date of birth is not proof. Used wherever the answer has to
    be positive: showing somebody to employers, selling them a subscription,
    or anything inside an institution.
    """
    got = age_on(dob, today)
    return got is not None and got >= MIN_JOB_AGE


def age_ok(dob, today, proof_required):
    """May this person reach the job side, on age alone?

    Two answers, and the difference is where children actually are.

    Inside an institution, `proof_required` is true and there is no way
    round it: a school hands us a room of teenagers and an empty birthday
    field is a teenager until it says otherwise.

    Outside one, an empty field is not evidence of a child. Every account
    on the open site was created by somebody accepting terms that say the
    paid product is for adults, and treating that silence as "under 18"
    would, on the day it shipped, take the job board, the resume builder
    and their own billing page away from every existing user without one
    of them having done anything. That is not a safety measure, it is an
    outage — and an outage teaches the next person to ship the gate loose.

    So outside an institution the rule is: a stated age is believed, in
    both directions, and silence keeps what it had. Somebody who tells us
    they are fifteen is fifteen.

    Set REQUIRE_DOB on a deployment that wants proof from everybody. It is
    off by default because turning it on locks out every existing account
    until each one comes back and fills in a date, and that is a decision
    with a support queue attached — it should be made deliberately, by
    somebody who has planned the email.
    """
    got = age_on(dob, today)
    if got is not None:
        return got >= MIN_JOB_AGE
    return not proof_required


# --------------------------------------------------------------------------
# What may be recorded about a learner
# --------------------------------------------------------------------------
# The kinds of activity worth keeping. Anything not on this list is not
# recorded, which is a shorter rule to audit than a list of exclusions.
RECORD_KINDS = ("ask", "board", "talk", "search", "sandbox", "lab", "network")

# The longest a recorded question is kept at. Not a privacy control on its
# own — a truncated question is still a question — but a question that runs
# to three hundred characters has stopped being a search and started being
# an essay, and storing the essay serves nobody.
MAX_RECORD = 200

# How many of a learner's own records to keep. Old ones are dropped rather
# than kept forever: the useful window for "what has this class been stuck
# on" is a term, not a lifetime, and data nobody reads is only a liability.
KEEP_PER_LEARNER = 200


def redact(text):
    """A recorded question, trimmed to what is worth keeping.

    Deliberately not an anonymiser. It does not attempt to strip names or
    addresses out of a question, because a redactor that half works is worse
    than none — it invites the record to be treated as anonymous when it is
    not. The record is personal data, it is stored as personal data, and the
    protection is the scope around it, not a regex.
    """
    t = " ".join(str(text or "").split())
    return t[:MAX_RECORD]


# --------------------------------------------------------------------------
# Where the answers come from
# --------------------------------------------------------------------------
# Every source of material that reaches a learner. `role` says what it is
# used for and `open` says whether it can be inspected and reused by anybody
# — which is the property an institution is really asking about when it asks
# where the content comes from.
#
# `role` is one of:
#   sourcing      the substance of an answer: facts, structures, pictures,
#                 the data a 2D or 3D view is built from, the material a
#                 sandbox exercise runs against
#   computation   arithmetic and algebra, checked rather than sourced
#
# Every sourcing entry is open, and tests/test_craxlearn.py asserts it. That
# assertion is the point of the table: adding a closed source for answer
# material takes a deliberate edit to a test that says, in words, why not.
SOURCES = (
    {"id": "pubchem", "name": "PubChem",
     "org": "US National Library of Medicine",
     "role": "sourcing", "open": True, "licence": "Public domain",
     "url": "https://pubchem.ncbi.nlm.nih.gov/",
     "used_for": "Measured atomic coordinates for molecules, and structural "
                 "formula images. Both the 3D view and the picture beside a "
                 "chemistry lesson."},
    {"id": "pdb", "name": "RCSB Protein Data Bank",
     "org": "RCSB / wwPDB",
     "role": "sourcing", "open": True, "licence": "CC0 1.0",
     "url": "https://www.rcsb.org/",
     "used_for": "Backbone coordinates for proteins and nucleic acids, "
                 "measured by crystallography, cryo-EM or NMR. The 3D "
                 "cartoon of a macromolecule."},
    {"id": "nasa", "name": "NASA image library",
     "org": "NASA",
     "role": "sourcing", "open": True, "licence": "Public domain",
     "url": "https://images.nasa.gov/",
     "used_for": "Photographs for astronomy, planetary science and earth "
                 "observation."},
    {"id": "wikimedia", "name": "Wikimedia Commons",
     "org": "Wikimedia Foundation",
     "role": "sourcing", "open": True,
     "licence": "CC BY / CC BY-SA / public domain, per file",
     "url": "https://commons.wikimedia.org/",
     "used_for": "Photographs for everything the other two do not cover. "
                 "Credited per file, because the licence requires it."},
    {"id": "tables", "name": "Craxlearn measured tables",
     "org": "In this repository",
     "role": "sourcing", "open": True,
     "licence": "Published values, cited in the source files",
     "url": "",
     "used_for": "Lattice constants, layer thicknesses, orbital distances "
                 "and periods, molar masses and balanced equations. The 3D "
                 "crystals, layer stacks and orbits, and every reaction the "
                 "practice lab simulates."},
    {"id": "packet", "name": "The packet engine",
     "org": "In this repository",
     "role": "sourcing", "open": True,
     "licence": "Computed from the rules on the page",
     "url": "",
     "used_for": "Every firewall and routing verdict in the network labs. "
                 "Longest-prefix matching and first-match rule evaluation, "
                 "computed the way a router computes them — so a dropped "
                 "packet has the actual reason, not a plausible one."},
    {"id": "sqlboard", "name": "The SQL practice database",
     "org": "In this repository",
     "role": "sourcing", "open": True,
     "licence": "Fixed tables, shipped with the site",
     "url": "",
     "used_for": "The rows every SQL sandbox query really runs against. The "
                 "same tables for everybody, so an exercise has one right "
                 "answer."},
    {"id": "phet", "name": "PhET Interactive Simulations",
     "org": "University of Colorado Boulder",
     "role": "sourcing", "open": True, "licence": "CC BY 4.0",
     "url": "https://phet.colorado.edu/",
     "used_for": "Interactive science and maths simulations a class can "
                 "drive on the board — build an atom, balance an equation, "
                 "wire a circuit. Embedded from PhET's own servers, never "
                 "copied, so what runs is the current published version."},
    # Recorded and honestly marked. Wolfram is not open, and it is not a
    # source: it is handed an expression and returns the result, which is
    # then explained. Nothing it returns is stored as institution material
    # and nothing about a learner is sent with it beyond the expression.
    # Listing it as not-open rather than leaving it out is the point — a
    # registry that only shows the flattering entries is not a registry.
    {"id": "wolfram", "name": "Wolfram|Alpha",
     "org": "Wolfram Research",
     "role": "computation", "open": False, "licence": "Proprietary, metered",
     "url": "https://www.wolframalpha.com/",
     "used_for": "Arithmetic and symbolic algebra, so a derivation is "
                 "checked against a computer algebra system rather than "
                 "against a language model's memory of one. Optional: "
                 "without a key the lesson is unchanged."},
)


# --------------------------------------------------------------------------
# PhET simulations
# --------------------------------------------------------------------------
# Candidates, not a catalogue. Every entry here is a simulation this file
# BELIEVES exists, and belief is not good enough to put in front of a class:
# a wrong id is a 404 in an iframe at the front of a room, mid-lesson, with
# thirty people watching.
#
# So nothing here is served until the server has actually fetched it and
# PhET has answered. An id that is wrong simply never appears, which means
# this list can be added to freely — the worst a mistake can do is nothing.
#
# PhET's URLs are stable and predictable:
#   https://phet.colorado.edu/sims/html/<id>/latest/<id>_en.html
# Embedded from their servers rather than copied, so a class always runs the
# current published version and the CC BY licence is satisfied by pointing
# at the original.
PHET_URL = "https://phet.colorado.edu/sims/html/{id}/latest/{id}_en.html"
PHET_PAGE = "https://phet.colorado.edu/en/simulations/{id}"

PHET_SIMS = (
    ("build-an-atom", "Build an Atom", "Chemistry"),
    ("states-of-matter-basics", "States of Matter", "Chemistry"),
    ("balancing-chemical-equations", "Balancing Chemical Equations", "Chemistry"),
    ("ph-scale-basics", "pH Scale", "Chemistry"),
    ("concentration", "Concentration", "Chemistry"),
    ("molecule-shapes", "Molecule Shapes", "Chemistry"),
    ("circuit-construction-kit-dc", "Circuit Construction Kit (DC)", "Physics"),
    ("forces-and-motion-basics", "Forces and Motion", "Physics"),
    ("energy-skate-park-basics", "Energy Skate Park", "Physics"),
    ("gravity-and-orbits", "Gravity and Orbits", "Physics"),
    ("projectile-motion", "Projectile Motion", "Physics"),
    ("wave-interference", "Wave Interference", "Physics"),
    ("density", "Density", "Physics"),
    ("ohms-law", "Ohm's Law", "Physics"),
    ("natural-selection", "Natural Selection", "Biology"),
    ("gene-expression-essentials", "Gene Expression", "Biology"),
    ("fractions-intro", "Fractions", "Mathematics"),
    ("graphing-lines", "Graphing Lines", "Mathematics"),
    ("area-model-multiplication", "Area Model Multiplication", "Mathematics"),
    ("trig-tour", "Trig Tour", "Mathematics"),
)


def phet_url(sim_id):
    return PHET_URL.format(id=sim_id)


def phet_page(sim_id):
    return PHET_PAGE.format(id=sim_id)


def phet_candidates(subject=""):
    """The list to check. Filtered by subject when one is asked for."""
    want = (subject or "").strip().lower()
    return tuple(
        {"id": i, "title": t, "subject": s,
         "url": phet_url(i), "page": phet_page(i)}
        for i, t, s in PHET_SIMS
        if not want or s.lower() == want)


def sourcing():
    """The sources answer material is drawn from. All open, by the rule."""
    return tuple(s for s in SOURCES if s["role"] == "sourcing")


def closed():
    """Anything in the registry that is not open, so it can be shown as such."""
    return tuple(s for s in SOURCES if not s["open"])


def public_registry():
    """The registry as an institution should see it: sorted, and honest.

    Open entries first because that is the answer to the question being
    asked, then anything closed, clearly marked. Not filtered — a
    procurement review that later finds an unlisted dependency has been
    given a reason to distrust the whole list.
    """
    rows = sorted(SOURCES, key=lambda s: (not s["open"], s["name"].lower()))
    return {
        "product": NAME,
        "policy": (
            "Answers, explanations, 2D diagrams, 3D models and sandbox "
            "material are sourced only from open sources, listed below with "
            "their licences. What a learner searched or asked is stored "
            "scoped to their institution and is never used to source anyone "
            "else's answer."),
        "sources": [dict(s) for s in rows],
        "open_count": sum(1 for s in SOURCES if s["open"]),
        "total": len(SOURCES),
    }
