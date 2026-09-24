"""The parts of driving an application form that no ATS disagrees about.

Greenhouse was the expensive one. Writing the second adapter made it obvious
that nothing in it was about Greenhouse except four lists of selectors and a
handful of phrases — the rest is: find the form, run the deterministic label
matcher, resolve what is left against this candidate's own answers, put the
file on the file input, click, and read back what the employer said.

So that is here, once, and an ATS is a subclass with selectors. Five of the
six are about twenty lines each. If a later one needs more than selectors it
overrides the method; that is what subclasses are for and it is not a defeat.

Selectors are ORDERED LISTS, never single strings. Every one of these serves
more than one generation of markup at the same time — a classic server
rendered board, a React embed, an iframe on the company's own careers page —
and taking the first selector that actually resolves covers all of them
without branching on a version that cannot be reliably detected.
"""
import os

from .base import Adapter, FillResult, Question, Unconfirmed

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _js(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return fh.read()


class FormAdapter(Adapter):
    """Everything except the selectors."""

    source = ""

    # The application form itself. Failing to find any of these means the
    # page is not a form — nearly always because the listing has closed.
    FORMS = ["form"]
    # Some boards keep the fields behind a button or a second page.
    APPLY_BUTTONS = []
    FILE_INPUTS = ["input[type=file]"]
    SUBMITS = ["button[type=submit]", "input[type=submit]"]
    # Matched case-insensitively against the page text after submitting. The
    # only evidence an application landed.
    CONFIRMS = ["thank you for applying", "application submitted",
                "thanks for applying", "your application has been submitted",
                "we have received your application",
                "we received your application"]
    # Waited for after pressing an apply button, before looking for the form.
    SETTLE_MS = 400

    async def _first(self, page, selectors):
        for sel in selectors:
            try:
                node = page.locator(sel).first
                if await node.count() > 0:
                    return node
            except Exception:
                # A selector this Playwright build cannot parse is not a
                # reason to abandon the row — try the next. One that parses
                # and matches nothing is handled by the count check.
                continue
        return None

    async def open(self, page, url) -> None:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        btn = await self._first(page, self.APPLY_BUTTONS)
        if btn is not None:
            try:
                await btn.click(timeout=5000)
                await page.wait_for_timeout(self.SETTLE_MS)
            except Exception:
                pass            # an anchor that only scrolls; carry on
        form = await self._first(page, self.FORMS)
        if form is None:
            raise RuntimeError(
                "No application form on that page — the listing has probably "
                "closed, or the link goes to a careers index rather than to "
                "a posting.")
        await page.wait_for_timeout(self.SETTLE_MS)

    async def fill(self, page, profile) -> FillResult:
        await page.add_script_tag(content=_js("filler.js"))
        got = await page.evaluate("(p) => window.__vpFill(p)", profile) or {}
        return FillResult(filled=list(got.get("filled") or []),
                          count=int(got.get("count") or 0),
                          resume_uploads=int(got.get("resumeUploads") or 0))

    async def answers(self, page, bank) -> list:
        """Fill what this candidate has answered before; report the rest.

        The bank is keyed by the normalised question, and normalising happens
        in one place — main.question_norm — so the key the API writes and the
        key read here cannot drift apart.
        """
        from main import question_norm          # one normaliser, not two

        await page.add_script_tag(content=_js("probe.js"))
        fields = await page.evaluate("() => window.__vpAsk()") or []
        missing = []
        for f in fields:
            label = (f.get("label") or "").strip()
            norm = question_norm(label)
            answer = bank.get(norm) if norm else None
            if answer:
                ok = await page.evaluate(
                    "([s, v]) => window.__vpSet(s, v)",
                    [f.get("selector"), answer])
                if ok:
                    continue
                # The bank had an answer and the field would not take it —
                # usually a select whose options changed. A question for a
                # person, not a silent skip.
            if not f.get("required"):
                continue
            missing.append(Question(
                selector=f.get("selector") or "",
                label=label or "A question on the form we could not read",
                norm=norm, kind=f.get("kind") or "text",
                required=True, options=list(f.get("options") or [])))
        return missing

    async def attach(self, page, resume_path) -> None:
        node = await self._first(page, self.FILE_INPUTS)
        if node is None:
            raise RuntimeError("No resume upload on that form.")
        await node.set_input_files(resume_path)
        # These boards show the filename once they have taken it. Give the
        # upload a moment rather than racing straight into submit.
        await page.wait_for_timeout(1200)

    async def submit(self, page) -> str:
        node = await self._first(page, self.SUBMITS)
        if node is None:
            raise RuntimeError("No submit button on that form.")
        await node.click(timeout=15000)
        try:
            await page.wait_for_load_state("networkidle", timeout=25000)
        except Exception:
            pass                # a single-page confirmation never idles
        try:
            body = (await page.inner_text("body"))[:4000]
        except Exception:
            body = ""
        low = body.lower()
        for phrase in self.CONFIRMS:
            if phrase in low:
                # The employer's own words back, trimmed to the line that
                # carries them. "Submitted" with invented evidence is exactly
                # the lie this feature must not tell.
                for line in body.splitlines():
                    if phrase in line.lower():
                        return line.strip()[:400]
                return phrase
        # Not a RuntimeError. The click happened; only the reading of the
        # response failed, and retrying would apply to the same job twice.
        raise Unconfirmed(
            "Sent, but the page did not confirm it. Worth checking this one "
            "by hand before assuming it went.")
