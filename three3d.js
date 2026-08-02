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
    var st = { r: radius, theta: Math.PI * 0.25, phi: Math.PI * 0.35,
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
  };

  /* z = f(x, y). Every optimisation surface, every wave, every potential
     well, and the only honest way to show a saddle point. */
  BUILD.surface = function (spec, group) {
    var N = 46, S = spec.span || 4;
    var g = new THREE.PlaneGeometry(S * 2, S * 2, N, N);
    var fn = FUNCS[spec.fn] || FUNCS.saddle;
    var p = g.attributes.position;
    for (var i = 0; i < p.count; i++) {
      var x = p.getX(i), y = p.getY(i);
      p.setZ(i, Math.max(-6, Math.min(6, fn(x, y))));
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
  BUILD.solid = function (spec, group) {
    var G = {
      cube: function () { return new THREE.BoxGeometry(2, 2, 2); },
      sphere: function () { return new THREE.SphereGeometry(1.4, 36, 24); },
      cylinder: function () { return new THREE.CylinderGeometry(1.1, 1.1, 2.4, 34); },
      cone: function () { return new THREE.ConeGeometry(1.3, 2.4, 34); },
      torus: function () { return new THREE.TorusGeometry(1.2, 0.42, 20, 44); },
      tetra: function () { return new THREE.TetrahedronGeometry(1.6); },
      octa: function () { return new THREE.OctahedronGeometry(1.5); },
      icosa: function () { return new THREE.IcosahedronGeometry(1.5); },
      prism: function () { return new THREE.CylinderGeometry(1.3, 1.3, 2.2, 3); }
    };
    var mk = G[spec.shape] || G.cube;
    var geo = mk();
    group.add(new THREE.Mesh(geo, new THREE.MeshStandardMaterial({
      color: spec.color || 0x4a90d9, roughness: 0.45,
      transparent: true, opacity: 0.82 })));
    group.add(new THREE.LineSegments(new THREE.EdgesGeometry(geo),
      new THREE.LineBasicMaterial({ color: 0xeafff2 })));
  };

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
      group.traverse(function (o) {
        if (o.isSprite) o.scale.multiplyScalar(k);
      });

      var ctl = orbit(cam, ren.domElement, span * 1.9);
      ctl.setRange(span * 0.55, span * 5);

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
