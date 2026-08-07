"""What a coaching centre teaches, and which of our books cover it.

A school says "Class 9". A coaching centre says "MPC", "BiPC", "NEET",
"JEE" — a GROUP, which is a bundle of subjects across the two intermediate
years, and the thing a parent is actually buying. Asking such a centre to
pick "Class 11 Physics" and then "Class 12 Physics" and then "Class 11
Chemistry" is asking them to translate their own product into ours.

So the groups are written down here, each mapped to the books we hold. Two
rules kept this honest and both matter more than the mapping itself:

**Nothing here claims a syllabus we do not have.** Every group carries the
books that back it AND the subjects that nothing in the corpus covers, and
`coverage()` reports the second as plainly as the first. A centre told
"Commerce is not covered" can decide; a centre shown a confident empty
result finds out in front of a class.

**These are the BOOKS, not the exam.** NCERT Physics is what JEE and NEET are
built on and it is not the same thing as a JEE syllabus — the exam adds
topics, changes the weighting, and is set by somebody else. Saying "NEET
group" means "the NCERT books NEET is drawn from", and the wording that
reaches a customer says exactly that.
"""

# The books the corpus actually holds, as they are titled in it.
SCIENCE_6_10 = [f"Class {c} Science" for c in (6, 7, 8, 9, 10)]
MATHS_6_10 = [f"Class {c} Mathematics" for c in (6, 7, 8, 9, 10)]

PHYSICS_11_12 = ["Class 11 Physics", "Class 12 Physics"]
CHEMISTRY_11_12 = ["Class 11 Chemistry", "Class 12 Chemistry"]
BIOLOGY_11_12 = ["Class 11 Biology", "Class 12 Biology"]
MATHS_11_12 = ["Class 11 Mathematics", "Class 12 Mathematics"]

# The commerce and civics stream. Business Studies is Class 12 only: NCERT
# publishes no Class 11 Business Studies PDF under any code that answers, so
# it is not claimed here and stays named as missing below.
ECONOMICS_11_12 = ["Class 11 Economics", "Class 12 Economics"]
ACCOUNTANCY_11_12 = ["Class 11 Accountancy", "Class 12 Accountancy"]
BUSINESS_12 = ["Class 12 Business Studies"]
CIVICS_11_12 = ["Class 11 Political Science", "Class 12 Political Science"]


GROUPS = [
    {
        "id": "mpc",
        "name": "MPC",
        "long": "Maths, Physics, Chemistry",
        "note": "Intermediate first and second year. The usual route to "
                "engineering entrance.",
        "books": MATHS_11_12 + PHYSICS_11_12 + CHEMISTRY_11_12,
        "missing": [],
    },
    {
        "id": "bipc",
        "name": "BiPC",
        "long": "Biology, Physics, Chemistry",
        "note": "Intermediate first and second year. The usual route to "
                "medical entrance.",
        "books": BIOLOGY_11_12 + PHYSICS_11_12 + CHEMISTRY_11_12,
        "missing": [],
    },
    {
        "id": "mec",
        "name": "MEC",
        "long": "Maths, Economics, Commerce",
        "note": "Maths, Economics and Accountancy are covered by the NCERT "
                "books, and Business Studies for second year. NCERT "
                "publishes no first-year Business Studies book.",
        "books": MATHS_11_12 + ECONOMICS_11_12 + ACCOUNTANCY_11_12
                 + BUSINESS_12,
        "missing": ["Class 11 Business Studies"],
    },
    {
        "id": "cec",
        "name": "CEC",
        "long": "Civics, Economics, Commerce",
        "note": "Civics is the NCERT Political Science books, and Economics "
                "and Commerce the Economics, Accountancy and second-year "
                "Business Studies ones. NCERT publishes no first-year "
                "Business Studies book.",
        "books": CIVICS_11_12 + ECONOMICS_11_12 + ACCOUNTANCY_11_12
                 + BUSINESS_12,
        "missing": ["Class 11 Business Studies"],
    },
    {
        "id": "jee",
        "name": "JEE",
        "long": "Engineering entrance — the NCERT books it is drawn from",
        "note": "The NCERT Physics, Chemistry and Maths that JEE is built "
                "on. Not a JEE syllabus: the exam adds topics and sets its "
                "own weighting.",
        "books": PHYSICS_11_12 + CHEMISTRY_11_12 + MATHS_11_12,
        "missing": [],
    },
    {
        "id": "neet",
        "name": "NEET",
        "long": "Medical entrance — the NCERT books it is drawn from",
        "note": "The NCERT Biology, Physics and Chemistry that NEET is "
                "built on. Not a NEET syllabus: the exam sets its own "
                "weighting, and Biology carries half the paper.",
        "books": BIOLOGY_11_12 + PHYSICS_11_12 + CHEMISTRY_11_12,
        "missing": [],
    },
    {
        "id": "foundation",
        "name": "Foundation",
        "long": "Classes 6 to 10, Maths and Science",
        "note": "What a centre teaches before the group is chosen, and what "
                "school tuition covers.",
        "books": MATHS_6_10 + SCIENCE_6_10,
        "missing": [],
    },
]

BY_ID = {g["id"]: g for g in GROUPS}


def held(con):
    """The set of books the corpus actually contains, read from it.

    Read rather than assumed. A list in this file that says we hold Class 12
    Biology when the ingestion missed it is worse than no list: it is a
    promise made to a coaching centre that the product then breaks.
    """
    try:
        rows = con.execute("select distinct title from passages").fetchall()
    except Exception:
        return set()
    return {str(r[0] or "").split(":")[0].strip() for r in rows}


def coverage(con, group_id=None):
    """Each group, with what is behind it and what is not.

    `passages` is the honest measure of "is this actually usable" — a book
    present with nine passages in it did not ingest properly, and a centre
    should see that number rather than a tick.
    """
    have = held(con)
    counts = {}
    try:
        for title, n in con.execute(
                "select title, count(*) from passages group by title"):
            book = str(title or "").split(":")[0].strip()
            counts[book] = counts.get(book, 0) + n
    except Exception:
        counts = {}

    out = []
    for g in GROUPS:
        if group_id and g["id"] != group_id:
            continue
        books = []
        for b in g["books"]:
            books.append({"book": b, "present": b in have,
                          "passages": counts.get(b, 0)})
        ready = [b for b in books if b["present"]]
        out.append({
            "id": g["id"], "name": g["name"], "long": g["long"],
            "note": g["note"],
            "books": books,
            "passages": sum(b["passages"] for b in books),
            # Whole, part, or nothing. A centre reads this word and decides;
            # a percentage invites an argument about the denominator.
            #
            # A subject we KNOW is not covered counts against this, and used
            # not to. `state` was computed from the books listed for the group
            # and ignored g["missing"] entirely — so MEC, which names
            # Economics, Commerce and Accountancy as absent in its own
            # definition, reported "ready" because the Maths books it does
            # have were all present. That is the exact thing this field exists
            # to prevent: a centre reads one word, buys, and finds out in
            # front of a class. A group that cannot teach part of its own
            # stream is at best partial.
            "state": ("ready" if books and len(ready) == len(books)
                      and not g["missing"]
                      else "partial" if ready else "none"),
            "missing": list(g["missing"]) + [b["book"] for b in books
                                             if not b["present"]],
        })
    return out
