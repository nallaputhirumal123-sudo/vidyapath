# VidyaPath — Changelog

The version number lives in the `VERSION` file. It appears in the app footer,
the admin panel, `/api/status`, and the deployment logs — so you can always
tell which build Railway is actually running.

**Bump it every time you push.** Then compare the number on your live site
with this file. If they differ, Railway has not deployed your latest code.

Format: MAJOR.MINOR.PATCH
- **PATCH** — bug fix, typo, small correction
- **MINOR** — new lessons, new feature
- **MAJOR** — something that breaks or replaces existing behaviour

---

## 1.4.0 — Vidya presenter

- Full-body animated presenter with gesturing arms, breathing and blinking
- 18-line spoken guided tour of the whole course, using live lesson counts
- Tour buttons on the landing page, dashboard and study guide
- Version tracking added — visible in app, admin, `/api/status` and logs

## 1.3.0 — Mathematics for AI

- New Maths track: linear algebra, statistics, probability, calculus
  (4 lessons, 32 exercises, all computed by hand in runnable code)
- Honest Roadmap page mapping all 80+ requested topics
- Daily challenge on the dashboard — same exercise for everyone each day
- Totals: 45 lessons, 289 exercises, 360 written questions

## 1.2.0 — Themes and admin recovery

- Light and dark themes with a toggle, remembered per device
- Admin bootstrap fixed: `ADMIN_PASSWORD` now resets the password on boot
  (previously it only worked when creating a brand-new account)
- `/api/status` diagnostic endpoint, with emails masked
- One-click "Reload curriculum from files" button in the admin panel
- Static file route added — `tutor.js` was silently returning HTML

## 1.1.0 — Gamification and landing page

- Landing page with hero, features, six-stage outline and FAQ
- XP, levels and streaks — computed from records, never stored
- Per-stage printable certificates
- Mobile drawer navigation, larger touch targets, no input auto-zoom
- Fixed: AI Engineering track was invisible due to a stage key mismatch

## 1.0.0 — Full curriculum and platform

- Six stages, 41 lessons: beginner → Python → SQL → data → ML → AI → career
- Every exercise auto-graded and verified to pass its own grader
- Vidya tutor with browser speech and contextual guidance
- Printable worksheets with teacher answer keys
- FastAPI backend, Postgres, admin panel with drop-off analytics
- Single-file study guide that works offline
