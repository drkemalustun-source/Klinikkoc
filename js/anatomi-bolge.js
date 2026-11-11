/* Bölgesel anatomik şablonlar: çene kemikleri, maksiller sinüs, sinirler ve damarlar.
 * anatomi.js'ten sonra yüklenir ve şablonlarını AT.anatomi.SABLONLAR'a ekler.
 * Ölçek: 160 × 90 tuval, 1,4 birim = 1 mm (diş/implant şablonundan küçük: daha geniş bölge görünür).
 * Koronal kesit; bukkal (yanak) taraf solda, orta hat sağda.
 * Görseller hiçbir atlastan kopyalanmadı; bilinen anatomik ölçülerle sıfırdan çizildi. */
(function (AT) {
  'use strict';
  if (!AT.anatomi) return;
  const { svg, smooth, poly, bant, ornekle, trabekul, range, clamp, f, uid } = AT.anatomi._y;
  const K = 1.4; // birim / mm
  const mm = (u) => Math.round((u / K) * 10) / 10;
  const tagger = (n, part) => { n.dataset.part = part; return n; };
  const nokta = (g, x, y, r, cls, part) => tagger(svg('circle', { cx: f(x), cy: f(y), r, class: cls }, g), part);
  // Diş içi kesitli damar-sinir demeti: arter (kırmızı), ven (mavi), sinir (sarı).
  function demet(g, x, y, r, parts, ad, onek) {
    nokta(g, x - r * 0.9, y + r * 0.15, r * 0.75, 'an-ven', onek + '-ven');
    nokta(g, x + r * 0.15, y - r * 0.75, r * 0.62, 'an-arter', onek + '-arter');
    nokta(g, x + r * 0.55, y + r * 0.45, r * 0.85, 'an-sinir', onek + '-sinir');
    parts[onek + '-sinir'] = { ad: ad.sinir, at: [x + r * 0.55, y + r * 0.45] };
    parts[onek + '-arter'] = { ad: ad.arter, at: [x + r * 0.15, y - r * 0.75] };
    parts[onek + '-ven'] = { ad: ad.ven, at: [x - r * 0.9, y + r * 0.15], ayrinti: true };
  }
  // Yivli implant: platform yP'de, gövde yukarı (yon -1) ya da aşağı (+1) uzar.
  function implantCiz(g, cx, yP, boy, yon, op) {
    const w = 3.15, adim = 1.6, sol = [[cx - w + 0.4, yP]];
    for (let s = 0.8; s < boy - 2; s += adim) sol.push([cx - w, yP + yon * s], [cx - w + 1, yP + yon * (s + adim / 2)]);
    sol.push([cx - w + 0.6, yP + yon * (boy - 1.2)]);
    const sag = sol.map(([x, y]) => [2 * cx - x, y]).reverse();
    const d = poly(sol) + ` Q${f(cx)},${f(yP + yon * (boy + 0.6))} ${f(sag[0][0])},${f(sag[0][1])} ` + poly(sag.slice(1), false) + ' Z';
    const n = tagger(svg('path', { d, class: 'an-implant', opacity: f(op) }, g), 'implant');
    return n;
  }

  /* ---------------- Maksiller sinüs (üst birinci büyük azı hizasında koronal kesit) ---------------- */

  const SINUS_DURUM = {
    dis:             { dis: 1, soket: 0, krest: 73, taban: 61, lift: 0, imp: 0, pencere: 0 },
    'cekim-sonrasi': { dis: 0, soket: 1, krest: 73, taban: 61, lift: 0, imp: 0, pencere: 0 },
    // Çekimden sonra kret yukarı-içe (santripetal) çekilir, sinüs tabanı aşağı iner (pnömatizasyon).
    dissiz:          { dis: 0, soket: 0, krest: 69, taban: 64, lift: 0, imp: 0, pencere: 0 },
    'ileri-atrofi':  { dis: 0, soket: 0, krest: 66.5, taban: 65, lift: 0, imp: 0, pencere: 0 },
    'sinus-lifti':   { dis: 0, soket: 0, krest: 69, taban: 64, lift: 8, imp: 1, pencere: 1 }
  };

  function sinusCiz(g, variant, opt) {
    const p = opt.p || SINUS_DURUM[variant] || SINUS_DURUM.dis;
    const id = uid();
    const defs = svg('defs', {}, g);
    trabekul(defs, id);
    const gr = svg('pattern', { id: id + 'gr', width: 2.2, height: 2, patternUnits: 'userSpaceOnUse' }, defs);
    svg('rect', { width: 2.2, height: 2, class: 'an-greft-zemin' }, gr);
    svg('path', { d: 'M0.5,0.6 l0.6,-0.3 l0.4,0.5 l-0.5,0.5 Z M1.4,1.3 l0.5,0.1 l0,0.5 l-0.6,0 Z', class: 'an-greft-tane' }, gr);
    const parts = {};
    const kr = p.krest, tb = p.taban, dis = clamp(p.dis), kubbe = Math.max(dis, clamp(p.soket || 0));
    const sx = 3.2 * clamp((73 - kr) / 7); // bukkal kemik daha çok kaybolur: kret palatinale kayar

    // Kemik dış hattı: bukkal yüz (yukarıdan kret'e), kret, damak (orta hatta).
    const bukkal = [[55, 9], [53, 20], [51.5, 32], [53.5, 42], [56.5, 50], [59.5, 58], [62, kr - 6], [63.8, kr - 2.2], [66, kr]]
      .map(([x, y]) => [x + sx * clamp((y - 50) / Math.max(1, kr - 50)), y]);
    const damak = [[73 + sx * 0.6, kr + 0.6], [79.5 + sx * 0.2, kr], [82, kr - 2], [86, kr - 5], [92, Math.min(64.5, kr - 6)], [100, 62], [111, 61]];
    const yuzey = bukkal.concat(damak);
    const kemik = smooth(yuzey) + ' L111,9 Z';
    svg('path', { d: kemik, class: 'an-kemik-zemin' }, g);
    tagger(svg('path', { d: kemik, fill: `url(#${id}tr)`, class: 'an-kemik' }, g), 'maksilla');
    tagger(svg('path', { d: smooth(yuzey), class: 'an-kortikal' }, g), 'maksilla');

    // Orbita ve infraorbital kanal.
    tagger(svg('path', { d: 'M57,0 L91,0 C92.5,4 92.8,8 92,10.5 C82,9.3 66,9.3 56,10.8 C55.4,7 55.8,3 57,0 Z', class: 'an-orbita' }, g), 'orbita');
    nokta(g, 72, 11.8, 1.05, 'an-sinir', 'infraorbital');

    // Burun boşluğu, konkalar, septum.
    tagger(svg('path', { d: 'M93.5,12 L108.8,12 L108.8,56 C108.8,57 108,57.2 107,57.2 L96.5,57.2 C94.6,57.2 93.5,56 93.5,54 Z', class: 'an-hava' }, g), 'burun');
    svg('path', { d: 'M93.5,12 L93.5,54 C93.5,56 94.6,57.2 96.5,57.2 L107,57.2 C108,57.2 108.8,57 108.8,56 L108.8,12', class: 'an-burun-mukoza' }, g);
    tagger(svg('path', { d: 'M93.5,37 C97,36 101,39 102.5,43 C103.5,46.5 101,49.5 97.5,49 C95.5,48.7 94.5,47 93.5,45.5 Z', class: 'an-konka' }, g), 'alt-konka');
    tagger(svg('path', { d: 'M93.5,17 C96.5,17 99,20 99,24 C99,27.5 96.5,29 94.5,28.2 L93.5,27 Z', class: 'an-konka' }, g), 'orta-konka');

    // Sinüs boşluğu: taban kökler çevresinde kubbeleşir (dis), çekimden sonra pnömatize olur (taban iner).
    const yan = [[57.5, 14], [55.5, 26], [55, 34], [56.5, 44], [59.5, 52]];
    const taban = [[61.5, tb - 3.5], [64, tb - 0.8], [65.2, tb - 0.4 - 0.4 * dis], [66.2, tb - 3.6 * kubbe], [67.8, tb - 3.8 * kubbe], [69, tb - 0.4],
                   [73.5, tb + 0.3], [78.6, tb - 0.2], [79.8, tb - 4.8 * kubbe], [82.2, tb - 4.8 * kubbe], [83.6, tb - 0.6], [86.5, tb - 1.6],
                   [89.6, tb - 5], [90.8, tb - 10]];
    const ic = [[91, 40], [91, 25], [90.8, 14]];
    const sinus = smooth(yan.concat(taban, ic)) + ' Z';
    tagger(svg('path', { d: sinus, class: 'an-hava' }, g), 'sinus');
    // Ostium: orta meatusa açılır.
    tagger(svg('path', { d: 'M90.4,23.4 L94,24.6 L94,26.6 L90.4,25.6 Z', class: 'an-hava' }, g), 'ostium');

    // Yükseltilmiş membran ve greft (sinüs lifti).
    const liftU = (p.lift || 0) * K;
    const can = (x) => clamp((x - 60) / 4.5) * clamp((90 - x) / 4.5);
    const mTaban = taban.map(([x, y]) => [x, Math.min(y, y - liftU * can(x))]);
    if (liftU > 0.05) {
      const greft = smooth(taban) + ' ' + smooth(mTaban.slice().reverse(), false) + ' Z';
      tagger(svg('path', { d: greft, fill: `url(#${id}gr)`, class: 'an-greft', opacity: f(clamp(liftU / 3)) }, g), 'greft');
    }
    tagger(svg('path', { d: smooth(yan.concat(mTaban, ic, [[90.8, 14], [57.5, 14]])), class: 'an-membran' }, g), 'membran');

    // Lateral pencere (lateral duvardan sinüse giriş) ve intraosseöz arka üst alveol arteri.
    if (p.pencere > 0.01) {
      tagger(svg('path', { d: 'M54.6,54.5 L60.8,54.5 L62.2,61 L57.6,61 Z', class: 'an-pencere', opacity: f(clamp(p.pencere)) }, g), 'pencere');
    }
    nokta(g, 54.9, 46.5, 0.75, 'an-arter', 'psa');

    // Yanak ve vestibül; ağız mukozası (alveol mukozası → çiğneme mukozası → damak mukozası).
    tagger(svg('path', { d: 'M55.8,49 C53.6,51.5 51.6,60 50.8,72 L50.5,88 L47.6,88 L47.6,30 L51.6,30 C52.2,36 53.2,42.5 55.8,49 Z', class: 'an-yanak' }, g), 'yanak');
    svg('path', { d: 'M55.8,49 C53.6,51.5 51.6,60 50.8,72 L50.5,88', class: 'an-mukoza-cizgi' }, g);
    const yon = [-0.35, 1];
    const alveolM = [[56, 49.2], [57.8, 53.5]].concat(bukkal.slice(5, 7));
    tagger(svg('path', { d: bant(alveolM, () => 1.5, yon), class: 'an-mukoza' }, g), 'alveol-mukozasi');
    const cigM = ornekleYol(bukkal.slice(6).concat(damak));
    tagger(svg('path', {
      d: bant(cigM, (s, q) => (q[0] < 82 ? 2.4 : q[0] < 96 ? 2.4 + 2.4 * clamp((q[0] - 82) / 6) - 1.6 * clamp((q[0] - 90) / 21) : 3.2 - 0.8 * clamp((q[0] - 96) / 15)), yon),
      class: 'an-dis-eti'
    }, g), 'damak-mukozasi');
    // Büyük palatin damar-sinir demeti: damak mukozasında, alveol çıkıntısı ile damak tonozunun birleşiminde.
    demet(g, 92.6, 66.6, 0.95, parts, { sinir: 'Büyük palatin sinir', arter: 'Büyük palatin arter', ven: 'Büyük palatin ven' }, 'buyuk-palatin');

    // Diş (üst birinci büyük azı: mezyobukkal ve palatinal kök). dis 0 iken görünmez (çekim → iyileşme).
    if (dis > 0.01) {
      const dg = svg('g', { opacity: f(dis) }, g);
      const tooth = 'M64.8,75.5 C64.5,69 64.5,62 66,58.5 Q67.5,57.5 68.6,59 C69.5,64 71,68.5 73,70 C75,68 77.5,62 79.8,57.5 Q81.3,56.3 82.4,58 C82.2,64 81,71 80.5,75.5 ' +
        'C81.5,78 82,82 79.5,85.7 Q77.5,87.2 75.5,85.8 C74.5,84.2 73.5,83.2 72.5,83.2 C71.5,83.2 70.5,84.4 69.5,85.5 Q67.5,86.9 65.6,85.3 C63.3,82 63.6,78 64.8,75.5 Z';
      svg('path', { d: tooth, class: 'an-pdl-cizgi' }, dg);
      tagger(svg('path', { d: tooth, class: 'an-dentin' }, dg), 'dis');
      tagger(svg('path', { d: 'M64.8,75.5 C63.6,78 63.3,82 65.6,85.3 Q67.5,86.9 69.5,85.5 C70.5,84.4 71.5,83.2 72.5,83.2 C73.5,83.2 74.5,84.2 75.5,85.8 Q77.5,87.2 79.5,85.7 C82,82 81.5,78 80.5,75.5 ' +
        'C79.8,78 79.6,81 78.4,83.4 Q77,84.6 75.6,83.6 C74.6,82.3 73.6,81.6 72.5,81.6 C71.5,81.6 70.5,82.3 69.5,83.4 Q68.3,84.4 67.2,83.6 C65.4,81 65.3,78 64.8,75.5 Z', class: 'an-mine' }, dg), 'mine');
      tagger(svg('path', { d: 'M68,79.5 Q68.5,80.8 69.5,80 L71,78.8 Q72.5,78.3 74,78.8 L75.6,80 Q76.6,80.8 77.2,79.5 C77.5,77.5 77.3,76.5 77,75.5 C78.5,70 80,63 81.3,57.8 L80.6,57.6 C79,63 77,69 75.5,73.6 ' +
        'C74.5,73.2 71.5,73.2 70.5,73.6 C69.2,69 68,63 67.2,59.4 L66.6,59.6 C67,64 67.6,70 68.2,75.5 C68,77 67.9,78 68,79.5 Z', class: 'an-pulpa' }, dg), 'pulpa');
    }
    // Taze çekim soketleri (kan pıhtısı): iki kök yuvası.
    if (p.soket > 0.01) tagger(svg('path', { d: 'M65.2,74 C64.9,68 65,62 66.3,59 Q67.5,58 68.4,59.4 C69.2,64 70.2,69 71.4,72.5 L71.4,74 Z M74.6,74 L74.6,72.4 C76.4,68 78.2,62 80,58.2 Q81.2,57.1 82,58.5 C81.9,64 81,70 80.4,74 Z', class: 'an-soket', opacity: f(clamp(p.soket)) }, g), 'soket');
    // İmplant: imp 0→1 boyunca kretten içeri vidalanır (10 mm).
    if (p.imp > 0.01) {
      const boy = 14, yP = kr + boy * (1 - clamp(p.imp)) + 0.4;
      implantCiz(g, 73 + sx * 0.4, yP, boy, -1, clamp(p.imp * 3));
    }

    Object.assign(parts, {
      sinus:          { ad: 'Maksiller sinüs', at: [74, 32] },
      membran:        { ad: liftU > 0.5 ? 'Yükseltilmiş membran' : 'Schneider membranı', at: liftU > 0.5 ? [76, tb - liftU + 0.2] : [55.9, 36] },
      taban:          { ad: 'Sinüs tabanı', at: [73.5, tb + 0.3] },
      rezidu:         { ad: `Rezidüel kemik ≈ ${mm(kr - tb)} mm`, at: [72.5, (kr + tb) / 2 + 0.4] },
      'lateral-duvar': { ad: 'Sinüs lateral duvarı', at: [54, 30] },
      'medial-duvar': { ad: 'Lateral burun duvarı', at: [92.2, 40] },
      ostium:         { ad: 'Ostium (orta meatusa)', at: [92.2, 25.2] },
      burun:          { ad: 'Burun boşluğu', at: [104, 31] },
      'alt-konka':    { ad: 'Alt konka', at: [99, 44] },
      'orta-konka':   { ad: 'Orta konka', at: [97, 22] },
      septum:         { ad: 'Burun septumu', at: [109.9, 34] },
      damak:          { ad: 'Sert damak', at: [105, 59] },
      orbita:         { ad: 'Orbita', at: [74, 5] },
      infraorbital:   { ad: 'İnfraorbital sinir', at: [72, 11.8] },
      psa:            { ad: 'Arka üst alveol a. (duvarda)', at: [54.9, 46.5] },
      'damak-mukozasi': { ad: 'Damak mukozası', at: [101, 63.6] },
      'alveol-mukozasi': { ad: 'Alveol mukozası', at: [57.3, 53] },
      vestibul:       { ad: 'Vestibül', at: [54.6, 58] },
      yanak:          { ad: 'Yanak', at: [49, 75] },
      kret:           { ad: 'Alveol kreti', at: [66.5, kr + 0.3] },
      maksilla:       { ad: 'Alveol çıkıntısı', at: [62, kr - 9] }
    });
    if (dis > 0.5) Object.assign(parts, {
      dis:   { ad: 'Üst birinci büyük azı', at: [72.5, 79] },
      'bukkal-kok':   { ad: 'Mezyobukkal kök', at: [65.4, 64] },
      'palatinal-kok': { ad: 'Palatinal kök', at: [81.6, 62] },
      furkasyon:      { ad: 'Furkasyon', at: [73, 70.4] }
    });
    if (p.soket > 0.5) parts.soket = { ad: 'Çekim soketi (kan pıhtısı)', at: [80.8, 64] };
    if (variant === 'ileri-atrofi') parts.atrofi = { ad: 'Kret palatinale çekilmiş', at: [64 + sx, kr - 1.5] };
    if (liftU > 0.5) parts.greft = { ad: 'Kemik grefti', at: [74, tb - liftU / 2] };
    if (p.pencere > 0.5) parts.pencere = { ad: 'Lateral pencere', at: [56.5, 57.8] };
    if (p.imp > 0.5) parts.implant = { ad: 'İmplant (10 mm)', at: [74.5, kr - 9] };
    return parts;
  }

  // Düz nokta listesini smooth()'un çizdiği eğri üzerinden sıklaştırır (bant için).
  function ornekleYol(pts) { return AT.anatomi._y.ornekle(pts); }

  /* ---------------- Mandibula (alt birinci büyük azı hizasında koronal kesit) ---------------- */

  // Çekimden sonra kret önce genişliğini, sonra yüksekliğini kaybeder (Cawood-Howell sınıfları II–VI).
  // Alt çenede rezorpsiyon dışa-aşağı (santrifügal): kret bukkale kayar. VI'da kanal krete yaklaşır.
  const MAND_DURUM = {
    dis:             { dis: 1, krest: 21, gen: 14.5, soket: 0, imp: 0 },
    'cekim-sonrasi': { dis: 0, krest: 21.5, gen: 14, soket: 1, imp: 0 },
    'cawood-3':      { dis: 0, krest: 26, gen: 12.5, soket: 0, imp: 0 },
    'cawood-4':      { dis: 0, krest: 28.5, gen: 3.2, soket: 0, imp: 0 },
    'cawood-5':      { dis: 0, krest: 35, gen: 14, soket: 0, imp: 0 },
    'cawood-6':      { dis: 0, krest: 41, gen: 16, soket: 0, imp: 0 },
    implant:         { dis: 0, krest: 26, gen: 12.5, soket: 0, imp: 1 }
  };
  const CAWOOD = { 'cekim-sonrasi': 'II', 'cawood-3': 'III', 'cawood-4': 'IV', 'cawood-5': 'V', 'cawood-6': 'VI' };

  function mandCiz(g, variant, opt) {
    const p = opt.p || MAND_DURUM[variant] || MAND_DURUM.dis;
    const id = uid();
    const defs = svg('defs', {}, g);
    trabekul(defs, id);
    const parts = {};
    const kr = p.krest, dis = clamp(p.dis);
    const rez = clamp((kr - 21) / 20);
    // Kanal: dişli çenede kretten ~17 mm aşağıda, lingual kortekse yakın; çap ~3 mm.
    const KX = 76.5, KY = 45, KR = 2.1;

    // Gövde: bukkalde eksternal oblik sırt, lingualde milohiyoid çizgi ve altında submandibular çukur, kalın bazal korteks.
    const cx = 73.2 - 2.2 * rez, w = p.gen / 2;
    const bk = [[61.2, 31], [59.8, 38], [60.2, 46], [61.5, 53], [64.5, 59.2]];
    const alt = [[70, 62], [76, 61.4]];
    const lg = [[80.6, 58], [82.4, 52.5], [82, 47], [81.2, 42.5], [83.2, 37.5], [83.6, 33]];
    const sivri = clamp((10 - p.gen) / 7); // bıçak sırtı kret: omuzlar aşağıda başlar
    const omuz = 3 + 4 * sivri;
    const solYan = bk.filter(([, y]) => y > kr + omuz + 1.5);
    const sagYan = lg.filter(([, y]) => y > kr + omuz + 1.5);
    const omB = [cx - w - 1.6 - 1.5 * sivri, kr + omuz], omL = [cx + w + 1.6 + 1.5 * sivri, kr + omuz];
    const cevre = [[cx - w, kr + 0.8], omB].concat(solYan, alt, sagYan, [omL, [cx + w, kr + 0.8]]);
    const r = Math.min(w, 1.6);
    const kemikD = smooth(cevre) + ` C${f(cx + w - r * 0.4)},${f(kr - 0.2)} ${f(cx + w - r)},${f(kr)} ${f(cx)},${f(kr)} C${f(cx - w + r)},${f(kr)} ${f(cx - w + r * 0.4)},${f(kr - 0.2)} ${f(cx - w)},${f(kr + 0.8)} Z`;
    const bx = cx - w, lx = cx + w;

    // Yumuşak dokular (önce): dil, ağız tabanı, milohiyoid kas, submandibular bez.
    tagger(svg('path', { d: 'M84.5,33 C86,24 95,15.5 111,14 L111,48 C102,49 92,46 85.5,40 C84,37.5 84,35 84.5,33 Z', class: 'an-dil' }, g), 'dil');
    tagger(svg('path', { d: 'M82.6,40.5 C90,48 100,53 111,55 L111,58.6 C99,56.6 89,51.6 81.8,44.2 Z', class: 'an-kas' }, g), 'milohiyoid');
    tagger(svg('path', { d: 'M82.2,48 C86,53 92,57.5 98.5,60 C99,66 94,71 87,70 C82.5,69.3 80.5,64.5 80.8,58.8 Z', class: 'an-bez' }, g), 'submandibular-bez');
    tagger(svg('path', { d: 'M84.2,31.4 C87,33 89.5,36 91.4,39.4 C89.2,40 86.4,38.6 83.6,35.4 Z', class: 'an-sublingual' }, g), 'sublingual-bez');
    tagger(svg('path', { d: 'M56.5,24 C55,36 54.6,50 56,60 C58,66 63,70 70,71 L70,74 C61,73.4 55,68.6 52.6,61 C50.8,50 51.4,36 53.2,24 Z', class: 'an-yanak' }, g), 'yanak');

    svg('path', { d: kemikD, class: 'an-kemik-zemin' }, g);
    tagger(svg('path', { d: kemikD, fill: `url(#${id}tr)`, class: 'an-kemik' }, g), 'mandibula');
    tagger(svg('path', { d: kemikD, class: 'an-kortikal-kalin' }, g), 'kortikal');

    // Mandibular kanal ve içindeki alt alveol sinir, arter, ven.
    tagger(svg('circle', { cx: KX, cy: KY, r: KR, class: 'an-kanal' }, g), 'kanal');
    demet(g, KX, KY, 1.05, parts, { sinir: 'Alt alveol sinir', arter: 'Alt alveol arter', ven: 'Alt alveol ven' }, 'alt-alveol');
    // Lingual sinir: ağız tabanında, lingual kortekse yakın mukozanın altında.
    const LN = [Math.max(omL[0], 82) + 2.4, Math.min(kr + 6, 34)];
    nokta(g, LN[0], LN[1], 0.95, 'an-sinir', 'lingual-sinir');
    // Taze çekim soketi (kan pıhtısı).
    if (p.soket > 0.01) tagger(svg('path', { d: 'M67,19 C66.4,25 67.2,32 69,37 Q72.6,39.2 76.2,37 C78.4,32 79.6,25 79.2,19 C76,18.2 70,18.2 67,19 Z', class: 'an-soket', opacity: f(clamp(p.soket)) }, g), 'soket');
    // Fasiyal arter ve ven: mandibula alt kenarına yakın, bezin yanında (masseterin önünde kesitte).
    nokta(g, 65.5, 66.4, 0.85, 'an-arter', 'fasiyal-arter');
    nokta(g, 63.4, 66.1, 0.95, 'an-ven', 'fasiyal-ven');

    // Mukoza: kret üzerinde çiğneme mukozası; bukkalde vestibül.
    const mukoza = AT.anatomi._y.ornekle([omB, [bx, kr + 0.8], [cx, kr], [lx, kr + 0.8], omL]);
    tagger(svg('path', { d: bant(mukoza, () => 2.2, [0, -1]), class: 'an-dis-eti' }, g), 'dis-eti');

    // Diş: alt birinci büyük azı mezyal kökü (iki kanallı). dis 0 iken görünmez.
    if (dis > 0.01) {
      const dg = svg('g', { opacity: f(dis) }, g);
      const t = 'M66.4,18.4 C65.8,25 66.6,32 68.6,37.4 Q72.5,39.8 76.6,37.6 C79,32 80.2,25 79.8,18.4 C80.8,16.5 81,12.5 79.4,9.3 Q78,8 76.6,9 C75.4,10.4 74.2,11 73.1,11 ' +
        'C72,11 70.8,10.3 69.6,9 Q68,8 66.8,9.3 C65.2,12.5 65.4,16.5 66.4,18.4 Z';
      svg('path', { d: t, class: 'an-pdl-cizgi' }, dg);
      tagger(svg('path', { d: t, class: 'an-dentin' }, dg), 'dis');
      tagger(svg('path', { d: 'M66.4,18.4 C65.4,16.5 65.2,12.5 66.8,9.3 Q68,8 69.6,9 C70.8,10.3 72,11 73.1,11 C74.2,11 75.4,10.4 76.6,9 Q78,8 79.4,9.3 C81,12.5 80.8,16.5 79.8,18.4 ' +
        'C79.2,16 79.4,13.5 78.4,11.8 Q77.6,11 76.8,11.8 C75.6,12.9 74.4,13.4 73.1,13.4 C71.8,13.4 70.6,12.9 69.4,11.8 Q68.6,11 67.8,11.8 C66.8,13.5 67,16 66.4,18.4 Z', class: 'an-mine' }, dg), 'mine');
      tagger(svg('path', { d: 'M69.6,15 Q70,13.6 71,14.4 Q73.1,15.6 75.2,14.4 Q76.2,13.6 76.6,15 C76.6,17 76.2,18.4 75.8,19.6 C76,26 75.4,32 74.8,36.6 L74.2,36.6 C74.4,31 74.4,25 73.6,20.4 L72.6,20.4 C71.8,25 71.8,31 72,36.6 L71.4,36.6 C70.8,32 70.2,26 70.4,19.6 C70,18.4 69.6,17 69.6,15 Z', class: 'an-pulpa' }, dg), 'pulpa');
    }
    // İmplant: kanalın 2 mm üstünde biter (güvenlik mesafesi); imp 0→1 içeri vidalanır.
    const guvenli = KY - KR - 2 * K; // implant ucu için en derin nokta
    const boy = guvenli - kr - 0.4;
    if (p.imp > 0.01) {
      implantCiz(g, 73.4, kr - 0.4 - boy * (1 - clamp(p.imp)), boy, 1, clamp(p.imp * 3));
      if (p.imp > 0.6) {
        svg('path', { d: `M${f(73.4)},${f(guvenli + 0.3)} L${f(73.4)},${f(KY - KR - 0.3)}`, class: 'an-guvenlik', opacity: f(clamp((p.imp - 0.6) * 2.5)) }, g);
      }
    }

    Object.assign(parts, {
      mandibula:       { ad: 'Mandibula gövdesi', at: [66, 50] },
      kortikal:        { ad: 'Bazal kortikal kemik', at: [70, 61.8] },

      'submandibular-cukur': { ad: 'Submandibular çukur', at: [82, 47] },
      kanal:           { ad: 'Mandibular kanal', at: [KX - KR, KY] },
      'lingual-sinir': { ad: 'Lingual sinir', at: LN },
      milohiyoid:      { ad: 'Milohiyoid kası', at: [97, 53.5] },
      'submandibular-bez': { ad: 'Submandibular bez', at: [90, 63] },
      'sublingual-bez': { ad: 'Sublingual bez', at: [87.5, 36.5] },
      dil:             { ad: 'Dil', at: [100, 30] },
      yanak:           { ad: 'Yanak (buksinatör)', at: [53.6, 45] },
      'fasiyal-arter': { ad: 'Fasiyal arter', at: [65.5, 66.4] },
      'fasiyal-ven':   { ad: 'Fasiyal ven', at: [63.4, 66.1], ayrinti: true },
      'dis-eti':       { ad: 'Çiğneme mukozası', at: [bx - 1.6, kr + 1.2] },
      kret:            { ad: 'Alveol kreti', at: [(bx + lx) / 2, kr - 0.6] },
      yukseklik:       { ad: `Kretten kanala ≈ ${mm(KY - KR - kr)} mm`, at: [KX + 0.5, (kr + KY - KR) / 2] }
    });
    if (kr < 28) parts['eksternal-oblik'] = { ad: 'Eksternal oblik sırt', at: [60.5, 33] };
    if (kr < 33) parts['milohiyoid-cizgi'] = { ad: 'Milohiyoid çizgi', at: [83.5, 36] };
    if (CAWOOD[variant]) parts.sinif = { ad: `Cawood-Howell sınıf ${CAWOOD[variant]}`, at: [cx, kr - 0.2] };
    if (p.soket > 0.5) parts.soket = { ad: 'Çekim soketi (kan pıhtısı)', at: [73, 30] };
    if (dis > 0.5) Object.assign(parts, {
      dis:  { ad: 'Alt 1. büyük azı (mezyal kök)', at: [73.1, 16] },
      apeks: { ad: 'Kök ucu', at: [72.6, 38.6] }
    });
    if (p.imp > 0.5) {
      parts.implant = { ad: `İmplant (${mm(boy)} mm)`, at: [74.4, kr + boy * 0.6] };
      parts.guvenlik = { ad: 'Güvenlik mesafesi 2 mm', at: [73.4, (guvenli + KY - KR) / 2] };
    }
    return parts;
  }

  /* ---------------- Furkasyon (alt birinci büyük azı) ----------------
   * Solda bukkalden görünüm (mezyal solda), sağda furkasyon düzeyinde yatay kesit (bukkal solda, mezyal üstte).
   * Ölçek 2,2 birim = 1 mm. Derece: Hamp (yatay kayıp; I < 3 mm, II ≥ 3 mm geçmeyen, III geçen). */
  const F = 2.2;
  const FUR_DURUM = {
    saglikli:   { kemik: 29.5, ic: 32.6, yatay: 0 },
    'derece-1': { kemik: 31.8, ic: 33, yatay: 2 },
    'derece-2': { kemik: 36, ic: 37, yatay: 5 },
    'derece-3': { kemik: 41, ic: 43, yatay: 11 }
  };
  const BL = 10.5; // furkasyon düzeyinde bukkolingual genişlik (mm)

  function furCiz(g, variant, opt) {
    const p = opt.p || FUR_DURUM[variant] || FUR_DURUM.saglikli;
    const id = uid();
    const defs = svg('defs', {}, g);
    trabekul(defs, id);
    const parts = {};
    const FORNIX = 31, yat = Math.max(0, p.yatay), gecen = clamp((yat - (BL - 0.5)) / 0.5);

    // Panel başlıkları ve yön harfleri.
    const yazi = (x, y, t, cls = 'an-panel-yazi') => { const n = svg('text', { x, y, class: cls, 'font-size': 2.6, 'text-anchor': 'middle' }, g); n.textContent = t; return n; };
    yazi(64, 4.2, 'Bukkalden görünüm');
    yazi(96, 4.2, 'Furkasyon düzeyinde kesit');
    yazi(50.6, 66, 'M', 'an-yon'); yazi(77.6, 66, 'D', 'an-yon');
    yazi(80.6, 46.3, 'B', 'an-yon'); yazi(111.2, 46.3, 'L', 'an-yon'); yazi(96, 25.6, 'M', 'an-yon'); yazi(96, 69.6, 'D', 'an-yon');

    // --- Sol panel: diş, ardından yarı saydam kemik (kökler kemiğin arkasında kalır).
    const dis = 'M52.6,24.5 C52.2,20 51.6,15 52.6,11 Q54,8.6 56,9.4 C57.5,10.4 58.6,10.6 60,9.6 Q62.5,7.8 65,9.4 C66.4,10.4 67.6,10.6 69,9.8 Q71.5,8.4 73.5,10 Q75.4,11.2 75.8,14 C76.3,18 75.8,21.5 75.2,24.5 ' +
      'C75,32 74.8,44 72.6,56.5 Q71.2,59.6 69.4,57.2 C68.6,48 67.4,38 65.6,32.4 Q64.2,30.4 62.6,32.4 C61.4,38 60.6,48 59.2,57.4 Q57.4,60.8 55.6,58.2 C54.2,48 53.4,34 52.6,24.5 Z';
    tagger(svg('path', { d: dis, class: 'an-dentin' }, g), 'dis');
    tagger(svg('path', { d: 'M52.6,24.5 C52.2,20 51.6,15 52.6,11 Q54,8.6 56,9.4 C57.5,10.4 58.6,10.6 60,9.6 Q62.5,7.8 65,9.4 C66.4,10.4 67.6,10.6 69,9.8 Q71.5,8.4 73.5,10 Q75.4,11.2 75.8,14 C76.3,18 75.8,21.5 75.2,24.5 ' +
      'L74,23.6 C74.4,20 74.4,16 73.4,13 Q71.5,11.6 69.5,12.6 C67.8,13.4 66.4,13.4 65,12.4 Q62.5,10.8 60,12.4 C58.6,13.4 57.5,13.4 56.2,12.4 Q54.4,11.4 53.9,13.6 C53.4,16.5 53.6,20.5 53.8,23.6 Z', class: 'an-mine' }, g), 'mine');
    tagger(svg('path', { d: 'M56.5,18 Q57,16.4 58.5,17.2 L62,18 Q64,18.4 66,18 L69.5,17.2 Q71,16.4 71.5,18 L71.6,24 C71.2,34 70.8,46 70.4,56.6 L69.8,56.6 C69.6,46 68.6,34 67.4,27.4 C66,26.4 62,26.4 60.6,27.4 C59.4,34 58.4,46 57.8,57 L57.2,57 C57,46 56.6,34 56.4,24 Z', class: 'an-pulpa', opacity: 0.55 }, g), 'pulpa');
    // Açığa çıkmış furkasyon girişi: kemik düzeyi fornixin altına inince görünür; III'te boydan boya açık (karanlık).
    if (p.kemik > FORNIX + 0.2) {
      const alt = Math.min(p.kemik, p.ic + 1.5);
      tagger(svg('path', { d: `M62.6,32.4 Q64.2,30.4 65.6,32.4 C66,${f(alt - 2)} 66.4,${f(alt)} 66.6,${f(alt)} L61.8,${f(alt)} C62,${f(alt)} 62.3,${f(alt - 2)} 62.6,32.4 Z`, class: 'an-furkasyon-acik', opacity: f(0.45 + 0.55 * clamp(yat / BL)) }, g), 'furkasyon-girisi');
    }
    // Kemik (bukkal plak): kökler arasında interradiküler kret, dişler arası septumlar.
    const k = p.kemik;
    const kemikYol = `M49,${f(k - 1.2)} C51,${f(k - 1.6)} 52.6,${f(k - 0.6)} 54,${f(k)} L61.6,${f(k)} C62.6,${f(k + 0.2)} 63.2,${f(Math.max(k, p.ic))} 64.1,${f(Math.max(k, p.ic))} C65,${f(Math.max(k, p.ic))} 65.6,${f(k + 0.2)} 66.6,${f(k)} L74,${f(k)} C75.6,${f(k - 0.6)} 77,${f(k - 1.6)} 79,${f(k - 1.2)} L79,72 L49,72 Z`;
    svg('path', { d: kemikYol, class: 'an-kemik-zemin', opacity: 0.72 }, g);
    tagger(svg('path', { d: kemikYol, fill: `url(#${id}tr)`, class: 'an-kemik', opacity: 0.5 }, g), 'kemik');
    tagger(svg('path', { d: kemikYol.split(' L79,72')[0], class: 'an-kortikal' }, g), 'kemik-duzeyi');
    // Dişeti kenarı (kesikli) ve kesit düzlemi.
    const dk = Math.min(k - 5.6, 25.6);
    tagger(svg('path', { d: `M49.5,${f(dk)} L78.5,${f(dk)}`, class: 'an-dis-eti-kenari' }, g), 'dis-eti-kenari');
    svg('path', { d: `M50,${FORNIX + 1.6} L78,${FORNIX + 1.6}`, class: 'an-kesit-duzlemi' }, g);

    // --- Sağ panel: yatay kesit. Kemik çerçevesi, kökler (PDL halkası ve sementle), kökler arası kemik.
    const cerceve = 'M84,30 C84,27.8 85.6,27 88,27 L104,27 C106.6,27 108.6,28 108.6,30.4 L108.6,61.6 C108.6,64 106.6,65 104,65 L88,65 C85.6,65 84,64 84,61.6 Z';
    svg('path', { d: cerceve, class: 'an-kemik-zemin' }, g);
    tagger(svg('path', { d: cerceve, fill: `url(#${id}tr)`, class: 'an-kemik' }, g), 'interradikuler-kemik');
    svg('path', { d: cerceve, class: 'an-kortikal' }, g);
    const xe = 87.2; // köklerin bukkal yüzlerini birleştiren çizgi (furkasyon girişi)
    if (yat > 0.01) {
      const uc = Math.min(xe + yat * F, 108.6 + 0.6);
      const ac = gecen > 0.5 ? 108.8 : uc;
      tagger(svg('path', { d: `M83.6,41.6 L${f(ac - 1.2)},41.6 Q${f(ac + 0.4)},41.6 ${f(ac + 0.4)},45.5 Q${f(ac + 0.4)},49.4 ${f(ac - 1.2)},49.4 L83.6,49.4 Z`, class: 'an-hava' }, g), 'defekt');
      svg('path', { d: `M83.6,43 L84.6,43 M83.6,48 L84.6,48`, class: 'an-kortikal' }, g);
    }
    const mez = 'M86.6,34.6 C86.6,32.4 88.8,32.2 92,32.4 L100,32.4 C103.4,32.2 105.4,32.6 105.4,35 C105.4,38.4 104.4,41.4 101.4,41.6 C99.2,41.7 98,40.4 96,40.4 C94,40.4 92.8,41.7 90.6,41.6 C87.6,41.4 86.6,38 86.6,34.6 Z';
    const dst = 'M87.8,53.6 C87.8,50.8 90,49.6 92,49.8 C93.6,50 94.6,50.8 96,50.8 C97.4,50.8 98.4,50 100,49.8 C102.2,49.6 104.4,50.8 104.4,53.8 C104.4,57.6 102,59.4 96,59.4 C90,59.4 87.8,57.4 87.8,53.6 Z';
    for (const [d, part] of [[mez, 'mezyal-kok-kesit'], [dst, 'distal-kok-kesit']]) {
      svg('path', { d, class: 'an-pdl-cizgi' }, g);
      tagger(svg('path', { d, class: 'an-dentin' }, g), part);
      svg('path', { d, class: 'an-sement-cizgi' }, g);
    }
    nokta(g, 91.4, 36.8, 0.8, 'an-pulpa', 'kanal-mb');
    nokta(g, 100.8, 36.8, 0.8, 'an-pulpa', 'kanal-ml');
    tagger(svg('ellipse', { cx: 96, cy: 54.6, rx: 2.2, ry: 0.9, class: 'an-pulpa' }, g), 'kanal-d');
    // Nabers sondası: bukkalden furkasyona, 3 mm aralıklı işaretler.
    if (opt.probe) {
      const uc = xe + Math.max(0.6, yat) * F - 0.3, bas = [77.5, 41];
      const pg = svg('g', { class: 'an-sonda' }, g);
      pg.dataset.part = 'sonda';
      svg('path', { d: `M${bas[0]},${bas[1]} Q${f((bas[0] + uc) / 2)},45.8 ${f(uc)},45.5`, class: 'an-sonda-govde', fill: 'none' }, pg);
      let d = '';
      for (let m = 3; m * F < uc - 80; m += 3) { const x = uc - m * F; d += `M${f(x)},44.6 L${f(x)},46.4 `; }
      svg('path', { d, class: 'an-sonda-cizgi' }, pg);
    }

    const H = ['', 'I', 'II', 'III'];
    const derece = gecen > 0.5 ? 3 : yat >= 3 ? 2 : yat > 0.2 ? 1 : 0;
    Object.assign(parts, {
      mine:              { ad: 'Mine', at: [56, 11.6] },
      'kok-govdesi':     { ad: 'Kök gövdesi (~3 mm)', at: [64.1, 27.6] },
      fornix:            { ad: 'Furkasyon tavanı (fornix)', at: [64.1, 31] },
      'mezyal-kok':      { ad: 'Mezyal kök', at: [55, 46] },
      'distal-kok':      { ad: 'Distal kök', at: [73.6, 46] },
      'kemik-duzeyi':    { ad: 'Kemik düzeyi', at: [76, k] },
      'dis-eti-kenari':  { ad: 'Dişeti kenarı', at: [76.5, dk] },
      'mezyal-kok-kesit': { ad: 'Mezyal kök (iki kanal)', at: [105, 35] },
      'distal-kok-kesit': { ad: 'Distal kök', at: [104, 55] },
      'interradikuler-kemik': { ad: 'Kökler arası kemik', at: [101, 45.5] },
      'kok-ici-oluk':    { ad: 'Kök iç yüzü oluğu', at: [96, 40.5], ayrinti: true }
    });
    if (derece) {
      parts['furkasyon-girisi'] = { ad: 'Açığa çıkmış furkasyon girişi', at: [64.1, Math.min(k, p.ic + 1.5) - 1] };
      parts.defekt = { ad: gecen > 0.5 ? 'Hamp III: boydan boya' : `Hamp ${H[derece]}: yatay ≈ ${Math.round(yat)} mm`, at: [Math.min(xe + yat * F, 106) - 1, 45.5] };
    } else parts['furkasyon-girisi'] = { ad: 'Furkasyon girişi (kemikle kapalı)', at: [64.1, 32.2] };
    if (opt.probe) parts.sonda = { ad: 'Nabers sondası', at: [79, 42.4] };
    return parts;
  }

  /* ---------------- Üst birinci büyük azı furkasyonu ----------------
   * Üç kök (mezyobukkal, distobukkal, palatinal), üç giriş: bukkal (MB–DB arası), mezyal (MB–P arası, palatinalden sondalanır),
   * distal (DB–P arası). Kök gövdesi yaklaşık mezyal 3,6 / bukkal 4,2 / distal 4,8 mm. Solda bukkal görünüm (diş aşağı bakar),
   * sağda furkasyon düzeyinde kesit (bukkal solda, mezyal üstte). yB/yM/yD: her girişten yatay kayıp (mm). */
  const FURU_DURUM = {
    saglikli:   { kemik: 41.6, yB: 0, yM: 0, yD: 0 },
    'bukkal-1': { kemik: 36, yB: 2, yM: 0, yD: 0 },
    'derece-2': { kemik: 32, yB: 3.2, yM: 2, yD: 1 },
    'derece-3': { kemik: 28, yB: 4, yM: 3.6, yD: 3.8 }
  };

  function furUstCiz(g, variant, opt) {
    const p = opt.p || FURU_DURUM[variant] || FURU_DURUM.saglikli;
    const id = uid();
    const defs = svg('defs', {}, g);
    trabekul(defs, id);
    const parts = {};
    const FORNIX = 37.6, k = p.kemik;
    const yazi = (x, y, t, cls = 'an-panel-yazi') => { const n = svg('text', { x, y, class: cls, 'font-size': 2.6, 'text-anchor': 'middle' }, g); n.textContent = t; return n; };
    yazi(64, 4.2, 'Bukkalden görünüm');
    yazi(96, 4.2, 'Furkasyon düzeyinde kesit');
    yazi(50.6, 66, 'M', 'an-yon'); yazi(77.6, 66, 'D', 'an-yon');
    yazi(80.6, 46.3, 'B', 'an-yon'); yazi(112, 46.3, 'P', 'an-yon'); yazi(96, 27.4, 'M', 'an-yon'); yazi(96, 66.6, 'D', 'an-yon');

    // Sol panel: palatinal kök arkada (soluk), diş, kemik (yukarıda, yarı saydam).
    tagger(svg('path', { d: 'M60,38 C60.5,28 62,16 64,8 Q65,6 66.4,8 C68,16 69,28 68.6,38 Z', class: 'an-dentin', opacity: 0.45 }, g), 'palatinal-kok');
    const dis = 'M52.6,45.5 C52.2,50 51.8,55 52.8,58.6 Q54.2,61.4 57,61 C59.6,60.6 61.6,59.6 63.6,58.6 Q64.2,58.3 64.8,58.6 C66.8,59.6 68.8,60.6 71.4,61 Q74.6,61.2 75.6,58.2 C76.3,54 75.8,49.5 75.2,45.5 ' +
      'C75,38 74.4,28 72.4,14 Q71,10.4 69.2,13 C68.4,22 67.4,31 65.6,37.6 Q64.2,39.6 62.6,37.6 C61.4,31 60.4,22 59.2,12.6 Q57.4,9.2 55.6,12 C54.2,22 53.4,36 52.6,45.5 Z';
    tagger(svg('path', { d: dis, class: 'an-dentin' }, g), 'dis');
    tagger(svg('path', { d: 'M52.6,45.5 C52.2,50 51.8,55 52.8,58.6 Q54.2,61.4 57,61 C59.6,60.6 61.6,59.6 63.6,58.6 Q64.2,58.3 64.8,58.6 C66.8,59.6 68.8,60.6 71.4,61 Q74.6,61.2 75.6,58.2 C76.3,54 75.8,49.5 75.2,45.5 ' +
      'L74,46.4 C74.4,50 74.2,54 73.4,57 Q71.5,58.6 69,58 C67.2,57.4 65.6,56.4 64.2,56.4 C62.8,56.4 61.2,57.4 59.4,58 Q55.8,58.8 54.4,56.6 C53.6,53.5 53.6,49.5 53.8,46.4 Z', class: 'an-mine' }, g), 'mine');
    tagger(svg('path', { d: 'M56.5,52 Q57,53.6 58.5,52.8 L62,52 Q64,51.6 66,52 L69.5,52.8 Q71,53.6 71.5,52 L71.6,46 C71.2,36 70.6,24 70,13.4 L69.4,13.4 C69.4,24 68.6,36 67.4,42.6 C66,43.6 62,43.6 60.6,42.6 C59.4,36 58.4,24 57.6,13 L57,13 C56.9,24 56.6,36 56.4,46 Z', class: 'an-pulpa', opacity: 0.55 }, g), 'pulpa');
    if (k < FORNIX - 0.2) {
      tagger(svg('path', { d: `M62.6,37.6 Q64.2,39.6 65.6,37.6 C66,${f(k + 2)} 66.4,${f(k)} 66.6,${f(k)} L61.8,${f(k)} C62,${f(k)} 62.3,${f(k + 2)} 62.6,37.6 Z`, class: 'an-furkasyon-acik', opacity: f(0.45 + 0.55 * clamp(p.yB / 3.5)) }, g), 'bukkal-giris');
    }
    const kemikYol = `M49,${f(k + 1.2)} C51,${f(k + 1.6)} 52.6,${f(k + 0.6)} 54,${f(k)} L74,${f(k)} C75.6,${f(k + 0.6)} 77,${f(k + 1.6)} 79,${f(k + 1.2)} L79,6 L49,6 Z`;
    svg('path', { d: kemikYol, class: 'an-kemik-zemin', opacity: 0.72 }, g);
    tagger(svg('path', { d: kemikYol, fill: `url(#${id}tr)`, class: 'an-kemik', opacity: 0.5 }, g), 'kemik');
    tagger(svg('path', { d: kemikYol.split(' L79,6')[0], class: 'an-kortikal' }, g), 'kemik-duzeyi');
    const dk = Math.max(k + 5.6, 44.4);
    tagger(svg('path', { d: `M49.5,${f(dk)} L78.5,${f(dk)}`, class: 'an-dis-eti-kenari' }, g), 'dis-eti-kenari');
    svg('path', { d: `M50,${FORNIX - 1.6} L78,${FORNIX - 1.6}`, class: 'an-kesit-duzlemi' }, g);

    // Sağ panel: üç kök kesiti ve kökler arası kemik; girişlerden yatay defektler.
    const cerceve = 'M83,32 C83,30 84.6,29.4 87,29.4 L106,29.4 C108.6,29.4 110,30.4 110,32.6 L110,59 C110,61.4 108.6,62 106,62 L87,62 C84.6,62 83,61.4 83,59 Z';
    svg('path', { d: cerceve, class: 'an-kemik-zemin' }, g);
    tagger(svg('path', { d: cerceve, fill: `url(#${id}tr)`, class: 'an-kemik' }, g), 'interradikuler-kemik');
    svg('path', { d: cerceve, class: 'an-kortikal' }, g);
    const MERKEZ = [95, 45.6];
    const girisler = [
      { ad: 'bukkal', y: p.yB, dis: [83, 45.6], giris: [87.4, 45.6] },
      { ad: 'mezyal', y: p.yM, dis: [99.6, 29.4], giris: [98.6, 38.4] },
      { ad: 'distal', y: p.yD, dis: [99.6, 62], giris: [98.6, 52.8] }
    ];
    let merkezeUlasan = 0;
    for (const G of girisler) {
      const dx = MERKEZ[0] - G.giris[0], dy = MERKEZ[1] - G.giris[1], L = Math.hypot(dx, dy);
      G.uzunluk = L; G.u = [dx / L, dy / L];
      if (G.y * F >= L - 0.3) merkezeUlasan++;
      if (G.y > 0.05) {
        const t = Math.min(G.y * F, L + 0.6);
        const uc = [G.giris[0] + G.u[0] * t, G.giris[1] + G.u[1] * t];
        tagger(svg('path', { d: `M${f(G.dis[0])},${f(G.dis[1])} L${f(G.giris[0])},${f(G.giris[1])} L${f(uc[0])},${f(uc[1])}`, class: 'an-defekt-cizgi' }, g), G.ad + '-defekt');
        G.uc = uc;
      }
    }
    const gecen = merkezeUlasan >= 2;
    if (gecen) tagger(svg('circle', { cx: MERKEZ[0], cy: MERKEZ[1], r: 2.2, class: 'an-hava' }, g), 'gecis');
    const kokler = [
      ['M86,35.6 C86,33.6 87.6,33 89.6,33 C91.8,33 93.4,34 93.4,36.4 C93.4,38.8 92.6,40.6 90.6,41.6 C89.2,42.2 87.6,42 86.8,40.6 C86.2,39.4 86,37.6 86,35.6 Z', 'mb-kesit'],
      ['M87,53.2 C87,51 88.4,49.8 90.2,49.8 C92,49.8 93,51 93,53 C93,55.2 91.8,56.6 90,56.6 C88.2,56.6 87,55.4 87,53.2 Z', 'db-kesit'],
      ['M99.4,45.6 C99.4,42 101,40.4 103.4,40.4 C105.8,40.4 107,42.4 107,45.6 C107,49 105.6,51 103.2,51 C100.8,51 99.4,49 99.4,45.6 Z', 'p-kesit']
    ];
    for (const [d, part] of kokler) {
      svg('path', { d, class: 'an-pdl-cizgi' }, g);
      tagger(svg('path', { d, class: 'an-dentin' }, g), part);
      svg('path', { d, class: 'an-sement-cizgi' }, g);
    }
    nokta(g, 89.8, 37.2, 0.7, 'an-pulpa', 'kanal-mb'); nokta(g, 90, 53.2, 0.6, 'an-pulpa', 'kanal-db'); nokta(g, 103.2, 45.6, 0.85, 'an-pulpa', 'kanal-p');
    if (opt.probe) {
      for (const G of girisler.slice(0, 2)) {
        const t = Math.max(0.8, G.y) * F, uc = [G.giris[0] + G.u[0] * Math.min(t, G.uzunluk), G.giris[1] + G.u[1] * Math.min(t, G.uzunluk)];
        const bas = G.ad === 'bukkal' ? [77.5, 41.4] : [104, 24.5];
        const pg = svg('g', { class: 'an-sonda' }, g); pg.dataset.part = 'sonda';
        svg('path', { d: `M${bas[0]},${bas[1]} Q${f(G.dis[0])},${f(G.dis[1])} ${f(uc[0])},${f(uc[1])}`, class: 'an-sonda-govde', fill: 'none' }, pg);
      }
    }

    const H = (y, gec) => (gec ? 'III' : y >= 3 ? 'II' : y > 0.2 ? 'I' : '0');
    Object.assign(parts, {
      mine:              { ad: 'Mine', at: [55.6, 58.6] },
      'kok-govdesi':     { ad: 'Kök gövdesi (~4 mm)', at: [64.1, 41.6] },
      fornix:            { ad: 'Furkasyon tavanı', at: [64.1, 38.6] },
      'mb-kok':          { ad: 'Mezyobukkal kök', at: [55.6, 24] },
      'db-kok':          { ad: 'Distobukkal kök', at: [72.6, 24] },
      'palatinal-kok':   { ad: 'Palatinal kök (arkada)', at: [64.6, 12] },
      'kemik-duzeyi':    { ad: 'Kemik düzeyi', at: [76.5, k] },
      'dis-eti-kenari':  { ad: 'Dişeti kenarı', at: [76.5, dk] },
      'mb-kesit':        { ad: 'Mezyobukkal kök', at: [93, 35] },
      'db-kesit':        { ad: 'Distobukkal kök', at: [92.6, 55] },
      'p-kesit':         { ad: 'Palatinal kök', at: [106.6, 44] },
      'interradikuler-kemik': { ad: 'Kökler arası kemik', at: [96.6, 41.6] },
      'mezyal-giris':    { ad: 'Mezyal giriş', at: [99.2, 33.6] },
      'distal-giris':    { ad: 'Distal giriş', at: [99.2, 57.6] }
    });
    if (k < FORNIX - 0.2) parts['bukkal-giris'] = { ad: 'Açığa çıkmış bukkal giriş', at: [64.1, k + 1] };
    else parts['bukkal-giris'] = { ad: 'Bukkal giriş (kemikle kapalı)', at: [64.1, 38.4] };
    for (const G of girisler) if (G.y > 0.2) parts[G.ad + '-defekt'] = { ad: `${G.ad[0].toUpperCase() + G.ad.slice(1)}: Hamp ${H(G.y, gecen && G.y * F >= G.uzunluk - 0.3)}`, at: G.uc };
    if (opt.probe) parts.sonda = { ad: 'Nabers sondası', at: [79, 42.6] };
    return parts;
  }

  /* ---------------- Çekim soketinin iyileşmesi ve soket koruma ----------------
   * Küçük azı soketinin bukkolingual kesiti (bukkal solda), 2,6 birim = 1 mm. t: 0 taze pıhtı → 1 granülasyon (~1. hafta)
   * → 2 geçici matris + örgü kemik (~4. hafta) → 3 örgü kemik dolumu (~8. hafta) → 4 yeniden şekillenme (3–6 ay).
   * Demet kemiği kaybolur, bukkal duvar daha çok rezorbe olur (yatay ≈ 3,8 mm, bukkal dikey ≈ 1,2 mm; Tan ve ark. 2012 derlemesi).
   * koruma: greft + kollajen örtü ile soket koruma; kayıp azalır. */
  const K2 = 2.6;
  const SOKET_DURUM = {
    taze:              { t: 0, koruma: 0 },
    'birinci-hafta':   { t: 1, koruma: 0 },
    'dorduncu-hafta':  { t: 2, koruma: 0 },
    'sekizinci-hafta': { t: 3, koruma: 0 },
    'alti-ay':         { t: 4, koruma: 0 },
    'soket-koruma':    { t: 4, koruma: 1 }
  };

  function soketCiz(g, variant, opt) {
    const p = opt.p || SOKET_DURUM[variant] || SOKET_DURUM.taze;
    const id = uid();
    const defs = svg('defs', {}, g);
    trabekul(defs, id);
    const og = svg('pattern', { id: id + 'og', width: 3.2, height: 2.6, patternUnits: 'userSpaceOnUse' }, defs);
    svg('rect', { width: 3.2, height: 2.6, class: 'an-matris' }, og);
    svg('path', { d: 'M0,1.3 C0.8,0.4 1.6,2 2.4,1 C2.8,0.6 3.2,1.2 3.2,1.2 M1.2,0 C1.4,0.8 1,1.6 1.6,2.6', class: 'an-orgu-tel' }, og);
    const gr = svg('pattern', { id: id + 'gr', width: 2.2, height: 2, patternUnits: 'userSpaceOnUse' }, defs);
    svg('rect', { width: 2.2, height: 2, class: 'an-greft-zemin' }, gr);
    svg('path', { d: 'M0.5,0.6 l0.6,-0.3 l0.4,0.5 l-0.5,0.5 Z M1.4,1.3 l0.5,0.1 l0,0.5 l-0.6,0 Z', class: 'an-greft-tane' }, gr);
    const parts = {};
    const t = Math.max(0, p.t), kor = clamp(p.koruma || 0);
    const r = clamp(t / 4) * (1 - 0.6 * kor);             // yeniden şekillenme oranı
    const Y0 = 25, ybk = Y0 + 1.24 * K2 * r, ylk = Y0 + 0.84 * K2 * r;
    const bukX = (y) => 68.4 - (y - Y0) * 0.14 + 3.8 * K2 * r * clamp(1 - (y - Y0) / 30);
    const linX = (y) => 94.5 + (y - Y0) * 0.15 - 0.8 * K2 * r * clamp(1 - (y - Y0) / 20);
    const buk = range(Math.ceil(ybk) + 1, 88, 4).reverse().map((y) => [bukX(y), y]).concat([[bukX(ybk), ybk]]);
    const lin = [[linX(ylk), ylk]].concat(range(Math.ceil(ylk) + 1, 88, 4).map((y) => [linX(y), y]));
    const tepeY = Math.min(ybk, ylk) - 0.6 * clamp(t - 2.5);
    const ust = `Q${f(80)},${f(tepeY)} ${f(lin[0][0])},${f(lin[0][1])}`;
    const sirt = smooth(buk) + ' ' + ust + ' ' + smooth(lin, false).replace(/^L/, 'L') + ' L98.5,88 L62,88 Z';
    svg('path', { d: sirt, class: 'an-kemik-zemin' }, g);
    tagger(svg('path', { d: sirt, fill: `url(#${id}tr)`, class: 'an-kemik' }, g), 'kemik');
    const clip = svg('clipPath', { id: id + 'sr' }, defs);
    svg('path', { d: sirt }, clip);
    const soket = 'M71,25 C71,38 75,52 80,57 C85,52 89,38 89,25 Z';
    const katman = (cls, op, part, extra = {}) => { if (op > 0.01) tagger(svg('path', Object.assign({ d: soket, class: cls, opacity: f(op), 'clip-path': `url(#${id}sr)` }, extra), g), part); };
    // Katmanlar: pıhtı → granülasyon dokusu → geçici matris/örgü kemik → olgun kemik (desen) ; koruma: greft.
    katman('an-soket', 1 - clamp(t - 0.4) * 0.9, 'pihti');
    katman('an-granulasyon', clamp(t - 0.3) * (1 - clamp(t - 1.9)), 'granulasyon');
    katman('an-orgu', clamp(t - 1.3) * (1 - 0.8 * clamp(t - 3.2)), 'orgu-kemik', { fill: `url(#${id}og)` });
    katman('an-kemik-zemin', clamp(t - 2.8), 'olgun-kemik');
    katman('an-kemik', clamp(t - 2.8), 'olgun-kemik', { fill: `url(#${id}tr)` });
    katman('an-greft', kor * (1 - 0.5 * clamp(t - 3)), 'greft', { fill: `url(#${id}gr)` });
    // Demet kemiği (soket duvarı): iyileşmeyle kaybolur.
    const dk = 1 - clamp(t - 1);
    if (dk > 0.01) tagger(svg('path', { d: 'M71,25 C71,38 75,52 80,57 C85,52 89,38 89,25', class: 'an-lamina', opacity: f(dk), 'clip-path': `url(#${id}sr)` }, g), 'demet-kemigi');
    tagger(svg('path', { d: smooth(buk) + ' ' + ust + ' ' + smooth(lin, false), class: 'an-kortikal' }, g), 'kret');
    if (r > 0.05) svg('path', { d: `M${f(bukX(Y0 + 15))},40 L68.4,25 L94.5,25`, class: 'an-eski-kemik' }, g); // eski sırt dış hattı

    // Yumuşak doku: çiğneme mukozası. t < 1 iken soketin üstü açık (yara), sonra epitel kapanır.
    const acik = 9.5 * (1 - clamp(t));
    const dis = ornekle([[bukX(46), 46], [bukX(36), 36]].concat([[bukX(ybk), ybk]], [[80, tepeY + 0.3]], [[linX(ylk), ylk]], [[linX(36), 36], [linX(46), 46]]), 6);
    const disa = (pts) => pts.map(([x, y]) => { const dx = x - 80, dy = y - 52, L = Math.hypot(dx, dy) || 1; return [x + (dx / L) * 6.5, y + (dy / L) * 6.5]; });
    const parcalar = acik < 0.05 ? [dis] : [dis.filter(([x]) => x < 80 - acik), dis.filter(([x]) => x > 80 + acik)];
    for (const pts of parcalar) if (pts.length > 1) {
      tagger(svg('path', { d: poly(pts) + ' ' + poly(disa(pts).reverse(), false) + ' Z', class: 'an-dis-eti' }, g), 'mukoza');
      svg('path', { d: poly(disa(pts)), class: 'an-keratin' }, g);
    }
    // Soket koruma örtüsü (rezorbe olan kollajen membran).
    if (kor > 0.01) tagger(svg('path', { d: `M69.5,${f(tepeY + 0.9)} Q80,${f(tepeY - 0.6)} 90.5,${f(Math.max(ylk, tepeY) + 0.9)}`, class: 'an-membran-kollajen', opacity: f(kor * (1 - 0.8 * clamp((t - 2) / 2))) }, g), 'kollajen-ortu');

    const kayipYatay = mm2(3.8 * r), kayipDikey = mm2(1.24 * r);
    Object.assign(parts, {
      kemik:          { ad: 'Alveol kemiği', at: [96, 70] },
      kret:           { ad: 'Sırt (kret) dış hattı', at: [bukX(ybk + 1), ybk + 1] },
      mukoza:         { ad: acik > 1 ? 'Dişeti (yara kenarı)' : 'Mukoza (kapanmış)', at: [acik > 1 ? 80 - acik - 2 : 80, tepeY - 3] },
      'bukkal-duvar': { ad: 'İnce bukkal duvar', at: [bukX(40) + 1.2, 40] },
      'lingual-duvar': { ad: 'Lingual duvar', at: [linX(40) - 1.6, 40] }
    });
    const ortaY = 42;
    if (t < 0.9) parts.pihti = { ad: 'Kan pıhtısı', at: [80, ortaY] };
    else if (t < 1.8) parts.granulasyon = { ad: 'Granülasyon dokusu', at: [80, ortaY] };
    else if (t < 3.2) parts['orgu-kemik'] = { ad: 'Geçici matris ve örgü kemik', at: [80, ortaY] };
    else parts['olgun-kemik'] = { ad: 'Olgunlaşan kemik', at: [80, ortaY] };
    if (dk > 0.5) parts['demet-kemigi'] = { ad: 'Demet kemiği (soket duvarı)', at: [74, 46] };
    if (r > 0.05) {
      parts.rezorpsiyon = { ad: `Yatay kayıp ≈ ${kayipYatay} mm`, at: [bukX(32) - 0.5, 32] };
      parts['dikey-kayip'] = { ad: `Bukkal dikey kayıp ≈ ${kayipDikey} mm`, at: [bukX(ybk), ybk] };
      parts['eski-hat'] = { ad: 'Çekim anındaki sırt hattı', at: [68.4, 25.4] };
    }
    if (kor > 0.5) { parts.greft = { ad: 'Kemik grefti', at: [82, 36] }; parts['kollajen-ortu'] = { ad: 'Kollajen örtü', at: [86, tepeY + 0.4] }; }
    return parts;
  }
  const mm2 = (v) => Math.round(v * 10) / 10;

  /* ---------------- Kemik içi (infraosseöz) defektler ----------------
   * Solda iki komşu küçük azının bukkalden görünümü (mezyal solda); defekt sağdaki dişin mezyalinde.
   * Sağda defektin orta düzeyinde yatay kesit (bukkal üstte). wB/wL/wP: bukkal, lingual, proksimal duvar (1 var, 0 yok);
   * krater: iki diş arasında, bukkal ve lingual duvarlı (iki duvarlı interdental krater). Ölçek 2,2 birim = 1 mm. */
  const KID_DURUM = {
    saglikli:      { D: 0, wB: 1, wL: 1, wP: 1, krater: 0 },
    'uc-duvarli':  { D: 5, wB: 1, wL: 1, wP: 1, krater: 0 },
    'iki-duvarli': { D: 5, wB: 0, wL: 1, wP: 1, krater: 0 },
    'tek-duvarli': { D: 5, wB: 0, wL: 0, wP: 1, krater: 0 },
    krater:        { D: 4, wB: 1, wL: 1, wP: 0, krater: 1 }
  };

  function kemikIciCiz(g, variant, opt) {
    const p = opt.p || KID_DURUM[variant] || KID_DURUM.saglikli;
    const id = uid();
    const defs = svg('defs', {}, g);
    trabekul(defs, id);
    const parts = {};
    const KR = 27.5, alt = KR + p.D * F, wB = clamp(p.wB), wL = clamp(p.wL), wP = clamp(p.wP), kr = clamp(p.krater);
    const yazi = (x, y, t, cls = 'an-panel-yazi') => { const n = svg('text', { x, y, class: cls, 'font-size': 2.6, 'text-anchor': 'middle' }, g); n.textContent = t; return n; };
    yazi(64, 4.2, 'Bukkalden görünüm');
    yazi(96.5, 4.2, 'Defekt düzeyinde kesit');
    yazi(50.6, 76, 'M', 'an-yon'); yazi(77.6, 76, 'D', 'an-yon');
    yazi(96.5, 27.4, 'B', 'an-yon'); yazi(96.5, 66.6, 'L', 'an-yon');

    // Sol panel: iki diş (kök kemiğin arkasında).
    const dis = (x0) => `M${x0 + 0.8},24 C${x0 + 0.2},20 ${x0},15 ${x0 + 0.8},11 Q${x0 + 3},7.6 ${x0 + 6.75},6.8 Q${x0 + 10.5},7.6 ${x0 + 12.7},11 C${x0 + 13.5},15 ${x0 + 13.3},20 ${x0 + 12.7},24 ` +
      `C${x0 + 12.4},36 ${x0 + 10.4},50 ${x0 + 7.6},59.4 Q${x0 + 6.75},61 ${x0 + 5.9},59.4 C${x0 + 3.1},50 ${x0 + 1.1},36 ${x0 + 0.8},24 Z`;
    const mine = (x0) => `M${x0 + 0.8},24 C${x0 + 0.2},20 ${x0},15 ${x0 + 0.8},11 Q${x0 + 3},7.6 ${x0 + 6.75},6.8 Q${x0 + 10.5},7.6 ${x0 + 12.7},11 C${x0 + 13.5},15 ${x0 + 13.3},20 ${x0 + 12.7},24 ` +
      `L${x0 + 11.6},23 C${x0 + 12},20 ${x0 + 12},15.6 ${x0 + 11.4},12.4 Q${x0 + 9.6},10 ${x0 + 6.75},9.4 Q${x0 + 3.9},10 ${x0 + 2.1},12.4 C${x0 + 1.5},15.6 ${x0 + 1.5},20 ${x0 + 1.9},23 Z`;
    const xA = 50.4, xB = 65.2;
    // Defekt (karanlık): B'nin mezyal kök yüzeyi boyunca; krater iki dişe de uzanır.
    const kokB = xB + 0.8 + 0.35 * Math.max(0, alt - 24) / 12, sol = kokB - 4 - 3.6 * kr;
    if (p.D > 0.05) tagger(svg('path', { d: `M${f(sol)},${f(KR - 0.5)} L${f(kokB + 0.4)},${f(KR - 0.5)} L${f(kokB + 0.4)},${f(alt)} Q${f((sol + kokB) / 2)},${f(alt + 1.8)} ${f(sol)},${f(alt - 0.8)} Z`, class: 'an-furkasyon-acik' }, g), 'defekt');
    for (const x0 of [xA, xB]) {
      tagger(svg('path', { d: dis(x0), class: 'an-dentin' }, g), 'dis');
      tagger(svg('path', { d: mine(x0), class: 'an-mine' }, g), 'mine');
    }
    // Kemik: interdental kret A tarafında proksimal duvar (wP), defektin önünde bukkal duvar (wB) kadar yüksek.
    const hP = KR + (1 - wP) * (alt - KR - 0.6), hB = KR + (1 - wB) * (alt - KR - 0.6);
    const kemikYol = `M49,29.4 C51,29.2 54,28.6 57,28.8 C59.5,29 ${f(sol - 1.5)},${f(hP + 0.4)} ${f(sol - 0.3)},${f(hP)} L${f(sol + 0.6)},${f(Math.max(hP, hB))} ` +
      `C${f(sol + 1.5)},${f(hB)} ${f(kokB - 0.5)},${f(hB)} ${f(kokB + 0.6)},${f(Math.min(hB + 0.4, 29))} C${f(xB + 4)},28.8 ${f(xB + 9)},28.8 79,29.4 L79,72 L49,72 Z`;
    svg('path', { d: kemikYol, class: 'an-kemik-zemin', opacity: 0.74 }, g);
    tagger(svg('path', { d: kemikYol, fill: `url(#${id}tr)`, class: 'an-kemik', opacity: 0.5 }, g), 'kemik');
    tagger(svg('path', { d: kemikYol.split(' L79,72')[0], class: 'an-kortikal' }, g), 'kemik-duzeyi');
    svg('path', { d: `M50,${f(KR + p.D * F * 0.55)} L78,${f(KR + p.D * F * 0.55)}`, class: 'an-kesit-duzlemi' }, g);
    tagger(svg('path', { d: 'M49.5,22.4 L78.5,22.4', class: 'an-dis-eti-kenari' }, g), 'dis-eti-kenari');

    // Sağ panel: yatay kesit, iki kök ve aradaki septum; defekt ve kalan duvarlar.
    const cerceve = 'M83,32 C83,30 84.6,29.4 87,29.4 L106,29.4 C108.6,29.4 110,30.4 110,32.6 L110,59 C110,61.4 108.6,62 106,62 L87,62 C84.6,62 83,61.4 83,59 Z';
    svg('path', { d: cerceve, class: 'an-kemik-zemin' }, g);
    tagger(svg('path', { d: cerceve, fill: `url(#${id}tr)`, class: 'an-kemik' }, g), 'septum');
    svg('path', { d: cerceve, class: 'an-kortikal' }, g);
    if (p.D > 0.05) {
      const x1 = 96 - (1 - wP) * 2.4 - kr * 2.6, x2 = 99.6 + kr * 0.2;
      const y1 = 40.6 - (1 - wB) * 11.6, y2 = 51.4 + (1 - wL) * 11;
      tagger(svg('path', { d: `M${f(x1)},${f(y1 + 1)} Q${f(x1)},${f(y1)} ${f(x1 + 1)},${f(y1)} L${f(x2)},${f(y1)} L${f(x2)},${f(y2)} L${f(x1 + 1)},${f(y2)} Q${f(x1)},${f(y2)} ${f(x1)},${f(y2 - 1)} Z`, class: 'an-hava' }, g), 'defekt-kesit');
    }
    const kok = (cx) => `M${cx},40.6 C${cx + 2.6},40.6 ${cx + 3.6},43 ${cx + 3.6},46 C${cx + 3.6},49 ${cx + 2.6},51.4 ${cx},51.4 C${cx - 2.6},51.4 ${cx - 3.6},49 ${cx - 3.6},46 C${cx - 3.6},43 ${cx - 2.6},40.6 ${cx},40.6 Z`;
    for (const [cx, part] of [[90, 'kok-a'], [103.2, 'kok-b']]) {
      svg('path', { d: kok(cx), class: 'an-pdl-cizgi' }, g);
      tagger(svg('path', { d: kok(cx), class: 'an-dentin' }, g), part);
      svg('path', { d: kok(cx), class: 'an-sement-cizgi' }, g);
      nokta(g, cx, 46, 0.7, 'an-pulpa', part + '-kanal');
    }

    const duvar = Math.round(wB + wL + wP);
    Object.assign(parts, {
      'kemik-duzeyi':  { ad: 'Kemik düzeyi', at: [53, 28.8] },
      'dis-eti-kenari': { ad: 'Dişeti kenarı', at: [52, 22.4] },
      'kok-a':         { ad: 'Komşu diş kökü', at: [87, 46], ayrinti: true },
      'kok-b':         { ad: 'Defektli diş kökü', at: [106.4, 46] },
      septum:          { ad: 'Interdental septum', at: [96.5, 58] }
    });
    if (p.D > 0.2) {
      parts.defekt = { ad: kr > 0.5 ? `İnterdental krater ≈ ${mm2(p.D)} mm` : `Kemik içi defekt ≈ ${mm2(p.D)} mm`, at: [(sol + kokB) / 2, alt - 2] };
      parts.duvar = { ad: kr > 0.5 ? 'İki duvarlı (krater)' : `${['Sıfır', 'Tek', 'İki', 'Üç'][duvar]} duvarlı defekt`, at: [97.8, 46] };
      if (wB > 0.5) parts['bukkal-duvar'] = { ad: 'Bukkal duvar', at: [97.8, 35] };
      if (wL > 0.5) parts['lingual-duvar'] = { ad: 'Lingual duvar', at: [97.8, 56] };
      if (wP > 0.5) parts['proksimal-duvar'] = { ad: 'Proksimal duvar', at: [94.6, 46] };
    }
    return parts;
  }

  /* ---------------- Dişeti çekilmesi (Cairo RT1–RT3) ve papilla ----------------
   * Üst orta kesicilerin vestibülden görünümü (diş aşağı bakar), 1,8 birim = 1 mm. Çekilme sağdaki dişte.
   * rec: bukkal çekilme (mm); ara: ara yüz ataşman/kemik kaybı (mm). Papilla doluluğu temas noktası–kemik kreti mesafesine
   * göre (Tarnow ve ark. 1992: ≤ 5 mm ≈ %98, 6 mm ≈ %56, 7 mm ≈ %27). */
  const C = 1.8;
  const CEK_DURUM = {
    saglikli: { rec: 0, ara: 0 },
    rt1:      { rec: 3, ara: 0 },
    rt2:      { rec: 3.5, ara: 2 },
    rt3:      { rec: 3.5, ara: 4.5 }
  };
  const papillaDolu = (d) => (d <= 5 ? 1 : d <= 6 ? 1 - 0.44 * (d - 5) : d <= 7 ? 0.56 - 0.29 * (d - 6) : Math.max(0.1, 0.27 - 0.17 * (d - 7)));

  function cekilmeCiz(g0, variant, opt) {
    const p = opt.p || CEK_DURUM[variant] || CEK_DURUM.saglikli;
    const id = uid();
    const defs = svg('defs', {}, g0);
    // Çizim 1,8 birim/mm koordinatlarında yapılır, tuvalin ortasına 1,22 kat büyütülerek yerleştirilir.
    const KB = 1.22, TX = 80 - 64.5 * KB, TY = 62 - 58.4 * KB;
    const g = svg('g', { transform: `translate(${f(TX)},${f(TY)}) scale(${KB})` }, g0);
    const parts = {};
    const W = 15.3, xA = 49.1, xB = 64.6, TEMAS = 49, MGJ = 24;
    const disYol = (x0) => `M${f(x0 + 7.65)},15.6 C${f(x0 + 4)},18 ${f(x0 + 2.2)},32 ${f(x0 + 1.7)},44.4 C${f(x0 + 0.6)},48 ${f(x0 + 0.2)},52 ${f(x0 + 0.5)},56 Q${f(x0 + 0.8)},58.4 ${f(x0 + 2.4)},58.4 ` +
      `L${f(x0 + 12.9)},58.4 Q${f(x0 + 14.5)},58.4 ${f(x0 + 14.8)},56 C${f(x0 + 15.1)},52 ${f(x0 + 14.7)},48 ${f(x0 + 13.6)},44.4 C${f(x0 + 13.1)},32 ${f(x0 + 11.3)},18 ${f(x0 + 7.65)},15.6 Z`;
    const kuron = (x0) => `M${f(x0 + 1.7)},44.4 Q${f(x0 + 7.65)},34.2 ${f(x0 + 13.6)},44.4 C${f(x0 + 14.7)},48 ${f(x0 + 15.1)},52 ${f(x0 + 14.8)},56 Q${f(x0 + 14.5)},58.4 ${f(x0 + 12.9)},58.4 ` +
      `L${f(x0 + 2.4)},58.4 Q${f(x0 + 0.8)},58.4 ${f(x0 + 0.5)},56 C${f(x0 + 0.2)},52 ${f(x0 + 0.6)},48 ${f(x0 + 1.7)},44.4 Z`;
    // Siyah üçgen için arka plan (ağız boşluğu) zaten koyu; dişler.
    for (const x0 of [xA, xB]) {
      tagger(svg('path', { d: disYol(x0), class: 'an-kok-yuzey' }, g), 'kok');
      tagger(svg('path', { d: kuron(x0), class: 'an-mine' }, g), 'kuron');
      tagger(svg('path', { d: `M${f(x0 + 1.7)},44.4 Q${f(x0 + 7.65)},34.2 ${f(x0 + 13.6)},44.4`, class: 'an-mse' }, g), 'mine-sement');
    }
    // Kemik düzeyleri (sondalama/radyografi ile; kesikli): bukkal kret MSS'den ~2 mm, ara yüz kreti.
    const araKret = 40.8 - p.ara * C, bukKret = 35.4 - Math.max(0, p.rec - 1) * C * 0.8;
    const d = (TEMAS - araKret) / C, dolu = papillaDolu(d);
    const tepe = araKret + Math.max(3.4, dolu * (TEMAS - araKret));
    const zA = 40.8, zB = 40.8 - p.rec * C;
    const kenar = [[49.1, 47.6], [51.4, 43.6], [56.75, zA], [62.2, 43.6], [64.5, tepe], [66.8, 43.6 - p.rec * C * 0.7], [72.25, zB], [77.6, 43.6 - p.rec * C * 0.25], [79.9, 47.6]];
    const de = smooth(kenar) + ' L79.9,4 L49.1,4 Z';
    tagger(svg('path', { d: de, class: 'an-dis-eti' }, g), 'dis-eti');
    const clipM = svg('clipPath', { id: id + 'mk' }, defs);
    svg('rect', { x: 40, y: 0, width: 50, height: MGJ }, clipM);
    tagger(svg('path', { d: de, class: 'an-mukoza', 'clip-path': `url(#${id}mk)` }, g), 'alveol-mukozasi');
    tagger(svg('path', { d: `M49.6,${MGJ} L79.4,${MGJ}`, class: 'an-mgj' }, g), 'mgj');
    tagger(svg('path', { d: smooth(kenar), class: 'an-keratin' }, g), 'dis-eti-kenari');
    tagger(svg('path', { d: `M52,${f(bukKret)} Q56.75,${f(bukKret - 2)} 61.5,${f(bukKret + 1.2)} Q64.5,${f(araKret - 0.4)} 67.5,${f(bukKret + 1.2)} Q72.25,${f(bukKret - 2)} 77,${f(bukKret)}`, class: 'an-kemik-hat' }, g), 'kemik-duzeyi');
    if (dolu < 0.97) tagger(svg('path', { d: `M64.5,${f(tepe + 0.2)} L${f(64.5 - 0.15)},${f(TEMAS)} L${f(64.5 + 0.15)},${f(TEMAS)} Z`, class: 'an-siyah-ucgen' }, g), 'siyah-ucgen');
    nokta(g, 64.5, TEMAS, 0.55, 'an-temas', 'temas');

    const sinif = p.rec < 0.3 ? '' : p.ara < 0.3 ? 'RT1' : p.ara <= p.rec ? 'RT2' : 'RT3';
    Object.assign(parts, {
      kuron:            { ad: 'Orta kesici kuronu', at: [56.75, 52] },
      'mine-sement':    { ad: 'Mine-sement sınırı', at: [72.25, 39.3] },
      'dis-eti':        { ad: 'Keratinize dişeti', at: [56.75, 33] },
      mgj:              { ad: 'Mukogingival sınır', at: [77, MGJ] },
      'alveol-mukozasi': { ad: 'Alveol mukozası', at: [56, 14] },
      papilla:          { ad: `Papilla (doluluk ≈ %${Math.round(dolu * 100)})`, at: [64.5, tepe - 1.2] },
      temas:            { ad: 'Temas noktası', at: [64.5, TEMAS] },
      'kemik-duzeyi':   { ad: 'Kemik düzeyi (kesikli)', at: [56.75, bukKret - 1.5] },
      'kret-temas':     { ad: `Kret–temas ≈ ${mm2(d)} mm`, at: [64.5, (araKret + TEMAS) / 2], ayrinti: true }
    });
    if (p.rec > 0.3) {
      parts.cekilme = { ad: `Bukkal çekilme ≈ ${mm2(p.rec)} mm`, at: [72.25, (zB + 39.3) / 2] };
      parts['acik-kok'] = { ad: 'Açığa çıkmış kök yüzeyi', at: [74.2, zB + 1.6] };
      parts.sinif = { ad: `Cairo ${sinif}`, at: [72.25, zB - 1] };
    }
    if (dolu < 0.97) parts['siyah-ucgen'] = { ad: 'Siyah üçgen', at: [64.5, (tepe + TEMAS) / 2] };
    if (p.ara > 0.3) parts['ara-kayip'] = { ad: `Ara yüz kaybı ≈ ${mm2(p.ara)} mm`, at: [64.5, araKret] };
    for (const k in parts) parts[k].at = [TX + parts[k].at[0] * KB, TY + parts[k].at[1] * KB];
    return parts;
  }


  /* ---------------- Plak ve gingival indeksler (vestibülden görünüm) ----------------
   * Üst orta kesici ve komşuları, kuron aşağı bakar; 2,6 birim = 1 mm (orta kesici kuronu ≈ 8,5 × 10,8 mm).
   * Silness–Löe plak indeksi (PlI 0–3, boyasız), Quigley–Hein (Turesky modifikasyonu, 0–5, plak boyası ile),
   * Löe–Silness gingival indeks (GI 0–3). Puanlanan diş ortadaki. Tüm alanlar sayısaldır, durumlar arası akar. */
  const dizi = (n) => Array.from({ length: n }, (_, i) => i);
  const OY_TEMEL = { sis: 0, skor: 0, h: 0, gor: 0, leke: 0, ara: 0, sonda: 0, boya: 0, gi: 0, s: 0, kanama: 0, spontan: 0 };
  const PLAK_DURUM = {
    'pli-0': { ...OY_TEMEL },
    'pli-1': { ...OY_TEMEL, skor: 1, h: 0.8, gor: 0.3, sonda: 1 },
    'pli-2': { ...OY_TEMEL, skor: 2, h: 2.4, gor: 0.9 },
    'pli-3': { ...OY_TEMEL, skor: 3, h: 5, gor: 1, ara: 1, gi: 1.2, s: 0.8 },
    'qh-0':  { ...OY_TEMEL, sis: 1, boya: 1 },
    'qh-1':  { ...OY_TEMEL, sis: 1, boya: 1, skor: 1, leke: 1, gor: 1 },
    'qh-2':  { ...OY_TEMEL, sis: 1, boya: 1, skor: 2, h: 2.2, gor: 1 },
    'qh-3':  { ...OY_TEMEL, sis: 1, boya: 1, skor: 3, h: 6.5, gor: 1 },
    'qh-4':  { ...OY_TEMEL, sis: 1, boya: 1, skor: 4, h: 14, gor: 1 },
    'qh-5':  { ...OY_TEMEL, sis: 1, boya: 1, skor: 5, h: 21.5, gor: 1 }
  };
  const GI_DURUM = {
    'gi-0': { ...OY_TEMEL, sis: 2 },
    'gi-1': { ...OY_TEMEL, sis: 2, skor: 1, gi: 1, s: 0.8, sonda: 1 },
    'gi-2': { ...OY_TEMEL, sis: 2, skor: 2, gi: 2, s: 2, sonda: 1, kanama: 1 },
    'gi-3': { ...OY_TEMEL, sis: 2, skor: 3, gi: 3, s: 3.2, kanama: 1, spontan: 1 }
  };
  const PLI_OLCUT = ['Dişeti bölgesinde plak yok', 'İnce plak; yalnız sonda ile görülür', 'Gözle görülen orta miktarda plak',
    'Cepte ve kenarda bol birikinti'];
  const QH_OLCUT = ['Plak yok', 'Servikalde ayrı plak lekeleri', 'Servikalde ≤ 1 mm kesintisiz ince bant', '1 mm’den geniş, kuronun 1/3’ünden az',
    'Kuronun 1/3–2/3’ü', 'Kuronun 2/3’ü ve fazlası'];
  const GI_OLCUT = ['Normal dişeti', 'Hafif iltihap, kanama yok', 'Orta iltihap, sondalamada kanama', 'Şiddetli iltihap, kendiliğinden kanama'];

  // Üst kesici kuronu, vestibülden: distal dış bükey ve köşesi yuvarlak, mezyal düz ve köşesi keskin; boyun dar.
  // u: distalden mezyale 0–w. mes: +1 mezyal sağda, −1 solda.
  function kesiciKuron(x0, o, mes) {
    const X = (u) => f(mes > 0 ? x0 + u : x0 + o.w - u), w = o.w, Z = o.Z, I = o.I;
    return `M${X(0.24 * w)},${f(Z - 9)} C${X(0.2 * w)},${f(Z - 3)} ${X(0.17 * w)},${f(Z + 1)} ${X(0.13 * w)},${f(Z + 4)} ` +
      `C${X(0.06 * w)},${f(Z + 9)} ${X(0)},${f(o.cD - 4)} ${X(0)},${f(o.cD)} L${X(0)},${f(o.cD + o.tD)} ` +
      `C${X(0)},${f(I - o.dI - o.rD * 0.45)} ${X(o.rD * 0.4)},${f(I - o.dI)} ${X(o.rD)},${f(I - o.dI * 0.7)} ` +
      `L${X(w - o.rM)},${f(I)} Q${X(w)},${f(I)} ${X(w)},${f(I - o.rM)} L${X(w)},${f(o.cM)} ` +
      `C${X(w)},${f(o.cM - 4)} ${X(0.95 * w)},${f(Z + 8)} ${X(0.89 * w)},${f(Z + 4)} C${X(0.86 * w)},${f(Z + 1)} ${X(0.83 * w)},${f(Z - 3)} ${X(0.8 * w)},${f(Z - 9)} Z`;
  }
  const ORTA_KESICI = { w: 22, Z: 30, I: 58, cD: 45.5, tD: 2.5, cM: 45, rD: 3.4, rM: 1.1, dI: 0.9 };
  const YAN_KESICI = { w: 17, Z: 32, I: 55.6, cD: 45.5, tD: 1.2, cM: 45.5, rD: 4.6, rM: 2.2, dI: 1.3 };

  function onYuzCiz(g0, variant, opt, tablo) {
    const p = { ...OY_TEMEL, ...(opt.p || tablo[variant] || tablo[Object.keys(tablo)[0]]) };
    const id = uid();
    const defs = svg('defs', {}, g0);
    const KB = 1.18, TX = 80 - 80 * KB, TY = 1.5;
    const kes = svg('clipPath', { id: id + 'c' }, defs);
    svg('rect', { x: 53, y: 4, width: 54, height: 60, rx: 3 }, kes);
    const gT = svg('g', { transform: `translate(${f(TX)},${TY}) scale(${KB})` }, g0);
    const g = svg('g', { 'clip-path': `url(#${id}c)` }, gT);
    const parts = {};
    // 12 (yan kesici) | 11 (puanlanan orta kesici) | 21. Orta hat x = 88,5. 2,6 birim = 1 mm.
    const DIS = [
      { x0: 49.5, o: YAN_KESICI, mes: 1, zu: 0.5 },
      { x0: 66.5, o: ORTA_KESICI, mes: 1, zu: 0.42 },
      { x0: 88.5, o: ORTA_KESICI, mes: -1, zu: 0.58 }
    ];
    const ORTA = 66.5, W = 22, MGJ = 16;
    const gi = clamp(p.gi / 3), s = p.s;
    const PAP = 43.2 + s * 0.5, us = 0.78 - 0.3 * clamp(s / 3);
    const kenarY = (x) => {
      let d = DIS[0];
      for (const k of DIS) if (x >= k.x0) d = k;
      const u = clamp((x - d.x0) / d.o.w), uz = d.zu;
      const t = u < uz ? (u / uz) * 0.5 : 0.5 + ((u - uz) / (1 - uz)) * 0.5;
      return PAP + (d.o.Z + s - PAP) * Math.pow(Math.sin(Math.PI * t), us);
    };
    const Z = ORTA_KESICI.Z + s, xz = ORTA + W * 0.42;
    for (const d of DIS) {
      tagger(svg('path', { d: kesiciKuron(d.x0, d.o, d.mes), class: 'an-mine' }, g), d.x0 === ORTA ? 'dis' : 'komsu');
      // Gelişim olukları (lob sınırları): kesici kenardan orta üçlüye silik iki çizgi.
      for (const k of [0.36, 0.66]) {
        const x = d.x0 + d.o.w * k;
        svg('path', { d: `M${f(x)},${f(d.o.I - 1.2)} Q${f(x + (k - 0.5) * 1.2)},${f(d.o.I - 8)} ${f(x + (0.5 - k) * 1.5)},${f(d.o.I - 15)}`, class: 'an-mine-oluk' }, g);
      }
    }
    const kc = svg('clipPath', { id: id + 'k' }, defs);
    svg('path', { d: kesiciKuron(ORTA, ORTA_KESICI, 1) }, kc);

    // Plak: dişeti kenarından kurona doğru bant (ara yüzlerde kalınlaşır); boya ile pembeleşir.
    const xs = dizi(45).map((i) => ORTA + (W * i) / 44);
    const plakH = (x) => { const t = (x - ORTA) / W; return p.h + p.ara * 5 * Math.pow(Math.abs(2 * t - 1), 4); };
    const plakCls = p.boya > 0.5 ? 'an-plak-boyali' : 'an-plak';
    if (p.h > 0.05 || p.ara > 0.05) {
      const duz = Math.max(0.15, 1 - p.h / 7);
      const ust = xs.map((x) => [x, kenarY(x) - 1.2]);
      const alt = xs.slice().reverse().map((x) => [x, Z + (kenarY(x) - Z) * duz + plakH(x)]);
      tagger(svg('path', { d: poly(ust.concat(alt)), class: plakCls, opacity: f(clamp(p.gor)), 'clip-path': `url(#${id}k)` }, g), 'plak');
    }
    if (p.leke > 0.05) for (const t of [0.14, 0.27, 0.41, 0.56, 0.7, 0.85]) {
      const x = ORTA + W * t;
      tagger(svg('ellipse', { cx: f(x), cy: f(kenarY(x) + 1), rx: 0.85, ry: 0.55, class: plakCls, opacity: f(clamp(p.leke)) }, g), 'plak');
    }

    // Sonda (GI'de oluğa girer): dişetinden önce çizilir, ucu dişeti altında kalır.
    if (p.sonda > 0.05 && p.sis > 1.5) svg('path', { d: `M103,62 L${f(xz + 1.5)},${f(Z - 2.6)}`, class: 'an-sonda-govde', opacity: f(clamp(p.sonda)) }, g);

    // Dişeti: yapışık dişeti + papilla; MGJ üstü alveol mukozası.
    const kenarNok = dizi(115).map((i) => { const x = 52 + i * 0.5; return [x, kenarY(Math.min(110, Math.max(49.5, x)))]; });
    const de = poly(kenarNok) + ' L109,2 L52,2 Z';
    tagger(svg('path', { d: de, class: 'an-dis-eti' }, g), 'dis-eti');
    const mk = svg('clipPath', { id: id + 'm' }, defs);
    svg('rect', { x: 40, y: 0, width: 80, height: MGJ }, mk);
    tagger(svg('path', { d: de, class: 'an-mukoza', 'clip-path': `url(#${id}m)` }, g), 'alveol-mukozasi');
    tagger(svg('path', { d: `M52,${MGJ} L108,${MGJ}`, class: 'an-mgj' }, g), 'mgj');
    // Portakal kabuğu (stippling): iltihapta ödemle kaybolur.
    const stOp = 1 - clamp((p.gi - 0.6) / 1.2);
    if (stOp > 0.05) {
      const st = svg('g', { opacity: f(stOp * 0.8) }, g);
      for (let yy = MGJ + 1.6; yy < 42; yy += 1.5) for (let xx = 53 + ((yy * 7) % 1.5); xx < 107; xx += 1.6) {
        if (yy < kenarY(xx) - 4.2) svg('circle', { cx: f(xx + Math.sin(xx * 3.1 + yy) * 0.35), cy: f(yy), r: 0.2, class: 'an-stippling' }, st);
      }
      st.dataset.part = 'stippling';
    }
    // Serbest dişeti oluğu.
    tagger(svg('path', { d: poly(kenarNok.map(([x, y]) => [x, y - 3.8])), class: 'an-dis-eti-olugu', opacity: f(1 - clamp(p.gi / 1.6)) }, g), 'serbest-oluk');
    // İltihap: kenar ve papillada kızarıklık (GI ile koyulaşır ve genişler).
    if (p.gi > 0.05) {
      const bandH = 3 + 3.4 * gi;
      const ic = kenarNok.map(([x, y]) => [x, y - bandH]).reverse();
      const yol = poly(kenarNok.concat(ic));
      tagger(svg('path', { d: yol, class: 'an-dis-eti an-iltihapli', opacity: f(clamp(p.gi / 2) * 0.9) }, g), 'renk');
      if (p.gi > 2) svg('path', { d: yol, class: 'an-mukoza', opacity: f(clamp(p.gi - 2) * 0.55) }, g);
      tagger(svg('path', { d: poly(kenarNok.filter(([x]) => x > 55 && x < 105).map(([x, y]) => [x, y - 1.5])), class: 'an-parlaklik', opacity: f(clamp(p.gi - 1) * 0.6) }, g), 'parlaklik');
    }
    // Kanama: sondalamadan sonra kenarda noktalar; GI 3'te kendiliğinden kanama ve ülser.
    if (p.kanama > 0.05) {
      const kg = svg('g', { opacity: f(clamp(p.kanama)) }, g);
      for (const t of [0.3, 0.42, 0.55, 0.68]) { const x = ORTA + W * t; svg('circle', { cx: f(x), cy: f(kenarY(x) + 0.45), r: 0.7, class: 'an-kanama' }, kg); }
      kg.dataset.part = 'kanama';
    }
    const xd = ORTA + W * 0.3;
    if (p.spontan > 0.05) {
      const yd = kenarY(xd);
      tagger(svg('path', { d: `M${f(xd - 0.8)},${f(yd)} C${f(xd - 0.9)},${f(yd + 3.4)} ${f(xd - 1.5)},${f(yd + 6)} ${f(xd)},${f(yd + 7.4)} C${f(xd + 1.5)},${f(yd + 6)} ${f(xd + 0.9)},${f(yd + 3.4)} ${f(xd + 0.8)},${f(yd)} Z`, class: 'an-kanama', opacity: f(clamp(p.spontan)) }, g), 'spontan');
      tagger(svg('ellipse', { cx: f(ORTA + 0.3), cy: f(PAP - 2.4), rx: 1.3, ry: 0.9, class: 'an-ulser-yuzey', opacity: f(clamp(p.spontan)) }, g), 'ulser');
    }
    // PlI 1: sonda kenarı sıyırır, ucunda plak.
    const xt = ORTA + W * 0.6;
    if (p.sonda > 0.05 && p.sis < 0.5) {
      const yt = kenarY(xt) + 0.6;
      svg('path', { d: `M106,50 L${f(xt)},${f(yt)}`, class: 'an-sonda-govde', opacity: f(clamp(p.sonda)) }, g);
      tagger(svg('circle', { cx: f(xt + 0.4), cy: f(yt), r: 0.7, class: 'an-plak', opacity: f(clamp(p.sonda)) }, g), 'sonda');
    }

    const sk = Math.round(p.skor);
    const xm = ORTA + W / 2;
    Object.assign(parts, {
      dis:              { ad: 'Puanlanan diş (üst orta kesici)', at: [84, 54] },
      komsu:            { ad: 'Yan kesici', at: [59, 50], ayrinti: true },
      'dis-eti':        { ad: 'Yapışık dişeti', at: [60, 24] },
      'alveol-mukozasi': { ad: 'Alveol mukozası', at: [98, 9] },
      mgj:              { ad: 'Mukogingival sınır', at: [102, MGJ] },
      papilla:          { ad: 'İnterdental papilla', at: [ORTA, PAP - 2.4] }
    });
    if (p.sis < 1.5) {
      const qh = p.sis > 0.5;
      parts.skor = { ad: qh ? `Quigley–Hein (Turesky) = ${sk}` : `Silness–Löe PlI = ${sk}`, at: [84.5, 46] };
      parts.olcut = { ad: (qh ? QH_OLCUT : PLI_OLCUT)[Math.min(sk, qh ? 5 : 3)], at: [85.5, 50] };
      if (p.h > 0.3 || p.leke > 0.3 || p.ara > 0.3) parts.plak = { ad: qh ? 'Boyanmış plak (eritrozin)' : 'Dental plak (biyofilm)', at: [xz - 3, Z + Math.max(1, p.h * 0.55)] };
      if (p.sonda > 0.3 && !qh) parts.sonda = { ad: 'Sonda ucunda plak', at: [xt + 0.4, kenarY(xt) + 0.6] };
      if (qh) parts.boya = { ad: 'Plak boyası ile değerlendirilir', at: [xm, 56], ayrinti: true };
    } else {
      parts.skor = { ad: `Löe–Silness GI = ${sk}`, at: [84.5, 47] };
      parts.olcut = { ad: GI_OLCUT[Math.min(sk, 3)], at: [85.5, 51] };
      parts['serbest-oluk'] = { ad: 'Serbest dişeti oluğu', at: [62, kenarY(62) - 3.8], ayrinti: true };
      if (p.gi < 1.2) parts.stippling = { ad: 'Portakal kabuğu görünümü', at: [98, 22] };
      if (p.gi > 0.3) {
        parts.renk = { ad: p.gi < 1.5 ? 'Hafif kızarıklık' : p.gi < 2.5 ? 'Kızarıklık' : 'Belirgin kızarıklık', at: [100, kenarY(100) - 2.4] };
        parts.odem = { ad: p.gi < 1.5 ? 'Hafif ödem' : p.gi < 2.5 ? 'Ödem, kenar kalınlaşır' : 'Belirgin ödem', at: [84, kenarY(84) - 1.2] };
      }
      if (p.gi > 1.5) parts.parlaklik = { ad: 'Parlak, gergin yüzey', at: [62, kenarY(62) - 1.5] };
      if (p.sonda > 0.3) parts.sonda = { ad: 'Sonda oluk boyunca gezdirilir', at: [96, 52.6] };
      if (p.kanama > 0.3) parts.kanama = { ad: p.spontan > 0.5 ? 'Kanama' : 'Sondalamada kanama', at: [ORTA + W * 0.68, kenarY(ORTA + W * 0.68) + 0.45] };
      if (p.spontan > 0.3) { parts.spontan = { ad: 'Kendiliğinden kanama', at: [xd, kenarY(xd) + 5] }; parts.ulser = { ad: 'Ülserasyon', at: [ORTA + 0.3, PAP - 2.4] }; }
    }
    for (const k in parts) parts[k].at = [TX + parts[k].at[0] * KB, TY + parts[k].at[1] * KB];
    return parts;
  }

  /* ---------------- Plak / kanama kayıt çizelgesi (O'Leary ve sondalamada kanama) ----------------
   * 16 diş (14–24, 44–34). tur 0: O'Leary plak kontrol kaydı, diş başına 4 yüzey; tur 1: sondalamada kanama (BOP),
   * diş başına 6 nokta. oran: işaretli yüzey oranı; hangi yüzeyin işaretleneceği sabit bir sırayla seçilir, böylece oran
   * değişince çizelge yavaşça dolar/boşalır. */
  const KAYIT_DURUM = {
    'plak-dusuk':    { tur: 0, oran: 0.09 },
    'plak-orta':     { tur: 0, oran: 0.38 },
    'plak-yuksek':   { tur: 0, oran: 0.78 },
    'kanama-saglik': { tur: 1, oran: 0.07 },
    'kanama-lokal':  { tur: 1, oran: 0.2 },
    'kanama-yaygin': { tur: 1, oran: 0.48 }
  };
  const UST = [14, 13, 12, 11, 21, 22, 23, 24], ALT = [44, 43, 42, 41, 31, 32, 33, 34];
  const sira = (n, tohum) => { let a = tohum; const r = dizi(n).map((i) => { a = (a * 48271) % 2147483647; return [a, i]; }); r.sort((x, y) => x[0] - y[0]); const o = []; r.forEach(([, i], k) => { o[i] = k; }); return o; };
  const SIRA4 = sira(64, 7), SIRA6 = sira(96, 11);

  function kayitCiz(g, variant, opt) {
    const p = opt.p || KAYIT_DURUM[variant] || KAYIT_DURUM['plak-orta'];
    const parts = {};
    const tur = clamp(p.tur), oran = clamp(p.oran);
    const yazi = (x, y, t, fs = 2.2) => { const n = svg('text', { x: f(x), y: f(y), class: 'an-panel-yazi', 'font-size': fs, 'text-anchor': 'middle' }, g); n.textContent = t; return n; };
    const ADIM = 7.3, X0 = 50.8, KUT = 6, satirY = [26, 52];
    const n4 = Math.round(oran * 64), n6 = Math.round(oran * 96);
    yazi(80, 9, tur < 0.5 ? 'O’Leary plak kontrol kaydı' : 'Sondalamada kanama (BOP) kaydı', 2.8);
    yazi(X0 + 1.5 * ADIM, 45.4, '← Sağ', 2); yazi(X0 + 6.5 * ADIM, 45.4, 'Sol →', 2);
    const g4 = svg('g', { opacity: f(1 - tur) }, g), g6 = svg('g', { opacity: f(tur) }, g);
    g4.dataset.part = 'cizelge'; g6.dataset.part = 'cizelge';
    [UST, ALT].forEach((dizi, r) => {
      const y0 = satirY[r];
      dizi.forEach((no, i) => {
        const x0 = X0 + i * ADIM, cx = x0 + KUT / 2, cy = y0 + KUT / 2;
        yazi(cx, r === 0 ? y0 - 1.6 : y0 + KUT + 3.4, String(no));
        // 4 yüzey: üçgenler (üst, sağ, alt, sol).
        const kose = [[x0, y0], [x0 + KUT, y0], [x0 + KUT, y0 + KUT], [x0, y0 + KUT]];
        for (let k = 0; k < 4; k++) {
          const idx = (r * 8 + i) * 4 + k;
          const a = kose[k], b = kose[(k + 1) % 4];
          svg('path', { d: `M${f(a[0])},${f(a[1])} L${f(b[0])},${f(b[1])} L${f(cx)},${f(cy)} Z`, class: SIRA4[idx] < n4 ? 'an-plak-boyali' : 'an-cizelge-kutu' }, g4);
        }
        svg('path', { d: `M${x0},${y0} L${x0 + KUT},${y0 + KUT} M${x0 + KUT},${y0} L${x0},${y0 + KUT}`, class: 'an-cizelge-cizgi' }, g4);
        svg('rect', { x: x0, y: y0, width: KUT, height: KUT, class: 'an-cizelge-cizgi' }, g4);
        // 6 nokta: vestibül (3) ve oral (3).
        svg('rect', { x: x0, y: y0, width: KUT, height: KUT, rx: 0.8, class: 'an-cizelge-kutu' }, g6);
        for (let k = 0; k < 6; k++) {
          const idx = (r * 8 + i) * 6 + k;
          const nx = x0 + 1.2 + (k % 3) * 1.8, ny = y0 + (k < 3 ? 1.4 : KUT - 1.4);
          svg('circle', { cx: f(nx), cy: f(ny), r: 0.65, class: SIRA6[idx] < n6 ? 'an-kanama' : 'an-kanama-yok' }, g6);
        }
      });
    });
    const yuzde = Math.round(oran * 100);
    const yorum = tur < 0.5 ? (yuzde <= 10 ? 'Hedef düzeyde (≤ %10)' : yuzde <= 20 ? 'Kabul edilebilir sınırda' : 'Yetersiz; hijyen eğitimi yinelenir')
      : (yuzde < 10 ? 'Dişeti sağlığı (BOP < %10)' : yuzde <= 30 ? 'Lokalize gingivitis (%10–30)' : 'Yaygın gingivitis (> %30)');
    Object.assign(parts, {
      cizelge: { ad: tur < 0.5 ? 'Her diş 4 yüzey (M, D, V, L/P)' : 'Her diş 6 nokta (3 vestibül, 3 oral)', at: [X0 + KUT / 2, satirY[0] + KUT / 2] },
      isaret:  { ad: tur < 0.5 ? 'Boyanan yüzey işaretlenir' : 'Kanayan nokta işaretlenir', at: [X0 + 3 * ADIM + KUT / 2, satirY[1] + KUT / 2] },
      formul:  { ad: tur < 0.5 ? 'Skor = boyalı ÷ taranan yüzey × 100' : 'BOP = kanayan ÷ toplam nokta × 100', at: [X0 + 7 * ADIM + KUT / 2, satirY[0] + KUT / 2] },
      sonuc:   { ad: tur < 0.5 ? `${n4} / 64 yüzey = %${Math.round((n4 / 64) * 100)}` : `${n6} / 96 nokta = %${Math.round((n6 / 96) * 100)}`, at: [X0 + 7 * ADIM + KUT / 2, satirY[1] + KUT / 2] },
      yorum:   { ad: yorum, at: [X0 + 7 * ADIM + KUT / 2, satirY[1] + KUT] }
    });
    if (tur > 0.5) parts['bop-not'] = { ad: 'Sağlam periodonsiyumda (2017 sınıflaması)', at: [80, 66], ayrinti: true };
    return parts;
  }


  /* ---------------- Ön maksilla ve dişeti fenotipi (üst orta kesiciden sagital kesit) ----------------
   * Labial solda, damak sağda, kuron aşağıda. 2,3 birim = 1 mm. tB: labial kemik plağı kalınlığı, tG: dişeti kalınlığı
   * (birim), deh: dehisens (mm), fen: fenestrasyon (0–1), rec: dişeti çekilmesi (mm), dis: diş var (1) / yok (0),
   * cok: çekim sonrası labial plağın çökmesi (0–1), imp: implant (0–1). */
  const S2 = 2.3;
  const OM_TEMEL = { dis: 1, tB: 2.8, tG: 3.4, deh: 0, fen: 0, rec: 0, cok: 0, imp: 0 };
  const OM_DURUM = {
    'kalin-fenotip': { ...OM_TEMEL },
    'ince-fenotip':  { ...OM_TEMEL, tB: 1.1, tG: 1.7 },
    dehisens:        { ...OM_TEMEL, tB: 1.1, tG: 1.7, deh: 4.5 },
    fenestrasyon:    { ...OM_TEMEL, tB: 1.1, tG: 1.7, fen: 1 },
    cekilme:         { ...OM_TEMEL, tB: 1.1, tG: 1.7, deh: 5, rec: 3 },
    'cekim-sonrasi': { ...OM_TEMEL, dis: 0, tB: 1.1, tG: 2.4, cok: 1 },
    implant:         { ...OM_TEMEL, dis: 0, tB: 2.4, tG: 3, cok: 0.4, imp: 1 }
  };

  function onMaksillaCiz(g0, variant, opt) {
    const p = { ...OM_TEMEL, ...(opt.p || OM_DURUM[variant] || OM_DURUM['kalin-fenotip']) };
    const id = uid();
    const defs = svg('defs', {}, g0);
    trabekul(defs, id);
    const kes = svg('clipPath', { id: id + 'c' }, defs);
    svg('rect', { x: 49.5, y: 3, width: 62, height: 82, rx: 3 }, kes);
    const g = svg('g', { 'clip-path': `url(#${id}c)` }, g0);
    const parts = {};
    const dis = clamp(p.dis), cok = clamp(p.cok), fen = clamp(p.fen), imp = clamp(p.imp);
    const rootLab = (y) => 65.5 + (56 - y) * 0.45;
    // Kuronun labial profili: servikal üçlüde dış bükey (en geniş yer), kesici kenara doğru düzleşir.
    const KL = [[56, 65.5], [58.5, 64.3], [61, 63.5], [64.5, 62.8], [68, 62.5], [72, 62.5], [75, 62.8], [78, 63.2], [80.3, 63.8]];
    const crownLab = (y) => { const yy = clamp(y, 56, 80.3); for (let i = 1; i < KL.length; i++) if (yy <= KL[i][0]) { const t = (yy - KL[i - 1][0]) / (KL[i][0] - KL[i - 1][0]); return KL[i - 1][1] + (KL[i][1] - KL[i - 1][1]) * t; } return 63.8; };
    const LB = (y) => rootLab(y) - (p.tB + Math.max(0, 52 - y) * 0.12) + cok * 5 * clamp((y - 30) / 22);
    const cL = 51 - p.deh * S2 - cok * 4, pcY = 54 - cok * 1.5, PCX = 81.8;
    const PB = [[PCX, pcY], [87, 49], [94, 41], [103, 33.5], [112, 29.3]];
    const adim = (a, b, st) => { const r = []; if (a > b) for (let y = a; y > b + 1e-6; y -= st) r.push(y); else for (let y = a; y < b - 1e-6; y += st) r.push(y); r.push(b); return r; };

    // Yumuşak doku: dudak, labial dişeti/mukoza, damak mukozası.
    const yMt = 58.3 - p.rec * S2, yM = cL + 1 + (yMt - (cL + 1)) * dis;
    const taban = (y) => (y > cL ? (y > 56 ? crownLab(y) : rootLab(y) + (1 - dis) * (LB(cL) - rootLab(cL))) : LB(y));
    const kalin = (y) => p.tG * Math.pow(clamp((yM - y) / 4), 0.6);
    const disY = adim(yM, 21, 1.5);
    const disNok = disY.map((y) => [taban(y) - kalin(y), y]);
    const gDis = (y) => taban(y) - kalin(y);
    const yA = yM - 4;
    const dudak = [[LB(22) - p.tG - 0.4, 20.5], [gDis(26) - 0.8, 26], [gDis(33) - 0.9, 33], [gDis(40) - 1, 40], [gDis(yA) - 1.1, yA],
      [Math.min(gDis(yA) - 1.2, crownLab(62) - 1.6), 62], [crownLab(70) - 1.9, 70], [62.4, 75.4], [59.5, 78], [54.5, 78.2], [50.8, 75], [48, 60], [48, 1], [58.6, 1], [57.4, 8], [56, 11.6], [59.5, 14.8]];
    tagger(svg('path', { d: smooth(dudak) + ' Z', class: 'an-yanak' }, g), 'dudak');
    tagger(svg('ellipse', { cx: 54.6, cy: 52, rx: 2.3, ry: 15, class: 'an-kas' }, g), 'orbikularis');
    nokta(g, 56.2, 69, 0.75, 'an-arter', 'ust-dudak-arteri');
    svg('path', { d: smooth(dudak.slice(0, 9)), class: 'an-mukoza-cizgi' }, g);
    const deYol = smooth(disNok) + ' ' + poly(disY.slice().reverse().map((y) => [taban(y) + 0.3, y]), false) + ' Z';
    tagger(svg('path', { d: deYol, class: 'an-dis-eti' }, g), 'dis-eti');
    const MGJ = Math.min(41, yM - 9);
    const mk = svg('clipPath', { id: id + 'm' }, defs);
    svg('rect', { x: 40, y: 0, width: 80, height: MGJ }, mk);
    tagger(svg('path', { d: deYol, class: 'an-mukoza', 'clip-path': `url(#${id}m)` }, g), 'alveol-mukozasi');
    svg('path', { d: smooth(disNok.filter(([, y]) => y >= MGJ)), class: 'an-keratin' }, g);
    const pm0 = [80.3 + (1 - dis) * 3.2, 62 + (1 - dis) * (pcY + 4.5 - 62)];
    const damak = [pm0, [84.6, 59.2 - (1 - dis) * 2], [90, 54], [97, 46.5], [105, 39.5], [112, 35.6]];
    tagger(svg('path', { d: smooth(damak) + ' ' + poly(PB.slice().reverse(), false) + ' Z', class: 'an-dis-eti' }, g), 'damak-mukozasi');
    svg('path', { d: smooth(damak), class: 'an-keratin' }, g);
    if (dis < 0.95) {
      const kx = LB(cL), tepe = Math.max(cL, pcY) + p.tG + 1.2;
      const kap = [[kx - p.tG, cL - 3], [kx - p.tG * 0.8, cL + 2.6], [(kx + PCX) / 2, tepe + 2], [83.8, pcY + 4.6], [86.4, 50.6], [PCX, pcY - 0.6], [(kx + PCX) / 2, Math.min(cL, pcY) - 0.4], [kx, cL - 0.6]];
      tagger(svg('path', { d: smooth(kap) + ' Z', class: 'an-dis-eti', opacity: f(1 - dis) }, g), 'kret-mukozasi');
    }

    // Kemik: labial plak → subnazal çukurluk (A noktası) → spina nasalis anterior → burun tabanı → sert damak.
    const labY = adim(cL, 26, 2);
    const kemik = labY.map((y) => [LB(y), y]).concat([[LB(26) - 0.8, 21], [61, 13.6], [56.6, 11.9], [60.5, 10.5], [75, 12], [92, 13.6], [112, 14.8]]);
    const tepeK = [(LB(cL) + PCX) / 2 + 1, Math.max(cL, pcY) + 1.6];
    const kemikYol = smooth(kemik) + ' ' + poly(PB.slice().reverse(), false) + ` Q${f(tepeK[0] + 3)},${f(tepeK[1] + 0.6)} ${f(tepeK[0])},${f(tepeK[1])} Q${f(LB(cL) + 0.6)},${f(cL + 2.4)} ${f(LB(cL))},${f(cL)} Z`;
    svg('path', { d: kemikYol, class: 'an-kemik-zemin' }, g);
    tagger(svg('path', { d: kemikYol, fill: `url(#${id}tr)`, class: 'an-kemik' }, g), 'kemik');
    tagger(svg('path', { d: smooth(kemik.slice(0, labY.length + 3)), class: 'an-kortikal' }, g), 'bukkal-kemik');
    svg('path', { d: smooth(kemik.slice(labY.length + 2)), class: 'an-kortikal' }, g);
    tagger(svg('path', { d: poly(PB), class: 'an-kortikal' }, g), 'palatinal-kemik');
    if (dis < 0.97) svg('path', { d: `M${f(PCX)},${f(pcY)} Q${f(tepeK[0] + 3)},${f(tepeK[1] + 0.6)} ${f(tepeK[0])},${f(tepeK[1])} Q${f(LB(cL) + 0.6)},${f(cL + 2.4)} ${f(LB(cL))},${f(cL)}`, class: 'an-kortikal', opacity: f(1 - dis) }, g);
    svg('path', { d: smooth([[61, 9.4], [75, 10.9], [92, 12.5], [112, 13.7]]), class: 'an-burun-mukoza' }, g);
    // Nazopalatin (insisiv) kanal: damaktaki insisiv foramenden burun tabanına.
    tagger(svg('path', { d: 'M90.9,44.6 L95,14.2', class: 'an-kanal-yol' }, g), 'nazopalatin-kanal');
    tagger(svg('path', { d: 'M90.2,49.5 Q90.2,46 90.6,44 L94.6,13.4', class: 'an-sinir-yol' }, g), 'nazopalatin-sinir');
    tagger(svg('path', { d: 'M91.6,49 Q91.4,46 91.6,44.4 L95.6,13.6', class: 'an-arter-yol' }, g), 'nazopalatin-arter');
    // Fenestrasyon: labial plakta, kök orta-apikal üçlüsünde pencere.
    if (fen > 0.05) tagger(svg('path', { d: poly([[LB(39.5) - 0.7, 39.5], [LB(33) - 0.7, 33], [rootLab(33), 33], [rootLab(39.5), 39.5]]) + ' Z', class: 'an-dis-eti', opacity: f(fen) }, g), 'fenestrasyon');

    // Diş.
    // Künt kesici kenar (~1 mm), palatinalde fossa (iç bükey) ve singulum (dış bükey).
    const kuronLab = KL.map(([y, x]) => [x, y]);
    const kuronPal = [[64.4, 81.3], [65.8, 81.6], [66.8, 80.6], [68.6, 77.6], [72, 73.4], [75.8, 68.6], [79.2, 64.4], [80.5, 61.2], [80, 58.5]];
    const kokPal = [[82, 50], [82.6, 42], [81.8, 33], [80.8, 28], [80, 25.6], [79, 26.2]];
    const kokLab = adim(28, 56, 4).map((y) => [rootLab(y), y]);
    const kok = [[80, 58.5]].concat(kokPal, kokLab);
    if (dis > 0.03) {
      const dg = svg('g', { opacity: f(dis) }, g);
      svg('path', { d: smooth(kok) + ' Z', class: 'an-pdl-cizgi' }, dg);
      tagger(svg('path', { d: smooth(kok) + ' Z', class: 'an-dentin' }, dg), 'kok');
      svg('path', { d: smooth(kok), class: 'an-sement-cizgi' }, dg);
      tagger(svg('path', { d: smooth(kuronLab.concat(kuronPal)) + ' Z', class: 'an-mine' }, dg), 'mine');
      svg('path', { d: smooth([[67.2, 57.4], [65.2, 62], [64.3, 68], [64.5, 75], [65.1, 78.4], [66.6, 78.2], [70.4, 73.2], [74, 68.8], [77.3, 64.6], [78.6, 61.2], [78.6, 59]]) + ' Z', class: 'an-dentin' }, dg);
      tagger(svg('path', { d: smooth([[69.3, 68.6], [70.3, 62], [72.9, 52], [77.2, 38], [79.6, 28.4], [80.2, 28.6], [78.9, 38], [75.6, 50], [73.4, 59], [71.8, 64.4], [70.4, 68.8]]) + ' Z', class: 'an-pulpa' }, dg), 'pulpa');
    }
    // İmplant: palatinal konumda, labialinde en az 2 mm kemik.
    const IX = 75.2, IY = 51.5 - cok * 3;
    if (imp > 0.03) {
      const ig = svg('g', { transform: `rotate(17,${IX},${IY})`, opacity: f(imp) }, g);
      implantCiz(ig, IX, IY, 24, -1, 1);
      const ag = svg('g', { opacity: f(imp) }, g);
      svg('path', { d: poly([[IX - 2.8, IY], [IX + 2.9, IY + 0.9], [79.4, 58.6], [67, 57]]) + ' Z', class: 'an-dayanak' }, ag);
      tagger(svg('path', { d: smooth(kuronLab.concat(kuronPal)) + ' Z', class: 'an-kron' }, ag), 'kron');
    }

    const tBmm = mm2(p.tB / S2), tGmm = mm2(p.tG / S2);
    Object.assign(parts, {
      dudak:            { ad: 'Üst dudak', at: [51.5, 40] },
      orbikularis:      { ad: 'M. orbicularis oris', at: [54.6, 52] },
      'ust-dudak-arteri': { ad: 'A. labialis superior', at: [56.2, 69] },
      vestibul:         { ad: 'Vestibül (forniks)', at: [LB(23) - p.tG - 0.6, 22.5] },
      'alveol-mukozasi': { ad: 'Alveol mukozası', at: [LB(32) - p.tG * 0.5, 32] },
      mgj:              { ad: 'Mukogingival sınır', at: [taban(MGJ) - kalin(MGJ), MGJ], ayrinti: true },
      'dis-eti':        { ad: `Dişeti kalınlığı ≈ ${tGmm} mm`, at: [taban(yM - 6) - kalin(yM - 6) * 0.5, yM - 6] },
      'bukkal-kemik':   { ad: `Labial kemik plağı ≈ ${tBmm} mm`, at: [LB(44) + 0.2, Math.min(44, cL - 2)] },
      ans:              { ad: 'Spina nasalis anterior', at: [57.4, 11.9] },
      'a-noktasi':      { ad: 'Subnazal çukurluk (A noktası)', at: [LB(26) - 0.6, 21.5], ayrinti: true },
      'burun-tabani':   { ad: 'Burun tabanı', at: [80, 12.2] },
      'nazopalatin-kanal': { ad: 'Nazopalatin (insisiv) kanal', at: [93.4, 26] },
      'nazopalatin-sinir': { ad: 'N. nasopalatinus', at: [92.2, 32] },
      'nazopalatin-arter': { ad: 'Nazopalatin damarlar', at: [92.4, 38], ayrinti: true },
      'insisiv-papilla': { ad: 'İnsisiv papilla (foramen)', at: [90.6, 51] },
      'palatinal-kemik': { ad: 'Palatinal kemik', at: [98, 30] },
      'damak-mukozasi': { ad: 'Damak mukozası', at: [101, 39.5] }
    });
    if (dis > 0.5) {
      Object.assign(parts, {
        mine:  { ad: 'Mine', at: [63.2, 70] },
        'kesici-kenar': { ad: 'Kesici kenar', at: [65.2, 81], ayrinti: true },
        singulum: { ad: 'Singulum', at: [79.6, 63.4] },
        pulpa: { ad: 'Pulpa', at: [74.6, 52] },
        kok:   { ad: 'Kök (dentin)', at: [81.8, 40] },
        kret:  { ad: 'Labial kret', at: [LB(cL) + 0.4, cL + 0.4], ayrinti: p.deh < 0.5 },
        fenotip: { ad: p.tG > 2.5 ? 'Kalın fenotip' : 'İnce fenotip', at: [taban(yM - 3) - kalin(yM - 3) * 0.6, yM - 3] }
      });
      if (p.deh > 0.5) parts.dehisens = { ad: `Dehisens ≈ ${mm2(p.deh)} mm`, at: [rootLab((cL + 51) / 2) - 0.3, (cL + 51) / 2] };
      if (fen > 0.5) parts.fenestrasyon = { ad: 'Fenestrasyon', at: [rootLab(36) - 0.8, 36] };
      if (p.rec > 0.3) parts.cekilme = { ad: `Dişeti çekilmesi ≈ ${mm2(p.rec)} mm`, at: [rootLab((yM + 56) / 2) - 0.2, (yM + 56) / 2] };
    } else {
      parts.kret = { ad: imp > 0.5 ? 'Alveol kreti' : 'Çökmüş labial duvar', at: [LB(cL + 0.01) + 0.6, cL + 1] };
      if (imp > 0.5) {
        parts.implant = { ad: 'İmplant (palatinal konumda)', at: [IX + 4, IY - 12] };
        parts.kron = { ad: 'İmplant üstü kuron', at: [70, 70] };
        parts['bukkal-kemik'].ad = 'Labialde ≥ 2 mm kemik hedeflenir';
      } else parts.rezorpsiyon = { ad: 'Kayıp en çok labial yüzde', at: [LB(46) - 0.4, 46] };
    }
    return parts;
  }


  /* ---------------- Ön mandibula (alt orta kesiciden sagital kesit, simfiz) ----------------
   * Labial solda, dil sağda, kuron yukarıda. 1,9 birim = 1 mm. dis: diş var/yok; at: kret yüksekliği kaybı (mm);
   * imp: implant; perf: implantın lingual kortekse yönelmesi (0–1; 1'de lingual perforasyon). */
  const S3 = 1.9;
  const AM_TEMEL = { dis: 1, at: 0, imp: 0, perf: 0, tB: 1.2, tG: 1.8 };
  const AM_DURUM = {
    dis:                   { ...AM_TEMEL },
    'cekim-sonrasi':       { ...AM_TEMEL, dis: 0, at: 3 },
    atrofi:                { ...AM_TEMEL, dis: 0, at: 10 },
    implant:               { ...AM_TEMEL, dis: 0, at: 4, imp: 1 },
    'lingual-perforasyon': { ...AM_TEMEL, dis: 0, at: 4, imp: 1, perf: 1 }
  };
  const araDeger = (L, y) => { if (y <= L[0][0]) return L[0][1]; for (let i = 1; i < L.length; i++) if (y <= L[i][0]) { const t = (y - L[i - 1][0]) / (L[i][0] - L[i - 1][0]); return L[i - 1][1] + (L[i][1] - L[i - 1][1]) * t; } return L[L.length - 1][1]; };

  function onMandibulaCiz(g0, variant, opt) {
    const p = { ...AM_TEMEL, ...(opt.p || AM_DURUM[variant] || AM_DURUM.dis) };
    const id = uid();
    const defs = svg('defs', {}, g0);
    trabekul(defs, id);
    const kes = svg('clipPath', { id: id + 'c' }, defs);
    svg('rect', { x: 49.5, y: 3, width: 62, height: 83, rx: 3 }, kes);
    const g = svg('g', { 'clip-path': `url(#${id}c)` }, g0);
    const parts = {};
    const dis = clamp(p.dis), imp = clamp(p.imp), perf = clamp(p.perf);
    const adim = (a, b, st) => { const r = []; for (let y = a; y < b - 1e-6; y += st) r.push(y); r.push(b); return r; };
    const KL = [[6.8, 66], [8, 65.6], [10, 65.2], [14, 64.5], [18, 63.9], [21.5, 63.9], [24, 64.6]];
    const crownLab = (y) => araDeger(KL, y);
    const rootLab = (y) => 64.6 + (y - 24) * 0.46;
    const cK = 27.8 + p.at * S3;
    const ALT = [[46, 72.4], [52, 71], [58, 67.4], [64, 63.8], [69, 62.6], [74, 64.2], [78, 67], [80.5, 70.5]];
    const LBs = (y) => (y <= 46 ? rootLab(y) - p.tB - (y - 27.8) * 0.06 : araDeger(ALT, y)) + (1 - dis) * 2.5 * clamp(1 - (y - cK) / 8);
    const LIN = [[28.2, 78.6], [31, 81.5], [38, 84.5], [48, 88], [58, 91], [61, 92.6], [64, 93.2], [67, 92.4], [70, 91.5], [76, 88.5], [80, 83.5]];
    const LS = (y) => araDeger(LIN, y);
    const kL = [LBs(cK), cK], kR = [LS(cK) - (1 - dis) * 1.2, cK + 0.4], kM = [(kL[0] + kR[0]) / 2, cK - 1.3 * (1 - dis) + dis];

    // Yumuşak doku: alt dudak ve çene ucu, dil, ağız tabanı.
    const yM = cK + 1 + (22.4 - (cK + 1)) * dis, yF = Math.max(45, cK + 7);
    const taban = (y) => (y < cK ? (dis > 0.5 ? (y < 24 ? crownLab(y) : rootLab(y)) : kL[0]) : LBs(y));
    const kalin = (y) => p.tG * Math.pow(clamp((y - yM) / 3), 0.6);
    const gD = (y) => taban(y) - kalin(y);
    const yA = yM + 4;
    const dudak = [[LBs(yF) - p.tG - 0.4, yF + 0.6], [gD(yF - 5) - 0.9, yF - 5], [gD(yA + 4) - 1, yA + 4], [gD(yA) - 1.1, yA], [Math.min(gD(yA) - 1.2, crownLab(18) - 1.6), 18], [62.4, 13.6], [59.4, 11.4], [54.6, 11.6], [50.6, 15],
      [48, 26], [48, 88], [88, 88], [82, 70], [74, 56]];
    tagger(svg('path', { d: smooth(dudak) + ' Z', class: 'an-yanak' }, g), 'alt-dudak');
    tagger(svg('ellipse', { cx: 54.6, cy: 27, rx: 2.2, ry: 9.5, class: 'an-kas' }, g), 'orbikularis');
    tagger(svg('ellipse', { cx: 57.4, cy: 60, rx: 2.8, ry: 9, transform: 'rotate(24,57.4,60)', class: 'an-kas' }, g), 'mentalis');
    nokta(g, 56.4, 16.4, 0.7, 'an-arter', 'alt-dudak-arteri');
    svg('path', { d: smooth(dudak.slice(0, 7)), class: 'an-mukoza-cizgi' }, g);
    const disY = adim(yM, yF, 1.5);
    const deYol = smooth(disY.map((y) => [gD(y), y])) + ' ' + poly(disY.slice().reverse().map((y) => [taban(y) + 0.3, y]), false) + ' Z';
    tagger(svg('path', { d: deYol, class: 'an-dis-eti' }, g), 'dis-eti');
    const MGJ = yM + 9;
    const mk = svg('clipPath', { id: id + 'm' }, defs);
    svg('rect', { x: 40, y: MGJ, width: 80, height: 60 }, mk);
    tagger(svg('path', { d: deYol, class: 'an-mukoza', 'clip-path': `url(#${id}m)` }, g), 'alveol-mukozasi');
    // Ağız tabanı (lingual): dişeti kenarından tabana, oradan dile.
    const tabanNok = dis > 0.5 && cK < 31 ? [[76.5, 22.6], [79.6, 25.6], [83.4, 30.6], [87, 36], [92, 39.5], [100, 41], [112, 40]]
      : [[kR[0] + 0.3, cK - 1.4], [kR[0] + 3.6, Math.min(cK + 2.5, 38)], [100, 41], [112, 40]];
    tagger(svg('path', { d: smooth(tabanNok) + ' L112,88 L84,88 L80,60 Z', class: 'an-yanak' }, g), 'agiz-tabani');
    svg('path', { d: smooth(tabanNok), class: 'an-mukoza-cizgi' }, g);
    if (dis > 0.05) tagger(svg('path', { d: poly([[76.5, 22.6], [79.6, 25.6], [83.4, 30.6], [81.5, 31], [78.6, 28.2], [76.2, 24.8]]) + ' Z', class: 'an-dis-eti', opacity: f(dis) }, g), 'lingual-dis-eti');
    if (dis < 0.95) {
      const kap = [[kL[0] - p.tG, cK + 4.5], [kL[0] - p.tG * 0.6, cK - 0.6], [kM[0], kM[1] - 2.5], [kR[0] + 1.6, cK - 0.8], [kR[0] + 2.8, cK + 4], [kR[0] + 0.6, cK + 3], [kM[0], kM[1] + 1], [kL[0] + 0.4, cK + 3]];
      tagger(svg('path', { d: smooth(kap) + ' Z', class: 'an-dis-eti', opacity: f(1 - dis) }, g), 'kret-mukozasi');
    }
    tagger(svg('ellipse', { cx: 93.4, cy: 46.6, rx: 5, ry: 3.1, transform: 'rotate(14,93.4,46.6)', class: 'an-sublingual' }, g), 'sublingual-bez');
    tagger(svg('path', { d: poly([[93, 61.2], [93.2, 64.3], [112, 60], [112, 43], [101, 45]]) + ' Z', class: 'an-kas' }, g), 'genioglossus');
    tagger(svg('path', { d: poly([[92.7, 65.3], [92.1, 68.8], [112, 77], [112, 66.5]]) + ' Z', class: 'an-kas', opacity: 0.8 }, g), 'geniohyoid');
    tagger(svg('path', { d: smooth([[80.4, 15.5], [83.6, 9], [92, 5.6], [112, 4.6], [112, 40], [100, 41], [92, 39.5], [87.4, 35.4], [84.4, 29.4], [81.8, 22.6]]) + ' Z', class: 'an-dil' }, g), 'dil');
    tagger(svg('path', { d: 'M112,51.6 Q102,54.6 97,55 T91.2,57.2', class: 'an-arter-yol' }, g), 'sublingual-arter');
    tagger(svg('path', { d: 'M112,81.4 Q100,82.2 94,81 T88.4,78.8', class: 'an-arter-yol' }, g), 'submental-arter');

    // Kemik: ince labial plak → B noktası → pogonion → menton → kalın alt kenar → spina mentalis → lingual kret.
    const labY = adim(cK, 80.5, 2.5), linY = adim(cK, 80, 2.5).reverse();
    const dis_ = labY.map((y) => [LBs(y), y]).concat([[75, 82.4], [80, 82.2]], linY.map((y) => [LS(y) - (y < cK + 6 ? (1 - dis) * 1.2 * (1 - (y - cK) / 6) : 0), y]));
    const kemikYol = smooth(dis_) + ` Q${f(kR[0] - 1)},${f(kM[1])} ${f(kM[0])},${f(kM[1])} Q${f(kL[0] + 1)},${f(kM[1])} ${f(kL[0])},${f(kL[1])} Z`;
    svg('path', { d: kemikYol, class: 'an-kemik-zemin' }, g);
    tagger(svg('path', { d: kemikYol, fill: `url(#${id}tr)`, class: 'an-kemik' }, g), 'kemik');
    tagger(svg('path', { d: smooth(dis_), class: 'an-kortikal-kalin' }, g), 'kortikal');
    if (dis < 0.97) svg('path', { d: `M${f(kR[0])},${f(kR[1])} Q${f(kR[0] - 1)},${f(kM[1])} ${f(kM[0])},${f(kM[1])} Q${f(kL[0] + 1)},${f(kM[1])} ${f(kL[0])},${f(kL[1])}`, class: 'an-kortikal', opacity: f(1 - dis) }, g);
    // Lingual foramen ve kanalı (a. sublingualis dalı girer); mandibular insisiv kanal kesiti.
    tagger(svg('path', { d: 'M91.4,57.2 L83,59.6', class: 'an-kanal-ince' }, g), 'lingual-foramen');
    svg('path', { d: 'M91.4,57.2 L83.4,59.5', class: 'an-arter-yol' }, g);
    nokta(g, 75.4, 61, 1.1, 'an-kanal', 'insisiv-kanal');
    nokta(g, 75.4, 61, 0.45, 'an-sinir', 'insisiv-kanal');

    // Diş.
    const kuronLab = KL.map(([y, x]) => [x, y]);
    const kuronLin = [[76, 24.6], [76.7, 23], [75.8, 21.4], [73.4, 18.6], [71, 14.5], [69.4, 10.4], [68.8, 7.8], [68.2, 6.7], [66.6, 6.4]];
    const kok = [[64.6, 24]].concat(adim(28, 44, 4).map((y) => [rootLab(y), y]), [[76, 47.8], [77, 48.4], [77.8, 45], [78.2, 39], [77.6, 31], [76, 24.6]]);
    if (dis > 0.03) {
      const dg = svg('g', { opacity: f(dis) }, g);
      svg('path', { d: smooth(kok) + ' Z', class: 'an-pdl-cizgi' }, dg);
      tagger(svg('path', { d: smooth(kok) + ' Z', class: 'an-dentin' }, dg), 'kok');
      svg('path', { d: smooth(kok), class: 'an-sement-cizgi' }, dg);
      tagger(svg('path', { d: smooth(kuronLin.concat(kuronLab)) + ' Z', class: 'an-mine' }, dg), 'mine');
      svg('path', { d: smooth([[66, 23.4], [65.2, 20.6], [65.4, 16], [66.2, 11.6], [66.8, 8.8], [67.9, 8.8], [69.8, 13.8], [72, 18], [74.4, 21.2], [75.2, 23.2], [74.8, 24.4]]) + ' Z', class: 'an-dentin' }, dg);
      tagger(svg('path', { d: smooth([[68, 15.6], [68.8, 21], [70.2, 28], [73.2, 38], [76.2, 46.6], [76.8, 46.4], [75, 38], [72.6, 28], [71.2, 21], [69.2, 15.8]]) + ' Z', class: 'an-pulpa' }, dg), 'pulpa');
    }
    // İmplant: kret ortasından; güvenli eksen simfizin eksenini izler, yanlış eksende lingual korteks delinir.
    const IX = (kL[0] + kR[0]) / 2 + 0.6, IY = cK - 0.2, aci = -8 - 28 * perf, boy = 22 + 4 * perf;
    const uc = [IX + Math.sin((-aci * Math.PI) / 180) * boy, IY + Math.cos((aci * Math.PI) / 180) * boy];
    if (imp > 0.03) {
      if (perf > 0.05) tagger(svg('ellipse', { cx: f(uc[0] + 3.4), cy: f(uc[1] - 1.5), rx: 5.2, ry: 4.2, class: 'an-kanama', opacity: f(perf * 0.75) }, g), 'hematom');
      const ig = svg('g', { transform: `rotate(${f(aci)},${f(IX)},${f(IY)})`, opacity: f(imp) }, g);
      implantCiz(ig, IX, IY, boy, 1, 1);
      svg('path', { d: poly([[IX - 2.6, IY], [IX + 2.6, IY], [IX + 1.8, IY - 5], [IX - 1.8, IY - 5]]) + ' Z', class: 'an-dayanak' }, ig);
    }

    const yuk = mm2((82.4 - cK) / S3);
    Object.assign(parts, {
      'alt-dudak':      { ad: 'Alt dudak', at: [51.4, 36] },
      orbikularis:      { ad: 'M. orbicularis oris', at: [54.6, 27] },
      'alt-dudak-arteri': { ad: 'A. labialis inferior', at: [56.4, 16.4] },
      mentalis:         { ad: 'M. mentalis', at: [57.4, 60] },
      vestibul:         { ad: 'Vestibül (forniks)', at: [LBs(yF) - p.tG - 0.4, yF] },
      'alveol-mukozasi': { ad: 'Alveol mukozası', at: [gD(MGJ + 3) + 0.5, MGJ + 3], ayrinti: true },
      'b-noktasi':      { ad: 'Supramental çukurluk (B noktası)', at: [LBs(50), 50], ayrinti: true },
      pogonion:         { ad: 'Pogonion (çene ucu)', at: [62.7, 69] },
      menton:           { ad: 'Menton', at: [72, 81.8], ayrinti: true },
      kortikal:         { ad: 'Alt kenar korteksi', at: [78, 82.3] },
      kemik:            { ad: `Simfiz yüksekliği ≈ ${yuk} mm`, at: [78, 70] },
      'insisiv-kanal':  { ad: 'Mandibular insisiv kanal', at: [75.4, 61] },
      'lingual-foramen': { ad: 'Lingual foramen ve kanalı', at: [89, 57.9] },
      'genial-tuberkul': { ad: 'Spina mentalis', at: [93, 64] },
      'sublingual-arter': { ad: 'A. sublingualis', at: [100, 54.6] },
      'submental-arter': { ad: 'A. submentalis', at: [98, 81.8] },
      genioglossus:     { ad: 'M. genioglossus', at: [104, 53], ayrinti: true },
      geniohyoid:       { ad: 'M. geniohyoideus', at: [104, 70] },
      'sublingual-bez': { ad: 'Sublingual bez', at: [94, 46.6] },
      'agiz-tabani':    { ad: 'Ağız tabanı', at: [98, 40.6] },
      dil:              { ad: 'Dil', at: [98, 20] }
    });
    parts.genioglossus = { ad: 'M. genioglossus', at: [106, 50] };
    if (dis > 0.5) {
      Object.assign(parts, {
        mine:  { ad: 'Mine', at: [64.4, 14] },
        pulpa: { ad: 'Pulpa', at: [71.6, 30] },
        kok:   { ad: 'Alt orta kesici kökü', at: [77.4, 38] },
        'labial-kemik': { ad: `Labial kemik plağı ≈ ${mm2(p.tB / S3)} mm`, at: [LBs(36) + 0.2, 36] },
        'lingual-kemik': { ad: 'Lingual kemik plağı', at: [LS(36) - 0.6, 36] },
        'dis-eti': { ad: 'Dişeti', at: [gD(yM + 4) + 0.6, yM + 4] }
      });
    } else {
      parts.kret = { ad: p.at > 7 ? 'Atrofik kret' : 'Alveol kreti', at: [kM[0], kM[1]] };
      if (imp > 0.5) {
        parts.implant = { ad: perf > 0.5 ? 'İmplant lingual korteksi deliyor' : 'İmplant (simfiz eksenine uygun)', at: [(IX + uc[0]) / 2, (IY + uc[1]) / 2] };
        if (perf > 0.5) parts.hematom = { ad: 'Ağız tabanı hematomu riski', at: [uc[0] + 3.4, uc[1] - 1.5] };
        else parts.guvenlik = { ad: 'Lingual kortekse güvenli mesafe', at: [(uc[0] + LS(uc[1])) / 2, uc[1]] };
      }
    }
    return parts;
  }

  Object.assign(AT.anatomi.SABLONLAR, {
    sinus: { ad: 'Maksiller sinüs ve üst azı bölgesi (koronal)', varyantlar: Object.keys(SINUS_DURUM), durumlar: SINUS_DURUM, ciz: sinusCiz, varsayilan: {} },
    mandibula: { ad: 'Mandibula, mandibular kanal ve komşuluklar (koronal)', varyantlar: Object.keys(MAND_DURUM), durumlar: MAND_DURUM, ciz: mandCiz, varsayilan: {} },
    furkasyon: { ad: 'Furkasyon (alt birinci büyük azı)', varyantlar: Object.keys(FUR_DURUM), durumlar: FUR_DURUM, ciz: furCiz, varsayilan: {} },
    'furkasyon-ust': { ad: 'Furkasyon (üst birinci büyük azı)', varyantlar: Object.keys(FURU_DURUM), durumlar: FURU_DURUM, ciz: furUstCiz, varsayilan: {} },
    soket: { ad: 'Çekim soketinin iyileşmesi', varyantlar: Object.keys(SOKET_DURUM), durumlar: SOKET_DURUM, ciz: soketCiz, varsayilan: {} },
    'kemik-ici': { ad: 'Kemik içi defektler (duvar sayısı)', varyantlar: Object.keys(KID_DURUM), durumlar: KID_DURUM, ciz: kemikIciCiz, varsayilan: {} },
    cekilme: { ad: 'Dişeti çekilmesi (Cairo) ve papilla', varyantlar: Object.keys(CEK_DURUM), durumlar: CEK_DURUM, ciz: cekilmeCiz, varsayilan: {} },
    'plak-indeksi': { ad: 'Plak indeksleri (Silness–Löe, Quigley–Hein)', varyantlar: Object.keys(PLAK_DURUM), durumlar: PLAK_DURUM, ciz: (g, v, o) => onYuzCiz(g, v, o, PLAK_DURUM), varsayilan: {} },
    'gingival-indeks': { ad: 'Gingival indeks (Löe–Silness)', varyantlar: Object.keys(GI_DURUM), durumlar: GI_DURUM, ciz: (g, v, o) => onYuzCiz(g, v, o, GI_DURUM), varsayilan: {} },
    'kayit-cizelgesi': { ad: 'Plak (O’Leary) ve kanama (BOP) kayıt çizelgesi', varyantlar: Object.keys(KAYIT_DURUM), durumlar: KAYIT_DURUM, ciz: kayitCiz, varsayilan: {} },
    'on-maksilla': { ad: 'Ön maksilla ve dişeti fenotipi (sagital)', varyantlar: Object.keys(OM_DURUM), durumlar: OM_DURUM, ciz: onMaksillaCiz, varsayilan: {} },
    'on-mandibula': { ad: 'Ön mandibula, simfiz ve ağız tabanı (sagital)', varyantlar: Object.keys(AM_DURUM), durumlar: AM_DURUM, ciz: onMandibulaCiz, varsayilan: {} }
  });
})(window.AT = window.AT || {});
