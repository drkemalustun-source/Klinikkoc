/* Vaka akışı (çevrimdışı oynatıcı): bir vaka kartını adım adım oynatır.
 * Öğrenci muayene ister (veri), karar verir (karar), kendi cümleleriyle cevaplar (acik), gidişatı dinler (bilgi).
 * Tahtada seçtiği yol bir karar ağacı olarak büyür; bulgular not alanına yazılır.
 * Her cevap ilerleme kaydına "vaka:<vaka>:<düğüm>" kimliğiyle işlenir; karne ve aralıklı tekrar bunu kullanır.
 * Kart biçimi: schema/vaka.schema.json, belgeler/vaka-karti.md. */
(function (AT) {
  'use strict';

  const SONUC_AD = { dogru: 'Doğru', kabul: 'Kabul edilebilir', yanlis: 'Yanlış', tehlikeli: 'Hastaya zarar verebilir' };
  const SON_AD = { iyi: 'Vaka iyi sonuçlandı', kabul: 'Vaka kabul edilebilir biçimde sonuçlandı', kotu: 'Vaka kötü sonuçlandı' };
  const BULGU_AD = { anamnez: 'Anamnez', klinik: 'Klinik', radyografik: 'Radyografi', laboratuvar: 'Laboratuvar', fotograf: 'Fotoğraf', diger: 'Diğer' };
  const PUAN = { dogru: 1, kabul: 0.5, yanlis: 0, tehlikeli: 0 };
  AT.VAKA_SONUC_AD = SONUC_AD;

  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  const stepId = (card, node) => 'vaka:' + card.id + ':' + node.id;

  // Vaka kaydı: progress.data.vakalar[vaka] = { son: [{at, sonuc, puan, en_yuksek, tehlikeli}] }
  function saveOutcome(progress, card, out) {
    const all = progress.data.vakalar || (progress.data.vakalar = {});
    const rec = all[card.id] || (all[card.id] = { son: [] });
    rec.son.push(out);
    progress.save();
  }
  AT.vakaSonuclari = (progress, id) => ((progress.data.vakalar || {})[id] || { son: [] }).son;

  class CaseRun {
    // ctx: { player, qEl, boardEl, toast, onExit(), onReteach(bolum, sayfa, not) }
    constructor(card, ctx) {
      this.card = card;
      this.ctx = ctx;
      this.p = ctx.player;
      this.nodes = new Map(card.dugumler.map((n) => [n.id, n]));
      this.findings = new Map(card.bulgular.map((b) => [b.id, b]));
      this.revealed = new Set();
      this.path = [];          // [{node, chosen?: index, result?}]
      this.score = 0;
      this.max = 0;
      this.danger = 0;
    }

    start() {
      this.p.pause();
      this.ctx.boardEl.classList.add('has-question', 'case-mode');
      this.boardBase();
      for (const f of this.card.bulgular) if (f.acilis === 'baslangic') this.reveal(f.id, true);
      this.go(this.card.baslangic);
    }

    boardBase() {
      const b = this.p.board;
      b.clear();
      b.run({ type: 'title', text: this.card.baslik, subtitle: (this.card.kurgusal ? 'Kurgusal vaka' : 'Gerçek hastadan, kimliksizleştirilmiş') + (this.card.sure_dk ? ' · ~' + this.card.sure_dk + ' dk' : '') }, true);
      const h = this.card.hasta || {};
      const who = [h.yas_araligi && h.yas_araligi + ' yaş', h.cinsiyet && h.cinsiyet !== 'belirtilmedi' ? h.cinsiyet : null].filter(Boolean).join(', ');
      const items = [];
      if (who) items.push('**Hasta:** ' + who);
      if (h.sistemik && h.sistemik.length) items.push('**Sistemik:** ' + h.sistemik.join('; '));
      if (h.aliskanliklar && h.aliskanliklar.length) items.push('**Alışkanlıklar:** ' + h.aliskanliklar.join('; '));
      if (items.length) b.run({ type: 'bullets', title: 'Hasta', items }, true);
    }

    // Yeniden anlatımdan dönüş: tahtayı kur, son düğümü yeniden aç (denenen seçenekler kapalı kalır).
    resume() {
      this.p.pause();
      this.ctx.boardEl.classList.add('has-question', 'case-mode');
      this.boardBase();
      const shown = [...this.revealed];
      this.revealed.clear();
      for (const id of shown) this.reveal(id, true);
      this._shownImg = null;
      this.drawTree();
      const n = this.path[this.path.length - 1].node;
      this['node_' + n.tur](n);
    }

    reveal(id, instant) {
      const f = this.findings.get(id);
      if (!f || this.revealed.has(id)) return;
      this.revealed.add(id);
      this.p.board.run({ type: 'text', style: 'note', text: '**' + f.baslik + ':** ' + f.metin }, !!instant);
    }

    drawTree() {
      const nodes = [];
      const path = [];
      let parent = null;
      this.path.forEach((step, i) => {
        const n = step.node;
        if (n.tur === 'son') return;
        const id = 'd' + i;
        nodes.push({ id, parent, edge: step.edge, text: n.baslik || n.soru || n.id, state: step.done ? 'accent' : '' });
        path.push(id);
        parent = id;
        if (n.tur === 'karar' && step.tried) {
          n.secenekler.forEach((o, k) => {
            if (!step.tried.has(k)) return;
            const oid = id + 'o' + k;
            const state = o.sonuc === 'dogru' ? 'ok' : o.sonuc === 'kabul' ? 'accent' : o.sonuc === 'tehlikeli' ? 'danger' : 'warn';
            nodes.push({ id: oid, parent: id, text: o.metin, state: k === step.chosen ? state : state + ' dim' });
            if (k === step.chosen) { path.push(oid); parent = oid; }
          });
        }
      });
      const last = this.path[this.path.length - 1];
      if (last && last.node.tur === 'son') {
        nodes.push({ id: 'son', parent, text: SON_AD[last.node.sonuc] || 'Son', state: last.node.sonuc === 'kotu' ? 'danger' : last.node.sonuc === 'iyi' ? 'ok' : 'accent' });
        path.push('son');
      }
      this.p.board.run({ type: 'tree', title: 'Karar yolun', nodes, path }, false);
    }

    go(id) {
      const n = this.nodes.get(id);
      if (!n) { this.ctx.toast('Vaka kartında "' + id + '" düğümü yok.'); this.exit(); return; }
      for (const f of n.acilan_bulgular || []) this.reveal(f);
      this.path.push({ node: n, edge: this._edge });
      this._edge = null;
      this.drawTree();
      this['node_' + n.tur](n);
    }

    // ---- Ortak kart ----
    card_(n, tagText) {
      const q = this.ctx.qEl;
      q.replaceChildren();
      q.hidden = false;
      const c = el('div', 'q-card case-card');
      const head = el('div', 'case-head');
      head.appendChild(el('div', 'q-tag', 'Vaka · ' + tagText + (n.hedef ? ' · ' + n.hedef : '') + (n.bloom ? ' · ' + AT.BLOOM_AD[n.bloom] : '')));
      const close = el('button', 'btn ghost small', 'Vakadan çık');
      close.addEventListener('click', () => this.exit());
      const peek = el('button', 'btn ghost small case-peek-btn', 'Tahtayı gör');
      peek.addEventListener('click', () => this.peek(true));
      head.append(peek, close);
      c.appendChild(head);
      if (this.path.length === 1 && this.card.basvuru) {
        const sc = el('div', 'q-scenario case-complaint');
        sc.appendChild(el('span', 'q-fiction', this.card.kurgusal ? 'KURGUSAL VAKA' : 'GERÇEK VAKA · KİMLİKSİZLEŞTİRİLMİŞ'));
        sc.appendChild(el('p', null, '“' + this.card.basvuru.sikayet + '”'));
        if (this.card.basvuru.oyku) sc.appendChild(el('p', null, this.card.basvuru.oyku));
        c.appendChild(sc);
      }
      for (const f of this.card.bulgular) if (this.revealed.has(f.id) && f.gorsel && !this._shownImg?.has(f.id)) {
        (this._shownImg || (this._shownImg = new Set())).add(f.id);
        c.appendChild(this.figure(f));
      }
      if (n.anlat) c.appendChild(el('p', 'case-narr', n.anlat));
      if (n.soru) c.appendChild(el('h3', 'q-prompt', n.soru));
      q.appendChild(c);
      q.scrollTop = 0;
      return c;
    }

    figure(f) {
      const fig = el('figure', 'case-fig');
      const img = el('img');
      img.src = AT.lessonUrl(this.p.lesson, f.gorsel);
      img.alt = f.gorsel_aciklama || f.baslik;
      img.loading = 'lazy';
      img.addEventListener('click', () => fig.classList.toggle('big'));
      fig.appendChild(img);
      fig.appendChild(el('figcaption', null, f.baslik + (f.gorsel_aciklama ? ': ' + f.gorsel_aciklama : '')));
      return fig;
    }

    hints(n, box) {
      const hs = n.ipuclari || [];
      const btn = el('button', 'btn ghost', 'İpucu');
      btn.hidden = !hs.length;
      const st = { used: 0, btn };
      st.next = () => {
        if (st.used >= hs.length) return false;
        box.appendChild(el('p', 'q-hint-item', hs[st.used]));
        st.used++;
        btn.hidden = st.used >= hs.length;
        return true;
      };
      btn.addEventListener('click', st.next);
      return st;
    }

    actions(c, ...btns) {
      const a = el('div', 'q-actions');
      a.append(...btns);
      c.appendChild(a);
      return a;
    }

    record(n, info) {
      const max = info.max || 1;
      this.score += info.score;
      this.max += max;
      if (info.danger) this.danger++;
      this.p.progress.record(stepId(this.card, n), Object.assign({
        goal: n.hedef, bloom: n.bloom, phase: 'sonra', kind: 'application', chosen: [], targets: [],
        case: this.card.id, node: n.id, max
      }, info));
    }

    nextBtn(label, fn) {
      const b = el('button', 'btn primary', label || 'Devam');
      b.addEventListener('click', fn);
      return b;
    }

    reteach(n, c) {
      const t = n.takilirsa;
      if (!t) return;
      const box = el('div', 'case-reteach');
      box.appendChild(el('p', null, 'Burada takıldın. İstersen ilgili ders bölümünü yeniden dinle, sonra vakaya dönersin.'));
      if (t.not) box.appendChild(el('p', 'q-src', t.not));
      if (t.bolum) {
        const b = el('button', 'btn', 'Bölümü yeniden dinle');
        b.addEventListener('click', () => this.ctx.onReteach(t, this));
        box.appendChild(b);
      } else if (t.sayfa) box.appendChild(el('p', 'q-src', 'Ders notu: sayfa ' + t.sayfa));
      c.appendChild(box);
    }

    // ---- Düğüm türleri ----
    node_bilgi(n) {
      const c = this.card_(n, n.baslik || 'Gidişat');
      this.path[this.path.length - 1].done = true;
      this.actions(c, this.nextBtn('Devam', () => this.go(n.sonraki)));
    }

    node_veri(n) {
      const c = this.card_(n, n.baslik || 'Muayene');
      const pool = this.card.bulgular.filter((f) => !this.revealed.has(f.id));
      const list = el('div', 'q-rubric case-exams');
      const boxes = [];
      for (const f of pool) {
        const row = el('label', 'q-rubric-row');
        const cb = el('input');
        cb.type = 'checkbox';
        cb.value = f.id;
        boxes.push(cb);
        row.append(cb, el('span', null, f.baslik), el('span', 'q-pts', BULGU_AD[f.tur] || ''));
        list.appendChild(row);
      }
      c.appendChild(list);
      const why = el('textarea', 'q-text-answer');
      why.rows = 2;
      why.placeholder = 'Neden istiyorsun? (isteğe bağlı, kendin için)';
      c.appendChild(why);
      const hintBox = el('div', 'q-hints');
      c.appendChild(hintBox);
      const fb = el('div', 'q-feedback');
      fb.hidden = true;
      c.appendChild(fb);
      const h = this.hints(n, hintBox);
      const ask = this.nextBtn('Muayeneleri iste', () => {
        const chosen = boxes.filter((b) => b.checked).map((b) => b.value);
        if (!chosen.length) { this.ctx.toast('En az bir muayene seç.'); return; }
        const need = n.gerekli_bulgular || [];
        const got = need.filter((x) => chosen.includes(x));
        const missing = need.filter((x) => !chosen.includes(x));
        const extra = chosen.filter((x) => !need.includes(x));
        boxes.forEach((b) => { b.disabled = true; });
        for (const id of chosen) this.reveal(id);
        const ok = !missing.length;
        c.classList.add('answered', ok ? 'is-correct' : 'is-wrong');
        fb.hidden = false;
        fb.appendChild(el('strong', null, ok ? 'Gerekli muayenelerin hepsini istedin.' : 'Bazı gerekli muayeneler eksik.'));
        if (missing.length) {
          fb.appendChild(el('p', null, 'Bunlara da bakmak gerekirdi: ' + missing.map((x) => this.findings.get(x)?.baslik || x).join(', ') + '. Bulguları tahtaya ekledim.'));
          for (const id of missing) this.reveal(id);
        }
        if (extra.length) fb.appendChild(el('p', 'q-src', 'Bu vakada karar için şart olmayan istekler: ' + extra.map((x) => this.findings.get(x)?.baslik || x).join(', ') + '.'));
        for (const id of chosen.concat(missing)) {
          const f = this.findings.get(id);
          if (f && f.gorsel) fb.appendChild(this.figure(f));
        }
        this.record(n, { type: 'vaka_veri', correct: ok, score: need.length ? got.length / need.length : 1, max: 1, hints: h.used, missed: missing.map((x) => this.findings.get(x)?.baslik || x) });
        this.path[this.path.length - 1].done = true;
        this.drawTree();
        ask.hidden = true;
        h.btn.hidden = true;
        this.actions(c, this.nextBtn('Devam', () => this.go(n.sonraki)));
      });
      this.actions(c, h.btn, ask);
    }

    node_karar(n) {
      const c = this.card_(n, n.baslik || 'Karar');
      const step = this.path[this.path.length - 1];
      step.tried = step.tried || new Set();
      let why = null;
      if (n.gerekce_iste) {
        why = el('textarea', 'q-text-answer');
        why.rows = 2;
        why.placeholder = 'Seçmeden önce kısaca neden? (kendin için)';
      }
      const opts = el('div', 'q-options');
      const buttons = n.secenekler.map((o, k) => {
        const b = el('button', 'q-opt');
        b.appendChild(el('span', 'q-letter', String.fromCharCode(65 + k)));
        b.appendChild(el('span', 'q-text', o.metin));
        b.addEventListener('click', () => choose(k));
        if (step.tried.has(k)) { b.disabled = true; b.classList.add('wrong'); }
        opts.appendChild(b);
        return b;
      });
      c.appendChild(opts);
      if (why) c.appendChild(why);
      const hintBox = el('div', 'q-hints');
      c.appendChild(hintBox);
      const fb = el('div', 'q-feedback');
      fb.hidden = true;
      c.appendChild(fb);
      const h = this.hints(n, hintBox);
      const acts = this.actions(c, h.btn);
      let wrong = 0;
      const choose = (k) => {
        const o = n.secenekler[k];
        const first = step.tried.size === 0;
        step.tried.add(k);
        const good = o.sonuc === 'dogru' || o.sonuc === 'kabul';
        buttons[k].classList.add(good ? 'right' : 'wrong');
        buttons[k].disabled = true;
        fb.hidden = false;
        const label = SONUC_AD[o.sonuc];
        const dup = o.geribildirim && o.geribildirim.toLocaleLowerCase('tr').startsWith(label.toLocaleLowerCase('tr'));
        fb.replaceChildren(el('strong', null, dup ? '' : label + '. '));
        if (o.sonuc === 'tehlikeli') fb.appendChild(el('p', 'q-misc', 'Bu seçim hastaya zarar verebilir. Karnende ayrıca gösterilir.'));
        if (o.geribildirim) fb.appendChild(el('p', null, o.geribildirim));
        c.classList.remove('is-correct', 'is-wrong');
        c.classList.add(good ? 'is-correct' : 'is-wrong');
        const misc = o.yanilgi ? [o.yanilgi] : [];
        const targets = n.secenekler.map((x) => x.yanilgi).filter(Boolean);
        this.record(n, {
          type: 'vaka_karar', correct: good, score: first ? PUAN[o.sonuc] : 0, max: 1, hints: h.used,
          chosen: misc, targets: good ? targets : [], danger: o.sonuc === 'tehlikeli', first, answer: o.metin
        });
        if (good || o.sonraki) {
          step.chosen = k;
          step.done = true;
          buttons.forEach((b) => { b.disabled = true; });
          h.btn.hidden = true;
          this._edge = null;
          this.drawTree();
          acts.appendChild(this.nextBtn('Devam', () => this.go(o.sonraki)));
          return;
        }
        // Yanlış ve dalı yok: aynı düğümde yeniden dene; bir ipucu aç; iki yanlıştan sonra yeniden anlatım öner.
        wrong++;
        this.drawTree();
        fb.appendChild(el('p', 'q-src', 'Yeniden dene.'));
        h.next();
        if (wrong === 2) this.reteach(n, c);
      };
    }

    node_acik(n) {
      const c = this.card_(n, n.baslik || 'Kendi cümlelerinle');
      const ta = el('textarea', 'q-text-answer');
      ta.rows = 4;
      ta.placeholder = 'Cevabını buraya yaz. İstersen aklından da cevaplayabilirsin.';
      c.appendChild(ta);
      const hintBox = el('div', 'q-hints');
      c.appendChild(hintBox);
      const fb = el('div', 'q-feedback');
      fb.hidden = true;
      c.appendChild(fb);
      const h = this.hints(n, hintBox);
      const rubric = n.rubrik || [];
      const boxes = [];
      const show = this.nextBtn('Örnek cevabı göster', () => {
        ta.readOnly = true;
        fb.hidden = false;
        fb.append(el('p', 'q-model-h', 'Öğretmenin örnek cevabı'), el('p', 'q-model', n.ornek_cevap || ''));
        fb.appendChild(el('p', 'q-model-h', 'Cevabında bunlar var mıydı? Olanları işaretle.'));
        const list = el('div', 'q-rubric');
        for (const r of rubric) {
          const row = el('label', 'q-rubric-row');
          const cb = el('input');
          cb.type = 'checkbox';
          boxes.push(cb);
          row.append(cb, el('span', null, r.olcut + (r.zorunlu ? ' (olmazsa olmaz)' : '')), el('span', 'q-pts', r.puan + ' puan'));
          list.appendChild(row);
        }
        fb.appendChild(list);
        show.hidden = true;
        h.btn.hidden = true;
        save.hidden = false;
      });
      const save = this.nextBtn('Puanımı kaydet', () => {
        const max = rubric.reduce((a, r) => a + r.puan, 0) || 1;
        const score = rubric.reduce((a, r, i) => a + (boxes[i].checked ? r.puan : 0), 0);
        const missed = rubric.filter((r, i) => !boxes[i].checked).map((r) => r.olcut);
        const reqOk = rubric.every((r, i) => !r.zorunlu || boxes[i].checked);
        const ok = reqOk && score / max >= 0.6;
        boxes.forEach((b) => { b.disabled = true; });
        c.classList.add('answered', ok ? 'is-correct' : 'is-wrong');
        fb.prepend(el('p', 'q-score', (ok ? 'Yeterli. ' : 'Henüz yeterli değil. ') + score + ' / ' + max + ' puan'));
        this.record(n, { type: 'vaka_acik', correct: ok, score: score / max, max: 1, hints: h.used, missed });
        if (!ok) this.reteach(n, c);
        this.path[this.path.length - 1].done = true;
        this.drawTree();
        save.hidden = true;
        this.actions(c, this.nextBtn('Devam', () => this.go(n.sonraki)));
      });
      save.hidden = true;
      this.actions(c, h.btn, show, save);
      ta.focus();
    }

    node_son(n) {
      const c = this.card_({ anlat: n.anlat }, SON_AD[n.sonuc] || 'Son');
      c.classList.add(n.sonuc === 'kotu' ? 'is-wrong' : 'is-correct', 'answered');
      const k = this.card.kapanis || {};
      const sum = el('div', 'q-feedback');
      sum.appendChild(el('strong', null, SON_AD[n.sonuc] || 'Vaka bitti'));
      sum.appendChild(el('p', 'q-score', 'Bu vakada ilk denemelerinle ' + Math.round(this.max ? 100 * this.score / this.max : 0) + '/100 aldın.'
        + (this.danger ? ' Hastaya zarar verebilecek seçim: ' + this.danger + '.' : '')));
      if (k.ozet) sum.append(el('p', 'q-model-h', 'Doğru akıl yürütme'), el('p', 'q-model', k.ozet));
      if (k.ogrenme_noktalari && k.ogrenme_noktalari.length) {
        sum.appendChild(el('p', 'q-model-h', 'Öğrenme noktaları'));
        const ul = el('ul');
        for (const x of k.ogrenme_noktalari) ul.appendChild(el('li', null, x));
        sum.appendChild(ul);
      }
      sum.appendChild(el('p', 'drawer-note', 'Puan not değildir; yalnız bu cihazda saklanır.'));
      c.appendChild(sum);
      saveOutcome(this.p.progress, this.card, { at: Date.now(), sonuc: n.sonuc, puan: this.score, en_yuksek: this.max, tehlikeli: this.danger });
      const again = el('button', 'btn', 'Vakayı yeniden çöz');
      again.addEventListener('click', () => { this.ctx.restart(this.card); });
      this.actions(c, again, this.nextBtn('Bitir', () => this.exit()));
    }

    // Dar ekranda kart tahtayı örter: "Tahtayı gör" kartı gizler, alttaki düğme geri getirir.
    peek(on) {
      const b = this.ctx.boardEl;
      if (!this._peekBtn) {
        this._peekBtn = el('button', 'btn primary case-peek-back', 'Vakaya dön');
        this._peekBtn.addEventListener('click', () => this.peek(false));
        b.appendChild(this._peekBtn);
      }
      b.classList.toggle('case-peek', on);
    }

    exit() {
      this.ctx.boardEl.classList.remove('case-peek');
      if (this._peekBtn) { this._peekBtn.remove(); this._peekBtn = null; }
      const q = this.ctx.qEl;
      q.hidden = true;
      q.replaceChildren();
      this.ctx.boardEl.classList.remove('has-question', 'case-mode');
      this.ctx.onExit(this);
    }
  }

  AT.CaseRun = CaseRun;

  // Ders klasöründeki vaka paketi (tools/paketle.mjs üretir). Yoksa boş liste.
  AT.loadCases = async (lesson) => {
    try {
      const d = await AT.loadLessonFile(lesson, 'vaka-paketi.json', lesson.id + ':vakalar');
      return (d && d.vakalar) || [];
    } catch (e) { return []; }
  };
})(window.AT = window.AT || {});
