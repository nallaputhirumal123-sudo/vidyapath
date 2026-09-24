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
import re

from .form import FormAdapter


class GreenhouseAdapter(FormAdapter):
    source = "greenhouse"

    FORMS = ["#application_form", "form#application-form",
             "form[action*='applications']", "#grnhse_app form",
             "main form", "form"]
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
    CONFIRMS = ["thank you for applying",
                "your application has been submitted",
                "application submitted", "thanks for applying"]

    # token and job id out of a posting URL: /<token>/jobs/<id>
    _PARTS = re.compile(r"greenhouse\.io/(?:embed/)?([^/]+)/jobs/(\d+)")

    def alternates(self, url):
        """Greenhouse's embed endpoint, which always serves the raw form.

        Many boards redirect their posting URL to the company's own careers
        site — boards.greenhouse.io/stripe/jobs/7962437 lands on
        stripe.com/careers/listing/... which renders no form at all, so the
        adapter reported the listing closed on a posting that was open and
        taking applications.

        The embed URL is the form itself, whatever the company has done with
        their careers page. Measured: stripe 62 fields and 2 file inputs,
        samsara 50, coinbase 48. A posting that really has gone still 404s
        here, which is the answer we want in that case.

        Tried AFTER the posting URL, never instead of it: when the posting
        does serve its own form that is the page the employer intended, and
        it carries the description and any board-specific questions.
        """
        out = super().alternates(url)
        hit = self._PARTS.search(url or "")
        if hit:
            token, jid = hit.group(1), hit.group(2)
            out.append("https://boards.greenhouse.io/embed/job_app"
                       f"?for={token}&token={jid}")
        return out
