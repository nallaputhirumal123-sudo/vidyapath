"""What every ATS adapter has to be able to do, and nothing more.

Six methods, because six is what a form needs: get there, fill what is
knowable, resolve the questions that are not, attach the file, send it, and
say what came back. Each ATS differs in the selectors and in almost nothing
else, which is why the first adapter is the expensive one and the other five
are an afternoon.

Two rules that live here rather than in any one adapter:

**Nothing is guessed.** `fill` runs the same deterministic label matcher the
browser extension uses. `answers` resolves what is left against a table of
this candidate's own previous answers. Anything neither of those can settle
is returned, by name, to be asked of a person. There is no model in this
path and there must not be: the output is submitted to an employer over
somebody's real name, and a plausible invention is worse than a blank.

**Errors escape.** An adapter that catches its own exception and returns
quietly reports success and does nothing, which is strictly worse than
failing — the row goes to `submitted` with no application behind it. The
recorder in flow.py is the only place that catches.
"""
from dataclasses import dataclass, field


class Unconfirmed(Exception):
    """The form was sent and the page did not say so.

    Its own exception because the flow must treat it as the opposite of a
    failure. A failure is retried; this must never be, because "I clicked
    submit and could not read the response" and "I did not click submit" look
    identical from here, and retrying the first one applies to the same job
    twice under somebody's real name. The row is recorded as submitted,
    unconfirmed, and a person is told to check it.
    """


@dataclass
class FillResult:
    """What the deterministic filler managed.

    `filled` is the profile keys it recognised, which is the useful thing in
    a log: "it matched email and phone and nothing else" tells you the label
    reading went wrong far faster than a count does.
    """
    filled: list = field(default_factory=list)
    count: int = 0
    resume_uploads: int = 0


@dataclass
class Question:
    """One field on the form that is still empty and still wanted.

    `label` is the employer's own wording, kept verbatim, because it is what
    a person is going to be shown when the row parks. `norm` is that wording
    run through main.question_norm — the key the answer bank is under.
    """
    selector: str
    label: str
    norm: str
    kind: str = "text"          # text | textarea | select | radio | checkbox
    required: bool = False
    options: list = field(default_factory=list)


class Adapter:
    """The interface. Subclasses override; nothing here does real work.

    Deliberately not an ABC. A half-written adapter should fail loudly on the
    method it has not written yet, with the name of that method in the
    traceback, rather than fail at import with a list of everything missing.
    """

    source = ""

    async def open(self, page, url) -> None:
        """Get to the application form itself.

        Not just the posting. Most ATSs put the form on the same page below
        the description; some need a button pressed first. A board that has
        closed the listing is a real outcome and should raise.
        """
        raise NotImplementedError(f"{type(self).__name__}.open")

    async def fill(self, page, profile) -> FillResult:
        """Run the deterministic label matcher over the form."""
        raise NotImplementedError(f"{type(self).__name__}.fill")

    async def answers(self, page, bank) -> list:
        """Fill what the bank knows; return the questions it does not.

        `bank` is {normalised question: answer}. The return is a list of
        Question for everything still required and still empty — which is
        what parks the row and what a person is then asked.

        Optional blanks are NOT returned. Parking a row because an employer
        offered an optional "how did you hear about us" would park every row
        ever queued.
        """
        raise NotImplementedError(f"{type(self).__name__}.answers")

    async def attach(self, page, resume_path) -> None:
        """Put the resume on the form.

        A file input cannot be set from page script — browsers forbid it, and
        they are right to. It is done through the driver instead, which is
        the one thing the worker can do that the extension cannot.
        """
        raise NotImplementedError(f"{type(self).__name__}.attach")

    async def submit(self, page) -> str:
        """Send it, and return what the employer said back.

        The returned text is the only evidence the application landed. An
        adapter that returns "" has not confirmed anything and the row must
        not be recorded as confirmed.
        """
        raise NotImplementedError(f"{type(self).__name__}.submit")
