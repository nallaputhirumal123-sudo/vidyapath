"""The model named in the settings, and what happens when it stops existing.

Google retires models. It has now done it twice to this site — first to
gemini-2.5-flash-lite, then to gemini-2.5-flash — and both times the same
three things went wrong together, so this is the test that holds all three.

**A withdrawn model 404s with a sentence nobody matched on.** "This model is
no longer available to new users. Please update your code" contains neither
"not found" nor "unknown model", which were the phrases the code looked for.
So the automatic fall back to the safe model never fired, and the failure was
sorted into the bucket for errors that match nothing — reported to the person
running the site as "Gemini could not be reached", which describes a network
fault. A working key, a working fallback, and an afternoon spent looking at
the wrong thing.

**The catalogue kept listing it.** /api/ai/models asked Google what the key
can use and got an entry for the model, so the one page built to answer
"can this key use this model" answered yes about a model that answered 404
to every call. Listed is not working, and it now tries the model rather than
trusting the list.

**And the default was a pinned version.** A pinned id is a dated default:
it works until a date nobody chose and then fails 404 on every request,
including on a fresh deployment that never touched the setting. The rolling
alias resolves to whatever the current model is, for any key. That note was
written the first time this happened and then not followed the second time,
so it is a test now rather than a comment.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import main                                            # noqa: E402

P, F = [], []


def ck(name, cond, why=""):
    print(("PASS " if cond else "FAIL ") + name + (" — " + why if why else ""),
          flush=True)
    (P if cond else F).append(name)


# Google's own words, from /api/ai/selftest on the day it happened.
RETIRED = RuntimeError(
    'gemini HTTP 404: {   "error": {     "code": 404,     "message": "This '
    'model models/gemini-2.5-flash is no longer available to new users. '
    'Please update your code to use a newer model for the latest features '
    'and improvements. We recommend you to use the Interactions API '
    '(https://ai.google.dev/gemini-api/docs/migrate-to-interactions)."')
BUSY = RuntimeError('gemini HTTP 503: {"error":{"code":503,"message":"The '
                    'model is overloaded. Please try again later."}}')
NOKEY = RuntimeError('gemini HTTP 400: {"error":{"message":"API key not '
                     'valid. Please pass a valid API key."}}')
STOPPED = RuntimeError("gemini stopped: MAX_TOKENS")

print("\na retired model is a missing model")
ck("the 404 is recognised", main._is_missing_model(RETIRED),
   "this is what makes the automatic fall back to the safe model fire; "
   "without it a working key sits there while the site reports an outage")
ck("so the fallback has somewhere to go",
   main._gemini_model()[1] and main._gemini_model()[1] != main.GEMINI_MODEL)
ck("and it is not called a network fault",
   main._one_provider_reason("gemini", RETIRED)[0] == "model",
   '"could not be reached" sends whoever reads it to check the internet')
ck("the words say what to do about it",
   "retired" in main._one_provider_reason("gemini", RETIRED)[1])
ck("and the user-facing message names the configuration, not the account",
   "site's own AI configuration"
   in main._ai_error_message(main.AIProvidersFailed([("gemini", RETIRED)])))

print("\nbusy is not broken, and broken is not busy")
ck("an overloaded model is worth asking twice", main._transient(BUSY))
ck("a retired one is not", not main._transient(RETIRED),
   "asking again changes nothing, and it costs a second and a half of a "
   "class's time to find that out")
ck("nor is a refused key", not main._transient(NOKEY))
ck("a busy model is described as busy",
   main._one_provider_reason("gemini", BUSY)[0] == "busy")

print("\na model that stopped early says why")
ck("MAX_TOKENS is reported as a length fault, on our side",
   main._one_provider_reason("gemini", STOPPED)[0] == "long")
ck("and not as a connection problem",
   "reached" not in main._one_provider_reason("gemini", STOPPED)[1])

print("\nthe default model is not a dated one")
ck("it is the rolling alias",
   main.GEMINI_MODEL.endswith("-latest")
   or bool(os.environ.get("GEMINI_MODEL")),
   "a pinned version is a default that fails 404 on a date nobody chose — "
   "it has happened twice, to 2.5-flash-lite and then to 2.5-flash")
ck("and it is not one of the retired ones",
   not re.match(r"^gemini-(?:1\.|2\.)", main.GEMINI_MODEL)
   or bool(os.environ.get("GEMINI_MODEL")))
ck("the safe fallback is an alias too",
   main.GEMINI_SAFE_MODEL.endswith("-latest"),
   "a fallback that can itself be retired is not a fallback")

print("\nthinking is only withheld where it was measured")
ck("the default keeps its thinking budget",
   not main._NO_THINKING.match("gemini-flash-latest"),
   "a budget is most of why a solved paper reasons before it answers; "
   "sweeping in every -latest alias threw it away on a guess")
ck("the alias that was actually measured does not",
   bool(main._NO_THINKING.match("gemini-flash-lite-latest")))
ck("and the old generations do not",
   bool(main._NO_THINKING.match("gemini-2.0-flash"))
   and bool(main._NO_THINKING.match("gemini-1.5-pro")))
ck("anything else is tried, and the retry catches a refusal",
   not main._NO_THINKING.match("gemini-3.5-flash")
   and main._rejects_thinking(RuntimeError("400 invalid argument")))

print("\nthe catalogue is not taken at its word")
import inspect                                          # noqa: E402
SRC = inspect.getsource(main.ai_models)
ck("/api/ai/models tries the model rather than listing it",
   "generateContent" in SRC and "current_works" in SRC,
   "it reported current_is_available: true for a model that 404s on every "
   "call, which is the answer that cost the afternoon")
ck("and reports what went wrong when it does not work",
   "current_error" in SRC)

print("\n" + ("PASSED %d   FAILED %d" % (len(P), len(F))))
if F:
    for name in F:
        print("  FAILED: " + name)
    sys.exit(1)
