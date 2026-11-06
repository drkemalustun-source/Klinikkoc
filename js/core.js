/* Ortak yardımcılar: ayarlar, olaylar, ders yükleme, ilerleme kaydı. */
(function (AT) {
  'use strict';

  // ---- Olaylar ----
  const listeners = {};
  AT.on = (name, fn) => { (listeners[name] = listeners[name] || []).push(fn); };
  AT.emit = (name, data) => { (listeners[name] || []).forEach((fn) => fn(data)); };

  // ---- Kalıcı ayarlar (tarayıcıda, cihaz başına) ----
  function store(key, val) {
    try {
      if (val === undefined) return JSON.parse(localStorage.getItem(key));
      localStorage.setItem(key, JSON.stringify(val));
    } catch (e) { return undefined; }
  }
  AT.prefs = {
    get: (k, d) => { const v = store('at:pref:' + k); return v == null ? d : v; },
    set: (k, v) => store('at:pref:' + k, v)
  };

  // ---- Ders yükleme ----
  // http(s) üzerinden JSON okunur. Dosya doğrudan açıldıysa (file://) tarayıcı
  // fetch'e izin vermez; o zaman tools/paketle.mjs'in ürettiği .js kopyaları yüklenir.
  const registry = { catalog: null, lessons: {} };
  AT.registerCatalog = (c) => { registry.catalog = c; };
  AT.registerLesson = (l) => { registry.lessons[l.id] = l; };

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = src;
      s.onload = resolve;
      s.onerror = () => reject(new Error('Yüklenemedi: ' + src));
      document.head.appendChild(s);
    });
  }

  async function loadJson(jsonPath, jsPath, pick) {
    if (location.protocol !== 'file:') {
      try {
        const r = await fetch(jsonPath, { cache: 'no-cache' });
        if (r.ok) return await r.json();
      } catch (e) { /* çevrimdışı ve önbellekte yoksa .js'e düş */ }
    }
    await loadScript(jsPath);
    const v = pick();
    if (!v) throw new Error('İçerik bulunamadı: ' + jsPath);
    return v;
  }

  AT.loadCatalog = () => loadJson('lessons/katalog.json', 'lessons/katalog.js', () => registry.catalog);

  AT.loadLesson = async (entry) => {
    const base = entry.path.replace(/\/?$/, '/');
    const lesson = await loadJson(base + 'ders.json', base + 'ders.js', () => registry.lessons[entry.id]);
    lesson._base = base;
    if (lesson.audio && lesson.audio.manifest) {
      try {
        lesson._audioManifest = await loadJson(base + lesson.audio.manifest,
          base + lesson.audio.manifest.replace(/\.json$/, '.js'), () => registry.lessons[entry.id + ':audio']);
      } catch (e) { console.info('Ses manifesti yok, tarayıcı seslendirmesi kullanılacak.'); }
    }
    return lesson;
  };
  AT.registerAudioManifest = (lessonId, m) => { registry.lessons[lessonId + ':audio'] = m; };

  // Ders klasöründeki ek bir JSON dosyası (ör. kaynak dizini). file:// için .js kopyası
  // AT.registerLessonData(anahtar, veri) çağırır.
  AT.registerLessonData = (key, data) => { registry.lessons[key] = data; };
  AT.loadLessonFile = (lesson, rel, key) =>
    loadJson(lesson._base + rel, lesson._base + rel.replace(/\.json$/, '.js'), () => registry.lessons[key]);

  AT.lessonUrl = (lesson, rel) => (/^(https?:|data:|\/)/.test(rel) ? rel : lesson._base + rel);

  // ---- İlerleme (notlandırma yok; yalnız öğrencinin kendi cihazında) ----
  // Kanıtlar birbirini ezmez: "dinlendi", "anlatımdan önce doğru", "anlatımdan sonra doğru",
  // "yeni örnekte uygulandı" ayrı tutulur. Her deneme kaydedilir; ilk deneme ayrıca bilinir.
  const emptyProgress = () => ({ answers: {}, attempts: [], heard: {}, lastStep: 0, mode: null, srs: {} });

  // Aralıklı tekrar (Leitner kutuları). Yanlış cevap 1. kutuya döner ve 10 dk sonra tekrar
  // sorulabilir; her doğru cevap bir üst kutuya taşır: 1 gün, 3 gün, 1 hafta, 3 hafta sonra.
  const MIN = 60 * 1000, DAY = 24 * 60 * MIN;
  const SRS_WAIT = { 1: 10 * MIN, 2: DAY, 3: 3 * DAY, 4: 7 * DAY, 5: 21 * DAY };
  AT.SRS_WAIT = SRS_WAIT;
  class Progress {
    constructor(lessonId) {
      this.key = 'at:progress:' + lessonId;
      this.data = Object.assign(emptyProgress(), store(this.key) || {});
    }
    save() { store(this.key, this.data); }

    // info: { goal, correct, phase: 'once'|'sonra', hints, kind, chosen: [misconception ids], targets }
    record(stepId, info) {
      const a = Object.assign({ step: stepId, at: Date.now() }, info);
      const prev = this.data.answers[stepId];
      this.data.attempts.push(a);
      this.data.answers[stepId] = a;
      this._schedule(stepId, a, prev);
      this.save();
    }

    _schedule(stepId, a, prev) {
      const srs = this.data.srs || (this.data.srs = {});
      const cur = srs[stepId] || { box: 0 };
      let box;
      if (!a.correct) box = 1;
      // Yanlıştan hemen sonra "Tekrar dene" ile gelen doğru, hatırlama sayılmaz: 1. kutuda kalır.
      else if (prev && !prev.correct && a.at - prev.at < SRS_WAIT[1]) box = 1;
      else box = Math.min(5, Math.max(cur.box, 1) + 1);
      const wait = a.correct && box === 1 ? DAY : SRS_WAIT[box];
      srs[stepId] = { box, due: a.at + wait };
    }

    // Tekrar zamanı gelmiş soruların adım kimlikleri (en eskisi önce).
    dueSteps(now = Date.now()) {
      return Object.entries(this.data.srs || {})
        .filter(([, v]) => v.due <= now)
        .sort((x, y) => x[1].due - y[1].due)
        .map(([k]) => k);
    }
    markHeard(sectionId) {
      if (this.data.heard[sectionId]) return;
      this.data.heard[sectionId] = Date.now();
      this.save();
    }
    setLastStep(i) { this.data.lastStep = i; this.save(); }
    setMode(m) { this.data.mode = m; this.save(); }
    reset() { const mode = this.data.mode; this.data = emptyProgress(); this.data.mode = mode; this.save(); }

    // Alt hedef özeti. status: 'ok' (tüm soruların son cevabı doğru), 'review' (yanlış var),
    // 'partial' (bir kısmı cevaplandı), 'none' (yoklanmadı), 'noquestion'.
    goalStatus(goalId, questionSteps, sectionsForGoal) {
      const qs = questionSteps.filter((s) => s.question.goal === goalId);
      const ev = {
        heard: sectionsForGoal.some((id) => this.data.heard[id]),
        before: false, after: false, applied: false, hints: 0
      };
      let answered = 0, correct = 0;
      for (const s of qs) {
        const last = this.data.answers[s.id];
        if (last) { answered++; if (last.correct) correct++; }
      }
      for (const a of this.data.attempts) {
        if (a.goal !== goalId) continue;
        ev.hints += a.hints || 0;
        if (!a.correct) continue;
        if (a.kind === 'application') ev.applied = true;
        if (a.phase === 'once' && !a.hints) ev.before = true;
        if (a.phase === 'sonra') ev.after = true;
      }
      const status = !qs.length ? 'noquestion'
        : answered === 0 ? 'none'
        : correct === qs.length ? 'ok'
        : correct < answered ? 'review' : 'partial';
      return Object.assign(ev, { status, total: qs.length, correct, answered });
    }

    // Yanılgılar: bir çeldiriciyle açılır; yalnızca aynı yanılgıyı hedefleyen bir soru
    // daha sonra doğru cevaplanınca kapanır. Genel bir doğru cevap onu kapatmaz.
    misconceptions() {
      const state = {};
      for (const a of this.data.attempts) {
        for (const m of a.chosen || []) state[m] = { open: true, at: a.at };
        if (a.correct) for (const m of a.targets || []) if (state[m] && state[m].open) state[m] = { open: false, at: a.at };
      }
      return state;
    }
  }
  AT.Progress = Progress;

  // ---- Ders içi adımları düzleştir ----
  // mode 'answer' (önce ben yanıtlayayım): bölümün yoklama soruları (probe) anlatımdan önce gelir.
  // mode 'learn' (öğrenerek ilerleyelim): yoklama soruları bölüm anlatımının sonuna taşınır.
  AT.flatten = (lesson, mode) => {
    const steps = [];
    lesson.sections.forEach((sec, si) => {
      const probes = sec.steps.filter((st) => st.question && st.question.probe);
      const rest = sec.steps.filter((st) => !(st.question && st.question.probe));
      let ordered = sec.steps;
      if (probes.length) {
        if (mode === 'answer') ordered = [...probes, ...rest];
        else {
          // Bölüm sonundaki diğer sorulardan hemen önce koy (anlatım bittikten sonra).
          let k = rest.length;
          while (k > 0 && rest[k - 1].question) k--;
          ordered = [...rest.slice(0, k), ...probes, ...rest.slice(k)];
        }
      }
      ordered.forEach((st, k) => steps.push({ ...st, _section: si, _first: k === 0 }));
    });
    return steps;
  };

  // Bir alt hedefi işleyen bölüm kimlikleri.
  AT.sectionsForGoal = (lesson, goalId) => lesson.sections.filter((s) => (s.goals || []).includes(goalId)).map((s) => s.id);

  AT.sessionOfSection = (lesson, sectionId) => (lesson.sessions || []).find((g) => g.sections.includes(sectionId)) || null;

  // 'say' metnini {n} işaretlerinden parçalara ayırır: [{cue:0,text}, {cue:1,text}, ...]
  AT.splitCues = (say) => {
    const parts = [];
    const re = /\{(\d+)\}/g;
    let last = 0, cue = 0, m;
    const text = say || '';
    while ((m = re.exec(text))) {
      parts.push({ cue, text: text.slice(last, m.index).trim() });
      cue = Number(m[1]);
      last = re.lastIndex;
    }
    parts.push({ cue, text: text.slice(last).trim() });
    return parts.filter((p, i) => p.text || p.cue || i === 0);
  };

  // Soru sonrası seslendirilen metin; tools/ses-uret.py de aynısını kullanır.
  AT.feedbackText = (q, correct) => (correct ? 'Doğru. ' : 'Tam değil. ') + (q.explanation || '');

  AT.plainSay = (say) => (say || '').replace(/\{\d+\}/g, '').replace(/\s+/g, ' ').trim();
})(window.AT = window.AT || {});
