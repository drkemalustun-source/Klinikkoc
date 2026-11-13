/* Çevrimdışı çalışma. İlk açılışta onbellek-listesi.json'daki tüm dosyalar
 * (oynatıcı + dersler + görseller + varsa ses) indirilir. Liste tools/paketle.mjs ile üretilir;
 * içindeki "version" değişince eski önbellek silinir.
 *
 * 4.0.2: Önce AĞ, sonra önbellek. Eskiden önce önbellekten veriliyordu; program güncellenince (aynı adres,
 * localhost:8810) tarayıcı eski board.js'i vermeyi sürdürdü ("board.animBekle is not a function").
 * Sunucu bu bilgisayarda çalıştığı için ağ her zaman hızlıdır; önbellek yalnız sunucu kapalıyken kullanılır. */
const PREFIX = 'klinik-koc-';
const SW_SURUM = '4.0.2'; // bu dosya değişince tarayıcı yeni işçiyi kurar

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    try {
      const res = await fetch('onbellek-listesi.json', { cache: 'no-cache' });
      const list = await res.json();
      const cache = await caches.open(PREFIX + list.version);
      // Tek dosya eksik diye kurulum bozulmasın; tek tek ekle.
      await Promise.all(list.files.map((f) => cache.add(new Request(f, { cache: 'reload' })).catch((e) => console.warn('Önbelleğe alınamadı:', f, e))));
    } catch (e) {
      console.warn('Önbellek listesi alınamadı:', e);
    }
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const res = await fetch('onbellek-listesi.json', { cache: 'no-cache' }).catch(() => null);
    const current = res && res.ok ? PREFIX + (await res.json()).version : null;
    let eskiVardi = false;
    if (current) {
      for (const k of await caches.keys()) {
        if (k.startsWith(PREFIX) && k !== current) { eskiVardi = true; await caches.delete(k); }
      }
    }
    await self.clients.claim();
    // Eski sürümün önbelleğinden açılmış sayfalar yeniden yüklensin (yeni dosyalar ağdan gelir).
    if (eskiVardi) {
      for (const c of await self.clients.matchAll({ type: 'window' })) {
        try { c.navigate(c.url); } catch (e) { /* bazı tarayıcılar izin vermez; sayfa sürüm denetimiyle kendini yeniler */ }
      }
    }
  })());
});

// Önce ağ; ağ yoksa (sunucu kapalı, çevrimdışı) önbellek. API çağrıları hiç önbelleğe girmez.
self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== location.origin || url.pathname.startsWith('/api/')) return;
  event.respondWith((async () => {
    try {
      const res = await fetch(req, { cache: 'no-cache' });
      if (res.ok && res.status === 200 && !req.headers.has('range')) {
        const cached = await caches.match(req, { ignoreSearch: true });
        if (cached) {
          const keys = await caches.keys();
          const name = keys.filter((k) => k.startsWith(PREFIX)).pop();
          if (name) (await caches.open(name)).put(req, res.clone()).catch(() => {});
        }
      }
      return res;
    } catch (e) {
      const cached = await caches.match(req, { ignoreSearch: true });
      if (cached) return cached;
      throw e;
    }
  })());
});
