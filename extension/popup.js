/* The site the extension pairs with. The Railway URL stays as a fallback so
 * an extension paired before the domain moved keeps working. */
const SITE = "https://craxle.com";
const FALLBACK_SITE = "https://vidyapath-athlyx-38f1.up.railway.app";

/* Fields worth nagging about: a form will almost always ask for these, and a
 * blank one is the difference between filling 4 boxes and filling 10. */
const IMPORTANT = {
  phone: "phone", location: "location", linkedin: "LinkedIn",
  work_authorized: "work authorisation",
};

const $ = (id) => document.getElementById(id);
const show = (el, on) => { el.style.display = on ? "block" : "none"; };

function say(text, kind, which) {
  const m = $(which || "msg");
  m.textContent = text;
  m.className = "msg " + (kind || "info");
  m.style.display = text ? "block" : "none";
}

async function getProfile() {
  const { profile } = await chrome.storage.local.get("profile");
  return profile || null;
}

// Checked on open, not on every fill: a form gets filled offline, in a hurry,
// and must never wait on a network call to do it.
async function getProfileChecked() {
  const p = await getProfile();
  if (!p) return null;
  const ok = await checkLicence(p);
  return ok ? p : null;
}

function paint(profile) {
  show($("setup"), !profile);
  show($("ready"), !!profile);
  if (!profile) return;
  $("who").textContent = profile.full_name || profile.email || "your account";
  const t = profile.synced_at ? new Date(profile.synced_at) : null;
  $("when").textContent = t ? "Details synced " + t.toLocaleDateString() : "";
  const gaps = Object.entries(IMPORTANT)
    .filter(([k]) => !(profile[k] || "").trim())
    .map(([, label]) => label);
  $("missing").textContent = gaps.length
    ? "Missing: " + gaps.join(", ") + " — press Edit my details to add them."
    : "";
}

/* ---------- licence ----------
   Pairing is paid, but a paired extension used to work forever: it stored the
   profile locally and never spoke to the server again. Good for privacy,
   wrong for billing — someone could subscribe for a month and autofill for a
   year.

   So it asks, at most once a day, whether the account behind it is still
   paying. The question carries a salted reference, never an id, an email or a
   session, and the answer is one boolean. If the answer is no, the stored
   profile is removed: the extension does nothing rather than filling forms
   for an account that has stopped paying.

   A network failure is NOT a no. Someone offline, or on a flaky train
   connection, keeps working — only an explicit refusal from the server clears
   anything, because breaking a paying customer's tool over dropped wifi is
   worse than a lapsed one getting a few extra days.
*/
const LICENCE_EVERY_MS = 24 * 60 * 60 * 1000;

async function checkLicence(profile) {
  if (!profile || !profile.licence_ref) return true;   // paired before this existed
  const last = Number(profile.licence_checked_at || 0);
  if (Date.now() - last < LICENCE_EVERY_MS) return true;

  for (const base of [SITE, FALLBACK_SITE]) {
    try {
      const r = await fetch(
        `${base}/api/apply/licence?ref=${encodeURIComponent(profile.licence_ref)}`);
      if (!r.ok) continue;
      const d = await r.json().catch(() => ({}));
      if (d && d.ok === false) {
        await chrome.storage.local.remove("profile");
        return false;
      }
      if (d && d.ok === true) {
        profile.licence_checked_at = Date.now();
        await chrome.storage.local.set({ profile });
        return true;
      }
    } catch (e) { /* offline: keep working, ask again tomorrow */ }
  }
  return true;
}

/* ---------- pairing ---------- */
async function pair(code) {
  let lastErr = "Could not connect";
  for (const base of [SITE, FALLBACK_SITE]) {
    try {
      const r = await fetch(`${base}/api/apply/profile?code=${encodeURIComponent(code)}`);
      const d = await r.json().catch(() => ({}));
      if (r.ok) {
        // A re-sync must not wipe details typed by hand: the site only knows
        // what the resume held, so anything it sends blank is left alone.
        const existing = (await getProfile()) || {};
        const merged = { ...existing };
        for (const [k, v] of Object.entries(d)) {
          if (String(v || "").trim() || !String(existing[k] || "").trim()) merged[k] = v;
        }
        await chrome.storage.local.set({ profile: merged });
        return merged;
      }
      lastErr = d.detail || lastErr;
      if (r.status === 401) break;      // bad code; another host won't help
    } catch (e) {
      lastErr = "Could not reach the site. Check your connection.";
    }
  }
  throw new Error(lastErr);
}

/* ---------- editor ---------- */
function openEditor(profile) {
  document.querySelectorAll("[data-f]").forEach((el) => {
    el.value = profile[el.dataset.f] || "";
  });
  show($("main"), false);
  show($("editor"), true);
  say("", "", "msg2");
}

async function saveEditor() {
  const profile = (await getProfile()) || {};
  document.querySelectorAll("[data-f]").forEach((el) => {
    profile[el.dataset.f] = el.value.trim();
  });
  // Keep full_name usable even if only the two halves were filled.
  if (!profile.full_name && (profile.first_name || profile.last_name)) {
    profile.full_name = [profile.first_name, profile.last_name].filter(Boolean).join(" ");
  }
  await chrome.storage.local.set({ profile });
  paint(profile);
  say("Saved. These are used on every form from now on.", "ok", "msg2");
  setTimeout(() => { show($("editor"), false); show($("main"), true); }, 900);
}

/* ---------- wiring ---------- */
$("siteLink").onclick = () => chrome.tabs.create({ url: `${SITE}/#careers` });

$("pair").onclick = async () => {
  const code = $("code").value.trim().toUpperCase();
  if (code.length < 6) return say("Enter the code from the site.", "err");
  $("pair").disabled = true;
  say("Connecting…");
  try {
    paint(await pair(code));
    say("Connected. Add anything missing under Edit my details.", "ok");
  } catch (e) {
    say(e.message, "err");
  }
  $("pair").disabled = false;
};

$("edit").onclick = async () => openEditor((await getProfile()) || {});
$("back").onclick = () => { show($("editor"), false); show($("main"), true); };
$("save").onclick = saveEditor;

$("resync").onclick = () => {
  say("Open Craxle and press Connect extension for a fresh code. "
    + "Anything you typed here is kept.", "info");
  chrome.tabs.create({ url: `${SITE}/#careers` });
};

$("forget").onclick = async () => {
  await chrome.storage.local.remove("profile");
  paint(null);
  say("Disconnected. Your details were removed from this browser.", "ok");
};

$("fill").onclick = async () => {
  const profile = await getProfile();
  if (!profile) return paint(null);

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !/^https?:/.test(tab.url || "")) {
    return say("Open the job application page first.", "err");
  }
  say("Filling…");
  try {
    // activeTab: this only works because the user just clicked. There is no
    // background script and nothing runs on any page until this moment.
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["filler.js"] });
    const [out] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: (p) => window.__vpFill(p),
      args: [profile],
    });
    const r = out?.result || { count: 0, filled: [], resumeUploads: 0 };
    if (!r.count) {
      say("No fields matched here. Fill it in manually — some forms use "
        + "layouts we cannot read safely.", "err");
    } else {
      let t = `Filled ${r.count} field${r.count > 1 ? "s" : ""}. Check them before you submit.`;
      if (r.resumeUploads) t += ` Attach your resume yourself (${r.resumeUploads} upload box highlighted).`;
      say(t, "ok");
    }
  } catch (e) {
    say("This page does not allow filling. Some sites block extensions.", "err");
  }
};

// On open: check the licence first, then paint. A refused licence clears the
// stored profile, so the popup falls back to the pairing screen — which is
// the honest state for an account that is no longer paying.
getProfileChecked().then(paint);
