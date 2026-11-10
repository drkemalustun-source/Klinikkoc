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
  dersleriYukle();
}());
