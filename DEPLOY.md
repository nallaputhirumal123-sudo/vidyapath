# VidyaPath — launch on Railway

Complete deployment guide. Total time: about 20 minutes, most of it waiting for builds.

---

## What you're deploying

| File | Purpose |
|---|---|
| `main.py` | FastAPI backend — auth, progress, admin API |
| `index.html` | Student platform (login-gated) |
| `admin.html` | Admin dashboard |
| `curriculum.json` | Seed content — loaded into the DB on first boot |
| `Dockerfile` | Build instructions for Railway |
| `railway.json` | Railway build/deploy config |
| `requirements.txt` | Python dependencies |
| `curriculum.js`, `convert.js` | Source of the seed data — not needed at runtime, keep for editing |

---

## Step 0 — Test it locally first

Do not skip this. Finding a bug on your laptop takes seconds; finding it on Railway takes ten minutes per attempt.

```bash
cd vidyapath

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt

# Local admin account + insecure local cookie setting
export ADMIN_EMAIL="you@example.com"
export ADMIN_PASSWORD="pick-a-strong-one"
export COOKIE_SECURE=0             # Windows PowerShell: $env:COOKIE_SECURE=0

uvicorn main:app --reload
```

Open **http://localhost:8000**

- Create a student account → confirm you land in the platform
- Open a Python lesson → click **Run Python** → wait ~10s for the runtime → confirm the lab grades itself
- Refresh the page → confirm your progress survived
- Open **http://localhost:8000/admin** → sign in with `ADMIN_EMAIL` → confirm the dashboard loads

`COOKIE_SECURE=0` is required locally because `localhost` is not HTTPS. On Railway you leave it unset, so cookies stay secure.

A file called `vidyapath.db` will appear — that's local SQLite. It's in `.gitignore` and never gets deployed.

---

## Step 1 — Push to GitHub

```bash
git init
git add .
git commit -m "VidyaPath initial"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/vidyapath.git
git push -u origin main
```

**Before you push, confirm `.gitignore` contains `.env` and `*.db`.** Committing secrets to a public repo is the single most common and most expensive launch mistake.

---

## Step 2 — Create the Railway project

1. Go to **railway.app** → sign in with GitHub
2. **New Project** → **Deploy from GitHub repo**
3. Authorise Railway and pick your `vidyapath` repo
4. Railway detects `Dockerfile` and starts building immediately

The first build takes 2–4 minutes. It will likely **fail or crash-loop** at this point — that's expected, because there's no database yet. Continue to step 3.

---

## Step 3 — Add Postgres

This is the step people skip, and it's why their data vanishes on every redeploy.

1. In your project canvas: **+ New** → **Database** → **Add PostgreSQL**
2. Wait for it to provision (~30 seconds)
3. Click your **app service** (not the database) → **Variables** tab
4. **+ New Variable** → **Add Reference** → select the Postgres service → choose **`DATABASE_URL`**

Railway now injects the connection string automatically. The app converts Railway's `postgres://` prefix to the `postgresql://` that SQLAlchemy needs — that's already handled in `main.py`.

> **Why not SQLite?** Railway containers have an ephemeral filesystem. Every deploy, restart or crash wipes it. You would lose every student account. Use Postgres.

---

## Step 4 — Set your environment variables

Still in **Variables** on the app service, add these four:

| Variable | Value | Notes |
|---|---|---|
| `JWT_SECRET` | a long random string | **Required.** Generate with the command below. If unset, every deploy logs all students out. |
| `ADMIN_EMAIL` | your email | Creates your admin account automatically on first boot |
| `ADMIN_PASSWORD` | a strong password | Only used to create the account — change it in your password manager, not here |
| `COOKIE_SECURE` | *leave unset* | Defaults to secure. Only set to `0` for local HTTP |

Generate a proper secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Paste the whole output as `JWT_SECRET`.

Railway redeploys automatically when you save variables.

---

## Step 5 — Generate your public URL

1. App service → **Settings** → **Networking**
2. **Generate Domain**
3. You get something like `vidyapath-production-a1b2.up.railway.app`

Visit it. You should see the login screen.

Check the **Deploy Logs** — you're looking for:

```
Seeded 9 tracks from curriculum.json
Created admin account: you@example.com
```

That confirms the database connected and the curriculum loaded.

---

## Step 6 — Verify the live site

Work through this list on the live URL, not localhost:

- [ ] `/api/health` returns `{"status":"ok"}`
- [ ] Create a test student account
- [ ] Open a Python lesson, run the lab, confirm it grades
- [ ] Log out, log back in, confirm progress persisted
- [ ] `/admin` → sign in with `ADMIN_EMAIL` → dashboard shows 1–2 students
- [ ] Admin → Students → click your test student → see their lesson history
- [ ] Admin → Content → edit a lesson title → save → confirm it changed on the student side
- [ ] Export CSV downloads

**Then redeploy once** (Railway → Deployments → Redeploy) and log in again. If you're still logged in and your test student still exists, your Postgres and `JWT_SECRET` are wired correctly. If you got logged out, `JWT_SECRET` isn't set.

---

## Step 7 — Custom domain (optional)

1. Buy a domain (Namecheap, GoDaddy, Cloudflare)
2. Railway → Settings → Networking → **Custom Domain** → enter `vidyapath.in`
3. Railway shows a CNAME target
4. At your registrar, add: `CNAME` record, host `@` or `www`, value = Railway's target
5. Wait 5–60 minutes for DNS. HTTPS is issued automatically.

---

## Costs

Railway's free trial credit covers early testing. After that you're on the Hobby plan — roughly **$5/month base**, plus usage. A low-traffic learning platform with Postgres typically lands around **$5–12/month**.

Set a **usage alert** in Railway → Account → Usage before you promote the site anywhere.

---

## Day-to-day operations

**Updating content:** use the admin panel at `/admin` → Content. Changes are live immediately — no redeploy.

**Updating code:** push to GitHub. Railway rebuilds and redeploys automatically.

**Editing the seed file:** `curriculum.json` only loads when the `tracks` table is *empty*. After first boot it's ignored — the database is the source of truth. To reseed from scratch you'd have to drop the tables, which deletes student progress. Don't. Edit through the admin panel instead.

**Backups:** Railway → Postgres service → **Backups**. Turn this on. Take a manual backup before any risky change.

**Watching for problems:** Railway → Deploy Logs. Set the log filter to `ERROR`.

---

## Troubleshooting

**Build fails, "no such file: requirements.txt"**
Your files are in a subfolder. Either move them to the repo root, or set Railway → Settings → **Root Directory** to that subfolder.

**App builds but crashes immediately**
Check logs for `could not translate host name`. That means `DATABASE_URL` isn't referenced. Redo step 3 — you must use **Add Reference**, not type the URL manually.

**"Not signed in" immediately after logging in**
Cookies are being rejected. Confirm you're on `https://`, and that `COOKIE_SECURE` is either unset or `1` in production.

**Everyone gets logged out after each deploy**
`JWT_SECRET` isn't set, so a new random one is generated per boot. Step 4.

**Admin panel says "not an administrator"**
`ADMIN_EMAIL` must match the account's email exactly, lowercase. If you created the account *before* setting the variable, set it and redeploy — the app promotes an existing matching account to admin on boot.

**Python labs won't run**
Pyodide loads from a CDN on first run. Needs internet and about 10 seconds. It's cached afterwards. JavaScript labs work regardless.

**Lost the admin password**
Change `ADMIN_PASSWORD` in Railway variables — but note this only creates the account if it doesn't exist; it does not reset an existing one. To reset, connect to Postgres via Railway's database tab and delete the user row, then redeploy.

---

## Security notes before you promote this

Things worth knowing, honestly:

- **Passwords** are bcrypt-hashed. Sessions are signed JWTs in httpOnly cookies. That's solid for this use case.
- **No email verification.** Anyone can sign up with any address. If that matters, add an email provider before launch.
- **No rate limiting on login.** A determined attacker could brute-force passwords. For a student platform this is low risk, but add rate limiting if you grow.
- **No password reset flow.** Students who forget their password need you to help them via the admin panel. Worth adding early — it will be your most common support request.
- **Admin content editing renders raw HTML** into lesson pages. Only give admin access to people you trust; a malicious admin could inject scripts.

None of these block a launch to a student cohort. All of them matter if this becomes a public product.
