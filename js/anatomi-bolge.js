/* Bölgesel anatomik şablonlar: çene kemikleri, maksiller sinüs, sinirler ve damarlar.
 * anatomi.js'ten sonra yüklenir ve şablonlarını AT.anatomi.SABLONLAR'a ekler.
 * Ölçek: 160 × 90 tuval, 1,4 birim = 1 mm (diş/implant şablonundan küçük: daha geniş bölge görünür).
 * Koronal kesit; bukkal (yanak) taraf solda, orta hat sağda.
 * Görseller hiçbir atlastan kopyalanmadı; bilinen anatomik ölçülerle sıfırdan çizildi. */
(function (AT) {
  'use strict';
  if (!AT.anatomi) return;
  const { svg, smooth, poly, bant, trabekul, range, clamp, f, uid } = AT.anatomi._y;
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

  Object.assign(AT.anatomi.SABLONLAR, {
    sinus: { ad: 'Maksiller sinüs ve üst azı bölgesi (koronal)', varyantlar: Object.keys(SINUS_DURUM), durumlar: SINUS_DURUM, ciz: sinusCiz, varsayilan: {} },
    mandibula: { ad: 'Mandibula, mandibular kanal ve komşuluklar (koronal)', varyantlar: Object.keys(MAND_DURUM), durumlar: MAND_DURUM, ciz: mandCiz, varsayilan: {} },
    furkasyon: { ad: 'Furkasyon (alt birinci büyük azı)', varyantlar: Object.keys(FUR_DURUM), durumlar: FUR_DURUM, ciz: furCiz, varsayilan: {} },
    'furkasyon-ust': { ad: 'Furkasyon (üst birinci büyük azı)', varyantlar: Object.keys(FURU_DURUM), durumlar: FURU_DURUM, ciz: furUstCiz, varsayilan: {} }
  });
})(window.AT = window.AT || {});
