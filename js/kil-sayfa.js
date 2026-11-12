/* Eski sayfaları (makaleler, sihirbaz, kılavuz, değerlendirme, şablon galerisi) kil arayüzüne uydurur.
   <body>'nin ilk satırında yüklenir. ?gomulu=1 ile ana ekranın panelinde açıldığında kendi başlık bağlantıları gizlenir. */
(function () {
  'use strict';
  var q = new URLSearchParams(location.search);
  var gomulu = q.get('gomulu') === '1' && window.parent !== window;
  document.body.classList.add('kil');
  if (gomulu) document.body.classList.add('gomulu');
  window.KK = { gomulu: gomulu, bolum: q.get('bolum') || '', kabuk: q.get('kabuk') || '',
    degisti: function () { if (gomulu) { try { window.parent.postMessage({ klinikkoc: 'degisti' }, location.origin); } catch (e) { /* yok */ } } } };
  document.addEventListener('DOMContentLoaded', function () {
    // Eski "‹ Dersler" bağlantıları artık ana ekrana döner.
    document.querySelectorAll('a.mk-geri[href="index.html"], main > a[href="index.html"]').forEach(function (a) {
      a.setAttribute('href', 'ana.html'); a.textContent = '‹ Ana ekran';
    });
    if (window.KK.bolum) {
      // Yalnız istenen bölüm görünür (ör. makaleler.html?bolum=depolama).
      var hedef = document.getElementById(window.KK.bolum);
      if (hedef) document.querySelectorAll('main > section, main > .mk-alt, main > header').forEach(function (s) { if (s !== hedef) s.hidden = true; });
    }
  });
}());
