"""The other five no-login ATSs, which are selectors and nothing else.

Every one of these is a public page with a real form and no account: that is
why they are the ones automated. All the behaviour lives in FormAdapter; what
differs between them is where the form is, what the file input is called,
which button sends it and what the employer says back.

Kept in one file on purpose. Five twenty-line classes in five files is five
files to open when a board changes its markup, and they change in the same
way for the same reason. Greenhouse keeps its own file because it carries
the comments explaining the shared design.

Where a selector list looks over-long, it is covering more than one
generation of that board's markup at once — see FormAdapter's header.
"""
from .form import FormAdapter


class LeverAdapter(FormAdapter):
    """jobs.lever.co/<company>/<id> — the form is on /apply."""

    source = "lever"
    APPLY_PATHS = ["/apply"]
    # Lever splits the posting and the form across two URLs. The posting
    # carries a prominent Apply button; following it is how the form is
    # reached when somebody pastes the posting rather than the form.
    APPLY_BUTTONS = ["a.postings-btn", "a[href$='/apply']",
                     "a[href*='/apply']",
                     "a:has-text('Apply for this job')",
                     "a:has-text('Apply')"]
    FORMS = ["form[action*='apply']", ".application-form", "#application-form",
             ".content form", "form"]
    FILE_INPUTS = ["input[type=file][name='resume']",
                   "input[type=file][name*='resume' i]", "input[type=file]"]
    SUBMITS = ["#btn-submit", "button[type=submit]",
               "button:has-text('Submit application')",
               "input[type=submit]"]
    CONFIRMS = ["thank you for applying", "application submitted",
                "thanks for applying", "we'll be in touch"]


class AshbyAdapter(FormAdapter):
    """jobs.ashbyhq.com/<company>/<uuid> — a React app on one page.

    Nothing here is server rendered, so the form appears after the bundle
    runs rather than in the HTML. SETTLE_MS is longer for that reason: the
    default 400ms finds a page with no form on it and reports the listing
    closed, which is the most misleading failure this adapter could produce.
    """

    source = "ashby"
    SETTLE_MS = 1200
    # Ashby keeps the posting and the form on different URLs, and the form
    # carries no <form> element — see FormAdapter._ready. Measured: the
    # posting page has 0 fields, <posting>/application has 9 to 20.
    APPLY_PATHS = ["/application"]
    APPLY_BUTTONS = ["button:has-text('Apply for this Job')",
                     "button:has-text('Apply for this job')",
                     "a:has-text('Apply')"]
    FORMS = ["form", "[class*='applicationForm' i]", "[class*='_form' i]"]
    FILE_INPUTS = ["input[type=file][id*='resume' i]",
                   "input[type=file][name*='resume' i]", "input[type=file]"]
    SUBMITS = ["button:has-text('Submit Application')",
               "button:has-text('Submit application')",
               "button[type=submit]"]
    CONFIRMS = ["thanks for applying", "thank you for applying",
                "your application has been submitted",
                "application received"]


class WorkableAdapter(FormAdapter):
    """apply.workable.com/<company>/j/<id>/ — apply is a second step."""

    source = "workable"
    SETTLE_MS = 800
    APPLY_PATHS = ["/apply"]
    APPLY_BUTTONS = ["a[href*='/apply']",
                     "button:has-text('Apply for this job')",
                     "a:has-text('Apply for this job')",
                     "button:has-text('Apply')"]
    FORMS = ["form[data-ui='application-form']", "form#application_form",
             "main form", "form"]
    FILE_INPUTS = ["input[type=file][name*='resume' i]",
                   "input[type=file][accept*='pdf']", "input[type=file]"]
    SUBMITS = ["button[data-ui='submit-application']",
               "button:has-text('Submit application')",
               "button[type=submit]"]
    CONFIRMS = ["thank you for applying", "application has been submitted",
                "we received your application", "thanks for applying"]


class SmartRecruitersAdapter(FormAdapter):
    """jobs.smartrecruiters.com/<company>/<id>.

    The apply button says "I'm interested", which is worth naming: a
    selector list written from the other five would look for "Apply" and
    find nothing on every SmartRecruiters posting there has ever been.
    """

    source = "smartrecruiters"
    SETTLE_MS = 900
    APPLY_BUTTONS = ["button:has-text(\"I'm interested\")",
                     "a:has-text(\"I'm interested\")",
                     "button[data-test='application-form-button']",
                     "a[href*='apply']"]
    FORMS = ["form[data-test='application-form']", "#application-form",
             "main form", "form"]
    FILE_INPUTS = ["input[type=file][name*='resume' i]", "input[type=file]"]
    SUBMITS = ["button[data-test='submit-application']",
               "button:has-text('Submit application')",
               "button:has-text('Apply')", "button[type=submit]"]
    CONFIRMS = ["thank you for applying", "application submitted",
                "thanks for applying", "we have received your application"]


class RecruiteeAdapter(FormAdapter):
    """<company>.recruitee.com/o/<slug> — form on the posting itself."""

    source = "recruitee"
    APPLY_BUTTONS = ["a[href*='#apply']", "button:has-text('Apply')",
                     "a:has-text('Apply for this job')"]
    FORMS = ["form#job-application-form", "form[class*='application' i]",
             "main form", "form"]
    FILE_INPUTS = ["input[type=file][name*='cv' i]",
                   "input[type=file][name*='resume' i]", "input[type=file]"]
    SUBMITS = ["button[type=submit]", "button:has-text('Apply')",
               "input[type=submit]"]
    CONFIRMS = ["thank you", "we received your application",
                "application has been sent", "thanks for applying"]
