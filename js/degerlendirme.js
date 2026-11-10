/* KlinikKoç · Ders sonu değerlendirme formu. Yerel sunucunun /api/makale/degerlendirme isteklerini kullanır. */
(function () {
  'use strict';
  const $ = (s) => document.querySelector(s);
  const q = new URLSearchParams(location.search);
  const ders = q.get('ders') || '';
  const ogrenci = q.get('ogrenci') || '';
  let F = null;
  let metin = '';

  function el(ad, ozellik, ...cocuklar) {
    const e = document.createElement(ad);
    for (const [k, v] of Object.entries(ozellik || {})) {
      if (k.startsWith('on')) e.addEventListener(k.slice(2), v); else if (v !== null && v !== undefined) e.setAttribute(k, v);
    }
    for (const c of cocuklar.flat()) if (c !== null && c !== undefined) e.append(c.nodeType ? c : String(c));
    return e;
  }
  async function api(yol, govde) {
    const y = await fetch('/api/makale/' + yol, govde ? { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(govde) } : undefined);
    let v = {};
    try { v = await y.json(); } catch (e) { /* boş gövde */ }
    if (!y.ok) throw new Error(v.hata || ('HTTP ' + y.status));
    return v;
  }
  const mesaj = (yer, m, hata) => { const e = $(yer); e.innerHTML = ''; e.append(el('span', { class: hata ? 'hata' : '' }, m)); };

  function secenekler(s, deger) {
    const ad = 'c-' + s.id;
    const kutu = el('div', { class: 'dg-secenek', role: 'radiogroup' });
    let liste;
    if (s.tur === 'olcek') {
      liste = F.olcek.map((m, i) => [String(i + 1), String(i + 1)]);
      if (s.bos) liste.push(['0', s.bos]);
    } else liste = s.secenekler.map((o) => [o, o]);
    for (const [v, yazi] of liste) {
      const g = el('input', { type: 'radio', name: ad, value: v, 'aria-label': s.tur === 'olcek' && v !== '0' ? F.olcek[Number(v) - 1] : yazi });
      if (String(deger) === v) g.checked = true;
      kutu.append(el('label', {}, g, yazi));
    }
    return kutu;
  }

  function sorulariCiz() {
    const k = $('#sorular'); k.innerHTML = '';
    k.append(el('p', { class: 'mk-ince' }, '1 = ' + F.olcek[0] + ' · 3 = ' + F.olcek[2] + ' · 5 = ' + F.olcek[4]));
    for (const s of F.sorular) {
      const d = el('div', { class: 'dg-soru', 'data-id': s.id, 'data-tur': s.tur },
        el('div', { class: 'dg-metin' }, s.metin, s.ders_ozel ? el('span', { class: 'dg-ozel' }, 'bu derse özel') : null));
      if (s.tur === 'metin') {
        const t = el('textarea', { rows: '2', maxlength: '2000' });
        t.value = F.cevaplar[s.id] || '';
        d.append(t);
      } else d.append(secenekler(s, F.cevaplar[s.id]));
      k.append(d);
    }
  }

  function tespitleriCiz() {
    const ul = $('#tespitler'); ul.innerHTML = '';
    if (!F.tespitler.length) ul.append(el('li', { class: 'mk-ince' }, 'Bu derste kayda geçen bir sorun yok.'));
    F.tespitler.forEach((t, i) => {
      const li = el('li', { class: t.cikar ? 'dg-cikti' : '' },
        el('span', { class: 'dg-tur' }, (F.tespit_turleri[t.tur] || t.tur) + (t.kaynak === 'otomatik' ? ' · kayıttan' : ' · Claude')),
        el('span', { class: 'dg-ayrinti' }, t.ayrinti, t.yer ? el('span', { class: 'mk-ince' }, ' (yer: ' + t.yer + ')') : null),
        el('button', { type: 'button', class: 'btn small ghost dg-cikar', onclick: () => { t.cikar = !t.cikar; tespitleriCiz(); } },
          t.cikar ? 'Geri al' : 'Çıkar'));
      ul.append(li);
    });
    const tur = el('select', {}, Object.entries(F.tespit_turleri).map(([k, v]) => el('option', { value: k }, v)));
    const ayr = el('textarea', { rows: '1', maxlength: '600', placeholder: 'Eklemek istediğiniz bir sorun (isteğe bağlı)' });
    ul.append(el('li', { class: 'dg-ekle' }, tur, ayr, el('button', { type: 'button', class: 'btn small', onclick: () => {
      if (!ayr.value.trim()) return;
      F.tespitler.push({ tur: tur.value, ayrinti: ayr.value.trim(), kaynak: 'ogrenci' });
      tespitleriCiz();
    } }, 'Ekle')));
  }

  function cevaplar() {
    const c = {};
    document.querySelectorAll('.dg-soru').forEach((d) => {
      if (d.dataset.tur === 'metin') { const v = d.querySelector('textarea').value.trim(); if (v) c[d.dataset.id] = v; } else {
        const s = d.querySelector('input:checked'); if (s) c[d.dataset.id] = d.dataset.tur === 'olcek' ? Number(s.value) : s.value;
      }
    });
    return c;
  }

  async function yukle() {
    if (location.protocol === 'file:') {
      mesaj('#dersAdi', 'Bu sayfa KlinikKoç açıkken çalışır: BASLAT dosyasına çift tıklayın ya da Claude\'a "değerlendirme formunu aç" deyin.', true);
      return;
    }
    if (!ders) { mesaj('#dersAdi', 'Ders seçilmedi. Claude\'a "bu dersin değerlendirme formunu aç" deyin.', true); return; }
    try {
      F = await api('degerlendirme?ders=' + encodeURIComponent(ders) + (ogrenci ? '&ogrenci=' + encodeURIComponent(ogrenci) : ''));
    } catch (e) { mesaj('#dersAdi', e.message, true); return; }
    $('#dersAdi').textContent = F.baslik + (F.gonderildi ? ' · daha önce ' + F.gonderildi + ' tarihinde kaydettiniz; yeniden kaydedebilirsiniz.' : '');
    const oz = F.ozet;
    if (oz) {
      $('#ozetMetni').textContent = ' (' + oz.oturum + ' oturum' + (oz.dakika ? ', ' + oz.dakika + ' dk' : '') +
        (oz.genel_basari !== null && oz.genel_basari !== undefined ? ', genel başarı %' + Math.round(oz.genel_basari * 100) : '') +
        ', hedeflerin durumu; ad ya da cevap metni yok)';
    } else { $('#ozetEkle').checked = false; $('#ozetEkle').closest('label').hidden = true; }
    sorulariCiz();
    tespitleriCiz();
    $('#form').hidden = false;
  }

  $('#form').addEventListener('submit', async (e) => {
    e.preventDefault();
    $('#kaydet').disabled = true;
    try {
      const r = await api('degerlendirme_kaydet', { ders, ogrenci: ogrenci || null, cevaplar: cevaplar(),
        tespitler: F.tespitler.filter((t) => !t.cikar), ozet_ekle: $('#ozetEkle').checked });
      metin = r.metin;
      $('#form').hidden = true;
      $('#sonra').hidden = false;
      const p = $('#sonraMetni'); p.innerHTML = '';
      p.append('Form bu bilgisayara kaydedildi: ', el('code', {}, r.metin_dosyasi), '. ');
      if (r.mailto) {
        const a = $('#epostaDugme'); a.href = r.mailto; a.hidden = false;
        p.append('Göndermek isterseniz ', el('b', {}, 'E-postayla gönder'), '\'e basın; e-posta programınız öğretmeninizin adresiyle (',
          r.eposta, ') açılır, siz gönderirsiniz. Metin e-postaya sığmadıysa dosyayı ekleyin.');
      } else {
        p.append('Bu ders için öğretmen adresi tanımlı değil. Göndermek isterseniz ', el('b', {}, 'Metni kopyala'),
          ' ile e-postanıza yapıştırın ya da dosyayı ekleyin.');
      }
      window.scrollTo(0, 0);
    } catch (err) { mesaj('#mesaj', err.message, true); $('#kaydet').disabled = false; }
  });
  $('#kopyala').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(metin); mesaj('#sonraMesaj', 'Kopyalandı.'); } catch (e) {
      mesaj('#sonraMesaj', 'Kopyalanamadı; klasördeki .txt dosyasını açıp kopyalayın.', true);
    }
  });
  $('#klasorAc').addEventListener('click', () => api('degerlendirme_klasoru_ac', {}).catch((e) => mesaj('#sonraMesaj', e.message, true)));
  yukle();
})();
