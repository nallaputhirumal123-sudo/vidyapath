/* The site the extension pairs with. The Railway URL stays as a fallback so
 * an extension paired before the domain moved keeps working. */
const SITE = "https://craxle.com";
const FALLBACK_SITE = "https://vidyapath-athlyx-38f1.up.railway.app";

const $ = (id) => document.getElementById(id);
const show = (el, on) => { el.style.display = on ? "block" : "none"; };

function say(text, kind) {
  const m = $("msg");
  m.textContent = text;
  m.className = "msg " + (kind || "info");
  m.style.display = text ? "block" : "none";
}

async function getProfile() {
  const { profile } = await chrome.storage.local.get("profile");
  return profile || null;
}

function paint(profile) {
  show($("setup"), !profile);
  show($("ready"), !!profile);
  if (profile) {
    $("who").textContent = profile.full_name || profile.email || "your account";
    const t = profile.synced_at ? new Date(profile.synced_at) : null;
    $("when").textContent = t ? "Details synced " + t.toLocaleDateString() : "";
  }
}

async function pair(code) {
  // Try the domain first, then the Railway URL — during a DNS move either
  // one may be the live site, and the user should not have to care which.
  let lastErr = "Could not connect";
  for (const base of [SITE, FALLBACK_SITE]) {
    try {
      const r = await fetch(`${base}/api/apply/profile?code=${encodeURIComponent(code)}`);
      const d = await r.json().catch(() => ({}));
      if (r.ok) {
        await chrome.storage.local.set({ profile: d });
        return d;
      }
      lastErr = d.detail || lastErr;
      if (r.status === 401) break;   // the code itself is bad; another host won't help
    } catch (e) {
      lastErr = "Could not reach the site. Check your connection.";
    }
  }
  throw new Error(lastErr);
}

$("siteLink").onclick = (e) => {
  e.preventDefault();
  chrome.tabs.create({ url: `${SITE}/#careers` });
};

$("pair").onclick = async () => {
  const code = $("code").value.trim().toUpperCase();
  if (code.length < 6) return say("Enter the code from the site.", "err");
  $("pair").disabled = true;
  say("Connecting…");
  try {
    paint(await pair(code));
    say("Connected. Open a job application and press Fill this form.", "ok");
  } catch (e) {
    say(e.message, "err");
  }
  $("pair").disabled = false;
};

$("resync").onclick = async () => {
  say("Open the site and press Connect extension for a fresh code.", "info");
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
    const res = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["filler.js"],
    });
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

getProfile().then(paint);
