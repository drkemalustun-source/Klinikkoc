/* Sözlü sınav provası (çevrimdışı oynatıcı).
 * Dersin açık uçlu soruları ve vakaların açık uçlu adımları, öğrencinin zayıf hedeflerinden başlayarak sorulur.
 * Öğrenci cevabı sesli söyler (isterse not alır); düşünme süresi sayılır. Sonra örnek cevap ve rubrikle
 * kendini puanlar. Sonunda sınav tarzı geri bildirim: eksik kalan ölçütler ve daha iyi nasıl söyleneceği.
 * Her cevap, sorunun kendi kimliğiyle ilerleme kaydına "sozlu" türüyle işlenir (karne ve aralıklı tekrar). */
(function (AT) {
  'use strict';

  const SURE = 90; // sn: bir soruda sesli cevap için önerilen süre

  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  const goalBloom = (lesson, id) => {
    for (const g of lesson.goals || []) for (const s of g.subgoals || []) if (s.id === id) return s.bloom;
    return null;
  };

  // Soru havuzu: { id, prompt, goal, bloom, rubric[{criterion, points, required}], model, from }
  AT.sozluHavuzu = (lesson, progress) => {
    const out = [];
    for (const sec of lesson.sections) for (const st of sec.steps) {
      const q = st.question;
      if (q && q.type === 'open' && q.rubric) {
        out.push({ id: st.id, prompt: q.prompt, scenario: q.scenario, goal: q.goal, bloom: q.bloom || goalBloom(lesson, q.goal),
          rubric: q.rubric, model: q.modelAnswer, from: sec.title });
      }
    }
    for (const c of lesson._cases || []) for (const n of c.dugumler || []) {
      if (n.tur !== 'acik' || !n.rubrik) continue;
      out.push({ id: 'vaka:' + c.id + ':' + n.id, prompt: n.soru, scenario: c.basvuru && c.basvuru.sikayet ? 'Vaka: ' + c.baslik + '. “' + c.basvuru.sikayet + '”' : null,
        goal: n.hedef, bloom: n.bloom, rubric: n.rubrik.map((r) => ({ criterion: r.olcut, points: r.puan, required: !!r.zorunlu })),
        model: n.ornek_cevap, from: 'Vaka: ' + c.baslik, case: c.id, node: n.id });
    }
    // Zayıf hedefler önce, sonra hiç yoklanmayanlar, sonra üst Bloom düzeyi.
    const k = AT.karne(lesson, progress.data);
    const weak = new Set(k.weak), untested = new Set(k.untested);
    const rank = (x) => (weak.has(x.goal) ? 0 : untested.has(x.goal) ? 1 : 2);
    const bl = (x) => -(AT.BLOOM.indexOf(x.bloom));
    return out.sort((a, b) => rank(a) - rank(b) || bl(a) - bl(b));
  };

  class OralRun {
    // ctx: { player, qEl, boardEl, toast, onExit() }
    constructor(items, ctx) {
      this.items = items;
      this.ctx = ctx;
      this.p = ctx.player;
      this.i = 0;
      this.results = [];
    }

    start() {
      this.p.pause();
      this.ctx.boardEl.classList.add('has-question');
      const b = this.p.board;
      b.clear();
      b.run({ type: 'title', text: 'Sözlü sınav provası', subtitle: this.items.length + ' soru · not verilmez' }, true);
      b.run({ type: 'bullets', title: 'Nasıl?', items: ['Soruyu dinle ya da oku.', 'Cevabı **sesli** söyle; istersen not al.', 'Örnek cevapla karşılaştır, kendini puanla.', 'Sonunda sınav tarzı geri bildirim gelir.'] }, true);
      this.ask();
    }

    card(tag) {
      const q = this.ctx.qEl;
      q.replaceChildren();
      q.hidden = false;
      const c = el('div', 'q-card oral-card');
      const head = el('div', 'case-head');
      head.appendChild(el('div', 'q-tag', tag));
      const close = el('button', 'btn ghost small', 'Provayı bitir');
      close.addEventListener('click', () => (this.results.length ? this.finish() : this.exit()));
      head.appendChild(close);
      c.appendChild(head);
      q.appendChild(c);
      q.scrollTop = 0;
      return c;
    }

    speak(text) {
      try { if (this.p.engine && !AT.prefs.get('muted', false)) this.p.engine.speak(text, { stepId: 'sozlu:' + this.i, segment: 0 }); } catch (e) { /* ses yok */ }
    }

    stopTimer() { clearInterval(this._t); this._t = null; }

    ask() {
      const it = this.items[this.i];
      const c = this.card('Sözlü prova · ' + (this.i + 1) + '/' + this.items.length + ' · ' + (it.goal || '') + (it.bloom ? ' · ' + AT.BLOOM_AD[it.bloom] : ''));
      if (it.scenario) {
        const sc = el('div', 'q-scenario');
        sc.appendChild(el('p', null, it.scenario));
        c.appendChild(sc);
      }
      c.appendChild(el('h3', 'q-prompt', it.prompt));
      this.p.board.run({ type: 'text', style: 'key', text: '**' + (this.i + 1) + '.** ' + it.prompt }, false);
      const timer = el('div', 'oral-timer');
      const bar = el('div', 'oral-bar');
      const fill = el('div', 'oral-fill');
      bar.appendChild(fill);
      const left = el('span', 'oral-left', SURE + ' sn');
      timer.append(bar, left);
      c.appendChild(timer);
      const note = el('textarea', 'q-text-answer');
      note.rows = 3;
      note.placeholder = 'İstersen anahtar sözcükleri not al. Asıl cevabı sesli söyle.';
      c.appendChild(note);
      const fb = el('div', 'q-feedback');
      fb.hidden = true;
      c.appendChild(fb);
      const acts = el('div', 'q-actions');
      c.appendChild(acts);
      const t0 = Date.now();
      this.stopTimer();
      this._t = setInterval(() => {
        const s = Math.round((Date.now() - t0) / 1000);
        fill.style.width = Math.min(100, (100 * s) / SURE) + '%';
        left.textContent = s < SURE ? (SURE - s) + ' sn' : 'Süre doldu; toparla.';
        timer.classList.toggle('over', s >= SURE);
      }, 500);
      this.speak(it.prompt);
      const done = el('button', 'btn primary', 'Cevabımı söyledim');
      const skip = el('button', 'btn ghost', 'Bilmiyorum, geç');
      acts.append(skip, done);
      const boxes = [];
      const reveal = (skipped) => {
        this.stopTimer();
        const secs = Math.round((Date.now() - t0) / 1000);
        this.p.engine && this.p.engine.stop && this.p.engine.stop();
        note.readOnly = true;
        done.hidden = true;
        skip.hidden = true;
        fb.hidden = false;
        fb.append(el('p', 'q-model-h', 'Sınavda beklenen cevap'), el('p', 'q-model', it.model || ''));
        fb.appendChild(el('p', 'q-model-h', skipped ? 'Bunlar beklenirdi' : 'Söylediklerinde bunlar var mıydı? Olanları işaretle.'));
        const list = el('div', 'q-rubric');
        for (const r of it.rubric) {
          const row = el('label', 'q-rubric-row');
          const cb = el('input');
          cb.type = 'checkbox';
          cb.disabled = skipped;
          boxes.push(cb);
          row.append(cb, el('span', null, r.criterion + (r.required ? ' (olmazsa olmaz)' : '')), el('span', 'q-pts', r.points + ' puan'));
          list.appendChild(row);
        }
        fb.appendChild(list);
        const save = el('button', 'btn primary', skipped ? 'Sonraki soru' : 'Puanla ve devam');
        save.addEventListener('click', () => this.score(it, boxes, secs, skipped));
        acts.appendChild(save);
        save.focus();
      };
      done.addEventListener('click', () => reveal(false));
      skip.addEventListener('click', () => reveal(true));
    }

    score(it, boxes, secs, skipped) {
      const max = it.rubric.reduce((a, r) => a + r.points, 0) || 1;
      const got = it.rubric.reduce((a, r, i) => a + (boxes[i].checked ? r.points : 0), 0);
      const missed = it.rubric.filter((r, i) => !boxes[i].checked);
      const reqOk = it.rubric.every((r, i) => !r.required || boxes[i].checked);
      const ok = !skipped && reqOk && got / max >= 0.6;
      this.p.progress.record(it.id, {
        goal: it.goal, correct: ok, phase: 'sonra', hints: 0, kind: 'check', chosen: [], targets: [],
        bloom: it.bloom, type: 'sozlu', score: got, max, missed: missed.map((r) => r.criterion), seconds: secs,
        case: it.case, node: it.node
      });
      this.results.push({ it, got, max, ok, missed, secs, skipped, reqOk });
      this.i++;
      if (this.i < this.items.length) this.ask(); else this.finish();
    }

    finish() {
      this.stopTimer();
      const c = this.card('Sözlü prova · geri bildirim');
      const R = this.results;
      const tot = R.reduce((a, r) => a + r.got, 0), mx = R.reduce((a, r) => a + r.max, 0) || 1;
      const ok = R.filter((r) => r.ok).length;
      c.appendChild(el('h3', 'q-prompt', R.length + ' sorudan ' + ok + ' tanesinde cevabın yeterliydi (' + Math.round(100 * tot / mx) + '/100).'));
      const fb = el('div', 'q-feedback');
      for (const r of R) {
        const box = el('div', 'oral-item ' + (r.ok ? 'ok' : 'warn'));
        box.appendChild(el('p', 'oral-q', r.it.prompt));
        if (r.skipped) box.appendChild(el('p', null, 'Bu soruyu geçtin. Önce ilgili bölümü (' + r.it.from + ') yeniden dinle, sonra kendi cümlelerinle anlatmayı dene.'));
        else {
          const good = r.it.rubric.filter((x) => !r.missed.includes(x)).map((x) => x.criterion);
          if (good.length) box.appendChild(el('p', null, 'İyiydi: ' + good.join('; ') + '.'));
          if (r.missed.length) box.appendChild(el('p', null, 'Eksik kaldı: ' + r.missed.map((x) => x.criterion + (x.required ? ' (olmazsa olmaz)' : '')).join('; ') + '.'));
          if (!r.reqOk) box.appendChild(el('p', 'q-misc', 'Sınavda olmazsa olmaz bir öğeyi atlamak cevabı yetersiz kılar.'));
          if (r.secs > SURE) box.appendChild(el('p', 'q-src', 'Cevap ' + r.secs + ' sn sürdü; sınavda daha kısa ve düzenli anlatmaya çalış.'));
        }
        fb.appendChild(box);
      }
      fb.appendChild(el('p', 'q-model-h', 'Sınavda daha iyi anlatmak için'));
      const ul = el('ul');
      for (const t of ['Önce tanımla ya da tanıyı söyle, sonra dayandığın bulguları say.', 'Kararını gerekçesiyle bitir: "...olduğu için ... yaparım."',
        'Terimleri doğru ve tam kullan; emin olmadığın yerde bunu açıkça söyle.', 'Eksik kalan ölçütler aralıklı tekrarda yeniden sorulacak.']) ul.appendChild(el('li', null, t));
      fb.appendChild(ul);
      fb.appendChild(el('p', 'drawer-note', 'Puanı sen verdin; not değildir ve yalnız bu cihazda saklanır.'));
      c.appendChild(fb);
      const acts = el('div', 'q-actions');
      const end = el('button', 'btn primary', 'Bitir');
      end.addEventListener('click', () => this.exit());
      acts.appendChild(end);
      c.appendChild(acts);
    }

    exit() {
      this.stopTimer();
      const q = this.ctx.qEl;
      q.hidden = true;
      q.replaceChildren();
      this.ctx.boardEl.classList.remove('has-question');
      this.ctx.onExit(this);
    }
  }

  AT.OralRun = OralRun;
})(window.AT = window.AT || {});
