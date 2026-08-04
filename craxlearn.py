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
