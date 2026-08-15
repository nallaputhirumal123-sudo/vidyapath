"""Recording the lesson, and the four things that must stay true about it.

A teacher works a derivation across four spaces and the board has no memory
of it. A screenshot keeps the end of the working and loses the order it was
arrived at, which on a derivation is the whole of the lesson. So the board
records its own screen.

**It goes to the board's disk and never to us.** The class shelf holds
twelve megabytes and its own comment says "a slide deck, not a film". An
hour of a lesson is hundreds, and posting that into a database row would be
an infrastructure decision wearing a feature's clothes. The file is asked
for before anything starts and written into as it goes, so memory stays flat
and a two-hour lesson weighs no more on the board than a two-minute one.

**The room is told, in words, for as long as it runs.** A screen recording
on a wall-mounted display is a camera pointed at a class. A button changing
colour is not disclosure — nobody at a desk can see a button on a board
eight feet away.

**The microphone is let go.** A board is a device in a room full of children
that nobody signs out of. A recording that ends without stopping its tracks
leaves the browser holding the microphone open, with the indicator on, until
somebody reloads the page.

**And the memory path stops itself.** Where a browser cannot write a file as
it goes — Chrome on Android, which is what a cheaper board runs — the whole
recording is held until the end. That path has a limit, because the failure
it prevents is a tab dying mid-lesson with nothing kept at all.
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

BOARD = io.open(os.path.join(ROOT, "craxlearn.html"), encoding="utf-8").read()
IDX = io.open(os.path.join(ROOT, "index.html"), encoding="utf-8").read()
# One implementation, in a file of its own.
#
# It was written into the board and only the board, so a teacher working on
# craxle.com — setting a paper, walking a class through a solved question,
# turning a structure around — could not record any of it, which is most of
# what they do at a desk. Two copies would have been two recorders that
# disagree about where the file went, the same reason mathtext.js exists.
REC = io.open(os.path.join(ROOT, "record.js"), encoding="utf-8").read()
P, F = [], []


def ck(name, cond, why=""):
    print(("PASS " if cond else "FAIL ") + name + (" — " + why if why else ""),
          flush=True)
    (P if cond else F).append(name)


print("\nthe button is on the board and wired to something")
ck("the board's top bar has it", 'id="recBtn"' in BOARD)
ck("and the website has one too", 'id="recFab"' in IDX,
   "setting a paper, or walking a class through a solved question, "
   "happens here rather than on the board")
ck("and pressing it does something",
   'el("recBtn").onclick' in BOARD and '#recFab' in IDX,
   "a button in the bar with no handler is the fault this board has had "
   "three times, and it fails silently every time")
ck("one button starts and stops",
   "recOn() ? recStop(\"\") : recStart()" in REC,
   "a board is operated mid-sentence; one button pressed again is easier "
   "to explain than two to choose between")
ck("and both screens press the same one",
   "Recorder.toggle()" in BOARD and "Recorder.toggle()" in IDX,
   "the recorder was on the board and only the board, so nothing a "
   "teacher did on the website could be recorded")
ck("each screen lends it a name for the file",
   "Recorder.attach" in BOARD and "Recorder.attach" in IDX,
   "a folder of craxlearn-1, craxlearn-2, craxlearn-3 sorts into nothing")
ck("and neither offers a button the browser cannot honour",
   "Recorder.supported()" in BOARD and "Recorder.supported()" in IDX,
   "an offer that fails when pressed is worse than no offer, and this is "
   "the first thing to go on an older board")
ck("it is hidden before anybody has signed in",
   "body.gated #recBtn" in BOARD)

print("\nthe room can see that it is recording")
ck("there is a notice, not just a coloured button", "#recPill" in REC)
ck("it says the word", ">Recording<" in REC.replace("</span>", "<"))
ck("it shows how long it has been running", 'class="rt"' in REC)
ck("and it can be stopped by tapping it",
   "pill.onclick" in REC and "recStop" in REC)
ck("the notice is removed when recording ends",
   "pill.remove()" in REC)

print("\nnothing is uploaded")
ck("the recording never posts to the class shelf",
   "board/file" not in REC and "bapi.send" not in REC,
   "the material limit is 12 MB and a lesson is hundreds; this is the "
   "board's own disk or nothing")
ck("it is written to the file as it goes where that is possible",
   "showSaveFilePicker" in REC and "createWritable" in REC,
   "holding an hour of video in memory is how a tab dies at the end of a "
   "lesson with nothing kept")
ck("writes are queued one behind another",
   "REC.queue = REC.queue.then" in REC,
   "two overlapping writes to one file interleave their bytes, and the "
   "recording will not play")
ck("and the file is closed before it is called saved",
   "await REC.queue" in REC and "sink.close()" in REC)

print("\nthe fallback path knows its own limit")
ck("there is a cap on what is held in memory", "REC_MEM_MS" in REC)
ck("it applies only when there is no file to write into",
   "REC.cap = sink ? 0 : REC_MEM_MS" in REC,
   "a recording streamed to disk has no reason to stop at fifteen minutes")
ck("reaching it saves rather than discards",
   "It has been saved" in REC)
ck("and a run away recording stops eventually", "REC_MAX_MS" in REC)

print("\nthe camera and the microphone are given back")
ck("the screen capture is stopped",
   "REC.view.getTracks().forEach" in REC and "t.stop()" in REC)
ck("the microphone is stopped too",
   "REC.mic.getTracks().forEach" in REC,
   "a board is a device in a room full of children that nobody signs out "
   "of, and a hot microphone stays hot until somebody reloads the page")
ck("the mixer is closed", "REC.ctx.close()" in REC)
ck("a refused microphone records the screen anyway",
   "mic = null;" in REC and "record the screen silently" in REC,
   "no microphone on the board is not a reason to lose the lesson")

print("\nand the ways it can end are all handled")
ck("the browser's own Stop sharing counts as stopping",
   'addEventListener("ended"' in REC,
   "the file is left unplayable if the recorder is not closed properly")
ck("cancelling the share picker is not an error",
   "cancelling the picker is not an error" in REC)
ck("cancelling the save dialog stops there",
   'e.name === "AbortError"' in REC)
ck("closing a screen mid-recording asks first",
   "beforeunload" in BOARD and "if(!Recorder.on()) return;" in BOARD)

print("\nthe file is named so it can be found again")
ck("it carries the subject and the date",
   "craxlearn-" in REC and "toISOString" in REC)
ck("and the extension matches what was actually recorded",
   'indexOf("mp4") >= 0 ? ".mp4" : ".webm"' in REC,
   "a webm named .mp4 is a file the school's own player refuses")
print("\nand it finishes exactly once, whatever ends it")
# Three ways in — the button, the notice, and the browser's own "Stop
# sharing" bar ending the track — and on a bad day two arrive together.
# The second one used to land on an already-finished recording and report
# "Nothing was recorded" over the line that said where the file went. A
# teacher who had just stopped a good recording would read the last
# sentence and believe they had lost it.
ck("finishing is guarded", "if(REC.ending) return;" in REC)
ck("and the guard is cleared when a new one starts",
   "REC.ending = false;" in REC)
ck("a stop with nothing running does not invent a failure",
   "if(REC.view || REC.sink || REC.chunks) recFinish();" in REC)


print("\n" + ("PASSED %d   FAILED %d" % (len(P), len(F))))
if F:
    for name in F:
        print("  FAILED: " + name)
    sys.exit(1)
