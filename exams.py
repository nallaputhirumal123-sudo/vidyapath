"""Past papers and entrance syllabuses — pointed at, not copied.

Two things a teacher and a candidate keep asking for, and they need opposite
treatment.

**Past papers we do not hold and will not host.** Every board owns the
copyright in its own question papers. The sites that pile them up by the
thousand are doing it without permission, and a school that buys a product
which quietly scrapes them inherits that. So this module holds no paper. It
holds the OFFICIAL place each paper is published, so a teacher picks board
and year and lands on the board's own page in one tap — which is also the
only copy that is certainly the real paper, correctly printed, with the
board's own corrections applied.

Each source says plainly what is actually there, because "past papers" means
three different things across these boards:

  free      the board publishes its real past papers openly
  specimen  the board publishes specimen or sample papers, not the sat ones
  login     papers exist but only for registered schools or paying candidates

A teacher who is told "specimen only" before clicking does not waste a free
period discovering it.

**Syllabuses we can state, because they are published to be stated.** An
entrance syllabus is a list of topics an authority publishes precisely so
candidates can study it. Repeating that list is the intended use, and it is
the thing every coaching centre in the country is asked for first.

What matters is the DIFFERENCE. A candidate already has the school books;
what they cannot see is which topics the exam adds on top of them. So each
unit is marked `extra` when the school corpus does not cover it, and that
flag is the product — the rest a learner already owns.

Nothing here is a promise about a particular year. Boards revise syllabuses,
and a list in a file goes stale silently. Every exam carries a link to the
authority's own syllabus document, said on screen, as the thing that settles
it.
"""

# --------------------------------------------------------------------------
# Where the real papers live.
#
# Deep links rot faster than domains — a board reorganises its site and a
# buried path 404s while the section it moved to is fine. So these point at
# the page the board keeps papers on, or its official site where it does not
# keep a stable one.
#
# Every host below was checked. The distinction that matters is DNS, not a
# response: a state board that resolves but refuses this machine is a board
# that geo-blocks or blocks non-browsers, and its site is fine for the
# teacher in Hyderabad who actually clicks it. A host with no DNS at all is
# simply wrong, and two were — tsche.ac.in went away when Telangana renamed
# the council to TGCHE, and Goa's board is on gov.in.
# --------------------------------------------------------------------------

SOURCES = [
    # ---- National boards -------------------------------------------------
    {"id": "cbse", "name": "CBSE", "kind": "national",
     "url": "https://www.cbse.gov.in/cbsenew/question-paper.html",
     "papers": "free",
     "note": "CBSE publishes the papers actually sat, by year and subject."},
    {"id": "cbse-sqp", "name": "CBSE sample papers", "kind": "national",
     "url": "https://cbseacademic.nic.in/", "papers": "specimen",
     "note": "The sample paper and marking scheme CBSE issues before each "
             "board exam, which is what the pattern for the year is read "
             "from."},
    {"id": "cisce", "name": "CISCE (ICSE and ISC)", "kind": "national",
     "url": "https://cisce.org/specimen-question-papers/",
     "papers": "specimen",
     "note": "CISCE publishes specimen papers openly. The sat papers go to "
             "registered schools."},
    {"id": "nios", "name": "NIOS", "kind": "national",
     "url": "https://www.nios.ac.in/online-course-material/question-papers"
            ".aspx",
     "papers": "free", "note": "Open schooling; past papers published free."},

    # ---- Entrance --------------------------------------------------------
    {"id": "jee-main", "name": "JEE Main", "kind": "entrance",
     "url": "https://jeemain.nta.nic.in/", "papers": "free",
     "note": "NTA publishes each session's question paper with the "
             "provisional answer key, per candidate response sheet."},
    {"id": "jee-adv", "name": "JEE Advanced", "kind": "entrance",
     "url": "https://jeeadv.ac.in/archive.html", "papers": "free",
     "note": "The archive carries past papers and answer keys back many "
             "years, which is the best free set of any exam here."},
    {"id": "neet", "name": "NEET UG", "kind": "entrance",
     "url": "https://neet.nta.nic.in/", "papers": "free",
     "note": "Question paper and answer key are released with each result "
             "cycle."},
    {"id": "ts-eapcet", "name": "TS EAPCET (EAMCET)", "kind": "entrance",
     # tsche.ac.in no longer resolves at all: Telangana renamed the council
     # TSCHE to TGCHE and the old host went with it. tgeapcet.nic.in is the
     # counselling site, which is a different thing and not where papers are.
     "url": "https://eapcet.tgche.ac.in/", "papers": "free",
     "note": "TSCHE publishes the question papers and keys for each shift "
             "after the exam."},
    {"id": "ap-eapcet", "name": "AP EAPCET (EAMCET)", "kind": "entrance",
     "url": "https://cets.apsche.ap.gov.in/EAPCET/", "papers": "free",
     "note": "APSCHE publishes papers and preliminary keys by shift."},

    # ---- State boards ----------------------------------------------------
    # Class 10 and Class 12 are separate authorities in most states, which is
    # why a state can appear twice. A teacher searching "Telangana" wants
    # both and should not have to know the acronym that splits them.
    {"id": "ts-ssc", "name": "Telangana SSC (Class 10)", "kind": "state",
     "state": "Telangana", "url": "https://bse.telangana.gov.in/",
     "papers": "free"},
    {"id": "ts-inter", "name": "Telangana Intermediate", "kind": "state",
     "state": "Telangana", "url": "https://tgbie.cgg.gov.in/",
     "papers": "free"},
    {"id": "ap-ssc", "name": "Andhra Pradesh SSC (Class 10)", "kind": "state",
     "state": "Andhra Pradesh", "url": "https://bse.ap.gov.in/",
     "papers": "free"},
    {"id": "ap-inter", "name": "Andhra Pradesh Intermediate", "kind": "state",
     "state": "Andhra Pradesh", "url": "https://bieap.apcfss.in/",
     "papers": "free"},
    {"id": "mh", "name": "Maharashtra HSC and SSC", "kind": "state",
     "state": "Maharashtra", "url": "https://mahahsscboard.in/",
     "papers": "free"},
    {"id": "tn", "name": "Tamil Nadu", "kind": "state", "state": "Tamil Nadu",
     "url": "https://dge.tn.gov.in/", "papers": "free"},
    {"id": "ka", "name": "Karnataka (KSEAB)", "kind": "state",
     "state": "Karnataka", "url": "https://kseab.karnataka.gov.in/",
     "papers": "free"},
    {"id": "kl", "name": "Kerala", "kind": "state", "state": "Kerala",
     "url": "https://keralapareekshabhavan.in/", "papers": "free"},
    {"id": "wb-10", "name": "West Bengal Madhyamik (Class 10)",
     "kind": "state", "state": "West Bengal",
     "url": "https://wbbse.wb.gov.in/", "papers": "free"},
    {"id": "wb-12", "name": "West Bengal Higher Secondary", "kind": "state",
     "state": "West Bengal", "url": "https://wbchse.wb.gov.in/",
     "papers": "free"},
    {"id": "up", "name": "Uttar Pradesh", "kind": "state",
     "state": "Uttar Pradesh", "url": "https://upmsp.edu.in/",
     "papers": "free"},
    {"id": "rj", "name": "Rajasthan", "kind": "state", "state": "Rajasthan",
     "url": "https://rajeduboard.rajasthan.gov.in/", "papers": "free"},
    {"id": "gj", "name": "Gujarat", "kind": "state", "state": "Gujarat",
     "url": "https://gseb.org/", "papers": "free"},
    {"id": "br", "name": "Bihar", "kind": "state", "state": "Bihar",
     "url": "https://biharboardonline.bihar.gov.in/", "papers": "free"},
    {"id": "mp", "name": "Madhya Pradesh", "kind": "state",
     "state": "Madhya Pradesh", "url": "https://mpbse.nic.in/",
     "papers": "free"},
    {"id": "od-10", "name": "Odisha (Class 10)", "kind": "state",
     "state": "Odisha", "url": "https://bseodisha.ac.in/", "papers": "free"},
    {"id": "od-12", "name": "Odisha Higher Secondary", "kind": "state",
     "state": "Odisha", "url": "https://chseodisha.nic.in/", "papers": "free"},
    {"id": "pb", "name": "Punjab", "kind": "state", "state": "Punjab",
     "url": "https://pseb.ac.in/", "papers": "free"},
    {"id": "hr", "name": "Haryana", "kind": "state", "state": "Haryana",
     "url": "https://bseh.org.in/", "papers": "free"},
    {"id": "as", "name": "Assam (SEBA)", "kind": "state", "state": "Assam",
     "url": "https://sebaonline.org/", "papers": "free"},
    {"id": "jh", "name": "Jharkhand", "kind": "state", "state": "Jharkhand",
     "url": "https://jac.jharkhand.gov.in/", "papers": "free"},
    {"id": "cg", "name": "Chhattisgarh", "kind": "state",
     "state": "Chhattisgarh", "url": "https://cgbse.nic.in/",
     "papers": "free"},
    {"id": "uk", "name": "Uttarakhand", "kind": "state",
     "state": "Uttarakhand", "url": "https://ubse.uk.gov.in/",
     "papers": "free"},
    {"id": "hp", "name": "Himachal Pradesh", "kind": "state",
     "state": "Himachal Pradesh", "url": "https://hpbose.org/",
     "papers": "free"},
    {"id": "jk", "name": "Jammu and Kashmir", "kind": "state",
     "state": "Jammu and Kashmir", "url": "https://jkbose.nic.in/",
     "papers": "free"},
    {"id": "goa", "name": "Goa", "kind": "state", "state": "Goa",
     "url": "https://gbshse.gov.in/", "papers": "free"},

    # ---- International ---------------------------------------------------
    # Said honestly. Cambridge and the IB both sell their papers, and a
    # teacher should learn that here rather than after ten minutes of
    # clicking.
    {"id": "cambridge", "name": "Cambridge (IGCSE, AS and A Level)",
     "kind": "international",
     "url": "https://www.cambridgeinternational.org/", "papers": "login",
     "note": "Past papers are released to registered centres through the "
             "school support site. A few specimen papers are public."},
    {"id": "ib", "name": "International Baccalaureate", "kind": "international",
     "url": "https://www.ibo.org/", "papers": "login",
     "note": "IB past papers are sold through the IB store; they are not "
             "published free."},
    {"id": "edexcel", "name": "Pearson Edexcel", "kind": "international",
     "url": "https://qualifications.pearson.com/en/support/support-topics/"
            "exams/past-papers.html",
     "papers": "free",
     "note": "Pearson publishes past papers and mark schemes openly, which "
             "is unusual among the international boards."},
]

BY_ID = {s["id"]: s for s in SOURCES}


def _hay(s):
    return " ".join(str(s.get(k, "")) for k in
                    ("name", "state", "kind", "id", "note")).lower()


def search(q="", kind=""):
    """Official sources matching a teacher's words.

    Matched on every word, so "telangana intermediate" narrows and does not
    widen — a teacher typing more expects fewer results, and a search that
    grows as you type reads as broken.
    """
    want = [w for w in str(q or "").lower().split() if w]
    kind = str(kind or "").strip().lower()
    out = []
    for s in SOURCES:
        if kind and s.get("kind") != kind:
            continue
        hay = _hay(s)
        if all(w in hay for w in want):
            out.append(dict(s))
    return out


# --------------------------------------------------------------------------
# Entrance syllabuses.
#
# `extra: True` marks a unit the school books do not cover — the whole reason
# a candidate reads one of these rather than just carrying on with Class 12.
# --------------------------------------------------------------------------

_JEE_MATHS = [
    ("Sets, relations and functions", False),
    ("Complex numbers and quadratic equations", False),
    ("Matrices and determinants", False),
    ("Permutations and combinations", False),
    ("Binomial theorem", False),
    ("Sequences and series", False),
    ("Limits, continuity and differentiability", False),
    ("Integral calculus", False),
    ("Differential equations", False),
    ("Coordinate geometry — straight lines, circles, conic sections", False),
    ("Three dimensional geometry", False),
    ("Vector algebra", False),
    ("Statistics and probability", False),
    ("Trigonometry, including inverse trigonometric functions", False),
]

_JEE_PHYSICS = [
    ("Units, dimensions and measurement", False),
    ("Kinematics", False),
    ("Laws of motion", False),
    ("Work, energy and power", False),
    ("Rotational motion", False),
    ("Gravitation", False),
    ("Properties of solids and liquids", False),
    ("Thermodynamics and kinetic theory of gases", False),
    ("Oscillations and waves", False),
    ("Electrostatics and current electricity", False),
    ("Magnetic effects of current and magnetism", False),
    ("Electromagnetic induction and alternating currents", False),
    ("Electromagnetic waves", False),
    ("Optics — ray and wave", False),
    ("Dual nature of matter and radiation", False),
    ("Atoms and nuclei", False),
    ("Electronic devices — semiconductors, diodes, transistors", False),
    ("Experimental skills — the prescribed practical list", True),
]

_JEE_CHEM = [
    ("Some basic concepts in chemistry", False),
    ("Atomic structure", False),
    ("Chemical bonding and molecular structure", False),
    ("Chemical thermodynamics", False),
    ("Solutions", False),
    ("Equilibrium — ionic and chemical", False),
    ("Redox reactions and electrochemistry", False),
    ("Chemical kinetics", False),
    ("Classification of elements and periodicity", False),
    ("p-block elements", False),
    ("d- and f-block elements", False),
    ("Coordination compounds", False),
    ("Purification and characterisation of organic compounds", False),
    ("Basic principles of organic chemistry", False),
    ("Hydrocarbons", False),
    ("Organic compounds containing halogens, oxygen, nitrogen", False),
    ("Biomolecules", False),
    ("Principles of practical chemistry — the prescribed experiments", True),
]

EXAMS = [
    {
        "id": "jee-main",
        "name": "JEE Main",
        "who": "National Testing Agency",
        "syllabus_url": "https://jeemain.nta.nic.in/",
        "note": "The unit list NTA publishes. It is revised — NTA has both "
                "added and dropped units in recent years — so the linked "
                "document is what settles any disagreement, not this page.",
        "built_on": "The NCERT Class 11 and 12 Physics, Chemistry and Maths "
                    "books, which are held here in full.",
        "subjects": [
            {"name": "Mathematics", "units": _JEE_MATHS},
            {"name": "Physics", "units": _JEE_PHYSICS},
            {"name": "Chemistry", "units": _JEE_CHEM},
        ],
    },
    {
        "id": "jee-adv",
        "name": "JEE Advanced",
        "who": "The IIT conducting it that year",
        "syllabus_url": "https://jeeadv.ac.in/",
        "note": "Same subjects as JEE Main and a different exam. The "
                "syllabus overlaps heavily; the depth, the question style "
                "and the marking do not, and that difference is not "
                "something a topic list can show you. Work the archive of "
                "past papers — it is public and it is the real measure.",
        "built_on": "The same NCERT Class 11 and 12 books, taken further.",
        "subjects": [
            {"name": "Mathematics", "units": _JEE_MATHS},
            {"name": "Physics", "units": _JEE_PHYSICS},
            {"name": "Chemistry", "units": _JEE_CHEM},
        ],
    },
    {
        "id": "eapcet",
        "name": "EAMCET / EAPCET",
        "who": "TSCHE for Telangana, APSCHE for Andhra Pradesh",
        "syllabus_url": "https://eapcet.tsche.ac.in/",
        # This is the single most useful true thing about EAMCET and it is
        # usually buried: it is not a separate syllabus. A candidate who
        # knows this stops buying a second set of books.
        "note": "EAPCET is set on the Intermediate first and second year "
                "syllabus of the state's own board — it is not a separate "
                "syllabus. A candidate teaching themselves Intermediate "
                "Physics, Chemistry, Maths or Biology properly is already "
                "covering it. What the exam adds is speed and a "
                "multiple-choice paper, not new topics.",
        "built_on": "The Intermediate first and second year books, which "
                    "run the same content as NCERT Class 11 and 12.",
        "subjects": [
            {"name": "Mathematics (Engineering stream)",
             "units": _JEE_MATHS},
            {"name": "Physics", "units": _JEE_PHYSICS[:-1]},
            {"name": "Chemistry", "units": _JEE_CHEM[:-1]},
            {"name": "Botany and Zoology (Agriculture and Medical stream)",
             "units": [
                 ("Diversity in the living world", False),
                 ("Structural organisation in plants and animals", False),
                 ("Cell structure and function", False),
                 ("Plant physiology", False),
                 ("Human physiology", False),
                 ("Reproduction in plants and humans", False),
                 ("Genetics and evolution", False),
                 ("Biology in human welfare", False),
                 ("Biotechnology", False),
                 ("Ecology and environment", False),
             ]},
        ],
    },
    {
        "id": "neet",
        "name": "NEET UG",
        "who": "National Testing Agency",
        "syllabus_url": "https://neet.nta.nic.in/",
        "note": "Biology carries half the paper — 90 of the 180 questions — "
                "and it is the half candidates from a Maths background "
                "underestimate.",
        "built_on": "The NCERT Class 11 and 12 Biology, Physics and "
                    "Chemistry books, held here in full.",
        "subjects": [
            {"name": "Physics", "units": _JEE_PHYSICS[:-1]},
            {"name": "Chemistry", "units": _JEE_CHEM[:-1]},
            {"name": "Biology (Botany and Zoology)", "units": [
                ("Diversity in the living world", False),
                ("Structural organisation in plants and animals", False),
                ("Cell structure and function", False),
                ("Plant physiology", False),
                ("Human physiology", False),
                ("Reproduction", False),
                ("Genetics and evolution", False),
                ("Biology and human welfare", False),
                ("Biotechnology and its applications", False),
                ("Ecology and environment", False),
            ]},
        ],
    },
]

EXAM_BY_ID = {e["id"]: e for e in EXAMS}


def syllabus(exam_id):
    """One exam's syllabus as the API returns it, or None.

    Units come out as objects rather than the tuples above, so a renderer
    never has to know which slot the flag is in.
    """
    got = EXAM_BY_ID.get(str(exam_id or "").strip().lower())
    if not got:
        return None
    out = dict(got)
    out["subjects"] = [
        {"name": s["name"],
         "units": [{"unit": u, "extra": bool(x)} for u, x in s["units"]],
         # Counted, not stated, so it cannot drift from the list beside it.
         "extra": sum(1 for _, x in s["units"] if x)}
        for s in got["subjects"]
    ]
    return out


def exam_list():
    """Enough of each exam to draw the chooser, without the unit lists."""
    return [{"id": e["id"], "name": e["name"], "who": e["who"],
             "subjects": [s["name"] for s in e["subjects"]],
             "units": sum(len(s["units"]) for s in e["subjects"])}
            for e in EXAMS]
