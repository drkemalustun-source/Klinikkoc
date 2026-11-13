/*
 * Tahtanın görüntüsü (v5, C aşaması): Claude tahtaya ne çizildiğini görebilsin diye tahta alanının PNG'sini çıkarır.
 * Dış kitaplık kullanmaz, çevrimdışı çalışır: tahta öğesi kopyalanır, sayfanın stil dosyaları ve resimler
 * (data: adresine çevrilerek) içine gömülür, SVG <foreignObject> içinde bir tuvale çizilir.
 * Çizim animasyonları (stroke-in, solma) kopyada kapatılır; her öğenin O ANKİ görünümü (çizginin ne kadarı
 * çizildi, saydamlık) satır içi stile yazılır. Böylece görüntü ekranda görüneni verir.
 * Kullanım: AT.tahtaGoruntu(document.getElementById('board'), { enFazla: 1400 }) → Promise<{ png, en, boy }>
 */
(function () {
  'use strict';
  const AT = (window.AT = window.AT || {});
  const SVG_NS = 'http://www.w3.org/2000/svg';
  // Animasyonla değişen ve kopyada donmuş hâli korunması gereken özellikler
  const ANLIK = ['opacity', 'stroke-dashoffset', 'stroke-dasharray', 'fill-opacity', 'stroke-opacity', 'transform',
    'visibility', 'clip-path'];

  function stilMetni() {
    let css = '';
    for (const s of Array.from(document.styleSheets)) {
      try {
        for (const r of Array.from(s.cssRules || [])) css += r.cssText + '\n';
      } catch (e) { /* başka kökenden stil: okunamaz, atlanır */ }
    }
    // Kopyada animasyonlar baştan oynamasın; o anki görünüm satır içi stilde.
    css += '*,*::before,*::after{animation:none!important;transition:none!important}';
    return css;
  }

  function dataAdresi(url) {
    return fetch(url, { cache: 'force-cache' })
      .then((r) => (r.ok ? r.blob() : Promise.reject(new Error(r.status))))
      .then((b) => new Promise((ok, hata) => {
        const f = new FileReader();
        f.onload = () => ok(f.result);
        f.onerror = hata;
        f.readAsDataURL(b);
      }));
  }

  async function resimleriGom(asil, kopya) {
    const a = asil.querySelectorAll('img, image, canvas, video');
    const k = kopya.querySelectorAll('img, image, canvas, video');
    const isler = [];
    for (let i = 0; i < a.length; i++) {
      const o = a[i], c = k[i];
      if (!c) continue;
      const tag = o.tagName.toLowerCase();
      if (tag === 'canvas') {
        const img = document.createElement('img');
        try { img.src = o.toDataURL('image/png'); } catch (e) { /* kirli tuval */ }
        img.setAttribute('style', o.getAttribute('style') || '');
        img.className = o.className;
        img.width = o.clientWidth; img.height = o.clientHeight;
        c.replaceWith(img);
      } else if (tag === 'video') {
        // Video karesi: aynı kökenden ise tuvale çizilebilir; değilse yer tutucu.
        const img = document.createElement('img');
        try {
          const t = document.createElement('canvas');
          t.width = o.videoWidth || o.clientWidth; t.height = o.videoHeight || o.clientHeight;
          t.getContext('2d').drawImage(o, 0, 0, t.width, t.height);
          img.src = t.toDataURL('image/jpeg', 0.8);
        } catch (e) { img.alt = '[video]'; }
        img.style.width = o.clientWidth + 'px'; img.style.height = o.clientHeight + 'px';
        c.replaceWith(img);
      } else {
        const ozellik = tag === 'img' ? 'src' : (c.hasAttribute('href') ? 'href' : 'xlink:href');
        const src = tag === 'img' ? (o.currentSrc || o.src) : (o.href && o.href.baseVal) || o.getAttribute(ozellik);
        if (!src || src.startsWith('data:')) continue;
        isler.push(dataAdresi(src).then((d) => c.setAttribute(ozellik, d)).catch(() => c.removeAttribute(ozellik)));
      }
    }
    await Promise.all(isler);
  }

  function anlikStilleriYaz(asil, kopya) {
    const a = [asil].concat(Array.from(asil.querySelectorAll('*')));
    const k = [kopya].concat(Array.from(kopya.querySelectorAll('*')));
    for (let i = 0; i < a.length && i < k.length; i++) {
      const o = a[i];
      const animli = typeof o.getAnimations === 'function' && o.getAnimations().length > 0;
      if (!animli && !(o instanceof SVGElement)) continue;
      const cs = getComputedStyle(o);
      for (const p of ANLIK) {
        const v = cs.getPropertyValue(p);
        if (v) k[i].style.setProperty(p, v);
      }
    }
    // Form alanlarının o anki değeri (yazı kutusu, seçim) özniteliğe geçmez; elle yazılır.
    a.forEach((o, i) => {
      if (o.tagName === 'INPUT' && k[i]) {
        if (o.type === 'checkbox' || o.type === 'radio') { if (o.checked) k[i].setAttribute('checked', ''); } else k[i].setAttribute('value', o.value);
      }
    });
  }

  // Seçicilerin (ör. .canli:not([data-zemin="koyu"]) .board) kopyada da tutması için ataları sığ kopyalarla sarılır.
  function atalarlaSar(asil, kopya) {
    let ic = kopya;
    for (let p = asil.parentElement; p && p !== document.documentElement; p = p.parentElement) {
      const s = p.cloneNode(false);
      s.removeAttribute('hidden');
      s.style.display = 'block';
      s.style.width = 'auto'; s.style.height = 'auto';
      s.style.margin = '0'; s.style.padding = '0'; s.style.overflow = 'visible';
      s.style.position = 'static'; s.style.transform = 'none';
      s.appendChild(ic);
      ic = s;
    }
    return ic;
  }

  async function tahtaGoruntu(el, secenek) {
    secenek = secenek || {};
    if (!el) throw new Error('tahta bulunamadı');
    const kutu = el.getBoundingClientRect();
    const en = Math.max(1, Math.round(kutu.width)), boy = Math.max(1, Math.round(kutu.height));
    const kopya = el.cloneNode(true);
    anlikStilleriYaz(el, kopya);
    await resimleriGom(el, kopya);
    kopya.style.width = en + 'px';
    kopya.style.height = boy + 'px';
    kopya.style.margin = '0';
    kopya.style.boxSizing = 'border-box';
    const sarili = atalarlaSar(el, kopya);
    const html = document.createElement('html');
    html.setAttribute('xmlns', 'http://www.w3.org/1999/xhtml');
    const govde = document.createElement('body');
    govde.setAttribute('style', 'margin:0;background:transparent');
    const stil = document.createElement('style');
    stil.textContent = stilMetni();
    html.appendChild(stil);
    govde.appendChild(sarili);
    html.appendChild(govde);
    const xhtml = new XMLSerializer().serializeToString(html);
    const svg = '<svg xmlns="' + SVG_NS + '" width="' + en + '" height="' + boy + '">' +
      '<foreignObject x="0" y="0" width="100%" height="100%">' + xhtml + '</foreignObject></svg>';
    const resim = await new Promise((ok, hata) => {
      const r = new Image();
      r.onload = () => ok(r);
      r.onerror = () => hata(new Error('tahta görüntüsü çizilemedi'));
      r.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
    });
    const enFazla = secenek.enFazla || 1400;
    const olcek = Math.min(secenek.olcek || 1.5, enFazla / en);
    const tuval = document.createElement('canvas');
    tuval.width = Math.round(en * olcek); tuval.height = Math.round(boy * olcek);
    const c = tuval.getContext('2d');
    // Zemin: tahtanın kendi rengi (saydam köşeler beyaz/siyah görünmesin)
    c.fillStyle = getComputedStyle(el).backgroundColor || '#FAF7F0';
    c.fillRect(0, 0, tuval.width, tuval.height);
    c.drawImage(resim, 0, 0, tuval.width, tuval.height);
    return { png: tuval.toDataURL('image/png'), en: tuval.width, boy: tuval.height };
  }

  AT.tahtaGoruntu = tahtaGoruntu;
})();
