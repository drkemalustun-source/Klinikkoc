/* KlinikKoç · Ana ekran ("Sihirbaz"). Yerel sunucunun /api/ana/, /api/makale/ isteklerini kullanır (tools/sunucu.py).
   Yan düğmeler paneli değiştirir; sayfa aşağı uzamaz, uzun listeler panelin içinde kayar. */
(function () {
  'use strict';
  const $ = (s) => document.querySelector(s);
  const KENDI = 'kendi-makalelerim';
  const IKON = {
    liste: '<path d="M5 7h14M5 12h14M5 17h9"/>',
    paket: '<path d="M12 15V5M8 9l4-4 4 4M5 15v4h14v-4"/>',
    pdf: '<path d="M7 3h7l4 4v14H7zM14 3v4h4M10 12h5M10 16h5"/>',
    ara: '<circle cx="11" cy="11" r="6"/><path d="M20 20l-4.5-4.5"/>',
    tamam: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    kalem: '<path d="M4 20l1-4L16 5l3 3L8 19zM14 7l3 3"/>',
    zarf: '<rect x="3" y="6" width="18" height="12" rx="2"/><path d="M4 8l8 6 8-6"/>',
    sekil: '<path d="M8 4c2-1 6-1 8 0 2 4 0 8-1 11-.5 2-.5 5-2 5s-1-4-1-4-.5 4-2 4-1.5-3-2-5C7 12 6 8 8 4z"/>',
    oynat: '<path d="M8 5l11 7-11 7z"/>',
  };
  const ikon = (ad) => `<svg viewBox="0 0 24 24" aria-hidden="true">${IKON[ad] || ''}</svg>`;
  const BOLUMLER = [
    { id: 'derslerim', ad: 'Derslerim', alt: 'Seç ve çalış', ikon: 'liste', renk: '#6f95c9', panel: 'mavi' },
    { id: 'paket', ad: 'Ders paketi ekle', alt: '.zip dosyası', ikon: 'paket', renk: '#6f95c9', panel: 'mavi' },
    { id: 'pdf', ad: 'Kendi PDF\'lerim', alt: 'Birden çok PDF', ikon: 'pdf', renk: '#d08a5c', panel: 'toprak' },
    { id: 'makale', ad: 'Makale yardımcısı', alt: 'DOI ile indir', ikon: 'ara', renk: '#d08a5c', panel: 'mavi' },
    { ayrac: true },
    { id: 'rapor', ad: 'Raporlarım', alt: 'Tamamlama, tekrar, arşiv', ikon: 'tamam', renk: '#6fa082', panel: 'adacayi' },
    { id: 'sablon', ad: 'Çizim şablonları', alt: 'Tahtadaki hazır çizimler', ikon: 'sekil', renk: '#6fa082', panel: 'adacayi' },
    { id: 'geribildirim', ad: 'Geri bildirim', alt: 'Programa öneriler', ikon: 'zarf', renk: '#c9973e', panel: 'okre' },
    { ayrac: true, ogretmen: true, baslik: 'Öğretmen' },
    { id: 'hazirla', ad: 'Ders hazırla', alt: 'Yeni ders paketi', ikon: 'kalem', renk: '#E06826', panel: 'fildisi', ogretmen: true },
  ];
  let OZ = null;                 // /api/ana/ozet
  let panel = 'derslerim';
  const secili = { dersler: new Set(), pdfler: new Set() };
  let makaleDers = '';
  let pdfHedef = KENDI;
  let zamanlayici = null;
  const pdfKuyruk = [];          // {ad, durum: sirada|okunuyor|hazir|hata, not}

  // ---------- yardımcılar ----------
  function el(etiket, ozellik, ...cocuk) {
    const e = document.createElement(etiket);
    for (const [k, v] of Object.entries(ozellik || {})) {
      if (v === undefined || v === null || v === false) continue;
      if (k === 'class') e.className = v;
      else if (k === 'html') e.innerHTML = v;
      else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
      else if (v === true) e.setAttribute(k, '');
      else e.setAttribute(k, v);
    }
    for (const c of cocuk.flat()) if (c !== null && c !== undefined && c !== false) e.append(c.nodeType ? c : String(c));
    return e;
  }
  const kure = (ad, renk) => el('span', { class: 'k-kure', style: `--c:${renk}`, html: ikon(ad) });
  const sayiKure = (n, renk) => el('span', { class: 'k-kure', style: `--c:${renk}` }, String(n));
  async function api(yol, govde, ham) {
    const sec = govde === undefined ? {} : { method: 'POST', body: ham ? govde : JSON.stringify(govde) };
    const y = await fetch('/api/' + yol, sec);
    let v = {};
    try { v = await y.json(); } catch (e) { /* boş gövde */ }
    if (!y.ok) throw Object.assign(new Error(v.hata || ('HTTP ' + y.status)), { kod: y.status });
    return v;
  }
  function birakmaAlani(alan, girdi, isle) {
    alan.addEventListener('dragover', (e) => { e.preventDefault(); alan.classList.add('ustunde'); });
    alan.addEventListener('dragleave', () => alan.classList.remove('ustunde'));
    alan.addEventListener('drop', (e) => { e.preventDefault(); alan.classList.remove('ustunde'); isle([...e.dataTransfer.files]); });
    girdi.addEventListener('change', () => { isle([...girdi.files]); girdi.value = ''; });
  }
  window.addEventListener('dragover', (e) => e.preventDefault());
  window.addEventListener('drop', (e) => e.preventDefault());
  async function kopyala(metin, dugme) {
    try { await navigator.clipboard.writeText(metin); } catch (e) {
      const t = el('textarea', {}, metin); document.body.append(t); t.select();
      try { document.execCommand('copy'); } catch (e2) { /* kopyalanamadı */ }
      t.remove();
    }
    if (dugme) { const eski = dugme.textContent; dugme.textContent = 'Kopyalandı ✓'; setTimeout(() => { dugme.textContent = eski; }, 1600); }
  }
  function pencere(...icerik) {
    const ic = $('#pencereIc'); ic.innerHTML = ''; ic.append(...icerik.flat().filter(Boolean));
    $('#pencere').hidden = false;
    const ilk = ic.querySelector('button, a'); if (ilk) ilk.focus();
  }
  const pencereKapat = () => { $('#pencere').hidden = true; };
  $('#pencere').addEventListener('click', (e) => { if (e.target === $('#pencere')) pencereKapat(); });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') pencereKapat(); });
  const ogretmen = () => OZ && OZ.tur === 'ogretmen';

  // ---------- kabuk ----------
  function yanCiz() {
    const yan = $('#yan'); yan.innerHTML = '';
    for (const b of BOLUMLER) {
      if (b.ogretmen && !ogretmen()) continue;
      if (b.ayrac) { yan.append(el('hr')); if (b.baslik) yan.append(el('div', { class: 'k-yan-baslik' }, b.baslik)); continue; }
      yan.append(el('button', { class: 'k-ydug' + (panel === b.id ? ' secili' : ''), type: 'button', 'aria-current': panel === b.id ? 'page' : null,
        onclick: () => git(b.id) }, kure(b.ikon, b.renk), el('span', {}, b.ad, el('small', {}, b.alt))));
    }
    yan.append(el('div', { class: 'k-yan-alt' }, 'Açık kaynak · ücretsiz · veriler bu bilgisayarda kalır'));
    $('#ustSihirbaz').classList.toggle('etkin', panel !== 'kilavuz');
    $('#ustKilavuz').classList.toggle('etkin', panel === 'kilavuz');
  }
  function git(id, ek) {
    clearTimeout(zamanlayici);
    panel = id;
    try { history.replaceState(null, '', '#' + id); } catch (e) { /* dosyadan açıldı */ }
    yanCiz();
    const p = $('#panel');
    p.innerHTML = '';
    const b = BOLUMLER.find((x) => x.id === id);
    p.dataset.renk = id === 'kilavuz' ? 'fildisi' : (b && b.panel) || 'mavi';
    (PANELLER[id] || PANELLER.derslerim)(p, ek);
  }
  function baslik(p, ad, alt) { const h = el('header', {}, el('h1', {}, ad), alt ? el('span', {}, alt) : null); p.append(h); return h; }
  function cerceve(p, adres, ad) { const f = el('iframe', { class: 'k-cerceve', src: adres, title: ad }); p.append(f); return f; }

  async function ozetYukle() {
    try { OZ = await api('ana/ozet'); } catch (e) { OZ = OZ || { hata: e.message, dersler: [], pdfler: [], secim: {}, tur: 'ogrenci' }; }
    $('#surum').textContent = OZ.surum || '';
    const r = $('#rozet');
    r.textContent = ogretmen() ? 'Öğretmen sürümü' : 'Öğrenci sürümü';
    r.classList.toggle('ogretmen', ogretmen());
    const g = OZ.guncelleme || {};
    $('#guncelle').hidden = !(g.var && !g.gelistirici);
    $('#guncelleSurum').textContent = g.yeni_surum || '';
    const ou = $('#ortakUyari'), od = OZ.ortak || {};
    ou.hidden = !od.uyari;
    ou.innerHTML = '';
    if (od.uyari) ou.append(el('b', {}, 'Ortak klasör: '), od.uyari);
    return OZ;
  }

  // ---------- Derslerim ----------
  function derslerim(p) {
    baslik(p, 'Derslerim', 'Çalışmak istediklerinizi işaretleyin');
    const kutu = el('div', { class: 'k-kaydir' });
    const alt = el('div', { class: 'k-alt' });
    p.append(kutu, alt);
    if (OZ.hata) {
      kutu.append(el('div', { class: 'k-bos' }, el('b', {}, 'KlinikKoç\'a ulaşılamadı'),
        'Bu sayfa KlinikKoç açıkken çalışır. Program klasöründeki BASLAT dosyasına çift tıklayın ya da Claude\'a "KlinikKoç\'u aç" deyin.'));
      return;
    }
    const RENK = ['#E06826', '#3f8a63', '#c9973e', '#6f95c9', '#d08a5c', '#6fa082'];
    const guncelle = () => {
      const n = secili.dersler.size + secili.pdfler.size;
      yazi.innerHTML = '';
      yazi.append(el('b', {}, n ? `${n} konu seçili. ` : 'Henüz seçim yok. '),
        n ? 'Claude dersi bunlardan anlatır, sorularını bunlardan sorar. '
          : 'Bir ya da birkaç ders ya da PDF işaretleyin. ',
        el('span', { class: 'k-soluk' }, 'Claude\'a “… dersini aç” demeniz de yeter.'));
      calis.disabled = !n;
    };
    const satir = (tur, kimlik, sol, orta, sag) => {
      const k = el('input', { type: 'checkbox', class: 'k-kutu', 'aria-label': 'Seç' });
      k.checked = secili[tur].has(kimlik);
      k.addEventListener('change', () => { if (k.checked) secili[tur].add(kimlik); else secili[tur].delete(kimlik); guncelle(); });
      return el('label', { class: 'k-satir' }, k, sol, el('div', { class: 'k-orta' }, orta), el('div', { class: 'k-sag' }, sag));
    };
    kutu.append(el('div', { class: 'k-bolum' }, 'Ders paketleri'));
    if (!OZ.dersler.length) {
      kutu.append(el('div', { class: 'k-bos' }, el('b', {}, 'Henüz ders yok'),
        'Öğretmeninizin verdiği ders paketini (.zip) ekleyin. ', el('button', { class: 'k-btn kucuk', onclick: () => git('paket') }, 'Ders paketi ekle')));
    }
    OZ.dersler.forEach((d, i) => {
      const parca = [d.egitmen, d.hedef ? `${d.hedef} hedef` : null, d.vaka ? `${d.vaka} vaka` : null,
        d.makale.toplam ? `${d.makale.hazir}/${d.makale.toplam} makale hazır` : null, d.sure_dk ? `${d.sure_dk} dk` : null].filter(Boolean).join(' · ');
      const sag = [];
      if (d.makale.toplam && d.makale.hazir < d.makale.toplam) {
        sag.push(el('button', { class: 'k-btn kucuk sade', type: 'button', onclick: (e) => { e.preventDefault(); makaleDers = d.ders; git('makale'); } }, 'Makaleler'));
      }
      if (d.kayitli_anlatim) sag.push(el('a', { class: 'k-btn kucuk sade', href: 'index.html?ders=' + encodeURIComponent(d.ders), title: 'Hazır sesli anlatımı Claude olmadan oynatır' }, 'Kayıtlı anlatım'));
      sag.push(el('span', { class: 'k-etiket' + (d.tamamlandi ? ' iyi' : '') }, d.tamamlandi ? 'bitirildi' : d.oturum ? `%${d.ilerleme}` : 'yeni'));
      sag.push(el('div', { class: 'k-cubuk', title: `İlerleme %${d.ilerleme}` }, el('i', { style: `width:${d.ilerleme}%` })));
      kutu.append(satir('dersler', d.ders, sayiKure(i + 1, RENK[i % RENK.length]),
        [el('b', {}, d.baslik), d.ozel ? el('span', { class: 'k-etiket mavi', style: 'margin-left:8px' }, 'fakülte') : null,
          el('div', { class: 'k-alt-yazi' }, parca || 'Ders paketi')], sag));
    });
    kutu.append(el('div', { class: 'k-bolum' }, 'Kendi PDF\'lerim'));
    const hazirPdf = OZ.pdfler.filter((x) => x.durum === 'hazir');
    if (!hazirPdf.length) {
      kutu.append(el('div', { class: 'k-bos' }, 'Kendi makalenizden ya da notunuzdan çalışmak için PDF ekleyin. ',
        el('button', { class: 'k-btn kucuk sade', onclick: () => git('pdf') }, 'PDF ekle')));
    }
    for (const m of hazirPdf) {
      kutu.append(satir('pdfler', m.id, kure('pdf', '#d08a5c'),
        [el('b', {}, m.baslik), el('div', { class: 'k-alt-yazi' }, ['Kendi makalelerim', m.sayfa ? `${m.sayfa} sayfa` : null].filter(Boolean).join(' · '))], []));
    }
    const yazi = el('div', { class: 'k-yazi' });
    const calis = el('button', { class: 'k-btn buyuk', type: 'button', html: ikon('oynat').replace('<svg', '<svg width="18" height="18" fill="currentColor"') + ' Seçilenlerle çalış', onclick: calismayaBasla });
    alt.append(yazi);
    if (OZ.tekrar_karti) alt.append(el('button', { class: 'k-btn sade', type: 'button', onclick: () => tekrarPenceresi() }, `Tekrar kartları (${OZ.tekrar_karti})`));
    alt.append(calis);
    guncelle();
  }
  function tekrarPenceresi() {
    const cumle = 'Bugünkü tekrar kartlarımı soralım.';
    pencere(el('h2', {}, 'Tekrar kartları'),
      el('p', {}, `Zamanı gelen ${OZ.tekrar_karti} tekrar kartınız var. Kartlar, zorlandığınız sorulardan oluşur ve Claude tarafından sorulur.`),
      el('p', {}, 'Claude masaüstü uygulamasına şunu yazın:'),
      el('div', { class: 'k-claude' }, el('q', {}, cumle), el('button', { class: 'k-btn kucuk sade', onclick: (e) => kopyala(cumle, e.currentTarget) }, 'Kopyala')),
      el('div', { class: 'k-alt' }, el('button', { class: 'k-btn sade', onclick: pencereKapat }, 'Kapat'), el('a', { class: 'k-btn', href: 'canli.html' }, 'Tahtayı aç')));
  }
  async function calismayaBasla() {
    let s;
    try { s = await api('ana/secim', { dersler: [...secili.dersler], pdfler: [...secili.pdfler] }); } catch (e) {
      return pencere(el('h2', {}, 'Seçim kaydedilemedi'), el('p', {}, e.message), el('div', { class: 'k-alt' }, el('button', { class: 'k-btn sade', onclick: pencereKapat }, 'Kapat')));
    }
    OZ.secim = s;
    const cumle = s.claude_cumlesi || 'Seçtiğim konuları çalışalım.';
    pencere(el('h2', {}, 'Seçiminiz hazır'),
      el('p', {}, [...s.ders_adlari, ...s.pdf_adlari].join(' · ')),
      el('p', {}, 'Şimdi Claude masaüstü uygulamasına şunu yazın (ya da yalnızca “seçtiklerimi çalışalım” deyin):'),
      el('div', { class: 'k-claude' }, el('q', {}, cumle), el('button', { class: 'k-btn kucuk sade', onclick: (e) => kopyala(cumle, e.currentTarget) }, 'Kopyala')),
      el('p', { class: 'k-soluk' }, 'Claude seçiminizi kendisi de görür; tahtayı açıp dersi başlatır.'),
      el('div', { class: 'k-alt' }, el('button', { class: 'k-btn sade', onclick: pencereKapat }, 'Seçimi değiştir'),
        el('a', { class: 'k-btn', href: 'canli.html' }, 'Tahtayı aç')));
    kopyala(cumle);
  }

  // ---------- Ders paketi ekle ----------
  function paket(p) {
    baslik(p, 'Ders paketi ekle', 'Öğretmeninizin verdiği .zip dosyası');
    const girdi = el('input', { type: 'file', accept: '.zip,application/zip', multiple: true, hidden: true });
    const alan = el('label', { class: 'k-birak' }, girdi,
      el('div', { class: 'k-yaprak zip' }, el('i'), el('i', {}, 'ZIP'), kure('paket', '#1B367B')),
      el('div', {}, el('strong', {}, 'Ders paketini buraya bırakın'), el('span', { html: 'ya da <u>bilgisayardan seçin</u> · birden çok paket olabilir' })));
    const sonuc = el('div', { class: 'k-kaydir duz' });
    p.append(alan, sonuc,
      el('div', { class: 'k-oyuk k-bilgi' }, el('b', {}, 'Pakette makalelerin kendisi yoktur, yalnız listesi vardır. '),
        'Paket kurulunca KlinikKoç açık erişimli makaleleri kendisi indirir; geri kalanlar için ', el('b', {}, 'Makale yardımcısı'), ' size yol gösterir.'),
      el('div', { class: 'k-alt', style: 'justify-content:flex-end' }, el('button', { class: 'k-btn mavi', onclick: () => git('derslerim') }, 'Derslerime git ›')));
    async function kur(dosya, uzerine, satir) {
      satir = satir || sonuc.appendChild(el('div', { class: 'k-satir' }));
      satir.innerHTML = '';
      satir.append(kure('paket', '#6f95c9'), el('div', { class: 'k-orta' }, el('b', {}, dosya.name), el('div', { class: 'k-alt-yazi' }, 'Kuruluyor…')),
        el('div', { class: 'k-sag' }, el('div', { class: 'k-cubuk turuncu akan' }, el('i'))));
      try {
        const v = await api('makale/paket' + (uzerine ? '?uzerine=1' : ''), dosya, true);
        satir.innerHTML = '';
        satir.append(kure('tamam', '#4f8a66'), el('div', { class: 'k-orta' }, el('b', {}, v.baslik),
          el('div', { class: 'k-alt-yazi' }, v.makale ? `Kuruldu · ${v.makale} makale aranıyor` : 'Kuruldu')),
        el('div', { class: 'k-sag' }, v.makale ? el('button', { class: 'k-btn kucuk sade', onclick: () => { makaleDers = v.ders; git('makale'); } }, 'Makaleleri gör') : null,
          el('span', { class: 'k-etiket iyi' }, 'hazır')));
        secili.dersler.add(v.ders);
        await ozetYukle();
      } catch (e) {
        satir.innerHTML = '';
        satir.append(kure('paket', '#b3401a'), el('div', { class: 'k-orta' }, el('b', {}, dosya.name), el('div', { class: 'k-alt-yazi' }, e.message)),
          el('div', { class: 'k-sag' }, e.kod === 409 ? el('button', { class: 'k-btn kucuk', onclick: () => kur(dosya, true, satir) }, 'Üzerine kur (güncelle)') : el('span', { class: 'k-etiket kotu' }, 'kurulamadı')));
      }
    }
    birakmaAlani(alan, girdi, (dosyalar) => dosyalar.forEach((f) => kur(f, false)));
  }

  // ---------- Kendi PDF'lerim ----------
  function pdf(p) {
    baslik(p, 'Kendi PDF\'lerim', 'Elinizdeki makaleleri ve notları ekleyin');
    const girdi = el('input', { type: 'file', accept: '.pdf,application/pdf', multiple: true, hidden: true });
    const alan = el('label', { class: 'k-birak' }, girdi,
      el('div', { class: 'k-yaprak' }, el('i'), el('i', {}, 'PDF'), kure('paket', '#1B367B')),
      el('div', {}, el('strong', {}, 'PDF\'leri buraya bırakın'), el('span', { html: 'Birden çok dosya seçebilirsiniz · ya da <u>bilgisayardan seçin</u>' })));
    const sec = el('select', { class: 'k-alan', 'aria-label': 'Hangi derse eklensin' }, el('option', { value: KENDI }, 'Kendi makalelerim (genel kitaplık)'));
    for (const d of OZ.dersler) sec.append(el('option', { value: d.ders }, d.baslik));
    sec.value = pdfHedef;
    sec.addEventListener('change', () => { pdfHedef = sec.value; listele(); });
    const liste = el('div', { class: 'k-kaydir duz' });
    p.append(alan, el('div', { class: 'k-alt' }, el('span', { class: 'k-soluk' }, 'Hangi derse eklensin?'), sec,
      el('span', { class: 'k-soluk k-yazi' }, 'PDF\'ler yalnız bu bilgisayarda kalır; hiçbir pakete girmez.')), liste,
    el('div', { class: 'k-alt', style: 'justify-content:flex-end' },
      el('button', { class: 'k-btn sade', onclick: () => api('makale/klasor_ac', { ders: pdfHedef === KENDI ? KENDI : pdfHedef }).catch(() => {}) }, 'Klasörü aç'),
      el('button', { class: 'k-btn mavi', onclick: () => git('derslerim') }, 'Derslerime git ›')));
    let kayitli = [];
    async function listele() {
      try { kayitli = (await api('makale/durum?ders=' + encodeURIComponent(pdfHedef))).makaleler.filter((m) => m.ogrenci || pdfHedef === KENDI); } catch (e) { kayitli = []; }
      ciz();
    }
    function ciz() {
      liste.innerHTML = '';
      for (const k of pdfKuyruk) {
        const bitti = k.durum === 'hazir' || k.durum === 'hata';
        if (bitti && kayitli.some((m) => m.durum === 'hazir' && k.id === m.id)) continue;
        liste.append(el('div', { class: 'k-satir' }, kure('pdf', k.durum === 'hata' ? '#b3401a' : '#d08a5c'),
          el('div', { class: 'k-orta' }, el('b', {}, k.ad), el('div', { class: 'k-alt-yazi' }, k.not || (k.durum === 'sirada' ? 'Sırada' : 'Metin çıkarılıyor…'))),
          el('div', { class: 'k-sag' }, k.durum === 'hata' ? el('span', { class: 'k-etiket kotu' }, 'eklenemedi')
            : el('div', { class: 'k-cubuk turuncu' + (k.durum === 'okunuyor' ? ' akan' : '') }, el('i', { style: k.durum === 'sirada' ? 'width:0' : null })))));
      }
      for (const m of kayitli) {
        liste.append(el('div', { class: 'k-satir' }, kure('pdf', '#d08a5c'),
          el('div', { class: 'k-orta' }, el('b', {}, m.kisa || m.id), el('div', { class: 'k-alt-yazi' },
            m.durum === 'hazir' ? [m.sayfa ? `${m.sayfa} sayfa okundu` : null, m.atif].filter(Boolean).join(' · ') : (m.neden || 'Okunamadı'))),
          el('div', { class: 'k-sag' }, el('span', { class: 'k-etiket ' + (m.durum === 'hazir' ? 'iyi' : 'kotu') }, m.durum === 'hazir' ? '✓ hazır' : 'okunamadı'),
            el('button', { class: 'k-btn kucuk sade', title: 'Listeden çıkarır; dosya klasörde kalır', onclick: async () => {
              try { await api('makale/kaldir', { ders: pdfHedef, id: m.id }); } catch (e) { /* liste yenilenir */ }
              await ozetYukle(); listele();
            } }, 'Çıkar'))));
      }
      if (!liste.children.length) liste.append(el('div', { class: 'k-bos' }, 'Bu listede henüz PDF yok.'));
    }
    let calisiyor = false;
    async function kuyruguIsle() {
      if (calisiyor) return;
      calisiyor = true;
      for (const k of pdfKuyruk) {
        if (k.durum !== 'sirada') continue;
        k.durum = 'okunuyor'; ciz();
        try {
          const v = await api('makale/ekle?' + new URLSearchParams({ ders: k.hedef, ad: k.ad }), k.dosya, true);
          k.id = v.id;
          if (v.durum === 'hazir') { k.durum = 'hazir'; k.not = `${v.sayfa} sayfa okundu`; if (k.hedef === KENDI) secili.pdfler.add(v.id); }
          else { k.durum = 'hata'; k.not = v.neden || 'Okunamadı'; }
        } catch (e) { k.durum = 'hata'; k.not = e.message; }
        k.dosya = null;
        await listele();
      }
      calisiyor = false;
      ozetYukle();
    }
    birakmaAlani(alan, girdi, (dosyalar) => {
      for (const f of dosyalar) {
        if (!/\.pdf$/i.test(f.name) && f.type !== 'application/pdf') { pdfKuyruk.unshift({ ad: f.name, durum: 'hata', not: 'Bu dosya PDF değil.' }); continue; }
        pdfKuyruk.push({ ad: f.name, dosya: f, hedef: pdfHedef, durum: 'sirada' });
      }
      ciz(); kuyruguIsle();
    });
    listele();
  }

  // ---------- Makale yardımcısı ----------
  function makale(p) {
    const h = baslik(p, 'Makale yardımcısı');
    const dersli = OZ.dersler.filter((d) => d.makale.toplam);
    if (!dersli.length) {
      p.append(el('div', { class: 'k-kaydir' }, el('div', { class: 'k-bos' }, el('b', {}, 'Makale listesi olan bir ders yok'),
        'Ders paketi eklediğinizde, o dersin makaleleri burada görünür ve indirilir. ',
        el('button', { class: 'k-btn kucuk', onclick: () => git('paket') }, 'Ders paketi ekle'))));
      return;
    }
    if (!dersli.some((d) => d.ders === makaleDers)) makaleDers = dersli[0].ders;
    const sec = el('select', { class: 'k-alan', 'aria-label': 'Ders' });
    for (const d of dersli) sec.append(el('option', { value: d.ders }, `${d.baslik} · ${d.makale.toplam} makale`));
    sec.value = makaleDers;
    sec.addEventListener('change', () => { makaleDers = sec.value; yukle(); });
    h.append(sec);
    const ozet = el('div', { class: 'k-ozet' });
    const liste = el('div', { class: 'k-kaydir duz' });
    const mesaj = el('div', { class: 'k-mesaj k-yazi' });
    const dene = el('button', { class: 'k-btn', type: 'button', onclick: async () => {
      try { await api('makale/hazirla', { ders: makaleDers }); mesaj.className = 'k-mesaj k-yazi'; mesaj.textContent = 'Makaleler aranıyor…'; } catch (e) { mesaj.className = 'k-mesaj k-yazi kotu'; mesaj.textContent = e.message; }
      yukle();
    } }, '⟳ Hepsini dene');
    const kunye = el('button', { class: 'k-btn sade', type: 'button' }, 'Künyeleri kopyala');
    p.append(ozet, liste,
      el('div', { class: 'k-oyuk k-bilgi' }, el('b', {}, 'İndirdiğiniz PDF\'i İndirilenler klasörüne kaydetmeniz yeter. '),
        'Yardımcı o klasöre bakar, dosyayı DOI\'sinden ya da başlığından tanır ve doğru makalenin yerine kendisi koyar. Abonelikli dergiler yalnız okul ağında (eduroam ya da VPN) iner; KlinikKoç hiçbir şifre kullanmaz.'),
      el('div', { class: 'k-alt' }, mesaj, el('button', { class: 'k-btn sade', onclick: () => api('makale/klasor_ac', { ders: makaleDers }).catch(() => {}) }, 'Klasörü aç'), kunye, dene));
    let son = null;
    kunye.addEventListener('click', () => son && kopyala(son.makaleler.map((m, i) => `${i + 1}. ${m.atif || m.kisa}${m.doi ? ' https://doi.org/' + m.doi : ''}`).join('\n'), kunye));
    async function yukle() {
      let o;
      try { o = await api('makale/durum?ders=' + encodeURIComponent(makaleDers)); } catch (e) { mesaj.className = 'k-mesaj k-yazi kotu'; mesaj.textContent = e.message; return; }
      if (panel !== 'makale') return;
      son = o;
      const hazir = o.makaleler.filter((m) => m.durum === 'hazir').length;
      const agda = o.makaleler.filter((m) => m.durum !== 'hazir' && m.doi).length;
      const elle = o.makaleler.filter((m) => m.durum !== 'hazir' && !m.doi).length;
      ozet.innerHTML = '';
      ozet.append(el('div', { style: 'background:#e2efe6' }, el('b', { style: 'color:#2f6b47' }, hazir), 'makale hazır'),
        el('div', { style: 'background:#f6ead2' }, el('b', { style: 'color:#9a6a16' }, agda), o.calisiyor ? 'aranıyor…' : 'yayıncıdan indirilebilir (okul ağı gerekebilir)'),
        el('div', { style: 'background:#f5dcd1' }, el('b', { style: 'color:#a8461a' }, elle), 'elle eklenmeli (DOI yok)'));
      liste.innerHTML = '';
      o.makaleler.forEach((m, i) => {
        const hz = m.durum === 'hazir';
        const NEREDEN = { paket: 'ders paketiyle geldi', klasor: 'makale klasöründe vardı', 'acik-erisim': 'açık erişimden indi', universite: 'yayıncıdan indi', elle: 'siz eklediniz', ders: 'dersin kendi metni' };
        const sag = [el('span', { class: 'k-etiket ' + (hz ? 'iyi' : m.doi ? 'uyari' : 'kotu') },
          hz ? '✓ hazır' : o.calisiyor && m.durum === 'denenmedi' ? 'aranıyor' : m.doi ? 'siz indirin' : 'elle ekleyin')];
        if (!hz && m.sayfa_adresi) sag.push(el('a', { class: 'k-btn kucuk', href: m.sayfa_adresi, target: '_blank', rel: 'noopener', onclick: () => taramayiBaslat() }, 'Yayıncıda aç ↗'));
        const g = el('input', { type: 'file', accept: '.pdf,application/pdf', hidden: true });
        g.addEventListener('change', async () => {
          if (!g.files[0]) return;
          mesaj.className = 'k-mesaj k-yazi'; mesaj.textContent = `${g.files[0].name} okunuyor…`;
          try {
            const v = await api('makale/ekle?' + new URLSearchParams({ ders: makaleDers, ad: g.files[0].name, kaynak: m.id }), g.files[0], true);
            mesaj.className = 'k-mesaj k-yazi ' + (v.durum === 'hazir' ? 'iyi' : 'kotu');
            mesaj.textContent = v.durum === 'hazir' ? `“${v.kisa}” eklendi (${v.sayfa} sayfa).` : (v.neden || 'Okunamadı');
          } catch (e) { mesaj.className = 'k-mesaj k-yazi kotu'; mesaj.textContent = e.message; }
          await ozetYukle(); yukle();
        });
        if (!hz || m.ogrenci) sag.push(el('label', { class: 'k-btn kucuk ' + (hz ? 'sade' : 'mavi') }, g, hz ? 'PDF\'i değiştir' : 'PDF seç…'));
        liste.append(el('div', { class: 'k-satir' }, sayiKure(i + 1, hz ? '#3f8a63' : m.doi ? '#c9973e' : '#d08a5c'),
          el('div', { class: 'k-orta' }, el('b', {}, m.kisa || m.id), m.rol === 'ana' ? el('span', { class: 'k-etiket mavi', style: 'margin-left:8px' }, 'ana kaynak') : null,
            el('div', { class: 'k-alt-yazi' }, m.atif || (m.doi ? 'doi:' + m.doi : '')),
            el('div', { class: 'k-alt-yazi' }, hz ? [NEREDEN[m.nereden], m.sayfa ? `${m.sayfa} sayfa okundu` : null].filter(Boolean).join(' · ') : (m.neden || ''))),
          el('div', { class: 'k-sag' }, sag)));
      });
      dene.disabled = !!o.calisiyor || hazir === o.makaleler.length;
      if (o.sekiller) mesaj.textContent = mesaj.textContent || `Makaleden şekil: ${o.sekiller.hazir}/${o.sekiller.toplam}`;
      clearTimeout(zamanlayici);
      if (o.calisiyor) zamanlayici = setTimeout(yukle, 2500);
      else if (hazir < o.makaleler.length && tarama > 0) zamanlayici = setTimeout(tara, 6000);
    }
    let tarama = 0;   // "Yayıncıda aç"a basıldıktan sonra İndirilenler klasörüne birkaç dakika bakılır
    function taramayiBaslat() { tarama = 40; clearTimeout(zamanlayici); zamanlayici = setTimeout(tara, 6000); }
    async function tara() {
      if (panel !== 'makale') return;
      tarama -= 1;
      try {
        const r = await api('makale/tara', { ders: makaleDers });
        if (r.eklenen && r.eklenen.length) {
          mesaj.className = 'k-mesaj k-yazi iyi';
          mesaj.textContent = 'İndirilenler\'den eklendi: ' + r.eklenen.map((x) => x.kisa).join(', ');
          await ozetYukle();
        }
      } catch (e) { /* tarama sessizdir */ }
      yukle();
    }
    tarama = 2;   // panel açılınca bir kez bakılır: önceden indirilmiş olabilir
    yukle();
  }

  // ---------- Raporlarım ----------
  function rapor(p, ek) {
    const h = baslik(p, 'Raporlarım');
    const sekmeler = el('div', { class: 'k-alt' });
    const govde = el('div', { style: 'flex:1;min-height:0;display:flex;flex-direction:column;gap:12px' });
    p.append(sekmeler, govde);
    const goster = (hangi) => {
      [...sekmeler.children].forEach((b) => b.classList.toggle('sade', b.dataset.id !== hangi));
      govde.innerHTML = '';
      if (hangi === 'arsiv') cerceve(govde, 'makaleler.html?gomulu=1&bolum=depolama', 'Depolama ve arşiv');
      else if (hangi === 'ortak') ortakKlasor(govde);
      else if (hangi === 'form') {
        const dl = OZ.dersler;
        if (!dl.length) { govde.append(el('div', { class: 'k-kaydir' }, el('div', { class: 'k-bos' }, 'Değerlendirme formu için önce bir ders gerekir.'))); return; }
        const sec = el('select', { class: 'k-alan' }, dl.map((d) => el('option', { value: d.ders }, d.baslik)));
        const f = el('iframe', { class: 'k-cerceve', title: 'Ders değerlendirme formu' });
        const ac = () => { f.src = 'degerlendirme.html?gomulu=1&ders=' + encodeURIComponent(sec.value); };
        sec.addEventListener('change', ac);
        govde.append(el('div', { class: 'k-alt' }, el('span', { class: 'k-soluk' }, 'Ders:'), sec), f);
        ac();
      } else {
        const kutu = el('div', { class: 'k-kaydir' });
        govde.append(kutu);
        if (!OZ.dersler.length) kutu.append(el('div', { class: 'k-bos' }, el('b', {}, 'Henüz rapor yok'), 'Bir dersi çalıştıkça ilerlemeniz burada görünür.'));
        for (const d of OZ.dersler) {
          const cumle = `${d.baslik} dersi için ${d.tamamlandi ? 'tamamlama raporumu göster' : 'karnemi göster'}.`;
          kutu.append(el('div', { class: 'k-satir' }, kure('tamam', d.tamamlandi ? '#4f8a66' : '#c9bfae'),
            el('div', { class: 'k-orta' }, el('b', {}, d.baslik), el('div', { class: 'k-alt-yazi' },
              d.tamamlandi ? 'Ders bitirildi · tamamlama raporu hazır' : d.oturum ? `${d.oturum} oturum · hedeflerin %${d.ilerleme}'i ele alındı` : 'Henüz çalışılmadı')),
            el('div', { class: 'k-sag' }, el('div', { class: 'k-cubuk' }, el('i', { style: `width:${d.ilerleme}%` })),
              d.oturum ? el('button', { class: 'k-btn kucuk sade', title: 'Claude\'a söylenecek cümleyi kopyalar', onclick: (e) => kopyala(cumle, e.currentTarget) }, 'Claude\'dan iste') : null,
              el('button', { class: 'k-btn kucuk sade', onclick: () => { goster('form'); govde.querySelector('select').value = d.ders; govde.querySelector('select').dispatchEvent(new Event('change')); } }, 'Değerlendir'))));
        }
        kutu.append(el('div', { class: 'k-oyuk k-bilgi', style: 'margin-top:10px' }, 'Karne ve tamamlama raporunu Claude hazırlar: “karnemi göster” ya da “dersi bitirelim” demeniz yeter. ',
          'Raporlar yalnız bu bilgisayarda durur ve not için değil, kendinizi görmeniz içindir.'));
      }
    };
    for (const [id, ad] of [['ilerleme', 'İlerlemem'], ['form', 'Ders değerlendirme formu'], ['arsiv', 'Depolama ve arşiv'], ['ortak', 'İki bilgisayarda çalışma']]) {
      sekmeler.append(el('button', { class: 'k-btn kucuk mavi', 'data-id': id, type: 'button', onclick: () => goster(id) }, ad));
    }
    h.append(el('span', {}, 'İlerleme, değerlendirme ve arşiv'));
    goster(ek || 'ilerleme');
  }

  // ---------- İki bilgisayarda çalışma: ortak (bulut) klasör ----------
  async function ortakKlasor(govde) {
    const kutu = el('div', { class: 'k-kaydir' });
    govde.append(kutu);
    let d;
    try { d = await api('ana/ortak'); } catch (e) { kutu.append(el('div', { class: 'k-bos' }, e.message)); return; }
    const mesaj = el('p', { class: 'k-mesaj', 'aria-live': 'polite' });
    const bitti = async (r, metin) => { mesaj.className = 'k-mesaj iyi'; mesaj.textContent = metin; await ozetYukle(); setTimeout(() => { govde.innerHTML = ''; ortakKlasor(govde); }, 2500); };
    kutu.append(el('div', { class: 'k-oyuk k-bilgi' },
      el('p', {}, el('b', {}, 'Mac\'te başladığınız çalışmaya Windows\'ta devam etmek için '),
        'iki bilgisayarda da aynı bulut klasörünü (OneDrive, Google Drive, iCloud Drive ya da Dropbox) seçin. ',
        'Öğrenci kayıtlarınız ve makale PDF\'leriniz oraya taşınır; dersler, ayarlar ve sesler her bilgisayarda ayrı kalır.'),
      el('p', {}, el('b', {}, 'Aynı anda iki bilgisayarda çalışmayın. '),
        'Bir bilgisayarda bitirip bulut eşitlemesi tamamlanınca öbüründe açın. Öbür bilgisayar açıkken KlinikKoç sizi uyarır. ',
        'Dersleri (ders paketlerini) iki bilgisayara da ayrıca kurmanız gerekir.')));
    if (d.acik) {
      const durum = d.erisilebilir === false ? 'Şu an ulaşılamıyor' : (d.baska_bilgisayar ? `“${d.baska_bilgisayar.ad}” bilgisayarında da açık görünüyor` : 'Kullanılıyor');
      kutu.append(el('div', { class: 'k-satir' }, el('div', { class: 'k-orta' }, el('b', {}, 'Ortak klasör'),
        el('div', { class: 'k-alt-yazi' }, d.yol), el('div', { class: 'k-alt-yazi' }, `${durum} · bu bilgisayar: ${d.bilgisayar}`))));
      if (d.uyari) kutu.append(el('p', { class: 'k-mesaj kotu' }, d.uyari));
      const birak = el('button', { class: 'k-btn sade', type: 'button' }, 'Ortak klasörü bırak');
      birak.addEventListener('click', async () => {
        if (birak.dataset.emin !== '1') { birak.dataset.emin = '1'; birak.textContent = 'Emin misiniz? Kayıtlar bu bilgisayara kopyalanıp ortak klasör bırakılacak'; return; }
        birak.disabled = true;
        try { await api('ana/ortak_kapat', {}); bitti(null, 'Ortak klasör bırakıldı. Kayıtlarınız ve makaleleriniz bu bilgisayara kopyalandı; bulut klasöründekiler de silinmedi.'); }
        catch (e) { mesaj.className = 'k-mesaj kotu'; mesaj.textContent = e.message; birak.disabled = false; }
      });
      kutu.append(el('div', { class: 'k-alt' }, birak), mesaj);
      return;
    }
    const sec = async (yol, dugme) => {
      if (dugme) dugme.disabled = true;
      mesaj.className = 'k-mesaj'; mesaj.textContent = 'Kayıtlarınız ve makaleleriniz ortak klasöre kopyalanıyor…';
      try {
        const r = await api('ana/ortak_ayarla', { yol });
        const n = Object.values(r.kopyalanan || {}).reduce((a, b) => a + b, 0);
        bitti(r, `Ortak klasör hazır: ${r.ortak_klasor}. ${n} dosya kopyalandı. Öbür bilgisayarda da aynı bulut klasörünü seçin. (Önceki kayıtlarınızın yedeği: ${r.yedek})`);
      } catch (e) { mesaj.className = 'k-mesaj kotu'; mesaj.textContent = e.message; if (dugme) dugme.disabled = false; }
    };
    kutu.append(el('div', { class: 'k-bolum' }, 'Bu bilgisayarda bulunan bulut klasörleri'));
    if (!d.adaylar.length) kutu.append(el('p', { class: 'k-soluk' }, 'Bulut klasörü bulunamadı. Bulut uygulamanızı (OneDrive, Google Drive…) kurup açın ya da klasörün yolunu aşağıya yazın.'));
    for (const a of d.adaylar) {
      const b = el('button', { class: 'k-btn kucuk mavi', type: 'button' }, 'Bunu kullan');
      b.addEventListener('click', () => sec(a.yol, b));
      kutu.append(el('div', { class: 'k-satir' }, el('div', { class: 'k-orta' }, el('b', {}, a.ad), el('div', { class: 'k-alt-yazi' }, a.yol)), el('div', { class: 'k-sag' }, b)));
    }
    const girdi = el('input', { class: 'k-alan', type: 'text', placeholder: 'ya da klasörün yolunu yapıştırın', style: 'flex:1;min-width:0' });
    const elle = el('button', { class: 'k-btn kucuk', type: 'button' }, 'Bu klasörü kullan');
    elle.addEventListener('click', () => { if (girdi.value.trim()) sec(girdi.value.trim(), elle); });
    kutu.append(el('div', { class: 'k-alt' }, girdi, elle), el('p', { class: 'k-soluk' }, 'Seçilen klasörün içinde “KlinikKoç Ortak” adlı bir klasör açılır.'), mesaj);
  }

  // ---------- Geri bildirim (Claude'un programa önerileri) ----------
  async function geribildirim(p) {
    baslik(p, 'Geri bildirim', 'Program kendini bununla geliştirir');
    const govde = el('div', { class: 'k-iki', style: 'flex:1;min-height:0' });
    const bilgi = el('div', { class: 'k-oyuk k-bilgi' });
    const alt = el('div', { class: 'k-alt', style: 'justify-content:flex-end' });
    p.append(govde, bilgi, alt);
    let v;
    try { v = await api('ana/geri_bildirim'); } catch (e) { govde.append(el('div', { class: 'k-bos' }, e.message)); return; }
    if (panel !== 'geribildirim') return;
    const sol = el('div', { class: 'k-kart', style: 'padding:16px;display:flex;flex-direction:column;gap:10px;min-height:0;background:#f6ecd8' }, el('h2', {}, 'Claude\'un programa önerileri'));
    const solListe = el('div', { class: 'k-kaydir duz' });
    sol.append(solListe);
    const RENK = { eksik_cizim: '#E06826', kaynakta_yok: '#c9973e', arac_hatasi: '#b3401a', kullanim: '#6f95c9', yeni_ozellik: '#4f8a66', diger: '#8d8573' };
    if (!v.oneriler.length) {
      solListe.append(el('div', { class: 'k-bos' }, el('b', {}, 'Henüz öneri yok'),
        'Her dersin sonunda Claude, programın kendisi için kısa notlar yazar: eksik bir çizim, kaynakta bulunamayan bir soru, çalışmayan bir araç gibi.'));
    }
    for (const o of v.oneriler) {
      solListe.append(el('div', { class: 'k-satir', style: 'align-items:flex-start' }, el('span', { class: 'k-kure', style: `--c:${RENK[o.tur] || RENK.diger};width:28px;height:28px;font-size:13px` }, '!'),
        el('div', { class: 'k-orta' }, el('b', { style: 'font-size:14.5px' }, v.turler[o.tur] || o.tur), el('div', { style: 'font-size:14.5px' }, o.metin),
          el('div', { class: 'k-alt-yazi' }, [o.ders, o.yer, o.tarih, o.gonderildi ? 'gönderildi' : null].filter(Boolean).join(' · '))),
        el('div', { class: 'k-sag' }, el('button', { class: 'k-btn kucuk sade', title: 'Bu öneriyi siler', onclick: async () => { await api('ana/oneri_sil', { id: o.id }).catch(() => {}); git('geribildirim'); } }, 'Sil'))));
    }
    const sag = el('div', { class: 'k-kart', style: 'padding:16px;display:flex;flex-direction:column;gap:10px;min-height:0;background:#f6ecd8' },
      el('h2', {}, ogretmen() ? 'Öğrencilerden gelen formlar' : 'Ders değerlendirme formlarım'));
    const sagIc = el('div', { class: 'k-kaydir duz' });
    sag.append(sagIc);
    if (v.form_sayisi) sagIc.append(el('pre', { class: 'k-metin' }, v.form_ozeti));
    else {
      sagIc.append(el('div', { class: 'k-bos' }, el('b', {}, 'Henüz form yok'),
        ogretmen() ? 'Öğrencilerin gönderdiği form dosyalarını “KlinikKoç Değerlendirmeler” klasörüne koyun; özet burada görünür.'
          : 'Ders bitince 2–3 dakikalık değerlendirme formunu doldurabilirsiniz (Raporlarım › Ders değerlendirme formu).'));
    }
    sag.append(el('div', { class: 'k-alt' }, el('button', { class: 'k-btn kucuk sade', onclick: () => api('ana/klasor_ac', { hangi: 'form' }).catch(() => {}) }, 'Form klasörünü aç'),
      ogretmen() ? null : el('button', { class: 'k-btn kucuk sade', onclick: () => git('rapor', 'form') }, 'Formu doldur')));
    govde.append(sol, sag);
    bilgi.append('Bu notlar ', el('b', {}, 'yalnız bu bilgisayarda'), ' durur ve isim içermez. İsterseniz metni kopyalayıp öğretmeninize ya da bize iletirsiniz; ',
      el('b', {}, 'siz göndermedikçe hiçbir şey dışarı çıkmaz.'));
    const yeni = v.oneriler.filter((o) => !o.gonderildi);
    const kop = el('button', { class: 'k-btn sade', type: 'button', onclick: () => kopyala(v.metin, kop) }, 'Metni kopyala');
    const gonder = el('button', { class: 'k-btn mavi', type: 'button', disabled: !yeni.length, onclick: () => {
      pencere(el('h2', {}, 'Geliştirme önerisi olarak gönder'),
        el('p', {}, `${yeni.length} öneri, KlinikKoç'un açık kaynak sayfasında (GitHub) yeni bir öneri olarak açılacak. Sayfa tarayıcınızda içi dolu gelir; metni okuyup düzenleyebilir, sonra orada “Submit” düğmesine basarsınız.`),
        el('p', { class: 'k-soluk' }, 'GitHub hesabı gerekir ve gönderdiğiniz metin herkese açık olur. Hesabınız yoksa “Metni kopyala” ile öğretmeninize iletin.'),
        el('pre', { class: 'k-metin k-oyuk', style: 'padding:10px 12px;max-height:180px;overflow:auto' }, v.metin),
        el('div', { class: 'k-alt' }, el('button', { class: 'k-btn sade', onclick: pencereKapat }, 'Vazgeç'),
          el('a', { class: 'k-btn mavi', href: v.gonderme_adresi, target: '_blank', rel: 'noopener', onclick: async () => {
            await api('ana/oneri_gonderildi', { idler: yeni.map((o) => o.id) }).catch(() => {});
            pencereKapat(); git('geribildirim');
          } }, 'Sayfayı aç ↗')));
    } }, 'Geliştirme önerisi olarak gönder ↗');
    alt.append(el('button', { class: 'k-btn sade', onclick: () => api('ana/klasor_ac', { hangi: 'oneri' }).catch(() => {}) }, 'Klasörü aç'), kop, gonder);
  }

  // ---------- Güncelleme ----------
  $('#guncelleDugme').addEventListener('click', () => {
    const g = OZ.guncelleme || {};
    const durum = el('p', { class: 'k-mesaj' });
    const evet = el('button', { class: 'k-btn', type: 'button' }, '⟳ Şimdi güncelle');
    evet.addEventListener('click', async () => {
      evet.disabled = true; durum.className = 'k-mesaj';
      durum.textContent = 'Yedek alınıyor ve yeni sürüm indiriliyor… Bu pencereyi kapatmayın.';
      try {
        const r = await api('ana/guncelle', {});
        if (!r.guncellendi) { durum.textContent = r.neden || 'Güncelleme gerekmedi.'; return; }
        durum.className = 'k-mesaj iyi';
        durum.textContent = `Sürüm ${r.surum} kuruldu. KlinikKoç yeniden açılıyor…`;
        yenidenBagla(r.surum);
      } catch (e) { durum.className = 'k-mesaj kotu'; durum.textContent = e.message; evet.disabled = false; }
    });
    pencere(el('h2', {}, `Yeni sürüm: ${g.yeni_surum}`),
      el('p', {}, `Şu an ${g.surum} kurulu. Güncelleme bir iki dakika sürer.`),
      el('p', {}, el('b', {}, 'Dersleriniz, kayıtlarınız, makaleleriniz ve ayarlarınız olduğu gibi kalır. '),
        'Önce çalışan sürümün yedeği alınır; bir sorun çıkarsa program kendiliğinden eski sürüme döner.'),
      durum, el('div', { class: 'k-alt' }, el('button', { class: 'k-btn sade', onclick: pencereKapat }, 'Sonra'), evet));
  });
  // Sürüm numarasına basınca: yeni sürüme elle bakma ve önceki sürüme dönme.
  $('#surum').setAttribute('role', 'button'); $('#surum').tabIndex = 0; $('#surum').title = 'Sürüm bilgisi ve güncelleme';
  $('#surum').style.cursor = 'pointer';
  const surumPenceresi = () => {
    const g = OZ.guncelleme || {};
    const durum = el('p', { class: 'k-mesaj' }, g.gelistirici ? 'Bu bir geliştirici kopyası; güncelleme elle yapılır.' : (g.hata || (g.denetim ? 'Son bakılma: ' + g.denetim : '')));
    const bak = el('button', { class: 'k-btn mavi', type: 'button' }, 'Yeni sürüme şimdi bak');
    bak.addEventListener('click', async () => {
      bak.disabled = true; durum.className = 'k-mesaj'; durum.textContent = 'Bakılıyor…';
      try {
        const r = await api('ana/guncelleme_denetle', {});
        OZ.guncelleme = r;
        durum.className = 'k-mesaj ' + (r.var ? 'iyi' : '');
        durum.textContent = r.hata || (r.var ? `Yeni sürüm var: ${r.yeni_surum}. Üstteki “Güncelle” düğmesine basın.` : 'En yeni sürümü kullanıyorsunuz.');
        $('#guncelle').hidden = !(r.var && !r.gelistirici); $('#guncelleSurum').textContent = r.yeni_surum || '';
      } catch (e) { durum.className = 'k-mesaj kotu'; durum.textContent = e.message; }
      bak.disabled = false;
    });
    const geri = el('button', { class: 'k-btn sade', type: 'button' }, 'Önceki sürüme dön');
    geri.addEventListener('click', async () => {
      if (geri.dataset.emin !== '1') { geri.dataset.emin = '1'; geri.textContent = 'Emin misiniz? Evet, önceki sürüme dön'; return; }
      geri.disabled = true; durum.className = 'k-mesaj'; durum.textContent = 'Önceki sürüm geri yükleniyor…';
      try { const r = await api('ana/geri_al', {}); durum.className = 'k-mesaj iyi'; durum.textContent = `Sürüm ${r.surum} geri yüklendi. KlinikKoç yeniden açılıyor…`; yenidenBagla(r.surum); }
      catch (e) { durum.className = 'k-mesaj kotu'; durum.textContent = e.message; geri.disabled = false; }
    });
    pencere(el('h2', {}, `KlinikKoç ${OZ.surum}`),
      el('p', {}, OZ.tur === 'ogretmen' ? 'Öğretmen sürümü: ders çalışma ve ders hazırlama.' : 'Öğrenci sürümü: ders çalışma.'),
      el('p', {}, 'Önceki sürüme dönmek yalnız programı eski hâline getirir; dersleriniz ve kayıtlarınız değişmez.'),
      durum, el('div', { class: 'k-alt' }, el('button', { class: 'k-btn sade', onclick: pencereKapat }, 'Kapat'), g.gelistirici ? null : geri, g.gelistirici ? null : bak));
  };
  $('#surum').addEventListener('click', surumPenceresi);
  $('#surum').addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); surumPenceresi(); } });
  async function yenidenBagla(surum) {
    for (let i = 0; i < 40; i++) {
      await new Promise((r) => setTimeout(r, 1500));
      try { const o = await api('ana/ozet'); if (o.surum === surum) break; } catch (e) { /* sunucu yeniden açılıyor */ }
    }
    pencere(el('h2', {}, 'Güncelleme tamam'),
      el('p', {}, `KlinikKoç ${surum} kuruldu.`),
      el('p', {}, el('b', {}, 'Son adım: Claude masaüstü uygulamasını tamamen kapatıp yeniden açın. '), 'Pencereyi kapatmak yetmez: Windows’ta saatin yanındaki simge alanında Claude simgesine sağ tıklayıp “Çıkış” deyin, Mac’te menüden Claude › Çıkış (⌘Q). Böylece Claude da yeni sürümün araçlarını görür.'),
      el('div', { class: 'k-alt' }, el('button', { class: 'k-btn', onclick: () => location.reload() }, 'Tamam')));
  }

  const PANELLER = {
    derslerim, paket, pdf, makale, rapor, geribildirim,
    sablon: (p) => { baslik(p, 'Çizim şablonları', 'Eğitmenin tahtada kullandığı hazır çizimler'); cerceve(p, 'sablon-galerisi.html?gomulu=1', 'Çizim şablonları'); },
    hazirla: (p) => { if (!ogretmen()) return derslerim(p); p.style.padding = '10px'; cerceve(p, 'sihirbaz.html?gomulu=1&kabuk=ana', 'Ders hazırlama'); },
    kilavuz: (p) => { cerceve(p, 'kilavuz.html?gomulu=1', 'Kullanım kılavuzu'); },
  };
  $('#ustSihirbaz').addEventListener('click', () => git('derslerim'));
  $('#ustKilavuz').addEventListener('click', () => git('kilavuz'));
  // İçteki sayfalar (sihirbaz, makaleler) bir şey değiştirince ana ekran listesini yeniler.
  window.addEventListener('message', (e) => {
    if (e.origin !== location.origin || !e.data || e.data.klinikkoc !== 'degisti') return;
    ozetYukle();
  });

  (async function baslat() {
    await ozetYukle();
    for (const d of (OZ.secim && OZ.secim.dersler) || []) secili.dersler.add(d);
    for (const x of (OZ.secim && OZ.secim.pdfler) || []) secili.pdfler.add(x);
    const istenen = (location.hash || '').slice(1);
    const gecerli = istenen === 'kilavuz' || BOLUMLER.some((b) => b.id === istenen && (!b.ogretmen || ogretmen()));
    git(gecerli ? istenen : 'derslerim');
    // Makaleler arka planda inerken liste kendiliğinden güncellensin.
    setInterval(async () => { if (panel === 'derslerim' && $('#pencere').hidden && OZ.dersler.some((d) => d.makale.calisiyor)) { await ozetYukle(); if (panel === 'derslerim') git('derslerim'); } }, 5000);
  }());
}());
