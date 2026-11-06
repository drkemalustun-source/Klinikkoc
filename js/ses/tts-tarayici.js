/* Seslendirme adaptörü: tarayıcının kendi Türkçe sesi (Web Speech API, speechSynthesis).
 * Ücretsiz, kurulum gerektirmez. Ses kalitesi işletim sistemine ve tarayıcıya göre değişir.
 * Not: Chrome'un "Google" adlı sesleri metni Google sunucularında seslendirir; işletim sisteminin
 * yerel sesleri (ör. Windows "Microsoft Tolga", macOS "Yelda") cihazda kalır. */
(function (AT) {
  'use strict';
  const ses = AT.ses;

  function sentences(text) {
    const out = [];
    const re = /[^.!?…;:]+[.!?…;:]*\s*/g;
    let m;
    while ((m = re.exec(text))) { const s = m[0].trim(); if (s) out.push(s); }
    return out.length ? out : [text];
  }

  function trVoices() {
    if (!('speechSynthesis' in window)) return [];
    return speechSynthesis.getVoices().filter((v) => v.lang.toLowerCase().replace('_', '-').startsWith('tr'));
  }

  function waitVoices(ms) {
    return new Promise((resolve) => {
      if (trVoices().length || !('speechSynthesis' in window)) return resolve();
      const t = setTimeout(resolve, ms);
      speechSynthesis.addEventListener('voiceschanged', () => { clearTimeout(t); resolve(); }, { once: true });
    });
  }

  ses.registerTTS('tarayici', () => {
    let token = 0;
    return {
      id: 'tarayici',
      label: 'Tarayıcının Türkçe sesi',
      info: {
        offline: 'Sese bağlı (işletim sistemi sesi: evet; "Google" sesleri: hayır)',
        dataLeavesDevice: 'Sese bağlı ("Google" sesleri metni Google\'a gönderir)',
        note: 'İndirme yok; kalite cihaza göre değişir.'
      },
      async init() {
        const t0 = performance.now();
        await waitVoices(2500);
        return { loadMs: performance.now() - t0, bytes: 0 };
      },
      status() {
        if (!('speechSynthesis' in window)) return { ok: false, message: 'Bu tarayıcıda seslendirme yok.' };
        return trVoices().length ? { ok: true, message: trVoices().length + ' Türkçe ses bulundu.' } : { ok: false, message: 'Türkçe ses bulunamadı.' };
      },
      voices() {
        return trVoices().map((v) => ({
          id: v.voiceURI,
          label: v.name + (v.localService ? ' (cihazda)' : ' (sunucuda)'),
          local: v.localService
        }));
      },
      speak(text, opts) {
        opts = opts || {};
        const my = ++token;
        speechSynthesis.cancel();
        const voice = trVoices().find((v) => v.voiceURI === opts.voice) || trVoices()[0] || null;
        const parts = sentences(ses.pronounce(text));
        const t0 = performance.now();
        let first = null;
        return new Promise((resolve) => {
          let i = 0;
          const next = () => {
            if (my !== token || i >= parts.length) {
              return resolve({ firstAudioMs: first, durationMs: performance.now() - t0, cancelled: my !== token });
            }
            const u = new SpeechSynthesisUtterance(parts[i++]);
            u.lang = 'tr-TR';
            if (voice) u.voice = voice;
            u.rate = opts.rate || 1;
            u.onstart = () => { if (first == null) first = performance.now() - t0; };
            u.onend = next;
            u.onerror = next;
            speechSynthesis.speak(u);
          };
          next();
        });
      },
      stop() { token++; if ('speechSynthesis' in window) speechSynthesis.cancel(); }
    };
  });
})(window.AT = window.AT || {});
