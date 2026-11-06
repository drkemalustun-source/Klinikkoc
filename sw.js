/* Çevrimdışı çalışma. İlk açılışta onbellek-listesi.json'daki tüm dosyalar
 * (oynatıcı + dersler + görseller + varsa ses) indirilir. Liste tools/paketle.mjs ile üretilir;
 * içindeki "version" değişince eski önbellek silinir. */
const PREFIX = 'akilli-tahta-';

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const res = await fetch('onbellek-listesi.json', { cache: 'no-cache' });
    const list = await res.json();
    const cache = await caches.open(PREFIX + list.version);
    // Tek dosya eksik diye kurulum bozulmasın; tek tek ekle.
    await Promise.all(list.files.map((f) => cache.add(new Request(f, { cache: 'reload' })).catch((e) => console.warn('Önbelleğe alınamadı:', f, e))));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const res = await fetch('onbellek-listesi.json', { cache: 'no-cache' }).catch(() => null);
    const current = res && res.ok ? PREFIX + (await res.json()).version : null;
    if (current) {
      for (const k of await caches.keys()) if (k.startsWith(PREFIX) && k !== current) await caches.delete(k);
    }
    await self.clients.claim();
  })());
});

// Önce önbellek; yoksa ağdan al ve önbelleğe ekle. JSON dosyaları için önce ağ (güncel ders).
self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== location.origin) return;
  const isJson = req.url.split('?')[0].endsWith('.json');
  event.respondWith((async () => {
    const cached = await caches.match(req, { ignoreSearch: true });
    if (cached && !isJson) return cached;
    try {
      const res = await fetch(req);
      if (res.ok && cached) {
        const keys = await caches.keys();
        const name = keys.filter((k) => k.startsWith(PREFIX)).pop();
        if (name) (await caches.open(name)).put(req, res.clone());
      }
      return res;
    } catch (e) {
      if (cached) return cached;
      throw e;
    }
  })());
});
