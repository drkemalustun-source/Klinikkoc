/* Anatomik şablonlar: tahtada ölçekli, anatomiye uygun hazır çizimler.
 * Claude (ya da ders dosyası) draw komutuna `template` verir; şablon çizilir,
 * `labels` ile parçalar adlandırılır, `highlight` ile vurgulanır.
 * Ölçek: 160 × 90 birimlik tuval, yaklaşık 3,4 birim = 1 mm.
 * Bukkal (vestibül) taraf solda, lingual/palatinal taraf sağdadır. */
(function (AT) {
  'use strict';

  const NS = 'http://www.w3.org/2000/svg';
  const MM = 3.4;
  let uid = 0;

  function svg(tag, attrs, parent) {
    const n = document.createElementNS(NS, tag);
    for (const k in attrs) if (attrs[k] != null) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }

  const f = (v) => Math.round(v * 100) / 100;

  // Noktalardan yumuşak eğri (Catmull-Rom → kübik Bézier).
  function smooth(pts, move = true) {
    if (!pts.length) return '';
    let d = (move ? 'M' : 'L') + f(pts[0][0]) + ',' + f(pts[0][1]);
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
      const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
      const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
      d += ` C${f(c1[0])},${f(c1[1])} ${f(c2[0])},${f(c2[1])} ${f(p2[0])},${f(p2[1])}`;
    }
    return d;
  }
  const poly = (pts, move = true) => pts.map((p, i) => (i === 0 && move ? 'M' : 'L') + f(p[0]) + ',' + f(p[1])).join(' ');
  const mirror = (pts) => pts.map(([x, y]) => [160 - x, y]);
  const range = (a, b, step) => { const r = []; for (let y = a; y < b - 1e-6; y += step) r.push(y); r.push(b); return r; };

  // Kübik Bézier üzerinde verilen y için x (eğri y yönünde tekdüze olmalı).
  function bezX(p0, p1, p2, p3, y) {
    let lo = 0, hi = 1;
    const by = (t) => (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t * t * p2[1] + t ** 3 * p3[1];
    const up = p3[1] > p0[1];
    for (let i = 0; i < 30; i++) {
      const m = (lo + hi) / 2;
      if ((by(m) < y) === up) lo = m; else hi = m;
    }
    const t = (lo + hi) / 2;
    return (1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t * t * p2[0] + t ** 3 * p3[0];
  }

  // Süngerimsi kemik: düzensiz ilmekli ağ deseni.
  function trabekul(defs, id) {
    const pat = svg('pattern', { id: id + 'tr', width: 9, height: 7, patternUnits: 'userSpaceOnUse' }, defs);
    svg('path', { d: 'M0.4,1.2 c1,-0.8 2.2,0.1 2.4,1.1 c0.2,1 -0.9,1.7 -1.8,1.3 c-0.9,-0.4 -1.2,-1.6 -0.6,-2.4 Z' +
      ' M4.6,0.6 c1.3,-0.3 2.6,0.5 2.5,1.6 c-0.1,0.9 -1.4,1.2 -2.2,0.7 c-0.7,-0.5 -0.9,-1.7 -0.3,-2.3 Z' +
      ' M3.2,4 c0.9,-0.5 2,0 2.1,0.9 c0.1,1 -1,1.6 -1.8,1.2 c-0.6,-0.4 -0.8,-1.5 -0.3,-2.1 Z' +
      ' M7,4.4 c0.8,-0.3 1.7,0.3 1.6,1.1 c-0.1,0.8 -1.1,1 -1.6,0.6 c-0.5,-0.4 -0.5,-1.3 0,-1.7 Z', fill: '#9e7c57', stroke: '#86663f', 'stroke-width': 0.25 }, pat);
  }

  // Ortak: kemiğin dış (kortikal) yüzü, alveol kretinin altında.
  const boneOuterX = (y) => (y >= 58 ? 58 - (y - 58) * 0.1875 : 58 + (58 - y) * 0.25);

  /* ---------------- Diş ve periodonsiyum (alt küçük azı, bukkolingual kesit) ---------------- */

  // Kuron ve kök dış çizgisi (sol = bukkal yüz). Sağ yüz kole altında simetriktir.
  const CROWN = 'M69,34 C66.5,30 65.5,26 66,22 C66.5,15 69,9 72,7 C74.5,8 77,11 80,12 C83,11 85.5,9 88,8.5 C91,10.5 93.5,15 94,21 C94.3,26 93,31 91,34';
  const DEJ = 'M69,34 C68.4,29.5 68.6,25 69.2,22 C70,16.5 71.7,12.5 73.2,10.6 C75.5,12.4 77.6,14.2 80,15 C82.4,14.2 84.6,12.6 87,11.6 C89.4,13.8 91,17.5 91.3,21.5 C91.5,26 91.2,30.5 91,34';
  const ROOT = 'M69,34 C69.5,50 73,72 77.5,82.5 Q80,85.5 82.5,82.5 C87,72 90.5,50 91,34';
  const PULP = 'M74.5,20 C74,24 74.5,30 75.5,36 C77,55 78.6,72 79.6,82.6 L80.4,82.6 C81.4,72 83,55 84.5,36 C85.5,30 86,24 85.5,19.5 C84.5,21 83,22 80,22 C77,22 75.8,21.5 74.5,20 Z';

  function toothX(y) {
    if (y <= 22) return 66;
    if (y <= 34) return bezX([66, 22], [65.5, 26], [66.5, 30], [69, 34], y);
    if (y >= 82.5) return 77.5;
    return bezX([69, 34], [69.5, 50], [73, 72], [77.5, 82.5], y);
  }

  const DIS_DURUM = {
    saglikli:      { mY: 28, sY: 32, jY: 37, cY: 41, g: 0.5, swell: 0, inflam: 0 },
    gingivitis:    { mY: 24.5, sY: 32, jY: 37, cY: 41, g: 0.9, swell: 1.6, inflam: 1 },
    periodontitis: { mY: 30, sY: 51, jY: 55, cY: 59.5, g: 1.7, swell: 0.8, inflam: 2, mgj: 66 }
  };
  const MGJ0 = 57;

  // Sol yarının (bukkal) yumuşak doku ve kemik geometrisi; sağ yarı aynası.
  function disGeo(p) {
    const C = [toothX(p.cY) - 1.2, p.cY];
    const boneOuter = [C, [C[0] - 2.2, p.cY + 0.9], [(C[0] - 2.2 + boneOuterX(p.cY + 4)) / 2 - 0.6, p.cY + 2.8]];
    for (const y of range(p.cY + 6, 90, 6)) boneOuter.push([boneOuterX(y), y]);
    const socket = [];
    for (const y of range(p.cY, 81, 3)) socket.push([toothX(y) - 1.2, y]);
    socket.push([78.3, 85.6], [80, 86.7]);
    const boneAt = (y) => (y < p.cY + 2 ? Infinity : y < p.cY + 6 ? C[0] - 2.2 - (y - p.cY) * 0.9 : boneOuterX(y));

    // Dişeti iç yüzü: kenar → cep/oluk duvarı → (birleşim epiteli + bağ dokusu dişe yapışık) → kret → kemik dış yüzü.
    const tip = [toothX(p.mY) - p.g * 0.7, p.mY];
    const pocket = [tip];
    for (const y of range(p.mY + 1.2, p.sY, 2)) pocket.push([toothX(y) - p.g, y]);
    const attach = [];
    for (const y of range(p.sY, p.cY, 1.5)) attach.push([toothX(y), y]);

    // Dişeti dış yüzü.
    const outer = [tip];
    let run = Infinity;
    const bump = (y) => p.swell * 1.9 * Math.exp(-(((y - (p.mY + 3.2)) / 3.2) ** 2));
    for (const y of [p.mY + 0.9, p.mY + 2.4].concat(range(p.mY + 4.5, 90, 3))) {
      const want = Math.min(toothX(Math.min(y, 40)) - 4.3 - (y < p.mY + 2 ? 2.3 - (y - p.mY) * 0.9 : 0), boneAt(y) - 3);
      run = Math.min(run, want);
      const groove = Math.abs(y - (p.mY + 6.5)) < 1.6 && !p.inflam ? 0.5 : 0;
      outer.push([run - bump(y) + groove, y]);
    }
    outer[1][0] = tip[0] - 1.1 - bump(p.mY + 0.9) * 0.6;
    const softX = (y) => { // dış yüzün y'deki x'i (etiketler için)
      for (let i = 1; i < outer.length; i++) if (outer[i][1] >= y) return outer[i][0];
      return outer[outer.length - 1][0];
    };
    return { C, boneOuter, socket, tip, pocket, attach, outer, softX, boneAt };
  }

  function disCiz(g, variant, opt) {
    const p = DIS_DURUM[variant] || DIS_DURUM.saglikli;
    const MGJ = p.mgj || MGJ0;
    const G = disGeo(p);
    const id = 'an' + (++uid);
    const defs = svg('defs', {}, g);
    // Süngerimsi kemik dokusu deseni.
    trabekul(defs, id);
    const clipM = svg('clipPath', { id: id + 'mk' }, defs);
    svg('rect', { x: 0, y: MGJ, width: 160, height: 40 }, clipM);
    const parts = {};
    const tag = (n, part) => { n.dataset.part = part; return n; };
    const both = (fn) => { fn(g, false); const r = svg('g', { transform: 'translate(160,0) scale(-1,1)' }, g); fn(r, true); };

    // 1) Kemik (alveol süreci) ve PDL boşluğu.
    const sR = mirror(G.socket).reverse();
    const bone = smooth(G.boneOuter.slice().reverse()) + ' ' + smooth(G.socket, false) + ' ' +
                 smooth(sR, false) + ' ' + smooth(mirror(G.boneOuter), false) + ' Z';
    svg('path', { d: bone, class: 'an-kemik-zemin' }, g);
    tag(svg('path', { d: bone, fill: `url(#${id}tr)`, class: 'an-kemik' }, g), 'kemik');
    both((r) => {
      tag(svg('path', { d: smooth(G.boneOuter), class: 'an-kortikal' }, r), 'kemik');
      tag(svg('path', { d: smooth(G.socket), class: 'an-lamina' }, r), 'kemik');
    });
    tag(svg('path', { d: smooth(G.socket) + ' ' + smooth(sR, false) + ' Z', class: 'an-pdl' }, g), 'pdl');
    if (variant === 'periodontitis') { // eski kemik düzeyi (kesikli)
      const old = disGeo(DIS_DURUM.saglikli);
      both((r) => tag(svg('path', { d: smooth(old.boneOuter.slice(0, 5)) + ' M' + f(old.C[0]) + ',' + f(old.C[1]) + ' ' + smooth(old.socket.slice(0, 7), false).replace(/^L/, 'L'), class: 'an-eski-kemik' }, r), 'kemik-kaybi'));
    }

    // 2) Diş: dentin, mine, pulpa, sement.
    tag(svg('path', { d: DEJ + ' C90.5,50 87,72 82.5,82.5 Q80,85.5 77.5,82.5 C73,72 69.5,50 69,34 Z', class: 'an-dentin' }, g), 'dentin');
    tag(svg('path', { d: CROWN + ' ' + revDEJ(), class: 'an-mine' }, g), 'mine');
    tag(svg('path', { d: PULP, class: 'an-pulpa' }, g), 'pulpa');
    tag(svg('path', { d: ROOT, class: 'an-sement' }, g), 'sement');
    tag(svg('path', { d: CROWN, class: 'an-dis-cizgi' }, g), 'dis');

    // 3) Yumuşak doku: dişeti (MGJ'ye kadar) ve alveol mukozası.
    const soft = smooth(G.outer.slice().reverse()) + ' ' + smooth(G.pocket, false) + ' ' + smooth(G.attach, false) +
                 ` L${f(G.C[0])},${f(G.C[1])} ` + smooth(G.boneOuter.slice(1), false) + ' Z';
    const inflamCls = p.inflam ? ' an-iltihapli' : '';
    both((r) => {
      tag(svg('path', { d: soft, class: 'an-dis-eti' + inflamCls }, r), 'dis-eti');
      tag(svg('path', { d: soft, class: 'an-mukoza', 'clip-path': `url(#${id}mk)` }, r), 'mukoza');
      tag(svg('path', { d: smooth(G.outer), class: 'an-epitel' }, r), 'dis-eti-epiteli');
      tag(svg('path', { d: smooth(G.pocket), class: 'an-oluk-epitel' + (p.inflam > 1 ? ' an-ulser' : '') }, r), 'cep');
      // Birleşim epiteli: oluk tabanında geniş, apikale doğru incelir.
      const je = [];
      for (const y of range(p.sY, p.jY, 1)) je.push([toothX(y), y]);
      const back = range(p.sY, p.jY, 1).reverse().map((y) => [toothX(y) - 1.1 * (1 - (y - p.sY) / (p.jY - p.sY)) - 0.1, y]);
      tag(svg('path', { d: poly(je) + ' ' + smooth(back, false) + ' Z', class: 'an-ba' }, r), 'ba');
      // Dentogingival ve kret lifleri.
      let d = '';
      for (const y of [p.jY + 0.8, p.jY + 2, (p.jY + p.cY) / 2 + 1]) {
        const x = toothX(y);
        d += `M${f(x - 0.3)},${f(y)} l${-4.2},${-2.2} `;
      }
      d += `M${f(toothX(p.cY - 0.6) - 0.3)},${f(p.cY - 0.6)} L${f(G.C[0] - 1.4)},${f(p.cY + 0.4)}`;
      tag(svg('path', { d, class: 'an-lif' }, r), 'bd');
      // PDL lifleri (eğik).
      let pd = '';
      for (const y of range(p.cY + 3, 78, 4.5)) { const x = toothX(y); pd += `M${f(x - 0.15)},${f(y)} L${f(x - 1.1)},${f(y - 0.8)} `; }
      tag(svg('path', { d: pd, class: 'an-pdl-lif' }, r), 'pdl');
      // MGJ çizgisi.
      tag(svg('path', { d: `M${f(G.softX(MGJ) - 0.3)},${MGJ} L${f(Math.min(G.boneAt(MGJ), G.softX(MGJ) + 3.2))},${MGJ}`, class: 'an-mgj' }, r), 'mgj');
    });

    // 4) Hastalık bulguları.
    if (p.inflam) {
      both((r) => {
        let d = '';
        const ys = range(p.mY + 2, p.sY + (p.inflam > 1 ? 2 : 1), p.inflam > 1 ? 2.2 : 1.6);
        ys.forEach((y, i) => { const x = toothX(y) - p.g - 1.6 - (i % 3) * 0.9; d += `M${f(x)},${f(y)} a0.45,0.45 0 1,0 0.01,0 `; });
        tag(svg('path', { d, class: 'an-infiltrat' }, r), 'iltihap');
      });
      both((r) => { // plak: dişeti kenarında, dişe yapışık
        let d = '';
        const top = variant === 'periodontitis' ? p.mY - 4 : p.mY - 3.2;
        const bot = variant === 'periodontitis' ? p.sY - 1 : p.mY + 2;
        for (const y of range(top, bot, 1.2)) { const x = toothX(y); d += `M${f(x + 0.1)},${f(y)} a0.5,0.5 0 1,0 0.01,0 `; }
        tag(svg('path', { d, class: 'an-plak' }, r), 'plak');
      });
    }
    if (variant === 'periodontitis') {
      both((r) => {
        const pts = [];
        for (const y of range(p.mY + 6, p.sY - 4, 1.3)) pts.push([toothX(y) - 0.45 - Math.sin(y * 2.1) * 0.25, y]);
        const back = range(p.mY + 6, p.sY - 4, 1.3).reverse().map((y) => [toothX(y) + 0.05, y]);
        tag(svg('path', { d: smooth(pts) + ' ' + poly(back, false) + ' Z', class: 'an-tartar' }, r), 'tartar');
      });
    }

    // 5) Periodontal sonda (sol cepte).
    if (opt.probe) probe(g, [toothX(p.sY) - p.g * 0.45, p.sY - 0.2], [toothX(p.mY) - p.g * 0.6, p.mY], (p.sY - p.mY) / MM);

    // Parçalar: varsayılan ad ve etiket noktası (sol yarıda; side 'sag' ise ayna).
    const S = (x, y) => [160 - x, y];
    const Gm = (p.mY + p.sY) / 2;
    Object.assign(parts, {
      mine:            { ad: 'Mine', at: [67.5, 16.5] },
      dentin:          { ad: 'Dentin', at: [71.6, 26] },
      pulpa:           { ad: 'Pulpa', at: S(76.6, 27) },
      'kok-kanali':    { ad: 'Kök kanalı', at: S(78.6, 62) },
      apeks:           { ad: 'Apeks', at: S(79.2, 84.6) },
      'mine-sement':   { ad: 'Mine-sement sınırı', at: [69, 34] },
      sement:          { ad: 'Sement', at: S(toothX(66) + 0.2, 66) },
      pdl:             { ad: 'Periodontal ligament', at: S(toothX(73) - 0.6, 73) },
      kemik:           { ad: 'Alveol kemiği', at: S(63, 76) },
      kret:            { ad: 'Alveol kreti', at: S(G.C[0] - 0.8, p.cY + 0.5) },
      'dis-eti':       { ad: variant === 'saglikli' ? 'Serbest dişeti' : 'Dişeti (iltihaplı)', at: [toothX(p.mY + 3) - p.g - 2.4, p.mY + 3.4] },
      'yapisik-dis-eti': { ad: 'Yapışık dişeti', at: [(G.softX(49) + G.boneAt(49)) / 2, 49] },
      mgj:             { ad: 'Mukogingival sınır', at: S(G.softX(MGJ) + 0.6, MGJ) },
      mukoza:          { ad: 'Alveol mukozası', at: S((G.softX(70) + G.boneAt(70)) / 2, 70) },
      'dis-eti-epiteli': { ad: 'Ağız dişeti epiteli', at: [G.softX(40), 40] },
      cep:             { ad: variant === 'saglikli' ? 'Dişeti oluğu (sulkus)' : variant === 'gingivitis' ? 'Yalancı cep' : 'Periodontal cep', at: [toothX(Gm) - p.g / 2, Gm] },
      ba:              { ad: 'Birleşim epiteli', at: [toothX((p.sY + p.jY) / 2) - 0.4, (p.sY + p.jY) / 2] },
      bd:              { ad: 'Bağ dokusu ataşmanı', at: [toothX((p.jY + p.cY) / 2) - 1.2, (p.jY + p.cY) / 2] },
      dis:             { ad: 'Diş', at: S(78, 40) }
    });
    if (p.inflam) {
      parts.iltihap = { ad: 'İltihabi hücre sızıntısı', at: [toothX(p.sY - 2) - p.g - 2.2, p.sY - 2] };
      parts.plak = { ad: 'Plak (biyofilm)', at: S(toothX(p.mY - 2) + 0.2, p.mY - 2) };
    }
    if (variant === 'periodontitis') {
      parts.tartar = { ad: 'Subgingival diştaşı', at: S(toothX(41) - 0.2, 41) };
      parts['atasman-kaybi'] = { ad: 'Ataşman kaybı', at: [toothX(44), 44] };
      parts['kemik-kaybi'] = { ad: 'Kemik kaybı', at: S(66, 50) };
    }
    if (opt.probe) parts.sonda = { ad: `Sondalama derinliği ≈ ${Math.round((p.sY - p.mY) / MM)} mm`, at: [toothX(p.mY) - p.g - 1.4, p.mY - 4] };
    return parts;
  }

  function revDEJ() {
    // Mine bölgesi: kuron dış çizgisi + DEJ ters yönde.
    return 'C91.2,30.5 91.5,26 91.3,21.5 C91,17.5 89.4,13.8 87,11.6 C84.6,12.6 82.4,14.2 80,15 C77.6,14.2 75.5,12.4 73.2,10.6 C71.7,12.5 70,16.5 69.2,22 C68.6,25 68.4,29.5 69,34 Z';
  }

  // Periodontal sonda: uç cep tabanında, 1 mm aralıklı çizgiler.
  function probe(g, tipPt, mid, depthMm) {
    const dx = mid[0] - tipPt[0], dy = mid[1] - tipPt[1];
    const L = Math.hypot(dx, dy), ux = dx / L, uy = dy / L;
    const len = 38;
    const end = [tipPt[0] + ux * len, tipPt[1] + uy * len];
    const pg = svg('g', { class: 'an-sonda' }, g);
    pg.dataset.part = 'sonda';
    svg('line', { x1: f(tipPt[0]), y1: f(tipPt[1]), x2: f(end[0]), y2: f(end[1]), class: 'an-sonda-govde' }, pg);
    let d = '';
    for (let k = 1; k <= 10; k++) {
      if (![1, 2, 3, 5, 7, 8, 9, 10].includes(k)) continue; // Williams sondası işaretleri
      const s = k * MM;
      const cx = tipPt[0] + ux * s, cy = tipPt[1] + uy * s;
      d += `M${f(cx - uy * 0.75)},${f(cy + ux * 0.75)} L${f(cx + uy * 0.75)},${f(cy - ux * 0.75)} `;
    }
    svg('path', { d, class: 'an-sonda-cizgi' }, pg);
    svg('line', { x1: f(end[0]), y1: f(end[1]), x2: f(end[0] + ux * 14), y2: f(end[1] + uy * 14), class: 'an-sonda-sap' }, pg);
    return depthMm;
  }

  /* ---------------- İmplant ve peri-implant dokular ---------------- */

  const IMP_DURUM = {
    saglikli:          { mY: 27.5, sY: 31, jY: 38, cY: 42.5, g: 0.5, swell: 0, inflam: 0, crater: 0 },
    mukozitis:         { mY: 24.5, sY: 31.5, jY: 38, cY: 42.5, g: 1, swell: 1.7, inflam: 1, crater: 0 },
    'peri-implantitis': { mY: 29, sY: 52, jY: 54.5, cY: 56.5, g: 1.8, swell: 0.9, inflam: 2, crater: 1 }
  };

  // Sol yüzey: kuron (y < 33), dayanak (33–42), implant gövdesi (42–78; yiv çekirdeği 74,6).
  function implantX(y) {
    if (y <= 21) return 66;
    if (y <= 33) return bezX([66, 21], [65.6, 26], [70, 31], [74, 33], y);
    if (y <= 34) return 74.2 + (y - 33) * 0.4;
    if (y <= 38) return 74.6 + (y - 34) / 4;
    if (y <= 42) return 75.6 + (y - 38) * 0.15;
    return 73;
  }
  const CORE = 74.6;

  function implantCiz(g, variant, opt) {
    const p = IMP_DURUM[variant] || IMP_DURUM.saglikli;
    const id = 'an' + (++uid);
    const defs = svg('defs', {}, g);
    trabekul(defs, id);
 const MGJ = MGJ0;
    const clipM = svg('clipPath', { id: id + 'mk' }, defs);
    svg('rect', { x: 0, y: MGJ, width: 160, height: 40 }, clipM);
    const tag = (n, part) => { n.dataset.part = part; return n; };
    const both = (fn) => { fn(g); const r = svg('g', { transform: 'translate(160,0) scale(-1,1)' }, g); fn(r); };

    // Kemik: implantla doğrudan temas (PDL yok). Peri-implantitiste krater biçimli defekt.
    const contactY = p.crater ? 56.5 : 42.5;
    const top = p.crater
      ? [[61.2, 47.5], [62.6, 46.6], [64.4, 47.4], [67, 50.2], [70.5, 54], [CORE, contactY]]
      : [[66.2, 45.6], [68.6, 43.6], [71.5, 42.8], [73.4, 42.5]];
    const outerTop = p.crater ? [[boneOuterX(56), 56], [boneOuterX(51.5), 51.5], [61.2, 47.5]] : [[boneOuterX(50), 50], [66.2, 45.6]];
    const boneOuter = [];
    for (const y of range(62, 90, 7).reverse()) boneOuter.push([boneOuterX(y), y]);
    const leftEdge = boneOuter.concat(outerTop, top.slice(1));
    const inner = p.crater ? [] : [[CORE, 44]];
    for (const y of range(Math.max(44, contactY) + 1, 76, 4)) inner.push([CORE, y]);
    inner.push([76.4, 77], [78.4, 79.2], [80, 79.6]);
    const half = leftEdge.concat(inner);
    const bone = smooth(half) + ' ' + smooth(mirror(half).reverse(), false) + ' Z';
    svg('path', { d: bone, class: 'an-kemik-zemin' }, g);
    tag(svg('path', { d: bone, fill: `url(#${id}tr)`, class: 'an-kemik' }, g), 'kemik');
    both((r) => tag(svg('path', { d: smooth(boneOuter.concat(outerTop, top.slice(1))), class: 'an-kortikal' }, r), 'kemik'));
    if (p.crater) { // eski kemik düzeyi
      both((r) => tag(svg('path', { d: smooth([[boneOuterX(50), 50], [66.2, 45.6], [68.6, 43.6], [71.5, 42.8], [73.4, 42.5]]), class: 'an-eski-kemik' }, r), 'krater'));
    }

    // İmplant gövdesi: yivli vida, düz boyun, yuvarlak apeks.
    const yiv = [[75.4, 42], [75.4, 44]];
    let y = 44;
    while (y < 72) { yiv.push([73, y + 1], [CORE, y + 2.4]); y += 2.9; }
    yiv.push([74.2, 74.5], [75.8, 77.5]);
    const right = mirror(yiv).reverse();
    const body = poly(yiv) + ` Q80,81 ${f(160 - 75.8)},77.5 ` + poly(right.slice(1), false) + ' Z';
    tag(svg('path', { d: body, class: 'an-implant' }, g), 'implant');
    tag(svg('path', { d: 'M75.4,42 L84.6,42 L84.6,44 L75.4,44 Z', class: 'an-implant-boyun' }, g), 'platform');
    // Dayanak (abutment) ve vida kanalı.
    const ab = [[76.2, 42], [75.6, 38], [74.6, 34], [74.2, 32.6]];
    tag(svg('path', { d: poly(ab) + ' ' + poly(mirror(ab).reverse(), false) + ' Z', class: 'an-dayanak' }, g), 'dayanak');
    svg('path', { d: 'M78.6,20 L78.6,48 M81.4,20 L81.4,48', class: 'an-vida-kanal' }, g);
    // Kuron (protez).
    const kron = 'M74,33 C70,31 65.6,26 66,21 C66.5,15 69,9 72,7 C74.5,8 77,11 80,12 C83,11 85.5,9 88,8.5 C91,10.5 93.5,15 94,21 C94.4,26 90,31 86,33 Z';
    tag(svg('path', { d: kron, class: 'an-kron' }, g), 'kron');

    // Peri-implant mukoza.
    const tip = [implantX(p.mY) - p.g * 0.7, p.mY];
    const pocket = [tip];
    for (const yy of range(p.mY + 1.2, p.sY, 2)) pocket.push([(yy < 42 ? implantX(yy) : (yy % 2.9 < 1.4 ? 73 : CORE)) - p.g, yy]);
    if (p.crater) for (const pt of pocket) if (pt[1] > 42) pt[0] = 73 - p.g;
    const attach = [];
    for (const yy of range(p.sY, p.cY, 1.5)) attach.push([yy < 42 ? implantX(yy) : 73, yy]);
    const crest = p.crater ? top.slice().reverse() : top.slice().reverse();
    const boneAt = (yy) => {
      if (p.crater) { if (yy < 47) return Infinity; if (yy < 56) return 62.6 - (yy - 47) * 0.12; return boneOuterX(yy); }
      if (yy < 43) return Infinity; if (yy < 46) return 72 - (yy - 43) * 1.9; return Math.min(boneOuterX(yy), 66.2);
    };
    const outer = [tip];
    let run = Infinity;
    const bump = (yy) => p.swell * 1.9 * Math.exp(-(((yy - (p.mY + 3.2)) / 3.2) ** 2));
    for (const yy of [p.mY + 0.9, p.mY + 2.4].concat(range(p.mY + 4.5, 90, 3))) {
      const want = Math.min(implantX(Math.min(yy, 33)) - 4.6 - (yy < p.mY + 2 ? 2.3 - (yy - p.mY) * 0.9 : 0), boneAt(yy) - 3, 66);
      run = Math.min(run, want);
      outer.push([run - bump(yy), yy]);
    }
    outer[1][0] = tip[0] - 1.1 - bump(p.mY + 0.9) * 0.6;
    const softX = (yy) => { for (let i = 1; i < outer.length; i++) if (outer[i][1] >= yy) return outer[i][0]; return outer[outer.length - 1][0]; };
    const boneSurf = (p.crater ? top.slice().reverse().concat([[61.2, 47.5]], outerTop.slice().reverse().slice(1)) : top.slice().reverse().concat(outerTop.slice().reverse().slice(1)));
    const boneSurfFull = boneSurf.concat(boneOuter.slice().reverse());
    const soft = smooth(outer.slice().reverse()) + ' ' + smooth(pocket, false) + ' ' + smooth(attach, false) + ' ' + smooth(boneSurfFull, false) + ' Z';
    const inflamCls = p.inflam ? ' an-iltihapli' : '';
    both((r) => {
      tag(svg('path', { d: soft, class: 'an-dis-eti' + inflamCls }, r), 'mukoza');
      tag(svg('path', { d: soft, class: 'an-mukoza', 'clip-path': `url(#${id}mk)` }, r), 'alveol-mukozasi');
      tag(svg('path', { d: smooth(outer), class: 'an-epitel' }, r), 'mukoza');
      tag(svg('path', { d: smooth(pocket), class: 'an-oluk-epitel' + (p.inflam > 1 ? ' an-ulser' : '') }, r), 'cep');
      const je = [], back = [];
      for (const yy of range(p.sY, p.jY, 1)) { const x = yy < 42 ? implantX(yy) : 73; je.push([x, yy]); back.unshift([x - 1.1 * (1 - (yy - p.sY) / (p.jY - p.sY)) - 0.1, yy]); }
      tag(svg('path', { d: poly(je) + ' ' + smooth(back, false) + ' Z', class: 'an-ba' }, r), 'bariyer-epiteli');
      if (!p.crater) { // implanta paralel/çevresel lifler (sement yok, lifler yüzeye girmez)
        let d = '';
        for (const yy of [p.jY + 1, p.jY + 2.4, p.jY + 3.6]) { const x = implantX(Math.min(yy, 42)); d += `M${f(x - 0.6)},${f(yy)} l-0.6,-4.5 `; }
        tag(svg('path', { d, class: 'an-lif' }, r), 'bd');
      }
    });
    const bx = implantX(p.mY) - p.g * 0.7 - 0.6;
    if (p.inflam) {
      both((r) => {
        let d = '';
        range(p.mY + 2, p.sY + 1, p.inflam > 1 ? 2.2 : 1.6).forEach((yy, i) => {
          const x = (yy < 42 ? implantX(yy) : 73) - p.g - 1.7 - (i % 3) * 0.9;
          d += `M${f(x)},${f(yy)} a0.45,0.45 0 1,0 0.01,0 `;
        });
        tag(svg('path', { d, class: 'an-infiltrat' }, r), 'iltihap');
        let pl = '';
        for (const yy of range(p.mY - 3.2, p.crater ? p.sY - 1 : p.mY + 2, 1.2)) { const x = yy < 42 ? implantX(yy) : (yy % 2.9 < 1.4 ? 73.2 : CORE); pl += `M${f(x + 0.1)},${f(yy)} a0.5,0.5 0 1,0 0.01,0 `; }
        tag(svg('path', { d: pl, class: 'an-plak' }, r), 'plak');
      });
      // Sondalamada kanama (ve peri-implantitiste süpürasyon) damlası.
      tag(svg('path', { d: `M${f(bx)},${f(p.mY - 3.6)} q-1.3,1.9 0,2.6 q1.3,-0.7 0,-2.6 Z`, class: 'an-kanama' }, g), 'kanama');
      if (p.crater) tag(svg('path', { d: `M${f(160 - bx)},${f(p.mY - 3.6)} q-1.3,1.9 0,2.6 q1.3,-0.7 0,-2.6 Z`, class: 'an-supurasyon' }, g), 'supurasyon');
    }
    if (opt.probe) probe(g, [73 - p.g * 0.45, p.sY - 0.2], [implantX(p.mY) - p.g * 0.6, p.mY], (p.sY - p.mY) / MM);

    const S = (x, yy) => [160 - x, yy];
    const Gm = (p.mY + p.sY) / 2;
    const parts = {
      kron:              { ad: 'Protetik kuron', at: S(70, 17) },
      dayanak:           { ad: 'Dayanak (abutment)', at: S(76, 36.5) },
      platform:          { ad: 'İmplant platformu', at: S(75.6, 43) },
      implant:           { ad: 'İmplant (titanyum vida)', at: S(77, 66) },
      yiv:               { ad: 'Yivler', at: S(73.4, 70.5) },
      mukoza:            { ad: variant === 'saglikli' ? 'Peri-implant mukoza' : 'Mukoza (iltihaplı)', at: [implantX(p.mY + 3) - p.g - 2.4, p.mY + 3.4] },
      cep:               { ad: variant === 'saglikli' ? 'Peri-implant oluk' : variant === 'mukozitis' ? 'Derinleşmiş oluk' : 'Peri-implant cep', at: [((Gm < 42 ? implantX(Gm) : 73)) - p.g / 2, Gm] },
      'bariyer-epiteli': { ad: 'Bariyer epiteli', at: [((p.sY + p.jY) / 2 < 42 ? implantX((p.sY + p.jY) / 2) : 73) - 0.4, (p.sY + p.jY) / 2] },
      bd:                { ad: 'Bağ dokusu (paralel lifler)', at: [implantX(Math.min(p.jY + 2.4, 42)) - 1.4, p.jY + 2.2] },
      kemik:             { ad: 'Alveol kemiği', at: S(64, 72) },
      osseo:             { ad: 'Kemik teması (PDL yok)', at: S(CORE - 0.4, 64.6) },
      kret:              { ad: 'Kemik kreti', at: S(p.crater ? 62.6 : 70, p.crater ? 46.8 : 43.6) },
      'alveol-mukozasi': { ad: 'Alveol mukozası', at: S((softX(72) + boneAt(72)) / 2, 72) }
    };
    if (p.inflam) {
      parts.iltihap = { ad: 'İltihabi hücre sızıntısı', at: [((p.sY - 2) < 42 ? implantX(p.sY - 2) : 73) - p.g - 2.2, p.sY - 2] };
      parts.plak = { ad: 'Plak (biyofilm)', at: S(implantX(p.mY - 2) + 0.2, p.mY - 2) };
      parts.kanama = { ad: 'Sondalamada kanama', at: [bx, p.mY - 2.6] };
    }
    if (p.crater) {
      parts.krater = { ad: 'Krater biçimli kemik defekti', at: S(68.6, 51.8) };
      parts.supurasyon = { ad: 'Süpürasyon', at: S(bx, p.mY - 2.6) };
      parts['acik-yiv'] = { ad: 'Açığa çıkmış yivler', at: S(73.2, 48.2) };
    }
    if (opt.probe) parts.sonda = { ad: `Sondalama derinliği ≈ ${Math.round((p.sY - p.mY) / MM)} mm`, at: [implantX(p.mY) - p.g - 1.4, p.mY - 4] };
    return parts;
  }

  const SABLONLAR = {
    dis: { ad: 'Diş ve periodonsiyum', varyantlar: Object.keys(DIS_DURUM), ciz: disCiz },
    implant: { ad: 'İmplant ve peri-implant dokular', varyantlar: Object.keys(IMP_DURUM), ciz: implantCiz }
  };

  // Etiketleri iki sütuna dizer, çakışmayı önler, kılavuz çizgisi çeker.
  function etiketle(g, parts, labels, instant, eski) {
    const sol = [], sag = [];
    for (const l of labels) {
      const lab = typeof l === 'string' ? { part: l } : l;
      const pr = parts[lab.part];
      if (!pr) { console.warn('Bilinmeyen parça:', lab.part); continue; }
      let at = pr.at;
      if (lab.side === 'sol' && at[0] > 80) at = [160 - at[0], at[1]];
      if (lab.side === 'sag' && at[0] < 80) at = [160 - at[0], at[1]];
      (at[0] < 80 ? sol : sag).push({ text: lab.text || pr.ad, at, color: lab.color, yeni: eski ? !eski.has(lab.part) : !instant });
    }
    const yerlestir = (arr) => {
      arr.sort((a, b) => a.at[1] - b.at[1]);
      let last = -Infinity;
      for (const a of arr) { a.y = Math.max(a.at[1], last + 4.8, 4); last = a.y; }
      let over = last - 88;
      for (let i = arr.length - 1; i >= 0 && over > 0; i--) {
        arr[i].y -= over;
        const prev = arr[i - 1];
        over = prev ? prev.y - (arr[i].y - 4.8) : 0;
      }
    };
    yerlestir(sol); yerlestir(sag);
    let delay = 0;
    const ciz = (a, side) => {
      const tx = side === 'sol' ? 47 : 113;
      const lg = svg('g', { class: 'an-etiket ' + (a.color || '') }, g);
      svg('path', { d: `M${tx + (side === 'sol' ? 0.8 : -0.8)},${f(a.y - 1.1)} L${f(a.at[0])},${f(a.at[1])}`, class: 'an-kilavuz' }, lg);
      svg('circle', { cx: f(a.at[0]), cy: f(a.at[1]), r: 0.65, class: 'an-nokta' }, lg);
      const t = svg('text', { x: tx, y: f(a.y), 'text-anchor': side === 'sol' ? 'end' : 'start', 'font-size': 3.4, class: 'an-yazi' }, lg);
      t.textContent = a.text;
      if (a.yeni) { lg.style.animationDelay = delay + 's'; lg.classList.add('fade-in'); delay += 0.35; }
    };
    sol.forEach((a) => ciz(a, 'sol'));
    sag.forEach((a) => ciz(a, 'sag'));
  }

  // svgEl içine şablonu çizer. c: {template, variant, labels, highlight, probe}
  function ciz(svgEl, c, instant, eski) {
    const s = SABLONLAR[c.template];
    if (!s) { console.warn('Bilinmeyen şablon:', c.template); return null; }
    const g = svg('g', { class: 'an-sablon' + (instant ? '' : ' fade-in') }, svgEl);
    const parts = s.ciz(g, c.variant || s.varyantlar[0], { probe: !!c.probe });
    for (const h of [].concat(c.highlight || [])) {
      g.querySelectorAll(`[data-part="${h}"]`).forEach((n) => n.classList.add('an-vurgu'));
    }
    let labels = c.labels || [];
    if (labels === 'hepsi' || labels === 'all') labels = Object.keys(parts);
    const lg = svg('g', { class: 'an-etiketler' }, svgEl);
    etiketle(lg, parts, labels, instant, eski);
    return parts;
  }

  // Claude'a ve ders yazarına parça listesi (araç açıklaması için).
  function liste() {
    const out = {};
    for (const k in SABLONLAR) {
      const tmp = document.createElementNS(NS, 'g');
      out[k] = {};
      for (const v of SABLONLAR[k].varyantlar) out[k][v] = Object.keys(SABLONLAR[k].ciz(tmp, v, { probe: true }));
    }
    return out;
  }

  AT.anatomi = { ciz, liste, SABLONLAR, MM };
})(window.AT = window.AT || {});
