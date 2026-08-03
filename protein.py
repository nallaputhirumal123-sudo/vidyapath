"""Proteins and nucleic acids in 3D, from crystallography.

The molecule renderer draws every atom as a sphere, which is right for
caffeine and useless for haemoglobin: four and a half thousand atoms arrive
as an indistinct ball, and the thing a student needs to see — that it is four
folded chains cradling four haem groups — is exactly what disappears.

So a macromolecule is drawn the way structural biology draws it: a trace
through the backbone. One point per residue, taken from the alpha carbon of
each amino acid or the phosphorus of each nucleotide, joined into a smooth
tube and coloured by chain. That is a cartoon, and it is the representation
every textbook uses, because the fold is the point.

The coordinates come from the Protein Data Bank — measured by X-ray
crystallography, cryo-EM or NMR, deposited by the labs that did the work.
Nothing here is drawn from a description.

Which structure to show is a curated decision for the classics. Searching the
PDB for "haemoglobin" returns 179 entries and the top hit is a mutant nobody
teaches; 1HHO is the human oxyhaemoglobin in every biochemistry course. The
search is still there for everything not on the list, so the coverage is the
whole bank rather than the list.
"""
import re

FILES = "https://files.rcsb.org/download/{}.pdb"
SEARCH = "https://search.rcsb.org/rcsbsearch/v2/query"

UA = "Craxle/1.0 (https://craxle.com; learning platform) python-httpx"
TIMEOUT = 12.0

# Enough residues to show a fold, few enough to send and to render. A trace is
# one point per residue, so this is generous — haemoglobin is 574.
MAX_POINTS = 1400
MAX_CHAINS = 8
MAX_BYTES = 6_000_000

# The structures that are actually taught, against the names people use for
# them. The PDB's own relevance ranking is tuned for researchers looking for
# the newest work, which is the opposite of what a lesson wants.
CANON = {
    "haemoglobin": "1HHO", "hemoglobin": "1HHO", "oxyhaemoglobin": "1HHO",
    "oxyhemoglobin": "1HHO", "deoxyhaemoglobin": "2HHB",
    "myoglobin": "1MBN",
    "insulin": "4INS",
    "lysozyme": "1LYZ",
    "dna": "1BNA", "b-dna": "1BNA", "double helix": "1BNA",
    "dna double helix": "1BNA", "z-dna": "2DCG",
    "trna": "1EHZ", "transfer rna": "1EHZ", "rna": "1EHZ",
    "ribosome": "4V6X",
    "collagen": "1CAG",
    "antibody": "1IGT", "immunoglobulin": "1IGT", "igg": "1IGT",
    "green fluorescent protein": "1EMA", "gfp": "1EMA",
    "trypsin": "2PTN", "chymotrypsin": "1YPH",
    "haemoglobin s": "2HBS", "sickle cell haemoglobin": "2HBS",
    "photosystem ii": "3WU2", "photosystem i": "1JB0",
    "rubisco": "1RCX",
    "atp synthase": "1E79",
    "potassium channel": "1BL8", "ion channel": "1BL8",
    "p53": "1TUP", "tumour suppressor p53": "1TUP",
    "prion": "1QM0",
    "amylase": "1SMD", "pepsin": "4PEP", "catalase": "1DGB",
    "ferritin": "1FHA", "actin": "1ATN", "myosin": "1B7T",
    "tubulin": "1TUB", "keratin": "3TNU", "ubiquitin": "1UBQ",
    "cytochrome c": "3CYT", "chlorophyll": "1JB0",
    "acetylcholinesterase": "1EA5", "dna polymerase": "1TAU",
    "reverse transcriptase": "1RTJ", "protease": "1HVR",
    "spike protein": "6VXX", "coronavirus spike": "6VXX",
}

# Chain colours, distinct at a glance and readable on a dark board.
CHAIN_COLOURS = [0x4FC3F7, 0xFFB74D, 0x81C784, 0xE57373,
                 0xBA68C8, 0x4DD0E1, 0xFFF176, 0xF06292]

_ID = re.compile(r"^[0-9][A-Za-z0-9]{3}$")

# Words that are never a macromolecule, so the bank is not asked about them.
_NOT = re.compile(
    r"\b(theorem|equation|algorithm|derivative|integral|matrix|"
    r"circuit|voltage|router|switch|kubernetes|python|javascript)\b", re.I)


def wanted(topic: str) -> bool:
    """Is this plausibly a macromolecule worth asking the PDB about?"""
    t = " ".join(str(topic or "").split())
    if not t or len(t) > 80 or _NOT.search(t):
        return False
    return bool(re.match(r"^[A-Za-z0-9][A-Za-z0-9 ,'()\-]*$", t))


def canonical(topic: str) -> str:
    """The taught structure for this topic, if there is one."""
    t = " ".join(str(topic or "").lower().split()).strip(" .?!")
    if _ID.match(t.upper()) and t.upper() in CANON.values():
        return t.upper()
    if t in CANON:
        return CANON[t]
    # "the structure of insulin", "insulin molecule"
    t2 = re.sub(r"\b(the|a|an|structure|of|molecule|protein|3d|model)\b",
                " ", t)
    t2 = " ".join(t2.split())
    return CANON.get(t2, "")


def parse_pdb(text: str) -> dict:
    """Backbone traces per chain from a PDB file, or an empty dict.

    ATOM records are fixed-column by specification and must be read that way:
    the residue name butts against the chain id, and splitting on whitespace
    merges fields in exactly the structures that matter.

    Only the first model is used. An NMR entry holds twenty or more
    conformations of the same molecule; drawing them all is a hairball.
    """
    chains, order = {}, []
    for line in str(text or "").splitlines():
        if line.startswith("ENDMDL"):
            break                                  # first model only
        if not line.startswith("ATOM"):
            continue
        if len(line) < 54:
            continue
        name = line[12:16].strip()
        # One point per residue: the alpha carbon of an amino acid, the
        # phosphorus of a nucleotide. Anything else is side chain or solvent.
        if name not in ("CA", "P"):
            continue
        alt = line[16]
        if alt not in (" ", "A"):
            continue                               # one alternate location
        chain = line[21].strip() or "A"
        try:
            x = float(line[30:38])
            y = float(line[38:46])
            z = float(line[46:54])
        except ValueError:
            continue
        if chain not in chains:
            if len(chains) >= MAX_CHAINS:
                continue
            chains[chain] = []
            order.append(chain)
        chains[chain].append([round(x, 2), round(y, 2), round(z, 2)])

    traces = [{"chain": c, "points": chains[c]} for c in order
              if len(chains[c]) >= 3]
    if not traces:
        return {}

    # Thin evenly if the structure is very large, keeping the ends. A trace
    # read every second residue still shows the fold; a browser asked for ten
    # thousand tube segments does not show anything.
    total = sum(len(t["points"]) for t in traces)
    if total > MAX_POINTS:
        keep = max(1, round(total / MAX_POINTS))
        for t in traces:
            pts = t["points"]
            t["points"] = pts[::keep] + ([pts[-1]] if len(pts) % keep else [])
        traces = [t for t in traces if len(t["points"]) >= 3]
        if not traces:
            return {}

    # Centre on the whole assembly so it turns about itself.
    allpts = [p for t in traces for p in t["points"]]
    cx = sum(p[0] for p in allpts) / len(allpts)
    cy = sum(p[1] for p in allpts) / len(allpts)
    cz = sum(p[2] for p in allpts) / len(allpts)
    span = 0.0
    for t in traces:
        moved = []
        for p in t["points"]:
            q = [round(p[0] - cx, 2), round(p[1] - cy, 2), round(p[2] - cz, 2)]
            span = max(span, abs(q[0]), abs(q[1]), abs(q[2]))
            moved.append(q)
        t["points"] = moved
    for i, t in enumerate(traces):
        t["color"] = CHAIN_COLOURS[i % len(CHAIN_COLOURS)]

    return {"traces": traces, "span": round(span or 1.0, 2),
            "residues": sum(len(t["points"]) for t in traces),
            "chains": len(traces)}


def title_of(text: str) -> str:
    """The structure's own name, from its TITLE records."""
    parts = [ln[10:].strip() for ln in str(text or "").splitlines()
             if ln.startswith("TITLE")]
    t = " ".join(" ".join(parts).split())
    return t[:120].title() if t else ""


async def _search(client, topic):
    """The PDB's best match for a name, as a 4-character id."""
    body = {"query": {"type": "terminal", "service": "full_text",
                      "parameters": {"value": str(topic)[:60]}},
            "return_type": "entry",
            "request_options": {"paginate": {"start": 0, "rows": 1}}}
    try:
        r = await client.post(SEARCH, json=body, timeout=TIMEOUT,
                              headers={"User-Agent": UA})
        if r.status_code != 200:
            return ""
        hits = (r.json() or {}).get("result_set") or []
    except Exception as e:
        print(f"PDB search failed for {topic!r}: {type(e).__name__}: {e}")
        return ""
    for h in hits:
        pid = str(h.get("identifier") or "").upper()
        if _ID.match(pid):
            return pid
    return ""


async def find(client, topic: str) -> dict:
    """A macromolecule's backbone in 3D, or nothing. Never raises."""
    if not wanted(topic):
        return {}
    pid = canonical(topic)
    if not pid:
        pid = await _search(client, topic)
    if not pid:
        return {}
    try:
        r = await client.get(FILES.format(pid), timeout=TIMEOUT,
                             headers={"User-Agent": UA})
        if r.status_code != 200:
            return {}
        text = r.text
        if len(text) > MAX_BYTES:
            text = text[:MAX_BYTES]
    except Exception as e:
        print(f"PDB fetch failed for {pid}: {type(e).__name__}: {e}")
        return {}

    out = parse_pdb(text)
    if out:
        out["pdb"] = pid
        out["title"] = title_of(text)
    return out


def clean(raw) -> dict:
    """Rebuild a structure from an untrusted dict, field by field."""
    if not isinstance(raw, dict):
        return {}
    traces = []
    for t in (raw.get("traces") or [])[:MAX_CHAINS]:
        if not isinstance(t, dict):
            continue
        pts = []
        for p in (t.get("points") or [])[:MAX_POINTS]:
            try:
                x, y, z = float(p[0]), float(p[1]), float(p[2])
            except (TypeError, ValueError, IndexError):
                continue
            if not all(abs(v) < 1e4 and v == v for v in (x, y, z)):
                continue
            pts.append([round(x, 2), round(y, 2), round(z, 2)])
        if len(pts) < 3:
            continue
        try:
            colour = int(t.get("color"))
        except (TypeError, ValueError):
            colour = CHAIN_COLOURS[len(traces) % len(CHAIN_COLOURS)]
        traces.append({"chain": str(t.get("chain") or "")[:4],
                       "points": pts,
                       "color": max(0, min(0xFFFFFF, colour))})
    if not traces:
        return {}
    try:
        span = float(raw.get("span") or 1.0)
    except (TypeError, ValueError):
        span = 1.0
    return {"traces": traces, "span": round(max(1.0, min(span, 1e4)), 2),
            "residues": sum(len(t["points"]) for t in traces),
            "chains": len(traces),
            "pdb": str(raw.get("pdb") or "")[:8],
            "title": str(raw.get("title") or "")[:120]}
