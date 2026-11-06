/* Oynatıcı: adımları sırayla anlatır, tahta komutlarını işaretlere göre çalıştırır,
 * soru adımlarında öğrencinin cevabını bekler. */
(function (AT) {
  'use strict';

  class Player {
    constructor(lesson, ui) {
      this.lesson = lesson;
      this.ui = ui;
      this.progress = new AT.Progress(lesson.id);
      this._layout(this.progress.data.mode || 'learn');
      this.board = new AT.Board(ui.board, lesson);
      this.index = 0;
      this.playing = false;
      this._run = 0; // her goTo'da artar; eski anlatımlar kendini durdurur

      const web = new AT.speech.WebSpeechEngine(lesson.language || 'tr-TR');
      this.webSpeech = web;
      const silent = new AT.speech.SilentEngine();
      const base = AT.prefs.get('muted', false) || !web.available ? silent : web;
      this.engine = lesson._audioManifest
        ? new AT.speech.AudioFileEngine(lesson, lesson._audioManifest, base)
        : base;
      // Hazır seslerin önerilen hızı (ör. 1,2) öğrenci kendi hızını seçene kadar geçerlidir.
      this.setRate(AT.prefs.get('rate', (lesson._audioManifest && lesson._audioManifest.rate) || 1), false);
    }

    _layout(mode) {
      this.mode = mode;
      this.steps = AT.flatten(this.lesson, mode);
      this.questionSteps = this.steps.filter((s) => s.question);
      // Her bölümün son anlatım adımı: oraya ulaşılınca bölüm "dinlendi" sayılır.
      this.lastNarration = {};
      this.steps.forEach((s, i) => { if (!s.question) this.lastNarration[s._section] = i; });
    }

    // Öğrenme modu: 'learn' (önce anlatım) ya da 'answer' (önce ben yanıtlayayım).
    setMode(mode) {
      const id = this.step && this.step.id;
      this.progress.setMode(mode);
      this._layout(mode);
      const i = this.steps.findIndex((s) => s.id === id);
      this.goTo(i >= 0 ? i : 0, { play: false });
    }

    _markHeardIfEnd() {
      const st = this.step;
      if (!st.question && this.lastNarration[st._section] === this.index) {
        this.progress.markHeard(this.lesson.sections[st._section].id);
      }
    }

    // Soru, bölüm anlatımından önce mi sonra mı cevaplanıyor?
    phaseOf(step) {
      return this.progress.data.heard[this.lesson.sections[step._section].id] ? 'sonra' : 'once';
    }

    setMuted(m) {
      AT.prefs.set('muted', m);
      this.engine.stop();
      const base = m || !this.webSpeech.available ? new AT.speech.SilentEngine() : this.webSpeech;
      this.engine = this.lesson._audioManifest && !m
        ? new AT.speech.AudioFileEngine(this.lesson, this.lesson._audioManifest, base)
        : base;
      this.setRate(this.rate || 1);
      if (this.playing) this.goTo(this.index);
    }

    setRate(r, save = true) {
      this.rate = r;
      this.engine.setRate(r);
      if (save) AT.prefs.set('rate', r);
    }

    // Geri sar: hazır seste o anki cümlenin başına; başka motorlarda adımı baştan anlat.
    replay() {
      if (this.playing && this.engine.replay()) return;
      if (!this.playing) { this.play(); return; }
      this.goTo(this.index);
    }

    get step() { return this.steps[this.index]; }

    // Bölüm başından i'ye kadar tahtayı animasyonsuz yeniden kur.
    _rebuild(i) {
      this.board.clear();
      let start = i;
      while (start > 0 && this.steps[start]._section === this.steps[i]._section) start--;
      if (this.steps[start]._section !== this.steps[i]._section) start++;
      for (let j = start; j < i; j++) {
        for (const c of this.steps[j].board || []) this.board.run(c, true);
      }
    }

    goTo(i, opts = {}) {
      if (i < 0 || i >= this.steps.length) return;
      this._sessionHold = false;
      if (!opts.keepReview) { this.review = null; this._returnTo = null; }
      const run = ++this._run;
      this.engine.stop();
      this.index = i;
      this.progress.setLastStep(i);
      this._rebuild(i);
      this.ui.onStep(this);
      if (opts.play !== false && this.playing) this._play(run);
      else this._showStatic();
    }

    // Duraklatılmışken adımın tüm tahta komutlarını hemen göster.
    _showStatic() {
      for (const c of this.step.board || []) this.board.run(c, true);
      this.ui.caption(AT.plainSay(this.step.say));
      if (this.step.question) this.ui.showQuestion(this.step, this);
      else this._markHeardIfEnd();
    }

    async _play(run) {
      const step = this.step;
      const parts = AT.splitCues(step.say || (step.question && step.question.prompt));
      const cmds = step.board || [];
      const alive = () => run === this._run && this.playing;
      if (step.question) this.ui.showQuestion(step, this);

      for (let p = 0; p < parts.length; p++) {
        if (!alive()) return;
        const part = parts[p];
        for (const c of cmds) {
          if ((c.cue || 0) === part.cue) this.board.run(c, false);
        }
        this.ui.caption(part.text, AT.plainSay(step.say));
        if (part.text) {
          await this.engine.speak(part.text, {
            stepId: step.id, segment: p,
            onSentence: (s) => { if (alive()) this.ui.caption(s, AT.plainSay(step.say)); }
          });
        }
      }
      // İşaret numarası metinde geçmeyen komutlar da sonunda gösterilsin.
      const used = new Set(parts.map((x) => x.cue));
      for (const c of cmds) if (alive() && !used.has(c.cue || 0)) this.board.run(c, false);
      if (!alive()) return;

      if (step.question) return; // öğrenci "Devam"a basınca next() çağrılır
      this._markHeardIfEnd();
      await this._wait((step.pauseAfter != null ? step.pauseAfter : 0.6) * 1000, run);
      if (alive()) this.next();
    }

    _wait(ms, run) {
      return new Promise((resolve) => {
        const t0 = Date.now();
        const iv = setInterval(() => {
          if (run !== this._run || Date.now() - t0 >= ms) { clearInterval(iv); resolve(); }
        }, 50);
      });
    }

    play(keepReview) {
      if (this.playing) return;
      this.playing = true;
      this.ui.onPlayState(true);
      // Kaldığı adımı baştan anlat.
      this.goTo(this.index, { keepReview: !!keepReview || !!this.review || !!this._returnTo });
    }

    pause() {
      this.playing = false;
      this._run++;
      this.engine.stop();
      this.ui.onPlayState(false);
    }

    toggle() { this.playing ? this.pause() : this.play(); }

    next() {
      // Mola kartı açıkken "ileri", yeni dilimin ilk adımını atlamadan kartı kapatır.
      if (this._sessionHold) { this.goTo(this.index); return; }
      // Yanlış cevaptan sonra ilgili yer dinlendiyse soruya geri dön.
      if (this._returnTo) {
        const back = this.steps.findIndex((s) => s.id === this._returnTo);
        this._returnTo = null;
        if (back >= 0) { this.pause(); this.goTo(back, { keepReview: true }); return; }
      }
      if (this.review) { this.nextReview(); return; }
      const i = this.index + 1;
      if (i >= this.steps.length) { this.pause(); this.ui.showSummary(this); return; }
      // Çalışma dilimi (ör. G1 → G2) değişiyorsa anlatımı durdur ve mola öner.
      const a = AT.sessionOfSection(this.lesson, this.lesson.sections[this.step._section].id);
      const b = AT.sessionOfSection(this.lesson, this.lesson.sections[this.steps[i]._section].id);
      if (this.playing && a && b && a !== b) {
        this.pause();
        this.goTo(i);
        this._sessionHold = true;
        this.ui.onSessionEnd(a, b);
        return;
      }
      this.goTo(i);
    }

    prev() { this.goTo(Math.max(0, this.index - 1)); }

    // Soru cevaplandıktan sonra geri bildirimi seslendir.
    // Önceden üretilmiş seste anahtar '<adım>:dogru' / '<adım>:yanlis' olur.
    async speakFeedback(text, correct) {
      if (!this.playing || !text) return;
      await this.engine.speak(text, { stepId: this.step.id + (correct ? ':dogru' : ':yanlis'), segment: 0 });
    }

    sectionStart(si) { return this.steps.findIndex((s) => s._section === si); }

    // ---- Yanlış cevapta dönülecek yer ----
    // Sorunun 'review' alanı varsa o adım; yoksa aynı bölümdeki anlatım adımlarından kaynağı
    // (şekil > alt bölüm numarası > sayfa) soruyla en çok örtüşen, eşitlikte görselli olan seçilir.
    reviewTarget(step) {
      const q = step.question;
      if (q.review) {
        const i = this.steps.findIndex((s) => s.id === q.review);
        if (i >= 0) return i;
      }
      const refs = (txt) => {
        const t = String(txt || '');
        return {
          fig: new Set([...t.matchAll(/Şekil\s*(\d+)/gi)].map((m) => m[1])),
          sec: new Set([...t.matchAll(/\b\d+(?:\.\d+)+\b/g)].map((m) => m[0])),
          page: new Set([...t.matchAll(/s\.\s*(\d+)(?:[–-](\d+))?/g)].flatMap((m) => {
            const a = Number(m[1]), b = Number(m[2] || m[1]);
            return Array.from({ length: Math.max(0, Math.min(b - a, 10)) + 1 }, (_, k) => String(a + k));
          }))
        };
      };
      const want = refs(q.sourceRef);
      const visual = (s) => (s.board || []).some((c) => ['image', 'highlight', 'zoom', 'table', 'flow', 'compare', 'draw'].includes(c.type));
      let best = -1, bestScore = 0;
      this.steps.forEach((s, i) => {
        if (s._section !== step._section || s.question) return;
        const have = refs(s.sourceRef);
        let score = 0;
        for (const f of want.fig) if (have.fig.has(f)) score += 6;
        for (const x of want.sec) for (const y of have.sec) if (x === y || y.startsWith(x + '.') || x.startsWith(y + '.')) { score += 3; break; }
        for (const p of want.page) if (have.page.has(p)) { score += 1; break; }
        if (score && visual(s)) score += 0.5;
        if (score > bestScore) { best = i; bestScore = score; }
      });
      return best >= 0 ? best : this.sectionStart(step._section);
    }

    // İlgili yeri dinlet, bitince soruya geri dön.
    listenFor(step) {
      const i = this.reviewTarget(step);
      const keep = this.review;
      this.goTo(i, { play: false, keepReview: true });
      this.review = keep;
      this._returnTo = step.id;
      if (!this.playing) this.play(true);
      else this.goTo(i, { keepReview: true });
    }

    // ---- Aralıklı tekrar ----
    dueQuestions() {
      const ids = new Set(this.progress.dueSteps());
      return this.questionSteps.filter((s) => ids.has(s.id)).map((s) => s.id);
    }

    startReview(ids) {
      if (!ids.length) return false;
      this.pause();
      const back = this.index;
      this.review = { queue: ids, i: 0, right: 0, back };
      this.goTo(this.steps.findIndex((s) => s.id === ids[0]), { play: false, keepReview: true });
      return true;
    }

    nextReview() {
      const r = this.review;
      r.i++;
      if (r.i >= r.queue.length) {
        this.review = null;
        this.pause();
        this.ui.onReviewEnd(r);
        this.goTo(r.back, { play: false });
        return;
      }
      this.pause();
      this.goTo(this.steps.findIndex((s) => s.id === r.queue[r.i]), { play: false, keepReview: true });
    }

    goalStatus(goalId) {
      return this.progress.goalStatus(goalId, this.questionSteps, AT.sectionsForGoal(this.lesson, goalId));
    }

    destroy() { this._run++; this.playing = false; this.engine.stop(); }
  }

  AT.Player = Player;
})(window.AT = window.AT || {});
