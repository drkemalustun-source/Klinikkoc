/* Soru-cevap karşılaştırması: aynı soruları iki sağlayıcıya sorar, puanlatır, rapor çıkarır. */
(function (AT) {
  'use strict';

  const $ = (s) => document.querySelector(s);
  const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
  const STORE = 'at:qa-testi';
  const QUESTIONS = [
    'Çevrili defekt neden rekonstrüktif tedaviye daha uygun?',
    'Rekonstrüktif tedavi açık flep debridmanından daha başarılı mı?',
    'Bariyer membran kullanmak sonucu iyileştiriyor mu?',
    'Sistemik antibiyotik cerrahi sonucu etkiliyor mu?',
    'Keratinize mukoza genişliği cerrahi sonucu etkiler mi?',
    'İmplantoplasti hangi durumda tercih edilir?',
    'Sigara içen hastalarda cerrahi tedavi sonucu nasıl etkilenir?',
    'Başarı ölçütleri çalışmalar arasında neden farklı?',
    'Destekleyici bakıma uyum neden önemlidir?',
    'Diş beyazlatmada hangi jel daha etkilidir?'
  ];
  const state = (() => { try { return JSON.parse(localStorage.getItem(STORE)) || {}; } catch (e) { return {}; } })();
  state.sides = state.sides || [
    { provider: 'anthropic', model: 'claude-opus-5-5', baseURL: '', tools: true },
    { provider: 'ollama', model: 'qwen2.5:3b', baseURL: 'http://localhost:11434', tools: true }
  ];
  state.results = state.results || [];
  const save = () => { try { localStorage.setItem(STORE, JSON.stringify(state)); } catch (e) { /* yok */ } };
  $('#questions').value = (state.questions || QUESTIONS).join('\n');
  $('#questions').addEventListener('change', () => { state.questions = qs(); save(); });
  const qs = () => $('#questions').value.split('\n').map((s) => s.trim()).filter(Boolean);

  let lesson, retriever, ctrl = null;

  function renderSides() {
    const box = $('#sides');
    box.replaceChildren();
    state.sides.forEach((s, i) => {
      const card = el('div', 'engine side');
      card.appendChild(el('header', null, 'Model ' + 'AB'[i]));
      const p = AT.qa.providers[s.provider];
      const sel = el('select');
      for (const x of Object.values(AT.qa.providers)) { const o = el('option', null, x.label); o.value = x.id; o.selected = x.id === s.provider; sel.appendChild(o); }
      sel.addEventListener('change', () => {
        const np = AT.qa.providers[sel.value];
        Object.assign(s, { provider: np.id, model: np.defaultModel, baseURL: np.defaultBaseURL || '' });
        save(); renderSides();
      });
      const row = (label, node) => { const l = el('label'); l.append(el('span', null, label), node); card.appendChild(l); };
      row('Sağlayıcı', sel);
      const m = el('input'); m.type = 'text'; m.value = s.model; m.addEventListener('change', () => { s.model = m.value.trim(); save(); });
      row('Model', m);
      if (p.kind === 'local') {
        const u = el('input'); u.type = 'text'; u.value = s.baseURL; u.addEventListener('change', () => { s.baseURL = u.value.trim(); save(); });
        row('Adres', u);
        const t = el('input'); t.type = 'checkbox'; t.checked = s.tools; t.addEventListener('change', () => { s.tools = t.checked; save(); });
        row('Tahta aracı', t);
      }
      if (p.needsKey) card.appendChild(el('p', 'small ' + (AT.qa.getKey(p.id) ? 'muted' : 'warn'),
        AT.qa.getKey(p.id) ? 'Anahtar bu tarayıcıda kayıtlı.' : 'Anahtar yok: uygulamada Ayarlar → Soru-cevap bölümünden girin.'));
      box.appendChild(card);
    });
  }

  function cell(r, side) {
    const a = r.answers[side];
    const box = el('div', 'ans');
    const s = state.sides[side];
    box.appendChild(el('strong', null, 'Model ' + 'AB'[side] + ' · ' + (a && a.model || s.model)));
    if (!a) { box.appendChild(el('span', 'muted', 'Bekliyor…')); return box; }
    if (a.error) box.appendChild(el('span', 'err', a.error));
    else {
      box.appendChild(el('div', 'txt', a.text || '(boş cevap)'));
      if (a.boardTypes && a.boardTypes.length) box.appendChild(el('span', 'meta', 'Tahta: ' + a.boardTypes.join(', ')));
      box.appendChild(el('span', 'meta', [(a.ms / 1000).toFixed(1).replace('.', ',') + ' sn', a.usage.input + ' girdi', a.usage.output + ' çıktı',
        a.usage.cacheRead ? a.usage.cacheRead + ' önbellek' : null, a.cost != null ? '≈ $' + a.cost.toFixed(4).replace('.', ',') : 'ücretsiz/bilinmiyor'].filter(Boolean).join(' · ')));
      const rate = el('div', 'rate');
      for (const [k, label] of [['bagli', 'Kaynağa bağlılık'], ['anlasilir', 'Anlaşılırlık']]) {
        const l = el('label');
        const sel = el('select');
        for (const v of ['', 1, 2, 3, 4, 5]) { const o = el('option', null, v === '' ? '—' : String(v)); o.value = v; o.selected = String(a[k] || '') === String(v); sel.appendChild(o); }
        sel.addEventListener('change', () => { a[k] = sel.value ? Number(sel.value) : null; save(); renderSummary(); });
        l.append(el('span', null, label + ' '), sel);
        rate.appendChild(l);
      }
      box.appendChild(rate);
    }
    return box;
  }

  function renderResults() {
    const box = $('#results');
    box.replaceChildren();
    for (const r of state.results) {
      const row = el('div', 'qrow');
      row.appendChild(el('h3', null, r.q));
      const pair = el('div', 'pair');
      pair.append(cell(r, 0), cell(r, 1));
      row.appendChild(pair);
      if (r.passages) {
        const d = el('details', 'passages');
        d.appendChild(el('summary', null, 'Modellere verilen kaynak parçaları (' + r.passages.length + ')'));
        const ol = el('ol');
        r.passages.forEach((p) => ol.appendChild(el('li', null, p.ref + ' — ' + p.text.slice(0, 260) + (p.text.length > 260 ? '…' : ''))));
        d.appendChild(ol);
        row.appendChild(d);
      }
      box.appendChild(row);
    }
    renderSummary();
  }

  function summarize(side) {
    const as = state.results.map((r) => r.answers[side]).filter((a) => a && !a.error);
    const avg = (f) => { const v = as.map(f).filter((x) => x != null); return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null; };
    const med = (v) => { if (!v.length) return null; const s = [...v].sort((a, b) => a - b); return s[Math.floor(s.length / 2)]; };
    return {
      n: as.length, errors: state.results.filter((r) => r.answers[side] && r.answers[side].error).length,
      ms: med(as.map((a) => a.ms)), input: as.reduce((t, a) => t + a.usage.input, 0), output: as.reduce((t, a) => t + a.usage.output, 0),
      cost: as.some((a) => a.cost != null) ? as.reduce((t, a) => t + (a.cost || 0), 0) : null,
      bagli: avg((a) => a.bagli), anlasilir: avg((a) => a.anlasilir)
    };
  }
  const f1 = (v) => (v == null ? '—' : v.toFixed(1).replace('.', ','));

  function summaryRows() {
    return state.sides.map((s, i) => {
      const m = summarize(i);
      return ['Model ' + 'AB'[i] + ': ' + AT.qa.providers[s.provider].label + ' · ' + s.model, m.n + (m.errors ? ' (+' + m.errors + ' hata)' : ''),
        m.ms == null ? '—' : f1(m.ms / 1000) + ' sn', m.input + ' / ' + m.output, m.cost == null ? '—' : '$' + m.cost.toFixed(3).replace('.', ','),
        f1(m.bagli), f1(m.anlasilir)];
    });
  }
  const HEAD = ['Model', 'Cevap', 'Süre (ortanca)', 'Token girdi / çıktı', 'Maliyet (toplam)', 'Kaynağa bağlılık', 'Anlaşılırlık'];

  function renderSummary() {
    const t = el('table', 'sum');
    const hr = el('tr');
    for (const h of HEAD) hr.appendChild(el('th', null, h));
    t.appendChild(hr);
    for (const row of summaryRows()) { const tr = el('tr'); for (const c of row) tr.appendChild(el('td', null, c)); t.appendChild(tr); }
    $('#summary').replaceChildren(t);
  }

  async function run() {
    if (!lesson) return;
    ctrl = new AbortController();
    $('#run').disabled = true; $('#stop').disabled = false;
    state.results = qs().map((q) => ({ q, answers: [null, null] }));
    renderResults();
    for (const [i, r] of state.results.entries()) {
      for (const side of [0, 1]) {
        if (ctrl.signal.aborted) break;
        $('#status').textContent = (i + 1) + '/' + state.results.length + ' · Model ' + 'AB'[side];
        const s = state.sides[side];
        const p = AT.qa.providers[s.provider];
        const ctx = { lesson, retriever, sectionTitle: '', narration: '', history: [] };
        try {
          const a = await AT.qa.ask(r.q, ctx, { signal: ctrl.signal, noTotals: true,
            override: { provider: p, model: s.model, baseURL: s.baseURL || p.defaultBaseURL || '', tools: p.kind === 'api' ? true : s.tools } });
          r.passages = a.passages.map((x, k) => ({ ref: '[K' + (k + 1) + '] ' + (x.ref || x.title), text: x.text }));
          r.answers[side] = { text: a.text, model: a.model, ms: Math.round(a.ms), usage: a.usage, cost: a.cost,
            boardTypes: a.board.commands.map((c) => c.type), stop: a.stop };
        } catch (e) {
          r.answers[side] = { error: e.name === 'AbortError' ? 'Durduruldu.' : e.message };
        }
        save();
        renderResults();
      }
    }
    $('#status').textContent = ctrl.signal.aborted ? 'Durduruldu.' : 'Bitti. Şimdi cevapları puanlayın.';
    $('#run').disabled = false; $('#stop').disabled = true;
  }

  function download(name, text, type) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([text], { type }));
    a.download = name;
    document.body.appendChild(a); a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  }

  function report() {
    const L = ['# Soru-cevap karşılaştırması', '', 'Tarih: ' + new Date().toLocaleString('tr-TR'), 'Ders: ' + (lesson ? lesson.title : ''), '',
      '| ' + HEAD.join(' | ') + ' |', '|' + HEAD.map(() => '---').join('|') + '|', ...summaryRows().map((r) => '| ' + r.join(' | ') + ' |'), ''];
    for (const r of state.results) {
      L.push('## ' + r.q, '');
      r.answers.forEach((a, i) => {
        L.push('**Model ' + 'AB'[i] + '** (' + ((a && a.model) || state.sides[i].model) + ')' + (a && !a.error ? ' · kaynağa bağlılık ' + (a.bagli || '—') + ' · anlaşılırlık ' + (a.anlasilir || '—') : ''), '');
        L.push(a ? (a.error ? 'Hata: ' + a.error : a.text) : '—', '');
      });
    }
    return L.join('\n') + '\n';
  }

  $('#run').addEventListener('click', run);
  $('#stop').addEventListener('click', () => ctrl && ctrl.abort());
  $('#exportMd').addEventListener('click', () => download('soru-cevap-karsilastirma.md', report(), 'text/markdown;charset=utf-8'));
  $('#exportJson').addEventListener('click', () => download('soru-cevap-karsilastirma.json', JSON.stringify({ sides: state.sides, results: state.results }, null, 1), 'application/json'));

  renderSides();
  renderResults();
  (async () => {
    try {
      const cat = await AT.loadCatalog();
      const entry = cat.lessons.find((l) => l.id === 'peri-implantitis-cerrahi') || cat.lessons[0];
      if (!entry) throw new Error('kurulu ders yok; önce peri-implantitis ders paketini kurun');
      lesson = await AT.loadLesson(entry);
      retriever = AT.createRetriever(lesson);
      $('#status').textContent = 'Ders: ' + lesson.title;
    } catch (e) { $('#status').textContent = 'Ders yüklenemedi: ' + e.message; }
  })();
})(window.AT = window.AT || {});
