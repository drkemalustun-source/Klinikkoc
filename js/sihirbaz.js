/* KlinikKoç · Ders hazırlama sihirbazı (öğretmen ekranı). Yerel sunucunun /api/sihirbaz/ isteklerini kullanır. */
(function () {
  'use strict';
  const $ = (s) => document.querySelector(s);
  const BLOOM_AD = { hatirla: 'Hatırla', anla: 'Anla', uygula: 'Uygula', cozumle: 'Çözümle', degerlendir: 'Değerlendir', olustur: 'Oluştur' };
  const TUR_AD = { hedefler: 'Hedef', terimler: 'Terim', sorular: 'Soru', yanilgilar: 'Yanılgı' };
  let KADEME = {};
  let BLOOM = Object.keys(BLOOM_AD);
  let ders = new URLSearchParams(location.search).get('ders') || '';
  let T = null;

  async function api(yol, govde, ham) {
    const sec = govde === undefined ? {} : { method: 'POST', body: ham ? govde : JSON.stringify(govde) };
    const y = await fetch('/api/sihirbaz/' + yol, sec);
    let v = {};
    try { v = await y.json(); } catch (e) { /* boş */ }
    if (!y.ok) throw Object.assign(new Error(v.hata || ('HTTP ' + y.status)), { kod: y.status });
    return v;
  }
  const el = (etiket, ozellik, ...cocuk) => {
    const e = document.createElement(etiket);
    for (const [k, v] of Object.entries(ozellik || {})) {
      if (k === 'class') e.className = v; else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
      else if (v !== undefined && v !== null) e.setAttribute(k, v);
    }
    for (const c of cocuk.flat()) if (c !== null && c !== undefined) e.append(c.nodeType ? c : String(c));
    return e;
  };
  const mesaj = (hedef, metin, sinif) => { const m = $(hedef); m.innerHTML = ''; m.append(el('span', { class: sinif || '' }, metin)); };
  const hata = (hedef) => (e) => mesaj(hedef, e.message, 'kotu');
  const secim = (deger, secenekler, adlar) => {
    const s = el('select');
    for (const o of secenekler) s.append(el('option', { value: o }, (adlar && adlar[o]) || o));
    s.value = deger || secenekler[0];
    return s;
  };

  async function baslat() {
    const v = await api('liste').catch(() => null);
    if (!v) { mesaj('#genelMesaj', 'Yerel sunucuya ulaşılamadı. Bu sayfa KlinikKoç sunucusuyla açılmalı (tools/sunucu.py).', 'kotu'); return; }
    KADEME = v.kademeler; BLOOM = v.bloom;
    const ks = $('#kademeSec'); ks.innerHTML = '';
    for (const [k, ad] of Object.entries(KADEME)) ks.append(el('option', { value: k }, ad));
    const sec = $('#dersSec'); sec.innerHTML = '';
    if (!v.taslaklar.length) { sec.append(el('option', { value: '' }, 'Henüz taslak yok')); $('#yeniKutu').open = true; }
    for (const t of v.taslaklar) sec.append(el('option', { value: t.ders }, `${t.baslik || t.ders}${t.paket ? ' · paketlendi ' + t.paket : ''}`));
    if (v.taslaklar.length && !v.taslaklar.some((t) => t.ders === ders)) ders = v.taslaklar[0].ders;
    sec.value = ders;
    if (ders) await yukle();
  }

  async function yukle() {
    try { T = await api('taslak?ders=' + encodeURIComponent(ders)); } catch (e) { return hata('#genelMesaj')(e); }
    $('#adimlar').hidden = false; $('#icerik').hidden = false;
    history.replaceState(null, '', '?ders=' + encodeURIComponent(ders));
    ciz();
  }

  function ciz() {
    document.querySelectorAll('[data-alan]').forEach((g) => { g.value = T[g.dataset.alan] ?? ''; });
    $('#claudeKomut').textContent = `"${T.baslik} dersi için sihirbaz önerilerini hazırla."`;
    kaynaklariCiz(); notlariCiz(); vakalariCiz(); listeCiz('dikkat', '#dikkatListe'); listeCiz('yanilgilar', '#yanilgiListe');
    sorulariCiz(); hedefleriCiz(); terimleriCiz(); onerileriCiz(); denetle();
  }

  // ---------- 1. Ders kartı ----------
  document.querySelectorAll('[data-alan]').forEach((g) => g.addEventListener('change', async () => {
    try { T = await api('kart', { ders, alanlar: { [g.dataset.alan]: g.value } }); denetle(); } catch (e) { hata('#genelMesaj')(e); }
  }));

  // ---------- 2. Makaleler ----------
  function kaynaklariCiz() {
    const ol = $('#kaynakListe'); ol.innerHTML = '';
    for (const k of T.kaynaklar) {
      const ust = el('div', { class: 'mk-ad' }, k.kisa || k.doi, k.rol === 'ana' ? el('span', { class: 'mk-rol' }, 'ana kaynak') : null);
      const oa = k.acik_erisim === true ? el('span', { class: 'mk-etiket hazir' }, 'açık erişim')
        : k.acik_erisim === false ? el('span', { class: 'mk-etiket denenmedi' }, 'abonelikli') : el('span', { class: 'mk-etiket denenmedi' }, '?');
      const li = el('li', {}, ust, oa, el('div', { class: 'mk-atif' }, k.atif || k.doi));
      if (k.uyari) li.append(el('div', { class: 'mk-not sh-uyari' }, k.uyari));
      if (k.ozet) li.append(el('details', { class: 'sh-bolumler mk-not' }, el('summary', {}, 'Özet'), el('p', { class: 'sh-ozet' }, k.ozet)));
      const islem = el('div', { class: 'mk-islem' });
      if (k.rol !== 'ana') islem.append(el('button', { class: 'btn small', onclick: () => degistir('ana', { ders, id: k.id }) }, 'Ana kaynak yap'));
      islem.append(el('button', { class: 'btn small ghost', onclick: () => sil('kaynaklar', k.id) }, 'Çıkar'));
      li.append(islem); ol.append(li);
    }
  }
  $('#doiDugme').addEventListener('click', async () => {
    const metin = $('#doiMetin').value.trim();
    if (!metin) return;
    mesaj('#doiMesaj', 'Künyeler getiriliyor…');
    try {
      const r = await api('doi', { ders, metin });
      const eksik = (r.kaynaklar || []).filter((k) => k.uyari).length;
      mesaj('#doiMesaj', `${r.eklenen} makale eklendi${r.zaten_vardi ? ', ' + r.zaten_vardi + ' tanesi zaten listedeydi' : ''}.`
        + (eksik ? ` ${eksik} makalenin künyesi alınamadı; internete bağlanınca "Eksik künyeleri yeniden sor"a basın.` : ''), eksik ? 'kotu' : 'iyi');
      $('#doiMetin').value = '';
      await yukle();
    } catch (e) { hata('#doiMesaj')(e); }
  });
  $('#kunyeDugme').addEventListener('click', () => degistir('kunye_yenile', { ders }, '#doiMesaj'));

  // ---------- 3. Notlar ve vakalar ----------
  function kademeSecimi(liste, oge) {
    const s = secim(oge.kademe, Object.keys(KADEME), KADEME);
    s.addEventListener('change', () => degistir('oge', { ders, liste, oge: { id: oge.id, kademe: s.value } }));
    return s;
  }
  function notlariCiz() {
    const ol = $('#notListe'); ol.innerHTML = '';
    for (const n of T.notlar) {
      const bol = el('details', { class: 'sh-bolumler mk-not' }, el('summary', {}, `${n.bolum_sayisi} bölüm, ${n.sozcuk} sözcük`),
        el('ol', {}, n.basliklar.map((b) => el('li', {}, b))));
      ol.append(el('li', {}, el('div', { class: 'mk-ad' }, n.ad), kademeSecimi('notlar', n), bol,
        el('div', { class: 'mk-islem' }, el('button', { class: 'btn small ghost', onclick: () => sil('notlar', n.id) }, 'Çıkar'))));
    }
    if (!T.notlar.length) ol.append(el('li', { class: 'mk-ince' }, 'Henüz not yok.'));
  }
  function vakalariCiz() {
    const ol = $('#vakaListe'); ol.innerHTML = '';
    for (const v of T.vakalar) {
      const li = el('li', {}, el('div', { class: 'mk-ad' }, v.baslik, v.kurgusal ? el('span', { class: 'mk-rol' }, 'kurgusal') : null), kademeSecimi('vakalar', v));
      for (const h of v.hata || []) li.append(el('div', { class: 'mk-not sh-hata' }, h));
      for (const u of v.uyari || []) li.append(el('div', { class: 'mk-not sh-uyari' }, u));
      li.append(el('div', { class: 'mk-islem' }, el('button', { class: 'btn small ghost', onclick: () => sil('vakalar', v.id) }, 'Çıkar')));
      ol.append(li);
    }
    if (!T.vakalar.length) ol.append(el('li', { class: 'mk-ince' }, 'Henüz vaka yok.'));
  }
  async function dosyaGonder(dosya) {
    const kademe = $('#kademeSec').value;
    const vaka = /\.(json|zip)$/i.test(dosya.name);
    mesaj('#dosyaMesaj', `${dosya.name} okunuyor…`);
    try {
      const q = new URLSearchParams({ ders, ad: dosya.name, kademe });
      const r = await api((vaka ? 'vaka?' : 'not?') + q, dosya, true);
      mesaj('#dosyaMesaj', vaka ? `Vaka eklendi: ${r.baslik}${r.hata && r.hata.length ? ' (denetimde sorun var, aşağıya bakın)' : ''}.`
        : `Not eklendi: ${r.bolum_sayisi} bölüm, ${r.sozcuk} sözcük.`, 'iyi');
      await yukle();
    } catch (e) { mesaj('#dosyaMesaj', `${dosya.name}: ${e.message}`, 'kotu'); }
  }
  const birak = $('#dosyaBirak');
  birak.addEventListener('dragover', (e) => { e.preventDefault(); birak.classList.add('ustunde'); });
  birak.addEventListener('dragleave', () => birak.classList.remove('ustunde'));
  birak.addEventListener('drop', (e) => { e.preventDefault(); birak.classList.remove('ustunde'); [...e.dataTransfer.files].forEach(dosyaGonder); });
  $('#dosyaSec').addEventListener('change', (e) => { [...e.target.files].forEach(dosyaGonder); e.target.value = ''; });
  window.addEventListener('dragover', (e) => e.preventDefault());
  window.addEventListener('drop', (e) => e.preventDefault());

  // ---------- 4. Dikkat, yanılgılar, sorular ----------
  function hedefSecimi(deger) {
    const s = el('select', {}, el('option', { value: '' }, 'hedef seçin'));
    for (const h of T.hedefler) s.append(el('option', { value: h.id }, `${h.id} ${h.baslik}`.slice(0, 70)));
    s.value = deger || '';
    return s;
  }
  function listeCiz(liste, hedef) {
    const ol = $(hedef); ol.innerHTML = '';
    for (const x of T[liste]) {
      const g = el('input', { value: x.metin || '' });
      g.addEventListener('change', () => degistir('oge', { ders, liste, oge: { id: x.id, metin: g.value } }));
      const satir = el('div', { class: 'sh-satir' }, g);
      if (liste === 'yanilgilar') {
        const h = hedefSecimi(x.hedef);
        h.addEventListener('change', () => degistir('oge', { ders, liste, oge: { id: x.id, hedef: h.value } }));
        satir.append(h);
      }
      satir.append(el('button', { class: 'btn small ghost', onclick: () => sil(liste, x.id) }, 'Sil'));
      ol.append(el('li', {}, satir));
    }
  }
  function sorulariCiz() {
    const ol = $('#soruListe'); ol.innerHTML = '';
    for (const s of T.sorular) {
      const metin = el('input', { value: s.metin || '' });
      metin.addEventListener('change', () => degistir('oge', { ders, liste: 'sorular', oge: { id: s.id, metin: metin.value } }));
      const bl = secim(s.bloom || 'anla', BLOOM, BLOOM_AD);
      bl.addEventListener('change', () => degistir('oge', { ders, liste: 'sorular', oge: { id: s.id, bloom: bl.value } }));
      const hd = hedefSecimi(s.hedef);
      hd.addEventListener('change', () => degistir('oge', { ders, liste: 'sorular', oge: { id: s.id, hedef: hd.value } }));
      const li = el('li', {}, el('div', { class: 'sh-satir' }, metin), el('div', { class: 'sh-satir' }, bl, hd, kademeSecimi('sorular', s),
        el('button', { class: 'btn small ghost', onclick: () => sil('sorular', s.id) }, 'Sil')));
      if (s.tur === 'secmeli' && s.secenekler) {
        li.append(el('ol', { class: 'mk-not', type: 'A' }, s.secenekler.map((x, i) => el('li', { class: i === s.dogru ? 'sh-tamam' : '' }, x))));
      }
      const ornek = el('textarea', { rows: 2, placeholder: 'Örnek cevap (açık uçlu soruda eğitmen buna göre geri bildirim verir)' });
      ornek.value = s.ornek_cevap || '';
      ornek.addEventListener('change', () => degistir('oge', { ders, liste: 'sorular', oge: { id: s.id, ornek_cevap: ornek.value } }));
      if (s.tur !== 'secmeli') li.append(ornek);
      ol.append(li);
    }
  }
  document.querySelectorAll('[data-ekle]').forEach((b) => b.addEventListener('click', async () => {
    const liste = b.dataset.ekle;
    const g = $('#' + liste + 'Yeni');
    if (!g.value.trim()) return;
    const oge = { metin: g.value.trim() };
    if (liste === 'sorular') Object.assign(oge, { tur: 'acik', bloom: 'anla', kademe: $('#kademeSec').value || 'fakulte' });
    await degistir('oge', { ders, liste, oge });
    g.value = '';
  }));

  // ---------- 5. Öneriler ----------
  function hedefleriCiz() {
    const ol = $('#hedefListe'); ol.innerHTML = '';
    for (const h of T.hedefler) {
      const b = el('input', { value: h.baslik || '' });
      b.addEventListener('change', () => degistir('oge', { ders, liste: 'hedefler', oge: { id: h.id, baslik: b.value } }));
      const bl = secim(h.bloom, BLOOM, BLOOM_AD);
      bl.addEventListener('change', () => degistir('oge', { ders, liste: 'hedefler', oge: { id: h.id, bloom: bl.value } }));
      ol.append(el('li', {}, el('div', { class: 'sh-satir' }, el('strong', {}, h.id), b, bl,
        el('button', { class: 'btn small ghost', onclick: () => sil('hedefler', h.id) }, 'Sil'))));
    }
    if (!T.hedefler.length) ol.append(el('li', { class: 'mk-ince' }, 'Henüz onaylı hedef yok.'));
  }
  function terimleriCiz() {
    const d = $('#terimListe'); d.innerHTML = '';
    for (const x of T.terimler) d.append(el('span', { class: 'sh-terim' }, x.terim, el('button', { title: 'Sil', onclick: () => sil('terimler', x.terim) }, '×')));
    if (!T.terimler.length) d.append(el('span', { class: 'mk-ince' }, 'Henüz onaylı terim yok.'));
  }
  function onerileriCiz() {
    const kutu = $('#oneriListe'); kutu.innerHTML = '';
    const o = T.oneriler || {};
    let sayi = 0;
    for (const tur of ['hedefler', 'terimler', 'sorular', 'yanilgilar']) {
      for (const x of o[tur] || []) {
        sayi++;
        const kart = el('div', { class: 'sh-oneri' }, el('div', { class: 'sh-kim' }, `${TUR_AD[tur]} önerisi · ${x.kim === 'claude' ? 'Claude' : 'hızlı öneri'}`));
        const duz = {};
        if (tur === 'terimler') {
          const g = el('input', { value: x.terim }); duz.terim = () => g.value; kart.append(g);
        } else {
          const g = el('input', { value: x.baslik || x.metin || '' });
          duz[tur === 'hedefler' ? 'baslik' : 'metin'] = () => g.value;
          const satir = el('div', { class: 'sh-satir' }, g);
          if (tur !== 'yanilgilar') { const bl = secim(x.bloom || 'anla', BLOOM, BLOOM_AD); duz.bloom = () => bl.value; satir.append(bl); }
          kart.append(satir);
          if (x.secenekler) kart.append(el('ol', { class: 'mk-not', type: 'A' }, x.secenekler.map((s, i) => el('li', { class: i === x.dogru ? 'sh-tamam' : '' }, s))));
          if (x.ornek_cevap) kart.append(el('div', { class: 'sh-gerekce' }, 'Örnek cevap: ' + x.ornek_cevap));
        }
        if (x.gerekce) kart.append(el('div', { class: 'sh-gerekce' }, x.gerekce));
        kart.append(el('div', { class: 'mk-islem' },
          el('button', { class: 'btn small primary', onclick: () => {
            const d = {}; for (const [k, f] of Object.entries(duz)) d[k] = f();
            degistir('kabul', { ders, tur, oneri_id: x.oneri_id, duzeltme: d }, '#oneriMesaj');
          } }, 'Kabul et'),
          el('button', { class: 'btn small ghost', onclick: () => degistir('reddet', { ders, tur, oneri_id: x.oneri_id }, '#oneriMesaj') }, 'Sil')));
        kutu.append(kart);
      }
    }
    if (!sayi) kutu.append(el('p', { class: 'mk-ince' }, 'Onay bekleyen öneri yok.'));
  }
  $('#kuralDugme').addEventListener('click', () => degistir('oner_kural', { ders }, '#oneriMesaj'));

  // ---------- 6. Denetle ve paketle ----------
  async function denetle() {
    const d = await api('denetle?ders=' + encodeURIComponent(ders)).catch(() => null);
    const k = $('#denetim'); k.innerHTML = '';
    if (!d) return;
    if (!d.hatalar.length) k.append(el('p', { class: 'sh-tamam' }, 'Paketlemeye hazır.'));
    for (const h of d.hatalar) k.append(el('p', { class: 'sh-hata' }, '✗ ' + h));
    for (const u of d.uyarilar) k.append(el('p', { class: 'sh-uyari' }, '! ' + u));
    $('#paketDugme').disabled = d.hatalar.length > 0;
  }
  $('#paketDugme').addEventListener('click', async () => {
    mesaj('#paketMesaj', 'Paketleniyor…');
    try {
      const r = await api('paketle', { ders });
      const m = $('#paketMesaj'); m.innerHTML = '';
      for (const [ad, p] of Object.entries(r.paketler)) {
        const i = p.icerik;
        m.append(el('p', { class: 'iyi' }, `${ad === 'acik' ? 'Herkese açık' : 'Fakülte'} paketi: ${p.dosya} (${p.boyut_kb} KB) · `
          + `${i.hedef} hedef, ${i.makale} makale, ${i.not_sayfasi} not bölümü, ${i.vaka} vaka, ${i.soru} soru`));
      }
      if (r.kuruldu) m.append(el('p', {}, `Ders bu bilgisayara da kuruldu (${r.kuruldu}); canlı tahtada deneyebilirsiniz.`));
      for (const u of r.uyarilar || []) m.append(el('p', { class: 'sh-uyari' }, '! ' + u));
      T = await api('taslak?ders=' + encodeURIComponent(ders));
    } catch (e) { hata('#paketMesaj')(e); }
  });
  $('#paketKlasorDugme').addEventListener('click', () => api('klasor_ac', { ders }).catch(hata('#paketMesaj')));

  // ---------- ortak ----------
  async function degistir(yol, govde, mesajYeri) {
    try {
      const r = await api(yol, govde);
      if (r && r.ders === ders && r.kaynaklar) T = r; else T = await api('taslak?ders=' + encodeURIComponent(ders));
      if (mesajYeri) $(mesajYeri).innerHTML = '';
      ciz();
    } catch (e) { hata(mesajYeri || '#genelMesaj')(e); }
  }
  function sil(liste, id) { return degistir('sil', { ders, liste, id }); }

  $('#dersSec').addEventListener('change', (e) => { ders = e.target.value; yukle(); });
  $('#yeniBaslik').addEventListener('input', (e) => {
    const k = $('#yeniKimlik');
    if (!k.dataset.elle) k.value = e.target.value.toLocaleLowerCase('tr').replace(/[çğıöşü]/g, (c) => ({ ç: 'c', ğ: 'g', ı: 'i', ö: 'o', ş: 's', ü: 'u' }[c]))
      .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 50);
  });
  $('#yeniKimlik').addEventListener('input', (e) => { e.target.dataset.elle = '1'; });
  $('#yeniDugme').addEventListener('click', async () => {
    try {
      const t = await api('yeni', { ders: $('#yeniKimlik').value.trim(), baslik: $('#yeniBaslik').value.trim() });
      ders = t.ders; $('#yeniKutu').open = false; await baslat();
    } catch (e) { hata('#genelMesaj')(e); }
  });
  baslat();
}());
