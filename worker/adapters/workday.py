"""Workday, which is 872 of the open postings here and none of the applies.

Every Workday tenant is a separate site with its own account:
mastercard.wd1.myworkdayjobs.com and adobe.wd5.myworkdayjobs.com share
nothing. So applying to 39 employers means 39 accounts, which is why this
one is different from the other six and why it was out of scope until now.

**The candidate makes the account.** This adapter never registers. Creating
an account accepts that employer's terms — a legal act in somebody's name —
and sends a verification email to their inbox. Both belong to the person.
So the worker gets as far as the sign-in page, finds no stored credential,
and stops with the employer's name; the row parks as `needs_login` until
they have made the account, verified it, and saved the sign-in.

**Then it never stops again for that employer.** Mastercard alone is 367 of
those 872. One setup, and the rest go through on their own — which is the
ratio that makes all of this worth a table and a migration.

What the sign-in does NOT do: it does not create, it does not reset a
password, and it does not click through anything a registration flow puts in
front of it. If the stored credentials do not work, it says so on the
account row and parks. A worker that guessed its way through an employer's
login would be indistinguishable from an attack on it.
"""
from .form import FormAdapter


class NeedsAccount(Exception):
    """This posting wants a login we do not hold for that site.

    Its own exception because it is not a failure: nothing is wrong, the
    candidate simply has not set that employer up yet. flow.py turns it into
    `needs_login`, which is a row waiting on a person, not a broken one.
    """

    def __init__(self, site, label=""):
        self.site = site
        self.label = label or site
        super().__init__(f"An account with {self.label} is needed first.")


class BadCredentials(Exception):
    """The stored sign-in was refused by the employer's site."""


class WorkdayAdapter(FormAdapter):
    source = "workday"

    # Workday is a slow React app behind a CDN; the default settle finds a
    # spinner and concludes the listing has closed.
    SETTLE_MS = 1800
    MAX_STEPS = 8

    APPLY_BUTTONS = ["a[data-automation-id='adventureButton']",
                     "button[data-automation-id='adventureButton']",
                     "a:has-text('Apply')", "button:has-text('Apply')"]
    APPLY_PATHS = ["/apply"]

    # Workday tags everything with data-automation-id, which is the one
    # stable thing about its markup across tenants and themes.
    SIGNIN_MARKS = ["[data-automation-id='signInFormo']",
                    "[data-automation-id='email']",
                    "input[data-automation-id='email']",
                    "button[data-automation-id='signInSubmitButton']",
                    "a[data-automation-id='createAccountLink']"]
    EMAIL_INPUTS = ["input[data-automation-id='email']",
                    "input[type=email]", "input[name='username']"]
    PASSWORD_INPUTS = ["input[data-automation-id='password']",
                       "input[type=password]"]
    SIGNIN_BUTTONS = ["button[data-automation-id='signInSubmitButton']",
                      "button:has-text('Sign In')",
                      "button:has-text('Sign in')"]

    FORMS = ["[data-automation-id='applyFlowPage']",
             "[data-automation-id='jobApplicationPage']", "form", "main"]
    FILE_INPUTS = ["input[data-automation-id='file-upload-input-ref']",
                   "input[type=file]"]
    NEXTS = ["button[data-automation-id='bottom-navigation-next-button']",
             "button:has-text('Save and Continue')",
             "button:has-text('Next')", "button:has-text('Continue')"]
    SUBMITS = ["button[data-automation-id='bottom-navigation-next-button']"
               ":has-text('Submit')",
               "button:has-text('Submit')"]
    CONFIRMS = ["thank you for applying", "your application was submitted",
                "application submitted", "we have received your application",
                "thank you for your interest"]

    async def at_signin(self, page) -> bool:
        return (await self._first_visible(page, self.SIGNIN_MARKS)) is not None

    async def open(self, page, url, account=None) -> None:
        """Reach the application form, signing in if the site asks.

        `account` is {username, password} or None. None at a sign-in page is
        NeedsAccount — a row for a person to act on — never an attempt to
        register, and never a guess at a password.
        """
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(self.SETTLE_MS)

        btn = await self._first_visible(page, self.APPLY_BUTTONS)
        if btn is not None:
            try:
                await btn.click(timeout=8000)
                await page.wait_for_timeout(self.SETTLE_MS)
            except Exception:
                pass

        if await self.at_signin(page):
            if not account or not account.get("username"):
                from main import ats_site_of
                raise NeedsAccount(ats_site_of(url),
                                   account.get("label") if account else "")
            await self.sign_in(page, account)

        if not await self._ready(page):
            raise RuntimeError(
                "No application form on that page — the listing has closed, "
                "or the link goes somewhere other than a posting.")

    async def sign_in(self, page, account) -> None:
        """Type the candidate's own credentials into the employer's form.

        Nothing here creates, resets or recovers anything. A refusal is
        reported and the row parks; it is never retried with a variation,
        because a worker trying passwords against an employer's login is an
        attack on it however good the intention.
        """
        em = await self._first_visible(page, self.EMAIL_INPUTS)
        pw = await self._first_visible(page, self.PASSWORD_INPUTS)
        if em is None or pw is None:
            raise BadCredentials("The sign-in form could not be read.")
        await em.fill(account["username"])
        await pw.fill(account["password"])
        go = await self._first_visible(page, self.SIGNIN_BUTTONS)
        if go is None:
            raise BadCredentials("No sign-in button on that page.")
        await go.click(timeout=15000)
        try:
            await page.wait_for_load_state("networkidle", timeout=30000)
        except Exception:
            pass
        await page.wait_for_timeout(self.SETTLE_MS)
        if await self.at_signin(page):
            # Still looking at the sign-in form: it was refused, or the
            # account exists but has never been verified.
            body = ""
            try:
                body = (await page.inner_text("body"))[:600].lower()
            except Exception:
                pass
            if "verif" in body:
                raise BadCredentials(
                    "That account has not been verified yet — open the email "
                    "from this employer and click the link, then try again.")
            raise BadCredentials(
                "That employer refused the sign-in. Check the email and "
                "password, or reset it on their site.")
