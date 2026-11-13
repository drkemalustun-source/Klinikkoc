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
 * Dikte: mikrofon tuşu (ya da M) konuşmayı Duyu-small (bu bilgisayarda) ya da tarayıcının Türkçe tanıyıcısıyla
 *   yazıya çevirir, terim sözlüğünden geçirir, 3 sn kutuda gösterir ve /api/canli/soyle ile sunucuya bırakır. Anlatım sürerken basılırsa anlatım duraklar (söz alma); Claude'un
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

  // Başka sekme tahtayı devralınca bu sekmenin bekleyen istekleri kesilir (aynı komutu iki sekme almasın).
  const sekmeKesici = new AbortController();
  let sekmeKapandi = false;
  // sure (ms): istek en çok bu kadar bekler; sunucu takılırsa tahta da takılı kalmasın.
  async function api(yol, govde, sure) {
    if (sekmeKapandi) throw new Error('Tahta başka sekmede açık');
    const kesici = new AbortController();
    const kes = () => kesici.abort();
    sekmeKesici.signal.addEventListener('abort', kes);
    const zaman = sure ? setTimeout(kes, sure) : null;
    try {
      const r = await fetch('/api/canli/' + yol, govde === undefined ? { cache: 'no-store', signal: kesici.signal } : {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(govde), signal: kesici.signal
      });
      if (!r.ok) throw new Error((await r.json().catch(() => ({}))).hata || ('HTTP ' + r.status));
      return r;
    } finally {
      if (zaman) clearTimeout(zaman);
      sekmeKesici.signal.removeEventListener('abort', kes);
    }
  }

  // ---------- Ses ----------
  const HIZLAR = [1, 1.2, 1.4];
  const SES_SURE = 25000; // ms: bir cümlenin sesi bundan uzun sürerse yedek sese geçilir
  const ONDEN = 2; // kaç cümle önceden seslendirilsin
  let hiz = Number(AT.prefs.get('canliHiz')) || 1.2;
  const duz = (t) => String(t || '').replace(/\*\*|(?<!\w)_|_(?!\w)/g, '').replace(/\{\d+\}/g, '').replace(/\s+/g, ' ').trim();

  const ses = {
    token: 0,
    audio: new Audio(),
    piperVar: true,
    web: new AT.speech.WebSpeechEngine('tr-TR'),
    konusuyor: false,

    // Bir cümlenin sesi en çok SES_SURE ms beklenir; gelmezse o cümle tarayıcı sesiyle okunur (anlatım takılmaz).
    async wav(metin) {
      const r = await api('ses', { metin }, SES_SURE);
      return URL.createObjectURL(await r.blob());
    },
    hata: 0,

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
        // Sıradaki ÖNDEN cümlenin sesi şimdiden istenir: cümle araları kısalır.
        const hazir = new Map();
        const iste = (k) => {
          if (!this.piperVar || k >= cumleler.length || hazir.has(k)) return;
          hazir.set(k, this.wav(cumleler[k]).catch(() => null));
        };
        for (let k = bas; k <= bas + ONDEN; k++) iste(k);
        const birak = () => { for (const p of hazir.values()) p.then((u) => u && URL.revokeObjectURL(u)); };
        for (let i = bas; i < cumleler.length; i++) {
          await durak.bekle();
          if (my !== this.token) { birak(); return 'kesildi'; }
          if (secenek.cumle) secenek.cumle(i);
          const bekleyen = hazir.get(i);
          const url = bekleyen ? await bekleyen : null;
          hazir.delete(i);
          iste(i + ONDEN + 1);
          altyazi(cumleler[i], 'Claude');
          await durak.bekle();
          if (my !== this.token) { if (url) URL.revokeObjectURL(url); birak(); return 'kesildi'; }
          if (url) {
            this.hata = 0;
            await this.cal(url, my);
            URL.revokeObjectURL(url);
            if (my !== this.token) { birak(); return 'kesildi'; }
          } else {
            // Bu cümlenin sesi gelmedi: yalnız bu cümle tarayıcı sesiyle okunur. Üst üste 3 kez olursa sunucu sesi
            // bırakılır (sayfa yenilenene kadar).
            if (this.piperVar && ++this.hata >= 3) {
              this.piperVar = false;
              toast('Bu bilgisayarın sesi yanıt vermiyor; tarayıcının Türkçe sesi (yedek) kullanılıyor.', 6000);
              sesGoster({ motor: 'tarayici', yazi: 'tarayıcı sesi (yedek)',
                ayrinti: 'Sunucu sesi (Pocket/Piper) üst üste yanıt vermedi; tarayıcının Türkçe sesi kullanılıyor.' }, true);
            }
            this.web.setRate(hiz);
            if (this.piperVar) {
              await this.web.speak(cumleler[i]);
              if (my !== this.token) { birak(); return 'kesildi'; }
              continue;
            }
            birak();
            let j = i;
            await this.web.speak(cumleler.slice(i).join(' '), { onSentence: (s) => {
              altyazi(s, 'Claude');
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
        const oynat = () => (durak.aktif ? Promise.resolve() : a.play().then(() => { this.izinli = true; })).catch(async (e) => {
          if (bitti || !benim()) return;
          if (e && e.name !== 'NotAllowedError') return son(); // ses bozuk: sonraki cümleye geç
          // Tarayıcı sesi engelledi: anlatım bu cümlede bekler, büyük düğmeye dokununca sürer.
          if (await sesIzniIste(my, this)) oynat(); else son();
        });
        oynat();
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

  // Hangi ses kullanılıyor? Üst çubukta gösterilir; yedek seste sarı. kalici: tarayıcı yedeğine düşüldü
  // (sayfa yenilenene kadar sunucu bilgisi bunu ezmesin).
  const sesEl = $('#sesMotor');
  let sesYedekKalici = false;
  function sesGoster(b, kalici) {
    if (!b || !sesEl) return;
    if (sesYedekKalici && !kalici) return;
    if (kalici) sesYedekKalici = true;
    sesEl.hidden = false;
    sesEl.textContent = 'Ses: ' + b.yazi;
    sesEl.title = b.ayrinti || b.yazi;
    sesEl.classList.toggle('yedek', b.motor !== 'pocket');
    sesEl.classList.toggle('yukleniyor', /yükleniyor/i.test(b.yazi || '')); // asıl ses (Pocket) hâlâ yükleniyor
  }

  // Tarayıcı otomatik oynatmayı engellediyse büyük "Sesi açmak için dokunun" düğmesi. true: dokunuldu;
  // false: anlatım bu arada durduruldu/değişti.
  let sesEngelli = false;
  function sesIzniIste(my, s) {
    return new Promise((resolve) => {
      const kutu = $('#sesAc');
      sesEngelli = true;
      kutu.hidden = false;
      durumEl.textContent = 'Ses engellendi · ekrandaki düğmeye dokunun';
      api('duraklat', { duraklatildi: durak.aktif, durum: durum() }).catch(() => {}); // Claude durumu görsün
      const bitir = (ok) => {
        clearInterval(iv);
        if (ok) {
          $('#baslat').hidden = true; // dokunuş izni de açar
          const v = board.video; // engellenmiş video da bu dokunuşla başlar
          if (v && v.durum === 'bekliyor' && v.dugmeAcik) { v.dugmeGizle(); v.oynat(); }
        }
        $('#sesAcDugme').onclick = null;
        kutu.hidden = true;
        sesEngelli = false;
        resolve(ok);
      };
      $('#sesAcDugme').onclick = () => bitir(true);
      const iv = setInterval(() => { if (my !== s.token) bitir(false); }, 200);
    });
  }

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
      const video = !!(board.video && board.video.durum === 'oynuyor');
      return !mik.aktif && qEl.hidden && (ses.konusuyor || video || !!(calisan && calisan.tur === 'adimlar'));
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
      AT.Board.animDurdu = true; // tahtadaki canlandırma da bekler
      if (board.video && board.video.durum === 'oynuyor') { board.video.duraklat(); this.videoDurdu = board.video; }
      try { if (window.speechSynthesis) speechSynthesis.pause(); } catch (e) { /* yok */ }
      this.goster();
      api('duraklat', { duraklatildi: true, durum: durum() }).catch(() => {});
    },
    devam() {
      if (!this.aktif) return;
      this.aktif = false;
      this.soz = false;
      if (ses.caliyor) ses.audio.play().catch(() => {});
      AT.Board.animDurdu = false;
      if (this.videoDurdu && this.videoDurdu === board.video) this.videoDurdu.oynat();
      this.videoDurdu = null;
      try { if (window.speechSynthesis) speechSynthesis.resume(); } catch (e) { /* yok */ }
      this.birak();
      api('duraklat', { duraklatildi: false, durum: durum() }).catch(() => {});
    },
    // Durdur ya da söz alma: duraklama kalkar, bekleyen döngüler bırakılır (onlar iptali görüp çıkar).
    sifirla() {
      this.soz = false;
      this.videoDurdu = null;
      AT.Board.animDurdu = false;
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
  // İki tanıyıcı: Duyu-small (bu bilgisayarda, tools/sunucu.py; ses dışarı çıkmaz, internetsiz) ve tarayıcının
  // kendi tanıyıcısı (Chrome'da ses Google'a gider). Duyu kurulu ve hazırsa varsayılan odur; seçim saklanır.
  // Tanınan metin terim sözlüğünden geçer (/api/canli/duzelt ya da /api/duyu/yaz?duzelt=1), 3 sn kutuda
  // görünür; öğrenci düzeltebilir ya da hemen gönderebilir. Claude düzeltilmiş metni ve ham_metin'i görür.
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const mikBtn = $('#mik');
  const motorBtn = $('#motor');
  const motorMenu = $('#motorMenu');
  const MOTOR_ANAHTAR = 'klinikkoc.dikte';
  const ONAY_MS = 2500;
  const dikte = {
    secim: (() => { try { return localStorage.getItem(MOTOR_ANAHTAR); } catch (e) { return null; } })(),
    duyu: null, // /api/duyu/durum
    motor() {
      const duyuVar = !!(this.duyu && this.duyu.kurulu);
      if (this.secim === 'tarayici' && SR) return 'tarayici';
      if (duyuVar && (this.secim === 'duyu' || !this.secim || !SR)) return 'duyu';
      return SR ? 'tarayici' : (duyuVar ? 'duyu' : null);
    },
    sec(m) {
      this.secim = m;
      try { localStorage.setItem(MOTOR_ANAHTAR, m); } catch (e) { /* özel pencere */ }
      this.goster();
      if (m === 'duyu' && !(this.duyu && this.duyu.kurulu)) {
        toast('Duyu kurulu değil. Kurmak için bir kez: ' + this.komut() + ' — o zamana kadar tarayıcı kullanılıyor.', 9000);
      }
    },
    komut() { return (this.duyu && this.duyu.komut) || 'python3 tools/sunucu.py --kur-duyu'; },
    async yenile() {
      try {
        const r = await fetch('/api/duyu/durum', { cache: 'no-store' });
        this.duyu = await r.json();
      } catch (e) {
        this.duyu = { kurulu: false, neden: 'Sunucuya ulaşılamadı.' };
      }
      this.goster();
      if (this.duyu.kurulu && !this.duyu.hazir && this.motor() === 'duyu' && !this.yukleniyor) {
        // Model ilk konuşmadan önce ısınsın. İlk kez kullanılıyorsa internetten iner: tahtada göster.
        this.yukleniyor = true;
        if (!this.duyu.model_indirildi) toast('Dikte modeli (Duyu) ilk kez indiriliyor, ~56 MB. Bir iki dakika sürebilir; bu sırada yazarak sorabilirsiniz.', 9000);
        this.goster();
        fetch('/api/duyu/yukle', { method: 'POST' }).catch(() => {}).then(() => { this.yukleniyor = false; this.yenile(); });
      }
    },
    goster() {
      const m = this.motor();
      const yedek = this.secim === 'duyu' && m !== 'duyu';
      motorBtn.textContent = m === 'duyu' ? (this.yukleniyor ? 'Duyu ⏳' : 'Duyu') : m === 'tarayici' ? 'Tarayıcı' : 'Yok';
      motorBtn.classList.toggle('uyari', yedek || !m);
      motorBtn.title = (m === 'duyu' ? 'Dikte: Duyu-small, bu bilgisayarda (ses dışarı çıkmaz)'
        : m === 'tarayici' ? 'Dikte: tarayıcının tanıyıcısı' + (yedek ? ' (Duyu kurulu değil)' : '')
          : 'Dikte kullanılamıyor') + ' · değiştirmek için dokunun';
      mikBtn.disabled = !m;
      mikBtn.title = m ? 'Konuş: dokunun, konuşun; susunca yazıya çevrilir (M)' : 'Konuşma tanıma yok: Duyu kurun ya da Chrome/Edge kullanın.';
      $('#motorDuyu').checked = m === 'duyu';
      $('#motorTarayici').checked = m === 'tarayici';
      $('#motorTarayici').disabled = !SR;
      const d = this.duyu || {};
      $('#motorDuyuDurum').textContent = d.kurulu
        ? (d.hazir ? 'Hazır.' : this.yukleniyor ? (d.model_indirildi ? 'Model yükleniyor…' : 'Model ilk kez iniyor (~56 MB)…') : d.model_indirildi ? 'Kurulu; ilk konuşmada yüklenir.' : 'Kurulu; model ilk kullanımda bir kez indirilir.')
        : 'Duyu kurulu değil. Kurmak için bir kez şu komutu çalıştırın:';
      $('#motorKomut').hidden = !!d.kurulu;
      $('#motorKomutYazi').textContent = this.komut();
      $('#motorTarayiciDurum').textContent = SR ? 'Kurulum gerekmez; internet ister (Chrome\'da ses Google\'a gider).' : 'Bu tarayıcıda yok (Chrome ya da Edge gerekir).';
    }
  };
  motorBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    motorMenu.hidden = !motorMenu.hidden;
    if (!motorMenu.hidden) dikte.yenile();
  });
  document.addEventListener('click', (e) => { if (!motorMenu.hidden && !motorMenu.contains(e.target)) motorMenu.hidden = true; });
  $('#motorDuyu').addEventListener('change', () => dikte.sec('duyu'));
  $('#motorTarayici').addEventListener('change', () => dikte.sec('tarayici'));
  $('#motorKopyala').addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(dikte.komut()); toast('Komut kopyalandı.'); } catch (e) { toast(dikte.komut(), 8000); }
  });

  let sozAlindi = false;
  let sozBitti = null;     // soru kartında söz alınınca: söz sunucuya ulaşınca çözülür
  let sozBittiCoz = null;
  const mik = {
    rec: null,        // tarayıcı tanıyıcısı
    kayit: null,      // Duyu için mikrofon kaydı
    aktif: false,
    isleniyor: false,
    motor: null,
    metin: '',
    sessizT: null,

    baslat() {
      if (this.aktif) return this.bitir();
      if (this.isleniyor) return;
      const motor = dikte.motor();
      if (!motor) return toast('Konuşma tanıma yok: Duyu kurun ya da Chrome/Edge kullanın. Yazarak da sorabilirsiniz.', 7000);
      onay.durdur(true);
      sozAl();
      this.motor = motor;
      this.aktif = true;
      this.metin = '';
      mikBtn.classList.add('dinliyor');
      durumEl.textContent = motor === 'duyu' ? 'Dinleniyor · susunca yazıya çevrilir (bitirmek için yeniden dokunun)'
        : 'Dinleniyor · susunca ya da “bitirdim” deyince gönderilir (bitirmek için yeniden dokunun)';
      dokEl.classList.add('dinleniyor');
      this.onceki = yaziEl.value.trim(); // kutuda yazılmış bir şey varsa söylenen onun arkasına eklenir
      yaziEl.placeholder = 'Dinliyorum… susunca yazıya çevrilir';
      if (motor === 'duyu') this.duyuBaslat(); else this.tarayiciBaslat();
    },

    ui() {
      mikBtn.classList.remove('dinliyor');
      dokEl.classList.remove('dinleniyor');
      dokEl.style.removeProperty('--seviye');
      dokEl.classList.remove('seviyeli');
      yaziEl.placeholder = YER_TUTUCU;
    },

    // --- tarayıcı ---
    tarayiciBaslat() {
      const rec = new SR();
      rec.lang = 'tr-TR';
      rec.continuous = true;
      rec.interimResults = true;
      rec.maxAlternatives = 1;
      const finals = [];
      this.rec = rec;
      this.sure(8000); // hiç konuşulmazsa 8 sn sonra kapanır
      rec.onresult = (ev) => {
        let ara = '';
        for (let i = ev.resultIndex; i < ev.results.length; i++) {
          const r = ev.results[i];
          if (r.isFinal) finals.push(r[0].transcript.trim());
          else ara += r[0].transcript;
        }
        this.metin = finals.join(' ').trim();
        // "Bitirdim" ya da "gönder" diye bitirilirse beklemeden gönderilir (söz yazıya girmez).
        const son = /[\s,.]*\b(bitirdim|gönder|gonder)[.!]?\s*$/i;
        if (son.test(this.metin)) {
          this.metin = this.metin.replace(son, '').trim();
          yaziEl.value = [this.onceki, this.metin].join(' ').replace(/\s+/g, ' ').trim();
          return this.bitir();
        }
        yaziEl.value = [this.onceki, this.metin, ara].join(' ').replace(/\s+/g, ' ').trim();
        gonderBtn.disabled = !yaziEl.value.trim();
        // Tarayıcı uzun cümleyi kısa duraklarda böler: 3,5 sn susunca bitir ("bitirdim" deyince hemen).
        this.sure(3500);
      };
      rec.onerror = (ev) => {
        if (ev.error === 'not-allowed' || ev.error === 'service-not-allowed') {
          toast('Mikrofon izni verilmedi. Adres çubuğundaki simgeden mikrofona izin verin.', 7000);
        } else if (ev.error === 'network') {
          toast('Tarayıcının tanıyıcısı internet istiyor. İnternetsiz çalışmak için Duyu\'yu kurun.', 7000);
        } else if (ev.error === 'audio-capture') {
          toast('Mikrofon bulunamadı.', 6000);
        } else if (ev.error !== 'no-speech' && ev.error !== 'aborted') {
          toast('Konuşma tanıma hatası: ' + ev.error);
        }
      };
      rec.onend = () => this.tarayiciBitti();
      try {
        rec.start();
      } catch (e) {
        this.aktif = false;
        this.rec = null;
        this.ui();
        toast('Mikrofon açılamadı: ' + e.message);
      }
    },

    async tarayiciBitti() {
      if (!this.aktif) return;
      this.aktif = false;
      this.rec = null;
      clearTimeout(this.sessizT);
      this.ui();
      if (this.yazilan != null) { const y = this.yazilan; this.yazilan = null; return sozGonder(y, { motor: 'yazi' }); }
      const ham = this.metin.trim();
      this.metin = '';
      if (!ham) return this.bos();
      await this.duzeltVeOnayla(ham, 'tarayici');
    },

    // --- Duyu: kayıt, sessizlik algılama, sunucuda yazıya çevirme ---
    async duyuBaslat() {
      let stream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      } catch (e) {
        this.aktif = false;
        this.ui();
        sozBitir();
        return toast(e.name === 'NotAllowedError' ? 'Mikrofon izni verilmedi. Adres çubuğundaki simgeden izin verin.' : 'Mikrofon açılamadı: ' + e.message, 7000);
      }
      if (!this.aktif) { stream.getTracks().forEach((t) => t.stop()); return; } // bu arada bırakıldı
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const src = ctx.createMediaStreamSource(stream);
      const node = ctx.createScriptProcessor(4096, 1, 1);
      const k = { stream, ctx, node, parcalar: [], oran: ctx.sampleRate, bas: performance.now(), sonSes: 0, konustu: false, taban: [], esik: 0.015 };
      node.onaudioprocess = (ev) => {
        const d = ev.inputBuffer.getChannelData(0);
        k.parcalar.push(new Float32Array(d));
        let s = 0;
        for (let i = 0; i < d.length; i++) s += d[i] * d[i];
        const rms = Math.sqrt(s / d.length);
        if (performance.now() - k.bas < 400) { k.taban.push(rms); k.esik = Math.max(0.012, Math.min(0.05, 3 * Math.max(...k.taban))); }
        else if (rms > k.esik) { k.konustu = true; k.sonSes = performance.now(); }
        dokEl.style.setProperty('--seviye', Math.min(1, rms * 12).toFixed(2));
        dokEl.classList.add('seviyeli');
      };
      src.connect(node);
      node.connect(ctx.destination);
      this.kayit = k;
      this.kayitT = setInterval(() => {
        const simdi = performance.now();
        if (!k.konustu && simdi - k.bas > 8000) this.bitir();              // hiç konuşulmadı
        else if (k.konustu && simdi - k.sonSes > 2000) this.bitir();       // 2 sn sustu
        else if (simdi - k.bas > 180000) this.bitir();                     // en çok 3 dk
      }, 100);
    },

    async duyuBitti() {
      const k = this.kayit;
      this.kayit = null;
      clearInterval(this.kayitT);
      this.aktif = false;
      this.ui();
      if (!k) return;
      try { k.node.disconnect(); } catch (e) { /* bitti */ }
      k.stream.getTracks().forEach((t) => t.stop());
      try { await k.ctx.close(); } catch (e) { /* kapalı */ }
      if (this.yazilan != null) { const y = this.yazilan; this.yazilan = null; return sozGonder(y, { motor: 'yazi' }); }
      if (!k.konustu) return this.bos();
      const n = k.parcalar.reduce((a, c) => a + c.length, 0);
      const hepsi = new Float32Array(n);
      let o = 0;
      for (const c of k.parcalar) { hepsi.set(c, o); o += c.length; }
      const ses16 = yenidenOrnekle(hepsi, k.oran, 16000);
      this.isleniyor = true;
      yaziEl.placeholder = 'Yazıya çevriliyor…';
      durumEl.textContent = (dikte.duyu && !dikte.duyu.hazir
        ? (dikte.duyu.model_indirildi ? 'Duyu modeli yükleniyor, ilk seferde biraz sürer… ' : 'Duyu modeli ilk kez iniyor (~56 MB), lütfen bekleyin… ')
        : 'Duyu yazıya çeviriyor ') + '(' + Math.round(ses16.length / 16000) + ' sn ses)';
      try {
        const r = await fetch('/api/duyu/yaz?duzelt=1&lang=mix&beam=5&mode=auto', {
          method: 'POST', headers: { 'Content-Type': 'application/octet-stream' },
          body: new Uint8Array(ses16.buffer, ses16.byteOffset, ses16.byteLength)
        });
        const j = await r.json();
        if (!r.ok || j.hata) throw new Error(j.hata || ('sunucu ' + r.status));
        this.isleniyor = false;
        yaziEl.placeholder = YER_TUTUCU;
        if (!(j.metin || '').trim()) return this.bos();
        onay.baslat(this.birlestir(j.metin), this.birlestir(j.ham_metin || j.metin), 'duyu', j.duzeltmeler);
      } catch (e) {
        this.isleniyor = false;
        yaziEl.placeholder = YER_TUTUCU;
        if (!calisan) durumEl.textContent = hazirYazisi();
        toast('Duyu yazıya çeviremedi: ' + e.message + '. Tarayıcı tanıyıcısını seçebilir ya da yazabilirsiniz.', 8000);
        if (durak.soz && !yaziEl.value.trim()) durak.devam();
        sozBitir();
      }
    },

    birlestir(m) { return [this.onceki, (m || '').trim()].join(' ').replace(/\s+/g, ' ').trim(); },

    async duzeltVeOnayla(ham, motor) {
      let d = { metin: ham, ham_metin: ham, duzeltmeler: [] };
      try {
        const r = await api('duzelt', { metin: ham });
        if (r.ok) d = await r.json();
      } catch (e) { /* sözlük yoksa ham metin */ }
      onay.baslat(this.birlestir(d.metin), this.birlestir(d.ham_metin), motor, d.duzeltmeler);
    },

    bos() {
      if (!calisan) durumEl.textContent = hazirYazisi();
      yaziEl.value = this.onceki || '';
      gonderBtn.disabled = !yaziEl.value.trim();
      toast('Ses algılanmadı.');
      if (durak.soz && !yaziEl.value.trim()) durak.devam(); // söz alınıp bir şey söylenmediyse anlatım sürer
      sozBitir();
    },

    sure(ms) {
      clearTimeout(this.sessizT);
      this.sessizT = setTimeout(() => this.bitir(), ms);
    },

    // Kaydı bitirir; o ana kadar söyleneni yazıya çevirir (tahta konuşmaya başlarsa da çağrılır:
    // mikrofon tahtanın kendi sesini almasın).
    bitir() {
      clearTimeout(this.sessizT);
      if (this.motor === 'duyu') { if (this.kayit) this.duyuBitti(); return; }
      if (this.rec) { try { this.rec.stop(); } catch (e) { /* zaten durdu */ } }
    }
  };
  mikBtn.addEventListener('click', () => mik.baslat());

  // Tarayıcının sesini 16 kHz'e indirir (ortalama alarak; basit alçak geçiren süzgeç).
  function yenidenOrnekle(veri, kaynak, hedef) {
    if (kaynak === hedef) return veri;
    const oran = kaynak / hedef;
    const n = Math.floor(veri.length / oran);
    const out = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const a = Math.floor(i * oran), b = Math.min(veri.length, Math.floor((i + 1) * oran));
      let s = 0;
      for (let j = a; j < b; j++) s += veri[j];
      out[i] = b > a ? s / (b - a) : veri[a] || 0;
    }
    return out;
  }

  // ---------- Onay: tanınan metin 3 sn kutuda görünür ----------
  const onay = {
    t: null,
    bilgi: null,
    baslat(metin, ham, motor, duzeltmeler) {
      this.bilgi = { ham_metin: ham, motor };
      yaziEl.value = metin;
      gonderBtn.disabled = !metin;
      dokEl.classList.remove('onayda');
      void dokEl.offsetWidth; // süre çizgisi baştan başlasın
      dokEl.style.setProperty('--onay-ms', ONAY_MS + 'ms');
      dokEl.classList.add('onayda');
      const d = (duzeltmeler || []).map((x) => '“' + x.ham + '” → ' + x.terim).join(', ');
      durumEl.textContent = (d ? 'Terim düzeltildi: ' + d + ' · ' : '') + 'Birazdan gönderilecek · düzeltmek için kutuya dokunun, hemen göndermek için ↑';
      clearTimeout(this.t);
      this.t = setTimeout(() => this.gonder(), ONAY_MS);
    },
    // Öğrenci kutuya dokundu ya da yazmaya başladı: süre durur, gönderme ona kalır.
    durdur(sessiz) {
      if (!this.t) return;
      clearTimeout(this.t);
      this.t = null;
      dokEl.classList.remove('onayda');
      if (!sessiz) durumEl.textContent = 'Düzeltin, sonra Enter ya da ↑ ile gönderin';
    },
    gonder() {
      clearTimeout(this.t);
      this.t = null;
      dokEl.classList.remove('onayda');
      const metin = yaziEl.value.trim();
      const b = this.bilgi;
      this.bilgi = null;
      if (!calisan) durumEl.textContent = hazirYazisi();
      if (metin) sozGonder(metin, b);
      else { sozBitir(); if (durak.soz) durak.devam(); }
    }
  };

  // ---------- Söz alma ve gönderme (mikrofon ve yazı kutusu ortak) ----------
  // Söz almak: anlatım sürüyorsa kaldığı yerde duraklar (Claude'un bekleyen çağrısı sözü hemen alır);
  // soru kartı açıksa kart kapanır.
  function sozAl() {
    const anlatan = araCalisan || (calisan && !calisan.askida ? calisan : null);
    if (anlatan && anlatan.tur === 'adimlar') {
      durak.duraklat('soz');
    } else if (ses.konusuyor || calisan || sira.length) {
      sozAlindi = true;
      sozBitti = new Promise((r) => { sozBittiCoz = r; });
      durdur(null);
    }
  }
  function sozBitir() {
    if (sozBittiCoz) { const c = sozBittiCoz; sozBittiCoz = null; c(); }
  }

  async function sozGonder(metin, ek) {
    yaziEl.value = '';
    gonderBtn.disabled = true;
    altyazi(metin, 'Siz');
    const govde = { metin, motor: (ek && ek.motor) || 'yazi' };
    if (ek && ek.ham_metin) govde.ham_metin = ek.ham_metin;
    try {
      const r = await api('soyle', govde);
      const j = await r.json();
      if (j.claude_dinliyor) {
        toast('Claude\'a iletildi.', 4000);
        if (durak.soz) durumEl.textContent = 'Sorunuz Claude\'a iletildi · anlatım kaldığı yerde bekliyor';
      } else {
        bekleyenGoster([metin]);
      }
    } catch (e) {
      toast('Gönderilemedi: ' + e.message + ' (sunucu yeniden başlatılmalı olabilir)', 7000);
      yaziEl.value = metin; // kaybolmasın
      gonderBtn.disabled = false;
    }
    sozBitir();
  }

  // Yazı kutusu: yazmaya başlamak söz almaktır; Enter ya da ↑ gönderir.
  const YER_TUTUCU = 'Claude\'a yazın…';
  const yaziEl = $('#yazi');
  const gonderBtn = $('#gonder');
  const dokEl = $('#dok');
  yaziEl.placeholder = YER_TUTUCU;
  yaziEl.addEventListener('input', () => {
    onay.durdur();
    const dolu = !!yaziEl.value.trim();
    gonderBtn.disabled = !dolu;
    if (dolu && !mik.aktif && !durak.soz) sozAl();
  });
  yaziEl.addEventListener('pointerdown', () => onay.durdur());
  yaziEl.addEventListener('keydown', (e) => {
    if (e.key !== 'Enter') onay.durdur();
    if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      yaziGonder();
    } else if (e.key === 'Escape') {
      yaziEl.blur();
    }
  });
  // Yazmaya başlayıp vazgeçerse (kutu boş, odak gitti) anlatım sürer.
  yaziEl.addEventListener('blur', () => {
    setTimeout(() => {
      if (!yaziEl.value.trim() && !mik.aktif && durak.soz && document.activeElement !== yaziEl) durak.devam();
    }, 300);
  });
  function yaziGonder() {
    const metin = yaziEl.value.trim();
    if (!metin) return;
    if (mik.aktif) { mik.yazilan = metin; mik.bitir(); return; } // dikteyi bitir, kutudakini gönder
    if (onay.bilgi) return onay.gonder();
    sozGonder(metin);
  }
  gonderBtn.addEventListener('click', yaziGonder);

  // ---------- Konuşma şeridi (eski altyazı): son iki ileti ----------
  const oncekiEl = $('#onceki');
  function altyazi(metin, kim) {
    if (capEl.textContent && capEl.dataset.kim && capEl.dataset.kim !== kim) {
      oncekiEl.dataset.kim = capEl.dataset.kim;
      oncekiEl.textContent = capEl.textContent;
      oncekiEl.hidden = false;
    }
    capEl.dataset.kim = kim;
    capEl.classList.toggle('siz', kim === 'Siz');
    capEl.textContent = metin;
  }

  // ---------- Ders (görseller için) ----------
  let ders = { assets: {} };
  let dersId = null;
  // Tablodaki "?" hücresine verilen cevap Claude'a öğrencinin sözü olarak gider.
  function tabloYanitiBagla(b) {
    b.onTabloYanit = (y) => {
      const yer = [y.tablo, y.satir, y.sutun].filter(Boolean).join(' · ');
      if (y.yaz) {
        yaziEl.value = 'Tablo yanıtı · ' + yer + ': ';
        yaziEl.focus();
        gonderBtn.disabled = false;
        return;
      }
      sozGonder('Tablo yanıtı · ' + yer + ': ' + y.yanit + (y.secenekli ? ' (seçenekten)' : ''), { motor: 'yazi' });
    };
    return b;
  }
  let board = tabloYanitiBagla(new AT.Board(boardEl, ders));

  async function egitmenDersi(id, base, ilkHata) {
    const r = await fetch(base + 'egitmen.json', { cache: 'no-store' });
    if (!r.ok) throw ilkHata;
    const eg = await r.json();
    const assets = {};
    for (const [k, g] of Object.entries(eg.gorseller || {})) {
      assets[k] = { src: g.src, caption: (g.baslik ? g.baslik + '. ' : '') + (g.aciklama || ''), alt: g.aciklama || k, makaleden: g.makaleden };
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
    board = tabloYanitiBagla(new AT.Board(boardEl, ders));
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
      mola: !!(AT.molada && AT.molada()), // kullanıcı ⚙ Ayarlar'dan mola verdi: yeni anlatım başlatma, dönmesini bekle
      kaldigi_yer: kaldigiYer(),
      video: board.video ? board.video.durum : null,
      ses_engelli: sesEngelli, // tarayıcı sesi engelledi; kullanıcı ekrandaki düğmeye dokunmalı
      ses_motoru: sesEl && !sesEl.hidden ? sesEl.textContent.replace(/^Ses: /, '') : null,
      dikte: dikte.motor(),
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
        if (c.type === 'compare' && Array.isArray(c.columns)) {
          for (const col of c.columns) {
            if (col && col.asset && !(ders.assets || {})[col.asset]) uyarilar.push('Görsel yok: ' + col.asset);
          }
        }
        if (typeof board['cmd_' + c.type] !== 'function') { uyarilar.push('Bilinmeyen komut: ' + c.type); continue; }
        try { board.run(c, false); } catch (e) { uyarilar.push(c.type + ': ' + e.message); }
      }
      // Video oynuyorsa anlatım video bitince (ya da bitis saniyesinde) başlar. bekle:false ise üstüne anlatılır.
      const vk = (Array.isArray(a.komutlar) ? a.komutlar : []).find((c) => c && c.type === 'video' && c.oynat !== false && c.bekle !== false);
      if (vk && board.video) await videoBekle(k, board.video, uyarilar);
      if (k.iptal) return { durum: 'iptal', tamamlanan: i, uyarilar };
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
      // Şablon canlandırması (draw.gecis) cümleden uzun sürdüyse sıradaki adım onun bitmesini bekler.
      if (!k.iptal) await board.animBekle();
    }
    if (k.iptal) return { durum: 'iptal', tamamlanan: liste.length, uyarilar };
    return uyarilar.length ? { durum: 'bitti', uyarilar } : { durum: 'bitti' };
  }

  // Video bitene kadar bekler. Duraklatma ve söz alma videoyu da durdurur (durak), askıya alınan anlatımın
  // videosu da bekler; devam edince video kaldığı yerden sürer.
  async function videoBekle(k, v, uyarilar) {
    let askidaDurdu = false;
    const basla = Date.now();
    for (;;) {
      if (k.iptal) { v.duraklat(); return; }
      if (v.durum === 'bitti') return;
      if (v.durum === 'hata') { uyarilar.push('Video oynatılamadı (' + (v.hata || 'hata') + ')'); return; }
      if (k.askida && v.durum === 'oynuyor') { v.duraklat(); askidaDurdu = true; }
      if (!k.askida && askidaDurdu && !durak.aktif) { askidaDurdu = false; v.oynat(); }
      if (v.durum === 'bekliyor' && !durak.aktif && !k.askida) {
        const gecen = Date.now() - basla;
        if ((v.engellendi || gecen > 4000) && !v.dugmeAcik && v.dugmeGoster) {
          // Tarayıcı kendiliğinden oynatmayı engelledi: videonun üstünde büyük ▶; anlatıcı da söyler.
          v.dugmeGoster();
          // Ses de engelliyse söylenemez (yalnız düğme); ses açıksa anlatıcı da söyler.
          if (ses.izinli) ses.anlat('Video kendiliğinden başlamadı. Başlatmak için videonun üstündeki büyük oynat düğmesine dokunun.');
        }
        if (gecen > 25000) {
          uyarilar.push('Video başlamadı: tarayıcı kendiliğinden oynatmayı engelledi. Tahtada videonun üstünde büyük ▶ '
            + 'düğmesi gösteriliyor; kullanıcıdan ▶\'e basmasını iste, sonra tahta_durumu ile videonun oynadığını denetle.');
          return;
        }
      }
      await Promise.race([v.bitti, new Promise((r) => setTimeout(r, 250))]);
    }
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
        sonuc = Object.assign({}, sonuc, { not: 'Kullanıcı mikrofonla söz aldı; söylediğini bekle aracıyla al.' });
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
      figure: board.figure, lastList: board.lastList, video: board.video
    };
    if (board.video) board.video.duraklat();
    board.video = null; // cevap tahtayı temizlese bile saklanan video kapanmasın
    // Cevap, tahtanın bir kopyası üzerine çizilir (görsel işaretlenebilsin diye görsel de kopyalanır).
    const kopya = (dizi) => dizi.map((n) => {
      const c = n.cloneNode(true);
      // Kopyadaki video ve YouTube çerçevesi yeniden oynamasın: yerine işaret konur.
      if (c.querySelectorAll) {
        c.querySelectorAll('video, iframe').forEach((x) => x.replaceWith(el('p', 'video-hata', '⏸ Video bekliyor')));
      }
      return c;
    });
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
    if (board.video && board.video !== t.video) board._videoBirak(); // cevabın videosu kapanır
    board = t.board; ders = t.ders; dersId = t.dersId;
    if (dersId) dersAdiEl.textContent = 'Canlı tahta · ' + (ders.title || dersId);
    board.header.replaceChildren(...t.header);
    board.visual.replaceChildren(...t.visual);
    board.notes.replaceChildren(...t.notes);
    board.figure = t.figure;
    board.lastList = t.lastList;
    board.video = t.video;
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

  // Tahtanın o anki görüntüsü (tahta_durumu goruntu:true). Anlatımı bölmez; sıradaki komutları beklemez.
  async function goruntuVer(k) {
    let sonuc;
    try {
      if (!AT.tahtaGoruntu) throw new Error('tahta-goruntu.js yüklenmedi');
      const g = await AT.tahtaGoruntu(document.getElementById('board'), { enFazla: k.en_fazla || 1400 });
      sonuc = { durum: 'bitti', png: g.png, en: g.en, boy: g.boy,
        baslik: (document.querySelector('#board .board-title') || {}).textContent || '' };
    } catch (e) {
      sonuc = { durum: 'hata', hata: String(e && e.message || e) };
    }
    api('bitti', { no: k.no, sonuc, durum: durum() }).catch(() => {});
  }

  function durdur(k) {
    ses.dur();
    if (board.video) board.video.duraklat();
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

  // Claude 'bekle' aracıyla (ya da bekleyen bir tahta çağrısıyla) beklerken mikrofon tuşunun çevresinde
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
  // Otomatik uyandırma: Claude dinlemiyorken söylenen söz birkaç saniye sonra Claude sohbetine kendiliğinden yazılıp
  // gönderilir (tools/uyandirma.py). Bekleyen uyarısındaki düğmeyle açılıp kapatılır.
  let uyandirmaT = '';
  let uyandirmaAcik = false;
  const uyDugme = $('#otomatikGonder');
  function uyandirmaGoster(u) {
    uyandirmaAcik = !!u.acik;
    if (uyDugme && u.destek === false) uyDugme.hidden = true; // bu sistemde otomatik gönderme yok
    if (uyDugme) {
      uyDugme.setAttribute('aria-pressed', uyandirmaAcik ? 'true' : 'false');
      uyDugme.textContent = 'Otomatik gönder: ' + (uyandirmaAcik ? 'açık' : 'kapalı');
    }
    const t = u.t === undefined ? '' : String(u.t);
    if (t === uyandirmaT) return;
    const ilk = uyandirmaT === '';
    uyandirmaT = t;
    if (ilk) return; // sayfa yeni açıldı: eski bildirimi gösterme
    if (u.durum === 'gonderildi') toast('Sorunuz Claude sohbetine gönderildi; Claude birazdan tahtada cevaplar.', 6000);
    else if (u.durum === 'olmadi') toast('Sorunuz Claude\'a kendiliğinden gönderilemedi: ' + (u.neden || '') +
      ' Sohbete "tahtaya bak" yazın ya da "Sohbete kopyala"ya basın.', 9000);
    bekleyenGoster(bekleyenSoz);
  }
  if (uyDugme) uyDugme.addEventListener('click', async () => {
    try {
      const r = await api('uyandirma', { acik: !uyandirmaAcik });
      uyandirmaGoster(await r.json());
    } catch (e) { toast('Ayar değiştirilemedi: ' + e.message, 5000); }
  });

  // Claude dinlemiyorken söylenenler: üstte uyarı ve "Sohbete kopyala" düğmesi.
  let bekleyenSoz = [];
  const bekleyenEl = $('#bekleyenSoru');
  function bekleyenGoster(liste) {
    bekleyenSoz = (liste || []).slice();
    const goster = bekleyenSoz.length > 0 && !claudeDinliyor;
    bekleyenEl.hidden = !goster;
    if (goster) $('#bekleyenMetin').textContent = '“' + bekleyenSoz.join(' ') + '”';
    const aciklama = $('#bekleyenAciklama');
    if (aciklama) aciklama.innerHTML = uyandirmaAcik
      ? 'Claude şu an dinlemiyor. Sorunuz birkaç saniye içinde Claude sohbetine <b>kendiliğinden</b> gönderilecek.'
      : 'Claude şu an dinlemiyor. Sohbete <b>“tahtaya bak”</b> yazın ya da sorunuzu kopyalayıp yapıştırın.';
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

  // Sayfanın sürümü (config.js) sunucununkinden farklıysa tarayıcı eski dosyaları vermiştir: bir kez yenile.
  // Yine farklıysa (ör. program açıkken güncellendi, sunucu eski) yalnız uyar.
  const SAYFA_SURUM = (AT.config && AT.config.version) || '';
  function surumDenetle(sunucu) {
    const et = $('#surumEtiket');
    if (et) { et.textContent = SAYFA_SURUM ? 'v' + SAYFA_SURUM : ''; et.classList.remove('uyumsuz'); }
    if (!sunucu || !SAYFA_SURUM || sunucu === SAYFA_SURUM) return false;
    const anahtar = 'klinikkoc.surumYenile.' + sunucu;
    let denendi = false;
    try { denendi = sessionStorage.getItem(anahtar) === '1'; sessionStorage.setItem(anahtar, '1'); } catch (e) { denendi = true; }
    if (!denendi) { location.reload(); return true; }
    if (et) {
      et.textContent = 'v' + SAYFA_SURUM + ' ≠ ' + sunucu;
      et.classList.add('uyumsuz');
      et.title = 'Sayfa ile program sürümü farklı. Tahtayı kapatıp KlinikKoç\'u yeniden başlatın.';
    }
    return false;
  }

  let son = 0;
  async function yokla() {
    try {
      const r = await api('merhaba', { durum: durum() });
      const j = await r.json();
      son = j.sayac || 0;
      if (surumDenetle(j.surum)) return; // sayfa eski sürümün dosyalarıyla açılmış: kendini yeniliyor
      sesGoster(j.ses);
      if (j.ogretmen && AT.sihirbazDugmesiGoster) AT.sihirbazDugmesiGoster();
      if (j.uyandirma) uyandirmaGoster(j.uyandirma);
    } catch (e) {
      baglanti(false);
      return setTimeout(yokla, 3000);
    }
    baglanti(true);
    for (;;) {
      if (sekmeKapandi) return;
      try {
        const r = await api('al?son=' + son + '&dinliyor=' + (claudeDinliyor ? 1 : 0) + '&bekleyen=' + bekleyenSoz.length +
          '&uy=' + encodeURIComponent(uyandirmaT), undefined, 45000);
        const j = await r.json();
        if (sekmeKapandi) return;
        const komutlar = j.komutlar;
        sesGoster(j.ses);
        baglanti(true);
        if (typeof j.dinliyor === 'boolean' && j.dinliyor !== claudeDinliyor) dinlemeIsareti(j.dinliyor);
        if (j.uyandirma) uyandirmaGoster(j.uyandirma);
        if (Array.isArray(j.bekleyen_konusma)) bekleyenGoster(j.bekleyen_konusma);
        for (const k of komutlar || []) {
          son = Math.max(son, k.no);
          if (k.tur === 'dur') durdur(k);
          else if (k.tur === 'goruntu') goruntuVer(k); // Claude tahtaya bakmak istiyor: sırayı beklemez
          else if (k.tur === 'devam') {
            if (araCalisan || araSira.length) { araSira.push(k); araIsle(); } else anlatimaDon(k);
          } else if (calisan && calisan.tur === 'adimlar' && (durak.soz || durak.aktif || calisan.askida)) {
            // Elle duraklatılmışken (⏸) gelen yeni cevap da beklemez: duraklayan anlatım askıya alınır,
            // cevap hemen tahtaya gelir; ▶ ile anlatım kaldığı yerden sürer.
            // Söz alınıp duraklayan bir cevap varsa o bırakılır; yeni cevap onun yerine geçer.
            if (araCalisan && (durak.soz || durak.aktif)) { araCalisan.iptal = true; ses.dur(); durak.sifirla(); }
            araSira.push(k);
            araIsle();
          } else {
            // Duraklatma bir anlatıma bağlı değilse (ör. video) yeni komut onu beklemesin.
            if (durak.aktif && !(calisan && calisan.tur === 'adimlar')) durak.sifirla();
            sira.push(k);
          }
        }
        isle();
      } catch (e) {
        if (sekmeKapandi) return;
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
  // Tam ekranda üst çubuk gizlenir; fare/dokunuş ekranın üst kenarına gelince 3 sn görünür.
  (() => {
    const kok = $('#lesson'); let sayac = null;
    const goster = () => { kok.classList.add('ust-acik'); clearTimeout(sayac); sayac = setTimeout(() => kok.classList.remove('ust-acik'), 3000); };
    document.addEventListener('fullscreenchange', () => { kok.classList.toggle('tam', !!document.fullscreenElement); if (document.fullscreenElement) goster(); });
    document.addEventListener('mousemove', (e) => { if (e.clientY < 48 && kok.classList.contains('tam')) goster(); });
    document.addEventListener('touchstart', (e) => { const t = e.touches[0]; if (t && t.clientY < 48 && kok.classList.contains('tam')) goster(); }, { passive: true });
    // Altyazı: 1 ileti → 2 ileti → kapalı
    const dok = $('#dok'), dugme = $('#altyazi'), adlar = { 1: 'Altyazı: 1 ileti', 2: 'Altyazı: 2 ileti', 0: 'Altyazı: kapalı' };
    let durumu = '1';
    try { durumu = localStorage.getItem('klinikkoc-altyazi') || '1'; } catch (e) { /* depolama kapalı */ }
    const yaz = () => { if (!(durumu in adlar)) durumu = '1'; dok.dataset.altyazi = durumu; dugme.textContent = adlar[durumu]; };
    dugme.addEventListener('click', () => { durumu = { 1: '2', 2: '0', 0: '1' }[durumu]; yaz(); try { localStorage.setItem('klinikkoc-altyazi', durumu); } catch (e) { /* depolama kapalı */ } });
    yaz();
  })();
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
    const v = board.video; // tarayıcının engellediği video da bu dokunuşla başlar
    if (v && v.durum === 'bekliyor' && v.dugmeAcik) { v.dugmeGizle(); v.oynat(); }
    if (tam) tamEkran();
  }
  dikte.goster();
  dikte.yenile();
  setInterval(() => { if (!mik.aktif && !mik.isleniyor) dikte.yenile(); }, 60000); // Duyu sonradan kurulursa görünsün
  $('#baslatPencere').addEventListener('click', () => baslat(false));
  $('#baslatTam').addEventListener('click', () => baslat(true));

  board.run({ type: 'title', text: 'Canlı tahta', subtitle: 'Claude masaüstü uygulamasında bir konu isteyin; tahtayı Claude yönetecek.' }, true);
  board.run({ type: 'bullets', title: 'Örnek istekler', items: [
    '"Tahtada bana peri-implantitis defekt sınıflamasını anlat."',
    '"Şekil 2\'yi göster ve Sınıf Ib\'yi işaretle."',
    '"Bana bu konudan iki soru sor."'
  ] }, true);
  // ---------- ⚙ Ayarlar: zemin, yan paneller, mola (5.0) ----------
  // Seçimler bu bilgisayarda (localStorage) hatırlanır. Açık zemin varsayılandır; paneller kapalı başlar.
  const AYAR_ANAHTAR = 'klinikkoc.tahtaAyar';
  const ayar = (() => {
    let a = {};
    try { a = JSON.parse(localStorage.getItem(AYAR_ANAHTAR) || '{}') || {}; } catch (e) { a = {}; }
    return { zemin: a.zemin === 'koyu' ? 'koyu' : 'acik', akis: !!a.akis, ilerleme: !!a.ilerleme };
  })();
  const lessonEl = $('#lesson');
  const ayarMenu = $('#ayarMenu'), ayarBtn = $('#ayarAc'), yanPanel = $('#yanPanel');
  function ayarKaydet() { try { localStorage.setItem(AYAR_ANAHTAR, JSON.stringify(ayar)); } catch (e) { /* özel pencere */ } }
  function ayarUygula() {
    lessonEl.dataset.zemin = ayar.zemin;
    const m = document.querySelector('meta[name="theme-color"]');
    if (m) m.content = '#EAE5DC';
    $('#zeminAcik').checked = ayar.zemin === 'acik';
    $('#zeminKoyu').checked = ayar.zemin === 'koyu';
    $('#panelAkis').checked = ayar.akis;
    $('#panelIlerleme').checked = ayar.ilerleme;
    $('#akisBolum').hidden = !ayar.akis;
    $('#ilerlemeBolum').hidden = !ayar.ilerleme;
    const panel = ayar.akis || ayar.ilerleme;
    yanPanel.hidden = !panel;
    lessonEl.classList.toggle('panelli', panel);
    if (ayar.akis) akisGoster();
    if (ayar.ilerleme) ilerlemeYenile();
  }
  ayarBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    ayarMenu.hidden = !ayarMenu.hidden;
    ayarBtn.setAttribute('aria-expanded', String(!ayarMenu.hidden));
  });
  document.addEventListener('click', (e) => {
    if (!ayarMenu.hidden && !ayarMenu.contains(e.target) && e.target !== ayarBtn) {
      ayarMenu.hidden = true; ayarBtn.setAttribute('aria-expanded', 'false');
    }
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !ayarMenu.hidden) { e.stopPropagation(); ayarMenu.hidden = true; ayarBtn.setAttribute('aria-expanded', 'false'); }
  }, true);
  $('#zeminAcik').addEventListener('change', () => { ayar.zemin = 'acik'; ayarKaydet(); ayarUygula(); });
  $('#zeminKoyu').addEventListener('change', () => { ayar.zemin = 'koyu'; ayarKaydet(); ayarUygula(); });
  $('#panelAkis').addEventListener('change', (e) => { ayar.akis = e.target.checked; ayarKaydet(); ayarUygula(); });
  $('#panelIlerleme').addEventListener('change', (e) => { ayar.ilerleme = e.target.checked; ayarKaydet(); ayarUygula(); });

  // Ders akışı: bu oturumda tahtaya gelen başlıklar (sırayla) ve anlatımın neresinde olunduğu.
  const akis = [];
  let akisDers = null;
  function akisGoster() {
    const liste = $('#akisListe');
    liste.replaceChildren(...akis.map((t, i) => { const li = el('li', i === akis.length - 1 ? 'simdi' : '', t); return li; }));
    $('#akisBos').hidden = akis.length > 0;
    const y = kaldigiYer();
    const adim = $('#akisAdim');
    if (y && y.toplam) {
      adim.replaceChildren(document.createTextNode('Anlatım: adım ' + y.adim + ' / ' + y.toplam + (y.askida ? ' (beklemede)' : '')));
      const c = el('div', 'cubuk'); const i = el('i'); i.style.width = Math.round(100 * y.adim / y.toplam) + '%'; c.appendChild(i);
      adim.appendChild(c);
    } else adim.replaceChildren();
  }
  new MutationObserver(() => {
    const h = boardEl.querySelector('.board-title h2');
    const t = h ? h.textContent.trim() : '';
    if (dersId !== akisDers) { akis.length = 0; akisDers = dersId; if (ayar.ilerleme) ilerlemeYenile(); }
    if (t && t !== 'Canlı tahta' && akis[akis.length - 1] !== t) {
      const eski = akis.indexOf(t);
      if (eski >= 0) akis.splice(eski, 1); // aynı konuya dönülünce sona taşınır
      akis.push(t);
    }
    if (ayar.akis) akisGoster();
  }).observe(boardEl.querySelector('.board-title'), { childList: true, subtree: true, characterData: true });
  setInterval(() => { if (ayar.akis) akisGoster(); }, 1500);

  // İlerleme: dersin hedefleri; durum bu bilgisayardaki kayıttan (eğitmen kayit_yaz ile işledikçe değişir).
  const DURUM_YAZI = { ele_alinmadi: 'henüz çalışılmadı', destekle_yapti: 'yardımla yaptı', bagimsiz_yapti: 'kendi başına yaptı',
    tekrar_gerekli: 'tekrar gerekli', devam_ediyor: 'devam ediyor' };
  let ilerlemeSon = 0;
  async function ilerlemeYenile() {
    const liste = $('#ilerlemeListe'), bos = $('#ilerlemeBos');
    if (!dersId) { liste.replaceChildren(); bos.hidden = false; return; }
    ilerlemeSon = Date.now();
    try {
      const r = await fetch('/api/canli/ilerleme?ders=' + encodeURIComponent(dersId), { cache: 'no-store' });
      const j = await r.json();
      const h = j.hedefler || [];
      liste.replaceChildren(...h.map((x) => {
        const li = el('li', x.durum || 'ele_alinmadi');
        li.appendChild(el('span', 'nokta'));
        li.appendChild(el('span', 'ad', x.baslik || x.id));
        const alt = [DURUM_YAZI[x.durum] || x.durum || ''];
        if (x.cevap) alt.push(x.cevap + ' cevap');
        li.appendChild(el('span', 'alt', alt.filter(Boolean).join(' · ')));
        return li;
      }));
      bos.hidden = h.length > 0;
      if (!h.length) bos.textContent = 'Bu dersin tanımlı hedefi yok.';
    } catch (e) { /* sunucu kapalı: sonra yeniden denenir */ }
  }
  setInterval(() => { if (ayar.ilerleme && !yanPanel.hidden && Date.now() - ilerlemeSon > 20000) ilerlemeYenile(); }, 5000);

  // Mola: anlatım duraklar (sürüyorsa), süre sayılır; Devam ile kaldığı yerden sürer. Claude durumda 'mola' görür.
  const molaEl = $('#mola');
  let molaBas = 0, molaT = null, molaDuraklatti = false;
  function molaVer() {
    ayarMenu.hidden = true; ayarBtn.setAttribute('aria-expanded', 'false');
    if (!molaEl.hidden) return;
    molaDuraklatti = false;
    if (!durak.aktif && durak.kullanilabilir()) { durak.duraklat(); molaDuraklatti = durak.aktif; }
    molaBas = Date.now();
    molaEl.hidden = false;
    const yaz = () => { const s = Math.floor((Date.now() - molaBas) / 1000); $('#molaSure').textContent = Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); };
    yaz(); molaT = setInterval(yaz, 1000);
    api('duraklat', { duraklatildi: durak.aktif, durum: durum() }).catch(() => {});
    $('#molaBitir').focus();
  }
  function molaBitir() {
    if (molaEl.hidden) return;
    molaEl.hidden = true;
    clearInterval(molaT);
    if (molaDuraklatti && durak.aktif) durak.devam();
    molaDuraklatti = false;
    api('duraklat', { duraklatildi: durak.aktif, durum: durum() }).catch(() => {});
  }
  AT.molada = () => !molaEl.hidden;
  $('#molaVer').addEventListener('click', molaVer);
  $('#molaBitir').addEventListener('click', molaBitir);
  ayarUygula();

  // ---------- Sihirbaz katmanı ----------
  // Sihirbaz tahtanın üstünde bir katmanda açılır; tahta sayfası kapanmadığı için çizim, ses ve
  // Claude bağlantısı olduğu gibi kalır. Aynı tuş (ya da sihirbazdaki "Tahtaya dön") geri getirir.
  (function () {
    const dugme = $('#sihirbazAc'), kat = $('#sihirbazKat'), cerceve = $('#sihirbazCerceve');
    if (!dugme || !kat || !cerceve) return;
    function goster(ac) {
      if (ac && !cerceve.getAttribute('src')) cerceve.setAttribute('src', 'sihirbaz.html?gomulu=1');
      const ust = document.querySelector('.canli .topbar');
      if (ust) kat.style.top = ust.offsetHeight + 'px';
      kat.hidden = !ac;
      dugme.setAttribute('aria-pressed', ac ? 'true' : 'false');
      dugme.textContent = ac ? 'Tahta' : 'Sihirbaz';
      if (ac) cerceve.focus(); else dugme.blur();
    }
    // Tuş yalnızca öğretmenin bilgisayarında görünür: sihirbaz bir kez açılmış ya da taslak varsa.
    let ogretmen = false;
    try { ogretmen = localStorage.getItem('klinikkoc-ogretmen') === '1'; } catch (e) { /* depolama kapalı */ }
    if (ogretmen) dugme.hidden = false;
    AT.sihirbazDugmesiGoster = () => { dugme.hidden = false; };
    dugme.addEventListener('click', () => goster(kat.hidden));
    window.addEventListener('message', (e) => {
      if (e.origin !== location.origin || !e.data) return;
      if (e.data.klinikkoc === 'tahtaya-don') goster(false);
    });
  })();

  // ---------- Tek sekme ----------
  // Aynı tahta ikinci bir sekmede açılınca eski sekme bağlantıyı bırakır ve bunu söyler.
  try {
    const kanal = new BroadcastChannel('klinikkoc-canli-tahta');
    const benimKimlik = Date.now() + '-' + Math.random().toString(36).slice(2);
    kanal.onmessage = (e) => {
      if (!e.data || e.data.tur !== 'yeni' || e.data.kimlik === benimKimlik || sekmeKapandi) return;
      sekmeKapandi = true;
      sekmeKesici.abort();
      ses.dur();
      if (board.video) board.video.duraklat();
      $('#baslat').hidden = true;
      $('#sesAc').hidden = true;
      $('#baskaSekme').hidden = false;
      dot.classList.remove('bagli');
      durumEl.textContent = 'Bu tahta başka bir sekmede açık';
    };
    kanal.postMessage({ tur: 'yeni', kimlik: benimKimlik });
  } catch (e) { /* BroadcastChannel yoksa eski davranış */ }
  $('#buradaDevam').addEventListener('click', () => location.reload());

  yokla();
})(window.AT = window.AT || {});
