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
 * The label reading here is deliberately simpler than filler.js's. That one
 * walks up through wrappers because it has to decide a VALUE from a caption
 * and a wrong decision writes the wrong thing into somebody's application.
 * This one only has to produce a question to show a human, so it stops at
 * the sources that are unambiguous — a <label for>, an aria-label, a
 * wrapping <label>, a placeholder — and reports an empty label rather than
 * guessing from a distant div. An unlabelled field becomes "a question on
 * the form we could not read", which is true, instead of the caption
 * belonging to the input above it, which is not.
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
      const options = [];
      if (kind === "select") {
        for (const o of el.options) {
          const t = text(o.textContent);
          if (t && !/^(select|choose|--)/i.test(t)) options.push(t);
        }
      } else if (kind === "radio" && name) {
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

  /* Writing one field. Separate from filler.js on purpose: that file decides
   * what a field means, this one is told. */
  window.__vpSet = function (selector, value) {
    const el = document.querySelector(selector);
    if (!el) return false;
    const want = String(value == null ? "" : value).trim();
    const fire = (n) => {
      n.dispatchEvent(new Event("input", { bubbles: true }));
      n.dispatchEvent(new Event("change", { bubbles: true }));
    };
    if (el.tagName === "SELECT") {
      const low = want.toLowerCase();
      for (const o of el.options) {
        const t = (o.textContent || "").trim().toLowerCase();
        if (!t) continue;
        if (t === low || t.startsWith(low) || low.startsWith(t)) {
          el.value = o.value;
          fire(el);
          return true;
        }
      }
      return false;
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
