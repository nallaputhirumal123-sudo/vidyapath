/* A PDF a teacher can write on, that saves as a PDF.
 *
 * Opening a document used to hand it to the browser's own viewer in another
 * window. Nothing could be drawn on it, and the board's pen — which lives
 * over a pane and scrolls with what is inside it — had nothing to sit on.
 *
 * So the pages are rendered INTO the pane, one canvas each, stacked and
 * scrolling like any other content. The pen needs no change at all: it
 * already sizes itself to the pane's scrollHeight, so a mark made on page
 * four stays on page four when the pane scrolls. That was the hard half and
 * it was already built.
 *
 * Saving is the other half, and it is the reason this file exists rather
 * than a screenshot. Exporting a picture of the page throws away the
 * document: the text stops being text, it cannot be searched or read aloud,
 * and a class opening it on a phone gets a photograph of a worksheet. So
 * the ORIGINAL bytes are kept, and on save the annotations go back on as a
 * transparent overlay per page — the original text and vectors survive
 * exactly as they were, with the writing on top. The file that comes out is
 * the file that went in, edited.
 *
 * Two libraries, both from a CDN and both optional: pdf.js to draw the
 * pages, pdf-lib to write them back. If either is blocked the caller is
 * told plainly rather than being handed a blank pane.
 */
(function (global) {
  "use strict";

  var PDFJS = "https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/";
  var PDFLIB = "https://cdn.jsdelivr.net/npm/pdf-lib@1.17.1/dist/pdf-lib.min.js";

  function script(src) {
    return new Promise(function (res, rej) {
      var s = document.createElement("script");
      s.src = src;
      s.onload = res;
      s.onerror = function () { rej(new Error("blocked")); };
      document.head.appendChild(s);
    });
  }

  async function pdfjs() {
    if (global.pdfjsLib) return global.pdfjsLib;
    await script(PDFJS + "pdf.min.js");
    global.pdfjsLib.GlobalWorkerOptions.workerSrc = PDFJS + "pdf.worker.min.js";
    return global.pdfjsLib;
  }

  async function pdflib() {
    if (global.PDFLib) return global.PDFLib;
    await script(PDFLIB);
    return global.PDFLib;
  }

  /* Everything open, by the element it was drawn into, so a pane can be
     asked "what document are you showing" when Save is pressed. */
  var OPEN = new WeakMap();

  /* Render every page into `host`, widest-fit, and remember the bytes.
     Returns the number of pages, or throws with something worth showing. */
  async function open(host, bytes, name) {
    var lib;
    try { lib = await pdfjs(); }
    catch (e) {
      throw new Error("The PDF viewer could not load. It comes from a "
        + "public CDN — this board may be offline or the network may be "
        + "blocking it.");
    }
    var doc = await lib.getDocument({ data: bytes.slice(0) }).promise;
    host.innerHTML = "";
    var wrap = document.createElement("div");
    wrap.className = "pdfPages";
    host.appendChild(wrap);

    /* Rendered at the pane's own width. Device pixel ratio is capped at 2:
       a phone at 3 makes an A4 page a 2500px canvas per page, and thirty of
       those is a tab that dies rather than a document. */
    var R = Math.min(global.devicePixelRatio || 1, 2);
    var wide = Math.max(240, wrap.clientWidth || host.clientWidth || 700);
    var pages = [];
    for (var n = 1; n <= doc.numPages; n++) {
      var page = await doc.getPage(n);
      var base = page.getViewport({ scale: 1 });
      var scale = wide / base.width;
      var vp = page.getViewport({ scale: scale });
      var cv = document.createElement("canvas");
      cv.className = "pdfPage";
      cv.width = Math.round(vp.width * R);
      cv.height = Math.round(vp.height * R);
      cv.style.width = Math.round(vp.width) + "px";
      cv.style.height = Math.round(vp.height) + "px";
      wrap.appendChild(cv);
      var ctx = cv.getContext("2d");
      ctx.setTransform(R, 0, 0, R, 0, 0);
      await page.render({ canvasContext: ctx, viewport: vp }).promise;
      pages.push(cv);
    }
    OPEN.set(host, { bytes: bytes, name: name || "document.pdf", pages: pages });
    return doc.numPages;
  }

  function shown(host) { return OPEN.get(host) || null; }

  /* The document as it now stands: the original, with whatever was drawn
     over it stamped on, page by page.
     `marks` is the pane's annotation canvas — one tall canvas covering the
     whole scrolling body, which is why each page has to take its own slice
     of it rather than the whole thing. */
  async function save(host, marks) {
    var rec = OPEN.get(host);
    if (!rec) throw new Error("No document is open here.");
    var PL;
    try { PL = await pdflib(); }
    catch (e) {
      throw new Error("The PDF writer could not load. It comes from a "
        + "public CDN — this board may be offline or the network may be "
        + "blocking it.");
    }
    var doc = await PL.PDFDocument.load(rec.bytes.slice(0));
    var pages = doc.getPages();

    for (var i = 0; i < rec.pages.length && i < pages.length; i++) {
      var slice = cutFor(rec.pages[i], marks);
      if (!slice) continue;
      var png = await new Promise(function (r) { slice.toBlob(r, "image/png"); });
      if (!png) continue;
      var buf = await png.arrayBuffer();
      var img = await doc.embedPng(buf);
      var pg = pages[i];
      var size = pg.getSize();
      /* Drawn over the whole page rather than at the mark's coordinates:
         the slice already has the marks in the right place within it, and
         a page-sized overlay cannot drift out of register. */
      pg.drawImage(img, { x: 0, y: 0, width: size.width, height: size.height });
    }
    var out = await doc.save();
    return new Blob([out], { type: "application/pdf" });
  }

  /* The part of the annotation canvas that lies over one page, as its own
     transparent canvas at that page's size. Positions come from the live
     layout, so a pane that has been resized or scrolled is still right. */
  function cutFor(pageCanvas, marks) {
    if (!marks || !marks.width) return null;
    var pr = pageCanvas.getBoundingClientRect();
    var mr = marks.getBoundingClientRect();
    var sx = (pr.left - mr.left) * (marks.width / mr.width);
    var sy = (pr.top - mr.top) * (marks.height / mr.height);
    var sw = pr.width * (marks.width / mr.width);
    var sh = pr.height * (marks.height / mr.height);
    if (!(sw > 0 && sh > 0)) return null;
    var out = document.createElement("canvas");
    out.width = Math.max(1, Math.round(pr.width * 2));
    out.height = Math.max(1, Math.round(pr.height * 2));
    var c = out.getContext("2d");
    try {
      c.drawImage(marks, sx, sy, sw, sh, 0, 0, out.width, out.height);
    } catch (e) { return null; }
    return out;
  }

  global.PdfView = { open: open, save: save, shown: shown };
})(window);
