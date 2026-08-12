/* Run the scene builders outside a browser, against the real three.js.
 *
 * three3d.js is an IIFE that keeps its builders private and hands the page a
 * mount() needing WebGL, which is not available here. So its body is
 * evaluated in a context with three.js injected and BUILD lifted out — the
 * file itself keeps no test hook, because a hook in shipped code is a hook
 * somebody can call.
 *
 * What this buys is the thing string-matching a test file cannot: whether
 * the geometry is actually there, where it ended up, and whether the physics
 * came out right.
 */
import fs from "fs";
import vm from "vm";
import path from "path";
import { fileURLToPath } from "url";
import * as THREE from "../three.module.js";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const src = fs.readFileSync(path.join(ROOT, "three3d.js"), "utf8");
const inner = src.slice(src.indexOf("{", src.indexOf("(function")) + 1,
                        src.lastIndexOf("})()"));

const ctx = {
  _THREE: THREE, console,
  window: {}, performance: { now: () => 0 },
  document: {
    createElement: () => ({
      getContext: () => ({
        font: "", textBaseline: "", fillStyle: "",
        measureText: () => ({ width: 40 }),
        fillRect() {}, fillText() {}, beginPath() {}, roundRect() {}, fill() {}
      }),
      width: 0, height: 0
    })
  },
  ResizeObserver: class { observe() {} disconnect() {} }
};
vm.createContext(ctx);
vm.runInContext(inner + "\n; THREE = _THREE; globalThis.__B = BUILD;", ctx);

export const BUILD = ctx.__B;
export { THREE };

export function build(kind, spec) {
  const g = new THREE.Group();
  BUILD[kind](spec, g);
  return g;
}

export function census(g) {
  let meshes = 0, lines = 0, labels = 0;
  const text = [];
  g.traverse(o => {
    if (o.isMesh) meshes++;
    if (o.isLine) lines++;
    if (o.isSprite) labels++;
  });
  const box = new THREE.Box3().setFromObject(g);
  const size = box.getSize(new THREE.Vector3());
  return { meshes, lines, labels, text,
           size: [size.x, size.y, size.z] };
}

/* Where every line of a field ends up, which is the only way to check that
   the integrator followed the field rather than a drawn curve. */
export function lineEnds(g) {
  const ends = [];
  g.traverse(o => {
    if (!o.isLine) return;
    const p = o.geometry.attributes.position;
    ends.push([p.getX(p.count - 1), p.getY(p.count - 1), p.getZ(p.count - 1)]);
  });
  return ends;
}
