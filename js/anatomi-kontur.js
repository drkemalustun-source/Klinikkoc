/* İmplant üstü restorasyonun konturu ve yumuşak doku: papil ve fasiyal kontur şablonları (v5, C aşaması).
 * anatomi.js'ten sonra yüklenir. Görseller hiçbir makale şeklinden kopyalanmadı ya da üzerinden çizilmedi;
 * bilinen ölçülerle (orta kesici kuronu ≈ 8,5 × 10,5 mm, implant çapı 4,1 mm, implant–diş arası ≥ 1,5–2 mm,
 * platform fasiyal kenarın ≈ 3 mm apikalinde) sıfırdan, parametrik çizildi.
 * Kritik kontur: restorasyonun yumuşak doku kenarının hemen apikalindeki ≈ 1 mm'lik bant.
 * Kritik altı kontur: bunun apikalinden implant platformuna dek uzanan bölüm.
 * Kontur değişince doku tepkisinin ölçüsü (ör. papil tepesinde 0,5–1 mm) gözlemdir, eşik değildir: "yaklaşık" yazılır. */
(function (AT) {
  'use strict';
  if (!AT.anatomi) return;
  const { svg, smooth, poly, trabekul, clamp, f, uid } = AT.anatomi._y;
  const tag = (n, part) => { n.dataset.part = part; return n; };
  const mm1 = (v) => String(Math.round(v * 10) / 10).replace('.', ',');
  // Hazır etiketlerdeki sayılar şemanın çizim ölçüleridir, bir makalenin bulgusu değildir. olcu:false ile yazılmaz;
  // yazıldığında çizimin altında "Ölçüler şematiktir" notu durur.
  const olculu = (opt) => !opt || opt.olcu !== false;
  const sayi = (opt, ad, ek) => (olculu(opt) ? ad + ek : ad);
  const sematikNot = (g0, opt) => { if (olculu(opt)) svg('text', { x: 1, y: 88.6, 'text-anchor': 'start', 'font-size': 2.3, class: 'an-yazi an-sematik-not' }, g0).textContent = 'Ölçüler şematiktir'; };
  const ayna = (x) => 160 - x;
  const sin = Math.sin, PI = Math.PI;

  // Yivli implant gövdesi (dik eksen): platform yP'de, gövde yukarı (apikale) uzar. r: yarıçap (birim).
  function implantGovde(g, cx, yP, r, boy, adim) {
    const sol = [[cx - r + 0.5, yP]];
    for (let s = 0.9; s < boy - adim; s += adim) sol.push([cx - r, yP - s], [cx - r + 0.9, yP - s - adim / 2]);
    sol.push([cx - r + 0.6, yP - boy]);
    const sag = sol.map(([x, y]) => [2 * cx - x, y]).reverse();
    return tag(svg('path', { d: poly(sol) + ' ' + poly(sag, false) + ' Z', class: 'an-implant' }, g), 'implant');
  }

  /* ---------------- Papil (iki birim arası, meziodistal kesit, önden) ----------------
   * Üst ön bölge, kuronlar aşağı bakar. Ölçüler mm: x temas noktasından (sağ +), y diş tarafındaki kemik
   * tepesinden (koronal +). Ekranda 4,2 birim = 1 mm. Birimler sol ve sağda; her biri diş ya da implant.
   * d: temas noktasının (apikal ucu) kemik tepesine uzaklığı, h: papil yüksekliği (mm).
   * İmplant tarafında restorasyon yüzeyi platformdan temasa iner; sub (+1 iç bükey, −1 dış bükey) kritik altı
   * konturu, crit (+1 fazla, −1 az) kritik konturu biçimlendirir; kare temas yüzeyini apikale uzatır (kare kron). */
  const K = 4.2, Y0 = 38;
  const X = (x) => 80 + K * x, Y = (y) => Y0 + K * y;
  const P = (pts) => pts.map(([x, y]) => [X(x), Y(y)]);
  const PAP_TEMEL = { impL: 0, impR: 1, d: 5.5, h: 4.5, sub: 0, crit: 0, kare: 0, b: 1 };
  const PAP_DURUM = {
    'dis-dis':         { ...PAP_TEMEL, impR: 0, d: 5, h: 5 },
    duz:               { ...PAP_TEMEL },
    // Su ve ark. 2010: ara yüzde kritik altı kontur dış bükey yapılınca papil desteklenir, tepesi koronale kayar
    // (≈ 0,5–1 mm, gözlem; etki ince-skalloplu biyotipte belirgin). İç bükey için ayrı bir sonuç gösterilmez.
    konkav:            { ...PAP_TEMEL, sub: 1 },
    konveks:           { ...PAP_TEMEL, sub: -1, h: 5.2 },
    'kare-kron':       { ...PAP_TEMEL, kare: 1, crit: 0.6, d: 4, h: 4.5 },
    'ince-biyotip':    { ...PAP_TEMEL, b: 0, h: 4 },
    'implant-implant': { ...PAP_TEMEL, impL: 1, d: 5, h: 3.4 }
  };
  const PLATFORM = -4.2, IMP_R = 2.05; // platform, diş tarafı kemik tepesinin 4,2 mm apikalinde

  function papilCiz(g0, variant, opt) {
    const p = { ...PAP_TEMEL, ...(opt.p || PAP_DURUM[variant] || PAP_DURUM.duz) };
    const id = uid();
    const defs = svg('defs', {}, g0);
    trabekul(defs, id);
    const kes = svg('clipPath', { id: id + 'c' }, defs);
    svg('rect', { x: 50, y: 2, width: 60, height: 84, rx: 3 }, kes);
    const g = svg('g', { 'clip-path': `url(#${id}c)` }, g0);
    const parts = {};
    const iL = clamp(p.impL), iR = clamp(p.impR);
    const ikiImp = iL * iR;
    const kenar = -1 - 0.5 * ikiImp;              // yakın yüzün kemik düzeyindeki yeri (sol birim; implantlar arası ≥ 3 mm)
    const kret = (i) => [kenar + 0.05 * i, -4.7 * i]; // dişte kemik tepesi 0; implantta platformun 0,5 mm apikali
    const kL = kret(iL), kR0 = kret(iR), kR = [-kR0[0], kR0[1]];
    const orta = -0.15 * (1 - iL) * (1 - iR) - 1.7 * (iL + iR) + 1.2 * ikiImp; // aradaki kemik tepesi
    const tepe = Math.max(kL[1], kR[1], orta);
    const d = p.d, h = Math.min(p.h, p.d);
    const yC = tepe + d, yC2 = yC + 1.4 + 1.2 * p.kare, yT = tepe + h, kritikBas = yT - 1;
    const kesici = Math.max(yC2 + 3.2, 11);

    // Sol birim koordinatında yakın yüzey (x ≤ 0): kemikten temasa.
    const disYuzey = () => {
      const pts = [[kenar - 0.35, -10], [kenar - 0.15, -4], [kenar, 0], [kenar + 0.15, 1.8]];
      for (let k = 1; k <= 10; k++) { const t = k / 10; pts.push([kenar + 0.15 + (-0.02 - kenar - 0.15) * Math.sqrt(t), 1.8 + (yC - 1.8) * t]); }
      return pts;
    };
    const impYuzey = () => {
      const pts = [], y0 = PLATFORM, y1 = yC - 1.3 * p.kare, x0 = kenar + 0.05;
      for (let k = 0; k <= 24; k++) {
        const y = y0 + (y1 - y0) * (k / 24);
        let x = x0 + (-0.02 - x0) * Math.pow((y - y0) / (y1 - y0), 1.6);
        if (y < kritikBas) x -= p.sub * 0.75 * sin(PI * clamp((y - y0) / (kritikBas - y0)));
        else x += p.crit * 0.45 * sin(PI * 0.5 * clamp(y - kritikBas));
        pts.push([Math.min(x, -0.02), y]);
      }
      if (y1 < yC) pts.push([-0.02, yC]);
      return pts;
    };
    const yuzey = (i) => (i > 0.5 ? impYuzey() : disYuzey());
    const yL = yuzey(iL), yR = yuzey(iR).map(([x, y]) => [-x, y]);
    const xAt = (pts, y) => { for (let k = 1; k < pts.length; k++) if (pts[k][1] >= y) { const a = pts[k - 1], b = pts[k], t = (y - a[1]) / ((b[1] - a[1]) || 1); return a[0] + (b[0] - a[0]) * t; } return pts[pts.length - 1][0]; };

    // Kemik (üstte) ve kret çizgisi.
    const kretCizgi = [[-8, kL[1] - 0.15], [kL[0] - 2.2, kL[1]], kL, [0, orta], kR, [kR[0] + 2.2, kR[1]], [8, kR[1] - 0.15]];
    const kemikYol = 'M' + f(X(-8)) + ',0 L' + f(X(8)) + ',0 ' + smooth(P(kretCizgi.slice().reverse()), false) + ' Z';
    svg('path', { d: kemikYol, class: 'an-kemik-zemin' }, g);
    tag(svg('path', { d: kemikYol, fill: `url(#${id}tr)`, class: 'an-kemik' }, g), 'kemik');
    tag(svg('path', { d: smooth(P(kretCizgi)), class: 'an-kortikal' }, g), 'kret');

    // Siyah üçgen.
    if (yC - yT > 0.08) {
      const ust = [[xAt(yL, yT), yT]].concat(yL.filter(([, y]) => y > yT && y < yC), [[0, yC]]);
      const alt = yR.filter(([, y]) => y > yT && y < yC).reverse();
      tag(svg('path', { d: poly(P(ust.concat(alt, [[xAt(yR, yT), yT]]))) + ' Z', class: 'an-siyah-ucgen' }, g), 'siyah-ucgen');
    }

    // Papil: iki yüzey arasında, kemikten tepeye. Kalın biyotipte tepe küt, incede sivri.
    const yk = Math.max(kL[1], kR[1], tepe - 0.6);
    const solK = yL.filter(([, y]) => y > kL[1] + 0.05 && y < yT - 0.45), sagK = yR.filter(([, y]) => y > kR[1] + 0.05 && y < yT - 0.45);
    const xl = xAt(yL, yT - 0.45), xr = xAt(yR, yT - 0.45), ort = (xl + xr) / 2, kut = 0.12 + 0.22 * p.b;
    const tepeN = [[xl, yT - 0.45], [ort - kut, yT - 0.05], [ort, yT], [ort + kut, yT - 0.05], [xr, yT - 0.45]];
    const papilYol = poly(P([kL].concat(solK))) + ' ' + smooth(P(tepeN), false) + ' ' + poly(P(sagK.slice().reverse().concat([kR])), false) +
      ' ' + smooth(P([kR, [0, orta], kL]), false) + ' Z';
    tag(svg('path', { d: papilYol, class: 'an-dis-eti' }, g), 'papil');
    svg('path', { d: smooth(P(tepeN)), class: 'an-keratin' }, g);
    void yk;

    // Birimler (sol birim koordinatında çizilir; sağdaki x = 80 çevresinde aynalanır).
    const birim = (i, sagda) => {
      const bg = svg('g', sagda ? { transform: 'translate(160,0) scale(-1,1)' } : {}, g);
      const kuronUc = [[-0.02, yC2], [-0.25, kesici - 1.4], [-0.9, kesici], [-8, kesici]];
      if (i < 0.5) {
        const kok = [[kenar + 0.15, 1.8], [kenar, 0], [kenar - 0.15, -4], [kenar - 0.35, -10], [-8, -10], [-8, 1.8]];
        svg('path', { d: poly(P(kok)) + ' Z', class: 'an-pdl-cizgi' }, bg);
        tag(svg('path', { d: poly(P(kok)) + ' Z', class: 'an-dentin' }, bg), sagda ? 'kok-sag' : 'kok');
        svg('path', { d: poly(P([[kenar + 0.15, 1.8], [kenar, 0], [kenar - 0.15, -4], [kenar - 0.35, -10]])), class: 'an-sement-cizgi' }, bg);
        svg('path', { d: poly(P([[-4.6, -10], [-4.4, 1.2], [-3.4, 1.6], [-3.3, -10]])) + ' Z', class: 'an-pulpa' }, bg);
        const kuron = disYuzey().slice(3).concat(kuronUc, [[-8, 1.8]]);
        tag(svg('path', { d: smooth(P(kuron.slice(0, -2))) + ' ' + poly(P(kuron.slice(-2)), false) + ' Z', class: 'an-mine' }, bg), sagda ? 'dogal-dis-sag' : 'dogal-dis');
        svg('path', { d: poly(P([[-8, 1.8], [kenar + 0.15, 1.8]])), class: 'an-mse' }, bg);
      } else {
        const ex = kenar - IMP_R; // implant ekseni
        implantGovde(bg, X(ex), Y(PLATFORM), IMP_R * K, Y(PLATFORM), 0.8 * K);
        const yakin = impYuzey();
        // Uzak yüzde yumuşak doku ve restorasyonun düz çıkışı (kesitin kenarında).
        const uzak = [[ex - IMP_R - 0.05, PLATFORM], [ex - IMP_R - 0.6, PLATFORM + 2.5], [-8, PLATFORM + 5.6]];
        tag(svg('path', { d: poly(P([[-8, PLATFORM - 0.6], [ex - IMP_R - 0.1, PLATFORM - 0.5]].concat(uzak))) + ' Z', class: 'an-dis-eti' }, bg), sagda ? 'mukoza-sag' : 'mukoza-sol');
        const restorasyon = poly(P(yakin)) + ' ' + smooth(P(kuronUc), false) + ' ' + poly(P(uzak.slice().reverse()), false) + ' Z';
        tag(svg('path', { d: restorasyon, class: 'an-kron' }, bg), sagda ? 'kron-sag' : 'kron-sol');
        // Dayanak bağlantısı: platformdan 1,6 mm (kuronun içinde, gri).
        tag(svg('path', { d: poly(P([[kenar + 0.05, PLATFORM], [xAt(yakin, PLATFORM + 1.6) - 0.15, PLATFORM + 1.6], [ex - IMP_R - 0.35, PLATFORM + 1.6], [ex - IMP_R - 0.05, PLATFORM]])) + ' Z', class: 'an-dayanak' }, bg), sagda ? 'dayanak-sag' : 'dayanak');
        const alt = yakin.filter(([, y]) => y <= kritikBas).concat([[xAt(yakin, kritikBas), kritikBas]]);
        const ust = [[xAt(yakin, kritikBas), kritikBas]].concat(yakin.filter(([, y]) => y > kritikBas && y < yT), [[xAt(yakin, yT), yT]]);
        tag(svg('path', { d: poly(P(alt)), class: 'an-kritik-alti' }, bg), sagda ? 'kritik-alti' : 'kritik-alti-sol');
        tag(svg('path', { d: poly(P(ust)), class: 'an-kritik' }, bg), sagda ? 'kritik' : 'kritik-sol');
      }
    };
    birim(iL, false);
    birim(iR, true);
    tag(svg('circle', { cx: 80, cy: f(Y(yC)), r: 0.9, class: 'an-temas' }, g), 'temas');
    // Ölçü: kemik tepesi – temas noktası (sağ birimin dışında, kesikli).
    const ox = 7;
    svg('path', { d: `M${f(X(0.3))},${f(Y(tepe))} L${f(X(ox))},${f(Y(tepe))} M${f(X(0.3))},${f(Y(yC))} L${f(X(ox))},${f(Y(yC))} M${f(X(ox - 0.4))},${f(Y(tepe))} L${f(X(ox - 0.4))},${f(Y(yC))}`, class: 'an-olcum-kilavuz' }, g0);

    const yuzR = (y) => [X(-xAt(impYuzey(), y)), Y(y)];
    Object.assign(parts, {
      papil:   { ad: 'İnterdental papil', at: [80, Y((tepe + yT) / 2)], yan: 'sol' },
      tepe:    { ad: sayi(opt, 'Papil yüksekliği', ` ≈ ${mm1(h)} mm`), at: [80, Y(yT) - 0.3], yan: 'sol' },
      temas:   { ad: 'Temas noktası', at: [80, Y(yC)] },
      olcum:   { ad: sayi(opt, 'Temas–kemik tepesi', ` ≈ ${mm1(d)} mm`), at: [X(ox - 0.4), Y((tepe + yC) / 2)] },
      kret:    { ad: ikiImp > 0.5 ? 'İmplantlar arası kemik tepesi' : 'Kemik tepesi', at: [X(0), Y(orta) - 0.3] },
      kemik:   { ad: 'Alveol kemiği', at: [X(-6), Y(-7)], ayrinti: true }
    });
    if (yC - yT > 0.08) parts['siyah-ucgen'] = { ad: p.sub < -0.5 ? 'Siyah üçgen küçülür' : 'Siyah üçgen', at: [80, Y((yT + yC) / 2)] };
    if (iL < 0.5) parts['dogal-dis'] = { ad: 'Doğal diş (orta kesici)', at: [X(-4), Y(8)] };
    else parts['kron-sol'] = { ad: 'İmplant üstü kron', at: [X(-4), Y(8)] };
    if (iR > 0.5) {
      Object.assign(parts, {
        'kron-sag':    { ad: 'İmplant üstü kron', at: [X(4), Y(8)] },
        implant:       { ad: sayi(opt, 'İmplant', ' (çap 4,1 mm)'), at: [X(-(kenar - IMP_R)), Y(-7)] },
        'dayanak-sag': { ad: 'Dayanak', at: [X(4), Y(PLATFORM + 1.1)], ayrinti: true },
        'kritik-alti': { ad: p.sub > 0.5 ? 'Kritik altı kontur: iç bükey' : p.sub < -0.5 ? 'Kritik altı kontur: dış bükey' : 'Kritik altı kontur: düz', at: yuzR((PLATFORM + kritikBas) / 2) },
        kritik:        { ad: p.kare > 0.5 ? 'Kritik kontur: geniş (kare kron)' : sayi(opt, 'Kritik kontur', ' (≈ 1 mm)'), at: yuzR(kritikBas + 0.5) }
      });
    } else parts['dogal-dis-sag'] = { ad: 'Komşu doğal diş', at: [X(4), Y(8)] };
    if (p.sub < -0.5) parts.kazanc = { ad: sayi(opt, 'Papil', ' ≈ 0,5–1 mm') + ' koronale (yaklaşık)', at: [79.7, Y(yT) + 0.4], yan: 'sol' };
    if (p.b < 0.5) parts.biyotip = { ad: 'İnce biyotip: sivri papil', at: [80, Y(yT) - 1.2], yan: 'sol' };
    sematikNot(g0, opt);
    return parts;
  }

  /* ---------------- Fasiyal kontur (orta kesici yerinde implant, labio-palatinal kesit) ----------------
   * Labial solda, kuron aşağı bakar. Ölçüler mm: x implant ekseninden (palatinal +), y platformdan (koronal +).
   * Ekranda 5,5 birim = 1 mm (geçiş bölgesine yakın). Planlanan mukoza kenarı platformun 3 mm koronalinde (G). Kritik kontur G'nin 1 mm
   * apikalinden G'ye; kritik altı kontur platformdan oraya. sub/crit papil şablonundaki gibi; kay: mukoza kenarının
   * planlanan yere göre kayması (mm, + koronal), yaklaşık ve gösterim içindir. */
  const FK = 5.5, FY0 = 31.5, G = 3;
  const FX = (x) => 80 + FK * (x + 0.8), FYy = (y) => FY0 + FK * y;
  const FP = (pts) => pts.map(([x, y]) => [FX(x), FYy(y)]);
  const FK_TEMEL = { sub: 0, crit: 0, kay: 0, tB: 2, tG: 2, dol: 0 };
  const FK_DURUM = {
    duz:                  { ...FK_TEMEL },
    'kritik-fazla':       { ...FK_TEMEL, crit: 1, kay: -1 },
    'kritik-az':          { ...FK_TEMEL, crit: -1, kay: 0.5 },
    'kritik-alti-konkav': { ...FK_TEMEL, sub: 1, kay: 0.3 },
    // Kritik altı kontur fizyolojik sınır içinde dış bükey: fasiyal profil dolgunlaşır, kenar düzeyi belirgin değişmez.
    // Sınır aşılınca (aşırı dış bükey): mukoza gerilir ve incelir, kenar apikale kayabilir (çekilme riski).
    'kritik-alti-konveks': { ...FK_TEMEL, sub: -1, dol: 1 },
    'kritik-alti-asiri-konveks': { ...FK_TEMEL, sub: -1.7, kay: -0.8, tG: 1.5, dol: 1 }
  };

  function konturCiz(g0, variant, opt) {
    const p = { ...FK_TEMEL, ...(opt.p || FK_DURUM[variant] || FK_DURUM.duz) };
    const id = uid();
    const defs = svg('defs', {}, g0);
    trabekul(defs, id);
    const kes = svg('clipPath', { id: id + 'c' }, defs);
    svg('rect', { x: 50, y: 2, width: 60, height: 84, rx: 3 }, kes);
    const g = svg('g', { 'clip-path': `url(#${id}c)` }, g0);
    const parts = {};
    const r = IMP_R, Gm = G + p.kay;
    // Labial restorasyon yüzeyi (platformdan kenara): x(y).
    const labial = () => {
      const pts = [];
      for (let k = 0; k <= 24; k++) {
        const y = (G * k) / 24;
        let x = -(r - 0.05) + (-3.4 + r - 0.05) * Math.pow(y / G, 1.4);
        if (y < G - 1) x += p.sub * 0.65 * sin(PI * clamp(y / (G - 1)));
        else x -= p.crit * 0.5 * sin(PI * 0.5 * clamp(y - (G - 1)));
        pts.push([x, y]);
      }
      return pts;
    };
    const lab = labial();
    const xAt = (pts, y) => { for (let k = 1; k < pts.length; k++) if (pts[k][1] >= y) { const a = pts[k - 1], b = pts[k], t = (y - a[1]) / ((b[1] - a[1]) || 1); return a[0] + (b[0] - a[0]) * t; } return pts[pts.length - 1][0]; };
    const ucX = lab[lab.length - 1][0];
    const kuronLab = [[ucX, G], [ucX - 0.25, G + 2], [ucX - 0.1, G + 6], [-2.7, G + 10.5]];
    const kuronPal = [[-1.6, G + 10.6], [0.6, G + 7.4], [2.4, G + 4.2], [3.4, G + 1.4], [3.45, G + 0.3]];
    const palEm = [[3.45, G + 0.3], [3.0, 1.6], [r - 0.05, 0]];

    // Kemik: labial plak (kalınlık tB) ve kalın palatinal kemik; kret platformun hemen apikalinde.
    const dis = -r - p.tB;
    const kemik = [[dis - 0.6, -10], [dis - 0.3, -3], [dis, -1.1], [dis + 0.9, -0.45], [-r, -0.3], [-r, -10]];
    const pal = [[r, -10], [r, -0.25], [r + 1.4, -0.15], [6, -0.6], [8.6, -1], [8.6, -10]];
    for (const [k, part] of [[kemik, 'labial-kemik'], [pal, 'palatinal-kemik']]) {
      svg('path', { d: smooth(FP(k)) + ' Z', class: 'an-kemik-zemin' }, g);
      tag(svg('path', { d: smooth(FP(k)) + ' Z', fill: `url(#${id}tr)`, class: 'an-kemik' }, g), part);
      svg('path', { d: smooth(FP(k.slice(0, -1))), class: 'an-kortikal' }, g);
    }
    // Labial mukoza: dış yüz, kenar (Gm), restorasyon yüzeyi, kemik kreti.
    const dYuz = [[dis - 0.6 - p.tG, -10], [dis - 0.3 - p.tG, -3], [dis - p.tG * 0.95 - 0.35 * p.dol, 0], [xAt(lab, Math.min(Gm, G)) - 1.5 - 0.3 * p.tG - 0.45 * p.dol, Gm - 1.1], [xAt(lab, Math.min(Gm, G)) - 0.55, Gm - 0.1]];
    const kenarX = Gm <= G ? xAt(lab, Gm) : ucX - 0.25 * clamp((Gm - G) / 2);
    const lyuz = lab.filter(([, y]) => y < Math.min(Gm, G)).reverse();
    const mukoza = smooth(FP(dYuz)) + ' ' + smooth(FP([[xAt(lab, Math.min(Gm, G)) - 0.55, Gm - 0.1], [kenarX, Gm]]), false) + ' ' +
      poly(FP((Gm > G ? [[ucX, G]] : []).concat(lyuz, [[-r, -0.3], [dis + 0.9, -0.45], [dis, -1.1], [dis - 0.3, -3], [dis - 0.6, -10]])), false) + ' Z';
    tag(svg('path', { d: mukoza, class: 'an-dis-eti' }, g), 'labial-mukoza');
    svg('path', { d: smooth(FP(dYuz.slice(2).concat([[kenarX, Gm]]))), class: 'an-keratin' }, g);
    // Palatinal mukoza.
    const palM = [[8.6, -1], [6, -0.6], [r + 1.4, -0.15], [r, -0.25]].concat(palEm.slice().reverse(), [[3.6, G + 0.9], [5, G + 0.5], [7, 3.1], [8.6, 2.6]]);
    tag(svg('path', { d: poly(FP(palM)) + ' Z', class: 'an-dis-eti' }, g), 'palatinal-mukoza');

    // İmplant, dayanak, kuron.
    implantGovde(g, FX(0), FYy(0), r * FK, FYy(0) + 2, 0.8 * FK);
    const rest = poly(FP(lab)) + ' ' + smooth(FP(kuronLab.concat(kuronPal)), false) + ' ' + poly(FP(palEm), false) + ' Z';
    tag(svg('path', { d: rest, class: 'an-kron' }, g), 'kron');
    tag(svg('path', { d: poly(FP([[-(r - 0.05), 0], [xAt(lab, 1.6) + 0.15, 1.6], [3.0 - 0.15, 1.6], [r - 0.05, 0]])) + ' Z', class: 'an-dayanak' }, g), 'dayanak');
    const altB = lab.filter(([, y]) => y <= G - 1), ustB = lab.filter(([, y]) => y >= G - 1);
    tag(svg('path', { d: poly(FP(altB)), class: 'an-kritik-alti' }, g), 'kritik-alti');
    tag(svg('path', { d: poly(FP(ustB)), class: 'an-kritik' }, g), 'kritik');
    // Planlanan kenar düzeyi (kesikli) ve kayma oku.
    svg('path', { d: poly(FP([[ucX - 3.2, G], [ucX + 0.4, G]])), class: 'an-olcum-kilavuz' }, g0);
    if (Math.abs(p.kay) > 0.1) {
      const ox = ucX - 2.6, yon = Math.sign(p.kay);
      svg('path', { d: poly(FP([[ox, G], [ox, Gm]])), class: 'an-kenar-ok' }, g0);
      svg('path', { d: poly(FP([[ox - 0.35, Gm - yon * 0.5], [ox, Gm], [ox + 0.35, Gm - yon * 0.5]])), class: 'an-kenar-ok' }, g0);
    }

    Object.assign(parts, {
      implant:        { ad: sayi(opt, 'İmplant', ' (çap 4,1 mm)'), at: [FX(0), FYy(-3.6)] },
      dayanak:        { ad: 'Dayanak', at: [FX(0.6), FYy(0.8)], ayrinti: true },
      kron:           { ad: 'İmplant üstü kron', at: [FX(0), FYy(G + 3.5)] },
      'labial-kemik': { ad: sayi(opt, 'Labial kemik', ` ≈ ${mm1(p.tB)} mm`), at: [FX(-r - p.tB / 2), FYy(-3)] },
      'palatinal-kemik': { ad: 'Palatinal kemik', at: [FX(3.4), FYy(-2.5)] },
      'labial-mukoza': { ad: sayi(opt, 'Labial mukoza', ` ≈ ${mm1(p.tG)} mm`), at: [FX(dis - p.tG / 2), FYy(-1.5)] },
      'palatinal-mukoza': { ad: 'Palatinal mukoza', at: [FX(3.8), FYy(1.6)] },
      kenar:          { ad: 'Mukoza kenarı', at: [FX(kenarX), FYy(Gm)] },
      'kritik-alti':  { ad: p.sub > 0.5 ? 'Kritik altı kontur: iç bükey' : p.sub < -1.3 ? 'Kritik altı kontur: aşırı dış bükey' : p.sub < -0.5 ? 'Kritik altı kontur: dış bükey' : 'Kritik altı kontur', at: FP([[xAt(lab, (G - 1) / 2), (G - 1) / 2]])[0] },
      kritik:         { ad: p.crit > 0.5 ? 'Kritik kontur: fazla (dış bükey)' : p.crit < -0.5 ? 'Kritik kontur: azaltılmış' : sayi(opt, 'Kritik kontur', ' (≈ 1 mm)'), at: FP([[xAt(lab, G - 0.5), G - 0.5]])[0] },
      plan:           { ad: 'Planlanan kenar düzeyi', at: [FX(ucX + 0.4), FYy(G)], ayrinti: true }
    });
    if (p.kay < -0.1) parts.kayma = { ad: p.sub < -1.3 ? 'Kenar apikale kayabilir (yaklaşık)' : 'Kenar apikale kayar (yaklaşık)', at: [FX(ucX - 2.6), FYy((G + Gm) / 2)] };
    if (p.kay > 0.1) parts.kayma = { ad: 'Kenar koronale kayabilir (yaklaşık)', at: [FX(ucX - 2.6), FYy((G + Gm) / 2)] };
    if (p.sub > 0.5) parts.hacim = { ad: 'Yumuşak doku hacmi artar', at: [FX(-r - 0.6), FYy(1.2)] };
    if (p.sub < -1.3) {
      parts.hacim = { ad: 'Mukoza gerilir ve incelir', at: [FX(xAt(lab, 1.2) - 0.45), FYy(1.2)] };
      parts.risk = { ad: 'Ödem ve çekilme riski', at: [FX(kenarX - 0.5), FYy(Gm - 0.5)] };
    } else if (p.sub < -0.5) {
      parts.hacim = { ad: 'Fasiyal profil dolgunlaşır', at: [FX(xAt(lab, 1.2) - 1.1), FYy(1.2)] };
      parts['kenar-duzeyi'] = { ad: 'Kenar düzeyi belirgin değişmez', at: [FX(ucX - 2.4), FYy(G)] };
    }
    sematikNot(g0, opt);
    return parts;
  }

  Object.assign(AT.anatomi.SABLONLAR, {
    'kontur-fasiyal': { ad: 'Fasiyal kontur: kritik ve kritik altı bölge (implant, labio-palatinal kesit)', varyantlar: Object.keys(FK_DURUM), durumlar: FK_DURUM, ciz: konturCiz, varsayilan: FK_TEMEL,
      not: 'Planlanan kenar çizgisi (kesikli) ve kenar kaydığında kırmızı kayma oku durumun parçasıdır: labels listesinde olmasa da çizilir. Oksuz çizim için kenarı kaymayan bir durum seç (duz, kritik-alti-konveks).' },
    papil: { ad: 'Papil: diş–implant arası kontur ve temas noktası (önden kesit)', varyantlar: Object.keys(PAP_DURUM), durumlar: PAP_DURUM, ciz: papilCiz, varsayilan: PAP_TEMEL,
      takma: { kuron: 'dogal-dis', 'kuron-sag': 'dogal-dis-sag' } }
  });
})(window.AT = window.AT || {});
