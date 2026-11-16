/* Web sürümü: yerel sunucunun (tools/sunucu.py) işini tarayıcıda gören modüllerin ortak kökü.
 * config.js içinde yerel: true değilse hiçbir şey tanımlanmaz; sayfalar eski yolu (sunucu) kullanır.
 * js/core.js'ten sonra yüklenir. */
(function (AT) {
  'use strict';
  if (!(AT.config && AT.config.yerel)) return;
  const yerel = AT.yerel = {};

  yerel.DEPO_YOK = 'Bu tarayıcı kipinde dersler saklanamıyor (gizli pencere olabilir). Normal bir pencerede açın.';

  let hazir = null;
  // Service worker'ı kaydeder ve sayfayı denetlemeye başlamasını bekler (ilk açılışta birkaç saniye sürebilir).
  yerel.hazirla = () => hazir || (hazir = (async () => {
    if (!('serviceWorker' in navigator) || !window.caches) throw new Error(yerel.DEPO_YOK);
    await navigator.serviceWorker.register('sw.js');
    if (navigator.serviceWorker.controller) return;
    await new Promise((tamam, hata) => {
      navigator.serviceWorker.addEventListener('controllerchange', tamam, { once: true });
      setTimeout(() => hata(new Error('Ders deposu hazır değil. Sayfayı yenileyin.')), 20000);
    });
  })());

  // Kurulu dersin dosyalarını sw.js verir; ders açılmadan önce sayfayı denetliyor olmalı.
  const dersYukle = AT.loadLesson;
  AT.loadLesson = async (entry) => { await yerel.hazirla(); return dersYukle(entry); };
})(window.AT = window.AT || {});
