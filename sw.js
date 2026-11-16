/* Çevrimdışı çalışma. İlk açılışta onbellek-listesi.json'daki tüm dosyalar
 * (oynatıcı + dersler + görseller + varsa ses) indirilir. Liste tools/paketle.mjs ile üretilir;
 * içindeki "version" değişince eski önbellek silinir.
 *
 * 4.0.2: Önce AĞ, sonra önbellek. Eskiden önce önbellekten veriliyordu; program güncellenince (aynı adres,
 * localhost:8810) tarayıcı eski board.js'i vermeyi sürdürdü ("board.animBekle is not a function").
 * Sunucu bu bilgisayarda çalıştığı için ağ her zaman hızlıdır; önbellek yalnız sunucu kapalıyken kullanılır. */
const PREFIX = 'klinik-koc-';
const SW_SURUM = '5.1.0'; // bu dosya değişince tarayıcı yeni işçiyi kurar
// Web sürümü: tarayıcıda kurulan ders paketleri (js/yerel/ders-deposu.js). Adı PREFIX ile başlamaz;
// program güncellenince silinmez.
const DERS = 'kk-ders-';

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

// lessons/<ders>/... isteği kurulu bir derse aitse dosyayı o dersin önbelleğinden verir; ders kurulu değilse null.
// Kurulu dersin pakette olmayan dosyası (ör. ses manifesti) ağda aranmaz: 404.
async function kuruluDers(req, url) {
  const m = /\/lessons\/([^/]+)\/./.exec(url.pathname);
  if (!m || !(await caches.has(DERS + m[1]))) return null;
  const y = await (await caches.open(DERS + m[1])).match(req, { ignoreSearch: true });
  if (!y) return new Response(null, { status: 404 });
  // Video oynatıcı dosyayı parça parça ister (Range); önbellekteki bütün dosyadan dilim verilir.
  const aralik = /^bytes=(\d+)-(\d*)$/.exec(req.headers.get('range') || '');
  if (!aralik) return y;
  const b = await y.blob();
  const bas = Number(aralik[1]);
  const son = aralik[2] ? Math.min(Number(aralik[2]), b.size - 1) : b.size - 1;
  if (bas > son) return new Response(null, { status: 416, headers: { 'Content-Range': 'bytes */' + b.size } });
  const basliklar = new Headers(y.headers);
  basliklar.set('Content-Range', 'bytes ' + bas + '-' + son + '/' + b.size);
  basliklar.set('Content-Length', String(son - bas + 1));
  return new Response(b.slice(bas, son + 1), { status: 206, headers: basliklar });
}

// Kurulu ders dosyaları önbellekten; gerisi önce ağ, ağ yoksa (sunucu kapalı, çevrimdışı) önbellek.
// API çağrıları hiç önbelleğe girmez.
self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== location.origin || url.pathname.startsWith('/api/')) return;
  event.respondWith((async () => {
    const ders = await kuruluDers(req, url);
    if (ders) return ders;
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
