/* KlinikKoç · Ders hazırlama sihirbazı (öğretmen ekranı). Yerel sunucunun /api/sihirbaz/ isteklerini kullanır. */
(function () {
  'use strict';
  const $ = (s) => document.querySelector(s);
  const BLOOM_AD = { hatirla: 'Hatırla', anla: 'Anla', uygula: 'Uygula', cozumle: 'Çözümle', degerlendir: 'Değerlendir', olustur: 'Oluştur' };
  const TUR_AD = { hedefler: 'Hedef', terimler: 'Terim', sorular: 'Soru', yanilgilar: 'Yanılgı', onemli: 'Önemli nokta', cizimler: 'Çizim / animasyon' };
  const A = (window.AT || {}).anatomi;   // hazır anatomik şablonlar (çizim adımı)
  let KADEME = {};
  let BLOOM = Object.keys(BLOOM_AD);
  let ders = new URLSearchParams(location.search).get('ders') || '';
  let T = null;
  // Tahtanın içinde (katman olarak) açıldıysa "Tahtaya dön" sayfayı değiştirmez, yalnızca katmanı kapatır.
  const GOMULU = window.parent !== window && new URLSearchParams(location.search).get('gomulu') === '1';
  document.addEventListener('DOMContentLoaded', () => {
    const don = $('#tahtayaDon');
    if (!don || !GOMULU) return;
    don.addEventListener('click', (e) => {
      e.preventDefault();
      window.parent.postMessage({ klinikkoc: 'tahtaya-don' }, location.origin);
    });
    const d = $('#derslereDon'); if (d) d.hidden = true;
    const k = $('#kilavuzBag'); if (k) k.target = '_blank';
    // Ana ekranın panelinde açıldıysa "Tahtaya dön" de gerekmez (üstte Canlı tahta düğmesi var).
    if (new URLSearchParams(location.search).get('kabuk') === 'ana') { don.hidden = true; if (k) k.hidden = true; }
  });
  try { localStorage.setItem('klinikkoc-ogretmen', '1'); } catch (e) { /* depolama kapalı */ }
  if (location.protocol === 'file:') {
    // Dosyaya çift tıklanarak açıldı: bu sayfa yerel sunucu olmadan çalışmaz.
    const u = document.createElement('div');
    u.className = 'dp-uyari';
    u.textContent = 'Bu sayfa KlinikKoç açıkken çalışır. Program klasöründeki BASLAT-Windows (Mac\'te BASLAT-Mac) dosyasına çift tıklayın ya da Claude\'a "ders paketi sayfasını aç" deyin.';
    document.addEventListener('DOMContentLoaded', () => document.querySelector('main').prepend(u));
    if (document.readyState !== 'loading') document.querySelector('main').prepend(u);
  }

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
    if (!v.taslaklar.length) { sec.append(el('option', { value: '' }, 'Henüz taslak yok')); $('#yeniKutu').hidden = false; }
    const vk = $('#videoKademe'); vk.innerHTML = '';
    for (const [k, ad] of Object.entries(KADEME)) vk.append(el('option', { value: k }, ad));
    for (const t of v.taslaklar) sec.append(el('option', { value: t.ders }, `${t.baslik || t.ders}${t.paket ? ' · paketlendi ' + t.paket : ''}`));
    if (v.taslaklar.length && !v.taslaklar.some((t) => t.ders === ders)) ders = v.taslaklar[0].ders;
    sec.value = ders;
    if (ders) await yukle();
  }

  async function yukle() {
    try { T = await api('taslak?ders=' + encodeURIComponent(ders)); } catch (e) { return hata('#genelMesaj')(e); }
    $('#icerik').hidden = false; $('#gezin').hidden = false;
    const q = new URLSearchParams(location.search); q.set('ders', ders);
    history.replaceState(null, '', '?' + q);
    ciz();
    adimGit(adim);
  }

  function ciz() {
    document.querySelectorAll('[data-alan]').forEach((g) => { g.value = T[g.dataset.alan] ?? ''; });
    $('#claudeKomut').textContent = `"${T.baslik} dersi için sihirbaz önerilerini hazırla."`;
    kaynaklariCiz(); notlariCiz(); vakalariCiz(); gorselleriCiz(); listeCiz('dikkat', '#dikkatListe'); listeCiz('yanilgilar', '#yanilgiListe');
    listeCiz('onemli', '#onemliListe'); cizimleriCiz(); videolariCiz();
    sorulariCiz(); hedefleriCiz(); terimleriCiz(); onerileriCiz(); denetle(); adimlariCiz();
  }

  // ---------- Adımlar: yanda liste, sağda yalnız seçili adım (sayfa aşağı uzamaz) ----------
  let adim = Math.max(1, parseInt((location.hash || '').replace('#a', ''), 10) || 1);
  const ADIMLAR = [...document.querySelectorAll('#icerik > section')];
  function bekleyenOneri() { return Object.values((T && T.oneriler) || {}).reduce((n, v) => n + (Array.isArray(v) ? v.length : 0), 0); }
  function adimTamam(n) {
    if (!T) return false;
    return [!!T.baslik, T.kaynaklar.length > 0, T.notlar.length + T.vakalar.length > 0, T.hedefler.length > 0,
      (T.cizimler || []).length > 0, (T.videolar || []).length > 0, T.sorular.length > 0,
      T.hedefler.length > 0 && !bekleyenOneri(), !!T.son_paket][n - 1];
  }
  function adimlariCiz() {
    const ol = $('#adimlar'); ol.innerHTML = '';
    ADIMLAR.forEach((sec, i) => {
      const n = i + 1, tamam = adimTamam(n);
      const rozet = n === 8 && bekleyenOneri() ? el('span', { class: 'sh-rozet' }, String(bekleyenOneri())) : null;
      ol.append(el('li', {}, el('button', { type: 'button', class: (n === adim ? 'secili ' : '') + (tamam ? 'tamam' : ''), 'aria-current': n === adim ? 'step' : null,
        onclick: () => adimGit(n) }, el('span', { class: 'sh-kure' }, tamam && n !== adim ? '✓' : String(n)), el('span', {}, sec.dataset.adim, rozet))));
    });
  }
  function adimGit(n) {
    adim = Math.min(ADIMLAR.length, Math.max(1, n));
    ADIMLAR.forEach((sec, i) => { sec.hidden = i + 1 !== adim; });
    $('#geriDugme').disabled = adim === 1;
    $('#ileriDugme').hidden = adim === ADIMLAR.length;
    try { history.replaceState(null, '', location.search + '#a' + adim); } catch (e) { /* yok */ }
    $('#icerik').scrollTop = 0;
    adimlariCiz();
    if (adim === 9) denetle();
  }
  $('#geriDugme').addEventListener('click', () => adimGit(adim - 1));
  $('#ileriDugme').addEventListener('click', () => { if (document.activeElement && document.activeElement.blur) document.activeElement.blur(); adimGit(adim + 1); });
  $('#yeniAc').addEventListener('click', () => { $('#yeniKutu').hidden = !$('#yeniKutu').hidden; if (!$('#yeniKutu').hidden) $('#yeniBaslik').focus(); });
  $('#claudeKopyala').addEventListener('click', async (e) => {
    try { await navigator.clipboard.writeText($('#claudeKomut').textContent.replace(/^"|"$/g, '')); e.target.textContent = 'Kopyalandı ✓'; } catch (x) { /* elle kopyalanır */ }
  });

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
      const li = el('li', {}, el('div', { class: 'mk-ad' }, n.ad), kademeSecimi('notlar', n), bol,
        el('div', { class: 'mk-islem' }, el('button', { class: 'btn small ghost', onclick: () => sil('notlar', n.id) }, 'Çıkar')));
      if (n.yayin_izi) {
        // Yayımlanmış makaleye benzeyen not: metni pakete girmeden önce öğretmen paylaşma hakkını onaylar.
        const kutu = el('input', { type: 'checkbox' });
        kutu.checked = !!n.izinli;
        kutu.addEventListener('change', () => degistir('oge', { ders, liste: 'notlar', oge: { id: n.id, izinli: kutu.checked } }));
        li.append(el('div', { class: 'mk-not sh-hata' }, 'Yayımlanmış bir makaleye benziyor (' + n.yayin_izi.join(', ') +
          '). Abonelikli makalenin metni pakete giremez; makaleyi DOI ile Kaynaklar\'a ekleyin.'),
          el('label', { class: 'mk-ince' }, kutu, ' Paylaşma hakkım var (metin benim, açık lisanslı ya da yayıncı izni var)'));
      }
      ol.append(li);
    }
    if (!T.notlar.length) ol.append(el('li', { class: 'mk-ince' }, 'Henüz not yok.'));
  }
  function gorselleriCiz() {
    const ol = $('#gorselListe'); ol.innerHTML = '';
    for (const g of T.gorseller || []) {
      const m = g.makaleden || {};
      ol.append(el('li', {}, el('div', { class: 'mk-ad' }, (g.baslik || g.id) + (g.aciklama ? ' · ' + g.aciklama : '')),
        el('div', { class: 'mk-ince' }, `${m.kaynak}, sayfa ${m.sayfa}${m.bolge ? ', bölge ' + m.bolge.join(' ') : ', bütün sayfa'}`),
        el('div', { class: 'mk-islem' }, el('button', { class: 'btn small ghost', onclick: () => sil('gorseller', g.id) }, 'Çıkar'))));
    }
    if (!(T.gorseller || []).length) ol.append(el('li', { class: 'mk-ince' }, 'Henüz şekil yok.'));
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
      if (liste === 'yanilgilar' || liste === 'onemli') {
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
      // Seçenekler: her satıra bir; doğrunun başına * konur. Açık uçlu soruda öğrenci takılınca gösterilir.
      const secMetin = el('textarea', { rows: 3, class: 'sh-secenek', placeholder: s.tur === 'secmeli'
        ? 'Seçenekler: her satıra bir, doğrunun başına * koyun'
        : 'Takılırsa gösterilecek seçenekler (isteğe bağlı): her satıra bir, doğrunun başına * koyun' });
      secMetin.value = (s.secenekler || []).map((x, i) => (i === s.dogru ? '* ' : '') + x).join('\n');
      secMetin.addEventListener('change', () => {
        const satirlar = secMetin.value.split('\n').map((x) => x.trim()).filter(Boolean);
        const dogru = satirlar.findIndex((x) => x.startsWith('*'));
        const secenekler = satirlar.map((x) => x.replace(/^\*\s*/, ''));
        degistir('oge', { ders, liste: 'sorular', oge: { id: s.id, secenekler, dogru: dogru < 0 ? null : dogru } });
      });
      li.append(el('div', { class: 'sh-gerekce' }, s.tur === 'secmeli' ? 'Seçmeli soru' : 'Açık uçlu: önce seçeneksiz sorulur'), secMetin);
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
    let oge = { metin: g.value.trim() };
    if (liste === 'hedefler') oge = { baslik: g.value.trim(), bloom: 'anla' };
    if (liste === 'terimler') oge = { terim: g.value.trim() };
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
    for (const tur of ['hedefler', 'onemli', 'cizimler', 'terimler', 'sorular', 'yanilgilar']) {
      for (const x of o[tur] || []) {
        sayi++;
        const kart = el('div', { class: 'sh-oneri' }, el('div', { class: 'sh-kim' }, `${TUR_AD[tur]} önerisi · ${x.kim === 'claude' ? 'Claude' : 'hızlı öneri'}`));
        const duz = {};
        if (tur === 'terimler') {
          const g = el('input', { value: x.terim }); duz.terim = () => g.value; kart.append(g);
        } else if (tur === 'cizimler') {
          const g = el('input', { value: x.baslik || '' }); duz.baslik = () => g.value;
          const tarif = el('textarea', { rows: 2 }); tarif.value = x.tarif || ''; duz.tarif = () => tarif.value;
          const bilinen = A && A.SABLONLAR[x.sablon];
          kart.append(g, el('div', { class: 'sh-gerekce' + (bilinen ? '' : ' sh-hata') },
            bilinen ? `Şablon: ${bilinen.ad || x.sablon} · ${x.varyant || bilinen.varyantlar[0]}${x.bitis ? ' → ' + x.bitis + ' (' + (x.sure_sn || 3) + ' sn canlandırma)' : ''}`
              : `Bilinmeyen şablon: ${x.sablon}. Kabul ederseniz 5. adımda şablonu siz seçin.`), tarif);
        } else {
          const g = el('input', { value: x.baslik || x.metin || '' });
          duz[tur === 'hedefler' ? 'baslik' : 'metin'] = () => g.value;
          const satir = el('div', { class: 'sh-satir' }, g);
          if (tur !== 'yanilgilar' && tur !== 'onemli') { const bl = secim(x.bloom || 'anla', BLOOM, BLOOM_AD); duz.bloom = () => bl.value; satir.append(bl); }
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

  // ---------- 5. Çizim ve animasyonlar ----------
  const kareler = new WeakMap();
  function onizle(svg, c, canlandir) {
    if (!A || !A.SABLONLAR[c.sablon]) return;
    cancelAnimationFrame(kareler.get(svg) || 0);
    const cizim = (varyant, p) => { while (svg.firstChild) svg.removeChild(svg.firstChild);
      try { A.ciz(svg, { template: c.sablon, variant: varyant, labels: p ? [] : 'hepsi', p }, true); } catch (e) { /* şablon çizilemedi */ } };
    const bas = c.varyant || A.SABLONLAR[c.sablon].varyantlar[0];
    if (!canlandir || !c.bitis || c.bitis === bas) { cizim(canlandir && c.bitis ? c.bitis : bas); return; }
    const d0 = A.durum(c.sablon, bas), d1 = A.durum(c.sablon, c.bitis);
    if (!d0 || !d1) { cizim(c.bitis); return; }
    const t0 = performance.now(), sure = (c.sure_sn || 3) * 1000;
    const kare = (t) => {
      const k = Math.min(1, (t - t0) / sure), e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      if (k < 1) { cizim(c.bitis, A.araDurum(c.sablon, d0, d1, e)); kareler.set(svg, requestAnimationFrame(kare)); } else cizim(c.bitis);
    };
    cizim(bas);
    kareler.set(svg, requestAnimationFrame(kare));
  }
  function cizimleriCiz() {
    const kutu = $('#cizimListe'); kutu.innerHTML = '';
    if (!A) { kutu.append(el('p', { class: 'sh-hata' }, 'Şablonlar yüklenemedi.')); return; }
    const sablonlar = Object.keys(A.SABLONLAR);
    for (const c of T.cizimler || []) {
      const kaydet = (alan) => degistir('oge', { ders, liste: 'cizimler', oge: Object.assign({ id: c.id }, alan) });
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('viewBox', '0 0 160 90'); svg.setAttribute('class', 'sh-onizleme'); svg.setAttribute('role', 'img');
      svg.setAttribute('aria-label', c.baslik || c.sablon);
      const S = A.SABLONLAR[c.sablon];
      const varyantlar = S ? S.varyantlar : [];
      const baslik = el('input', { value: c.baslik || '', placeholder: 'Çizimin adı (ör. Periodontal cep oluşumu)' });
      baslik.addEventListener('change', () => kaydet({ baslik: baslik.value }));
      const sb = secim(c.sablon, sablonlar, Object.fromEntries(sablonlar.map((k) => [k, A.SABLONLAR[k].ad || k])));
      sb.addEventListener('change', () => kaydet({ sablon: sb.value, varyant: A.SABLONLAR[sb.value].varyantlar[0], bitis: '' }));
      const vr = secim(c.varyant || varyantlar[0], varyantlar.length ? varyantlar : ['']);
      vr.addEventListener('change', () => kaydet({ varyant: vr.value }));
      const bt = secim(c.bitis || '', [''].concat(varyantlar), { '': 'yok (durağan çizim)' });
      bt.addEventListener('change', () => kaydet({ bitis: bt.value }));
      const sure = el('input', { type: 'number', min: 1, max: 20, value: c.sure_sn || 3, 'aria-label': 'Geçiş süresi (saniye)' });
      sure.addEventListener('change', () => kaydet({ sure_sn: sure.value }));
      const tarif = el('textarea', { rows: 2, placeholder: c.bitis ? 'Animasyon tarifi: çizim akarken eğitmen ne söylesin?' : 'Eğitmen bu çizimde neyi göstersin? (isteğe bağlı)' });
      tarif.value = c.tarif || '';
      tarif.addEventListener('change', () => kaydet({ tarif: tarif.value }));
      const hd = hedefSecimi(c.hedef);
      hd.addEventListener('change', () => kaydet({ hedef: hd.value }));
      const oynat = el('button', { class: 'btn small', type: 'button', onclick: () => onizle(svg, c, true) }, c.bitis ? '▶ Canlandır' : '↻ Yeniden çiz');
      kutu.append(el('div', { class: 'sh-cizim' }, el('div', { class: 'sh-cizim-sol' }, svg, oynat),
        el('div', { class: 'sh-form' }, baslik,
          el('div', { class: 'sh-satir' }, el('label', {}, 'Şablon ', sb), el('label', {}, 'Başlangıç durumu ', vr)),
          el('div', { class: 'sh-satir' }, el('label', {}, 'Bitiş durumu (animasyon) ', bt), c.bitis ? el('label', { class: 'sh-dar' }, 'Süre (sn) ', sure) : null),
          tarif, el('div', { class: 'sh-satir' }, hd, el('button', { class: 'btn small ghost', onclick: () => sil('cizimler', c.id) }, 'Sil')))));
      onizle(svg, c, false);
    }
    if (!(T.cizimler || []).length) kutu.append(el('p', { class: 'mk-ince' }, 'Henüz çizim seçilmedi. Seçmezseniz eğitmen konuya uyan şablonu kendisi seçer.'));
  }
  $('#cizimEkle').addEventListener('click', () => {
    if (!A) return;
    const ilk = Object.keys(A.SABLONLAR)[0];
    degistir('oge', { ders, liste: 'cizimler', oge: { sablon: ilk, varyant: A.SABLONLAR[ilk].varyantlar[0], baslik: '' } });
  });

  // ---------- 6. Videolar ----------
  const ytKimlik = (a) => { const m = /(?:youtu\.be\/|youtube(?:-nocookie)?\.com\/(?:watch\?(?:.*&)?v=|embed\/|shorts\/|live\/))([A-Za-z0-9_-]{11})/.exec(a || ''); return m ? m[1] : null; };
  const sureYaz = (sn) => (sn === null || sn === undefined || sn === '') ? '' : `${Math.floor(sn / 60)}:${String(sn % 60).padStart(2, '0')}`;
  function videolariCiz() {
    const ol = $('#videoListe'); ol.innerHTML = '';
    for (const v of T.videolar || []) {
      const kaydet = (alan) => degistir('oge', { ders, liste: 'videolar', oge: Object.assign({ id: v.id }, alan) }, '#videoMesaj');
      const baslik = el('input', { value: v.baslik || '', placeholder: 'Videonun adı' });
      baslik.addEventListener('change', () => kaydet({ baslik: baslik.value }));
      const bas = el('input', { value: sureYaz(v.baslangic), placeholder: 'başlangıç 0:00', 'aria-label': 'Başlangıç' });
      bas.addEventListener('change', () => kaydet({ baslangic: bas.value }));
      const bit = el('input', { value: sureYaz(v.bitis), placeholder: 'bitiş', 'aria-label': 'Bitiş' });
      bit.addEventListener('change', () => kaydet({ bitis: bit.value }));
      const hd = hedefSecimi(v.hedef);
      hd.addEventListener('change', () => kaydet({ hedef: hd.value }));
      const yt = v.tur !== 'dosya';
      const li = el('li', {}, el('div', { class: 'mk-ad' }, yt ? 'YouTube' : 'Kendi videom', el('span', { class: 'mk-rol' }, yt ? 'internet ister' : `${((v.boyut || 0) / 1048576).toFixed(1)} MB`)),
        el('span', { class: 'mk-etiket ' + (yt ? 'calisiyor' : 'hazir') }, yt ? 'bağlantı' : 'dosya'),
        el('div', { class: 'mk-atif' }, yt ? el('a', { href: v.adres, target: '_blank', rel: 'noopener' }, v.adres) : v.dosya),
        el('div', { class: 'sh-satir mk-not' }, baslik), el('div', { class: 'sh-satir mk-not' }, el('span', { class: 'sh-dar' }, bas), el('span', { class: 'sh-dar' }, bit), hd,
          yt ? null : kademeSecimi('videolar', v), el('button', { class: 'btn small ghost', onclick: () => sil('videolar', v.id) }, 'Sil')));
      ol.append(li);
    }
    if (!(T.videolar || []).length) ol.append(el('li', { class: 'mk-ince' }, 'Henüz video yok.'));
  }
  $('#ytEkle').addEventListener('click', async () => {
    const adres = $('#ytAdres').value.trim();
    if (!ytKimlik(adres)) return mesaj('#videoMesaj', 'Bu bir YouTube bağlantısı değil. Videonun adresini tarayıcının adres çubuğundan kopyalayın.', 'kotu');
    await degistir('oge', { ders, liste: 'videolar', oge: { tur: 'youtube', adres, baslik: $('#ytBaslik').value.trim(), baslangic: $('#ytBas').value, bitis: $('#ytBit').value, kademe: 'acik' } }, '#videoMesaj');
    for (const k of ['#ytAdres', '#ytBaslik', '#ytBas', '#ytBit']) $(k).value = '';
  });
  async function videoGonder(dosya) {
    mesaj('#videoMesaj', `${dosya.name} kopyalanıyor…`);
    try {
      await api('video?' + new URLSearchParams({ ders, ad: dosya.name, kademe: $('#videoKademe').value || 'fakulte' }), dosya, true);
      mesaj('#videoMesaj', `${dosya.name} eklendi.`, 'iyi');
      await yukle();
    } catch (e) { mesaj('#videoMesaj', `${dosya.name}: ${e.message}`, 'kotu'); }
  }
  const vBirak = $('#videoBirak');
  vBirak.addEventListener('dragover', (e) => { e.preventDefault(); vBirak.classList.add('ustunde'); });
  vBirak.addEventListener('dragleave', () => vBirak.classList.remove('ustunde'));
  vBirak.addEventListener('drop', (e) => { e.preventDefault(); vBirak.classList.remove('ustunde'); [...e.dataTransfer.files].forEach(videoGonder); });
  $('#videoSec').addEventListener('change', (e) => { [...e.target.files].forEach(videoGonder); e.target.value = ''; });

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
          + `${i.hedef} hedef, ${i.makale} makale, ${i.not_sayfasi} not bölümü, ${i.vaka} vaka, ${i.soru} soru, `
          + `${i.onemli || 0} önemli nokta, ${i.cizim || 0} çizim, ${i.video || 0} video`));
      }
      if (r.kuruldu) m.append(el('p', {}, `Ders bu bilgisayara da kuruldu (${r.kuruldu}); canlı tahtada deneyebilirsiniz.`));
      for (const u of r.uyarilar || []) m.append(el('p', { class: 'sh-uyari' }, '! ' + u));
      T = await api('taslak?ders=' + encodeURIComponent(ders));
      adimlariCiz();
      if (window.KK) window.KK.degisti();
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

  $('#dersSec').addEventListener('change', (e) => { ders = e.target.value; adim = 1; yukle(); });
  $('#yeniBaslik').addEventListener('input', (e) => {
    const k = $('#yeniKimlik');
    if (!k.dataset.elle) k.value = e.target.value.toLocaleLowerCase('tr').replace(/[çğıöşü]/g, (c) => ({ ç: 'c', ğ: 'g', ı: 'i', ö: 'o', ş: 's', ü: 'u' }[c]))
      .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 50);
  });
  $('#yeniKimlik').addEventListener('input', (e) => { e.target.dataset.elle = '1'; });
  $('#yeniDugme').addEventListener('click', async () => {
    try {
      const t = await api('yeni', { ders: $('#yeniKimlik').value.trim(), baslik: $('#yeniBaslik').value.trim() });
      ders = t.ders; $('#yeniKutu').hidden = true; adim = 1; await baslat();
    } catch (e) { hata('#genelMesaj')(e); }
  });
  baslat();
}());
