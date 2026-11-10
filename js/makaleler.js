/* KlinikKoç · Makaleler sayfası. Yerel sunucunun /api/makale/ isteklerini kullanır (tools/sunucu.py). */
(function () {
  'use strict';
  const $ = (s) => document.querySelector(s);
  const DURUM = { hazir: 'Hazır', eksik: 'Eksik', hata: 'Okunamadı', denenmedi: 'Denenmedi' };
  const NEREDEN = {
    paket: 'ders paketiyle geldi', klasor: 'makale klasöründe vardı', 'acik-erisim': 'açık erişimden indi',
    universite: 'yayıncıdan indi', elle: 'siz eklediniz', ders: 'dersin kendi metni',
  };
  let ders = new URLSearchParams(location.search).get('ders') || '';
  let izleme = null;
  if (location.protocol === 'file:') {
    // Dosyaya çift tıklanarak açıldı: bu sayfa yerel sunucu olmadan çalışmaz.
    const u = document.createElement('div');
    u.className = 'dp-uyari';
    u.textContent = 'Bu sayfa KlinikKoç açıkken çalışır. Program klasöründeki BASLAT-Windows (Mac\'te BASLAT-Mac) dosyasına çift tıklayın ya da Claude\'a "ders paketi sayfasını aç" deyin.';
    document.addEventListener('DOMContentLoaded', () => document.querySelector('main').prepend(u));
    if (document.readyState !== 'loading') document.querySelector('main').prepend(u);
  }

  async function api(yol, secenek) {
    const y = await fetch('/api/makale/' + yol, secenek);
    let v = {};
    try { v = await y.json(); } catch (e) { /* boş gövde */ }
    if (!y.ok) throw Object.assign(new Error(v.hata || ('HTTP ' + y.status)), { kod: y.status });
    return v;
  }
  const yaziyla = (el, metin, sinif) => { el.innerHTML = ''; const s = document.createElement('span');
    if (sinif) s.className = sinif; s.textContent = metin; el.appendChild(s); };
  const etiket = (tur, metin) => { const s = document.createElement('span'); s.className = 'mk-etiket ' + tur;
    s.textContent = metin; return s; };

  async function dersleriYukle() {
    let v;
    try { v = await api('dersler'); } catch (e) {
      yaziyla($('#ozet'), 'Yerel sunucuya ulaşılamadı. Bu sayfa KlinikKoç sunucusuyla açılmalı (tools/sunucu.py).', 'kotu');
      return;
    }
    const sec = $('#dersSec');
    sec.innerHTML = '';
    for (const d of v.dersler) {
      const o = document.createElement('option');
      o.value = d.ders; o.textContent = `${d.baslik} (${d.makale} makale)`;
      sec.appendChild(o);
    }
    if (!v.dersler.length) {
      yaziyla($('#ozet'), 'Makale listesi olan bir ders yok. Önce yukarıdan bir ders paketi ekleyin.');
      $('#liste').innerHTML = '';
      return;
    }
    if (!v.dersler.some((d) => d.ders === ders)) ders = v.dersler[0].ders;
    sec.value = ders;
    if (!v.pdf_okuyucu) {
      yaziyla($('#pdfMesaj'), 'PDF okuyucu kurulu değil: inen makaleler okunamaz. KUR dosyasını yeniden çalıştırın.', 'kotu');
    }
    await durumYukle();
  }

  async function durumYukle() {
    if (!ders) return;
    let o;
    try { o = await api('durum?ders=' + encodeURIComponent(ders)); } catch (e) {
      yaziyla($('#ozet'), e.message, 'kotu'); return;
    }
    const oz = $('#ozet');
    oz.innerHTML = '';
    if (o.calisiyor) oz.appendChild(etiket('calisiyor', 'Makaleler aranıyor…'));
    for (const [k, n] of Object.entries(o.sayilar)) oz.appendChild(etiket(k, `${DURUM[k] || k}: ${n}`));
    $('#klasorYolu').textContent = 'Makale klasörü: ' + o.klasor;
    $('#bulDugme').disabled = !!o.calisiyor;
    listeyiCiz(o.makaleler);
    clearTimeout(izleme);
    if (o.calisiyor) izleme = setTimeout(durumYukle, 2500);
  }

  function listeyiCiz(makaleler) {
    const ol = $('#liste');
    ol.innerHTML = '';
    for (const m of makaleler) {
      const li = document.createElement('li');
      const ad = document.createElement('div');
      ad.className = 'mk-ad';
      ad.textContent = m.kisa || m.id;
      if (m.rol === 'ana') { const r = document.createElement('span'); r.className = 'mk-rol'; r.textContent = 'ana kaynak'; ad.appendChild(r); }
      if (m.ogrenci) { const r = document.createElement('span'); r.className = 'mk-rol'; r.textContent = 'sizin eklediğiniz'; ad.appendChild(r); }
      li.appendChild(ad);
      li.appendChild(etiket(m.durum, DURUM[m.durum] || m.durum));
      if (m.atif) { const a = document.createElement('div'); a.className = 'mk-atif'; a.textContent = m.atif; li.appendChild(a); }
      const not = document.createElement('div');
      not.className = 'mk-not';
      if (m.durum === 'hazir') {
        not.textContent = (NEREDEN[m.nereden] || '') + (m.sayfa ? ` · ${m.sayfa} sayfa okundu` : '');
      } else if (m.neden) {
        not.textContent = m.neden;
      }
      if (not.textContent) li.appendChild(not);
      const islem = document.createElement('div');
      islem.className = 'mk-islem';
      if (m.durum !== 'hazir' && m.sayfa_adresi) {
        const a = document.createElement('a');
        a.className = 'btn small'; a.href = m.sayfa_adresi; a.target = '_blank'; a.rel = 'noopener';
        a.textContent = 'Yayıncı sayfasını aç';
        islem.appendChild(a);
      }
      if (m.durum !== 'hazir' || m.ogrenci) {
        const lb = document.createElement('label');
        lb.className = 'btn small';
        lb.textContent = m.durum === 'hazir' ? 'PDF\'i değiştir' : 'PDF\'i seç';
        const inp = document.createElement('input');
        inp.type = 'file'; inp.accept = '.pdf,application/pdf'; inp.hidden = true;
        inp.addEventListener('change', () => inp.files[0] && pdfGonder(inp.files[0], m.id));
        lb.appendChild(inp);
        islem.appendChild(lb);
      }
      if (m.ogrenci) {
        const b = document.createElement('button');
        b.className = 'btn small ghost'; b.textContent = 'Dersten çıkar';
        b.addEventListener('click', async () => {
          try { await api('kaldir', { method: 'POST', body: JSON.stringify({ ders, id: m.id }) }); } catch (e) { alertYerine(e.message); }
          durumYukle();
        });
        islem.appendChild(b);
      }
      if (islem.children.length) li.appendChild(islem);
      ol.appendChild(li);
    }
  }

  function alertYerine(metin) { yaziyla($('#pdfMesaj'), metin, 'kotu'); }

  async function pdfGonder(dosya, kaynak) {
    const mesaj = $('#pdfMesaj');
    yaziyla(mesaj, `${dosya.name} okunuyor…`);
    try {
      const q = new URLSearchParams({ ders, ad: dosya.name });
      if (kaynak) q.set('kaynak', kaynak);
      const v = await api('ekle?' + q, { method: 'POST', body: dosya });
      if (v.durum === 'hazir') {
        yaziyla(mesaj, `${dosya.name}: ${v.ogrenci ? 'listede yoktu, sizin eklediğiniz makale olarak' : '“' + v.kisa + '” olarak'} eklendi (${v.sayfa} sayfa).`, 'iyi');
      } else {
        yaziyla(mesaj, `${dosya.name}: ${v.neden || 'okunamadı'}`, 'kotu');
      }
    } catch (e) { yaziyla(mesaj, `${dosya.name}: ${e.message}`, 'kotu'); }
    durumYukle();
  }

  async function paketGonder(dosya, uzerine) {
    const mesaj = $('#paketMesaj');
    yaziyla(mesaj, `${dosya.name} kuruluyor…`);
    try {
      const v = await api('paket' + (uzerine ? '?uzerine=1' : ''), { method: 'POST', body: dosya });
      yaziyla(mesaj, `Kuruldu: ${v.baslik}. ${v.makale ? v.makale + ' makale aranıyor.' : ''}`, 'iyi');
      ders = v.ders;
      history.replaceState(null, '', '?ders=' + encodeURIComponent(ders));
      await dersleriYukle();
      depolamaYukle();
    } catch (e) {
      if (e.kod === 409) {
        mesaj.innerHTML = '';
        const s = document.createElement('span'); s.className = 'kotu'; s.textContent = e.message + ' ';
        const b = document.createElement('button'); b.className = 'btn small'; b.textContent = 'Güncelle';
        b.addEventListener('click', () => paketGonder(dosya, true));
        mesaj.append(s, b);
      } else {
        yaziyla(mesaj, e.message, 'kotu');
      }
    }
  }

  function birakmaAlani(alan, girdi, isle) {
    alan.addEventListener('dragover', (e) => { e.preventDefault(); alan.classList.add('ustunde'); });
    alan.addEventListener('dragleave', () => alan.classList.remove('ustunde'));
    alan.addEventListener('drop', (e) => {
      e.preventDefault(); alan.classList.remove('ustunde');
      [...e.dataTransfer.files].forEach((f) => isle(f));
    });
    girdi.addEventListener('change', () => { [...girdi.files].forEach((f) => isle(f)); girdi.value = ''; });
  }

  // Sayfanın herhangi bir yerine bırakılan dosya tarayıcıda açılmasın.
  window.addEventListener('dragover', (e) => e.preventDefault());
  window.addEventListener('drop', (e) => e.preventDefault());

  birakmaAlani($('#pdfBirak'), $('#pdfSec'), (f) => pdfGonder(f, null));
  birakmaAlani($('#paketBirak'), $('#paketSec'), (f) => paketGonder(f, false));
  $('#dersSec').addEventListener('change', (e) => {
    ders = e.target.value;
    history.replaceState(null, '', '?ders=' + encodeURIComponent(ders));
    durumYukle();
  });
  $('#bulDugme').addEventListener('click', async () => {
    try { await api('hazirla', { method: 'POST', body: JSON.stringify({ ders }) }); } catch (e) { alertYerine(e.message); }
    durumYukle();
  });
  $('#klasorDugme').addEventListener('click', () => api('klasor_ac', { method: 'POST', body: JSON.stringify({ ders }) })
    .catch((e) => alertYerine(e.message)));
  // ---------- Depolama ve arşiv ----------
  const boyut = (n) => {
    for (const [b, d] of [['GB', 1024 ** 3], ['MB', 1024 ** 2], ['KB', 1024]]) if (n >= d) return (n / d).toFixed(1).replace('.', ',') + ' ' + b;
    return n + ' bayt';
  };
  const yeni = (etiketAdi, sinif, metin) => { const e = document.createElement(etiketAdi); if (sinif) e.className = sinif;
    if (metin != null) e.textContent = metin; return e; };
  let DP = null;

  async function depolamaYukle() {
    try { DP = await api('depolama'); } catch (e) { return; }
    const oran = DP.toplam_bayt / DP.sinir_bayt;
    $('#dpMetre').value = Math.min(1, oran);
    $('#dpMetre').optimum = 0.3; $('#dpMetre').high = 0.85;
    $('#dpSayi').textContent = `${boyut(DP.toplam_bayt)} / ${String(DP.sinir_gb).replace('.', ',')} GB`;
    if (document.activeElement !== $('#dpSinir')) $('#dpSinir').value = DP.sinir_gb;
    for (const yer of ['#dpUyari', '#dpUstUyari']) {
      const u = $(yer);
      u.hidden = !DP.asildi;
      u.innerHTML = '';
      if (DP.asildi) {
        u.append(yeni('strong', '', 'Ders verisi sınırı aştı. '),
          document.createTextNode('Hangi dersleri arşive kaldıralım? En uzun süredir açmadığınız dersler başta. '));
        if (yer === '#dpUstUyari') { const a = yeni('a', '', 'Depolama ve arşive git'); a.href = '#depolama'; u.append(a); }
      }
    }
    const ol = $('#dpDersler'); ol.innerHTML = '';
    const sira = [...DP.arsiv_adaylari, ...DP.dersler.filter((d) => d.yerlesik).map((d) => d.ders)];
    const dersler = [...DP.dersler].sort((x, y) => sira.indexOf(x.ders) - sira.indexOf(y.ders));
    for (const d of dersler) {
      const li = yeni('li');
      const kutu = yeni('input'); kutu.type = 'checkbox'; kutu.value = d.ders; kutu.disabled = d.yerlesik;
      kutu.setAttribute('aria-label', d.baslik + ' dersini seç');
      kutu.addEventListener('change', secimDegisti);
      const ad = yeni('div', 'mk-ad', d.baslik);
      if (d.tamamlandi) ad.append(yeni('span', 'mk-rol', 'bitirildi'));
      if (d.yerlesik) ad.append(yeni('span', 'mk-rol', 'programla gelir'));
      li.append(kutu, ad, yeni('span', 'dp-boyut', boyut(d.toplam)));
      li.append(yeni('div', 'mk-not', `Son açılma: ${d.son_acilma || '-'} · ders ${boyut(d.ders_bayt)}, arama ${boyut(d.dizin_bayt)}, `
        + `makale PDF'leri ${boyut(d.pdf_bayt)}`));
      ol.append(li);
    }
    if (!dersler.length) ol.append(yeni('li', 'mk-ince', 'Bu bilgisayarda kurulu ders yok.'));
    const ar = $('#dpArsiv'); ar.innerHTML = '';
    for (const a of DP.arsiv) {
      const li = yeni('li');
      li.append(yeni('span', '', '🗄'), yeni('div', 'mk-ad', a.baslik || a.ders), yeni('span', 'dp-boyut', a.boyut ? boyut(a.boyut) : ''));
      li.append(yeni('div', 'mk-not', `${a.tarih} · ${a.dosya_var ? a.dosya : 'zip bulunamadı; taşıdıysanız aşağıya bırakın'}`));
      const islem = yeni('div', 'mk-islem');
      const b = yeni('button', 'btn small', 'Geri yükle'); b.disabled = !a.dosya_var;
      b.addEventListener('click', () => geriYukle(JSON.stringify({ ders: a.ders }), a.baslik || a.ders));
      islem.append(b); li.append(islem); ar.append(li);
    }
    if (!DP.arsiv.length) ar.append(yeni('li', 'mk-ince', 'Arşivde ders yok.'));
    secimDegisti();
  }

  function secilenler() { return [...document.querySelectorAll('#dpDersler input:checked')].map((k) => k.value); }
  function secimDegisti() { $('#dpArsivDugme').disabled = !secilenler().length; }

  $('#dpArsivDugme').addEventListener('click', () => {
    const s = secilenler();
    if (!s.length) return;
    const adlar = s.map((x) => (DP.dersler.find((d) => d.ders === x) || {}).baslik || x);
    const m = $('#dpMesaj'); m.innerHTML = '';
    const onay = yeni('div', 'dp-onay');
    onay.append(yeni('span', '', `${adlar.join(', ')} arşive kaldırılacak. Raporlar yazılır, ilerlemeniz ve PDF'leriniz kalır.`));
    const evet = yeni('button', 'btn small primary', 'Evet, arşive kaldır');
    const hayir = yeni('button', 'btn small ghost', 'Vazgeç');
    hayir.addEventListener('click', () => { m.innerHTML = ''; });
    evet.addEventListener('click', () => arsivle(s));
    onay.append(evet, hayir); m.append(onay);
  });

  async function arsivle(liste) {
    const m = $('#dpMesaj');
    for (const d of liste) {
      yaziyla(m, `${d} arşivleniyor…`);
      try {
        const r = await api('arsivle', { method: 'POST', body: JSON.stringify({ ders: d }) });
        m.innerHTML = '';
        m.append(yeni('p', 'iyi', `${r.baslik} arşive kaldırıldı, ${boyut(r.acilan_yer)} yer açıldı. Arşiv: ${r.dosya}. `
          + `PDF'ler (${r.pdf_sayisi}) şurada kalıyor: ${r.makale_klasoru}`));
        for (const u of r.uyarilar || []) m.append(yeni('p', 'kotu', u));
      } catch (e) { yaziyla(m, `${d}: ${e.message}`, 'kotu'); break; }
    }
    await depolamaYukle();
    dersleriYukle();
  }

  async function geriYukle(govde, ad) {
    const m = $('#dpMesaj');
    yaziyla(m, `${ad} geri yükleniyor…`);
    try {
      const r = await api('geri_yukle', { method: 'POST', body: govde });
      m.innerHTML = '';
      m.append(yeni('p', 'iyi', `${r.baslik || r.ders} geri geldi${r.kayit_geri.length ? `; ${r.kayit_geri.length} öğrencinin ilerlemesi yüklendi` : ''}`
        + `${r.kayit_korundu.length ? `; bu bilgisayardaki daha yeni ilerleme korundu` : ''}. Makaleler hazırlanıyor.`));
      for (const u of r.uyarilar || []) m.append(yeni('p', 'kotu', u));
      ders = r.ders;
      history.replaceState(null, '', '?ders=' + encodeURIComponent(ders) + '#depolama');
    } catch (e) { yaziyla(m, e.message, 'kotu'); }
    await depolamaYukle();
    dersleriYukle();
  }

  birakmaAlani($('#arsivBirak'), $('#arsivSec'), (f) => geriYukle(f, f.name));
  $('#dpSinirDugme').addEventListener('click', async () => {
    const gb = parseFloat(String($('#dpSinir').value).replace(',', '.'));
    try { await api('sinir', { method: 'POST', body: JSON.stringify({ gb }) }); yaziyla($('#dpMesaj'), 'Sınır kaydedildi.', 'iyi'); }
    catch (e) { yaziyla($('#dpMesaj'), e.message, 'kotu'); }
    depolamaYukle();
  });
  $('#dpKlasorDugme').addEventListener('click', () => api('arsiv_klasoru_ac', { method: 'POST' }).catch((e) => yaziyla($('#dpMesaj'), e.message, 'kotu')));

  dersleriYukle();
  depolamaYukle();
}());
