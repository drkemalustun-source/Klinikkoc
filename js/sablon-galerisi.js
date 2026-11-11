/* Çizim şablonları galerisi: şablonları eğitmen olmadan görmek ve durumlar arası geçişi denemek için. */
(function () {
  'use strict';
  const A = window.AT.anatomi;
  const tahta = document.getElementById('sgTahta');
  const sablonSec = document.getElementById('sgSablon');
  const etiketSec = document.getElementById('sgEtiket');
  const sonda = document.getElementById('sgSonda');
  const durumlar = document.getElementById('sgDurumlar');
  let sablon = 'dis', varyant = null, simdiki = null, kare = 0;

  function ciz(p, bitti) {
    while (tahta.firstChild) tahta.removeChild(tahta.firstChild);
    const etiket = etiketSec.value === 'yok' ? [] : etiketSec.value;
    A.ciz(tahta, { template: sablon, variant: varyant, probe: sonda.checked, labels: bitti ? etiket : [], p }, true);
  }
  function git(yeni) {
    cancelAnimationFrame(kare);
    const hedef = A.durum(sablon, yeni), bas = simdiki;
    varyant = yeni;
    for (const b of durumlar.children) b.classList.toggle('secili', b.dataset.v === yeni);
    if (!bas || !hedef) { simdiki = hedef; ciz(undefined, true); return; }
    const t0 = performance.now(), sure = 2500;
    const adim = (t) => {
      const k = Math.min(1, (t - t0) / sure), e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      if (k < 1) { ciz(A.araDurum(sablon, bas, hedef, e), false); kare = requestAnimationFrame(adim); }
      else { simdiki = hedef; ciz(undefined, true); }
    };
    kare = requestAnimationFrame(adim);
  }
  function sablonKur() {
    cancelAnimationFrame(kare);
    sablon = sablonSec.value; simdiki = null;
    durumlar.textContent = '';
    for (const v of A.SABLONLAR[sablon].varyantlar) {
      const b = document.createElement('button');
      b.type = 'button'; b.textContent = v; b.dataset.v = v;
      b.addEventListener('click', () => git(v));
      durumlar.appendChild(b);
    }
    git(A.SABLONLAR[sablon].varyantlar[0]);
  }
  for (const k of Object.keys(A.SABLONLAR)) {
    const o = document.createElement('option');
    o.value = k; o.textContent = A.SABLONLAR[k].ad || k;
    sablonSec.appendChild(o);
  }
  sablonSec.addEventListener('change', sablonKur);
  etiketSec.addEventListener('change', () => ciz(undefined, true));
  sonda.addEventListener('change', () => ciz(undefined, true));
  sablonKur();
})();
