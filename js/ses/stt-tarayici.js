/* Konuşma tanıma adaptörü: tarayıcının Web Speech API'si (SpeechRecognition). İki mod:
 *   tarayici-sunucu : Chrome'un varsayılanı. Ses Google sunucularına gönderilir ve orada yazıya çevrilir.
 *   tarayici-cihaz  : processLocally = true. Ses cihazdan çıkmaz; dil paketi bir kez indirilir.
 *                     Türkçe paketin olup olmadığını SpeechRecognition.available() söyler.
 * Kaydı motora vermek için Chrome'un start(MediaStreamTrack) desteği kullanılır; böylece
 * diğer motorlarla aynı kayıt dinletilir. Bu destek yoksa "canlı" modda mikrofon dinlenir. */
(function (AT) {
  'use strict';
  const ses = AT.ses;
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const LANG = 'tr-TR';

  // Bazı ortamlarda cihaz içi durum sorgusu yanıt vermiyor, hatta sekmeyi çökertiyor (ör. ekransız
  // Chromium). Bu yüzden: süre sınırı var; sorgudan önce bir işaret bırakılır, sayfa çökerse
  // bir sonraki açılışta sorgu yapılmaz ve nedeni yazılır.
  const GUARD = 'at:sr-local-check';
  function guardSet(v) { try { v ? localStorage.setItem(GUARD, String(Date.now())) : localStorage.removeItem(GUARD); } catch (e) { /* yok */ } }
  function crashedBefore() { try { return !!localStorage.getItem(GUARD); } catch (e) { return false; } }

  async function availability(local) {
    if (!SR) return 'yok';
    if (typeof SR.available !== 'function') return local ? 'desteklenmiyor' : 'bilinmiyor';
    if (local && crashedBefore()) return 'cokme';
    if (local) guardSet(true);
    try {
      return await Promise.race([
        SR.available({ langs: [LANG], processLocally: local }),
        new Promise((r) => setTimeout(() => r('zamanasimi'), 10000))
      ]);
    } catch (e) {
      return 'hata: ' + e.message;
    } finally {
      if (local) guardSet(false);
    }
  }

  const STATUS_TEXT = {
    available: 'Türkçe hazır.',
    downloadable: 'Türkçe paket indirilebilir (hazırlıkta indirilir).',
    downloading: 'Türkçe paket iniyor.',
    unavailable: 'Türkçe bu modda desteklenmiyor.',
    desteklenmiyor: 'Bu tarayıcıda cihaz içi mod yok (Chrome güncel mi?).',
    bilinmiyor: 'Tarayıcı durum bildirmiyor; denenecek.',
    zamanasimi: 'Tarayıcı 10 saniyede yanıt vermedi; cihaz içi tanıma bu cihazda çalışmıyor olabilir.',
    cokme: 'Önceki denemede sayfa bu kontrol sırasında kapandı; bu tarayıcıda cihaz içi tanıma desteklenmiyor. (Yeniden denemek için Ayarlar > Site verilerini temizleyin.)',
    bekliyor: 'Türkçe paket durumu "Hazırla"ya basınca kontrol edilir.',
    yok: 'Bu tarayıcıda konuşma tanıma yok (Chrome veya Edge gerekir).'
  };

  function make(local) {
    const id = local ? 'tarayici-cihaz' : 'tarayici-sunucu';
    return () => ({
      id,
      label: local ? 'Tarayıcı · cihaz içi' : 'Tarayıcı · Google sunucusu',
      info: local
        ? { offline: 'Evet (paket indirildikten sonra)', dataLeavesDevice: 'Hayır', note: 'Chrome\'un cihaz içi tanıması; Türkçe paketi varsa.' }
        : { offline: 'Hayır', dataLeavesDevice: 'Evet: ses Google sunucularına gider', note: 'Kurulum yok, internet gerekir.' },
      realtime: true, // kayıt gerçek zamanlı dinletilir: süre en az kayıt kadar
      live: false,     // true olursa kayıt yerine mikrofon dinlenir
      lastAvailability: null,
      async status() {
        // Cihaz içi sorgu riskli olduğu için sayfa açılışında yapılmaz; hazırlıkta yapılır.
        if (local && SR && typeof SR.available === 'function' && !crashedBefore()) {
          return { ok: true, message: STATUS_TEXT.bekliyor, raw: 'bekliyor' };
        }
        const a = await availability(local);
        this.lastAvailability = a;
        const ok = a === 'available' || a === 'downloadable' || a === 'downloading' || (!local && a === 'bilinmiyor');
        return { ok, message: STATUS_TEXT[a] || String(a), raw: a };
      },
      async init() {
        const t0 = performance.now();
        if (local) {
          const a = await availability(true);
          if (a === 'downloadable' || a === 'downloading') {
            const ok = await SR.install({ langs: [LANG], processLocally: true });
            if (!ok) throw new Error('Türkçe cihaz içi paket indirilemedi.');
          } else if (a !== 'available') {
            throw new Error(STATUS_TEXT[a] || 'Cihaz içi tanıma kullanılamıyor: ' + a);
          }
        }
        return { loadMs: performance.now() - t0, bytes: null };
      },
      transcribe(audio16k) {
        return recognize(local, audio16k, this.live);
      }
    });
  }

  // Kaydı tarayıcının tanıyıcısına gerçek zamanlı dinletir; kayıt bitince son sonucu bekler.
  // Gecikme (ms): kaydın bitişinden son kesin sonuca kadar geçen süre.
  function recognize(local, audio16k, live) {
    return new Promise((resolve, reject) => {
      if (!SR) return reject(new Error('Konuşma tanıma yok.'));
      const rec = new SR();
      rec.lang = LANG;
      rec.continuous = true;
      rec.interimResults = true;
      rec.maxAlternatives = 1;
      if ('processLocally' in rec) rec.processLocally = local;
      else if (local) return reject(new Error('Cihaz içi mod desteklenmiyor.'));

      let ctx = null, src = null, audioEnd = null, lastFinal = null, pending = false, stopTimer = null, settled = false;
      const finals = [];
      const durMs = audio16k.length / ses.SAMPLE_RATE * 1000;
      const t0 = performance.now();

      const finish = (err) => {
        if (settled) return;
        settled = true;
        clearTimeout(stopTimer);
        try { src && src.stop(); } catch (e) { /* bitti */ }
        try { ctx && ctx.close(); } catch (e) { /* kapalı */ }
        if (err) return reject(err);
        const end = audioEnd || performance.now();
        resolve({
          text: finals.join(' ').replace(/\s+/g, ' ').trim(),
          ms: lastFinal ? Math.max(0, lastFinal - end) : null,
          totalMs: performance.now() - t0,
          audioMs: durMs,
          source: live ? 'mikrofon' : 'kayıt'
        });
      };
      // Ses bitti ve bekleyen ara sonuç yoksa durdur; en fazla 6 sn bekle.
      const maybeStop = () => {
        if (audioEnd && !pending) { clearTimeout(stopTimer); stopTimer = setTimeout(() => rec.stop(), 700); }
      };

      rec.onresult = (ev) => {
        pending = false;
        for (let i = ev.resultIndex; i < ev.results.length; i++) {
          const r = ev.results[i];
          if (r.isFinal) { finals.push(r[0].transcript); lastFinal = performance.now(); } else pending = true;
        }
        maybeStop();
      };
      rec.onerror = (ev) => {
        if (ev.error === 'no-speech' || ev.error === 'aborted') return; // sessizlik: boş sonuç
        finish(new Error('Tanıma hatası: ' + ev.error + (ev.message ? ' (' + ev.message + ')' : '')));
      };
      rec.onend = () => finish();

      if (live) {
        // Canlı mod: mikrofonu dinle; kayıt süresi kadar sonra durmaya hazırlan.
        rec.start();
        setTimeout(() => { audioEnd = performance.now(); maybeStop(); setTimeout(() => rec.stop(), 6000); }, durMs + 300);
        return;
      }

      ctx = new AudioContext({ sampleRate: ses.SAMPLE_RATE });
      const buf = ctx.createBuffer(1, audio16k.length, ses.SAMPLE_RATE);
      buf.copyToChannel(audio16k, 0);
      // Kayıt 0,3 sn gecikmeyle başlar: tanıyıcının ilk heceyi kaçırmaması için.
      const dest = ctx.createMediaStreamDestination();
      src = ctx.createBufferSource();
      src.buffer = buf;
      src.connect(dest);
      src.onended = () => { audioEnd = performance.now(); maybeStop(); stopTimer = setTimeout(() => rec.stop(), 6000); };
      const track = dest.stream.getAudioTracks()[0];
      try {
        rec.start(track);
      } catch (e) {
        return finish(new Error('Tarayıcı kayıttan tanımayı desteklemiyor (' + e.message + '). Canlı modu kullanın.'));
      }
      ctx.resume().then(() => src.start(ctx.currentTime + 0.3));
    });
  }

  ses.registerSTT('tarayici-sunucu', make(false));
  ses.registerSTT('tarayici-cihaz', make(true));
})(window.AT = window.AT || {});
