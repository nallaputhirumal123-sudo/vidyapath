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
 * Three.js is fetched once, on first use, from a CDN — the same way the
 * Python labs already fetch Pyodide. If it will not load, the caption and the
 * description still render: a lesson never depends on the picture arriving.
 */
(function () {
  "use strict";

  var THREE = null, loading = null;
  var SRC = "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";

  function load() {
    if (THREE) return Promise.resolve(THREE);
    if (loading) return loading;
    loading = import(SRC).then(function (m) {
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
      if (L.name) label(group, L.name, (L.x || 0) + W / 2 + 0.55, y + h / 2, 0);
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

      var w = el.clientWidth || 480, h = spec.height || 300;
      var scene = new THREE.Scene();
      var cam = new THREE.PerspectiveCamera(45, w / h, 0.1, 400);
      var ren = new THREE.WebGLRenderer({ antialias: true, alpha: true });
      ren.setPixelRatio(Math.min(devicePixelRatio, 2));
      ren.setSize(w, h);
      el.innerHTML = "";
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

      var spinners = [], flows = [];
      group.traverse(function (o) {
        if (o.userData.spin) spinners.push(o);
        if (o.userData.flow) flows.push(o);
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
        if (spec.turntable !== false && !ctl.isDragging) group.rotation.y += 0.0016;
        ctl.update();
        ren.render(scene, cam);
      })(t0);

      var ro = new ResizeObserver(function () {
        var nw = el.clientWidth || w;
        cam.aspect = nw / h;
        cam.updateProjectionMatrix();
        ren.setSize(nw, h);
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
