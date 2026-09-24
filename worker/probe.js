/* Reading what is still unanswered, and writing one field at a time.
 *
 * filler.js is copied into this directory byte for byte and is not edited —
 * a test asserts that. It answers "what can I fill from a profile". This
 * answers the two questions that come after it:
 *
 *   __vpAsk()  — which visible fields are still empty, and what is each one
 *                actually called on screen.
 *   __vpSet()  — put this exact value in that exact field.
 *
 * The label reading takes the unambiguous sources first — a <label for>, an
 * aria-label, a wrapping <label>, a placeholder — and only then walks up for
 * a caption in a plain div.
 *
 * It started without that walk, on the reasoning that a guessed caption
 * risks showing somebody the wrong question. Measured against twenty real
 * postings, leaving it out cost more than it saved: twenty required fields
 * came back as "a question on the form we could not read", which is a
 * question nobody can answer and a row parked for good. Greenhouse's React
 * boards and Ashby render every caption as a div.
 *
 * The walk is safe here in a way it would not be inside filler.js: that file
 * picks a VALUE from a caption, and a wrong caption writes the wrong thing
 * into an application. This only produces text to show a person, who is
 * looking at the same form and will notice if it reads oddly.
 *
 * Eighteen of the twenty are still unreadable after it — custom comboboxes
 * whose caption is further away than four hops. Worth more work; not worth
 * pretending it is solved.
 */
(function () {
  const clean = (s) => (s || "").toLowerCase()
    .replace(/[*∗]/g, " ")
    .replace(/\(optional\)|\(required\)/g, " ")
    .replace(/\s+/g, " ").trim();

  /* Kept as the employer wrote it, case and all. This is the string a person
   * is shown when a row parks, and "ARE YOU AUTHORIZED TO WORK" lowercased
   * reads like a different question from the one on their screen. */
  const text = (s) => (s || "").replace(/[*∗]/g, " ")
    .replace(/\s+/g, " ").trim();

  function labelOf(el) {
    let out = "";
    const take = (t) => { if (!out && text(t)) out = text(t); };
    if (el.id) {
      const l = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (l) take(l.innerText);
    }
    take(el.getAttribute("aria-label"));
    const by = el.getAttribute("aria-labelledby");
    if (by && !out) {
      by.split(/\s+/).forEach((id) => {
        const n = document.getElementById(id);
        if (n) take(n.innerText);
      });
    }
    const wrap = el.closest("label");
    if (wrap && !out) {
      /* A wrapping label contains the input's own text too on a radio or a
       * checkbox. Strip nothing — just take it; the value is elsewhere. */
      take(wrap.innerText);
    }
    take(el.getAttribute("placeholder"));

    /* Walk up for a caption, when none of the unambiguous sources had one.
     *
     * This was deliberately left out, on the reasoning that guessing a label
     * from a nearby div risks showing somebody the wrong question. Measured
     * against twenty real postings, the cost of leaving it out was worse:
     * twenty required fields came back as "A question on the form we could
     * not read", which is a question nobody can answer and a row parked
     * forever. Greenhouse's React boards and Ashby render every caption as a
     * plain div.
     *
     * Safe in a way the same walk is not inside filler.js: that one picks a
     * VALUE from a caption, and a wrong caption writes the wrong thing into
     * an application. This only produces text to show a person, who can see
     * the form and will notice if it reads oddly.
     *
     * Stops at any container holding more than one field, so a caption is
     * never borrowed from a sibling input's group.
     */
    const FIELDS = "input,textarea,select";
    let node = el, hops = 0;
    while (node && hops < 4 && !out) {
      node = node.parentElement;
      if (!node) break;
      hops++;
      if (node.querySelectorAll(FIELDS).length > 1) break;
      for (const lb of node.children) {
        if (out) break;
        if (lb.contains(el) || lb.querySelector(FIELDS)) continue;
        const t = text(lb.innerText);
        if (t && t.length <= 120) take(t);
      }
      let sib = node.previousElementSibling;
      while (sib && !out) {
        if (!sib.querySelector(FIELDS) && !sib.matches(FIELDS)) {
          const t = text(sib.innerText);
          if (t && t.length <= 120) take(t);
        }
        sib = sib.previousElementSibling;
      }
    }
    return out.slice(0, 300);
  }

  /* A selector that will still find this element on the next call. Stable
   * ids are preferred; a name is next; an index into the form is the last
   * resort and is why nothing between the two calls may re-render. */
  function pathOf(el, i) {
    if (el.id) return `#${CSS.escape(el.id)}`;
    const n = el.getAttribute("name");
    if (n) return `${el.tagName.toLowerCase()}[name="${CSS.escape(n)}"]`;
    el.setAttribute("data-vp-idx", String(i));
    return `[data-vp-idx="${i}"]`;
  }

  /* Every option a field offers, including the ones you would have to
   * scroll to see, and including the ones that are not <option> elements.
   *
   * Two things were wrong before. The list was capped at forty, so a country
   * dropdown lost most of itself and the right answer was often not among
   * what we offered. And only <select> was read at all — the ATSs render
   * "years of experience" and skill pickers as a div with role=combobox and
   * a separate listbox, which produced a field with no options, no readable
   * label, and nothing anybody could answer.
   */
  function optionsOf(el) {
    const out = [];
    const push = (t) => {
      t = text(t);
      if (t && !/^(select|choose|--|please select)/i.test(t)
          && out.indexOf(t) < 0) out.push(t);
    };
    if (el.tagName === "SELECT") {
      for (const o of el.options) push(o.textContent);
      return out.slice(0, 400);
    }
    /* A combobox names its listbox, or owns it, or sits beside it. */
    const ids = [el.getAttribute("aria-controls"),
                 el.getAttribute("aria-owns")].filter(Boolean)
      .join(" ").split(/\s+/).filter(Boolean);
    const lists = [];
    ids.forEach((id) => {
      const n = document.getElementById(id);
      if (n) lists.push(n);
    });
    if (!lists.length) {
      const near = el.closest("[class*='select' i],[class*='combobox' i],div");
      if (near) {
        near.querySelectorAll("[role='listbox']").forEach((n) => lists.push(n));
      }
    }
    lists.forEach((l) => {
      l.querySelectorAll("[role='option'],li,option").forEach(
        (o) => push(o.textContent));
    });
    return out.slice(0, 400);
  }

  function visible(el) {
    if (el.disabled || el.readOnly) return false;
    if (el.type === "hidden") return false;
    if (el.offsetParent === null && el.type !== "radio") return false;
    return true;
  }

  /* Required, as the form actually expresses it. Three ways, because the
   * three ATSs in scope each pick a different one, and a field whose
   * requiredness we cannot read is treated as optional — parking a row on a
   * guess is the failure that would make this feature unusable. */
  function isRequired(el) {
    if (el.required || el.getAttribute("aria-required") === "true") return true;
    const lab = el.id
      ? document.querySelector(`label[for="${CSS.escape(el.id)}"]`) : null;
    const src = [(lab && lab.innerText) || "",
                 el.getAttribute("aria-label") || ""].join(" ");
    if (/[*∗]/.test(src)) return true;
    const wrap = el.closest("[class*='required' i],[data-required='true']");
    return !!wrap;
  }

  function emptyNow(el) {
    if (el.tagName === "SELECT") {
      if (el.selectedIndex <= 0) return true;
      const t = clean(el.options[el.selectedIndex].textContent);
      return !t || /^(select|choose|--)/.test(t);
    }
    if (el.type === "checkbox" || el.type === "radio") {
      const name = el.getAttribute("name");
      if (!name) return !el.checked;
      return !document.querySelector(
        `input[name="${CSS.escape(name)}"]:checked`);
    }
    return !(el.value && el.value.trim());
  }

  window.__vpAsk = function () {
    const out = [];
    const seenRadio = new Set();
    const nodes = document.querySelectorAll(
      "input:not([type='file']):not([type='submit']):not([type='button'])," +
      "textarea,select");
    let i = 0;
    for (const el of nodes) {
      i += 1;
      if (!visible(el) || !emptyNow(el)) continue;
      const name = el.getAttribute("name") || "";
      let kind = el.tagName === "SELECT" ? "select"
        : el.tagName === "TEXTAREA" ? "textarea" : (el.type || "text");
      if ((kind === "radio" || kind === "checkbox") && name) {
        /* One question, several inputs. Reporting each radio separately
         * would ask somebody the same question four times and then fill
         * none of them. */
        if (seenRadio.has(name)) continue;
        seenRadio.add(name);
      }
      let options = optionsOf(el);
      if (!options.length && kind === "radio" && name) {
        document.querySelectorAll(`input[name="${CSS.escape(name)}"]`)
          .forEach((r) => {
            const t = labelOf(r);
            if (t) options.push(t);
          });
      }
      out.push({
        selector: pathOf(el, i),
        label: labelOf(el),
        kind: kind,
        required: isRequired(el),
        options: options.slice(0, 40),
      });
    }
    return out;
  };

  /* Which option in a list is the answer "6" to a question whose choices are
   * "0-2 years", "3-5 years", "6-10 years", "10+".
   *
   * String matching cannot do this, and it is the commonest dropdown on a
   * job application. So: an exact match first, then a containment match,
   * then — only when the answer is a bare number — the band it falls in.
   * Returns an index, or -1 for "none of these", which is the answer that
   * makes the row park instead of choosing something wrong.
   */
  /* Nothing matched. Is there an option that says so honestly?
   *
   * Two kinds, and only two. "Prefer not to say" / "Decline to self
   * identify" asserts nothing about the person and is the choice these
   * forms exist to offer — on a demographic question it is the right answer
   * when nobody has told us. "Other" is fine on a question like where did
   * you hear about us.
   *
   * The caller decides whether either is allowed, because on a legal
   * declaration neither is: picking anything at all on "are you authorized
   * to work" when we do not know is a false statement, and that row must
   * park for the person. See APPLY_LEGAL in main.py.
   */
  function fallbackOption(texts, mode) {
    const norm = texts.map((t) => (t || "").trim().toLowerCase());
    const find = (rx) => {
      for (let i = 0; i < norm.length; i++) {
        if (norm[i] && rx.test(norm[i])) return i;
      }
      return -1;
    };
    if (mode === "decline" || mode === "other") {
      const i = find(/prefer not|decline|do not wish|don't wish|not disclose|choose not/);
      if (i >= 0) return i;
    }
    if (mode === "other") {
      const i = find(/^other($|[ (,.:-])|^none of|^not listed|^prefer to/);
      if (i >= 0) return i;
    }
    return -1;
  }

  function chooseOption(want, texts, mode) {
    const low = String(want || "").trim().toLowerCase();
    /* No answer at all still gets the fallback. On a demographic question
       that is the whole point: nobody has told us, and "Prefer not to say"
       is the honest option the form is offering for exactly this. */
    if (!low) return fallbackOption(texts, mode);
    const norm = texts.map((t) => (t || "").trim().toLowerCase());
    let i = norm.indexOf(low);
    if (i >= 0) return i;
    for (i = 0; i < norm.length; i++) {
      if (!norm[i] || /^(select|choose|--)/.test(norm[i])) continue;
      if (norm[i] === low) return i;
    }
    const num = parseFloat(low.replace(/[^0-9.]/g, ""));
    const isNumber = /^[0-9]+(\.[0-9]+)?$/.test(low.replace(/[^0-9.]/g, ""))
      && !isNaN(num) && /[0-9]/.test(low);
    if (isNumber) {
      let best = -1, bestFloor = -1;
      for (i = 0; i < norm.length; i++) {
        const t = norm[i];
        if (!t || /^(select|choose|--)/.test(t)) continue;
        const ns = (t.match(/[0-9]+(\.[0-9]+)?/g) || []).map(parseFloat);
        if (!ns.length) continue;
        /* "3-5 years": inside the band. */
        if (ns.length >= 2 && num >= ns[0] && num <= ns[1]) return i;
        /* "10+", "more than 5", "5 or more": the highest floor at or under
         * the answer, so 7 picks "5+" over "2+". */
        if (/\+|more|over|at least|above|greater/.test(t)
            && num >= ns[0] && ns[0] > bestFloor) {
          best = i; bestFloor = ns[0];
        }
        /* "less than 2", "under 1". */
        if (/less|under|fewer|below/.test(t) && num < ns[0] && best < 0) {
          best = i;
        }
        if (ns.length === 1 && ns[0] === num && best < 0) best = i;
      }
      if (best >= 0) return best;
    }
    for (i = 0; i < norm.length; i++) {
      if (!norm[i] || /^(select|choose|--)/.test(norm[i])) continue;
      if (norm[i].indexOf(low) >= 0 || low.indexOf(norm[i]) >= 0) return i;
    }
    return fallbackOption(texts, mode);
  }

  /* Writing one field. Separate from filler.js on purpose: that file decides
   * what a field means, this one is told. */
  /* Exposed so the adapter can ask "is there an honest way out of this
     dropdown" without duplicating the rules for what counts as one. */
  /* Exposed for the test that pins the band matching. */
  window.__vpChoose = function (want, texts, mode) {
    return chooseOption(want, texts || [], mode);
  };

  window.__vpPick = function (texts, mode) {
    return fallbackOption(texts || [], mode);
  };

  window.__vpSet = function (selector, value, mode) {
    const el = document.querySelector(selector);
    if (!el) return false;
    const want = String(value == null ? "" : value).trim();
    const fire = (n) => {
      n.dispatchEvent(new Event("input", { bubbles: true }));
      n.dispatchEvent(new Event("change", { bubbles: true }));
    };
    if (el.tagName === "SELECT") {
      const texts = [];
      for (const o of el.options) texts.push((o.textContent || "").trim());
      const idx = chooseOption(want, texts, mode);
      if (idx < 0) return false;
      el.value = el.options[idx].value;
      fire(el);
      return true;
    }
    if (el.type === "radio" || el.type === "checkbox") {
      const name = el.getAttribute("name");
      const group = name
        ? document.querySelectorAll(`input[name="${CSS.escape(name)}"]`)
        : [el];
      const low = want.toLowerCase();
      for (const r of group) {
        const lab = (labelOf(r) || r.value || "").trim().toLowerCase();
        if (lab === low || lab.startsWith(low) || low.startsWith(lab)) {
          r.checked = true;
          fire(r);
          return true;
        }
      }
      return false;
    }
    /* React and Angular ignore a plain assignment; go through the native
     * setter the same way filler.js does. */
    const proto = el instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
    setter.call(el, want);
    fire(el);
    el.dispatchEvent(new Event("blur", { bubbles: true }));
    return true;
  };
})();
