/* Seslendirme adaptörü: Piper (açık kaynak sinir ağı sesi), tarayıcıda WebAssembly ile.
 * Türkçe sesler: tr_TR-ilkiz-medium (kadın, varsayılan; ilkeraktuna/piper-tts-tr-ilkiz-medium, MIT),
 * tr_TR-dfki-medium, tr_TR-fahrettin-medium, tr_TR-fettah-medium (rhasspy/piper-voices, MIT).
 * İlkiz yüklenemezse dfki'ye dönülür.
 * İlk kullanımda ses modeli (her biri ~60 MB) Hugging Face'ten indirilir ve tarayıcının
 * kalıcı deposunda (OPFS) saklanır; sonra internetsiz çalışır. Metin cihazdan çıkmaz.
 * Hazır derslerde aynı sesler tools/ses-uret.py ile önceden dosyaya da üretilebilir. */
(function (AT) {
  'use strict';
  const ses = AT.ses;

  const VOICES = [
    { id: 'tr_TR-ilkiz-medium', label: 'Piper · İlkiz (kadın)' },
    { id: 'tr_TR-dfki-medium', label: 'Piper · dfki (erkek)' },
    { id: 'tr_TR-fahrettin-medium', label: 'Piper · fahrettin (erkek)' },
    { id: 'tr_TR-fettah-medium', label: 'Piper · fettah (erkek)' }
  ];

  const YEDEK = 'tr_TR-dfki-medium';
  // İlkiz kitaplığın ses listesinde yok; yolu ekliyoruz. Kitaplık yolu diffusionstudio/piper-voices/resolve/main
  // köküne ekler, "../" ile aynı sitedeki ilkeraktuna deposuna çıkılır (önbellekte dosya adı: ilkiz.onnx).
  const EK_YOLLAR = {
    'tr_TR-ilkiz-medium': '../../../../ilkeraktuna/piper-tts-tr-ilkiz-medium/resolve/main/ilkiz.onnx'
  };

  let libPromise = null;
  const lib = () => (libPromise = libPromise || import(ses.ROOT + 'vendor/piper-tts-web.js').then((m) => {
    if (m.PATH_MAP) Object.assign(m.PATH_MAP, EK_YOLLAR);
    return m;
  }));
  const sessions = new Map();

  async function session(voiceId, onProgress) {
    if (sessions.has(voiceId)) return sessions.get(voiceId);
    const piper = await lib();
    // Kütüphane tek bir oturumu yeniden kullanıyor ve sesi değiştirince modeli yenilemiyor;
    // her ses için ayrı oturum açmak üzere önceki örneği bırakıyoruz.
    piper.TtsSession._instance = null;
    const meter = ses.progressMeter(onProgress);
    const p = piper.TtsSession.create({
      voiceId,
      progress: (pr) => { if (pr.url && !pr.url.startsWith('tts://')) meter.update(pr.url, pr.loaded, pr.total); }
    }).then((s) => ({ s, bytes: meter.bytes }));
    sessions.set(voiceId, p);
    p.catch(() => sessions.delete(voiceId));
    if (voiceId === YEDEK) return p;
    // Varsayılan ses (İlkiz) inmezse erkek dfki sesiyle devam edilir.
    return p.catch(() => session(YEDEK, onProgress));
  }

  ses.registerTTS('piper', () => {
    let audio = null;
    let token = 0;
    return {
      id: 'piper',
      label: 'Piper (tarayıcıda)',
      info: {
        offline: 'Evet (ilk indirmeden sonra)',
        dataLeavesDevice: 'Hayır',
        note: 'Ses başına ~60 MB, bir kez indirilir.'
      },
      voiceList: VOICES,
      status() {
        if (!('WebAssembly' in window)) return { ok: false, message: 'WebAssembly yok.' };
        if (!navigator.storage || !navigator.storage.getDirectory) return { ok: false, message: 'Tarayıcı kalıcı depo (OPFS) desteklemiyor; sayfayı http://localhost üzerinden açın.' };
        return { ok: true, message: 'Kullanılabilir.' };
      },
      async init(onProgress, opts) {
        const voice = (opts && opts.voice) || VOICES[0].id;
        const t0 = performance.now();
        const { bytes } = await session(voice, onProgress);
        return { loadMs: performance.now() - t0, bytes };
      },
      voices() { return VOICES.map((v) => ({ id: v.id, label: v.label, local: true })); },
      // Ses dosyası üretir (WAV Blob). Önceden ses üretmek için de kullanılabilir.
      async synthesize(text, opts) {
        const { s } = await session((opts && opts.voice) || VOICES[0].id);
        return s.predict(ses.pronounce(text));
      },
      async speak(text, opts) {
        opts = opts || {};
        const my = ++token;
        this.stop(true);
        const t0 = performance.now();
        const blob = await this.synthesize(text, opts);
        if (my !== token) return { firstAudioMs: null, durationMs: 0, cancelled: true };
        const synthMs = performance.now() - t0;
        const url = URL.createObjectURL(blob);
        audio = new Audio(url);
        audio.playbackRate = opts.rate || 1;
        return new Promise((resolve) => {
          let first = null;
          audio.onplaying = () => { if (first == null) first = performance.now() - t0; };
          const done = () => { URL.revokeObjectURL(url); resolve({ firstAudioMs: first, synthMs, durationMs: performance.now() - t0, cancelled: my !== token }); };
          audio.onended = done;
          audio.onerror = done;
          audio.onpause = () => { if (my !== token) done(); };
          audio.play().catch(done);
        });
      },
      stop(keepToken) {
        if (!keepToken) token++;
        if (audio) { audio.pause(); audio = null; }
      }
    };
  });
})(window.AT = window.AT || {});
