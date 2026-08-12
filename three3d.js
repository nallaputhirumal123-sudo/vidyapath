/* Real 3D, built from parameters rather than downloaded as models.
 *
 * The obvious way to do 3D teaching content is a library of GLB models. That
 * needs every model sourced, licence-checked and hosted, it is tens of
 * megabytes on a phone, and the day somebody asks about a topic nobody bought
 * a model for, there is nothing to show.
 *
 * So these scenes are generated. A molecule is spheres at coordinates joined
 * by cylinders; a MOSFET is doped slabs stacked in order; a crystal is a
 * lattice of points repeated. All of it is arithmetic, which means it renders
 * for any topic the parameters can describe, weighs nothing, and can be
 * emitted by a model as numbers and labels — never as geometry we then have
 * to trust.
 *
 * That is also the honest limit, and it is worth stating plainly: this draws
 * things with structure — molecules, lattices, layer stacks, orbitals,
 * surfaces, solids. It does not draw a human heart. Organic anatomy is
 * genuinely a scanned-mesh problem, and pretending a few ellipsoids are a
 * heart would teach somebody the wrong shape. Where that is what is wanted,
 * the lesson says so rather than showing a lie.
 *
 * Three.js is fetched once, on first use, from this site. If it will not
 * load, the caption and the description still render: a lesson never depends
 * on the picture arriving.
 */
(function () {
  "use strict";

  var THREE = null, loading = null;
  /* From here, not from a CDN, for the same reason KaTeX is.
   *
   * A school network that blocks cdn.jsdelivr.net is not an unusual school
   * network, and the failure is total: the molecule the lesson is about
   * does not appear, on the one screen the whole class is looking at, in
   * the middle of the lesson it was the point of. A filtered network was
   * getting a notice where every other school got a structure to turn
   * around — and it is the schools with the strictest filtering that this
   * is sold into.
   *
   * The same file and the same version: three r160, the minified ES module
   * out of the npm package the CDN URL was pointing at. 670 KB, fetched on
   * first use and never on a page that has no 3D on it.
   *
   * The CDN stays behind it as a second chance, for a deployment where the
   * file did not ship. It is never reached when the first one works, which
   * on a filtered network is exactly the point.
   *
   * The ?v= is the library's own revision, and it changes when the file
   * does — a cache holding last year's three.js against this year's scene
   * code is a bug nobody can reproduce.
   */
  var SRC = "/three.module.js?v=160";
  var SRC_CDN =
    "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";

  function load() {
    if (THREE) return Promise.resolve(THREE);
    if (loading) return loading;
    loading = import(SRC).catch(function () {
      return import(SRC_CDN);
    }).then(function (m) {
      THREE = m;
      return THREE;
    }).catch(function (e) {
      loading = null;
      throw e;
    });
    return loading;
  }

  /* Drag to turn, wheel or pinch to zoom.
   *
   * Written here rather than pulled from three's examples folder, which was
   * the first attempt and did not work: OrbitControls.js imports from the
   * bare specifier "three", so it needs an import map on the page before any
   * module loads. That is a second moving part and a second CDN request to
   * get rotate-and-zoom, which is forty lines of spherical coordinates.
   *
   * It also means one less thing that can be missing when somebody opens a
   * lesson on a bad connection.
   */
  /* How big to draw a scene.
   *
   * A host can ask for the scene to FILL it by carrying data-fill="1". That
   * is for a board, where the space a viewer is in gets dragged to another
   * size in the middle of a lesson and a fixed height is either a small
   * picture on a wall or one taller than the space it was given. Everywhere
   * else keeps the height the scene asked for, so a lesson's figures stay
   * the size they were written to be.
   *
   * Padding is taken off, because clientWidth and clientHeight include it
   * and a canvas sized to them overflows its own box by exactly that much.
   */
  function pad(el, a, b) {
    var cs = getComputedStyle(el);
    return (parseFloat(cs[a]) || 0) + (parseFloat(cs[b]) || 0);
  }
  function hostW(el, fallback) {
    if (el.dataset.fill !== "1") return fallback;
    var w = el.clientWidth - pad(el, "paddingLeft", "paddingRight");
    return w > 40 ? Math.round(w) : fallback;
  }
  function hostH(el, fallback) {
    if (el.dataset.fill !== "1") return fallback;
    var h = el.clientHeight - pad(el, "paddingTop", "paddingBottom");
    return h > 40 ? Math.round(h) : fallback;
  }

  function orbit(cam, dom, radius) {
    // phi is measured down from straight up, so 0.44pi opens about ten
    // degrees above the horizon — almost side-on. It was 0.35pi, looking down
    // at 27 degrees, which foreshortened every layer stack in the library
    // into a flat slab and hid the one thing those scenes exist to show.
    var st = { r: radius, theta: Math.PI * 0.22, phi: Math.PI * 0.44,
               drag: false, x: 0, y: 0, min: radius * 0.4, max: radius * 5,
               dragging: false };

    function apply() {
      st.phi = Math.max(0.08, Math.min(Math.PI - 0.08, st.phi));
      st.r = Math.max(st.min, Math.min(st.max, st.r));
      cam.position.set(
        st.r * Math.sin(st.phi) * Math.sin(st.theta),
        st.r * Math.cos(st.phi),
        st.r * Math.sin(st.phi) * Math.cos(st.theta));
      cam.lookAt(0, 0, 0);
    }

    function down(e) {
      st.drag = true; st.dragging = true;
      st.x = e.clientX; st.y = e.clientY;
      dom.setPointerCapture && dom.setPointerCapture(e.pointerId);
    }
    function move(e) {
      if (!st.drag) return;
      st.theta -= (e.clientX - st.x) * 0.008;
      st.phi -= (e.clientY - st.y) * 0.008;
      st.x = e.clientX; st.y = e.clientY;
      apply();
    }
    function up() { st.drag = false; setTimeout(function () {
      st.dragging = false; }, 900); }
    function wheel(e) {
      // Only when the pointer is over the canvas, and only then do we take
      // the scroll — a diagram that hijacks the page scroll as you pass it is
      // infuriating on a phone.
      e.preventDefault();
      st.r *= e.deltaY > 0 ? 1.09 : 0.92;
      apply();
    }

    var pinch = 0;
    function touch(e) {
      if (e.touches.length !== 2) { pinch = 0; return; }
      var dx = e.touches[0].clientX - e.touches[1].clientX;
      var dy = e.touches[0].clientY - e.touches[1].clientY;
      var d = Math.hypot(dx, dy);
      if (pinch) { st.r *= pinch / d; apply(); }
      pinch = d;
      e.preventDefault();
    }

    dom.style.touchAction = "none";
    dom.addEventListener("pointerdown", down);
    dom.addEventListener("pointermove", move);
    dom.addEventListener("pointerup", up);
    dom.addEventListener("pointercancel", up);
    dom.addEventListener("wheel", wheel, { passive: false });
    dom.addEventListener("touchmove", touch, { passive: false });
    apply();

    return {
      get isDragging() { return st.dragging; },
      setRange: function (lo, hi) { st.min = lo; st.max = hi; },
      update: function () {},
      dispose: function () {
        dom.removeEventListener("pointerdown", down);
        dom.removeEventListener("pointermove", move);
        dom.removeEventListener("pointerup", up);
        dom.removeEventListener("pointercancel", up);
        dom.removeEventListener("wheel", wheel);
        dom.removeEventListener("touchmove", touch);
      }
    };
  }

  /* ---- palettes ----------------------------------------------------- *
   * CPK for atoms, because a chemist reading this expects oxygen to be red
   * and will misread it otherwise. Everything else is picked for contrast on
   * a dark board. */
  var CPK = {
    H: 0xf2f2f2, C: 0x3a3a3a, N: 0x3050f8, O: 0xff0d0d, F: 0x90e050,
    P: 0xff8000, S: 0xffff30, Cl: 0x1ff01f, Si: 0xf0c8a0, Na: 0xab5cf2,
    Mg: 0x8aff00, K: 0x8f40d4, Ca: 0x3dff00, Fe: 0xe06633, Zn: 0x7d80b0,
    Cu: 0xc88033, Ga: 0xc28f8f, As: 0xbd80e3, Ge: 0x668f8f, B: 0xffb5b5
  };
  var RADIUS = {
    H: 0.32, C: 0.55, N: 0.52, O: 0.5, F: 0.45, P: 0.7, S: 0.68, Cl: 0.65,
    Si: 0.78, Ge: 0.8, Ga: 0.8, As: 0.75
  };
  // Doped silicon and its neighbours, for the semiconductor stacks.
  var LAYERC = {
    "n": 0x4a90d9, "n+": 0x2d6fb8, "p": 0xd96f4a, "p+": 0xb8492d,
    "oxide": 0x9aa7b0, "metal": 0xd8d8d8, "poly": 0xc9a227,
    "substrate": 0x5a5a5a, "gate": 0xc9a227, "": 0x7a8a99
  };

  function colourFor(label) {
    var k = String(label || "").toLowerCase();
    var hit = Object.keys(LAYERC).filter(function (n) {
      return n && k.indexOf(n) === 0;
    }).sort(function (a, b) { return b.length - a.length; })[0];
    return LAYERC[hit || ""];
  }

  /* ---- scene builders ------------------------------------------------ */
  var BUILD = {};

  /* Atoms and bonds. Coordinates in ångström-ish units; the camera frames
     whatever it is given, so a water molecule and a protein fragment both
     arrive on screen the right size. */
  BUILD.molecule = function (spec, group) {
    var atoms = spec.atoms || [];
    atoms.forEach(function (a) {
      var el = a.el || "C";
      var r = RADIUS[el] || 0.6;
      var m = new THREE.Mesh(
        new THREE.SphereGeometry(r, 26, 18),
        new THREE.MeshStandardMaterial({
          color: CPK[el] === undefined ? 0x9aa7b0 : CPK[el],
          roughness: 0.42, metalness: 0.05
        }));
      m.position.set(a.x || 0, a.y || 0, a.z || 0);
      group.add(m);
      if (a.el) label(group, el, a.x || 0, (a.y || 0) + r + 0.32, a.z || 0);
    });
    (spec.bonds || []).forEach(function (b) {
      var A = atoms[b[0]], B = atoms[b[1]];
      if (!A || !B) return;
      var order = b[2] || 1;
      // A double bond drawn as one fat cylinder is a single bond that looks
      // wrong; drawn as two thin ones it reads correctly at a glance.
      for (var k = 0; k < Math.min(order, 3); k++) {
        var off = (k - (Math.min(order, 3) - 1) / 2) * 0.16;
        bond(group, A, B, off);
      }
    });
  };

  function bond(group, A, B, off) {
    var a = new THREE.Vector3(A.x || 0, A.y || 0, A.z || 0);
    var b = new THREE.Vector3(B.x || 0, B.y || 0, B.z || 0);
    var d = new THREE.Vector3().subVectors(b, a);
    var len = d.length();
    if (!len) return;
    var g = new THREE.CylinderGeometry(0.09, 0.09, len, 14);
    var m = new THREE.Mesh(g, new THREE.MeshStandardMaterial({
      color: 0xbfc7cf, roughness: 0.5 }));
    m.position.copy(a).add(b).multiplyScalar(0.5);
    m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.clone().normalize());
    if (off) {
      var perp = new THREE.Vector3(0, 0, 1).cross(d).normalize();
      if (!perp.length()) perp = new THREE.Vector3(1, 0, 0);
      m.position.add(perp.multiplyScalar(off));
    }
    group.add(m);
  }

  /* A stack of slabs, bottom to top. This is the one the chip people need:
     a MOSFET cross-section, a photodiode, a deposition stack — and it is the
     same builder as geological strata or a battery, because "labelled layers
     in order, with thicknesses" is the same picture in every subject. */
  BUILD.layers = function (spec, group) {
    var y = 0, W = 6, D = 4;
    (spec.layers || []).forEach(function (L) {
      var h = Math.max(0.16, Math.min(3, L.t || 0.5));
      var m = new THREE.Mesh(
        new THREE.BoxGeometry(L.w ? Math.min(W, L.w) : W, h, D),
        new THREE.MeshStandardMaterial({
          color: L.color !== undefined ? L.color : colourFor(L.name),
          roughness: 0.55, metalness: 0.15,
          transparent: !!L.clear, opacity: L.clear ? 0.45 : 1
        }));
      m.position.set(L.x || 0, y + h / 2, 0);
      group.add(m);
      group.add(new THREE.LineSegments(
        new THREE.EdgesGeometry(m.geometry),
        new THREE.LineBasicMaterial({ color: 0x000000, opacity: 0.28,
                                      transparent: true })
      ).translateX(L.x || 0).translateY(y + h / 2));
      // The real thickness, where the stack is a measured one. The drawn
      // height is a logarithm — a gate oxide and a wafer differ by a factor
      // of a quarter of a million and cannot share a linear picture — so the
      // true figure has to be written down or the compression becomes the
      // claim being made.
      if (L.name) {
        label(group, L.real ? (L.name + "  —  " + L.real) : L.name,
              (L.x || 0) + W / 2 + 0.55, y + h / 2, 0);
      }
      y += h;
    });
  };

  /* A repeating cell — silicon's diamond cubic, a metal's FCC, table salt.
     Materials science and anything about why a crystal behaves as it does. */
  BUILD.lattice = function (spec, group) {
    var n = Math.max(1, Math.min(4, spec.repeat || 2));
    var a = spec.a || 2;
    var basis = spec.basis || [{ x: 0, y: 0, z: 0, el: "Si" }];
    for (var i = 0; i < n; i++) {
      for (var j = 0; j < n; j++) {
        for (var k = 0; k < n; k++) {
          basis.forEach(function (b) {
            var m = new THREE.Mesh(
              new THREE.SphereGeometry(RADIUS[b.el] || 0.42, 20, 14),
              new THREE.MeshStandardMaterial({
                color: CPK[b.el] === undefined ? 0x8fb8d9 : CPK[b.el],
                roughness: 0.4 }));
            m.position.set((i + (b.x || 0)) * a, (j + (b.y || 0)) * a,
                           (k + (b.z || 0)) * a);
            group.add(m);
          });
        }
      }
    }
    // The cell outline, so you can see what is actually repeating.
    var box = new THREE.Box3().setFromObject(group);
    group.add(new THREE.Box3Helper(box, 0xffb020));

    /* The measured facts, when the structure is one that gets taught.
     *
     * The lattice constant and the coordination number are the lesson: rock
     * salt and caesium chloride look similar at a glance and differ in
     * exactly these two numbers. They come from a table of real values, not
     * from the model, so they are worth putting on the picture.
     *
     * a_angstrom is the real cell edge; spec.a is how big it is drawn. Those
     * are different numbers on purpose and only the first is a fact. */
    if (spec.measured) {
      var top = box.max.y + 0.7;
      if (spec.structure) label(group, spec.structure, 0, top + 0.7, 0);
      if (spec.a_angstrom) {
        label(group, "a = " + spec.a_angstrom + " Å", 0, top, 0);
      }
      if (spec.coordination) {
        label(group, "coordination " + spec.coordination,
              0, box.min.y - 0.7, 0);
      }
    }
  };

  /* z = f(x, y). Every optimisation surface, every wave, every potential
     well, and the only honest way to show a saddle point. */
  /* A macromolecule, drawn the way structural biology draws one.
   *
   * Every atom as a sphere is right for caffeine and useless for
   * haemoglobin: four and a half thousand spheres arrive as an indistinct
   * ball, and the thing worth seeing — four folded chains around four haem
   * groups — is exactly what disappears.
   *
   * So this is a backbone trace: one point per residue, from the server,
   * pulled through a smooth curve and swept into a tube. One colour per
   * chain, because the chains are usually the lesson.
   *
   * The coordinates are crystallographic. Nothing here invents a position;
   * the curve only decides how to travel between measured points. */
  BUILD.protein = function (spec, group) {
    var traces = spec.traces || [];
    // Scale the whole assembly to a consistent size on screen. A ribosome
    // and a ubiquitin differ by a factor of thirty in ångström and should
    // arrive looking like objects of comparable size on a board.
    var span = spec.span || 20;
    var k = 9 / span;
    // A thinner tube for a big structure, or the folds merge into a blob.
    var radius = Math.max(0.10, Math.min(0.42, 26 / (spec.residues || 200)));

    traces.forEach(function (t, i) {
      var pts = (t.points || []).map(function (p) {
        return new THREE.Vector3(p[0] * k, p[1] * k, p[2] * k);
      });
      if (pts.length < 3) return;
      var curve = new THREE.CatmullRomCurve3(pts, false, "centripetal", 0.5);
      // Enough segments to follow a helix, capped so a large assembly does
      // not build a hundred thousand triangles on a phone.
      var seg = Math.max(24, Math.min(pts.length * 4, 1600));
      var geo = new THREE.TubeGeometry(curve, seg, radius, 8, false);
      group.add(new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
        color: t.color === undefined ? 0x4FC3F7 : t.color,
        roughness: 0.45, metalness: 0.05
      })));
      // Where each chain starts, so a four-chain assembly can be read.
      if (t.chain && traces.length > 1) {
        label(group, t.chain, pts[0].x, pts[0].y + 0.6, pts[0].z);
      }
    });
  };

  BUILD.surface = function (spec, group) {
    /* Two ways to get a height, and the first is the real one.
     *
     * spec.z is a grid the server computed by evaluating the lesson's own
     * function at each point. It arrives as plain numbers — no expression is
     * ever sent here and nothing is evaluated in the browser. The six named
     * shapes below remain only as the fallback for a lesson that named a
     * shape instead of stating a function.
     *
     * A null in the grid means the function has no real value there, which
     * is a fact about the function: sqrt(9 - x² - y²) is a hemisphere with
     * nothing outside the circle. Those points are pushed out of range so
     * the mesh does not weld a flat lid across a hole that is really there. */
    var N = 46, S = spec.span || 4;
    var grid = spec.z;
    if (grid && grid.length > 1) N = grid.length - 1;
    var g = new THREE.PlaneGeometry(S * 2, S * 2, N, N);
    var fn = FUNCS[spec.fn] || FUNCS.saddle;
    var p = g.attributes.position;

    // Keep the drawn range proportionate to the function's own range, so a
    // surface spanning 0..0.001 is not rendered as a flat sheet and one
    // spanning 0..25 is not a spike with everything else crushed flat.
    var lo = Infinity, hi = -Infinity;
    if (grid) {
      for (var r = 0; r < grid.length; r++) {
        for (var c = 0; c < grid[r].length; c++) {
          var v = grid[r][c];
          if (v === null || v === undefined) continue;
          if (v < lo) lo = v;
          if (v > hi) hi = v;
        }
      }
    }
    var scale = 1;
    if (grid && hi > lo) scale = Math.min(1, (S * 1.1) / (hi - lo));

    var hole = {};
    for (var i = 0; i < p.count; i++) {
      var x = p.getX(i), y = p.getY(i);
      if (grid) {
        // PlaneGeometry runs its vertices row by row from +y down to -y.
        var col = i % (N + 1), row = (i - col) / (N + 1);
        var gv = (grid[grid.length - 1 - row] || [])[col];
        if (gv === null || gv === undefined) {
          hole[i] = 1;
          p.setZ(i, 0);
        } else {
          p.setZ(i, (gv - (lo + hi) / 2) * scale);
        }
        continue;
      }
      p.setZ(i, Math.max(-6, Math.min(6, fn(x, y))));
    }

    /* Drop the triangles that touch a hole.
     *
     * A NaN position would be the obvious way to punch a hole and it is the
     * wrong one: it propagates through computeVertexNormals and the entire
     * mesh disappears. Removing the faces instead leaves the surface exactly
     * where the function is defined and nothing where it is not, which is
     * what a hemisphere should look like. */
    if (grid && g.index) {
      var idx = g.index.array, keep = [];
      for (var t = 0; t < idx.length; t += 3) {
        if (hole[idx[t]] || hole[idx[t + 1]] || hole[idx[t + 2]]) continue;
        keep.push(idx[t], idx[t + 1], idx[t + 2]);
      }
      if (keep.length && keep.length < idx.length) g.setIndex(keep);
    }
    g.computeVertexNormals();
    g.rotateX(-Math.PI / 2);
    group.add(new THREE.Mesh(g, new THREE.MeshStandardMaterial({
      color: 0x4a90d9, roughness: 0.55, side: THREE.DoubleSide,
      flatShading: false })));
    group.add(new THREE.Mesh(g, new THREE.MeshBasicMaterial({
      color: 0xeafff2, wireframe: true, transparent: true, opacity: 0.14 })));
  };

  // Named rather than evaluated. A model that can send a formula to run is a
  // model that can send anything to run, and eval on generated content is how
  // a teaching aid becomes a security hole.
  var FUNCS = {
    saddle: function (x, y) { return (x * x - y * y) / 4; },
    bowl: function (x, y) { return (x * x + y * y) / 5; },
    dome: function (x, y) { return 4 - (x * x + y * y) / 4; },
    ripple: function (x, y) {
      var r = Math.sqrt(x * x + y * y);
      return Math.cos(r * 2) * 1.6 / (1 + r * 0.5);
    },
    well: function (x, y) {
      var r = x * x + y * y;
      return -4 / (1 + r * 0.6);
    },
    plane: function (x, y) { return x * 0.4 + y * 0.2; }
  };

  /* Bodies on orbits. Astronomy, and the electron shells that chemistry
     draws even though it knows they are not really rings. */
  BUILD.orbit = function (spec, group) {
    group.add(new THREE.Mesh(
      new THREE.SphereGeometry(spec.centre_r || 0.9, 30, 22),
      new THREE.MeshStandardMaterial({
        color: spec.centre_color || 0xffcc55,
        emissive: spec.centre_color || 0xffcc55, emissiveIntensity: 0.45 })));
    if (spec.centre) label(group, spec.centre, 0, (spec.centre_r || 0.9) + 0.5, 0);
    (spec.bodies || []).forEach(function (b, i) {
      var r = b.r || (2 + i * 1.3);
      var pts = [];
      for (var t = 0; t <= 64; t++) {
        var th = (t / 64) * Math.PI * 2;
        pts.push(new THREE.Vector3(Math.cos(th) * r, 0, Math.sin(th) * r));
      }
      group.add(new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(pts),
        new THREE.LineBasicMaterial({ color: 0x8fa3b0, transparent: true,
                                      opacity: 0.55 })));
      // The measured figures, where we have them. The ring is drawn on the
      // square root of the true distance so the system fits a screen, so the
      // real number has to be written down or the compression becomes the
      // claim.
      if (b.au) {
        label(group, b.name + "  " + b.au + " AU, " + b.years + " yr",
              r + 0.1, 0.55, 0);
      }
      var m = new THREE.Mesh(
        new THREE.SphereGeometry(b.size || 0.3, 22, 16),
        new THREE.MeshStandardMaterial({ color: b.color || 0x7fb8ff,
                                         roughness: 0.5 }));
      var a0 = (i * 1.1);
      m.position.set(Math.cos(a0) * r, 0, Math.sin(a0) * r);
      m.userData.spin = { r: r, speed: b.speed || (0.5 / Math.sqrt(r)), t: a0 };
      group.add(m);
      if (b.name) label(group, b.name, m.position.x, (b.size || 0.3) + 0.45,
                        m.position.z);
    });
  };

  /* Plain solids, for geometry and for anything that is simply a shape. */
  /* A solid, with the numbers that make it worth showing.
   *
   * This drew nine shapes at a fixed size and put nothing on them. A cube
   * with no edge length teaches "this is a cube", which the word already
   * did — the reason a geometry lesson shows a solid at all is the
   * relationship between its dimensions and its volume and surface area.
   *
   * The measurements are computed on the server from the stated size, by the
   * formula the lesson is teaching, so they are exact and cannot disagree
   * with the shape beside them. The geometry here is built at that same size,
   * so the picture and the numbers describe one object.
   *
   * The cylinder and the cone are drawn with height twice the radius,
   * because that is what the server assumed when it worked out the volume.
   */
  BUILD.solid = function (spec, group) {
    var a = spec.size || 1;
    // Everything is drawn relative to a, then the camera frames it, so a
    // solid of side 3 and one of side 300 both arrive the right size.
    var G = {
      cube: function () { return new THREE.BoxGeometry(a, a, a); },
      sphere: function () { return new THREE.SphereGeometry(a, 40, 26); },
      cylinder: function () { return new THREE.CylinderGeometry(a, a, 2 * a, 40); },
      cone: function () { return new THREE.ConeGeometry(a, 2 * a, 40); },
      torus: function () { return new THREE.TorusGeometry(a, a * 0.35, 22, 48); },
      tetra: function () { return new THREE.TetrahedronGeometry(a * 0.61); },
      octa: function () { return new THREE.OctahedronGeometry(a * 0.71); },
      icosa: function () { return new THREE.IcosahedronGeometry(a * 0.95); },
      prism: function () { return new THREE.CylinderGeometry(a * 0.58, a * 0.58, 2 * a, 3); }
    };
    var mk = G[spec.shape] || G.cube;
    var geo = mk();
    group.add(new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
      color: spec.color || 0x4a90d9, roughness: 0.45,
      transparent: true, opacity: 0.8 })));
    group.add(new THREE.LineSegments(new THREE.EdgesGeometry(geo),
      new THREE.LineBasicMaterial({ color: 0xeafff2 })));

    var m = spec.measures;
    if (!m) return;
    var unit = spec.unit || "unit";
    // The defining length, on the solid, where a textbook would put it.
    label(group, m.of + " = " + trim(a) + " " + unit, 0, -a * 1.15, 0);
    // And what follows from it. Stacked above so they read as a pair.
    label(group, "V = " + trim(m.volume) + " " + unit + "\u00b3",
          0, a * 1.32, 0);
    label(group, "A = " + trim(m.area) + " " + unit + "\u00b2",
          0, a * 1.05, 0);
  };

  /* 27, not 27.0000; 113.1, not 113.0973. A volume printed to four decimals
     is a number nobody reads. */
  function trim(v) {
    var n = Number(v);
    if (!isFinite(n)) return String(v);
    if (Math.abs(n - Math.round(n)) < 1e-9) return String(Math.round(n));
    return String(Math.round(n * 100) / 100);
  }

  /* A process: stations with something moving between them.
   *
   * This is the kind that was missing, and its absence showed. Asked about
   * photosynthesis the model reached for "molecule" — the only kind that
   * could hold anything biological — and drew the magnesium and nitrogen of
   * a chlorophyll molecule. Correct atoms, and an answer to a question nobody
   * asked: photosynthesis is a sequence, and none of the other five kinds can
   * draw a sequence.
   *
   * Laid out as a ring when the last stage feeds the first, and as a line
   * when it runs start to finish, because that difference is most of what
   * somebody needs to understand about a cycle. The pulses travelling the
   * arrows carry the label of what actually flows.
   */
  BUILD.process = function (spec, group) {
    var st = spec.stages || [], n = st.length;
    var cycle = spec.layout === "cycle";
    // Wider than it looks like it needs to be. The text is what has to fit,
    // not the discs.
    var R = Math.max(4.4, n * 1.25);
    var GAP = 4.6;
    var pos = st.map(function (_, i) {
      if (cycle) {
        var a = (i / n) * Math.PI * 2 - Math.PI / 2;
        return new THREE.Vector3(Math.cos(a) * R, 0, Math.sin(a) * R);
      }
      return new THREE.Vector3((i - (n - 1) / 2) * GAP, 0, 0);
    });

    pos.forEach(function (p, i) {
      // A disc rather than a box: a station on a route, not a component.
      var m = new THREE.Mesh(
        new THREE.CylinderGeometry(1.05, 1.05, 0.34, 40),
        new THREE.MeshStandardMaterial({
          color: cycle ? 0x3f8f6a : 0x3a6ea8, roughness: 0.4,
          metalness: 0.1 }));
      m.position.copy(p);
      group.add(m);
      group.add(new THREE.Mesh(
        new THREE.TorusGeometry(1.05, 0.05, 10, 44),
        new THREE.MeshBasicMaterial({ color: 0xeafff2 })
      ).rotateX(Math.PI / 2).translateOnAxis(new THREE.Vector3(0, 0, 0), 0)
       .translateX(p.x).translateY(p.y + 0.18).translateZ(p.z));
      label(group, String(i + 1), p.x, p.y + 0.42, p.z);
      // Two lines rather than one long one, and alternating heights so a
      // stage never sits at the same level as the one beside it.
      var lift = 1.35 + (i % 2) * 0.62;
      wrapLabel(st[i].name, 15).forEach(function (line, k) {
        label(group, line, p.x, p.y + lift + k * 0.42, p.z);
      });
    });

    // The arrows, and what travels along them.
    var links = [];
    for (var i = 0; i < n - (cycle ? 0 : 1); i++) {
      links.push([i, (i + 1) % n]);
    }
    links.forEach(function (L) {
      var a = pos[L[0]], b = pos[L[1]];
      var dir = new THREE.Vector3().subVectors(b, a);
      var len = dir.length() - 2.1;                 // stop short of the discs
      if (len <= 0.2) return;
      var mid = new THREE.Vector3().addVectors(a, b).multiplyScalar(0.5);
      var shaft = new THREE.Mesh(
        new THREE.CylinderGeometry(0.05, 0.05, len, 10),
        new THREE.MeshBasicMaterial({ color: 0xffb020, transparent: true,
                                      opacity: 0.65 }));
      shaft.position.copy(mid);
      shaft.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0),
                                          dir.clone().normalize());
      group.add(shaft);

      var head = new THREE.Mesh(
        new THREE.ConeGeometry(0.16, 0.42, 14),
        new THREE.MeshBasicMaterial({ color: 0xffb020 }));
      head.position.copy(b).addScaledVector(dir.clone().normalize(), -1.15);
      head.quaternion.copy(shaft.quaternion);
      group.add(head);

      // What passes along this arrow — the whole point of the picture.
      var carried = st[L[0]].out || st[L[1]]["in"];
      if (carried) {
        label(group, carried.length > 18 ? carried.slice(0, 17) + "\u2026"
                                         : carried,
              mid.x, mid.y - 0.55, mid.z);
      }

      var pulse = new THREE.Mesh(
        new THREE.SphereGeometry(0.15, 14, 10),
        new THREE.MeshBasicMaterial({ color: 0xffe6a1 }));
      pulse.userData.flow = { a: a.clone(), b: b.clone(),
                              t: Math.random(), speed: 0.35 };
      group.add(pulse);
    });

    if (st[0] && st[0]["in"]) {
      label(group, "in: " + st[0]["in"], pos[0].x, pos[0].y - 1.45, pos[0].z);
    }
    var last = st[n - 1];
    if (!cycle && last && last.out) {
      label(group, "out: " + last.out, pos[n - 1].x,
            pos[n - 1].y - 1.45, pos[n - 1].z);
    }
  };

  /* ---- the thing itself, with what goes in and comes out ------------
   *
   * The process kind draws stations and arrows, which is right for a cycle
   * and wrong for photosynthesis. Nobody understands photosynthesis from four
   * labelled discs. They understand it from a leaf with sunlight falling on
   * it, carbon dioxide and water going in, and oxygen and sugar coming out —
   * the object, and the traffic around the object.
   *
   * So the bodies here are real shapes, built from curves rather than boxes:
   * a leaf is a leaf, not a green rectangle. Only shapes that can be made
   * honestly this way are offered. An organ with real anatomy is still a
   * scanned-mesh problem and still says so.
   */
  var BODY = {};

  /* A leaf, cut open.
   *
   * The first version was the outline of a leaf, and the outline of a leaf is
   * not where photosynthesis happens. What teaches it is the section: waxy
   * cuticle on top, the epidermis under it, the palisade cells standing on
   * end where most of the chloroplasts are, the loose spongy layer below them
   * with the air spaces the gases move through, and the stomata underneath
   * that let them in and out. That is the structure, and the structure is the
   * explanation — every layer is there for a reason you can point at.
   *
   * So the blade is half transparent and the section sits inside it, cut
   * away, with the layers labelled where they are rather than in a key.
   */
  BODY.leaf = function () {
    var g = new THREE.Group();
    var sh = new THREE.Shape();
    sh.moveTo(0, -2.2);
    sh.bezierCurveTo(1.9, -1.1, 1.6, 1.4, 0, 2.4);
    sh.bezierCurveTo(-1.6, 1.4, -1.9, -1.1, 0, -2.2);
    var blade = new THREE.Mesh(
      new THREE.ExtrudeGeometry(sh, { depth: 0.09, bevelEnabled: true,
        bevelSize: 0.05, bevelThickness: 0.04, bevelSegments: 2 }),
      new THREE.MeshStandardMaterial({ color: 0x3f9d54, roughness: 0.6,
        side: THREE.DoubleSide, transparent: true, opacity: 0.45 }));
    blade.rotation.x = -Math.PI / 2.35;
    g.add(blade);

    // The cut section, standing beside the blade so both are readable at once.
    var sec = new THREE.Group();
    // Below the blade, not beside it. Beside it put the section between x=2.9
    // and x=6.3, which is exactly where the outgoing stream's labels sit —
    // "glucose" and "oxygen" landed on top of "cuticle" and "palisade
    // mesophyll". The traffic runs left to right, so the section goes down.
    sec.position.set(0, -3.6, 0);
    // Names only. The first version put a description under each layer as
    // well, which doubled the number of labels in a section a couple of units
    // tall — they all landed on top of one another and the structure was
    // buried under its own captions. What each layer does belongs in the
    // step's text; the picture's job is to show where it is.
    var LAYERS = [
      ["cuticle", 0.28, 0xd8e8c0],
      ["upper epidermis", 0.48, 0x8fd18f],
      ["palisade mesophyll", 1.45, 0x2f8f45],
      ["spongy mesophyll", 1.25, 0x63b878],
      ["lower epidermis", 0.48, 0x8fd18f]
    ];
    // Slabs first, remembering where the middle of each one is.
    var y = 0, mids = [];
    LAYERS.forEach(function (L) {
      var h = L[1];
      var slab = new THREE.Mesh(
        new THREE.BoxGeometry(3.4, h, 2.0),
        new THREE.MeshStandardMaterial({ color: L[2], roughness: 0.62 }));
      slab.position.y = -y - h / 2;
      sec.add(slab);
      sec.add(new THREE.LineSegments(new THREE.EdgesGeometry(slab.geometry),
        new THREE.LineBasicMaterial({ color: 0x14301c, transparent: true,
          opacity: 0.45 })).translateY(-y - h / 2));
      mids.push(-y - h / 2);
      y += h;
    });

    // Labels fanned out evenly, with a leader line back to the layer each one
    // names. Placed at their layer's own height they were 0.2 units apart on
    // the thin ones — cuticle, upper epidermis and palisade all landed on top
    // of each other. Even spacing plus a line is how a textbook annotates a
    // section, and for exactly this reason.
    var top = mids[0] + 0.5, step = (top - (mids[mids.length - 1] - 0.5))
      / Math.max(1, mids.length - 1);
    mids.forEach(function (my, i) {
      var ly = top - i * step;
      label(sec, LAYERS[i][0], 4.4, ly, 0);
      sec.add(new THREE.Line(
        new THREE.BufferGeometry().setFromPoints([
          new THREE.Vector3(1.75, my, 0),
          new THREE.Vector3(2.6, ly, 0),
          new THREE.Vector3(3.1, ly, 0)]),
        new THREE.LineBasicMaterial({ color: LAYERS[i][2], transparent: true,
          opacity: 0.95 })));
      // A dot on the layer itself, same colour, so the line has a visible
      // origin instead of appearing to start in mid-air.
      sec.add(new THREE.Mesh(new THREE.SphereGeometry(0.075, 10, 8),
        new THREE.MeshBasicMaterial({ color: LAYERS[i][2] })
      ).translateX(1.75).translateY(my));
    });

    // Chloroplasts, packed in the palisade layer where they actually are.
    for (var c = 0; c < 14; c++) {
      var ch = new THREE.Mesh(new THREE.SphereGeometry(0.075, 10, 8),
        new THREE.MeshStandardMaterial({ color: 0x0f5c25, roughness: 0.4 }));
      ch.scale.set(1, 0.7, 1);
      ch.position.set(-1.4 + (c % 7) * 0.45, -0.75 - Math.floor(c / 7) * 0.3,
                      -0.4 + (c % 3) * 0.4);
      sec.add(ch);
    }
    label(sec, "chloroplasts", -2.7, -0.75, 0);

    // Stomata on the underside: the holes the gases actually pass through.
    for (var st2 = 0; st2 < 3; st2++) {
      var pore = new THREE.Mesh(
        new THREE.TorusGeometry(0.13, 0.045, 8, 18),
        new THREE.MeshStandardMaterial({ color: 0x2c6b3c }));
      pore.rotation.x = Math.PI / 2;
      pore.position.set(-0.9 + st2 * 0.9, -y + 0.02, 0.3);
      sec.add(pore);
    }
    label(sec, "stomata", 0, -y - 0.45, 0);
    g.add(sec);

    // Midrib and veins, which is what makes it read as a leaf rather than a
    // green blob.
    var vein = new THREE.MeshStandardMaterial({ color: 0x2b6e3a,
      roughness: 0.7 });
    var rib = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.03, 4.4, 8),
                             vein);
    rib.rotation.x = -Math.PI / 2.35;
    rib.position.y = 0.06;
    g.add(rib);
    for (var i = -3; i <= 3; i++) {
      if (!i) continue;
      var t = i / 4;
      var v = new THREE.Mesh(
        new THREE.CylinderGeometry(0.025, 0.012, 1.5 - Math.abs(t) * 0.7, 6),
        vein);
      v.rotation.x = -Math.PI / 2.35;
      v.rotation.z = (i > 0 ? 1 : -1) * 1.0;
      v.position.set(0, 0.08, 0);
      v.translateOnAxis(new THREE.Vector3(0, 1, 0), t * 1.9);
      g.add(v);
    }
    // The stalk.
    var st = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.09, 1.5, 8),
                            vein);
    st.rotation.x = -Math.PI / 2.35;
    st.position.set(0, -0.55, 1.6);
    g.add(st);
    return g;
  };

  /* A cell with its organelles, not a blue ball. The membrane is see-through
     because everything worth pointing at is behind it. */
  BODY.cell = function () {
    var g = new THREE.Group();
    var m = new THREE.Mesh(new THREE.SphereGeometry(2, 40, 28),
      new THREE.MeshStandardMaterial({ color: 0x6fb7d9, roughness: 0.35,
        transparent: true, opacity: 0.2, side: THREE.DoubleSide }));
    m.scale.set(1.25, 0.85, 1);
    g.add(m);
    label(g, "cell membrane", 0, 1.95, 0);

    var nuc = new THREE.Mesh(new THREE.SphereGeometry(0.72, 26, 18),
      new THREE.MeshStandardMaterial({ color: 0x9a6fd9, roughness: 0.45 }));
    g.add(nuc);
    g.add(new THREE.Mesh(new THREE.SphereGeometry(0.26, 18, 12),
      new THREE.MeshStandardMaterial({ color: 0x6b3fa0 })));
    label(g, "nucleus", 0, 0.95, 0);

    // Mitochondria, where respiration happens — the thing most lessons are
    // actually about when they show a cell.
    [[1.5, 0.35, 0.4], [-1.4, -0.3, -0.5], [0.3, -0.75, 1.0],
     [-0.8, 0.6, -1.0]].forEach(function (p, i) {
      var mito = new THREE.Mesh(new THREE.CapsuleGeometry(0.16, 0.44, 6, 12),
        new THREE.MeshStandardMaterial({ color: 0xd9704a, roughness: 0.5 }));
      mito.position.set(p[0], p[1], p[2]);
      mito.rotation.z = 0.6 + i * 0.5;
      g.add(mito);
    });
    label(g, "mitochondria", 1.5, 0.85, 0.4);
    return g;
  };

  BODY.root = function () {
    var g = new THREE.Group();
    var mat = new THREE.MeshStandardMaterial({ color: 0xb08b5a,
      roughness: 0.75 });
    var main = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.06, 4, 12),
                              mat);
    g.add(main);
    for (var i = 0; i < 6; i++) {
      var b = new THREE.Mesh(
        new THREE.CylinderGeometry(0.08, 0.02, 1.5, 8), mat);
      b.position.y = 1.3 - i * 0.55;
      b.rotation.z = (i % 2 ? 1 : -1) * 0.9;
      b.translateOnAxis(new THREE.Vector3(0, 1, 0), 0.6);
      g.add(b);
    }
    return g;
  };

  BODY.panel = function () {
    var g = new THREE.Group();
    g.add(new THREE.Mesh(new THREE.BoxGeometry(4, 0.12, 2.6),
      new THREE.MeshStandardMaterial({ color: 0x1c3f6e, roughness: 0.25,
        metalness: 0.5 })));
    for (var i = -1; i <= 1; i++) {
      g.add(new THREE.Mesh(new THREE.BoxGeometry(0.04, 0.14, 2.6),
        new THREE.MeshBasicMaterial({ color: 0x8fa3b0 })
      ).translateX(i * 1.3));
    }
    return g;
  };

  BODY.vessel = function () {
    return new THREE.Mesh(new THREE.CylinderGeometry(1.5, 1.5, 2.6, 34),
      new THREE.MeshStandardMaterial({ color: 0x9aa7b0, roughness: 0.3,
        metalness: 0.3, transparent: true, opacity: 0.5 }));
  };

  BODY.box = function () {
    return new THREE.Mesh(new THREE.BoxGeometry(3, 2, 2),
      new THREE.MeshStandardMaterial({ color: 0x5c6b7a, roughness: 0.5 }));
  };

  BUILD.flow = function (spec, group) {
    var make = BODY[spec.body] || BODY.box;
    group.add(make());

    var ins = spec["in"] || [], outs = spec.out || [];

    // The sun, when something is arriving as light. It is the reason the
    // whole picture makes sense for photosynthesis.
    if (ins.some(function (x) { return /light|sun|photon/i.test(x.name); })) {
      var sun = new THREE.Mesh(new THREE.SphereGeometry(0.55, 22, 16),
        new THREE.MeshBasicMaterial({ color: 0xffd75c }));
      sun.position.set(-2.2, 4.2, 2.6);
      group.add(sun);
      label(group, "sunlight", -2.2, 5.1, 2.6);
      for (var r = 0; r < 5; r++) {
        var ray = new THREE.Mesh(
          new THREE.CylinderGeometry(0.02, 0.02, 3.4, 6),
          new THREE.MeshBasicMaterial({ color: 0xffe6a1, transparent: true,
            opacity: 0.5 }));
        ray.position.set(-1.7 + r * 0.5, 2.6, 1.9 - r * 0.2);
        ray.rotation.z = 0.55;
        group.add(ray);
      }
    }

    function stream(list, side) {
      list.forEach(function (item, i) {
        if (/light|sun|photon/i.test(item.name)) return;   // drawn as the sun
        var spread = (i - (list.length - 1) / 2) * 1.5;
        var from = new THREE.Vector3(side * 5.4, spread, side * 0.9);
        var to = new THREE.Vector3(side * 0.6, spread * 0.35, 0);
        var a = side < 0 ? from : to;
        var b = side < 0 ? to : from;
        label(group, item.name, from.x, from.y + 0.75, from.z);

        // A faint rail along the path. The beads are only in one place at a
        // time, so without this the route they travel is invisible between
        // them and the picture reads as dots hanging in space.
        var rail = new THREE.Line(
          new THREE.BufferGeometry().setFromPoints([a, b]),
          new THREE.LineBasicMaterial({
            color: side < 0 ? 0x7fb8ff : 0x8fe3b0,
            transparent: true, opacity: 0.28 }));
        group.add(rail);
        // Three beads per stream, evenly offset, so it reads as continuous
        // traffic rather than one thing making a trip.
        for (var k = 0; k < 3; k++) {
          var p = new THREE.Mesh(
            new THREE.SphereGeometry(0.19, 16, 12),
            new THREE.MeshStandardMaterial({
              color: item.color !== undefined ? item.color
                : (side < 0 ? 0x7fb8ff : 0x8fe3b0),
              emissive: side < 0 ? 0x14324f : 0x14402a,
              emissiveIntensity: 0.5, roughness: 0.35 }));
          p.userData.flow = { a: a.clone(), b: b.clone(),
                              t: k / 3, speed: 0.28 };
          group.add(p);
        }
      });
    }
    stream(ins, -1);      // in from the left
    stream(outs, 1);      // out to the right
  };

  /* Push overlapping labels apart.
   *
   * Every builder places its labels where the thing they name actually is,
   * which is right and which is also why they collide: a leaf section has
   * five layers within two units, and a flow has traffic labels crossing the
   * same space. Fixing it per builder means fixing it again for the next one.
   *
   * So it happens once, here, after everything is built and scaled. Sprites
   * are billboards — they always face the camera — so their footprint in the
   * scene is close enough to their scale, and separating any two whose boxes
   * meet is enough to make a scene readable from the angle it opens at.
   *
   * Bounded iterations, because with enough labels in one place this can
   * chase its own tail. Eight passes settles every scene here and gives up
   * gracefully rather than hanging on a pathological one.
   */
  function declutter(sprites) {
    if (sprites.length < 2) return;
    var PAD = 0.06;
    for (var pass = 0; pass < 8; pass++) {
      var moved = false;
      // Top down, so a label pushed aside lands somewhere already settled.
      sprites.sort(function (a, b) { return b.position.y - a.position.y; });
      for (var i = 0; i < sprites.length; i++) {
        for (var j = i + 1; j < sprites.length; j++) {
          var A = sprites[i], B = sprites[j];
          var dx = Math.abs(A.position.x - B.position.x);
          var dy = Math.abs(A.position.y - B.position.y);
          var dz = Math.abs(A.position.z - B.position.z);
          var wx = (A.scale.x + B.scale.x) / 2 + PAD;
          var wy = (A.scale.y + B.scale.y) / 2 + PAD;
          // Depth counts: two labels far apart in z read as near and far, not
          // as one on top of the other, so they are left alone.
          if (dx < wx && dy < wy && dz < wx) {
            B.position.y -= (wy - dy) + 0.02;
            moved = true;
          }
        }
      }
      if (!moved) return;
    }
  }

  /* ---- biology: the helix -------------------------------------------- *
   *
   * Every one of the builders above was a chemistry or a physics picture,
   * and biology got a leaf with arrows round it. The double helix is the
   * one structure a biology class is actually examined on the shape of, and
   * it is the one shape on this whole page that a flat diagram genuinely
   * cannot teach: the two grooves are different widths, the strands run in
   * opposite directions, and neither of those is visible until you turn it.
   *
   * Measured, like the lattice and the orbits. The rise per base pair, the
   * bases per turn, the diameter and the handedness are crystallography,
   * not decoration — B-DNA turns right and Z-DNA turns left, and a model
   * asked to write those numbers itself will produce a plausible helix that
   * is wrong in the one respect a student is asked about. So the model
   * names the form and the numbers come from here.
   */
  var HELIX = {
    // rise per unit (Å), units per turn, diameter (Å), handedness, strands
    dna:   { rise: 3.4, per: 10.5, dia: 20, hand: 1, strands: 2,
             name: "B-DNA", unit: "base pair" },
    "a-dna": { rise: 2.6, per: 11, dia: 23, hand: 1, strands: 2,
             name: "A-DNA", unit: "base pair" },
    "z-dna": { rise: 3.7, per: 12, dia: 18, hand: -1, strands: 2,
             name: "Z-DNA (left-handed)", unit: "base pair" },
    rna:   { rise: 2.8, per: 11, dia: 23, hand: 1, strands: 1,
             name: "RNA", unit: "base" },
    alpha: { rise: 1.5, per: 3.6, dia: 10, hand: 1, strands: 1,
             name: "α-helix", unit: "residue" }
  };
  // The pairing is the lesson, so the second strand is computed and never
  // taken from the model: A with T, G with C, and U where it is RNA.
  var PAIR = { A: "T", T: "A", G: "C", C: "G", U: "A" };
  var BASEC = { A: 0x4caf50, T: 0xe53935, G: 0xfb8c00, C: 0x1e88e5,
                U: 0xab47bc };

  BUILD.helix = function (spec, group) {
    var H = HELIX[spec.form] || HELIX.dna;
    // Ångström to world units. A twenty-ångström helix drawn at 1:1 is
    // twenty units wide and the camera frames it fine, but the bases end up
    // a tenth of a unit apart; a fifth of that reads properly.
    var K = 0.2;
    var R = H.dia * K / 2;
    var rise = H.rise * K;
    var seq = String(spec.sequence || "").toUpperCase()
                .replace(/[^ACGTU]/g, "");
    var turns = Math.max(1, Math.min(6, spec.turns || 2.5));
    var n = Math.max(6, Math.min(120, Math.round(turns * H.per)));
    if (seq) n = Math.min(n, Math.max(6, seq.length));

    var y0 = -(n - 1) * rise / 2;
    function at(i, strand) {
      var a = H.hand * (i / H.per) * Math.PI * 2
            + (strand ? Math.PI * (H.strands === 2 ? 0.72 : 0) : 0);
      // 0.72π rather than π. The two backbones of B-DNA are NOT opposite
      // each other — that offset is exactly what makes one groove wide and
      // the other narrow, and setting them half a turn apart draws a ladder
      // with two identical grooves, which is the thing the picture is for.
      return new THREE.Vector3(Math.cos(a) * R, y0 + i * rise,
                               Math.sin(a) * R);
    }

    for (var s = 0; s < H.strands; s++) {
      var pts = [];
      for (var i = 0; i < n; i++) pts.push(at(i, s));
      var curve = new THREE.CatmullRomCurve3(pts);
      group.add(new THREE.Mesh(
        new THREE.TubeGeometry(curve, n * 4, R * 0.16, 10, false),
        new THREE.MeshStandardMaterial({
          color: s ? 0x7e9cb8 : 0xc7d3de, roughness: 0.45 })));
    }

    // The rungs. On a two-stranded helix these are the base pairs and they
    // are drawn in two halves so each base carries its own colour.
    for (var j = 0; j < n; j++) {
      var A = at(j, 0);
      if (H.strands === 1) {
        var beadC = seq ? (BASEC[seq[j % seq.length]] || 0x9aa7b0) : 0x9aa7b0;
        var bead = new THREE.Mesh(
          new THREE.SphereGeometry(R * 0.22, 14, 10),
          new THREE.MeshStandardMaterial({ color: beadC, roughness: 0.4 }));
        bead.position.copy(A);
        group.add(bead);
        continue;
      }
      var B = at(j, 1);
      var mid = new THREE.Vector3().addVectors(A, B).multiplyScalar(0.5);
      var b1 = seq ? seq[j % seq.length] : "";
      var b2 = b1 ? PAIR[b1] : "";
      halfRung(group, A, mid, b1 ? BASEC[b1] : 0x8d99a6);
      halfRung(group, mid, B, b2 ? BASEC[b2] : 0x8d99a6);
      if (b1 && n <= 24) {
        label(group, b1 + "–" + b2,
              A.x * 1.35, A.y, A.z * 1.35);
      }
    }

    // What it is and what the numbers are, written on the scene rather than
    // left to the caption — a picture of a helix with no scale on it is a
    // decoration.
    var top = y0 + (n - 1) * rise;
    label(group, H.name, 0, top + rise * 2.4, 0);
    label(group, H.rise + " Å per " + H.unit, 0, top + rise * 1.2, R * 1.6);
    label(group, H.per + " per turn · " + H.dia + " Å across",
          0, y0 - rise * 1.6, R * 1.6);
    if (H.hand < 0) label(group, "left-handed", 0, y0 - rise * 3, R * 1.6);
    if (H.strands === 2) {
      label(group, "5′ → 3′", R * 1.9, top - rise * 1.2, 0);
      label(group, "3′ ← 5′", -R * 1.9, y0 + rise * 1.2, 0);
    }
  };

  function halfRung(group, a, b, colour) {
    var d = new THREE.Vector3().subVectors(b, a);
    var len = d.length();
    if (!len) return;
    var m = new THREE.Mesh(
      new THREE.CylinderGeometry(len * 0.07, len * 0.07, len, 8),
      new THREE.MeshStandardMaterial({ color: colour, roughness: 0.45 }));
    m.position.copy(a).add(b).multiplyScalar(0.5);
    m.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0),
                                    d.clone().normalize());
    group.add(m);
  }

  /* ---- biology: a cell, with the organelles at their real sizes ------ *
   *
   * The rule at the top of this file says a liver cannot be drawn honestly
   * from curves and should not be attempted. A cell is the case that rule
   * does NOT cover, and the difference is worth being precise about: a
   * liver has a shape a student is examined on and ellipsoids get it wrong,
   * whereas a nucleus IS a sphere, a mitochondrion IS a capsule with folded
   * cristae, and every textbook in the world draws them that way. What a
   * flat diagram loses is that they sit at different depths in a volume,
   * which is the one thing turning it around restores.
   *
   * The sizes are micrometres from measurement, scaled together, so a
   * mitochondrion is genuinely a fifth of the nucleus and not whatever fits
   * the picture. Anything this cannot place honestly is left out rather
   * than approximated.
   */
  var ORGANELLE = {
    // radius or half-lengths in µm, colour, and where it sits
    nucleus:      { r: [3, 3, 3], c: 0x6a5acd, at: [0, 0, 0] },
    nucleolus:    { r: [1, 1, 1], c: 0x4b3fa8, at: [0.6, 0.5, 0.4] },
    mitochondrion:{ r: [1, 0.4, 0.4], c: 0xe07a5f, at: [4.5, 1.5, 1] },
    chloroplast:  { r: [2.5, 1.2, 1.2], c: 0x3d9970, at: [-4.5, 2, 1.5] },
    vacuole:      { r: [4, 4, 4], c: 0x88c0d0, at: [0, -3, -2] },
    ribosome:     { r: [0.15, 0.15, 0.15], c: 0xf4d35e, at: [3, -2, 2] },
    lysosome:     { r: [0.4, 0.4, 0.4], c: 0xd45d79, at: [-3, -2.5, 2] },
    golgi:        { r: [2, 0.25, 1.2], c: 0xffb703, at: [-4, -1, -2] },
    "endoplasmic reticulum":
                  { r: [3, 0.2, 2], c: 0xc77dff, at: [4, 0.5, -2] },
    centriole:    { r: [0.25, 0.5, 0.25], c: 0x9aa7b0, at: [-2, 3.5, -1] },
    chromosome:   { r: [0.3, 1.4, 0.3], c: 0x2f4858, at: [0.5, 0, -0.8] }
  };

  BUILD.cell = function (spec, group) {
    var plant = spec.cell === "plant";
    var K = 0.55;                     // µm to world units
    var Rc = 9 * K;                   // a cell around 18 µm across

    // The outside, drawn as a shell you can see into. A solid one hides
    // everything the picture is about.
    var wall = plant
      ? new THREE.BoxGeometry(Rc * 2, Rc * 1.7, Rc * 1.6)
      : new THREE.SphereGeometry(Rc, 40, 28);
    group.add(new THREE.Mesh(wall, new THREE.MeshStandardMaterial({
      color: plant ? 0x7ba05b : 0x9bb8c9, transparent: true, opacity: 0.16,
      roughness: 0.6, side: THREE.DoubleSide })));
    group.add(new THREE.LineSegments(
      new THREE.EdgesGeometry(wall),
      new THREE.LineBasicMaterial({ color: 0x000000, transparent: true,
                                    opacity: 0.22 })));
    label(group, plant ? "cell wall" : "cell membrane", 0, Rc * 1.15, 0);

    (spec.parts || []).forEach(function (p, idx) {
      var key = String(p.name || "").toLowerCase();
      var O = ORGANELLE[key];
      if (!O) return;               // not one we can place honestly
      var n = Math.max(1, Math.min(12, p.n || 1));
      for (var i = 0; i < n; i++) {
        // Copies are spread around the cell rather than stacked, keeping
        // the count meaningful: "many mitochondria" is a fact about a cell.
        var a = (i / n) * Math.PI * 2 + idx;
        var spread = n > 1 ? 0.55 : 0;
        var g = new THREE.SphereGeometry(1, 20, 14);
        var m = new THREE.Mesh(g, new THREE.MeshStandardMaterial({
          color: O.c, roughness: 0.45,
          transparent: key === "vacuole", opacity: 0.45 }));
        m.scale.set(O.r[0] * K, O.r[1] * K, O.r[2] * K);
        m.position.set(
          (O.at[0] + Math.cos(a) * spread * 4) * K,
          (O.at[1] + Math.sin(a * 1.7) * spread * 3) * K,
          (O.at[2] + Math.sin(a) * spread * 4) * K);
        group.add(m);
        if (i === 0) {
          label(group, key + (n > 1 ? " ×" + n : ""),
                m.position.x, m.position.y + O.r[1] * K + 0.5 * K,
                m.position.z);
        }
      }
    });
    label(group, "sizes to scale · about 18 µm across", 0, -Rc * 1.2, 0);
  };

  /* ---- physics: a field, integrated rather than drawn ----------------- *
   *
   * The two pictures a physics class most needs in three dimensions are the
   * ones no flat diagram can give: a field, which fills a volume, and a
   * wave, which moves. Both were missing here entirely.
   *
   * Nothing about these lines is drawn by hand. A seed point is placed
   * around each source and then walked, one small step at a time, in the
   * direction the field points AT THAT POINT — the field summed from every
   * source, by superposition. What comes out is where the field actually
   * goes, so a dipole's lines close on the negative charge because the
   * arithmetic takes them there and not because somebody curved them.
   *
   * Two fields, one integrator. Electric from point charges by Coulomb;
   * magnetic from current loops by Biot–Savart, summed over the segments of
   * each loop. The loop is what makes it worth having: the field of a bar
   * magnet is the one every student draws from memory and few can place in
   * space.
   */
  function eField(p, charges) {
    var E = new THREE.Vector3();
    charges.forEach(function (c) {
      var d = new THREE.Vector3(p.x - c.x, p.y - c.y, p.z - c.z);
      var r = d.length();
      if (r < 1e-3) return;
      E.add(d.multiplyScalar(c.q / (r * r * r)));
    });
    return E;
  }

  function bField(p, loops) {
    var B = new THREE.Vector3();
    loops.forEach(function (L) {
      var N = 48, prev = null;
      for (var i = 0; i <= N; i++) {
        var a = (i / N) * Math.PI * 2;
        // A loop in the xz plane, carrying current I, centred where it says.
        var q = new THREE.Vector3(L.x + Math.cos(a) * L.r, L.y,
                                  L.z + Math.sin(a) * L.r);
        if (prev) {
          var dl = new THREE.Vector3().subVectors(q, prev);
          var mid = new THREE.Vector3().addVectors(q, prev).multiplyScalar(0.5);
          var r = new THREE.Vector3(p.x - mid.x, p.y - mid.y, p.z - mid.z);
          var rl = r.length();
          if (rl > 1e-3) {
            B.add(new THREE.Vector3().crossVectors(dl, r)
                   .multiplyScalar((L.i || 1) / (rl * rl * rl)));
          }
        }
        prev = q;
      }
    });
    return B;
  }

  BUILD.field = function (spec, group) {
    var charges = (spec.charges || []).map(function (c) {
      return { q: c.q || 1, x: c.x || 0, y: c.y || 0, z: c.z || 0 };
    });
    var loops = (spec.loops || []).map(function (L) {
      return { r: L.r || 2, i: L.i || 1, x: L.x || 0, y: L.y || 0,
               z: L.z || 0 };
    });
    var magnetic = !charges.length && loops.length;
    var f = magnetic ? function (p) { return bField(p, loops); }
                     : function (p) { return eField(p, charges); };

    charges.forEach(function (c) {
      var pos = c.q >= 0;
      var m = new THREE.Mesh(
        new THREE.SphereGeometry(0.34, 22, 16),
        new THREE.MeshStandardMaterial({
          color: pos ? 0xe53935 : 0x1e88e5, roughness: 0.35 }));
      m.position.set(c.x, c.y, c.z);
      group.add(m);
      label(group, (pos ? "+" : "−") + (Math.abs(c.q) === 1 ? "" :
            Math.abs(c.q)), c.x, c.y + 0.75, c.z);
    });
    loops.forEach(function (L) {
      var t = new THREE.Mesh(
        new THREE.TorusGeometry(L.r, 0.06, 10, 60),
        new THREE.MeshStandardMaterial({ color: 0xc9a227, roughness: 0.4 }));
      t.rotation.x = Math.PI / 2;
      t.position.set(L.x, L.y, L.z);
      group.add(t);
      label(group, "I", L.x + L.r + 0.5, L.y, L.z);
    });

    // Seeds: a ring of starting points around each source, at several
    // heights, so the lines leave in every direction rather than in a plane.
    var seeds = [];
    var sources = charges.length ? charges : loops;
    sources.forEach(function (c) {
      var out = charges.length ? (c.q >= 0 ? 1 : -1) : 1;
      for (var ring = 0; ring < 3; ring++) {
        var phi = (ring + 1) / 4 * Math.PI;
        for (var k = 0; k < 8; k++) {
          var th = (k / 8) * Math.PI * 2 + ring * 0.4;
          var rr = charges.length ? 0.45 : (c.r || 2) * 1.02;
          seeds.push({
            p: new THREE.Vector3(
              c.x + rr * Math.sin(phi) * Math.cos(th),
              c.y + rr * Math.cos(phi),
              c.z + rr * Math.sin(phi) * Math.sin(th)),
            dir: out
          });
        }
      }
    });

    var STEP = 0.16, MAX = 260, FAR = 14;
    seeds.forEach(function (s) {
      var p = s.p.clone(), pts = [p.clone()];
      for (var i = 0; i < MAX; i++) {
        var v = f(p);
        var len = v.length();
        if (!len || len !== len) break;
        p = p.clone().add(v.multiplyScalar(s.dir * STEP / len));
        if (p.length() > FAR) { pts.push(p.clone()); break; }
        // Stop on arrival at a source, which is where a field line ends.
        var hit = false;
        sources.forEach(function (c) {
          if (p.distanceTo(new THREE.Vector3(c.x, c.y, c.z)) < 0.36) hit = true;
        });
        pts.push(p.clone());
        if (hit) break;
      }
      if (pts.length < 3) return;
      group.add(new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(pts),
        new THREE.LineBasicMaterial({
          color: magnetic ? 0x8ad3a0 : 0xa9c6e8,
          transparent: true, opacity: 0.75 })));
      // One arrowhead per line, a third of the way along, because a field
      // line without a direction on it is half of the information.
      var mid = pts[Math.floor(pts.length / 3)];
      var nxt = pts[Math.floor(pts.length / 3) + 1];
      if (mid && nxt) {
        var d = new THREE.Vector3().subVectors(nxt, mid);
        if (d.length()) {
          var cone = new THREE.Mesh(
            new THREE.ConeGeometry(0.09, 0.26, 8),
            new THREE.MeshBasicMaterial({
              color: magnetic ? 0x8ad3a0 : 0xa9c6e8 }));
          cone.position.copy(mid);
          cone.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0),
                                             d.normalize());
          group.add(cone);
        }
      }
    });
    label(group, magnetic ? "magnetic field of the current"
                          : "electric field lines", 0, FAR * 0.42, 0);
  };

  /* ---- physics: a wave, which has to move ---------------------------- *
   *
   * A standing wave drawn still is a picture of a curve; the whole point is
   * that the nodes do not move while everything between them does. So this
   * one is animated, and the surface is recomputed each frame from the
   * actual superposition rather than being a shape that wobbles.
   *
   * Two sources give the interference pattern from the double-slit lesson —
   * and seen from above it is the textbook figure, while from the side it
   * is water, which is the connection the figure is trying to make.
   */
  BUILD.wave = function (spec, group) {
    var mode = spec.mode || "travelling";
    var lam = Math.max(0.4, Math.min(8, spec.wavelength || 2));
    var amp = Math.max(0.05, Math.min(2, spec.amplitude || 0.5));
    var span = Math.max(4, Math.min(16, spec.span || 9));
    var srcs = (spec.sources || []).slice(0, 4).map(function (s) {
      return { x: s.x || 0, z: s.z || 0 };
    });
    if (mode === "interference" && srcs.length < 2) {
      var d = Math.max(lam, span / 4);
      srcs = [{ x: -d / 2, z: 0 }, { x: d / 2, z: 0 }];
    }
    var N = 96;
    var geo = new THREE.PlaneGeometry(span, span, N, N);
    geo.rotateX(-Math.PI / 2);
    var mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
      color: 0x4da6ff, roughness: 0.35, metalness: 0.05,
      side: THREE.DoubleSide, flatShading: false, wireframe: !!spec.wire }));
    group.add(mesh);

    var k = 2 * Math.PI / lam, w = 2 * Math.PI * (spec.speed || 0.6);
    var pos = geo.attributes.position;
    var base = [];
    for (var i = 0; i < pos.count; i++) base.push([pos.getX(i), pos.getZ(i)]);

    function height(x, z, t) {
      if (mode === "standing") {
        return amp * Math.sin(k * x) * Math.cos(w * t);
      }
      if (srcs.length) {
        var sum = 0;
        srcs.forEach(function (s) {
          var r = Math.sqrt((x - s.x) * (x - s.x) + (z - s.z) * (z - s.z));
          // 1/sqrt(r), because a circular wave's amplitude falls that way
          // and drawing it constant makes the far interference fringes look
          // stronger than they are.
          sum += Math.cos(k * r - w * t) / Math.sqrt(Math.max(0.6, r));
        });
        return amp * sum;
      }
      return amp * Math.sin(k * x - w * t);
    }

    mesh.userData.animate = function (t) {
      for (var i = 0; i < base.length; i++) {
        pos.setY(i, height(base[i][0], base[i][1], t));
      }
      pos.needsUpdate = true;
      geo.computeVertexNormals();
    };
    mesh.userData.animate(0);

    srcs.forEach(function (s, i) {
      var m = new THREE.Mesh(
        new THREE.SphereGeometry(0.16, 16, 12),
        new THREE.MeshBasicMaterial({ color: 0xffd75c }));
      m.position.set(s.x, amp + 0.3, s.z);
      group.add(m);
      label(group, "source " + (i + 1), s.x, amp + 0.9, s.z);
    });
    label(group, "λ = " + lam + (spec.unit ? " " + spec.unit : ""),
          -span / 2 + lam / 2, amp + 1.4, -span / 2 + 0.6);
    if (mode === "standing") label(group, "nodes stay still", 0, amp + 1.4, 0);
  };

  /* Break a long label on word boundaries, so a stage name reads as two
     short lines instead of one that overlaps its neighbours. */
  function wrapLabel(text, max) {
    var words = String(text || "").split(/\s+/), lines = [], cur = "";
    words.forEach(function (w) {
      if (!cur) { cur = w; return; }
      if ((cur + " " + w).length <= max) cur += " " + w;
      else { lines.push(cur); cur = w; }
    });
    if (cur) lines.push(cur);
    return lines.slice(0, 2);
  }

  /* ---- labels, as sprites so they always face you ------------------- */
  function label(group, text, x, y, z) {
    var cv = document.createElement("canvas");
    var ctx = cv.getContext("2d");
    ctx.font = "600 40px system-ui, sans-serif";
    var w = Math.ceil(ctx.measureText(text).width) + 22;
    cv.width = w; cv.height = 56;
    var c2 = cv.getContext("2d");
    c2.font = "600 40px system-ui, sans-serif";
    c2.fillStyle = "rgba(10,12,16,.72)";
    c2.roundRect ? (c2.beginPath(), c2.roundRect(0, 0, w, 56, 10), c2.fill())
                 : c2.fillRect(0, 0, w, 56);
    c2.fillStyle = "#eafff2";
    c2.textBaseline = "middle";
    c2.fillText(text, 11, 30);
    var tex = new THREE.CanvasTexture(cv);
    tex.minFilter = THREE.LinearFilter;
    var s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex,
      transparent: true, depthTest: false }));
    // /120, not /46. At the larger size a stage called "ATP + NADPH made"
    // was over three world units wide against a three-unit gap between
    // stations, so every label in a process overlapped its neighbours and the
    // scene was a pile of text with geometry somewhere behind it.
    s.scale.set(w / 120, 56 / 120, 1);
    s.position.set(x, y, z);
    group.add(s);
  }

  /* ---- the viewer ---------------------------------------------------- */
  window.Three3D = {
    kinds: Object.keys(BUILD),

    /* Start fetching three.js before anything needs it.
     *
     * The library is a few hundred kilobytes from a CDN and was only
     * requested when a scene mounted — which is the moment the reader is
     * looking at the space where the diagram should be. Building a lesson
     * takes several seconds at the server, so calling this when the request
     * goes out lets the download finish inside that time and the scene
     * appears immediately instead of after a second wait the reader has to
     * sit through.
     *
     * Safe to call as often as you like: load() returns the same promise
     * after the first call, and a failure here is ignored because mount()
     * handles it properly and this is only a head start. */
    preload() {
      try { load().catch(function () {}); } catch (e) { /* never fatal */ }
    },

    /* Mount a scene into an element. Returns a disposer, because a page with
       five lessons on it would otherwise keep five WebGL contexts and five
       animation loops alive after you scrolled past them — browsers cap the
       number of contexts and start killing the oldest, which looks like the
       first diagram randomly going black. */
    async mount(el, spec) {
      if (!el) return function () {};
      var build = BUILD[spec && spec.kind];
      if (!build) return function () {};
      try {
        await load();
      } catch (e) {
        el.innerHTML = '<div class="td-fail">The 3D view could not load — ' +
          "you are probably offline. Everything else on this page still " +
          "works.</div>";
        return function () {};
      }

      var w = hostW(el, el.clientWidth || 480);
      var h = hostH(el, spec.height || 300);
      var scene = new THREE.Scene();
      var cam = new THREE.PerspectiveCamera(45, w / h, 0.1, 400);
      /* preserveDrawingBuffer so the scene can be photographed for the
         printed sheet. WebGL may discard its drawing buffer as soon as
         it has been composited, and toDataURL on a discarded buffer
         returns a blank rectangle — which reads as a broken diagram
         rather than as a missing one. */
      var ren = new THREE.WebGLRenderer({ antialias: true, alpha: true,
                                          preserveDrawingBuffer: true });
      ren.setPixelRatio(Math.min(devicePixelRatio, 2));
      ren.setSize(w, h);
      el.innerHTML = "";
      /* A block, not the default inline: an inline canvas sits on a text
         baseline, so the host is a few pixels taller than the canvas — and
         a host that is measured to size that canvas would then grow by
         those few pixels every time the observer fired. */
      ren.domElement.style.display = "block";
      el.appendChild(ren.domElement);

      scene.add(new THREE.AmbientLight(0xffffff, 0.62));
      var key = new THREE.DirectionalLight(0xffffff, 0.85);
      key.position.set(4, 7, 5);
      scene.add(key);
      var fill = new THREE.DirectionalLight(0x88aaff, 0.28);
      fill.position.set(-5, -2, -4);
      scene.add(fill);

      var group = new THREE.Group();
      build(spec, group);
      scene.add(group);

      // Frame whatever was built, so every scene arrives the right size with
      // no per-scene camera tuning.
      var box = new THREE.Box3().setFromObject(group);
      var size = box.getSize(new THREE.Vector3());
      var mid = box.getCenter(new THREE.Vector3());
      group.position.sub(mid);
      var span = Math.max(size.x, size.y, size.z) || 4;

      // Labels are built at a fixed size, because the builders do not know
      // how big the finished scene will be until it is finished. Scaling them
      // here is what stops "H" and "O" from being drawn larger than the water
      // molecule they belong to.
      // Clamped. Straight proportionality made labels grow without limit on
      // wide scenes — the very ones that have the most of them.
      var k = Math.max(0.6, Math.min(1.6, span / 9));
      var sprites = [];
      group.traverse(function (o) {
        if (o.isSprite) { o.scale.multiplyScalar(k); sprites.push(o); }
      });
      declutter(sprites);

      // 1.35, not 1.9. The framing is driven by the bounding box, and a scene
      // with traffic streaming in from both sides has a box far wider than
      // the thing being taught — so the leaf everybody is meant to be looking
      // at ended up small and adrift in the middle of a lot of nothing.
      var ctl = orbit(cam, ren.domElement, span * 1.35);
      ctl.setRange(span * 0.45, span * 4);

      var spinners = [], flows = [], movers = [];
      group.traverse(function (o) {
        if (o.userData.spin) spinners.push(o);
        if (o.userData.flow) flows.push(o);
        // A general per-frame hook, for a builder that has to recompute its
        // own geometry rather than move a finished mesh around. A standing
        // wave drawn still is a picture of a curve; the nodes holding still
        // while everything between them moves IS the lesson.
        if (typeof o.userData.animate === "function") movers.push(o);
      });

      var live = true, raf = 0, t0 = performance.now();
      (function tick(now) {
        if (!live) return;
        raf = requestAnimationFrame(tick);
        var dt = ((now || t0) - t0) / 1000;
        spinners.forEach(function (o) {
          var s = o.userData.spin;
          var a = s.t + dt * s.speed;
          o.position.set(Math.cos(a) * s.r, 0, Math.sin(a) * s.r);
        });
        // Things moving between the stations of a process. The motion is the
        // explanation: a static arrow says two stages are connected, a pulse
        // says which way it goes and that something is being carried.
        flows.forEach(function (o) {
          var f = o.userData.flow;
          var u = (f.t + dt * f.speed) % 1;
          o.position.lerpVectors(f.a, f.b, u);
        });
        movers.forEach(function (o) { o.userData.animate(dt); });
        if (spec.turntable !== false && !ctl.isDragging) group.rotation.y += 0.0016;
        ctl.update();
        ren.render(scene, cam);
      })(t0);

      var ro = new ResizeObserver(function () {
        var nw = hostW(el, el.clientWidth || w);
        var nh = hostH(el, h);
        if (nw === w && nh === h) return;
        w = nw; h = nh;
        cam.aspect = nw / nh;
        cam.updateProjectionMatrix();
        ren.setSize(nw, nh);
      });
      ro.observe(el);

      return function dispose() {
        live = false;
        cancelAnimationFrame(raf);
        ro.disconnect();
        ctl.dispose();
        scene.traverse(function (o) {
          if (o.geometry) o.geometry.dispose();
          if (o.material) {
            (Array.isArray(o.material) ? o.material : [o.material])
              .forEach(function (mm) {
                if (mm.map) mm.map.dispose();
                mm.dispose();
              });
          }
        });
        ren.dispose();
        if (ren.domElement.parentNode) ren.domElement.remove();
      };
    }
  };
})();
