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

  /* ---------- finding the label that belongs to a field ----------
   * Returns two things, and the distinction matters. `label` is the human
   * caption alone, so an exact rule like ^name$ can be tested against it.
   * `blob` is everything we know, for looser word-boundary rules. Joining
   * the two together was a bug: "Name" became "name type here _field_name",
   * and every anchored rule stopped matching.
   */
  const clean = (s) => (s || "").toLowerCase()
    .replace(/[*∗]/g, " ")             // required-field asterisks
    .replace(/\(optional\)|\(required\)/g, " ")
    .replace(/\s+/g, " ").trim();

  function labelFor(el) {
    let label = "";
    const take = (t) => { if (!label && clean(t)) label = clean(t); };

    if (el.id) {
      const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (l) take(l.innerText);
    }
    const by = el.getAttribute("aria-labelledby");
    if (by) {
      by.split(/\s+/).forEach((id) => {
        const n = document.getElementById(id);
        if (n) take(n.innerText);
      });
    }
    const wrap = el.closest("label");
    if (wrap) take(wrap.innerText);
    take(el.getAttribute("aria-label"));

    /* Ashby, Workday and most React forms render the caption as a plain div
     * above the input rather than a <label>. Walk up a few levels looking
     * for a label-ish node or a preceding sibling with short text. */
    const FIELDS = "input,textarea,select";
    let node = el, hops = 0;
    while (node && hops < 4 && !label) {
      node = node.parentElement;
      if (!node) break;
      hops++;
      // Stop as soon as the container holds another field: we have left this
      // input's own group, and anything found above belongs to a sibling.
      // Without this the walk reached the <form> and handed every unlabelled
      // input the form's first label.
      if (node.querySelectorAll(FIELDS).length > 1) break;
      // `i` flag: classes like _fieldLabel_x8k are camelCase, and CSS
      // attribute matching is case-sensitive without it.
      for (const lb of node.children) {
        if (label) break;
        if (lb.contains(el) || lb.querySelector(FIELDS)) continue;
        if (lb.matches("label,legend,[class*='label' i]") ||
            clean(lb.innerText).length <= 60) take(lb.innerText);
      }
      let sib = node.previousElementSibling;
      while (sib && !label) {
        if (!sib.querySelector(FIELDS)) {
          const t = clean(sib.innerText);
          if (t && t.length <= 60) take(t);
        }
        sib = sib.previousElementSibling;
      }
    }

    const blob = [label, el.getAttribute("aria-label"),
                  el.getAttribute("placeholder"), el.getAttribute("name"),
                  el.id].map(clean).filter(Boolean).join(" ");
    return { label, blob };
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
    { key: "full_name", yes: [/\bfull[\s_-]*name\b/, /^name$/, /^full name$/,
        /\byour name\b/, /\bcandidate name\b/, /\blegal name\b/, /^name of applicant$/],
      no: [/first/, /last/, /user ?name/, /company/, /school/, /referr/, /file/,
           /nickname/, /preferred/] },
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

  function valueFor(found) {
    const { label, blob } = found;
    // The caption is checked first and on its own, so an exact rule can be
    // exact. Only then do we fall back to the looser blob.
    for (const src of [label, blob]) {
      if (!src) continue;
      for (const r of RULES) {
        const v = profile[r.key];
        if (!v) continue;
        if (r.no.some((rx) => rx.test(src))) continue;
        if (r.yes.some((rx) => rx.test(src))) return { key: r.key, value: v };
      }
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
