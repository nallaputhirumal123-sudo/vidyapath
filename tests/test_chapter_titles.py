"""What a chapter is called, when the book's own PDF will not say plainly.

Reported from a live board: a teacher searched "rocket" in Search the
sources and got back three chapters named "How Forces Affect", "PHYSICS"
and "LIMITS AND DERIVATIVES". Two of those are not chapter names at all,
and the result read as broken even where the match was right — Newton's
third law IS where a rocket belongs.

The title is not cosmetic. It is indexed as searchable text, so a chapter
called "NIT" is both a worse label and a worse search: nothing matches it,
and whatever it should have matched now points somewhere else.

Four faults, all from how NCERT sets a page and how pdfplumber reads one:

  the drop cap    "CHAPTER FIVE" has a large decorative C, which the
                  extractor places elsewhere. What is left is "HAPTER IVE",
                  and "UNIT" becomes "NIT" — furniture that reads as
                  content, which is worse than furniture that reads as
                  furniture.

  the running head  the subject's name sits at the top of every page, so
                  chapters were titled "PHYSICS". A chapter is not called
                  Physics.

  the page number  set on the heading's own line: "INTRODUCTION TO
                  TRIGONOMETRY 113".

  the run-on      a heading continues onto a second line often enough that
                  there is a rule for it, and that rule swallowed the first
                  sentence of the chapter whenever it happened to open with
                  "In" or "To".
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import corpus                                      # noqa: E402

P, F = [], []


def ck(name, got, want):
    ok = got == want
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else
          "\n     got  " + repr(got) + "\n     want " + repr(want)),
          flush=True)
    (P if ok else F).append(name)


print("\nthe drop cap that the extractor lifts off")
ck("CHAPTER FIVE does not become the title",
   corpus.title_of("HAPTER IVE\nLAWS OF MOTION\n"
                   "In the preceding chapter we described"),
   "LAWS OF MOTION")
ck("nor does UNIT",
   corpus.title_of("NIT\nPHOTOSYNTHESIS IN HIGHER PLANTS\n"
                   "Green plants carry out photosynthesis"),
   "PHOTOSYNTHESIS IN HIGHER PLANTS")
ck("nor a numbered one",
   corpus.title_of("HAPTER 12\nTHERMODYNAMICS\nIn this chapter we shall"),
   "THERMODYNAMICS")

print("\nthe running head is not a chapter name")
ck("a chapter is not called Physics",
   corpus.title_of("PHYSICS\nSYSTEMS OF PARTICLES AND ROTATIONAL MOTION\n"
                   "In the earlier chapters"),
   "SYSTEMS OF PARTICLES AND ROTATIONAL MOTION")
ck("nor Mathematics",
   corpus.title_of("MATHEMATICS\nBINOMIAL THEOREM\nIn earlier classes"),
   "BINOMIAL THEOREM")

print("\nthe page number set on the heading's line")
ck("it is not part of the name",
   corpus.title_of("INTRODUCTION TO TRIGONOMETRY 113\n"
                   "There is perhaps nothing so"),
   "INTRODUCTION TO TRIGONOMETRY")

print("\na heading stops where the chapter starts")
ck("capitals do not run on into sentence case",
   corpus.title_of("LAWS OF MOTION\nIn the preceding chapter we described"),
   "LAWS OF MOTION")
ck("and nothing runs on into a finished sentence",
   corpus.title_of("Force and Pressure\nIn our daily life we come across."),
   "Force and Pressure")

print("\nand the headings that really do continue still do")
ck("two lines, sentence case",
   corpus.title_of("Mindful Eating: A Path\nto a Healthy Body\n"
                   "Food is essential"),
   "Mindful Eating: A Path to a Healthy Body")
ck("two lines, both in capitals",
   corpus.title_of("SOME APPLICATIONS OF\nTRIGONOMETRY\n"
                   "In the previous chapter"),
   "SOME APPLICATIONS OF TRIGONOMETRY")

print("\nand an ordinary chapter is left exactly alone")
ck("a normal heading",
   corpus.title_of("Light - Reflection and Refraction\n"
                   "We see a variety of objects"),
   "Light - Reflection and Refraction")
ck("a one-word chapter that is genuinely one word",
   corpus.title_of("MOTION\nIn everyday life we see some objects at rest"),
   "MOTION")
ck("a numbered heading loses only its number",
   corpus.title_of("3 Mindful Eating\nFood is essential to life"),
   "Mindful Eating")

if F:
    print("\n".join("FAIL " + x for x in F))
print("\nPASSED " + str(len(P)) + "   FAILED " + str(len(F)))
sys.exit(1 if F else 0)
