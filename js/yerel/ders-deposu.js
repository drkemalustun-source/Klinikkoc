/* Ders paketi (.zip) tarayıcıda kurulur: tools/ders_paketi.py'nin (paketi_incele, yukle, katalog_guncelle)
 * tarayıcı karşılığı. Dosyalar Cache Storage'a kendi adresleriyle yazılır (lessons/<ders>/...); sw.js onları
 * ağdan önce verir, bu yüzden oynatıcı ders dosyalarını her zamanki adreslerinden okur.
 *   kk-ders-<ders>  bir dersin dosyaları        kk-katalog  ders listesi
 * Hiçbir şey sunucuya gönderilmez; ders yalnız bu tarayıcıda durur. js/yerel/zip.js'ten sonra yüklenir. */
(function (AT) {
  'use strict';
  const yerel = AT.yerel;
  if (!yerel) return;

  const EN_BUYUK = 500 * 1024 * 1024;   // açılmış toplam boyut sınırı
  const EN_COK_DOSYA = 5000;
  const ATLA = ['makale-metin/', 'audio/'];               // öğrencinin cihazında üretilir: pakette gelirse atlanır
  const KORU = ['makale-metin/', 'audio/', 'videolar/'];  // güncellemede yerinde kalır
  const ONEK = 'kk-ders-', KATALOG = 'kk-katalog';
  const TUR = {
    json: 'application/json', txt: 'text/plain; charset=utf-8', md: 'text/plain; charset=utf-8',
    png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', gif: 'image/gif', webp: 'image/webp', svg: 'image/svg+xml',
    mp4: 'video/mp4', m4v: 'video/mp4', webm: 'video/webm', ogv: 'video/ogg', mov: 'video/quicktime',
    mp3: 'audio/mpeg', wav: 'audio/wav', pdf: 'application/pdf'
  };

  // Zip'i açmadan denetler (paketi_incele ile aynı kurallar ve iletiler). Dönen: { ders, alinacak: [{ g, ic }] }.
  yerel.paketiIncele = (girdiler) => {
    const adlar = girdiler.filter((g) => !g.ad.endsWith('/'));
    if (!adlar.length) throw new Error('Paket boş.');
    if (adlar.length > EN_COK_DOSYA) throw new Error('Pakette çok fazla dosya var.');
    const kokler = new Set();
    const alinacak = [];
    let toplam = 0;
    for (const g of adlar) {
      const ad = g.ad.replace(/\\/g, '/');
      if (ad.startsWith('/') || /^[A-Za-z]:/.test(ad) || ad.split('/').includes('..')) {
        throw new Error('Pakette güvensiz bir dosya yolu var: ' + ad);
      }
      if (ad.startsWith('__MACOSX/') || ['.DS_Store', 'Thumbs.db'].includes(ad.split('/').pop())) continue;
      const bol = ad.indexOf('/');
      if (bol < 0) throw new Error('Paketin içinde tek bir ders klasörü olmalı (dosya kökte: ' + ad + ').');
      kokler.add(ad.slice(0, bol));
      const ic = ad.slice(bol + 1);
      if (ATLA.some((a) => ic.startsWith(a))) continue;
      toplam += g.boyut;
      alinacak.push({ g, ic });
    }
    if (toplam > EN_BUYUK) throw new Error('Paket açılınca çok büyük (en çok 500 MB).');
    if (kokler.size !== 1) throw new Error('Paketin içinde tek bir ders klasörü olmalı; bulunan: ' + [...kokler].sort().join(', '));
    const ders = [...kokler][0];
    if (!/^[A-Za-z0-9][A-Za-z0-9_-]{0,80}$/.test(ders) || ders === 'tanitim') throw new Error('Ders kimliği uygun değil: ' + ders);
    if (!alinacak.some((a) => a.ic === 'ders.json' || a.ic === 'egitmen.json')) {
      throw new Error('Bu bir KlinikKoç ders paketi değil (ders.json ya da egitmen.json yok).');
    }
    return { ders, alinacak };
  };

  // Ders listesindeki giriş (katalog_guncelle ile aynı alanlar ve sıra).
  yerel.katalogGirisi = (ders, d, eg) => {
    const giris = { id: ders, title: d.title || eg.baslik || ders, level: d.level || eg.duzey || null, path: 'lessons/' + ders + '/' };
    if (d.subtitle) giris.subtitle = d.subtitle;
    if (d.estimatedMinutes) giris.estimatedMinutes = d.estimatedMinutes;
    return giris;
  };

  // '?' ve '#' adres ayracıdır; dosya adında geçerse kaçırılır. Gerisini tarayıcının adres çözücüsü yapar.
  const adres = (yol) => new URL(yol.replace(/[?#]/g, encodeURIComponent), document.baseURI).href;
  const KATALOG_ADRESI = () => adres('lessons/katalog.json');

  // Paketteki bir dosya adres çubuğundan doğrudan açılırsa sayfanın yetkileriyle çalışmasın: sandbox.
  const yanit = (blob, ic) => new Response(blob, {
    headers: {
      'Content-Type': TUR[ic.split('.').pop().toLowerCase()] || 'application/octet-stream',
      'Content-Length': String(blob.size),
      'Content-Security-Policy': 'sandbox',
      'X-Content-Type-Options': 'nosniff'
    }
  });

  // Ders listesi doğrudan depodan okunur (sw.js'i beklemez; ana sayfa ilk açılışta da hemen çizilir).
  yerel.katalog = async () => {
    if (!window.caches) return { lessons: [] };
    const y = await (await caches.open(KATALOG)).match(KATALOG_ADRESI());
    return y ? y.json() : { lessons: [] };
  };
  AT.loadCatalog = yerel.katalog;

  const katalogYaz = async (kat) => (await caches.open(KATALOG)).put(KATALOG_ADRESI(),
    new Response(JSON.stringify(kat, null, 2) + '\n', { headers: { 'Content-Type': 'application/json' } }));

  const jsonOku = async (dosya, alinacak, ic) => {
    const a = alinacak.find((x) => x.ic === ic);
    if (!a) return {};
    try { return JSON.parse(await (await yerel.zipAc(dosya, a.g)).text()) || {}; } catch (e) { return {}; }
  };

  // Paketi kurar. dosya: File ya da Blob. Ders kuruluysa ve uzerine verilmediyse kod: 409 taşıyan hata fırlatır.
  // Güncellemede yeni dosyalar eskilerin üzerine yazılır, pakette artık olmayanlar silinir; yarıda kalırsa
  // ders listesi eski hâliyle durur ve paket yeniden bırakılınca tamamlanır.
  yerel.dersKur = async (dosya, sec = {}) => {
    if (!window.caches) throw new Error(yerel.DEPO_YOK);
    const { ders, alinacak } = yerel.paketiIncele(await yerel.zipOku(dosya));
    const kat = await yerel.katalog();
    const kurulu = kat.lessons.some((g) => g.id === ders);
    if (kurulu && !sec.uzerine) {
      throw Object.assign(new Error("'" + ders + "' dersi zaten kurulu. Güncellemek için üzerine yazmayı seçin."), { kod: 409 });
    }
    if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(() => {});
    const kok = adres('lessons/' + ders + '/');
    const c = await caches.open(ONEK + ders);
    const yeni = new Set();
    try {
      for (const { g, ic } of alinacak) {
        // .js kopyaları yalnız file:// içindir; tarayıcıda kurulu derste çalıştırılabilir dosya saklanmaz.
        if (/\.js$/i.test(ic)) continue;
        const a = adres('lessons/' + ders + '/' + ic);
        await c.put(a, yanit(await yerel.zipAc(dosya, g), ic));
        yeni.add(a);
      }
    } catch (e) {
      if (!kurulu) await caches.delete(ONEK + ders);
      throw e.name === 'QuotaExceededError' ? new Error('Tarayıcıda yer kalmadı; ders kurulamadı.') : e;
    }
    for (const istek of await c.keys()) {
      if (!yeni.has(istek.url) && !KORU.some((k) => istek.url.startsWith(kok + k))) await c.delete(istek);
    }
    const giris = yerel.katalogGirisi(ders, await jsonOku(dosya, alinacak, 'ders.json'), await jsonOku(dosya, alinacak, 'egitmen.json'));
    kat.lessons = kat.lessons.filter((g) => g.id !== ders).concat(giris);
    await katalogYaz(kat);
    const kj = await jsonOku(dosya, alinacak, 'kaynaklar/kaynaklar.json');
    return { ders, baslik: giris.title, makale: (kj.kaynaklar || []).length };
  };

  yerel.dersKaldir = async (ders) => {
    await caches.delete(ONEK + ders);
    const kat = await yerel.katalog();
    kat.lessons = kat.lessons.filter((g) => g.id !== ders);
    await katalogYaz(kat);
  };
})(window.AT = window.AT || {});
