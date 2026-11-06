/* Ses katmanı. Oynatıcı yalnız bu arayüzü kullanır:
 *   engine.speak(text, { stepId, segment, onSentence }) -> Promise (bitince ya da durdurulunca çözülür)
 *       onSentence(cümle): o an okunan cümle; altyazı bununla eşlenir.
 *   engine.stop()
 *   engine.replay()   -> true: o anki cümlenin başına sardı; false: motor desteklemiyor
 *   engine.available  (bool)
 * İki motor var:
 *   WebSpeechEngine  : tarayıcının ücretsiz seslendirmesi (tr-TR).
 *   AudioFileEngine  : önceden üretilmiş ses dosyaları (örn. Piper). Dosyası
 *                      olmayan parçada Web Speech'e düşer. */
(function (AT) {
  'use strict';

  // Chrome uzun cümleleri ~15 sn sonra kesebiliyor; metni cümlelere bölüyoruz.
  function sentences(text) {
    const out = [];
    const re = /[^.!?…;:]+[.!?…;:]*\s*/g;
    let m;
    while ((m = re.exec(text))) {
      const s = m[0].trim();
      if (s) out.push(s);
    }
    return out.length ? out : [text];
  }

  class WebSpeechEngine {
    constructor(lang) {
      this.lang = lang || 'tr-TR';
      this.rate = 1;
      this.voice = null;
      this.voices = [];
      this.available = 'speechSynthesis' in window;
      this._token = 0;
      if (this.available) {
        this._loadVoices();
        speechSynthesis.addEventListener?.('voiceschanged', () => this._loadVoices());
      }
    }

    _loadVoices() {
      const prefix = this.lang.slice(0, 2).toLowerCase();
      this.voices = speechSynthesis.getVoices().filter((v) => v.lang.toLowerCase().replace('_', '-').startsWith(prefix));
      const saved = AT.prefs.get('voice');
      // Eğitmenler (İnci, Mercan) kadın: kayıtlı seçim yoksa bilinen kadın Türkçe sesleri öne alınır.
      const KADIN = /emel|seda|filiz|yelda|aylin|ipek|female|kad[ıi]n/i;
      this.voice = this.voices.find((v) => v.voiceURI === saved)
        || this.voices.find((v) => KADIN.test(v.name))
        || this.voices.find((v) => v.lang.toLowerCase().replace('_', '-') === this.lang.toLowerCase())
        || this.voices[0] || null;
      AT.emit('voices', this.voices);
    }

    get hasLanguageVoice() { return !!this.voice; }

    setRate(r) { this.rate = r; }

    setVoice(uri) {
      this.voice = this.voices.find((v) => v.voiceURI === uri) || this.voice;
      AT.prefs.set('voice', uri);
    }

    async speak(text, info) {
      const onSentence = (info && info.onSentence) || (() => {});
      if (!this.available || !text) { onSentence(text); return estimateWait(text, this.rate, () => this._token); }
      const token = ++this._token;
      for (const s of sentences(text)) {
        if (token !== this._token) return;
        onSentence(s);
        await this._utter(s, token);
      }
    }

    replay() { return false; }

    _utter(text, token) {
      return new Promise((resolve) => {
        const u = new SpeechSynthesisUtterance(text);
        u.lang = this.lang;
        if (this.voice) u.voice = this.voice;
        u.rate = this.rate;
        let done = false;
        const finish = () => { if (!done) { done = true; clearInterval(keepAlive); resolve(); } };
        u.onend = finish;
        u.onerror = finish;
        // Bazı tarayıcılar onend'i hiç tetiklemiyor; tahmini süre sonunda yine de devam et.
        const guard = setTimeout(finish, (text.length * 110) / this.rate + 4000);
        u.addEventListener('end', () => clearTimeout(guard));
        const keepAlive = setInterval(() => {
          if (token !== this._token) { finish(); return; }
          if (!speechSynthesis.speaking) finish();
        }, 500);
        speechSynthesis.speak(u);
      });
    }

    stop() {
      this._token++;
      if (this.available) speechSynthesis.cancel();
    }
  }

  // Seslendirme yoksa altyazıyı okuyacak kadar bekle.
  function estimateWait(text, rate, tokenFn) {
    const start = tokenFn();
    const ms = Math.max(1500, (String(text || '').length * 65) / (rate || 1));
    return new Promise((resolve) => {
      const t0 = Date.now();
      const iv = setInterval(() => {
        if (tokenFn() !== start || Date.now() - t0 >= ms) { clearInterval(iv); resolve(); }
      }, 100);
    });
  }

  class SilentEngine {
    constructor() { this.rate = 1; this._token = 0; this.available = true; }
    setRate(r) { this.rate = r; }
    speak(text, info) {
      if (info && info.onSentence) info.onSentence(text);
      const t = ++this._token;
      return estimateWait(text, this.rate, () => (this._token === t ? t : -1));
    }
    replay() { return false; }
    stop() { this._token++; }
  }

  // Önceden üretilmiş ses (tools/ses-uret.py). Manifest biçimi:
  //   { "format": "mp3", "rate": 1.2, "steps": { "<stepId>": [parça, ...] } }
  // Her parça, 'say' metnindeki {n} işaretleriyle bölünen bir parçaya karşılık gelir:
  //   { "src": "audio/x.mp3", "dur": 12.3, "sentences": [{ "t": 0, "text": "..." }, ...] }
  // Eski biçimde parça yalnız dosya yoludur ("audio/x.mp3"); o zaman altyazı parça boyu gösterilir.
  class AudioFileEngine {
    constructor(lesson, manifest, fallback) {
      this.lesson = lesson;
      this.manifest = manifest;
      this.fallback = fallback;
      this.audio = new Audio();
      this.audio.preload = 'auto';
      this.rate = 1;
      this.available = true;
      this._token = 0;
    }

    setRate(r) { this.rate = r; this.audio.playbackRate = r; this.fallback.setRate(r); }

    speak(text, info) {
      const files = info && this.manifest.steps[info.stepId];
      let entry = files && files[info.segment];
      if (!entry) return this.fallback.speak(text, info);
      if (typeof entry === 'string') entry = { src: entry, sentences: [{ t: 0, text }] };
      const onSentence = info.onSentence || (() => {});
      const marks = entry.sentences && entry.sentences.length ? entry.sentences : [{ t: 0, text }];
      const token = ++this._token;
      this._marks = marks;
      return new Promise((resolve) => {
        const a = this.audio;
        let check, shown = -1;
        const sync = () => {
          let k = 0;
          while (k + 1 < marks.length && a.currentTime >= marks[k + 1].t - 0.05) k++;
          if (k !== shown) { shown = k; onSentence(marks[k].text); }
        };
        const done = () => { clearInterval(check); a.onended = a.onerror = a.ontimeupdate = null; this._marks = null; resolve(); };
        a.onended = done;
        a.onerror = () => { done(); };
        a.ontimeupdate = sync;
        a.src = AT.lessonUrl(this.lesson, entry.src);
        a.playbackRate = this.rate;
        sync();
        a.play().catch(done);
        check = setInterval(() => { if (token !== this._token) done(); else sync(); }, 200);
      });
    }

    // Geri sar: o anki cümlenin başına; cümlenin ilk saniyesindeyse bir önceki cümleye.
    replay() {
      const marks = this._marks;
      if (!marks || this.audio.paused) return false;
      const now = this.audio.currentTime;
      let k = 0;
      while (k + 1 < marks.length && now >= marks[k + 1].t) k++;
      if (now - marks[k].t < 1 && k > 0) k--;
      this.audio.currentTime = marks[k].t;
      return true;
    }

    stop() {
      this._token++;
      this.audio.pause();
      this.fallback.stop();
    }
  }

  AT.speech = { WebSpeechEngine, AudioFileEngine, SilentEngine, sentences };
})(window.AT = window.AT || {});
