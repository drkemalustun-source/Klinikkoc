/* Ses katmanı: konuşma tanıma (STT) ve seslendirme (TTS) için ortak arayüz.
 *
 * Uygulamanın geri kalanı motorları tanımaz; yalnızca bu iki arayüzü kullanır.
 * Her motor ayrı bir dosyada bir "adaptör"dür ve kendini burada kaydeder.
 * Yeni bir motor (ör. sunucudaki bir model) eklemek için yeni bir adaptör dosyası yeterlidir.
 *
 * TextToSpeech (seslendirme)
 *   id, label                    kimlik ve görünen ad
 *   info                         { offline, dataLeavesDevice, note }
 *   init(onProgress) -> { loadMs, bytes }       gerekiyorsa modeli indirir/hazırlar
 *   voices() -> [{ id, label }]
 *   speak(text, { voice, rate }) -> { firstAudioMs, durationMs }   bitince çözülür
 *   stop()
 *
 * SpeechToText (konuşma tanıma)
 *   id, label, info              { offline, dataLeavesDevice, note }
 *   init(onProgress) -> { loadMs, bytes }
 *   status() -> { ok, message }  bu tarayıcıda/cihazda kullanılabilir mi
 *   transcribe(audio16k, { lang }) -> { text, ms }
 *       audio16k: 16 kHz tek kanal Float32Array. Tüm motorlar aynı kaydı alır;
 *       böylece karşılaştırma aynı koşullarda yapılır.
 *
 * Telaffuz sözlüğü: metin TTS'ye gitmeden önce AT.ses.pronounce() ile düzeltilir.
 */
(function (AT) {
  'use strict';

  const tts = new Map();
  const stt = new Map();

  // Bu dosyanın klasöründen proje köküne giden yol (vendor/ ve ses/ dosyaları için).
  const here = document.currentScript ? document.currentScript.src : location.href;
  const ROOT = new URL('../../', here).href;

  const ses = {
    ROOT,
    SAMPLE_RATE: 16000,

    registerTTS(id, factory) { tts.set(id, factory); },
    registerSTT(id, factory) { stt.set(id, factory); },
    ttsIds() { return [...tts.keys()]; },
    sttIds() { return [...stt.keys()]; },
    createTTS(id, opts) { const f = tts.get(id); if (!f) throw new Error('Bilinmeyen seslendirme motoru: ' + id); return f(opts || {}); },
    createSTT(id, opts) { const f = stt.get(id); if (!f) throw new Error('Bilinmeyen konuşma tanıma motoru: ' + id); return f(opts || {}); },

    // ---------- Telaffuz sözlüğü ----------
    // Biçim: { "entries": [ { "yazim": "implantoplasti", "okunus": "implanto plasti" }, ... ] }
    // Büyük-küçük harf duyarsız. Kayıt sözcüğün başında aranır ve sözcüğün geri kalanı (ek) korunur:
    // "implantoplastinin" -> "implanto plastinin". Yalnız tam sözcük eşleşsin istenirse "tam": true eklenir
    // (ör. "PD" kısaltması "PDL" içinde değişmesin).
    dictionary: [],
    setDictionary(entries) {
      ses.dictionary = (entries || [])
        .filter((e) => e && e.yazim && e.okunus != null)
        .sort((a, b) => b.yazim.length - a.yazim.length);
    },
    pronounce(text) {
      if (!text || !ses.dictionary.length) return text;
      for (const e of ses.dictionary) text = replaceTr(text, e.yazim, e.okunus, !!e.tam);
      return text;
    },
    async loadDictionary(url) {
      const local = readLocalDictionary();
      if (local) { ses.setDictionary(local); return { source: 'local', entries: local }; }
      try {
        const res = await fetch(url || ROOT + 'ses/telaffuz.json', { cache: 'no-cache' });
        const data = await res.json();
        ses.setDictionary(data.entries);
        return { source: 'file', entries: data.entries };
      } catch (e) {
        ses.setDictionary([]);
        return { source: 'none', entries: [] };
      }
    },
    saveLocalDictionary(entries) {
      try { localStorage.setItem('at:telaffuz', JSON.stringify(entries)); } catch (e) { /* özel pencere */ }
      ses.setDictionary(entries);
    },
    clearLocalDictionary() { try { localStorage.removeItem('at:telaffuz'); } catch (e) { /* yok */ } },

    // ---------- Ses yardımcıları ----------
    // Herhangi bir örnekleme hızındaki sesi 16 kHz'e indirir (doğrusal ara değerleme; konuşma için yeterli).
    resample(input, fromRate, toRate) {
      toRate = toRate || ses.SAMPLE_RATE;
      if (fromRate === toRate) return input;
      const ratio = fromRate / toRate;
      const n = Math.floor(input.length / ratio);
      const out = new Float32Array(n);
      // İndirmeden önce kaba alçak geçiren süzgeç: pencere içi ortalama.
      for (let i = 0; i < n; i++) {
        const start = i * ratio, end = Math.min(input.length, start + ratio);
        let s = 0, c = 0;
        for (let j = Math.floor(start); j < end; j++) { s += input[j]; c++; }
        out[i] = c ? s / c : 0;
      }
      return out;
    },

    // Basit enerji tabanlı ses etkinliği algılama. Konuşma olan bölgeyi döndürür; konuşma yoksa null.
    // Sessiz kayıtta modelin uydurma metin üretmesini (halüsinasyon) önlemek için kullanılır.
    detectSpeech(audio, rate, opts) {
      rate = rate || ses.SAMPLE_RATE;
      opts = opts || {};
      const frame = Math.round(rate * 0.03);
      const energies = [];
      for (let i = 0; i + frame <= audio.length; i += frame) {
        let s = 0;
        for (let j = i; j < i + frame; j++) s += audio[j] * audio[j];
        energies.push(Math.sqrt(s / frame));
      }
      if (!energies.length) return null;
      const sorted = [...energies].sort((a, b) => a - b);
      const floor = sorted[Math.floor(sorted.length * 0.1)] || 0;
      const threshold = Math.max(opts.minRms || 0.008, floor * 3);
      let first = -1, last = -1, voiced = 0;
      energies.forEach((e, i) => { if (e > threshold) { voiced++; if (first < 0) first = i; last = i; } });
      const minFrames = Math.ceil((opts.minSpeechMs || 250) / 30);
      if (voiced < minFrames) return null;
      const pad = Math.round((opts.padMs || 200) / 30);
      const a = Math.max(0, first - pad) * frame;
      const b = Math.min(audio.length, (last + 1 + pad) * frame);
      return { start: a, end: b, audio: audio.subarray(a, b), threshold, floor };
    },

    // Float32 PCM -> 16 bit WAV (Blob). Kayıtları indirmek ve dinlemek için.
    toWav(audio, rate) {
      rate = rate || ses.SAMPLE_RATE;
      const buf = new ArrayBuffer(44 + audio.length * 2);
      const v = new DataView(buf);
      const w = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
      w(0, 'RIFF'); v.setUint32(4, 36 + audio.length * 2, true); w(8, 'WAVE'); w(12, 'fmt ');
      v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
      v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
      w(36, 'data'); v.setUint32(40, audio.length * 2, true);
      for (let i = 0; i < audio.length; i++) {
        const s = Math.max(-1, Math.min(1, audio[i]));
        v.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
      }
      return new Blob([buf], { type: 'audio/wav' });
    },

    // Whisper'ın sessizlikte ve parça sonlarında ürettiği bilinen uydurma kalıpları ve tekrar döngülerini temizler.
    cleanTranscript(text) {
      if (!text) return '';
      let t = text.replace(/\s+/g, ' ').trim();
      for (const re of HALLUCINATIONS) t = t.replace(re, ' ');
      t = collapseRepeats(t);
      return t.replace(/\s+/g, ' ').trim();
    },

    // ---------- Ölçüm ----------
    // Türkçe kurallarla küçük harfe çevirir, noktalama, kesme ve tireyi atar.
    // "Peri-implantitis'in" ve "periimplantitisin" aynı sayılır; "yüzde" ile "%" farkını önlemek için
    // test cümlelerinde sayılar yazıyla yazılır.
    normalize(text) {
      return (text || '')
        .toLocaleLowerCase('tr-TR')
        .normalize('NFC')
        .replace(/[âà]/g, 'a').replace(/[îì]/g, 'i').replace(/[ûù]/g, 'u')
        .replace(/['’‘`´-]/g, '')
        .replace(/[^\p{L}\p{N}\s]/gu, ' ')
        .replace(/\s+/g, ' ')
        .trim();
    },
    // Kelime hata oranı: (yerine koyma + silme + ekleme) / referans kelime sayısı.
    wer(reference, hypothesis) {
      const r = ses.normalize(reference).split(' ').filter(Boolean);
      const h = ses.normalize(hypothesis).split(' ').filter(Boolean);
      const e = editDistance(r, h);
      return { errors: e, words: r.length, rate: r.length ? e / r.length : 0 };
    },
    // Karakter hata oranı (boşluksuz). Ek ve yazım farklarını kelime oranından daha yumuşak ölçer.
    cer(reference, hypothesis) {
      const r = [...ses.normalize(reference).replace(/ /g, '')];
      const h = [...ses.normalize(hypothesis).replace(/ /g, '')];
      const e = editDistance(r, h);
      return { errors: e, chars: r.length, rate: r.length ? e / r.length : 0 };
    },
    // Terimin tanınıp tanınmadığı: normalize edilmiş terim, normalize edilmiş çıktının içinde geçiyor mu
    // (ek almış biçimler de sayılır: "debridmanı" içinde "debridman").
    termHit(term, hypothesis) {
      const t = ses.normalize(term).replace(/ /g, '');
      const h = ses.normalize(hypothesis).replace(/ /g, '');
      return !!t && h.includes(t);
    }
  };

  const HALLUCINATIONS = [
    /altyaz[ıi]\s*m\.?\s*k\.?/gi,
    /altyaz[ıi]lar?\b[^.]*\btaraf[ıi]ndan[^.]*\.?/gi,
    /[iİ]zledi[ğg]iniz [iİ][çc]in te[şs]ekk[üu]r ederim\.?/gi,
    /[iİ]zledi[ğg]iniz [iİ][çc]in te[şs]ekk[üu]rler\.?/gi,
    /abone olmay[ıi] unutmay[ıi]n\.?/gi,
    /bir sonraki videoda g[öo]r[üu][şs]mek [üu]zere\.?/gi,
    /\[(m[üu]zik|alk[ıi][şs]|sessizlik|music|applause|blank_audio)\]/gi,
    /♪+/g
  ];

  // Aynı 1–6 kelimelik öbek art arda 3 kez ve fazlası geçiyorsa bir kez bırakır.
  function collapseRepeats(text) {
    let words = text.split(' ');
    for (let n = 6; n >= 1; n--) {
      const out = [];
      let i = 0;
      while (i < words.length) {
        const chunk = words.slice(i, i + n).join(' ').toLocaleLowerCase('tr-TR');
        let k = 1;
        while (i + (k + 1) * n <= words.length && words.slice(i + k * n, i + (k + 1) * n).join(' ').toLocaleLowerCase('tr-TR') === chunk) k++;
        if (k >= 3) { out.push(...words.slice(i, i + n)); i += k * n; } else { out.push(words[i]); i++; }
      }
      words = out;
    }
    return words.join(' ');
  }

  function editDistance(a, b) {
    const m = a.length, n = b.length;
    let prev = new Array(n + 1), cur = new Array(n + 1);
    for (let j = 0; j <= n; j++) prev[j] = j;
    for (let i = 1; i <= m; i++) {
      cur[0] = i;
      for (let j = 1; j <= n; j++) {
        cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
      }
      [prev, cur] = [cur, prev];
    }
    return prev[n];
  }

  // Türkçe büyük-küçük harf duyarsız değiştirme. JavaScript'in /i bayrağı İ ile i'yi eşlemediği için
  // eşleşme Türkçe küçük harfe çevrilmiş kopyada aranır, değişiklik özgün metne aynı konumda uygulanır.
  function replaceTr(text, find, repl, whole) {
    const low = text.toLocaleLowerCase('tr-TR');
    const key = find.toLocaleLowerCase('tr-TR');
    if (!key || low.length !== text.length) return text;
    const isWord = (ch) => !!ch && /[\p{L}\p{N}]/u.test(ch);
    let out = '', i = 0, from = 0;
    while ((i = low.indexOf(key, from)) !== -1) {
      const before = low[i - 1], after = low[i + key.length];
      if (!isWord(before) && (!whole || !isWord(after))) {
        out += text.slice(from, i) + repl;
      } else {
        out += text.slice(from, i + key.length);
      }
      from = i + key.length;
    }
    return out + text.slice(from);
  }

  function readLocalDictionary() {
    try { const v = localStorage.getItem('at:telaffuz'); return v ? JSON.parse(v) : null; } catch (e) { return null; }
  }

  // Ağdan indirilen dosyaların toplam boyutunu ve süresini izleyen yardımcı (model boyutunu raporlamak için).
  ses.progressMeter = function (onProgress) {
    const files = new Map();
    return {
      update(name, loaded, total) {
        files.set(name, { loaded: loaded || 0, total: total || loaded || 0 });
        let l = 0, t = 0;
        for (const f of files.values()) { l += f.loaded; t += f.total; }
        if (onProgress) onProgress({ loaded: l, total: t, file: name });
      },
      get bytes() { let t = 0; for (const f of files.values()) t += Math.max(f.total, f.loaded); return t; }
    };
  };

  AT.ses = ses;
})(window.AT = window.AT || {});
