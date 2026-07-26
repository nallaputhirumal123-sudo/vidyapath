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

  /* "Preferred" name fields are usually the same as the legal ones. Filling
   * them from the legal name when the user has not set a different one is
   * what they would type anyway, and leaving a required field blank is worse. */
  profile = Object.assign({}, profile);
  const fallback = {
    preferred_first_name: "first_name",
    preferred_middle_name: "middle_name",
    preferred_last_name: "last_name",
  };
  for (const [pref, legal] of Object.entries(fallback)) {
    if (!(profile[pref] || "").trim()) profile[pref] = profile[legal] || "";
  }
  if (!(profile.full_name || "").trim()) {
    profile.full_name = [profile.first_name, profile.middle_name, profile.last_name]
      .filter(Boolean).join(" ");
  }

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

    const FIELDS = "input,textarea,select";

    /* Flat layouts put the caption directly before the input with no wrapper
     * — "Email Address" then <input> as siblings inside the form. The walk-up
     * below bails on any container holding several fields, which is the whole
     * form here, so check the immediate siblings first. */
    let sib0 = el.previousElementSibling, near = 0;
    while (sib0 && !label && near < 3) {
      if (!sib0.querySelector(FIELDS) && !sib0.matches(FIELDS)) {
        const t = clean(sib0.innerText);
        if (t && t.length <= 60) take(t);
      } else break;          // hit another field: its label, not ours
      sib0 = sib0.previousElementSibling;
      near++;
    }

    /* Ashby, Workday and most React forms render the caption as a plain div
     * above the input rather than a <label>. Walk up a few levels looking
     * for a label-ish node or a preceding sibling with short text. */
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
    /* Combined name fields must be tested before the split ones. "Legal First
     * and Last Name" contains both words, so the single-name rules exclude
     * each other and nothing matched at all. */
    { key: "full_name", yes: [/first and last name/, /first & last name/,
        /full legal name/, /legal name/, /name \(first and last\)/,
        /first.{0,6}last name/],
      no: [/referr/, /emergency/, /manager/, /spouse/, /company/, /school/] },
    { key: "preferred_first_name", yes: [/preferred first name/, /preferred given name/],
      no: [/\breferr/, /emergency/] },
    { key: "preferred_middle_name", yes: [/preferred middle name/], no: [] },
    { key: "preferred_last_name", yes: [/preferred last name/, /preferred surname/],
      no: [/\breferr/, /emergency/] },
    { key: "middle_name", yes: [/\bmiddle[\s_-]*name\b/, /\bmiddle initial\b/],
      no: [/preferred/, /\breferr/, /emergency/] },
    { key: "first_name", yes: [/\bfirst[\s_-]*name\b/, /\bgiven name\b/, /\bfname\b/],
      no: [/last/, /middle/, /preferred/, /\breferr/, /emergency/, /manager/, /spouse/] },
    { key: "last_name", yes: [/\blast[\s_-]*name\b/, /\bsurname\b/, /\bfamily name\b/, /\blname\b/],
      no: [/first/, /middle/, /preferred/, /\breferr/, /emergency/, /manager/] },
    { key: "phone_country_code", yes: [/country code/, /dial(ling)? code/, /phone code/],
      no: [/post/, /zip/] },
    { key: "full_name", yes: [/\bfull[\s_-]*name\b/, /^name$/, /^full name$/,
        /\byour name\b/, /\bcandidate name\b/, /^name of applicant$/],
      no: [/first/, /last/, /user ?name/, /company/, /school/, /referr/, /file/,
           /nickname/] },
    { key: "email", yes: [/\be-?mail\b/],
      no: [/confirm/, /referr/, /manager/, /emergency/, /alternate/] },
    { key: "phone", yes: [/\bphone\b/, /\bmobile\b/, /\btelephone\b/, /\bcontact number\b/],
      no: [/emergency/, /referr/, /work phone/, /home phone/] },
    /* Deliberately narrow, and listed before the split address fields below
     * would otherwise lose to it. A bare "address" or "city" belongs to the
     * specific field, not to the one-line location — otherwise "Street
     * Address" and "City" both received "Dallas, TX". */
    { key: "location", yes: [/^location$/, /current location/, /city, ?state/,
        /city\/state/, /where are you (based|located)/, /^city and state$/],
      no: [/email/, /ip\b/, /website/, /url/, /street/, /^city$/, /^state$/] },
    { key: "linkedin", yes: [/linked ?in/], no: [] },
    { key: "github", yes: [/git ?hub/], no: [] },
    { key: "portfolio", yes: [/portfolio/, /personal (site|website)/, /\bwebsite\b/],
      no: [/company/, /linkedin/, /github/] },
    { key: "current_title", yes: [/current (job )?title/, /\bjob title\b/, /\byour title\b/, /current role/],
      no: [/desired/, /company/] },
    { key: "current_company", yes: [/current (employer|company)/, /\bemployer\b/, /\bcompany\b/],
      no: [/why/, /about/, /desired/, /school/] },
    { key: "school", yes: [/\bschool\b/, /\buniversity\b/, /\bcollege\b/, /\binstitution\b/], no: [] },
    { key: "field_of_study", yes: [/field of study/, /\bmajor\b/, /discipline/,
        /course of study/], no: [] },
    { key: "degree", yes: [/\bdegree\b/, /\bqualification\b/, /level of education/], no: [] },
    { key: "grad_year", yes: [/grad(uation)? year/, /year of (graduation|passing)/, /end year/], no: [] },
    { key: "summary", yes: [/\bsummary\b/, /about (you|yourself)/, /tell us about/, /\bbio\b/],
      no: [/why (this|our|do you)/, /cover letter/] },
    /* Fields a resume does not carry but forms keep asking for. */
    { key: "address", yes: [/street address/, /address line ?1/, /^address$/],
      no: [/email/, /city/, /website/, /ip\b/] },
    { key: "city", yes: [/^city$/, /^town$/, /city\/town/], no: [/state|country|code/] },
    { key: "state", yes: [/^state$/, /^province$/, /state\/province/, /^region$/], no: [] },
    { key: "postcode", yes: [/post(al)? ?code/, /zip ?code/, /^zip$/, /pin ?code/], no: [] },
    { key: "country", yes: [/^country$/, /country of residence/], no: [/code/, /citizen/] },
    { key: "years_experience", yes: [/years of (relevant )?experience/, /how many years/,
        /^experience \(years\)$/, /total experience/], no: [] },
    { key: "notice_period", yes: [/notice period/, /when can you (start|join)/,
        /availability to start/, /earliest start date/], no: [] },
    { key: "desired_salary", yes: [/salary expectation/, /expected (ctc|salary|compensation)/,
        /desired salary/, /compensation expectation/], no: [/current/] },
    { key: "work_authorized", yes: [/authoriz(ed|ation) to work/, /legally authoriz/,
        /right to work/, /eligible to work/], no: [/sponsor/] },
    { key: "needs_sponsorship", yes: [/require .*sponsorship/, /need .*sponsorship/,
        /visa sponsorship/, /will you .*sponsor/], no: [] },
    { key: "willing_to_relocate", yes: [/willing to relocate/, /open to relocat/], no: [] },
    { key: "how_heard", yes: [/how did you hear/, /where did you (hear|find)/,
        /referral source/], no: [] },
  ];

  /* Yes/no questions are usually a <select> or radios, not a text box. */
  function fillChoice(el, value) {
    const want = value.trim().toLowerCase();
    if (el.tagName === "SELECT") {
      for (const o of el.options) {
        const t = (o.textContent || "").trim().toLowerCase();
        if (!t || /select|choose|^--/.test(t)) continue;
        if (t === want || t.startsWith(want) || want.startsWith(t)) {
          el.value = o.value;
          el.dispatchEvent(new Event("input", { bubbles: true }));
          el.dispatchEvent(new Event("change", { bubbles: true }));
          return true;
        }
      }
    }
    return false;
  }

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
    "input[type='number'], input:not([type]), textarea, select");

  for (const el of fields) {
    if (el.disabled || el.readOnly || el.offsetParent === null) continue;
    // A select sitting on its placeholder counts as empty; a text box with
    // anything in it is left alone.
    const isSelect = el.tagName === "SELECT";
    if (!isSelect && el.value && el.value.trim()) { skipped.push("already filled"); continue; }
    if (isSelect && el.selectedIndex > 0) { skipped.push("already chosen"); continue; }
    const hit = valueFor(labelFor(el));
    if (!hit) continue;
    try {
      const ok = isSelect ? fillChoice(el, hit.value)
                          : (setValue(el, hit.value), true);
      if (ok) { flash(el, true); filled.push(hit.key); }
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
