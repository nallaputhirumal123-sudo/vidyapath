/* Injected into the page ONLY when the user clicks "Fill this form".
 *
 * Two rules this file will not break:
 *   1. It never submits. It does not click buttons, does not press Enter,
 *      and does not touch <form>.submit(). The person reviews and sends.
 *   2. It only writes fields it can identify with confidence. A wrong value
 *      in a job application is worse than an empty box the user fills in.
 */
window.__vpFill = function (profile) {
  const filled = [];
  const skipped = [];

  /* ---------- finding the label that belongs to a field ---------- */
  function labelFor(el) {
    const bits = [];
    if (el.id) {
      const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (l) bits.push(l.innerText);
    }
    const wrap = el.closest("label");
    if (wrap) bits.push(wrap.innerText);
    // Greenhouse/Lever/Ashby all put the label in a parent div's first text node
    const box = el.closest("div,fieldset,section");
    if (box) {
      const lb = box.querySelector("label,legend,.label,[class*='label']");
      if (lb) bits.push(lb.innerText);
    }
    bits.push(el.getAttribute("aria-label") || "");
    bits.push(el.getAttribute("placeholder") || "");
    bits.push(el.getAttribute("name") || "");
    bits.push(el.id || "");
    return bits.join(" ").toLowerCase().replace(/\s+/g, " ").trim();
  }

  /* ---------- what each profile value is allowed to match ----------
   * `no` entries are the important half: "first name" must not win on a
   * field labelled "first name of your referrer", and "email" must never
   * land in "email of your manager".
   */
  const RULES = [
    { key: "first_name", yes: [/\bfirst[\s_-]*name\b/, /\bgiven name\b/, /\bfname\b/],
      no: [/last/, /referr/, /emergency/, /manager/, /spouse/] },
    { key: "last_name", yes: [/\blast[\s_-]*name\b/, /\bsurname\b/, /\bfamily name\b/, /\blname\b/],
      no: [/first/, /referr/, /emergency/, /manager/] },
    { key: "full_name", yes: [/\bfull[\s_-]*name\b/, /^name$/, /\byour name\b/, /\bcandidate name\b/],
      no: [/first/, /last/, /user ?name/, /company/, /school/, /referr/, /file/] },
    { key: "email", yes: [/\be-?mail\b/],
      no: [/confirm/, /referr/, /manager/, /emergency/, /alternate/] },
    { key: "phone", yes: [/\bphone\b/, /\bmobile\b/, /\btelephone\b/, /\bcontact number\b/],
      no: [/emergency/, /referr/, /work phone/, /home phone/] },
    { key: "location", yes: [/\blocation\b/, /\bcity\b/, /\bcurrent (city|location)\b/, /\baddress\b/],
      no: [/email/, /ip\b/, /website/, /url/] },
    { key: "linkedin", yes: [/linked ?in/], no: [] },
    { key: "github", yes: [/git ?hub/], no: [] },
    { key: "portfolio", yes: [/portfolio/, /personal (site|website)/, /\bwebsite\b/],
      no: [/company/, /linkedin/, /github/] },
    { key: "current_title", yes: [/current (job )?title/, /\bjob title\b/, /\byour title\b/, /current role/],
      no: [/desired/, /company/] },
    { key: "current_company", yes: [/current (employer|company)/, /\bemployer\b/, /\bcompany\b/],
      no: [/why/, /about/, /desired/, /school/] },
    { key: "school", yes: [/\bschool\b/, /\buniversity\b/, /\bcollege\b/, /\binstitution\b/], no: [] },
    { key: "degree", yes: [/\bdegree\b/, /\bqualification\b/, /field of study/], no: [] },
    { key: "grad_year", yes: [/grad(uation)? year/, /year of (graduation|passing)/, /end year/], no: [] },
    { key: "summary", yes: [/\bsummary\b/, /about (you|yourself)/, /tell us about/, /\bbio\b/],
      no: [/why (this|our|do you)/, /cover letter/] },
  ];

  function valueFor(label) {
    for (const r of RULES) {
      const v = profile[r.key];
      if (!v) continue;
      if (r.no.some((rx) => rx.test(label))) continue;
      if (r.yes.some((rx) => rx.test(label))) return { key: r.key, value: v };
    }
    return null;
  }

  /* React and Angular ignore a plain `.value =`, so set it through the
   * native setter and then fire the events their listeners expect. */
  function setValue(el, value) {
    const proto = el instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
    setter.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    el.dispatchEvent(new Event("blur", { bubbles: true }));
  }

  function flash(el, ok) {
    const prev = el.style.outline;
    el.style.outline = ok ? "2px solid #4bbf82" : "2px solid #e0b050";
    el.style.outlineOffset = "1px";
    setTimeout(() => { el.style.outline = prev; }, 2500);
  }

  const fields = document.querySelectorAll(
    "input[type='text'], input[type='email'], input[type='tel'], input[type='url'], " +
    "input:not([type]), textarea");

  for (const el of fields) {
    if (el.disabled || el.readOnly || el.offsetParent === null) continue;
    if (el.value && el.value.trim()) { skipped.push("already filled"); continue; }
    const hit = valueFor(labelFor(el));
    if (!hit) continue;
    try {
      setValue(el, hit.value);
      flash(el, true);
      filled.push(hit.key);
    } catch (e) {
      skipped.push(hit.key);
    }
  }

  /* File inputs cannot be set programmatically — browsers forbid it, for good
   * reason. Point them out instead of pretending it worked. */
  const files = [...document.querySelectorAll("input[type='file']")]
    .filter((el) => el.offsetParent !== null);
  files.forEach((el) => flash(el, false));

  return {
    filled: [...new Set(filled)],
    count: filled.length,
    resumeUploads: files.length,
  };
};
