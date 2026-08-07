"""Every curriculum file is actually loaded, and every exercise actually runs.

Two faults found by writing one new track, and the second is destructive.

**A curriculum file that nobody loads.** The list of files to seed was
hard-coded in the startup path, and startup printed "curriculum files found:
[every .json in the folder]" immediately beside it — which reads as "these
are loaded" and means nothing of the kind. stage5.json was written,
committed and deployed, and the track in it simply did not exist. Nothing
errored.

**A repair button that deleted four tracks.** /api/admin/reload-curriculum
kept its OWN copy of the list, and that copy had drifted to six files. It
deletes every track before reseeding, so pressing it removed DSA, aptitude,
game development and cybersecurity and did not bring them back.

One list now, used by both, with a warning for any file holding tracks that
is not on it.

The rest of this file is about the content itself. An exercise ships a
starter, a solution and the output it should produce, and a solution whose
output does not match its own check is a lesson that marks a correct answer
wrong. They are all run.
"""
import io
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("JWT_SECRET", "t" * 40)
os.environ["DATABASE_URL"] = "sqlite:///./vidyapath.db"
os.environ["ALLOW_SQLITE"] = "1"
os.environ["JOBS_ENABLED"] = "0"
os.environ["COOKIE_SECURE"] = "0"

import main                                         # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P, F = [], []


def ck(n, c, d=""):
    print(("PASS " if c else "FAIL ") + n + (f" — {d}" if d else ""),
          flush=True)
    (P if c else F).append(n)


print("\nthere is one list of curriculum files, not two")
ck("it is declared once", hasattr(main, "CURRICULUM_FILES"))
names = [n for n, _, _ in main.CURRICULUM_FILES]
ck("stage5 is on it", "stage5.json" in names, str(names))
for must in ("school.json", "stage4.json", "curriculum.json",
             "placement.json", "gamedev.json", "cybersec.json"):
    ck(f"{must} is on it", must in names,
       "reload deletes every track first, so anything missing here is a "
       "track the repair button destroys")

src = io.open(os.path.join(ROOT, "main.py"), encoding="utf-8").read()
ck("startup uses the list rather than its own copy",
   "for name, aud, off in CURRICULUM_FILES" in src)
ck("and so does reload-curriculum",
   src.count("for name, aud, off in CURRICULUM_FILES") >= 2,
   str(src.count("for name, aud, off in CURRICULUM_FILES")))

print("\nand a file it does not know about is reported")
ck("there is a check for one", hasattr(main, "_unseeded_curriculum"))
ck("nothing is currently unloaded", main._unseeded_curriculum() == [],
   str(main._unseeded_curriculum()))
ck("and it would say so if there were",
   "curriculum files NOT loaded" in src,
   "silence here cost a whole track")

print("\nevery track file parses and has the shape the seeder expects")
for name, _aud, _off in main.CURRICULUM_FILES:
    path = os.path.join(ROOT, name)
    if not os.path.exists(path):
        ck(f"{name} exists", False, "listed but not on disk")
        continue
    try:
        data = json.loads(io.open(path, encoding="utf-8").read())
    except Exception as e:
        ck(f"{name} parses", False, f"{type(e).__name__}: {e}")
        continue
    tracks = data.get("tracks")
    ok = isinstance(tracks, list) and bool(tracks)
    ck(f"{name} holds tracks", ok, str(type(tracks)))
    if not ok:
        continue
    for t in tracks:
        has = all(k in t for k in ("id", "name", "lessons"))
        ck(f"  {t.get('name', '?')[:34]} has id, name and lessons", has)
        for l in t.get("lessons", []):
            if not all(k in l for k in ("id", "title")):
                ck(f"  lesson in {t.get('name')} has id and title", False,
                   str(l)[:60])

print("\nevery exercise solution produces the output its check expects")
# A solution that does not match its own check marks a right answer wrong,
# which is worse than having no exercise: the learner concludes they are
# wrong and the lesson is trusted less for everything after it.
checked = broken = 0
for name, _a, _o in main.CURRICULUM_FILES:
    path = os.path.join(ROOT, name)
    if not os.path.exists(path):
        continue
    data = json.loads(io.open(path, encoding="utf-8").read())
    for t in data.get("tracks", []):
        for l in t.get("lessons", []):
            for i, ex in enumerate(l.get("exercises") or []):
                # Older tracks store an exercise as a bare string. Nothing to
                # run and nothing to check — skipped, not a failure.
                if not isinstance(ex, dict):
                    continue
                want = (ex.get("check") or {}).get("lines")
                sol = ex.get("solution")
                # Only Python exercises with an exact expected output.
                if not want or not sol or l.get("lang") not in ("py", None):
                    continue
                checked += 1
                fh = tempfile.NamedTemporaryFile("w", suffix=".py",
                                                 delete=False,
                                                 encoding="utf-8")
                fh.write(sol)
                fh.close()
                try:
                    r = subprocess.run([sys.executable, fh.name],
                                       capture_output=True, text=True,
                                       timeout=25)
                    got = [x.strip() for x in r.stdout.strip().splitlines()
                           if x.strip()]
                finally:
                    os.unlink(fh.name)
                if r.returncode != 0 or got != [str(x) for x in want]:
                    broken += 1
                    ck(f"{l['id']} exercise {i + 1} runs and matches", False,
                       f"got {got}, want {want}")
ck(f"all {checked} runnable exercise solutions match their check",
   broken == 0, f"{broken} do not")

print("\nthe new Deep Learning track is real, not a stub")
dl = json.loads(io.open(os.path.join(ROOT, "stage5.json"),
                        encoding="utf-8").read())["tracks"][0]
ck("five lessons", len(dl["lessons"]) == 5, str(len(dl["lessons"])))
short = [l["title"] for l in dl["lessons"] if len(l.get("content", "")) < 2500]
ck("each carries real teaching, not a paragraph", not short, str(short))
thin = [l["title"] for l in dl["lessons"] if len(l.get("exercises") or []) < 5]
ck("each has exercises to type", not thin, str(thin))
noworks = [l["title"] for l in dl["lessons"] if not l.get("worksheet")]
ck("and questions to answer away from the screen", not noworks, str(noworks))

print("\n".join("FAIL " + x for x in F) if F else "")
print(f"\n{len(P)} passed, {len(F)} failed")
sys.exit(1 if F else 0)
