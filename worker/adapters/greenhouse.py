"""Greenhouse. The first adapter, and the only one in this slice.

Chosen first because it is the most common ATS in the crawl and because it
needs no candidate account — the form is a plain form on a public page, the
file input is a real `input[type=file]`, and the confirmation is text on the
page afterwards. Everything the other five need is the same shape with
different selectors, which is why they are mechanical once this one works.

Selectors are ordered candidate lists rather than single strings. Greenhouse
serves at least three generations of markup — the classic `#application_form`
board, the newer `job-boards.greenhouse.io` React embed, and the
`grnhse_app` iframe embedded on a company's own careers page. Taking the
first selector that actually resolves is how one adapter covers all three
without branching on a version it cannot reliably detect.
"""
import os

from .base import Adapter, FillResult, Question, Unconfirmed

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _js(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return fh.read()


class GreenhouseAdapter(Adapter):
    source = "greenhouse"

    # The form itself. If none of these resolve, the page is not an
    # application form — usually because the listing has closed and
    # Greenhouse served the "no longer accepting applications" page.
    FORMS = ["#application_form", "form#application-form",
             "form[action*='applications']", "#grnhse_app form",
             "main form", "form"]

    # Some boards hide the fields behind an "Apply for this job" button.
    APPLY_BUTTONS = ["a[href='#app']", "#apply_button",
                     "button:has-text('Apply for this job')",
                     "a:has-text('Apply for this job')"]

    FILE_INPUTS = ["input[type=file]#resume",
                   "input[type=file][name='resume']",
                   "input[type=file][id*='resume' i]", "input[type=file]"]

    SUBMITS = ["#submit_app", "input[type=submit]",
               "button[type=submit]",
               "button:has-text('Submit application')",
               "button:has-text('Submit Application')"]

    # What Greenhouse says when it has taken the application. Matched
    # case-insensitively against the page text after submitting.
    CONFIRMS = ["thank you for applying",
                "your application has been submitted",
                "application submitted", "thanks for applying"]

    async def _first(self, page, selectors):
        for sel in selectors:
            try:
                node = page.locator(sel).first
                if await node.count() > 0:
                    return node
            except Exception:
                # A selector this Playwright build cannot parse (`:has-text`
                # on an old version) is not a reason to abandon the row —
                # try the next one. A selector that parses and matches
                # nothing is handled by the count check above.
                continue
        return None

    async def open(self, page, url) -> None:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        btn = await self._first(page, self.APPLY_BUTTONS)
        if btn is not None:
            try:
                await btn.click(timeout=4000)
            except Exception:
                pass            # an anchor that scrolls; the form is there
        form = await self._first(page, self.FORMS)
        if form is None:
            raise RuntimeError(
                "No application form on that page — the listing has probably "
                "closed.")
        await page.wait_for_timeout(300)

    async def fill(self, page, profile) -> FillResult:
        await page.add_script_tag(content=_js("filler.js"))
        got = await page.evaluate("(p) => window.__vpFill(p)", profile)
        got = got or {}
        return FillResult(filled=list(got.get("filled") or []),
                          count=int(got.get("count") or 0),
                          resume_uploads=int(got.get("resumeUploads") or 0))

    async def answers(self, page, bank) -> list:
        """Fill what this candidate has answered before; report the rest.

        The bank is keyed by the normalised question, and normalising is done
        in one place — main.question_norm — so the key written by the API and
        the key read here cannot drift apart.
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
                # usually a select whose options changed. That is a question
                # for a person, not a silent skip.
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
        # Greenhouse shows the filename once it has taken it. Give the
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
        body = ""
        try:
            body = (await page.inner_text("body"))[:4000]
        except Exception:
            body = ""
        low = body.lower()
        for phrase in self.CONFIRMS:
            if phrase in low:
                # The employer's own words back, trimmed to the line that
                # carries them. "Submitted" with no evidence is exactly the
                # lie this whole feature must not tell.
                for line in body.splitlines():
                    if phrase in line.lower():
                        return line.strip()[:400]
                return phrase
        # Not a RuntimeError. The click happened; only the reading of the
        # response failed, and retrying would apply to the same job twice.
        raise Unconfirmed(
            "Sent, but the page did not confirm it. Worth checking this one "
            "by hand before assuming it went.")
