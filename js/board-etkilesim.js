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

  // Şablonun parça listesi (ad ve etiket noktası), çizimi etkilemeden hesaplanır.
  function parcalar(c) {
    const s = AT.anatomi && AT.anatomi.SABLONLAR[c.template];
    if (!s) return {};
    const g = document.createElementNS(NS, 'g');
    return s.ciz(g, c.variant || s.varyantlar[0], { probe: !!c.probe, p: c.p }) || {};
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
    const dogru = new Set([].concat(o.dogru || []));
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
    const liste = [].concat(o.etiketler || []).filter((k) => parts[k]);
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
        if (y.dogru) n++; else yanlis.push(`${parts[k].ad} → ${y.uzerinde ? (parts[y.uzerinde] || {}).ad || y.uzerinde : 'boş alan'}`);
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
        const tasi = (ev) => { hayalet.style.left = ev.clientX + 'px'; hayalet.style.top = ev.clientY + 'px'; };
        tasi(e);
        const birak = (ev) => {
          window.removeEventListener('pointermove', tasi);
          window.removeEventListener('pointerup', birak);
          window.removeEventListener('pointercancel', birak);
          hayalet.remove();
          const r = s.getBoundingClientRect();
          if (ev.type === 'pointercancel' || ev.clientX < r.left || ev.clientX > r.right || ev.clientY < r.top || ev.clientY > r.bottom) return;
          const p = svgNokta(s, ev.clientX, ev.clientY);
          const uzerinde = noktadakiParca(s, ev.clientX, ev.clientY);
          const [ax, ay] = parts[k].at;
          const dogru = uzerinde === k || Math.hypot(p.x - ax, p.y - ay) <= YAKIN;
          const g = svg('g', { class: 'etk-etiket' }, katman);
          svg('circle', { cx: p.x, cy: p.y, r: 0.8, class: 'etk-nokta' }, g);
          const t = svg('text', { x: p.x + 1.4, y: p.y + 1, class: 'etk-yazi', 'font-size': 2.8 }, g);
          t.textContent = parts[k].ad;
          yerlesen.set(k, { x: p.x, y: p.y, dogru, uzerinde, g });
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
