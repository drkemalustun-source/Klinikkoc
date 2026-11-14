/*
 * Öğrencinin şablon üzerinde yanıt vermesi (v5, E aşaması). board.js'ten sonra yüklenir.
 *
 * 1) İşaretleme: draw komutunda isaretle: {soru, dogru?: [parça], coklu?: true}
 *    Öğrenci şablonda bir bölgeye dokunur; dokunulan parça vurgulanır ve "İşaretleme · soru: parça adı" Claude'a
 *    öğrencinin sözü olarak gider. dogru verilmişse hemen yeşil/kırmızı gösterilir ve sonuç da iletilir.
 * 2) Etiket sürükleme: draw komutunda etiket_surukle: {etiketler: [parça], soru?}
 *    Şablon etiketsiz çizilir; altta etiket kartları çıkar. Öğrenci her kartı çizimde yerine sürükler. Hepsi
 *    yerleşince doğru/yanlış gösterilir ve "Etiket yerleştirme: 3/4 doğru (…)" Claude'a gider. Claude doğruluğu
 *    kesin bilir: her parçanın şablondaki yeri bellidir (bırakılan nokta parçanın üstünde ya da yakınındaysa doğru).
 * Sonuç Board.onYanit(metin) ile canlı tahtaya iletilir.
 */
(function (AT) {
  'use strict';
  if (!AT.Board) return;
  const NS = 'http://www.w3.org/2000/svg';
  const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
  const svg = (tag, attrs, ust) => { const n = document.createElementNS(NS, tag); for (const k in attrs) if (attrs[k] != null) n.setAttribute(k, attrs[k]); if (ust) ust.appendChild(n); return n; };
  const YAKIN = 6.5; // birim: bırakılan nokta parçanın etiket noktasına bu kadar yakınsa da doğru sayılır
  const TOLERANS_PX = 24; // ince/kısa parçalarda (çizgi, bant, nokta) bırakılan yer parçaya bu kadar yakınsa doğru sayılır
  const INCE_PX = 34;     // ekranda kısa kenarı bundan küçük olan parça "ince" sayılır

  // Şablonun parça listesi (ad ve etiket noktası), çizimi etkilemeden hesaplanır.
  function parcalar(c) {
    const s = AT.anatomi && AT.anatomi.SABLONLAR[c.template];
    if (!s) return {};
    const g = document.createElementNS(NS, 'g');
    return s.ciz(g, c.variant || s.varyantlar[0], { probe: !!c.probe, p: c.p, olcu: c.olcu }) || {};
  }

  // Parçanın çizimdeki şekilleri (etiket ve etkileşim katmanları hariç).
  function parcaDugumleri(s, part) {
    return [...s.querySelectorAll(`[data-part="${CSS.escape(part)}"]`)].filter((n) => !n.closest('.an-etiketler, .etk-katman'));
  }

  // Ekran noktasının bir parçaya uzaklığı (px). Parça yalnız çizgiyse ya da küçükse ince: true.
  function parcaUzakligi(s, part, x, y) {
    let en = Infinity, ince = false, var_ = false;
    for (const n of parcaDugumleri(s, part)) {
      const m = n.getScreenCTM && n.getScreenCTM();
      if (!m) continue;
      var_ = true;
      const r = n.getBoundingClientRect();
      const cizgi = getComputedStyle(n).fill === 'none';
      if (cizgi || Math.min(r.width, r.height) < INCE_PX) ince = true;
      if (!cizgi && x >= r.left && x <= r.right && y >= r.top && y <= r.bottom && n.isPointInFill) {
        const p = s.createSVGPoint(); p.x = x; p.y = y;
        try { if (n.isPointInFill(p.matrixTransform(m.inverse()))) return { px: 0, ince }; } catch (e) { /* eski tarayıcı */ }
      }
      if (n.getTotalLength) {
        const L = n.getTotalLength(), adim = Math.max(8, Math.min(120, Math.ceil(L / 0.6)));
        for (let i = 0; i <= adim; i++) {
          const q = n.getPointAtLength((L * i) / adim).matrixTransform(m);
          en = Math.min(en, Math.hypot(q.x - x, q.y - y));
        }
      } else {
        const dx = Math.max(r.left - x, 0, x - r.right), dy = Math.max(r.top - y, 0, y - r.bottom);
        en = Math.min(en, Math.hypot(dx, dy));
      }
    }
    return var_ ? { px: en, ince } : null;
  }

  // Bırakılan noktaya en yakın parça (aday listesinden): {part, px}.
  function enYakinParca(s, adaylar, x, y) {
    let iyi = null;
    for (const k of adaylar) {
      const u = parcaUzakligi(s, k, x, y);
      if (u && (!iyi || u.px < iyi.px)) iyi = { part: k, px: u.px };
    }
    return iyi;
  }

  function svgNokta(s, x, y) {
    const pt = s.createSVGPoint();
    pt.x = x; pt.y = y;
    const m = s.getScreenCTM();
    return m ? pt.matrixTransform(m.inverse()) : { x: 0, y: 0 };
  }

  // Ekrandaki noktanın altındaki şablon parçası (etiket katmanı ve etkileşim katmanı hariç).
  function noktadakiParca(s, x, y) {
    for (const n of document.elementsFromPoint(x, y)) {
      if (!s.contains(n)) continue;
      if (n.closest('.an-etiketler, .etk-katman')) continue;
      const p = n.closest('[data-part]');
      if (p) return p.dataset.part;
    }
    return null;
  }

  function isaretle(board, wrap, s, c, parts) {
    const o = c.isaretle || {};
    const tk = (AT.anatomi.SABLONLAR[c.template] || {}).takma || {};
    const dogru = new Set([].concat(o.dogru || []).map((k) => (tk[k] && !parts[k] ? tk[k] : k)));
    const soru = el('div', 'etk-soru', o.soru || 'İstenen bölgeye dokunun');
    wrap.insertBefore(soru, s.nextSibling);
    wrap.classList.add('etk-isaretle');
    let bitti = false;
    s.addEventListener('click', (e) => {
      if (bitti) return;
      const part = noktadakiParca(s, e.clientX, e.clientY);
      if (!part) return;
      s.querySelectorAll('.etk-secili').forEach((n) => n.classList.remove('etk-secili', 'etk-dogru', 'etk-yanlis'));
      const sinif = dogru.size ? (dogru.has(part) ? 'etk-dogru' : 'etk-yanlis') : '';
      s.querySelectorAll(`[data-part="${CSS.escape(part)}"]`).forEach((n) => n.classList.add('etk-secili', ...(sinif ? [sinif] : [])));
      const ad = (parts[part] && parts[part].ad) || part;
      if (dogru.size) {
        soru.textContent = (dogru.has(part) ? '✓ ' : '✗ ') + ad;
        soru.classList.add(dogru.has(part) ? 'dogru' : 'yanlis');
        if (!o.coklu) bitti = true;
      } else {
        soru.textContent = 'Seçiminiz: ' + ad;
      }
      const sonuc = dogru.size ? (dogru.has(part) ? ' (doğru)' : ' (yanlış)') : '';
      if (board.onYanit) board.onYanit(`İşaretleme · ${o.soru || ''}: ${ad} [${part}]${sonuc}`);
    });
  }

  function etiketSurukle(board, wrap, s, c, parts) {
    const o = c.etiket_surukle || {};
    const tk = (AT.anatomi.SABLONLAR[c.template] || {}).takma || {};
    const liste = [].concat(o.etiketler || []).map((k) => (tk[k] && !parts[k] ? tk[k] : k)).filter((k) => parts[k]);
    if (!liste.length) return;
    const katman = svg('g', { class: 'etk-katman' }, s);
    const raf = el('div', 'etk-raf');
    if (o.soru) raf.appendChild(el('div', 'etk-soru', o.soru));
    const kartlar = el('div', 'etk-kartlar');
    raf.appendChild(kartlar);
    wrap.insertBefore(raf, s.nextSibling);
    const yerlesen = new Map(); // parça → {x, y, dogru}

    const sonuclandir = () => {
      let n = 0;
      const yanlis = [];
      for (const [k, y] of yerlesen) {
        if (y.dogru) n++;
        else {
          const nereye = y.uzerinde ? (parts[y.uzerinde] || {}).ad || y.uzerinde : 'boş alan';
          // Doğru parçaya ne kadar yaklaştığı da söylenir: eğitmen "çok yaklaştın" diyebilsin.
          const yakin = y.dogruyaPx != null && y.dogruyaPx < 80 ? `; doğru yere ${Math.round(y.dogruyaPx)} px uzakta` : '';
          yanlis.push(`${parts[k].ad} → ${nereye}${yakin}`);
        }
        y.g.classList.add(y.dogru ? 'dogru' : 'yanlis');
        if (!y.dogru) { // doğru yeri ince kesikli çizgiyle göster
          const [tx, ty] = parts[k].at;
          svg('path', { d: `M${y.x},${y.y} L${tx},${ty}`, class: 'etk-duzeltme' }, katman);
          svg('circle', { cx: tx, cy: ty, r: 0.9, class: 'etk-dogru-yer' }, katman);
        }
      }
      raf.querySelector('.etk-soru') || raf.prepend(el('div', 'etk-soru'));
      raf.querySelector('.etk-soru').textContent = `${n} / ${yerlesen.size} doğru`;
      if (board.onYanit) board.onYanit(`Etiket yerleştirme: ${n}/${yerlesen.size} doğru` + (yanlis.length ? ' (yanlış: ' + yanlis.join('; ') + ')' : ''));
    };

    for (const k of liste) {
      const kart = el('button', 'etk-kart', parts[k].ad);
      kart.type = 'button';
      kartlar.appendChild(kart);
      kart.addEventListener('pointerdown', (e) => {
        if (kart.disabled) return;
        e.preventDefault();
        const hayalet = el('div', 'etk-hayalet', parts[k].ad);
        document.body.appendChild(hayalet);
        // Sürüklerken parmağın altındaki (ya da hemen yanındaki ince) parça hafifçe belirir: neye bırakıldığı görülsün.
        const adaylar = Object.keys(parts).filter((x) => parcaDugumleri(s, x).length);
        let hedef = null, sonBakis = 0;
        const hedefGoster = (part) => {
          if (part === hedef) return;
          if (hedef) parcaDugumleri(s, hedef).forEach((n) => n.classList.remove('etk-hedef'));
          hedef = part;
          if (hedef) parcaDugumleri(s, hedef).forEach((n) => n.classList.add('etk-hedef'));
        };
        const altindaki = (x, y) => {
          const yk = enYakinParca(s, adaylar.filter((a) => (parcaUzakligi(s, a, x, y) || {}).ince), x, y);
          if (yk && yk.px <= TOLERANS_PX) return yk.part;
          return noktadakiParca(s, x, y);
        };
        const tasi = (ev) => {
          hayalet.style.left = ev.clientX + 'px'; hayalet.style.top = ev.clientY + 'px';
          const t = performance.now();
          if (t - sonBakis > 60) { sonBakis = t; hedefGoster(altindaki(ev.clientX, ev.clientY)); }
        };
        tasi(e);
        const birak = (ev) => {
          window.removeEventListener('pointermove', tasi);
          window.removeEventListener('pointerup', birak);
          window.removeEventListener('pointercancel', birak);
          hayalet.remove();
          hedefGoster(null);
          const r = s.getBoundingClientRect();
          if (ev.type === 'pointercancel' || ev.clientX < r.left || ev.clientX > r.right || ev.clientY < r.top || ev.clientY > r.bottom) return;
          const p = svgNokta(s, ev.clientX, ev.clientY);
          const uzerinde = altindaki(ev.clientX, ev.clientY);
          const [ax, ay] = parts[k].at;
          const u = parcaUzakligi(s, k, ev.clientX, ev.clientY);
          // Doğru: parçanın üstünde, etiket noktasının yakınında ya da (ince parçada) birkaç piksel yanında.
          const dogru = uzerinde === k || Math.hypot(p.x - ax, p.y - ay) <= YAKIN || !!(u && u.ince && u.px <= TOLERANS_PX);
          const g = svg('g', { class: 'etk-etiket' }, katman);
          svg('circle', { cx: p.x, cy: p.y, r: 0.8, class: 'etk-nokta' }, g);
          const t = svg('text', { x: p.x + 1.4, y: p.y + 1, class: 'etk-yazi', 'font-size': 2.8 }, g);
          t.textContent = parts[k].ad;
          yerlesen.set(k, { x: p.x, y: p.y, dogru, uzerinde, g, dogruyaPx: u ? u.px : null });
          kart.disabled = true;
          kart.classList.add('yerlesti');
          if (yerlesen.size === liste.length) sonuclandir();
        };
        window.addEventListener('pointermove', tasi);
        window.addEventListener('pointerup', birak);
        window.addEventListener('pointercancel', birak);
      });
    }
  }

  AT.Board.prototype._etkilesim = function (wrap, s, c) {
    const parts = parcalar(c);
    if (c.isaretle) isaretle(this, wrap, s, c, parts);
    if (c.etiket_surukle) etiketSurukle(this, wrap, s, c, parts);
  };
})(window.AT = window.AT || {});
