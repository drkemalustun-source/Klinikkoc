/* Canlı tahta: Claude'un gönderdiği komutları tahtaya çizer ve anlatır.
 *
 * Akış: Claude masaüstü uygulaması → tools/tahta-mcp.py → tools/sunucu.py (/api/canli/)
 *       → bu sayfa (uzun yoklama) → tahta + ses → sonuç sunucuya → Claude'a.
 *
 * Komut türleri (sunucudan gelir, her birinin "no"su vardır):
 *   adimlar : { ders?, adimlar: [{ komutlar: [tahta komutu...], anlat: "metin" }] }
 *             Tahta komutları ders dosyasındakilerle aynıdır (bkz. js/board.js).
 *   soru    : { soru, secenekler: [..], dogru?, aciklama?, anlat? } → tıklanan cevap döner
 *   temizle : tahtayı siler
 *   dur     : anlatımı hemen keser, sıradaki komutları iptal eder
 *   devam   : sözü kesilen anlatımı kaldığı yerden sürdürür ({ birak: true } ise bırakır)
 * Dikte: mikrofon tuşu (ya da M) konuşmayı tarayıcının Türkçe tanıyıcısıyla yazıya çevirir ve
 *   /api/canli/soyle ile sunucuya bırakır. Anlatım sürerken basılırsa anlatım duraklar (söz alma); Claude'un
 *   bekleyen tahta çağrısı sözü hemen alır. Claude'un cevabı (yeni tahta komutu) araya girer; tahta cevaptan
 *   sonra eski hâline döner ve 'devam' komutuyla anlatım kaldığı cümleden sürer.
 * Claude dinlemiyorken söylenenler için üstte uyarı ve "Sohbete kopyala" düğmesi çıkar; üst çubuktaki
 *   ışık Claude'un dinleyip dinlemediğini gösterir.
 * Duraklat: ⏸ tuşu (ya da P / Boşluk) anlatımı iptal etmeden bekletir; yeniden basınca aynı cümlenin
 *   kaldığı yerinden sürer. Sunucuya /api/canli/duraklat ile bildirilir; Claude 'duraklatildi' görür.
 * Ses: bu bilgisayardaki sunucu sesi (/api/canli/ses; ses/ses-ayari.json, varsayılan Pocket TTS kadın 3,
 *   yedek Piper dfki); o da yoksa tarayıcının Türkçe sesi. */
(function (AT) {
  'use strict';

  const $ = (s) => document.querySelector(s);
  const boardEl = $('#board');
  const qEl = $('#question');
  const capEl = $('#caption');
  const dot = $('#dot');
  const durumEl = $('#durum');
  const dersAdiEl = $('#dersAdi');

  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  let toastTimer = null;
  function toast(msg, ms = 4000) {
    const t = $('#toast');
    t.textContent = msg;
    t.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { t.hidden = true; }, ms);
  }

  async function api(yol, govde) {
    const r = await fetch('/api/canli/' + yol, govde === undefined ? { cache: 'no-store' } : {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(govde)
    });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).hata || ('HTTP ' + r.status));
    return r;
  }

  // ---------- Ses ----------
  const HIZLAR = [1, 1.2, 1.4];
  let hiz = Number(AT.prefs.get('canliHiz')) || 1.2;
  const duz = (t) => String(t || '').replace(/\*\*|(?<!\w)_|_(?!\w)/g, '').replace(/\{\d+\}/g, '').replace(/\s+/g, ' ').trim();

  const ses = {
    token: 0,
    audio: new Audio(),
    piperVar: true,
    web: new AT.speech.WebSpeechEngine('tr-TR'),
    konusuyor: false,

    async wav(metin) {
      const r = await api('ses', { metin });
      return URL.createObjectURL(await r.blob());
    },

    // Döner: 'kesildi' (durduruldu ya da araya cevap girdi) ya da undefined (bitti).
    // secenek.bas: kaçıncı cümleden başlansın; secenek.cumle(i): okunan cümle bildirilir (kaldığı yer için).
    async anlat(metin, secenek = {}) {
      metin = duz(metin);
      if (!metin) return;
      if (mik.aktif) mik.bitir(); // tahta konuşurken mikrofon kendi sesini duymasın
      const my = ++this.token;
      this.konusuyor = true;
      dot.classList.add('konusuyor');
      try {
        const cumleler = AT.speech.sentences(metin);
        const bas = Math.max(0, Math.min(secenek.bas || 0, cumleler.length - 1));
        let sonraki = this.piperVar ? this.wav(cumleler[bas]).catch(() => null) : null;
        for (let i = bas; i < cumleler.length; i++) {
          await durak.bekle();
          if (my !== this.token) return 'kesildi';
          if (secenek.cumle) secenek.cumle(i);
          const url = sonraki ? await sonraki : null;
          sonraki = this.piperVar && i + 1 < cumleler.length ? this.wav(cumleler[i + 1]).catch(() => null) : null;
          capEl.classList.remove('siz');
          capEl.textContent = cumleler[i];
          await durak.bekle();
          if (my !== this.token) { if (url) URL.revokeObjectURL(url); return 'kesildi'; }
          if (url) {
            await this.cal(url, my);
            URL.revokeObjectURL(url);
            if (my !== this.token) return 'kesildi';
          } else {
            if (this.piperVar) {
              this.piperVar = false;
              toast('Piper sesi bulunamadı; tarayıcının Türkçe sesi kullanılıyor.');
            }
            this.web.setRate(hiz);
            let j = i;
            await this.web.speak(cumleler.slice(i).join(' '), { onSentence: (s) => {
              capEl.textContent = s;
              if (secenek.cumle) secenek.cumle(j++);
            } });
            return my !== this.token ? 'kesildi' : undefined;
          }
        }
      } finally {
        if (my === this.token) { this.konusuyor = false; dot.classList.remove('konusuyor'); }
      }
    },

    cal(url, my) {
      return new Promise((resolve) => {
        const a = this.audio;
        let bitti = false;
        // Ses öğesi tek; araya giren bir cevap onu devralmış olabilir: yalnız kendi işleyicilerimizi temizle.
        const benim = () => a.onended === son;
        const son = () => {
          if (bitti) return;
          bitti = true;
          clearInterval(iv);
          if (benim()) { this.caliyor = false; a.onended = a.onerror = null; }
          resolve();
        };
        this.caliyor = true;
        a.onended = son;
        a.onerror = son;
        a.src = url;
        a.playbackRate = hiz;
        (durak.aktif ? Promise.resolve() : a.play()).catch(() => {
          // Tarayıcı sesi engelledi: başlat ekranı yeniden gösterilir, metin altyazıda kalır.
          $('#baslat').hidden = false;
          son();
        });
        const iv = setInterval(() => { if (my !== this.token) { if (benim()) a.pause(); son(); } }, 150);
      });
    },

    dur() {
      this.token++;
      this.audio.pause();
      this.web.stop();
      this.konusuyor = false;
      dot.classList.remove('konusuyor');
    }
  };

  // ---------- Duraklat ----------
  // Anlatımı iptal etmeden bekletir: çalan ses olduğu yerde durur, cümle ve adım döngüleri durak.bekle()'de
  // bekler. Devam'da ses aynı noktadan sürer. Yalnız anlatım varken (soru kartı ve dikte dışında) etkindir.
  const durakBtn = $('#duraklat');
  const durakIsaret = $('#durakIsaret');
  const durak = {
    aktif: false,
    soz: false, // kullanıcı mikrofonla söz aldığı için duraklatıldı
    bekleyenler: [],
    kullanilabilir() {
      if (askidaki() && !araCalisan && !mik.aktif) return true; // ▶: araya girilen anlatıma dön
      return !mik.aktif && qEl.hidden && (ses.konusuyor || !!(calisan && calisan.tur === 'adimlar'));
    },
    bekle() {
      return this.aktif ? new Promise((r) => this.bekleyenler.push(r)) : Promise.resolve();
    },
    degistir() {
      if (this.aktif) this.devam();
      else if (askidaki() && !araCalisan) anlatimaDon(null);
      else this.duraklat();
    },
    duraklat(neden) {
      if (this.aktif) { if (neden === 'soz') { this.soz = true; this.goster(); } return; }
      if (!this.kullanilabilir()) return;
      this.aktif = true;
      this.soz = neden === 'soz';
      ses.audio.pause();
      try { if (window.speechSynthesis) speechSynthesis.pause(); } catch (e) { /* yok */ }
      this.goster();
      api('duraklat', { duraklatildi: true, durum: durum() }).catch(() => {});
    },
    devam() {
      if (!this.aktif) return;
      this.aktif = false;
      this.soz = false;
      if (ses.caliyor) ses.audio.play().catch(() => {});
      try { if (window.speechSynthesis) speechSynthesis.resume(); } catch (e) { /* yok */ }
      this.birak();
      api('duraklat', { duraklatildi: false, durum: durum() }).catch(() => {});
    },
    // Durdur ya da söz alma: duraklama kalkar, bekleyen döngüler bırakılır (onlar iptali görüp çıkar).
    sifirla() {
      this.soz = false;
      if (!this.aktif) return;
      this.aktif = false;
      try { if (window.speechSynthesis) speechSynthesis.resume(); } catch (e) { /* yok */ }
      this.birak();
      api('duraklat', { duraklatildi: false }).catch(() => {});
    },
    birak() {
      const b = this.bekleyenler.splice(0);
      b.forEach((r) => r());
      this.goster();
    },
    goster() {
      durakBtn.classList.toggle('duraklatildi', this.aktif);
      durakBtn.setAttribute('aria-pressed', String(this.aktif));
      durakBtn.setAttribute('aria-label', this.aktif ? 'Devam' : 'Duraklat');
      durakBtn.title = this.aktif ? 'Devam: kaldığı yerden sürer (P ya da Boşluk)'
        : 'Duraklat: anlatımı bekletir, yeniden basınca kaldığı yerden sürer (P ya da Boşluk)';
      durakBtn.disabled = !this.aktif && !this.kullanilabilir();
      durakIsaret.hidden = !this.aktif;
      durakIsaret.textContent = this.soz ? '🎤 Söz sizde · anlatım bekliyor (devam için ▶)'
        : '⏸ Duraklatıldı · devam için ▶, P ya da Boşluk';
      if (this.aktif) durumEl.textContent = this.soz ? 'Söz sizde · anlatım kaldığı yerde bekliyor' : 'Duraklatıldı · devam için ▶';
      else if (calisan && calisan.tur === 'adimlar') durumEl.textContent = 'Claude anlatıyor';
    }
  };
  durakBtn.addEventListener('click', () => durak.degistir());
  // Tuşun etkin/sönük hali anlatım, soru kartı ve dikte değiştikçe güncellenir.
  setInterval(() => { if (!durak.aktif) durakBtn.disabled = !durak.kullanilabilir(); }, 250);

  // ---------- Dikte (mikrofon) ----------
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const mikBtn = $('#mik');
  if (!SR) {
    mikBtn.disabled = true;
    mikBtn.title = 'Bu tarayıcıda konuşma tanıma yok (Chrome ya da Edge gerekir).';
  }
  let sozAlindi = false;
  let sozBitti = null;     // soru kartında söz alınınca: söz sunucuya ulaşınca çözülür
  let sozBittiCoz = null;
  const mik = {
    rec: null,
    aktif: false,
    metin: '',
    sessizT: null,

    baslat() {
      if (!SR) return toast('Bu tarayıcıda konuşma tanıma yok; Chrome ya da Edge kullanın.');
      if (this.aktif) return this.bitir();
      // Söz almak: anlatım sürüyorsa kaldığı yerde duraklar (Claude'un bekleyen çağrısı sözü hemen alır);
      // soru kartı açıksa kart kapanır.
      const anlatan = araCalisan || (calisan && !calisan.askida ? calisan : null);
      if (anlatan && anlatan.tur === 'adimlar') {
        durak.duraklat('soz');
      } else if (ses.konusuyor || calisan || sira.length) {
        sozAlindi = true;
        sozBitti = new Promise((r) => { sozBittiCoz = r; });
        durdur(null);
      }
      const rec = new SR();
      rec.lang = 'tr-TR';
      rec.continuous = true;
      rec.interimResults = true;
      rec.maxAlternatives = 1;
      const finals = [];
      this.rec = rec;
      this.aktif = true;
      this.metin = '';
      mikBtn.classList.add('dinliyor');
      durumEl.textContent = 'Dinleniyor · susunca gönderilir (bitirmek için yeniden dokunun)';
      capEl.classList.add('siz');
      capEl.textContent = '🎤 Dinliyorum…';
      this.sure(8000); // hiç konuşulmazsa 8 sn sonra kapanır
      rec.onresult = (ev) => {
        let ara = '';
        for (let i = ev.resultIndex; i < ev.results.length; i++) {
          const r = ev.results[i];
          if (r.isFinal) finals.push(r[0].transcript.trim());
          else ara += r[0].transcript;
        }
        this.metin = finals.join(' ');
        capEl.textContent = '🎤 ' + (this.metin + ' ' + ara).trim();
        this.sure(2500); // 2,5 sn susunca gönder
      };
      rec.onerror = (ev) => {
        if (ev.error === 'not-allowed' || ev.error === 'service-not-allowed') {
          toast('Mikrofon izni verilmedi. Adres çubuğundaki simgeden mikrofona izin verin.', 7000);
        } else if (ev.error === 'network') {
          toast('Konuşma tanıma için internet bağlantısı gerekiyor.', 6000);
        } else if (ev.error === 'audio-capture') {
          toast('Mikrofon bulunamadı.', 6000);
        } else if (ev.error !== 'no-speech' && ev.error !== 'aborted') {
          toast('Konuşma tanıma hatası: ' + ev.error);
        }
      };
      rec.onend = () => this.gonder();
      try {
        rec.start();
      } catch (e) {
        this.aktif = false;
        this.rec = null;
        mikBtn.classList.remove('dinliyor');
        toast('Mikrofon açılamadı: ' + e.message);
      }
    },

    sure(ms) {
      clearTimeout(this.sessizT);
      this.sessizT = setTimeout(() => this.bitir(), ms);
    },

    bitir() {
      clearTimeout(this.sessizT);
      if (this.rec) { try { this.rec.stop(); } catch (e) { /* zaten durdu */ } }
    },

    async gonder() {
      if (!this.aktif) return;
      this.aktif = false;
      this.rec = null;
      clearTimeout(this.sessizT);
      mikBtn.classList.remove('dinliyor');
      if (!calisan) durumEl.textContent = hazirYazisi();
      const metin = this.metin.trim();
      this.metin = '';
      if (!metin) {
        capEl.classList.remove('siz');
        capEl.textContent = '';
        toast('Ses algılanmadı.');
        if (durak.soz) durak.devam(); // söz alınıp bir şey söylenmediyse anlatım sürer
        this.sozBitir();
        return;
      }
      capEl.textContent = 'Siz: ' + metin;
      try {
        const r = await api('soyle', { metin });
        const j = await r.json();
        if (j.claude_dinliyor) {
          toast('Claude\'a iletildi.', 4000);
          if (durak.soz) durumEl.textContent = 'Sorunuz Claude\'a iletildi · anlatım kaldığı yerde bekliyor';
        } else {
          bekleyenGoster([metin]);
        }
      } catch (e) {
        toast('Gönderilemedi: ' + e.message + ' (sunucu yeniden başlatılmalı olabilir)', 7000);
      }
      this.sozBitir();
    },

    sozBitir() {
      if (sozBittiCoz) { const c = sozBittiCoz; sozBittiCoz = null; c(); }
    }
  };
  mikBtn.addEventListener('click', () => mik.baslat());

  // ---------- Ders (görseller için) ----------
  let ders = { assets: {} };
  let dersId = null;
  let board = new AT.Board(boardEl, ders);

  async function egitmenDersi(id, base, ilkHata) {
    const r = await fetch(base + 'egitmen.json', { cache: 'no-store' });
    if (!r.ok) throw ilkHata;
    const eg = await r.json();
    const assets = {};
    for (const [k, g] of Object.entries(eg.gorseller || {})) {
      assets[k] = { src: g.src, caption: (g.baslik ? g.baslik + '. ' : '') + (g.aciklama || ''), alt: g.aciklama || k };
    }
    const kay = eg.kaynak || {};
    for (let i = 1; kay.sayfaGorseli && i <= (kay.sayfaSayisi || 0); i++) {
      const nn = String(i).padStart(2, '0');
      assets['sayfa-' + nn] = { src: kay.sayfaGorseli.replace('{nn}', nn), caption: 'Kaynak, sayfa ' + i, alt: 'Kaynak sayfa ' + i };
    }
    return { id, title: eg.baslik || id, assets, _base: base, source: { label: kay.tur === 'ders notu' ? 'Ders notu' : 'Makale' } };
  }

  async function dersYukle(id) {
    if (!id || id === dersId) return;
    let giris = null;
    try {
      const k = await AT.loadCatalog();
      giris = (k.lessons || []).find((l) => l.id === id);
    } catch (e) { /* katalog yoksa doğrudan klasöre bakılır */ }
    giris = giris || { id, path: 'lessons/' + id + '/' };
    try {
      ders = await AT.loadLesson(giris);
    } catch (e) {
      // Yalnız canlı eğitmenle çalışılan ders: ders.json yok, egitmen.json var.
      ders = await egitmenDersi(id, giris.path.replace(/\/?$/, '/'), e);
    }
    dersId = id;
    board = new AT.Board(boardEl, ders);
    dersAdiEl.textContent = 'Canlı tahta · ' + (ders.title || id);
  }

  function durum() {
    const h = boardEl.querySelector('.board-title h2');
    return {
      ders: dersId,
      baslik: h ? h.textContent : '',
      gorsel: !!board.figure,
      soruAcik: !qEl.hidden,
      konusuyor: ses.konusuyor,
      duraklatildi: durak.aktif,
      kaldigi_yer: kaldigiYer(),
      hiz
    };
  }

  function kaldigiYer() {
    if (!calisan || calisan.tur !== 'adimlar') return null;
    const toplam = Array.isArray(calisan.adimlar) ? calisan.adimlar.length : 0;
    return { no: calisan.no, adim: Math.min((calisan.adim || 0) + 1, toplam), toplam,
             askida: !!calisan.askida, araya_giren: araCalisan ? araCalisan.no : null };
  }

  function soruyuKapat() {
    qEl.hidden = true;
    qEl.replaceChildren();
    boardEl.classList.remove('has-question');
  }

  // ---------- Komutlar ----------
  async function adimlar(k) {
    const uyarilar = [];
    if (k.ders) {
      try { await dersYukle(k.ders); } catch (e) { uyarilar.push('Ders yüklenemedi: ' + k.ders); }
    }
    const liste = Array.isArray(k.adimlar) ? k.adimlar : [];
    for (let i = 0; i < liste.length; i++) {
      await durak.bekle(); // duraklatıldıysa sıradaki adım bekler (iptal edilmez)
      if (k.askida) await k.uyanis; // araya cevap girdiyse 'devam' beklenir
      if (k.iptal) return { durum: 'iptal', tamamlanan: i, uyarilar };
      k.adim = i;
      k.cumle = 0;
      const a = liste[i] || {};
      soruyuKapat();
      for (const c of (Array.isArray(a.komutlar) ? a.komutlar : [])) {
        if (!c || typeof c.type !== 'string') continue;
        if (c.type === 'image' && !(ders.assets || {})[c.asset]) {
          uyarilar.push('Görsel yok: ' + c.asset + (dersId ? '' : ' (önce ders seçilmeli)'));
          continue;
        }
        if (typeof board['cmd_' + c.type] !== 'function') { uyarilar.push('Bilinmeyen komut: ' + c.type); continue; }
        try { board.run(c, false); } catch (e) { uyarilar.push(c.type + ': ' + e.message); }
      }
      if (a.anlat) {
        const cumle = (n) => { k.cumle = n; };
        let r = await ses.anlat(a.anlat, { cumle });
        // Araya cevap girdi: 'devam' gelince aynı adımın kesilen cümlesinden sürer (tahta geri yüklenmiştir).
        while (r === 'kesildi' && k.askida && !k.iptal) {
          await k.uyanis;
          if (k.iptal) break;
          r = await ses.anlat(a.anlat, { bas: k.cumle, cumle });
        }
      } else if (a.bekle) await new Promise((r) => setTimeout(r, Math.min(15, a.bekle) * 1000));
    }
    if (k.iptal) return { durum: 'iptal', tamamlanan: liste.length, uyarilar };
    return uyarilar.length ? { durum: 'bitti', uyarilar } : { durum: 'bitti' };
  }

  function soru(k) {
    return new Promise((resolve) => {
      soruyuKapat();
      qEl.hidden = false;
      boardEl.classList.add('has-question');
      const card = el('div', 'q-card');
      card.appendChild(el('div', 'q-tag', k.etiket || 'Kendini yokla'));
      card.appendChild(el('h3', 'q-prompt', k.soru || ''));
      const secenekler = (Array.isArray(k.secenekler) ? k.secenekler : []).slice(0, 6);
      const dogruVar = Number.isInteger(k.dogru);
      const list = el('div', 'q-options');
      const fb = el('div', 'q-feedback');
      fb.hidden = true;
      const bekle = el('p', 'q-bekle', 'Bir seçeneğe dokunun.');
      const butonlar = secenekler.map((s, i) => {
        const b = el('button', 'q-opt');
        b.appendChild(el('span', 'q-letter', String.fromCharCode(65 + i)));
        b.appendChild(el('span', 'q-text', String(s)));
        b.addEventListener('click', () => {
          if (card.classList.contains('answered')) return;
          card.classList.add('answered');
          bekle.remove();
          butonlar.forEach((x) => { x.disabled = true; });
          const dogru = dogruVar ? i === k.dogru : null;
          if (dogruVar) {
            butonlar[k.dogru] && butonlar[k.dogru].classList.add('right');
            if (!dogru) b.classList.add('wrong');
            card.classList.add(dogru ? 'is-correct' : 'is-wrong');
            fb.hidden = false;
            fb.appendChild(el('strong', null, dogru ? 'Doğru.' : 'Tam değil.'));
            if (k.aciklama) fb.appendChild(el('p', null, k.aciklama));
          } else {
            b.classList.add('canli-secili');
          }
          resolve({ durum: 'cevaplandi', secim: i, harf: String.fromCharCode(65 + i), metin: String(s), dogru });
        });
        list.appendChild(b);
        return b;
      });
      card.append(list, fb, bekle);
      qEl.appendChild(card);
      k._iptal = () => resolve({ durum: 'iptal' });
      if (k.anlat) ses.anlat(k.anlat);
    });
  }

  async function uygula(k) {
    switch (k.tur) {
      case 'adimlar': return adimlar(k);
      case 'soru': return soru(k);
      case 'temizle':
        soruyuKapat();
        board.clear();
        capEl.textContent = '';
        return { durum: 'bitti' };
      default:
        return { durum: 'hata', hata: 'Bilinmeyen komut türü: ' + k.tur };
    }
  }

  // ---------- Sıra ve yoklama ----------
  const sira = [];
  let calisan = null;

  async function isle() {
    if (calisan) return;
    while (sira.length) {
      calisan = sira.shift();
      durumEl.textContent = calisan.tur === 'soru' ? 'Cevabınız bekleniyor' : 'Claude anlatıyor';
      let sonuc;
      try { sonuc = await uygula(calisan); } catch (e) { sonuc = { durum: 'hata', hata: e.message }; }
      if (sozAlindi) {
        // Söz sunucuya ulaşmadan sonucu bildirme: Claude sözü sonuçla birlikte ya da ondan önce alsın.
        if (sozBitti) await Promise.race([sozBitti, new Promise((r) => setTimeout(r, 20000))]);
        sonuc = Object.assign({}, sonuc, { not: 'Kullanıcı mikrofonla söz aldı; söylediğini dinle aracıyla al.' });
        sozAlindi = false;
        sozBitti = null;
      }
      const no = calisan.no;
      calisan = null;
      api('bitti', { no, sonuc, durum: durum() }).catch(() => {});
    }
    durumEl.textContent = hazirYazisi();
  }

  // ---------- Araya cevap ----------
  // Kullanıcı söz alıp anlatım duraklamışken Claude yeni komut gönderirse komut beklemeden, araya girer.
  // Duraklayan anlatım askıya alınır; tahtanın o anki hâli saklanır, cevap bir kopyası üzerine çizilir.
  // 'devam' gelince (ya da ▶ ile) tahta geri yüklenir ve anlatım kesilen cümleden sürer.
  const araSira = [];
  let araCalisan = null;
  let tahtaKaydi = null;

  function askidaki() { return calisan && calisan.askida ? calisan : null; }

  function tahtayiSakla() {
    const parca = (n) => Array.from(n.childNodes);
    tahtaKaydi = {
      board, ders, dersId, layout: boardEl.dataset.layout,
      header: parca(board.header), visual: parca(board.visual), notes: parca(board.notes),
      figure: board.figure, lastList: board.lastList
    };
    // Cevap, tahtanın bir kopyası üzerine çizilir (görsel işaretlenebilsin diye görsel de kopyalanır).
    const kopya = (dizi) => dizi.map((n) => n.cloneNode(true));
    board.header.replaceChildren(...kopya(tahtaKaydi.header));
    board.visual.replaceChildren(...kopya(tahtaKaydi.visual));
    board.notes.replaceChildren(...kopya(tahtaKaydi.notes));
    const fig = board.visual.querySelector('.board-figure');
    board.figure = fig ? { fig, inner: fig.querySelector('.figure-inner'), overlay: fig.querySelector('.figure-overlay') } : null;
    const ul = board.notes.querySelectorAll('ul');
    board.lastList = ul.length ? ul[ul.length - 1] : null;
  }

  function tahtayiGeriYukle() {
    const t = tahtaKaydi;
    if (!t) return;
    tahtaKaydi = null;
    board = t.board; ders = t.ders; dersId = t.dersId;
    if (dersId) dersAdiEl.textContent = 'Canlı tahta · ' + (ders.title || dersId);
    board.header.replaceChildren(...t.header);
    board.visual.replaceChildren(...t.visual);
    board.notes.replaceChildren(...t.notes);
    board.figure = t.figure;
    board.lastList = t.lastList;
    boardEl.dataset.layout = t.layout;
    soruyuKapat();
  }

  function askiyaAl(k) {
    if (k.askida) return;
    k.askida = true;
    k.uyanis = new Promise((r) => { k.uyandir = () => { k.askida = false; r(); }; });
    ses.dur();          // çalan cümle kesilir; 'devam'da o cümleden yeniden okunur
    durak.sifirla();    // duraklama kalkar; askıdaki anlatım uyanışı bekler
    tahtayiSakla();
    durak.goster();
  }

  async function araIsle() {
    if (araCalisan) return;
    while (araSira.length) {
      const k = araSira.shift();
      if (k.tur === 'devam') { anlatimaDon(k); continue; }
      const eski = askidaki() || calisan;
      if (eski && eski.tur === 'adimlar') askiyaAl(eski);
      araCalisan = k;
      durumEl.textContent = k.tur === 'soru' ? 'Cevabınız bekleniyor' : 'Claude cevaplıyor';
      let sonuc;
      try { sonuc = await uygula(k); } catch (e) { sonuc = { durum: 'hata', hata: e.message }; }
      araCalisan = null;
      api('bitti', { no: k.no, sonuc: Object.assign({ araya_girdi: true }, sonuc), durum: durum() }).catch(() => {});
    }
    if (askidaki()) durumEl.textContent = 'Claude cevapladı · anlatıma dönmek için ▶';
    durak.goster();
  }

  // 'devam' komutu (k) ya da ▶ (k = null): askıdaki ya da söz için duraklayan anlatım kaldığı yerden sürer.
  function anlatimaDon(k) {
    const eski = askidaki();
    let sonuc;
    if (k && k.birak) {
      if (eski) { eski.iptal = true; tahtaKaydi = null; eski.uyandir(); }
      else if (durak.soz && calisan) { calisan.iptal = true; ses.dur(); durak.sifirla(); }
      sonuc = { durum: eski || calisan ? 'birakildi' : 'devam_edilecek_anlatim_yok' };
    } else if (eski) {
      tahtayiGeriYukle();
      durak.sifirla();
      eski.uyandir();
      durumEl.textContent = 'Claude anlatıyor';
      sonuc = { durum: 'devam_ediyor', anlatim_no: eski.no };
    } else if (durak.aktif && calisan && calisan.tur === 'adimlar') {
      durak.devam();
      sonuc = { durum: 'devam_ediyor', anlatim_no: calisan.no };
    } else {
      sonuc = { durum: calisan ? 'zaten_suruyor' : 'devam_edilecek_anlatim_yok' };
      if (calisan) sonuc.anlatim_no = calisan.no;
    }
    durak.goster();
    if (k) api('bitti', { no: k.no, sonuc, durum: durum() }).catch(() => {});
  }

  function durdur(k) {
    ses.dur();
    for (const x of sira.splice(0).concat(araSira.splice(0))) {
      api('bitti', { no: x.no, sonuc: { durum: 'iptal' } }).catch(() => {});
    }
    for (const x of [araCalisan, calisan]) {
      if (!x) continue;
      x.iptal = true;
      if (x._iptal) { soruyuKapat(); x._iptal(); }
      if (x.askida) { x.askida = false; tahtaKaydi = null; x.uyandir(); }
    }
    durak.sifirla();
    if (k) api('bitti', { no: k.no, sonuc: { durum: 'durduruldu' }, durum: durum() }).catch(() => {});
  }

  // Claude 'dinle' aracıyla (ya da bekleyen bir tahta çağrısıyla) beklerken mikrofon tuşunun çevresinde
  // yeşil halka ve üstteki ışık yanar.
  let claudeDinliyor = false;
  const isikEl = $('#claudeIsik');
  function dinlemeIsareti(var_) {
    claudeDinliyor = !!var_;
    isikEl.classList.toggle('acik', claudeDinliyor);
    isikEl.querySelector('span').textContent = claudeDinliyor ? 'Claude dinliyor' : 'Claude dinlemiyor';
    isikEl.title = claudeDinliyor ? 'Konuşursanız Claude hemen duyar.'
      : 'Claude şu an dinlemiyor. Konuşursanız sorunuz bekler; sohbete "tahtaya bak" yazın.';
    bekleyenGoster(bekleyenSoz);
    mikBtn.classList.toggle('claude-dinliyor', claudeDinliyor);
    if (SR) mikBtn.title = claudeDinliyor ? 'Claude dinliyor · dokunup konuşun (M)' : 'Konuş: dokunun, konuşun; susunca gönderilir (M)';
    if (!calisan && !mik.aktif) durumEl.textContent = hazirYazisi();
  }
  // Claude dinlemiyorken söylenenler: üstte uyarı ve "Sohbete kopyala" düğmesi.
  let bekleyenSoz = [];
  const bekleyenEl = $('#bekleyenSoru');
  function bekleyenGoster(liste) {
    bekleyenSoz = (liste || []).slice();
    const goster = bekleyenSoz.length > 0 && !claudeDinliyor;
    bekleyenEl.hidden = !goster;
    if (goster) $('#bekleyenMetin').textContent = '“' + bekleyenSoz.join(' ') + '”';
  }
  async function panoyaYaz(metin) {
    try {
      await navigator.clipboard.writeText(metin);
      return true;
    } catch (e) {
      const t = document.createElement('textarea');
      t.value = metin;
      t.style.position = 'fixed';
      t.style.opacity = '0';
      document.body.appendChild(t);
      t.select();
      let ok = false;
      try { ok = document.execCommand('copy'); } catch (_) { /* yok */ }
      t.remove();
      return ok;
    }
  }
  $('#sohbeteKopyala').addEventListener('click', async () => {
    if (!bekleyenSoz.length) return;
    const metin = 'Tahtadan sesli soru: ' + bekleyenSoz.join(' ');
    if (!(await panoyaYaz(metin))) return toast('Kopyalanamadı. Sohbete "tahtaya bak" yazın.', 6000);
    // Söz sohbete taşındı: Claude onu bir araçtan ikinci kez almasın.
    api('birak', {}).catch(() => {});
    bekleyenGoster([]);
    const mac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
    toast('Kopyalandı. Claude sohbetine yapıştırıp gönderin (' + (mac ? 'Cmd+V' : 'Ctrl+V') + ').', 7000);
  });

  function hazirYazisi() {
    return claudeDinliyor ? 'Claude dinliyor · mikrofona dokunup konuşabilirsiniz' : 'Hazır · Claude\'dan komut bekleniyor';
  }

  let son = 0;
  async function yokla() {
    try {
      const r = await api('merhaba', { durum: durum() });
      son = (await r.json()).sayac || 0;
    } catch (e) {
      baglanti(false);
      return setTimeout(yokla, 3000);
    }
    baglanti(true);
    for (;;) {
      try {
        const r = await api('al?son=' + son + '&dinliyor=' + (claudeDinliyor ? 1 : 0) + '&bekleyen=' + bekleyenSoz.length);
        const j = await r.json();
        const komutlar = j.komutlar;
        baglanti(true);
        if (typeof j.dinliyor === 'boolean' && j.dinliyor !== claudeDinliyor) dinlemeIsareti(j.dinliyor);
        if (Array.isArray(j.bekleyen_konusma)) bekleyenGoster(j.bekleyen_konusma);
        for (const k of komutlar || []) {
          son = Math.max(son, k.no);
          if (k.tur === 'dur') durdur(k);
          else if (k.tur === 'devam') {
            if (araCalisan || araSira.length) { araSira.push(k); araIsle(); } else anlatimaDon(k);
          } else if (calisan && calisan.tur === 'adimlar' && (durak.soz || calisan.askida)) {
            // Söz alınıp duraklayan bir cevap varsa o bırakılır; yeni cevap onun yerine geçer.
            if (araCalisan && durak.soz) { araCalisan.iptal = true; ses.dur(); durak.sifirla(); }
            araSira.push(k);
            araIsle();
          } else sira.push(k);
        }
        isle();
      } catch (e) {
        baglanti(false);
        await new Promise((r) => setTimeout(r, 3000));
        // Sunucu yeniden açıldıysa sayaç sıfırlanmış olabilir.
        try { const r = await api('merhaba', { durum: durum() }); son = (await r.json()).sayac || 0; } catch (_) { /* tekrar denenir */ }
      }
    }
  }

  function baglanti(var_) {
    dot.classList.toggle('bagli', var_);
    if (!var_) durumEl.textContent = 'Sunucuya ulaşılamıyor · tools/sunucu.py açık mı?';
    else if (!calisan) durumEl.textContent = hazirYazisi();
  }

  // ---------- Düğmeler ----------
  const hizBtn = $('#hiz');
  const hizYaz = () => { hizBtn.textContent = String(hiz).replace('.', ',') + '×'; };
  hizYaz();
  hizBtn.addEventListener('click', () => {
    hiz = HIZLAR[(HIZLAR.indexOf(hiz) + 1) % HIZLAR.length] || 1.2;
    AT.prefs.set('canliHiz', hiz);
    ses.audio.playbackRate = hiz;
    hizYaz();
  });
  $('#dur').addEventListener('click', () => durdur(null));
  const tamEkran = () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else document.documentElement.requestFullscreen && document.documentElement.requestFullscreen().catch(() => {});
  };
  $('#tamEkran').addEventListener('click', tamEkran);
  document.addEventListener('keydown', (e) => {
    if (e.target.closest && e.target.closest('input, textarea')) return;
    if (e.key === 'Escape') durdur(null);
    if (e.key === 'f' || e.key === 'F') tamEkran();
    if ((e.key === 'm' || e.key === 'M') && !e.repeat) mik.baslat();
    if ((e.key === 'p' || e.key === 'P') && !e.repeat) durak.degistir();
    if (e.key === ' ' && !e.repeat && (durak.aktif || durak.kullanilabilir())) {
      // Boşluk yalnız anlatım sürerken duraklatır; odaktaki düğmeyi tıklamasın.
      e.preventDefault();
      if (document.activeElement && document.activeElement.blur) document.activeElement.blur();
      durak.degistir();
    }
  });

  // Tarayıcı, sesin çalması için kullanıcı dokunuşu ister.
  function baslat(tam) {
    $('#baslat').hidden = true;
    // Boş bir sesle izni aç.
    ses.audio.src = 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA=';
    ses.audio.play().catch(() => {});
    if (tam) tamEkran();
  }
  $('#baslatPencere').addEventListener('click', () => baslat(false));
  $('#baslatTam').addEventListener('click', () => baslat(true));

  board.run({ type: 'title', text: 'Canlı tahta', subtitle: 'Claude masaüstü uygulamasında bir konu isteyin; tahtayı Claude yönetecek.' }, true);
  board.run({ type: 'bullets', title: 'Örnek istekler', items: [
    '"Tahtada bana peri-implantitis defekt sınıflamasını anlat."',
    '"Şekil 2\'yi göster ve Sınıf Ib\'yi işaretle."',
    '"Bana bu konudan iki soru sor."'
  ] }, true);
  yokla();
})(window.AT = window.AT || {});
