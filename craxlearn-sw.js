/* Craxlearn's service worker.
 *
 * It exists so the app can be INSTALLED — a smart board's browser will only
 * offer "install" for a page with a manifest and a service worker, and an
 * icon on the board's home screen is the difference between a teacher
 * opening this and a teacher opening whatever was already there.
 *
 * What it deliberately does NOT do is cache the app's data. A lesson, a
 * register, a fee balance and a mark are all things where a stale answer is
 * worse than no answer, and a classroom device that has been on the same
 * wall for two years is exactly where a stale cache lives forever. So:
 *
 *   - the shell (page, styles, the board modules) is cached, and served
 *     from cache only when the network fails
 *   - anything under /api/ is never cached, never served from cache, and
 *     never even looked at here
 *
 * That gives an installable app that opens instantly and still tells the
 * truth, and it fails honestly when the school's wifi does: the shell
 * appears and says it cannot reach the server, rather than showing last
 * Tuesday's homework as though it were today's.
 */
var CACHE = "craxlearn-shell-v1";
var SHELL = [
  "/craxlearn",
  "/sqlboard.js",
  "/net.js",
  "/lab.js",
  "/icon-192.png",
  "/icon-512.png"
];

self.addEventListener("install", function (e) {
  // addAll rejects the whole install if any one file 404s, which would
  // leave the app uninstallable for a reason nobody would look for. Each
  // file is added on its own and a miss is survivable.
  e.waitUntil(caches.open(CACHE).then(function (c) {
    return Promise.all(SHELL.map(function (u) {
      return c.add(u).catch(function () { return null; });
    }));
  }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.map(function (k) {
      return k === CACHE ? null : caches.delete(k);
    }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener("fetch", function (e) {
  var req = e.request;
  if (req.method !== "GET") return;
  var url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  // Never the API. Not cached, not read from cache, not touched.
  if (url.pathname.indexOf("/api/") === 0) return;

  e.respondWith(
    fetch(req).then(function (res) {
      if (res && res.ok) {
        var copy = res.clone();
        caches.open(CACHE).then(function (c) { c.put(req, copy); });
      }
      return res;
    }).catch(function () {
      return caches.match(req).then(function (hit) {
        return hit || caches.match("/craxlearn");
      });
    })
  );
});
