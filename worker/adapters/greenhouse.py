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
