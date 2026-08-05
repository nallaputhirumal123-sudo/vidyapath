/* The pitch decks: schools, degree colleges, engineering colleges.
 *
 *     node tools/build_deck.js schools      Craxlearn-for-Schools.pptx
 *     node tools/build_deck.js colleges     Craxlearn-for-Colleges.pptx
 *     node tools/build_deck.js engineering  Craxlearn-for-Engineering.pptx
 *     node tools/build_deck.js all
 *
 * Three audiences, three decks, because the true claim is different in each
 * room. The retrieval corpus is NCERT Class 6 to 12 plus our own computing
 * curriculum, so the school deck can say "answers out of the actual textbook"
 * and mean it. A college deck saying the same sentence would be selling a
 * corpus that does not cover their syllabus.
 *
 * What a college gets instead is three grounds rather than one: the corpus
 * where it reaches, the open catalogues it cites, and — the one that closes
 * the gap — the lecturer's own PDF, uploaded and turned into a lesson. That
 * is a feature this repository already has, and for a department with its own
 * notes it is worth more than somebody else's textbook.
 *
 * Plus the half a school cannot use at all: students over 18 reach the job
 * board and the placement tooling. For an engineering college that, and the
 * sandboxes they can genuinely push on, is the pitch.
 *
 * Every feature named here was read out of this repository: the tiles from
 * TILES in craxlearn.html, the roles from the routes in main.py, the sources
 * from SOURCES in craxlearn.py, the DPDP wording from privacy.html.
 */
const pptxgen = require("pptxgenjs");

/* Chalkboard, chalk, and the amber of a classroom lamp. */
const BOARD = "16302B", BOARD2 = "24473D";
const CHALK = "F2F5F1", CARD = "E7EDE7";
const INK = "16302B", MUTED = "5C7268";
const AMBER = "E0913A", AMBER_SOFT = "F6E3C7", AMBER_INK = "7A4E12";
const HEAD = "Cambria", BODY = "Calibri";

/* Vertical budget. Content lives between these, and tools/check_deck.py
   reports anything that leaves the box or cannot fit inside its own card. */
const TOP = 1.75, FOOT_Y = 6.66;

function kit(p) {
  const K = {};
  const sh = () => ({ type: "outer", color: "10231E", blur: 10, offset: 2,
                      angle: 90, opacity: 0.16 });

  K.dark = s => { s.background = { color: BOARD }; };
  K.light = s => { s.background = { color: CHALK }; };

  K.title = (s, t, kicker, onDark) => {
    if (kicker) {
      s.addText(kicker.toUpperCase(), {
        x: 0.62, y: 0.5, w: 11, h: 0.28, margin: 0,
        fontFace: BODY, fontSize: 12, bold: true, color: AMBER, charSpacing: 2
      });
    }
    s.addText(t, {
      x: 0.6, y: kicker ? 0.82 : 0.58, w: 12.1, h: 0.78, margin: 0,
      fontFace: HEAD, fontSize: 33, bold: true, color: onDark ? CHALK : INK
    });
  };

  K.bead = (s, x, y, glyph, d = 0.46, fill = AMBER, fg = "FFFFFF") => {
    s.addShape(p.ShapeType.ellipse, { x, y, w: d, h: d, fill: { color: fill } });
    s.addText(glyph, {
      x, y, w: d, h: d, margin: 0, align: "center", valign: "middle",
      fontFace: BODY, fontSize: d > 0.5 ? 16 : 12.5, bold: true, color: fg
    });
  };

  K.card = (s, x, y, w, h, fill = CARD) => {
    s.addShape(p.ShapeType.roundRect, {
      x, y, w, h, rectRadius: 0.11, fill: { color: fill }, shadow: sh()
    });
  };

  /* Bead, bold heading, description. The description starts at +0.58 — at
     +0.72 a 1.14in card left 0.22in for two lines of 10.5pt text, which is
     162% of what fits, and the geometry check said so before anyone read it. */
  K.feature = (s, x, y, w, h, glyph, head, sub, o = {}) => {
    K.card(s, x, y, w, h, o.fill || CARD);
    K.bead(s, x + 0.24, y + 0.2, glyph, 0.44, o.bead || AMBER, o.beadFg || "FFFFFF");
    s.addText(head, {
      x: x + 0.8, y: y + 0.16, w: w - 1.0, h: 0.32, margin: 0, valign: "middle",
      fontFace: BODY, fontSize: o.headSize || 13, bold: true,
      color: o.headColor || INK
    });
    if (sub) {
      /* Clear of the bead: it sits at y+0.2 and is 0.44 across, so it ends at
         y+0.64. Starting the description at y+0.58 put its first line under
         the bottom of the circle — a 0.06in clip the geometry check found and
         a reader would notice as a letter with a bite out of it. */
      s.addText(sub, {
        x: x + 0.26, y: y + 0.68, w: w - 0.52, h: h - 0.8, margin: 0,
        fontFace: BODY, fontSize: o.subSize || 10.5,
        color: o.subColor || MUTED, lineSpacing: 13
      });
    }
  };

  K.foot = (s, t, onDark) => {
    s.addText(t, {
      x: 0.6, y: FOOT_Y, w: 12.1, h: 0.3, margin: 0,
      fontFace: BODY, fontSize: 11, italic: true,
      color: onDark ? "8FA89B" : MUTED
    });
  };

  K.pills = (s, y, items, activeIndex) => {
    const n = items.length, gap = 0.18;
    const w = (12.1 - gap * (n - 1)) / n;
    items.forEach((t, i) => {
      const x = 0.6 + i * (w + gap), on = i === activeIndex;
      s.addShape(p.ShapeType.roundRect, {
        x, y, w, h: 0.58, rectRadius: 0.29,
        fill: { color: on ? AMBER : BOARD2 },
        line: { color: on ? AMBER : "3D6355", width: 1 }
      });
      s.addText(t, {
        x, y, w, h: 0.58, margin: 0, align: "center", valign: "middle",
        fontFace: BODY, fontSize: 12, bold: true, color: on ? BOARD : CHALK
      });
    });
  };

  K.grid = (s, items, cols, y0, rowH, gap, o = {}) => {
    const gapX = 0.22;
    const w = (12.1 - gapX * (cols - 1)) / cols;
    items.forEach((it, i) => {
      const c = i % cols, r = Math.floor(i / cols);
      K.feature(s, 0.6 + c * (w + gapX), y0 + r * (rowH + gap), w, rowH,
        it[0], it[1], it[2], o);
    });
  };

  return K;
}

/* ================================================================== */
/* Slides shared by all three decks                                    */
/* ================================================================== */

function cover(p, K, c) {
  const s = p.addSlide(); K.dark(s);
  s.addShape(p.ShapeType.ellipse, { x: 10.1, y: -1.5, w: 5.4, h: 5.4, fill: { color: BOARD2 } });
  s.addShape(p.ShapeType.ellipse, { x: 11.9, y: 4.6, w: 3.0, h: 3.0, fill: { color: BOARD2 } });
  s.addText(c.cover.kicker.toUpperCase(), {
    x: 0.85, y: 1.32, w: 8.6, h: 0.3, margin: 0,
    fontFace: BODY, fontSize: 13, bold: true, color: AMBER, charSpacing: 2.4
  });
  s.addText("Craxlearn", {
    x: 0.8, y: 1.72, w: 9.4, h: 1.3, margin: 0,
    fontFace: HEAD, fontSize: 64, bold: true, color: CHALK
  });
  s.addText(c.cover.line, {
    x: 0.85, y: 3.06, w: 8.4, h: 1.0, margin: 0,
    fontFace: BODY, fontSize: 15.5, color: "C7D6CD", lineSpacing: 24
  });
  c.cover.chips.forEach((t, i) => {
    const x = 0.85 + i * 2.16;
    s.addShape(p.ShapeType.roundRect, {
      x, y: 4.4, w: 1.96, h: 0.5, rectRadius: 0.25,
      fill: { color: BOARD2 }, line: { color: "3D6355", width: 1 }
    });
    s.addText(t, {
      x, y: 4.4, w: 1.96, h: 0.5, margin: 0, align: "center", valign: "middle",
      fontFace: BODY, fontSize: 11.5, bold: true, color: CHALK
    });
  });
  s.addText("craxle.com/craxlearn", {
    x: 0.85, y: 5.7, w: 6, h: 0.36, margin: 0,
    fontFace: BODY, fontSize: 15, bold: true, color: AMBER
  });
  s.addText("Runs in the browser on the panel you already own.", {
    x: 0.85, y: 6.08, w: 8.6, h: 0.32, margin: 0,
    fontFace: BODY, fontSize: 12, color: "8FA89B"
  });
  s.addNotes(c.cover.notes);
}

function howItWorks(p, K, c) {
  const s = p.addSlide(); K.light(s);
  K.title(s, "How the smart board works", "The board");
  const steps = [
    ["1", "The panel you have", "Any smart board or TV with an OPS mini PC, or any Windows or Android panel with a browser."],
    ["2", "Open the address", "craxle.com/craxlearn. No app store, no installer, no licence key on a USB stick."],
    ["3", "Install it once", "It installs as an app and opens full screen from the home screen after that."],
    ["4", "Sign in with a code", "The code tells the board which class and subject it is standing in."],
    ["5", "Teach", "Everything saved from the board goes straight to that subject's study material."]
  ];
  const gapX = 0.22, w = (12.1 - gapX * 4) / 5;
  steps.forEach((st, i) => {
    const x = 0.6 + i * (w + gapX);
    K.card(s, x, TOP, w, 2.44);
    K.bead(s, x + 0.24, TOP + 0.22, st[0], 0.48);
    s.addText(st[1], {
      x: x + 0.24, y: TOP + 0.84, w: w - 0.48, h: 0.56, margin: 0,
      fontFace: BODY, fontSize: 12.5, bold: true, color: INK, lineSpacing: 15
    });
    s.addText(st[2], {
      x: x + 0.24, y: TOP + 1.42, w: w - 0.48, h: 0.9, margin: 0,
      fontFace: BODY, fontSize: 9.5, color: MUTED, lineSpacing: 12
    });
  });
  K.card(s, 0.6, 4.52, 12.1, 1.9, BOARD);
  K.bead(s, 0.94, 4.84, "+", 0.5, AMBER);
  s.addText("It also runs on a laptop, a tablet and a phone", {
    x: 1.62, y: 4.8, w: 10.6, h: 0.34, margin: 0,
    fontFace: BODY, fontSize: 14.5, bold: true, color: CHALK
  });
  s.addText(
    "The same address, the same account. A teacher can prepare at home and pick it up in the room. " +
    "A phone works as the remote, so the lesson is driven facing the room rather than from the " +
    "screen — type or speak the next topic and it appears on the board.", {
    x: 1.62, y: 5.22, w: 10.6, h: 1.0, margin: 0,
    fontFace: BODY, fontSize: 11, color: "BCCFC4", lineSpacing: 14
  });
  s.addNotes("Demo point: install it on their own panel during the meeting. It takes under a minute.");
}

function surfaces(p, K) {
  const s = p.addSlide(); K.light(s);
  K.title(s, "Twelve teaching surfaces", "On the board");
  K.grid(s, [
    ["A", "Ask the board", "Any subject, taught step by step, with a diagram where one helps."],
    ["W", "Writing space", "A blank surface to work on by hand. Save it as a picture."],
    ["C", "Calculator", "Arithmetic, powers and roots, worked where the room can see it."],
    ["3", "3D structures", "A molecule, crystal, protein or orbit, turned. Measured, never drawn."],
    ["S", "Search the sources", "A photograph or structure from the open catalogues, with its licence."],
    ["P", "Simulations", "PhET: build an atom, wire a circuit, balance an equation."],
    ["Q", "Scan a problem", "Photograph a question from a book and have it worked through."],
    ["E", "Courses and exams", "The lessons, the labs you type into, and the track exams."],
    ["N", "Trace a packet", "Send a packet through real routes and firewall rules."],
    ["L", "The lab", "Mix real reagents. Every reaction from a table, never guessed."],
    ["D", "SQL board", "Write queries against a real database and see what comes back."],
    ["R", "Remote", "Drive the board from a phone and teach facing the room."]
  ], 4, TOP, 1.5, 0.16, { headSize: 12.5, subSize: 9.8 });
  K.foot(s, "Any two of these open side by side on one board — the lesson on the left, the simulation on the right.");
  s.addNotes("This is the whole home screen of the board, nothing held back.");
}

function levels(p, K, c) {
  const s = p.addSlide(); K.dark(s);
  K.title(s, c.levels.title, "Taught to any level", true);
  K.pills(s, TOP, ["Class 6", "Class 8", "Class 10", "Class 12", "Undergraduate", "Research"],
    c.levels.active);
  s.addText(c.levels.body, {
    x: 0.6, y: 2.56, w: 12.1, h: 0.8, margin: 0,
    fontFace: BODY, fontSize: 12.5, color: "C7D6CD", lineSpacing: 18
  });
  const gapX = 0.22, w = (12.1 - gapX * 2) / 3;
  c.levels.examples.forEach((e, i) => {
    const x = 0.6 + i * (w + gapX);
    K.card(s, x, 3.56, w, 2.4, BOARD2);
    s.addShape(p.ShapeType.roundRect, {
      x: x + 0.26, y: 3.8, w: 1.9, h: 0.4, rectRadius: 0.2, fill: { color: AMBER }
    });
    s.addText(e[0], {
      x: x + 0.26, y: 3.8, w: 1.9, h: 0.4, margin: 0, align: "center", valign: "middle",
      fontFace: BODY, fontSize: 11, bold: true, color: BOARD
    });
    s.addText('"' + e[1] + '"', {
      x: x + 0.26, y: 4.34, w: w - 0.52, h: 1.5, margin: 0,
      fontFace: BODY, fontSize: 11, italic: true, color: "D6E2DA", lineSpacing: 15
    });
  });
  K.foot(s, c.levels.foot, true);
  s.addNotes("The most persuasive live demo there is: type one topic, change the level, ask again.");
}

function midLesson(p, K) {
  const s = p.addSlide(); K.light(s);
  K.title(s, "What a teacher does with it, mid-lesson", "On the board");
  K.grid(s, [
    ["1", "Write anywhere on the screen", "Pen or finger, over anything — a diagram, a simulation, a PDF. Not only in a canvas."],
    ["2", "Mark a line and ask", "Circle an equation: Copy, Paste, or Ask Axle. The answer opens in a window you can resize."],
    ["3", "Undo, redo, thickness, rub out", "The controls a person mid-sentence can hit without reading a menu."],
    ["4", "Save the board as a picture", "Or screenshot one space. It lands in the study material."],
    ["5", "Two spaces side by side", "The lesson on one half, the lab or the simulation on the other."],
    ["6", "Say it instead of typing", "Speak the topic. Useful with chalk in the other hand."],
    ["7", "A PDF as-is, or as a lesson", "Upload a chapter: show it exactly as it is, or have it written up and taught."],
    ["8", "Lines, not paragraphs", "Explanations come out line by line, so a room can read them from the back."],
    ["9", "Report an error in this", "A button on the answer itself. A wrong thing on a board gets reported, not argued with."]
  ], 3, TOP, 1.5, 0.16, { headSize: 12.5, subSize: 9.8 });
  K.foot(s, "Every one of these exists because a teacher cannot stop the lesson to work a screen out.");
  s.addNotes("Walk the room through one of these live rather than reading the list.");
}

function teacher(p, K, c) {
  const s = p.addSlide(); K.light(s);
  K.title(s, c.staffTitle, "Who does what");
  const rows = [
    ["Their own classes, and only theirs", "They see the students they teach. Nobody else's."],
    ["Any class, several subjects", "One person can hold two classes and three subjects at once."],
    ["The register", "Roll numbers, search, edit a row, mark attendance."],
    ["Set and collect work", "Post work with a due date, see submissions, close it when done."],
    ["Study material", "Upload chapters and slides or add links, kept per subject."],
    ["Subject discussion", "A thread the class and the teacher share, per subject."],
    ["An inbox", "Questions from students across every class they teach, with the name."],
    ["Save from the board", "Whatever is taught on the board files itself into that subject."]
  ];
  const gapX = 0.22, w = (12.1 - gapX) / 2;
  rows.forEach((r, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = 0.6 + col * (w + gapX), y = TOP + row * 1.24;
    K.card(s, x, y, w, 1.08);
    K.bead(s, x + 0.24, y + 0.28, "+", 0.44);
    s.addText(r[0], {
      x: x + 0.8, y: y + 0.16, w: w - 1.0, h: 0.32, margin: 0, valign: "middle",
      fontFace: BODY, fontSize: 13, bold: true, color: INK
    });
    s.addText(r[1], {
      x: x + 0.8, y: y + 0.52, w: w - 1.0, h: 0.44, margin: 0,
      fontFace: BODY, fontSize: 10, color: MUTED, lineSpacing: 12.5
    });
  });
  K.foot(s, "The boundary is enforced on the server, not hidden in a menu — nobody is handed the whole institution to do their own job.");
  s.addNotes("Say the last line out loud. Heads ask about it before anything else.");
}

function threePlaces(p, K) {
  const s = p.addSlide(); K.light(s);
  K.title(s, "Three separate places, not one feed", "Teaching");
  const cols = [
    ["W", "Work set", ["What was set, and when it is due", "Who has handed in and who has not", "Open or closed, and who closed it", "A thread under each piece of work"]],
    ["M", "Study material", ["Chapters, slides, notes, links", "Anything saved from the board", "Kept per subject", "There when it is needed again"]],
    ["D", "Subject discussion", ["The subject's own thread", "Students ask, students answer", "The subject teacher is in it", "Not a general noticeboard"]]
  ];
  const gapX = 0.22, w = (12.1 - gapX * 2) / 3;
  cols.forEach((cc, i) => {
    const x = 0.6 + i * (w + gapX);
    K.card(s, x, TOP, w, 3.5);
    K.bead(s, x + 0.28, TOP + 0.26, cc[0], 0.52);
    s.addText(cc[1], {
      x: x + 0.94, y: TOP + 0.26, w: w - 1.16, h: 0.52, margin: 0, valign: "middle",
      fontFace: HEAD, fontSize: 17, bold: true, color: INK
    });
    s.addText(cc[2].map((t, j) => ({
      text: t, options: { bullet: true, breakLine: j < cc[2].length - 1 }
    })), {
      x: x + 0.32, y: TOP + 1.0, w: w - 0.64, h: 2.3, margin: 0,
      fontFace: BODY, fontSize: 11, color: MUTED, paraSpaceAfter: 7, lineSpacing: 14
    });
  });
  K.card(s, 0.6, 5.5, 12.1, 1.0, AMBER_SOFT);
  K.bead(s, 0.9, 5.74, "!", 0.46);
  s.addText("Why it is not one feed", {
    x: 1.52, y: 5.62, w: 10.9, h: 0.3, margin: 0,
    fontFace: BODY, fontSize: 13, bold: true, color: AMBER_INK
  });
  s.addText("Homework, the chapter needed again in March, and a question asked on Tuesday have different lifetimes. Merge them and the one that matters is the one scrolled past.", {
    x: 1.52, y: 5.96, w: 10.9, h: 0.42, margin: 0,
    fontFace: BODY, fontSize: 10, color: AMBER_INK, lineSpacing: 12.5
  });
  s.addNotes("Contrast with the WhatsApp group, which is what most institutions use today.");
}

function office(p, K, c) {
  const s = p.addSlide(); K.light(s);
  K.title(s, c.office.title, "Who does what");
  K.grid(s, c.office.items, 2, TOP, 1.10, 0.10, { headSize: 12.5, subSize: 10 });
  K.foot(s, "We create the institution and its first administrator. Everything after that is yours to run — nobody rings us to add a teacher in June.");
  s.addNotes("The objection this answers: who maintains it when the vendor stops answering the phone.");
}

function privacy(p, K, c) {
  const s = p.addSlide(); K.light(s);
  K.title(s, "Privacy, under the DPDP Act 2023", c.privacy.kicker);
  K.grid(s, c.privacy.items, 2, TOP, 1.36, 0.14, { headSize: 12.5, subSize: 9.8 });
  K.foot(s, "The policy is written for India first and names the Act. It is at craxle.com/privacy, in plain language, before anybody signs anything.");
  s.addNotes(c.privacy.notes);
}

/* The board itself, drawn, with a real lesson on it.
 *
 * Every other slide DESCRIBES the board. A room being pitched to has no idea
 * what that means until they see one, and "twelve teaching surfaces" is a
 * phrase, not a picture. So this is a panel with an actual class on it: the
 * lesson written out in lines, the 3D view beside it, and Axle answering the
 * question a child would really ask next.
 *
 * Drawn from shapes rather than pasted as a screenshot, because a screenshot
 * of a product still being built goes stale between the pitch and the demo.
 */
function boardShot(p, K, c) {
  const s = p.addSlide(); K.dark(s);
  K.title(s, c.shot.title, "What it looks like in the room", true);

  const b = c.shot;
  /* Bezel, then the panel. */
  K.card(s, 0.5, 1.56, 12.33, 5.12, "0D1F1A");
  s.addShape(p.ShapeType.roundRect, {
    x: 0.66, y: 1.7, w: 12.01, h: 4.84, rectRadius: 0.08,
    fill: { color: "FBFCFB" }
  });

  /* The strip along the top of the board: where you are, and the time. */
  s.addText(b.where, {
    x: 0.86, y: 1.82, w: 8.0, h: 0.3, margin: 0, valign: "middle",
    fontFace: BODY, fontSize: 11, bold: true, color: INK
  });
  s.addText(b.clock + "  ·  IST", {
    x: 9.4, y: 1.82, w: 3.1, h: 0.3, margin: 0, align: "right", valign: "middle",
    fontFace: BODY, fontSize: 11, bold: true, color: AMBER
  });

  const PY = 2.24, PH = 4.14;

  /* ---- the lesson, in lines ---- */
  s.addShape(p.ShapeType.roundRect, {
    x: 0.86, y: PY, w: 4.94, h: PH, rectRadius: 0.07, fill: { color: "F1F5F1" }
  });
  s.addText(b.lesson.title, {
    x: 1.04, y: PY + 0.16, w: 4.58, h: 0.3, margin: 0,
    fontFace: BODY, fontSize: 13, bold: true, color: INK
  });
  s.addText(b.lesson.lines.map((t, i) => ({
    text: t,
    options: { bullet: true, breakLine: i < b.lesson.lines.length - 1 }
  })), {
    x: 1.06, y: PY + 0.56, w: 4.5, h: PH - 1.0, margin: 0, valign: "top",
    fontFace: BODY, fontSize: 10.5, color: "2E4740", paraSpaceAfter: 6,
    lineSpacing: 14
  });
  s.addText("Saved to " + b.savedTo + " · study material", {
    x: 1.04, y: PY + PH - 0.34, w: 4.58, h: 0.24, margin: 0,
    fontFace: BODY, fontSize: 8.5, italic: true, color: MUTED
  });

  /* Ink over the top of it — the pen works anywhere, so show it doing that.
     Lines carry no text, so they cannot collide with anything the geometry
     check measures. */
  const ink = (x1, y1, x2, y2, w) => s.addShape(p.ShapeType.line, {
    x: Math.min(x1, x2), y: Math.min(y1, y2),
    w: Math.abs(x2 - x1), h: Math.abs(y2 - y1),
    line: { color: "E0913A", width: w || 2.25 },
    flipH: x2 < x1, flipV: y2 < y1
  });
  b.underline.forEach(u => ink(u[0], u[1], u[2], u[3]));

  /* ---- the 3D view ---- */
  s.addShape(p.ShapeType.roundRect, {
    x: 5.96, y: PY, w: 2.96, h: PH, rectRadius: 0.07, fill: { color: "16302B" }
  });
  s.addText("3D · drag to turn", {
    x: 6.14, y: PY + 0.16, w: 2.6, h: 0.26, margin: 0,
    fontFace: BODY, fontSize: 9.5, bold: true, color: AMBER
  });
  ({ methane, lattice })[b.model](p)(s, 7.44, PY + 1.92);
  s.addText(b.modelCaption, {
    x: 6.14, y: PY + 3.34, w: 2.6, h: 0.62, margin: 0,
    fontFace: BODY, fontSize: 8.5, color: "9DB6A9", lineSpacing: 11
  });

  /* ---- Axle, answering ---- */
  s.addShape(p.ShapeType.roundRect, {
    x: 9.08, y: PY, w: 3.6, h: PH, rectRadius: 0.07,
    fill: { color: "1E3D34" }, shadow: { type: "outer", color: "000000",
      blur: 12, offset: 3, angle: 90, opacity: 0.3 }
  });
  K.bead(s, 9.26, PY + 0.16, "A", 0.34);
  s.addText("Ask Axle", {
    x: 9.68, y: PY + 0.16, w: 1.28, h: 0.34, margin: 0, valign: "middle",
    fontFace: BODY, fontSize: 11.5, bold: true, color: CHALK
  });
  s.addText("resize  ·  close", {
    x: 11.0, y: PY + 0.16, w: 1.5, h: 0.34, margin: 0, align: "right",
    valign: "middle", fontFace: BODY, fontSize: 8.5, color: "7E9A8C"
  });
  s.addText('"' + b.asked + '"', {
    x: 9.26, y: PY + 0.62, w: 3.24, h: 0.42, margin: 0,
    fontFace: BODY, fontSize: 10, italic: true, color: AMBER, lineSpacing: 12
  });
  s.addText(b.answer.map((t, i) => ({
    text: t, options: { bullet: true, breakLine: i < b.answer.length - 1 }
  })), {
    x: 9.28, y: PY + 1.1, w: 3.2, h: PH - 1.62, margin: 0, valign: "top",
    fontFace: BODY, fontSize: 9.5, color: "C7D6CD", paraSpaceAfter: 6,
    lineSpacing: 12.5
  });
  s.addText("Report an error in this", {
    x: 9.26, y: PY + PH - 0.36, w: 3.24, h: 0.26, margin: 0,
    fontFace: BODY, fontSize: 8.5, italic: true, color: "7E9A8C"
  });

  K.foot(s, b.foot, true);
  s.addNotes(b.notes);
}

/* What the tools are FOR, from the student's side.
 *
 * Every other slide lists what the board can do. This one answers the
 * question a parent or a head of department is actually asking, which is what
 * the child gets out of it — so each row is a moment in a student's day and
 * the tool that meets it, rather than a feature and its description.
 */
function forStudents(p, K, c) {
  const s = p.addSlide(); K.light(s);
  K.title(s, "What a student gets out of it", "Not the feature list — the point of it");

  const rows = [
    ["A", "Stuck at 9pm, nobody to ask",
      "The tutor",
      "Ask it at their own level and keep asking. It does not get tired of the third follow-up, which is usually the one that matters."],
    ["S", "A question they cannot even type",
      "Scan a problem",
      "Photograph it out of the textbook — the diagram, the equation, the circuit — and have it worked through step by step."],
    ["L", "An experiment the timetable has no room for",
      "The lab",
      "Mix the reagents and run it. Every reaction comes from a measured table, so a wrong prediction is corrected by the chemistry, not by a marking scheme."],
    ["D", "Learning to query without a database to break",
      "The SQL board",
      "Real queries against a real database, including the errors. They cannot break anything, so they can try the thing they are unsure about."],
    ["N", "Networking as an abstraction that never lands",
      "Trace a packet",
      "Send one through real routing tables and firewall rules and watch each decision as it happens."],
    ["3", "Something flat on a page that is not flat",
      "3D structures",
      "Turn the molecule, the crystal or the orbit and measure it. Real coordinates from the open catalogues."]
  ];
  const gapX = 0.22, w = (12.1 - gapX) / 2;
  rows.forEach((r, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = 0.6 + col * (w + gapX), y = TOP + row * 1.62;
    K.card(s, x, y, w, 1.46);
    K.bead(s, x + 0.24, y + 0.22, r[0], 0.44);
    s.addText(r[1], {
      x: x + 0.8, y: y + 0.18, w: w - 1.0, h: 0.3, margin: 0, valign: "middle",
      fontFace: BODY, fontSize: 11, italic: true, color: MUTED
    });
    s.addText(r[2], {
      x: x + 0.8, y: y + 0.46, w: w - 1.0, h: 0.3, margin: 0, valign: "middle",
      fontFace: BODY, fontSize: 13.5, bold: true, color: INK
    });
    s.addText(r[3], {
      x: x + 0.26, y: y + 0.82, w: w - 0.52, h: 0.56, margin: 0,
      fontFace: BODY, fontSize: 10, color: MUTED, lineSpacing: 12.5
    });
  });
  K.foot(s, "All of it on the board at the front and on their own phone or laptop, from one address and one account.");
  s.addNotes("If you only get one slide in front of a parent, this is the one.");
}

/* A tetrahedral molecule, drawn. Real geometry rather than a clip-art blob:
   one atom in the middle, four around it, bonds between. */
function methane(p) {
  return (s, cx, cy) => {
    const bond = (dx, dy) => s.addShape(p.ShapeType.line, {
      x: Math.min(cx, cx + dx), y: Math.min(cy, cy + dy),
      w: Math.abs(dx), h: Math.abs(dy),
      line: { color: "6E8C7F", width: 2 }, flipH: dx < 0, flipV: dy < 0
    });
    const at = [[-0.62, -0.42], [0.62, -0.42], [-0.5, 0.58], [0.58, 0.5]];
    at.forEach(a => bond(a[0], a[1]));
    at.forEach(a => {
      s.addShape(p.ShapeType.ellipse, {
        x: cx + a[0] - 0.16, y: cy + a[1] - 0.16, w: 0.32, h: 0.32,
        fill: { color: "DCE6DF" }
      });
      s.addText("H", {
        x: cx + a[0] - 0.16, y: cy + a[1] - 0.16, w: 0.32, h: 0.32, margin: 0,
        align: "center", valign: "middle",
        fontFace: BODY, fontSize: 8, bold: true, color: "16302B"
      });
    });
    s.addShape(p.ShapeType.ellipse, {
      x: cx - 0.26, y: cy - 0.26, w: 0.52, h: 0.52, fill: { color: AMBER }
    });
    s.addText("C", {
      x: cx - 0.26, y: cy - 0.26, w: 0.52, h: 0.52, margin: 0,
      align: "center", valign: "middle",
      fontFace: BODY, fontSize: 12, bold: true, color: "16302B"
    });
  };
}

/* A cubic lattice cell, for the engineering deck: eight corners and the
   edges between them, drawn in projection. */
function lattice(p) {
  return (s, cx, cy) => {
    const d = 0.78, o = 0.34;          // cell size, and the depth offset
    const front = [[-d / 2, -d / 2], [d / 2, -d / 2], [d / 2, d / 2], [-d / 2, d / 2]];
    const line = (x1, y1, x2, y2, col, w) => s.addShape(p.ShapeType.line, {
      x: Math.min(x1, x2), y: Math.min(y1, y2),
      w: Math.abs(x2 - x1), h: Math.abs(y2 - y1),
      line: { color: col, width: w }, flipH: x2 < x1, flipV: y2 < y1
    });
    const back = front.map(f => [f[0] + o, f[1] - o]);
    for (let i = 0; i < 4; i++) {
      const j = (i + 1) % 4;
      line(cx + back[i][0], cy + back[i][1], cx + back[j][0], cy + back[j][1], "3F6154", 1.25);
      line(cx + back[i][0], cy + back[i][1], cx + front[i][0], cy + front[i][1], "3F6154", 1.25);
    }
    for (let i = 0; i < 4; i++) {
      const j = (i + 1) % 4;
      line(cx + front[i][0], cy + front[i][1], cx + front[j][0], cy + front[j][1], "6E8C7F", 2);
    }
    back.forEach(b2 => s.addShape(p.ShapeType.ellipse, {
      x: cx + b2[0] - 0.1, y: cy + b2[1] - 0.1, w: 0.2, h: 0.2,
      fill: { color: "5E7D6F" }
    }));
    /* One corner is left empty and filled by the dopant instead: doping is
       substitutional, so the phosphorus takes a silicon's place. Drawn
       floating between sites it would be an interstitial, and would
       contradict the lesson in the pane beside it. */
    front.forEach((f, i) => {
      if (i === 1) return;
      s.addShape(p.ShapeType.ellipse, {
        x: cx + f[0] - 0.13, y: cy + f[1] - 0.13, w: 0.26, h: 0.26,
        fill: { color: "DCE6DF" }
      });
    });
    s.addShape(p.ShapeType.ellipse, {
      x: cx + front[1][0] - 0.17, y: cy + front[1][1] - 0.17, w: 0.34, h: 0.34,
      fill: { color: AMBER }
    });
    s.addText("P", {
      x: cx + front[1][0] - 0.17, y: cy + front[1][1] - 0.17, w: 0.34, h: 0.34,
      margin: 0, align: "center", valign: "middle",
      fontFace: BODY, fontSize: 9.5, bold: true, color: "16302B"
    });
  };
}

function sources(p, K) {
  const s = p.addSlide(); K.light(s);
  K.title(s, "Where the answers come from", "Sources, and their licences");
  K.grid(s, [
    ["1", "NCERT", "Class 6 to 12 Science, Maths, Physics, Chemistry and Biology."],
    ["2", "PhET, University of Colorado", "The interactive simulations, free and open."],
    ["3", "RCSB Protein Data Bank", "Real protein and molecular structures, measured."],
    ["4", "PubChem", "Chemical structures and properties, from the NIH."],
    ["5", "Wikimedia Commons", "Photographs and diagrams, each with its licence shown."],
    ["6", "NASA image library", "Astronomy and earth imagery, public domain."],
    ["7", "Craxlearn measured tables", "The reaction and property tables the lab runs on — never guessed."],
    ["8", "Our own curriculum", "82 lessons of computing and data, written here."]
  ], 2, TOP, 1.06, 0.10, { headSize: 12.5, subSize: 9.8 });
  K.card(s, 0.6, 6.4, 12.1, 0.6, AMBER_SOFT);
  s.addText("The full list, with licences, is public at craxle.com/api/craxlearn/sources — no account needed.", {
    x: 0.9, y: 6.52, w: 11.5, h: 0.36, margin: 0,
    fontFace: BODY, fontSize: 11, bold: true, color: AMBER_INK, lineSpacing: 13.5
  });
  s.addNotes("Procurement asks this first, usually before anyone has an account. That is why it is unauthenticated.");
}

function start(p, K, c) {
  const s = p.addSlide(); K.light(s);
  K.title(s, "What it takes to start", "Getting going");
  const steps = [
    ["1", "You give us the name", "We create the institution and its first administrator account. One call."],
    ["2", "The office sets up", "Classes, staff, subjects. An afternoon, once."],
    ["3", "Codes go out", "One code per class for students, one per subject for whoever teaches it."],
    ["4", "The board goes on", "Open the address on the panel and install it."]
  ];
  const gapX = 0.22, w = (12.1 - gapX * 3) / 4;
  steps.forEach((st, i) => {
    const x = 0.6 + i * (w + gapX);
    K.card(s, x, TOP, w, 1.9);
    K.bead(s, x + 0.24, TOP + 0.2, st[0], 0.48);
    s.addText(st[1], {
      x: x + 0.24, y: TOP + 0.8, w: w - 0.48, h: 0.34, margin: 0,
      fontFace: BODY, fontSize: 12.5, bold: true, color: INK
    });
    s.addText(st[2], {
      x: x + 0.24, y: TOP + 1.16, w: w - 0.48, h: 0.62, margin: 0,
      fontFace: BODY, fontSize: 9.8, color: MUTED, lineSpacing: 12
    });
  });
  K.card(s, 0.6, 3.94, 5.94, 2.4, BOARD);
  K.bead(s, 0.9, 4.2, "$", 0.5, AMBER);
  s.addText(c.pay.head, {
    x: 1.56, y: 4.18, w: 4.7, h: 0.42, margin: 0, valign: "middle",
    fontFace: HEAD, fontSize: 17, bold: true, color: CHALK
  });
  s.addText(c.pay.body, {
    x: 0.9, y: 4.78, w: 5.34, h: 1.36, margin: 0,
    fontFace: BODY, fontSize: 11, color: "C7D6CD", lineSpacing: 15
  });
  K.card(s, 6.76, 3.94, 5.94, 2.4, AMBER_SOFT);
  s.addText("No new hardware", {
    x: 7.06, y: 4.16, w: 5.3, h: 0.34, margin: 0,
    fontFace: HEAD, fontSize: 17, bold: true, color: AMBER_INK
  });
  s.addText([
    { text: "Runs on the panel already in the room", options: { bullet: true, breakLine: true } },
    { text: "Runs on a laptop, tablet or phone for anyone without one", options: { bullet: true, breakLine: true } },
    { text: "Nothing to install on your PCs", options: { bullet: true, breakLine: true } },
    { text: "No server on site, and nobody to maintain it", options: { bullet: true } }
  ], {
    x: 7.1, y: 4.66, w: 5.26, h: 1.5, margin: 0,
    fontFace: BODY, fontSize: 10.5, color: AMBER_INK, paraSpaceAfter: 5, lineSpacing: 13
  });
  s.addNotes("Leave the number for the conversation, not the slide.");
}

function close(p, K, c) {
  const s = p.addSlide(); K.dark(s);
  s.addShape(p.ShapeType.ellipse, { x: -1.6, y: 4.3, w: 4.6, h: 4.6, fill: { color: BOARD2 } });
  s.addShape(p.ShapeType.ellipse, { x: 11.3, y: -1.1, w: 3.6, h: 3.6, fill: { color: BOARD2 } });
  s.addText(c.close.head, {
    x: 1.0, y: 2.1, w: 11.2, h: 1.6, margin: 0,
    fontFace: HEAD, fontSize: 36, bold: true, color: CHALK, lineSpacing: 44
  });
  s.addText(c.close.body, {
    x: 1.04, y: 3.86, w: 9.2, h: 0.9, margin: 0,
    fontFace: BODY, fontSize: 14.5, color: "C7D6CD", lineSpacing: 22
  });
  s.addText("craxle.com/craxlearn", {
    x: 1.04, y: 5.0, w: 7, h: 0.4, margin: 0,
    fontFace: BODY, fontSize: 17, bold: true, color: AMBER
  });
  s.addNotes(c.close.notes);
}

/* ================================================================== */
/* Audience-specific slides                                            */
/* ================================================================== */

function studentSchool(p, K) {
  const s = p.addSlide(); K.light(s);
  K.title(s, "The student", "Who does what");
  K.card(s, 0.6, TOP, 5.36, 4.4, BOARD);
  K.bead(s, 0.9, TOP + 0.26, "*", 0.5, AMBER);
  s.addText("Signing in", {
    x: 1.56, y: TOP + 0.26, w: 4.1, h: 0.44, margin: 0, valign: "middle",
    fontFace: HEAD, fontSize: 19, bold: true, color: CHALK
  });
  s.addText("The student enters the class code and taps their own name on the register. That is the whole sign-in.", {
    x: 0.9, y: TOP + 0.9, w: 4.76, h: 0.76, margin: 0,
    fontFace: BODY, fontSize: 11.5, color: "C7D6CD", lineSpacing: 15
  });
  [["No email address", "Children do not have one, and asking for one creates an account the school cannot see."],
   ["No password to forget", "Nothing to reset in week three in front of the class."],
   ["Sign out, sign back in", "The name stays on the register and taps back into the same account, with the same work on it."],
   ["The register is protected", "Wrong codes are rate-limited per minute, per address, and across the service."]
  ].forEach((r, i) => {
    const y = TOP + 1.76 + i * 0.66;
    s.addText(r[0], {
      x: 0.9, y, w: 4.76, h: 0.24, margin: 0,
      fontFace: BODY, fontSize: 11, bold: true, color: AMBER
    });
    s.addText(r[1], {
      x: 0.9, y: y + 0.23, w: 4.76, h: 0.38, margin: 0,
      fontFace: BODY, fontSize: 9, color: "A9BFB3", lineSpacing: 11
    });
  });
  [["1", "My class", "Their class opens first, not buried under anything else."],
   ["2", "Subjects, and who teaches each", "Tap a subject: the teacher's name, and everything that teacher posted."],
   ["3", "Work to hand in", "What is due, what is closed, and handing it in."],
   ["4", "Ask in the right place", "Under the work, in the subject thread, or straight to that subject's teacher."],
   ["5", "The board's tools on their own device", "Ask Axle, scan a problem from the textbook, the calculator, the 3D structures."]
  ].forEach((r, i) => {
    const y = TOP + i * 0.9;
    K.card(s, 6.18, y, 6.52, 0.78);
    K.bead(s, 6.4, y + 0.17, r[0], 0.44);
    s.addText(r[1], {
      x: 6.96, y: y + 0.06, w: 5.5, h: 0.3, margin: 0, valign: "middle",
      fontFace: BODY, fontSize: 12, bold: true, color: INK
    });
    s.addText(r[2], {
      x: 6.96, y: y + 0.36, w: 5.5, h: 0.34, margin: 0,
      fontFace: BODY, fontSize: 9.3, color: MUTED, lineSpacing: 11.5
    });
  });
  K.foot(s, "A school account never sees the job board or anything commercial. That half of the product does not exist for them.");
  s.addNotes("Demo: hand a parent a phone and have them sign a child in. Two taps.");
}

function studentCollege(p, K) {
  const s = p.addSlide(); K.light(s);
  K.title(s, "The student", "Who does what");
  K.grid(s, [
    ["1", "Sign in with a code, or an account", "Tap a name on the register with the class code, or use an ordinary email account. Both reach the same place."],
    ["2", "Their classes and subjects", "Each subject shows who teaches it and everything that lecturer posted."],
    ["3", "Work to hand in", "What is due, what is closed, and handing it in."],
    ["4", "Ask in the right place", "Under the work, in the subject thread, or straight to that subject's lecturer."],
    ["5", "The board's tools on their own laptop", "Ask Axle at their own level, the sandboxes, the 3D structures, scan a problem."],
    ["6", "The job board, once they are 18", "Real openings from Indian employers, resume matching, and what an ATS sees. Off until they ask for it."]
  ], 2, TOP, 1.3, 0.16, { headSize: 12.5, subSize: 9.8 });
  K.foot(s, "The same account carries them from first year to first application. Nothing is re-entered at the end of it.");
  s.addNotes("For a college this is the slide students will hear about from each other.");
}

function ownMaterial(p, K, c) {
  const s = p.addSlide(); K.light(s);
  K.title(s, "Your syllabus, not somebody else's", "Bring your own material");
  s.addText(
    "No corpus covers every " + c.progName + " in India, and a product that pretends otherwise is one " +
    "a department finds out about in week one. So the material a lecturer already has is a first-class " +
    "input, not a workaround.", {
    x: 0.6, y: TOP, w: 12.1, h: 0.72, margin: 0,
    fontFace: BODY, fontSize: 13, color: MUTED, lineSpacing: 19
  });
  const g = [
    ["1", "Upload the PDF", "A chapter, a paper, a set of notes, a lab manual, last year's question paper."],
    ["2", "Show it exactly as it is", "For when the department's own document is the thing that must be on screen."],
    ["3", "Or have it taught", "Axle writes it up as a lesson: line by line, at the level set, with a diagram where one helps."],
    ["4", "It stays in the subject", "Filed under that subject's study material, there next term, for the next batch too."],
    ["5", "Add links as well", "A paper, a dataset, a repository, a recorded lecture — kept beside the files."],
    ["6", "Anything from the board", "Whatever gets taught on the panel is saved into the same place, automatically."]
  ];
  K.grid(s, g, 3, 2.66, 1.7, 0.18, { headSize: 12.5, subSize: 10 });
  K.foot(s, "Between this, the corpus and the open catalogues, a department is not waiting on us to cover their syllabus.");
  s.addNotes("This is the answer to 'do you cover our syllabus'. The honest answer is: you do, and here is how.");
}

function sandboxes(p, K) {
  const s = p.addSlide(); K.dark(s);
  K.title(s, "Things they can actually break", "Sandboxes", true);
  s.addText(
    "A quiz has a bottom and a B.Tech student finds it in an afternoon. These do not: they are real " +
    "engines with real rules, and the answer comes from running the thing rather than from a table of " +
    "expected responses.", {
    x: 0.6, y: TOP, w: 12.1, h: 0.72, margin: 0,
    fontFace: BODY, fontSize: 12.5, color: "C7D6CD", lineSpacing: 18
  });
  const boxes = [
    ["SQL board", "Write queries against a real database and see what comes back, errors included. Not a multiple-choice question about SQL."],
    ["Trace a packet", "Send a packet through real routing tables and firewall rules and watch each decision as it is taken."],
    ["The lab", "Mix reagents and run experiments. Every reaction comes from a measured table and is never guessed at."],
    ["3D structures", "Molecules, crystals, proteins and orbits, turned and measured. Real coordinates from the open catalogues, not artwork."]
  ];
  const gapX = 0.22, w = (12.1 - gapX) / 2;
  boxes.forEach((b, i) => {
    const c = i % 2, r = Math.floor(i / 2);
    const x = 0.6 + c * (w + gapX), y = 2.68 + r * 1.74;
    K.card(s, x, y, w, 1.58, BOARD2);
    K.bead(s, x + 0.26, y + 0.24, String(i + 1), 0.46);
    s.addText(b[0], {
      x: x + 0.84, y: y + 0.2, w: w - 1.1, h: 0.34, margin: 0, valign: "middle",
      fontFace: BODY, fontSize: 14, bold: true, color: AMBER
    });
    s.addText(b[1], {
      x: x + 0.28, y: y + 0.66, w: w - 0.56, h: 0.84, margin: 0,
      fontFace: BODY, fontSize: 10.5, color: "B4C8BC", lineSpacing: 13.5
    });
  });
  K.foot(s, "All four run on the panel at the front and on a student's own laptop, from the same address.", true);
  s.addNotes("Offer to let a student try to break one. That offer is the pitch.");
}

function placement(p, K) {
  const s = p.addSlide(); K.light(s);
  K.title(s, "The placement half", "Why an institution buys this");
  K.grid(s, [
    ["1", "Real openings, from India", "Fetched from employers' own public hiring systems. Nothing scraped from job aggregators, and nothing outside India."],
    ["2", "Matching, free for every student", "Paste a CV and see it ranked against real openings. Deterministic scoring, no per-student cost."],
    ["3", "What an ATS sees", "The CV as a screening system reads it, and the gaps named as gaps."],
    ["4", "A tracker and apply kits", "Saved and applied roles, and material prepared per application."],
    ["5", "Autofill in the browser", "An extension that fills the employer's own form from the student's stored profile."],
    ["6", "Age-gated, and off by default", "It opens once a student states a date of birth making them 18. Being visible to employers stays off until they turn it on."]
  ], 2, TOP, 1.3, 0.16, { headSize: 12.5, subSize: 9.8 });
  K.foot(s, "The placement cell gets the half a teaching product never has, on accounts the students already hold.");
  s.addNotes("Ask who runs placements and whether they are in the room. If not, ask for a second meeting with them.");
}

function corpusSchool(p, K) {
  const s = p.addSlide(); K.dark(s);
  K.title(s, "Axle answers from the textbook, not from memory", "The AI helper", true);
  const flow = [
    ["1", "The question", "Typed, spoken, or photographed off a page."],
    ["2", "The search", "An index built from NCERT Class 6 to 12 is searched on our server, before any answer is written."],
    ["3", "The passages", "The actual paragraphs from the actual chapter go in with the question."],
    ["4", "The answer", "Written at the level chosen, in lines a room can read, with a diagram where one helps."]
  ];
  const gapX = 0.22, w = (12.1 - gapX * 3) / 4;
  flow.forEach((f, i) => {
    const x = 0.6 + i * (w + gapX);
    K.card(s, x, TOP, w, 2.5, BOARD2);
    K.bead(s, x + 0.26, TOP + 0.22, f[0], 0.48);
    s.addText(f[1], {
      x: x + 0.26, y: TOP + 0.82, w: w - 0.52, h: 0.32, margin: 0,
      fontFace: BODY, fontSize: 13, bold: true, color: CHALK
    });
    s.addText(f[2], {
      x: x + 0.26, y: TOP + 1.2, w: w - 0.52, h: 1.14, margin: 0,
      fontFace: BODY, fontSize: 10, color: "B4C8BC", lineSpacing: 13
    });
  });
  const notes = [
    ["Nothing is invented", "A chapter that will not download is recorded as missing. A corpus holding nine chapters while claiming sixteen is worse than one holding nine and saying so."],
    ["It says where it came from", "Every diagram and structure carries its source and its licence, on screen."],
    ["And your own material", "A teacher's own PDF can be shown as-is or written up as a lesson, filed in that subject."]
  ];
  const w3 = (12.1 - gapX * 2) / 3;
  notes.forEach((r, i) => {
    const x = 0.6 + i * (w3 + gapX);
    K.card(s, x, 4.5, w3, 1.66, BOARD2);
    s.addText(r[0], {
      x: x + 0.26, y: 4.7, w: w3 - 0.52, h: 0.28, margin: 0,
      fontFace: BODY, fontSize: 12.5, bold: true, color: AMBER
    });
    s.addText(r[1], {
      x: x + 0.26, y: 5.02, w: w3 - 0.52, h: 1.0, margin: 0,
      fontFace: BODY, fontSize: 9.6, color: "B4C8BC", lineSpacing: 12
    });
  });
  K.foot(s, "What a student searched or asked is stored scoped to their own school, and never used to source anybody else's answer.", true);
  s.addNotes("Grounding is the answer to 'but AI makes things up'. Show the search step, not the claim.");
}

function corpusCollege(p, K) {
  const s = p.addSlide(); K.dark(s);
  K.title(s, "Three things it stands on", "The AI helper", true);
  const g = [
    ["1", "A searched corpus", "NCERT Class 6 to 12 and our own computing and data curriculum. Where these reach, the passages are searched on our server and go in with the question — written against the source, not out of memory."],
    ["2", "Your own material", "The lecturer's PDF, uploaded and either shown as it is or written up as a lesson. This is what covers a syllabus no public corpus does, and it is already built."],
    ["3", "The open catalogues", "PhET, the Protein Data Bank, PubChem, Wikimedia, NASA. Every picture and structure arrives with its source and its licence attached."]
  ];
  const gapX = 0.22, w = (12.1 - gapX * 2) / 3;
  g.forEach((r, i) => {
    const x = 0.6 + i * (w + gapX);
    K.card(s, x, TOP, w, 3.0, BOARD2);
    K.bead(s, x + 0.28, TOP + 0.24, r[0], 0.5);
    s.addText(r[1], {
      x: x + 0.28, y: TOP + 0.86, w: w - 0.56, h: 0.36, margin: 0,
      fontFace: BODY, fontSize: 14, bold: true, color: AMBER
    });
    s.addText(r[2], {
      x: x + 0.28, y: TOP + 1.28, w: w - 0.56, h: 1.56, margin: 0,
      fontFace: BODY, fontSize: 10.5, color: "B4C8BC", lineSpacing: 13.5
    });
  });
  K.card(s, 0.6, 5.02, 12.1, 1.28, BOARD2);
  s.addText("What we are not claiming", {
    x: 0.92, y: 5.18, w: 11.5, h: 0.3, margin: 0,
    fontFace: BODY, fontSize: 12.5, bold: true, color: AMBER
  });
  s.addText(
    "There is no B.Tech textbook corpus in there today. Degree-level explanations are written at the " +
    "level you set, against your material and the catalogues. NPTEL and MIT OpenCourseWare are next, " +
    "and we would rather say that here than have you find it in week one.", {
    x: 0.92, y: 5.5, w: 11.5, h: 0.66, margin: 0,
    fontFace: BODY, fontSize: 10.5, color: "B4C8BC", lineSpacing: 13.5
  });
  K.foot(s, "What a student searched or asked is stored scoped to their own institution, and never used to source anybody else's answer.", true);
  s.addNotes("Do not soften the bottom band. Saying it is what makes the rest of the deck credible.");
}

/* ================================================================== */
/* Audience content                                                    */
/* ================================================================== */

const SCHOOL = {
  file: "Craxlearn-for-Schools.pptx",
  staffTitle: "The teacher",
  progName: "board",
  cover: {
    kicker: "For Indian schools",
    line: "A smart board that teaches any subject at any level, and the school " +
          "software behind it — classes, teachers, students, work, fees.",
    chips: ["The board", "Teachers", "Students", "The office"],
    notes: "Open on the promise: one thing to buy, four people it serves."
  },
  levels: {
    active: 2,
    title: "Answered for the child in front of you",
    body: "One control on the board. The teacher picks the level and asks the topic — the explanation, " +
          "the vocabulary and the depth all change with it. The same board serves a Class 6 science " +
          "period and a Class 12 physics period.",
    examples: [
      ["Class 6", "Light bends when it moves from air into water. That is why a straw looks broken in a glass."],
      ["Class 10", "Refraction, with the normal, the two media, and Snell's law set out and used on a worked value."],
      ["Class 12", "The same law from Fermat's principle, with the wave picture and the refractive index derived."]
    ],
    foot: "Asked as \"why does a straw look bent in water\" — one topic, three rooms."
  },
  office: {
    title: "The school office",
    items: [
      ["C", "Classes", "Every class and section, each with a join code you can rotate."],
      ["T", "Teachers", "Add teachers once at school level, then pick them inside a class."],
      ["S", "Subjects", "One teacher, many classes, many subjects — assigned per class."],
      ["R", "Students", "Add the roll, or let them join with the code and appear on it."],
      ["N", "Notices", "Post to the whole school, one class, or staff only — with a file attached."],
      ["A", "Attendance", "Marked per class, held per school."],
      ["F", "Fees", "A plan across a class, invoices per student, and who is overdue."],
      ["O", "The school, seen whole", "Money outstanding, requests waiting, and what falls due next."]
    ]
  },
  privacy: {
    kicker: "The part that matters most",
    notes: "If asked about consent mechanics: the school's own admission form is where it is captured today.",
    items: [
      ["1", "Anybody under 18 is a child", "The Act says so and this product treats it that way. A child's data is processed only with verifiable consent from a parent or guardian."],
      ["2", "The school holds the consent", "The institution obtains and holds it and confirms that to us. We act on the school's instructions for those accounts."],
      ["3", "No advertising. None.", "No ad network, no behavioural profiling, no third-party analytics anywhere in the product, for anybody of any age."],
      ["4", "No tracking of children", "Behavioural monitoring of children is forbidden by the Act and is not done here."],
      ["5", "A student can delete their history", "There is a button for it. It is theirs."],
      ["6", "Nothing commercial reaches a child", "The job side is closed to school accounts and to anybody who has not stated they are over 18."]
    ]
  },
  pay: {
    head: "The school pays. Nobody else.",
    body: "One fee from the institution. No per-student charge at the gate, no parent asked for a card, " +
          "no free tier that stops working mid-term, and nothing sold to a child inside a lesson."
  },
  shot: {
    title: "A Class 10 science period, as the room sees it",
    where: "Class 10-A  ·  Science  ·  Mrs Iyer",
    savedTo: "Class 10-A · Science",
    clock: "10:42",
    lesson: {
      title: "Methane, CH₄ — a covalent compound",
      lines: [
        "Carbon has 4 electrons in its outer shell. It needs 4 more to be full.",
        "It cannot lose or gain 4 — that would take far too much energy.",
        "So it SHARES. Four shared pairs, one with each hydrogen.",
        "Each shared pair is one covalent bond, written C–H.",
        "Four bonds, so the formula is CH₄.",
        "The four bonds push apart as far as they can go — 109.5° apart.",
        "That is why methane is a tetrahedron and not a flat cross.",
        "No ions are formed, so methane does not conduct electricity."
      ]
    },
    underline: [[1.42, 3.53, 3.32, 3.53], [1.42, 4.37, 2.80, 4.37]],
    model: "methane",
    modelCaption: "Methane, from PubChem. Real bond angles — turn it and measure one.",
    asked: "Why 109.5 and not 90?",
    answer: [
      "Each bond is a pair of electrons, and electrons repel each other.",
      "Four pairs on a sphere settle where they are furthest apart.",
      "In a flat cross that angle would be 90°.",
      "Lifting into three dimensions opens it to 109.5°.",
      "So the shape is not decoration — it is the repulsion, solved."
    ],
    foot: "Board time runs on IST. The lesson, the model and the answer are all on one panel, and all three save into that class.",
    notes: "Do not read this slide out. Point at the three panes, then offer to do the same thing live with their own topic."
  },
  close: {
    head: "Put it on your board and ask it something",
    body: "Bring a topic from next week's lesson. We will open it on the panel in your own room, " +
          "at the level of the class that sits in it.",
    notes: "Close by asking for a live demo in their room, not for a signature."
  }
};

const COLLEGE = {
  file: "Craxlearn-for-Colleges.pptx",
  staffTitle: "The lecturer",
  progName: "degree syllabus",
  cover: {
    kicker: "For Indian degree colleges",
    line: "A teaching board that works at degree level on your own material, the " +
          "department software behind it, and the placement half your students are here for.",
    chips: ["The board", "Faculty", "Students", "Placement"],
    notes: "For a college the placement half is the differentiator. Do not bury it."
  },
  levels: {
    active: 4,
    title: "It teaches at the level you set, up to research",
    body: "One control on the board. The lecturer sets the level and asks the topic. A first-year " +
          "section and a final-year elective get different explanations of the same thing, from the " +
          "same board, in the same hour.",
    examples: [
      ["Class 12", "The refractive index as a ratio, with Snell's law used on a worked value."],
      ["Undergraduate", "The same law from Fermat's principle, with the wave picture and dispersion set out."],
      ["Research", "Group and phase velocity, anomalous dispersion, and where the simple index stops describing the medium."]
    ],
    foot: "One topic, three years of the same degree."
  },
  office: {
    title: "The college office",
    items: [
      ["C", "Classes and sections", "Create each one, with a join code that can be rotated if it leaks."],
      ["T", "Faculty", "Add lecturers once at institution level, then pick them inside a class."],
      ["S", "Subjects", "Assign a lecturer to a subject. One lecturer, many classes, many subjects."],
      ["R", "Students", "Add the roll, or let students join with the code and appear on the register."],
      ["N", "Notices", "Post to the whole college, one class, or staff only — with a file attached."],
      ["A", "Attendance", "Marked per class, held per institution."],
      ["F", "Fees", "A plan across a class, invoices per student, and who is overdue."],
      ["O", "The college, seen whole", "Money outstanding, requests waiting, and what falls due next."]
    ]
  },
  privacy: {
    kicker: "What a college has to answer for",
    notes: "Most college students are adults, so consent is their own. That is simpler than the school case — say so.",
    items: [
      ["1", "Adults consent for themselves", "Over 18 the student is the data principal. No institutional consent is needed and none is faked."],
      ["2", "Under-18s are still children", "A first-year who is 17 is treated as a child under the Act until their stated date of birth says otherwise."],
      ["3", "No advertising. None.", "No ad network, no behavioural profiling, no third-party analytics anywhere in the product, for anybody of any age."],
      ["4", "The job board is age-gated", "It opens only once a student states a date of birth that makes them 18. Nothing is sold to anyone inside a lecture."],
      ["5", "A student can delete their history", "There is a button for it. It is theirs."],
      ["6", "Resumes go where the student sends them", "Being visible to employers is off by default and stays off until the student turns it on."]
    ]
  },
  pay: {
    head: "The college pays. Nobody else.",
    body: "One fee from the institution, covering teaching and the placement tooling for every enrolled " +
          "student. No per-student charge at the gate, and no card asked of a student inside a lecture."
  },
  shot: {
    title: "A first-year chemistry lecture",
    where: "B.Sc I  ·  Chemistry  ·  Dr Bhaskar",
    savedTo: "B.Sc I · Chemistry",
    clock: "11:15",
    lesson: {
      title: "VSEPR: why molecules have the shapes they have",
      lines: [
        "Electron pairs around a central atom repel one another.",
        "They settle in the arrangement that puts them furthest apart.",
        "Four bonding pairs: tetrahedral, 109.5° (CH₄).",
        "Three bonding and one lone pair: pyramidal, 107° (NH₃).",
        "Two bonding and two lone: bent, 104.5° (H₂O).",
        "A lone pair is fatter than a bonding pair, so it squeezes the rest.",
        "That single fact explains the whole sequence above.",
        "Uploaded from the department's own notes and taught from them."
      ]
    },
    underline: [[1.42, 3.26, 3.50, 3.26], [1.42, 4.64, 3.06, 4.64]],
    model: "methane",
    modelCaption: "Methane, from PubChem. Turn it, measure the angle, then compare with ammonia.",
    asked: "Where does 104.5 come from in water?",
    answer: [
      "Start from the tetrahedral 109.5° of four pairs.",
      "Two of those pairs are lone pairs, held closer to oxygen.",
      "Being closer, they take up more angular room.",
      "They press the two O–H bonds together.",
      "Each lone pair costs roughly two and a half degrees."
    ],
    foot: "The lesson here came from a PDF the department uploaded — the board taught from their notes, not from somebody else's textbook.",
    notes: "Point out the last line of the lesson pane. That is the answer to 'do you cover our syllabus'."
  },
  close: {
    head: "Teach a lecture on it, then look at the placement side",
    body: "Bring a topic from next week and a final-year CV. We will run the lecture on your own panel " +
          "and put the CV through the matching in the same sitting.",
    notes: "Two demos, not one. The lecture wins the department, the CV wins the placement cell."
  }
};

const ENGINEERING = {
  file: "Craxlearn-for-Engineering.pptx",
  staffTitle: "The faculty member",
  progName: "B.Tech branch",
  cover: {
    kicker: "For engineering colleges",
    line: "Sandboxes a B.Tech student cannot exhaust, a board that teaches to research " +
          "level on your own material, and the placement pipeline at the end of it.",
    chips: ["Real labs", "The board", "Courses", "Placement"],
    notes: "This room will push on depth. Lead with the sandboxes, not the board."
  },
  levels: {
    active: 5,
    title: "It does not stop where the syllabus does",
    body: "The level control runs to research, and a student who keeps asking keeps getting further. " +
          "That matters more here than anywhere else: a B.Tech student who has understood the lecture " +
          "has three more questions, and the usual answer to those is nothing at all.",
    examples: [
      ["Undergraduate", "The transistor as a switch, with the transfer characteristic and the two regions that matter."],
      ["Research", "Short-channel effects, subthreshold slope, and why the scaling that used to be free stopped being free."],
      ["Ask again", "And again. Depth is not a fixed number of paragraphs — the next question gets the next layer."]
    ],
    foot: "The board's own level control, from Class 6 to research, on one screen."
  },
  office: {
    title: "The department office",
    items: [
      ["C", "Classes and sections", "Create each one, with a join code that can be rotated if it leaks."],
      ["T", "Faculty", "Add staff once at institution level, then pick them inside a class."],
      ["S", "Subjects", "Assign staff to a subject. One lecturer, many classes, many subjects."],
      ["R", "Students", "Add the roll, or let students join with the code and appear on the register."],
      ["N", "Notices", "Post to the department, one class, or staff only — with a file attached."],
      ["A", "Attendance", "Marked per class, held per institution."],
      ["F", "Fees", "A plan across a class, invoices per student, and who is overdue."],
      ["O", "The department, seen whole", "Money outstanding, requests waiting, and what falls due next."]
    ]
  },
  privacy: {
    kicker: "What an engineering college has to answer for",
    notes: "Same as the college deck: adults consent for themselves, and the job board is age-gated.",
    items: COLLEGE.privacy.items
  },
  pay: COLLEGE.pay,
  shot: {
    title: "A third-year ECE class, as the room sees it",
    where: "B.Tech III  ·  ECE  ·  Semiconductor Devices",
    savedTo: "B.Tech III · Semiconductor Devices",
    clock: "14:30",
    lesson: {
      title: "Doping: making silicon conduct on purpose",
      lines: [
        "Pure silicon has four valence electrons and four neighbours.",
        "Every electron is locked into a bond, so none is free to move.",
        "Replace one silicon atom with phosphorus, which has five.",
        "Four of those electrons bond. The fifth has nowhere to go.",
        "It sits ~45 meV below the conduction band — thermal energy frees it.",
        "One dopant atom in 10⁷ raises conductivity by orders of magnitude.",
        "This is n-type. Boron instead of phosphorus gives p-type.",
        "Put the two together and you have a junction, which is every device."
      ]
    },
    underline: [[1.42, 3.53, 3.60, 3.53], [1.42, 4.64, 3.20, 4.64]],
    model: "lattice",
    modelCaption: "A silicon cell with one phosphorus substitution. Turn it to see which neighbour is short.",
    asked: "Why does 1 in 10^7 change anything?",
    answer: [
      "Intrinsic silicon has ~10¹⁰ carriers per cm³ at room temperature.",
      "Silicon itself has ~5×10²² atoms per cm³.",
      "One dopant in 10⁷ is therefore ~5×10¹⁵ donors per cm³.",
      "That is five orders of magnitude more carriers than were there.",
      "The ratio is the answer — the doping is tiny, the population is tinier."
    ],
    foot: "Ask it the next question and it goes further. This is the point of the level control for a room that will keep pushing.",
    notes: "Let a faculty member ask the follow-up rather than reading the answer pane out."
  },
  close: {
    head: "Give it to your sharpest student for an hour",
    body: "Not a demo we drive. Sit a final-year student in front of the SQL board and the packet engine " +
          "and let them try to reach the bottom of it.",
    notes: "This is the strongest close available in this room. Offer it without hedging."
  }
};

/* ================================================================== */

function build(c, extra) {
  const p = new pptxgen();
  p.layout = "LAYOUT_WIDE";
  const K = kit(p);
  cover(p, K, c);
  extra(p, K, c);
  close(p, K, c);
  return p.writeFile({ fileName: c.file }).then(f => console.log("wrote " + f));
}

const DECKS = {
  schools: () => build(SCHOOL, (p, K, c) => {
    howItWorks(p, K, c); boardShot(p, K, c); surfaces(p, K); levels(p, K, c);
    midLesson(p, K); forStudents(p, K, c); teacher(p, K, c); threePlaces(p, K);
    studentSchool(p, K); office(p, K, c); corpusSchool(p, K); sources(p, K);
    privacy(p, K, c); start(p, K, c);
  }),
  colleges: () => build(COLLEGE, (p, K, c) => {
    howItWorks(p, K, c); boardShot(p, K, c); surfaces(p, K); levels(p, K, c);
    midLesson(p, K); forStudents(p, K, c); ownMaterial(p, K, c); teacher(p, K, c);
    threePlaces(p, K); studentCollege(p, K); office(p, K, c); corpusCollege(p, K);
    sources(p, K); placement(p, K); privacy(p, K, c); start(p, K, c);
  }),
  engineering: () => build(ENGINEERING, (p, K, c) => {
    sandboxes(p, K); boardShot(p, K, c); levels(p, K, c); forStudents(p, K, c);
    ownMaterial(p, K, c); howItWorks(p, K, c); surfaces(p, K); midLesson(p, K);
    teacher(p, K, c); threePlaces(p, K); studentCollege(p, K); office(p, K, c);
    corpusCollege(p, K); sources(p, K); placement(p, K); privacy(p, K, c);
    start(p, K, c);
  })
};

const want = (process.argv[2] || "all").toLowerCase();
const run = want === "all" ? Object.keys(DECKS) : [want];
for (const k of run) {
  if (!DECKS[k]) {
    console.error(`unknown deck: ${k} (schools | colleges | engineering | all)`);
    process.exit(2);
  }
}
(async () => { for (const k of run) await DECKS[k](); })();
