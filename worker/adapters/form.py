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


async def _inject(page, name):
    """Run one of our scripts in the page, CSP or no CSP.

    Deliberately NOT page.add_script_tag: that injects a <script> element,
    which a Content-Security-Policy header is entitled to refuse — and Ashby
    does, with "Executing inline script violates the following Content
    Security Policy directive". Every Ashby application failed on that line,
    after the adapter had correctly found the form.

    evaluate() goes through the debugger protocol rather than the DOM, so
    the page's CSP does not apply to it. Wrapped in a function body because
    these files are statements, not an expression.
    """
    await page.evaluate("() => {" + _js(name) + "}")


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
    # Moving to the next page of a form that has several. Deliberately does
    # NOT include anything that might be the send button: SUBMITS is checked
    # first and a page offering both is treated as the last one.
    NEXTS = ["button:has-text('Next')", "button:has-text('Continue')",
             "button:has-text('Save and continue')",
             "button:has-text('Save & Continue')",
             "a:has-text('Next')",
             "[data-automation-id='bottom-navigation-next-button']"]
    # A form with more pages than this is not a form, it is a wizard that has
    # gone wrong, and clicking Next forty times on somebody's behalf is worse
    # than stopping.
    MAX_STEPS = 8
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

    # Some boards put the application on its own URL. Tried first, and only
    # used if it actually produces fields — Ashby's is <posting>/application,
    # and Greenhouse's equivalent 404s, so this has to be attempted rather
    # than assumed.
    APPLY_PATHS = []

    def alternates(self, url):
        """Other URLs that might carry this posting's form, in order.

        Suffixes by default — Ashby's /application, Lever's /apply. An
        adapter overrides this when the alternative is not a suffix, which
        Greenhouse's is not.
        """
        return [url.rstrip("/") + s for s in self.APPLY_PATHS]

    async def _fields(self, page):
        """How many things on this page can be filled in."""
        try:
            return await page.locator(
                "input:not([type=hidden]):not([type=submit])"
                ":not([type=button]),select,textarea").count()
        except Exception:
            return 0

    async def _ready(self, page):
        """Is there an application form here — by fields, not by tag.

        The original test was "does a <form> element exist", and it is wrong
        for most of the modern boards. Measured against real listings: Ashby
        renders twenty inputs and two file pickers with NO <form> element at
        all, because it POSTs through fetch. That check reported "the listing
        has probably closed" on every Ashby posting there is, which was a
        confident lie about a page that was working perfectly.
        """
        if await self._fields(page) >= 3:
            return True
        return (await self._first(page, self.FORMS)) is not None

    async def open(self, page, url) -> None:
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(self.SETTLE_MS)

        # Already on the form?
        if await self._ready(page):
            return

        # Other places this board keeps the form.
        for target in self.alternates(url):
            try:
                r = await page.goto(target, wait_until="domcontentloaded",
                                    timeout=45000)
                await page.wait_for_timeout(self.SETTLE_MS)
                if (r is None or r.status < 400) and await self._ready(page):
                    return
            except Exception:
                continue
        # Back to the posting, then try whatever button it offers.
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(self.SETTLE_MS)
        except Exception:
            pass
        btn = await self._first(page, self.APPLY_BUTTONS)
        if btn is not None:
            try:
                await btn.click(timeout=5000)
                await page.wait_for_timeout(self.SETTLE_MS + 600)
            except Exception:
                pass            # an anchor that only scrolls; carry on
        if not await self._ready(page):
            raise RuntimeError(
                "No application form on that page — the listing has closed, "
                "or the link goes to a careers index rather than a posting.")

    async def fill(self, page, profile) -> FillResult:
        await _inject(page, "filler.js")
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
        from main import question_norm, apply_option_mode

        await _inject(page, "probe.js")
        fields = await page.evaluate("() => window.__vpAsk()") or []
        missing = []
        for f in fields:
            label = (f.get("label") or "").strip()
            norm = question_norm(label)
            # What this field may fall back to when the answer matches none
            # of its options. "none" on a legal declaration, so those park.
            mode = apply_option_mode(norm)
            answer = bank.get(norm) if norm else None
            if answer:
                ok = await page.evaluate(
                    "([s, v, mo]) => window.__vpSet(s, v, mo)",
                    [f.get("selector"), answer, mode])
                if ok:
                    continue
                # The bank had an answer and the field would not take it —
                # usually a select whose options changed. A question for a
                # person, not a silent skip.
            if not f.get("required"):
                continue
            # About to park. If this is a required dropdown that offers an
            # honest way out — "Prefer not to say" on a demographic
            # question, "Other" on a harmless one — take it rather than
            # stopping the whole application on a box the person cannot
            # usefully fill either. Legal declarations get mode "none" and
            # fall through to park, which is the point of the split.
            if mode != "none" and (f.get("options") or []):
                took = await page.evaluate(
                    "([s, mo]) => { const el = document.querySelector(s);"
                    " if (!el) return false;"
                    " const ts = el.tagName === 'SELECT'"
                    "   ? [...el.options].map(o => o.textContent) : [];"
                    " if (!ts.length) return false;"
                    " const i = window.__vpPick(ts, mo);"
                    " if (i < 0) return false;"
                    " el.value = el.options[i].value;"
                    " el.dispatchEvent(new Event('input', {bubbles: true}));"
                    " el.dispatchEvent(new Event('change', {bubbles: true}));"
                    " return true; }",
                    [f.get("selector"), mode])
                if took:
                    continue
            missing.append(Question(
                selector=f.get("selector") or "",
                label=label or "A question on the form we could not read",
                norm=norm, kind=f.get("kind") or "text",
                required=True, options=list(f.get("options") or [])))
        return missing

    async def _first_visible(self, page, selectors):
        """The first selector that resolves to something a person can see.

        Distinct from _first, which counts hidden elements too — and must,
        because a styled file upload is nearly always a hidden input behind
        a pretty button.

        For BUTTONS the opposite is true, and getting it wrong is subtle: a
        three-page form has all three pages in the DOM at once with two of
        them display:none, so the submit button on the last page exists from
        the moment the first page loads. Counting it made the adapter believe
        page one was the last page, so it never pressed Next and every
        multi-page form stopped after its first screen.
        """
        for sel in selectors:
            try:
                nodes = page.locator(sel)
                for i in range(min(await nodes.count(), 8)):
                    node = nodes.nth(i)
                    if await node.is_visible():
                        return node
            except Exception:
                continue
        return None

    async def at_last_step(self, page) -> bool:
        """Is this the page with the send button on it?

        Checked before Next, always. A page offering both is the last one —
        some boards keep a disabled Next beside an enabled Submit — and
        clicking Next there would walk past the thing we came to do.
        """
        return (await self._first_visible(page, self.SUBMITS)) is not None

    async def next_step(self, page) -> bool:
        """Advance one page. False when there is nowhere left to go.

        Never clicks anything on the last page. This is the only method that
        presses a button the candidate did not see, so it is kept as narrow
        as it can be: no Next while a Submit exists, no Next that is itself
        disabled, and no Next that leaves the page looking identical.
        """
        if await self.at_last_step(page):
            return False
        btn = await self._first_visible(page, self.NEXTS)
        if btn is None:
            return False
        try:
            if not await btn.is_enabled():
                return False
        except Exception:
            pass
        before = await self._signature(page)
        try:
            await btn.click(timeout=10000)
        except Exception:
            return False
        await page.wait_for_timeout(self.SETTLE_MS + 700)
        # A Next that changed nothing is a validation error we cannot see,
        # and clicking it again forever is the one failure mode a loop like
        # this must not have.
        return (await self._signature(page)) != before

    async def _signature(self, page):
        """Enough of the page to tell whether pressing Next did anything.

        VISIBLE fields only. A wizard keeps every page in the DOM and toggles
        display, so a signature built from all of them is identical on every
        page — Next was pressed, nothing appeared to change, and the walk
        stopped after the first screen believing it had hit a validation
        error it could not see.
        """
        try:
            return await page.evaluate(
                "() => location.href + '|' + "
                "[...document.querySelectorAll('input,select,textarea')]"
                ".filter(e => e.offsetParent !== null)"
                ".map(e => e.id || e.name || '').join(',')")
        except Exception:
            return ""

    async def attach(self, page, resume_path) -> None:
        node = await self._first(page, self.FILE_INPUTS)
        if node is None:
            raise RuntimeError("No resume upload on that form.")
        await node.set_input_files(resume_path)
        # These boards show the filename once they have taken it. Give the
        # upload a moment rather than racing straight into submit.
        await page.wait_for_timeout(1200)

    async def submit(self, page) -> str:
        node = (await self._first_visible(page, self.SUBMITS)
                or await self._first(page, self.SUBMITS))
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
