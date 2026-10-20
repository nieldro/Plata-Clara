/* Service worker de Plata Clara.
 *
 * Solo guarda la «carcasa» de la app (HTML, JS, CSS, fuentes, íconos) para que abra rápido y muestre algo sin internet.
 * NUNCA guarda respuestas de /api: tus datos financieros no se almacenan en el dispositivo por este medio.
 */
const VERSION = "v1";
const SHELL = `plata-clara-shell-${VERSION}`;
const ASSETS = `plata-clara-assets-${VERSION}`;
const KEEP = new Set([SHELL, ASSETS]);

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(SHELL).then((c) => c.addAll(["/", "/manifest.webmanifest", "/icons/icon-192.png"])).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(names.filter((n) => n.startsWith("plata-clara-") && !KEEP.has(n)).map((n) => caches.delete(n))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Solo GET del mismo sitio, y jamás la API ni nada que pueda traer datos de la persona.
  if (req.method !== "GET" || url.origin !== self.location.origin || url.pathname.startsWith("/api")) return;

  // Páginas: primero la red (siempre la versión más nueva); sin conexión, la última carcasa guardada.
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res.ok) caches.open(SHELL).then((c) => c.put("/", res.clone()));
          return res;
        })
        .catch(() => caches.match("/").then((hit) => hit || new Response("Sin conexión", { status: 503, headers: { "Content-Type": "text/plain; charset=utf-8" } }))),
    );
    return;
  }

  // Archivos con hash en el nombre (/assets/…): nunca cambian, así que primero la copia guardada.
  if (url.pathname.startsWith("/assets/") || url.pathname.startsWith("/icons/")) {
    event.respondWith(
      caches.open(ASSETS).then((cache) =>
        cache.match(req).then((hit) => hit || fetch(req).then((res) => {
          if (res.ok) cache.put(req, res.clone());
          return res;
        })),
      ),
    );
  }
});
