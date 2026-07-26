# Craxle Autofill — browser extension

Fills your details into a job application form you have already opened.
**It never submits anything.**

## Install it locally (for testing)

1. Open `chrome://extensions` in Chrome or Edge.
2. Turn on **Developer mode** (top right).
3. Click **Load unpacked** and choose this `extension/` folder.
4. Pin the extension so its icon is visible.

You need an `icon128.png` in this folder before Chrome will accept it — any
128×128 PNG will do for local testing.

## Connect it to your account

1. Sign in to Craxle and go to **Careers & jobs**.
2. Press **🔗 Connect extension**. A code appears, valid for 10 minutes.
3. Click the extension icon, type the code, press **Connect**.

The extension trades that code once for your profile and stores it in this
browser. After that it makes no network calls at all.

## Use it

Open a job application form, click the extension, press **Fill this form**.
Filled boxes flash green. File-upload boxes flash amber — browsers do not
allow an extension to attach your resume, so do that yourself.

Then **check every field and press the employer's own submit button.**

## How it is built, and why

**No AI, no tokens.** Field matching is deterministic label matching. An LLM
would cost money per form and would not be more accurate at deciding that
"First Name" means your first name.

**No session cookie ever reaches the extension.** The pairing code is
single-use and expires in 10 minutes. It buys a read-only profile — name,
email, phone, links, education. There is no token that can act as you, so a
compromised extension cannot log in as you or change your account.

**It only runs when you click.** There is no background script and no content
script registered against any site. The `activeTab` permission means the
filler is injected at the moment you press the button, into the tab you are
looking at, and never otherwise.

**It refuses more than it fills.** Every rule carries exclusions. "First Name"
will not fill "Referrer First Name"; "Email" will not fill "Confirm Email" or
"Emergency Contact Email"; "Phone" will not fill "Emergency Contact Phone". A
field that already has a value is left alone. When a form uses a layout it
cannot read, it fills nothing and says so rather than guessing.

**It cannot submit.** The code never calls `form.submit()`, never clicks a
button, and never dispatches Enter. This is a deliberate boundary, not an
oversight: submitting on someone's behalf puts their data in front of an
employer without them seeing it, breaks the terms of every applicant tracking
system, and gets real applicants blacklisted.

## If the domain changes

Two files: `SITE` at the top of `popup.js`, and `host_permissions` in
`manifest.json`. Both currently point at `craxle.com`, with the Railway URL
kept as a fallback so an extension paired before the move keeps working.
Reload the extension at `chrome://extensions` after editing either.

## Before publishing to the Chrome Web Store
- The store listing must include a privacy policy URL and declare what you
  collect. This extension stores the profile locally and transmits nothing
  after pairing — say exactly that.
- Expect review to focus on `scripting` + `activeTab`. Explaining that
  injection is user-gesture-only is usually what gets it through.
- Check the terms of the applicant tracking systems you expect users to
  encounter. Assisted form-filling where the human reviews and submits is
  ordinary browser behaviour, but some sites restrict automation, and that is
  your users' risk to understand.
