/* Ses testi sayfası. Motorları yalnızca AT.ses arayüzü üzerinden kullanır. */
(function (AT) {
  'use strict';
  const ses = AT.ses;
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => [...(r || document).querySelectorAll(s)];
  const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
  const fmtPct = (x) => x == null ? '–' : '%' + (x * 100).toFixed(1).replace('.', ',');
  const fmtMs = (x) => x == null ? '–' : (x >= 1000 ? (x / 1000).toFixed(1).replace('.', ',') + ' sn' : Math.round(x) + ' ms');
  const fmtMB = (b) => b == null ? '–' : b === 0 ? 'indirme yok' : (b / 1048576).toFixed(b > 104857600 ? 0 : 1).replace('.', ',') + ' MB';
  const fmtNum = (x, d) => x == null || isNaN(x) ? '–' : x.toFixed(d == null ? 1 : d).replace('.', ',');

  // ---------- Kalıcı durum ----------
  const store = {
    get(k, d) { try { const v = localStorage.getItem('st:' + k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem('st:' + k, JSON.stringify(v)); } catch (e) { /* özel pencere */ } }
  };
  const db = {
    open() {
      return this._p = this._p || new Promise((res, rej) => {
        const r = indexedDB.open('ses-testi', 1);
        r.onupgradeneeded = () => r.result.createObjectStore('kayit');
        r.onsuccess = () => res(r.result);
        r.onerror = () => rej(r.error);
      });
    },
    async tx(mode, fn) {
      const d = await this.open();
      return new Promise((res, rej) => {
        const t = d.transaction('kayit', mode);
        const out = fn(t.objectStore('kayit'));
        t.oncomplete = () => res(out && out.result !== undefined ? out.result : out);
        t.onerror = () => rej(t.error);
      });
    },
    put(k, v) { return this.tx('readwrite', (s) => s.put(v, k)); },
    del(k) { return this.tx('readwrite', (s) => s.delete(k)); },
    clear() { return this.tx('readwrite', (s) => s.clear()); },
    async all() {
      const d = await this.open();
      return new Promise((res, rej) => {
        const out = new Map();
        const c = d.transaction('kayit').objectStore('kayit').openCursor();
        c.onsuccess = () => { const cur = c.result; if (cur) { out.set(cur.key, cur.value); cur.continue(); } else res(out); };
        c.onerror = () => rej(c.error);
      });
    }
  };

  const state = {
    sentences: [],
    stt: new Map(),   // id -> { engine, selected, status, prep, error }
    tts: new Map(),   // anahtar -> { engine, voice, label, selected, status, prep, error }
    recordings: new Map(), // cümle id -> Float32Array (16 kHz)
    sttResults: store.get('sttResults', {}),
    sttPrep: store.get('sttPrep', {}),
    ttsPrep: store.get('ttsPrep', {}),
    ratings: store.get('ratings', {}),
    ttsTimes: store.get('ttsTimes', {}),
    device: null
  };

  function toast(msg, ms) {
    const t = $('#toast');
    t.textContent = msg; t.hidden = false;
    clearTimeout(toast._t); toast._t = setTimeout(() => { t.hidden = true; }, ms || 3500);
  }

  // ---------- Sekmeler ----------
  function showTab(id) {
    $$('.tabs button').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.tab === id)));
    $$('.tab').forEach((s) => { s.hidden = s.id !== id; });
    if (id === 'stt') renderStt();
    if (id === 'tts') renderTts();
    if (id === 'sonuc') renderResults();
    try { history.replaceState(null, '', '#' + id); } catch (e) { /* yok */ }
  }

  // ---------- 1. Hazırlık ----------
  async function setupEngines() {
    for (const id of ses.sttIds()) {
      const engine = ses.createSTT(id);
      const saved = store.get('sel:stt:' + id, null);
      state.stt.set(id, { engine, selected: saved == null ? id !== 'whisper-turbo' : saved, status: null, prep: state.sttPrep[id] || null, error: null });
    }
    const browser = ses.createTTS('tarayici');
    const bprep = await browser.init();
    // Tarayıcı sesleri indirme gerektirmez; hazır sayılır.
    for (const v of browser.voices()) Object.assign(addTts('tarayici|' + v.id, browser, v.id, 'Tarayıcı · ' + v.label), { ready: true, prep: bprep });
    if (!browser.voices().length) addTts('tarayici|', browser, null, 'Tarayıcı · (Türkçe ses yok)');
    const piper = ses.createTTS('piper');
    for (const v of piper.voices()) addTts('piper|' + v.id, piper, v.id, v.label);
    renderEngines();
    // Durumları sırayla sor (bazıları ağ/cihaz kontrolü yapar).
    for (const [, s] of state.stt) { s.status = await safeStatus(s.engine); renderEngines(); }
    for (const [, s] of state.tts) { s.status = await safeStatus(s.engine); renderEngines(); }
  }

  function addTts(key, engine, voice, label) {
    const saved = store.get('sel:tts:' + key, null);
    const s = { engine, voice, label, selected: saved == null ? true : saved, status: null, prep: state.ttsPrep[key] || null, error: null };
    state.tts.set(key, s);
    return s;
  }

  async function safeStatus(engine) {
    try { return await engine.status(); } catch (e) { return { ok: false, message: e.message }; }
  }

  function renderEngines() {
    renderEngineList($('#sttEngines'), state.stt, 'stt');
    renderEngineList($('#ttsEngines'), state.tts, 'tts');
  }

  function renderEngineList(root, map, kind) {
    root.replaceChildren();
    for (const [key, s] of map) {
      const info = s.engine.info || {};
      const card = el('article', 'engine' + (s.status && !s.status.ok ? ' off' : ''));
      const head = el('header');
      const cb = el('input'); cb.type = 'checkbox'; cb.checked = !!s.selected;
      cb.addEventListener('change', () => { s.selected = cb.checked; store.set('sel:' + kind + ':' + key, cb.checked); });
      head.append(cb, el('span', null, kind === 'stt' ? s.engine.label : s.label));
      card.appendChild(head);
      const dl = el('dl');
      const row = (k, v, cls) => { dl.append(el('dt', null, k)); dl.append(el('dd', cls || null, v)); };
      row('Veri cihazdan çıkar mı', info.dataLeavesDevice || '–', /^Evet/.test(info.dataLeavesDevice || '') ? 'bad' : null);
      row('İnternetsiz', info.offline || '–');
      if (info.note) row('Not', info.note);
      if (s.prep) {
        row('Hazırlık süresi', fmtMs(s.prep.loadMs));
        row('İndirilen', fmtMB(s.prep.bytes));
        if (s.prep.device) row('Çalıştığı yer', s.prep.device === 'webgpu' ? 'Ekran kartı (WebGPU)' : s.prep.device === 'wasm' ? 'İşlemci (WASM)' : s.prep.device);
      }
      card.appendChild(dl);
      const st = el('div', 'state');
      if (s.error) { st.textContent = 'Hata: ' + s.error; st.classList.add('bad'); }
      else if (s.ready) { st.textContent = 'Hazır.'; st.classList.add('ok'); }
      else if (s.status) { st.textContent = s.status.message; st.classList.add(s.status.ok ? 'muted' : 'bad'); }
      else st.textContent = 'Kontrol ediliyor…';
      card.appendChild(st);
      const bar = el('div', 'bar'); const fill = el('div'); bar.appendChild(fill); bar.hidden = true;
      card.appendChild(bar);
      s._bar = { bar, fill, st };
      root.appendChild(card);
    }
  }

  async function prepareOne(kind, key, s) {
    s.error = null;
    s._bar.bar.hidden = false;
    s._bar.st.textContent = 'Hazırlanıyor…';
    s._bar.st.className = 'state muted';
    const onProgress = (p) => {
      if (p.total) s._bar.fill.style.width = Math.min(100, p.loaded / p.total * 100) + '%';
      s._bar.st.textContent = 'İndiriliyor: ' + fmtMB(p.loaded) + (p.total ? ' / ' + fmtMB(p.total) : '');
    };
    try {
      const prep = await s.engine.init(onProgress, { voice: s.voice });
      s.prep = prep; s.ready = true;
      (kind === 'stt' ? state.sttPrep : state.ttsPrep)[key] = prep;
      store.set(kind === 'stt' ? 'sttPrep' : 'ttsPrep', kind === 'stt' ? state.sttPrep : state.ttsPrep);
    } catch (e) {
      s.error = friendlyError(e);
      console.error(key, e);
    }
  }

  function friendlyError(e) {
    const m = (e && (e.message || String(e))) || 'bilinmeyen hata';
    if (/Failed to fetch|NetworkError|ERR_|Load failed|status 4\d\d|status 5\d\d/i.test(m)) {
      return 'Model indirilemedi. İnternet bağlantısını ve huggingface.co / cdn.jsdelivr.net adreslerine erişimi kontrol edin. (' + m + ')';
    }
    if (/out of memory|Aborted\(|RangeError: Array buffer allocation/i.test(m)) return 'Bellek yetmedi; daha küçük bir model deneyin. (' + m + ')';
    return m;
  }

  async function prepareAll() {
    const btn = $('#prepareAll');
    btn.disabled = true;
    const todo = [];
    for (const [k, s] of state.stt) if (s.selected && s.status && s.status.ok && !s.ready) todo.push(['stt', k, s]);
    for (const [k, s] of state.tts) if (s.selected && s.status && s.status.ok && !s.ready) todo.push(['tts', k, s]);
    $('#prepareNote').textContent = todo.length ? todo.length + ' motor hazırlanacak.' : 'Hazırlanacak motor yok (seçili olanlar hazır ya da bu cihazda çalışmıyor).';
    let n = 0;
    for (const [kind, key, s] of todo) {
      $('#prepareNote').textContent = (++n) + ' / ' + todo.length + ' hazırlanıyor: ' + (s.label || s.engine.label);
      await prepareOne(kind, key, s);
      renderEngines();
    }
    btn.disabled = false;
    const failed = todo.filter(([, , s]) => s.error).length;
    $('#prepareNote').textContent = todo.length ? 'Bitti. ' + (todo.length - failed) + ' hazır' + (failed ? ', ' + failed + ' hata' : '') + '.' : $('#prepareNote').textContent;
  }

  // ---------- 2. Kayıt ----------
  let mic = null; // { stream, ctx, node, chunks, id, rate }

  async function startRecording(id, btn) {
    if (mic) await stopRecording();
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
    } catch (e) {
      toast('Mikrofona erişilemedi: ' + e.message, 6000);
      return;
    }
    const ctx = new AudioContext();
    const src = ctx.createMediaStreamSource(stream);
    const node = ctx.createScriptProcessor(4096, 1, 1);
    const chunks = [];
    node.onaudioprocess = (ev) => {
      const d = ev.inputBuffer.getChannelData(0);
      chunks.push(new Float32Array(d));
      let s = 0; for (let i = 0; i < d.length; i++) s += d[i] * d[i];
      $('#meterFill').style.width = Math.min(100, Math.sqrt(s / d.length) * 400) + '%';
    };
    src.connect(node); node.connect(ctx.destination);
    mic = { stream, ctx, node, chunks, id, rate: ctx.sampleRate, btn };
    btn.textContent = 'Durdur'; btn.classList.add('rec');
  }

  async function stopRecording() {
    if (!mic) return;
    const m = mic; mic = null;
    m.node.disconnect(); m.stream.getTracks().forEach((t) => t.stop());
    await m.ctx.close();
    $('#meterFill').style.width = '0';
    const len = m.chunks.reduce((a, c) => a + c.length, 0);
    const all = new Float32Array(len);
    let o = 0; for (const c of m.chunks) { all.set(c, o); o += c.length; }
    const a16 = ses.resample(all, m.rate, ses.SAMPLE_RATE);
    state.recordings.set(m.id, a16);
    await db.put(m.id, a16);
    renderRecList();
  }

  function renderRecList() {
    const root = $('#recList');
    root.replaceChildren();
    for (const c of state.sentences) {
      const li = el('li');
      li.appendChild(el('div', 'text', c.metin));
      const ctl = el('div', 'ctl');
      const rec = el('button', null, state.recordings.has(c.id) ? 'Yeniden kaydet' : 'Kaydet');
      rec.addEventListener('click', () => (mic && mic.id === c.id ? stopRecording() : startRecording(c.id, rec)));
      ctl.appendChild(rec);
      const a = state.recordings.get(c.id);
      if (a) {
        const play = el('button', 'ghost', 'Dinle');
        play.addEventListener('click', () => { const u = URL.createObjectURL(ses.toWav(a)); const au = new Audio(u); au.onended = () => URL.revokeObjectURL(u); au.play(); });
        ctl.appendChild(play);
        const sp = ses.detectSpeech(a);
        ctl.appendChild(el('span', sp ? 'muted small' : 'bad small', (a.length / ses.SAMPLE_RATE).toFixed(1).replace('.', ',') + ' sn' + (sp ? '' : ' · konuşma algılanmadı, yeniden kaydedin')));
      }
      ctl.appendChild(el('span', 'tag', ({ makale: 'makale dili', gunluk: 'günlük klinik dil', karisik: 'İngilizce karışık', latince: 'Latince' })[c.tur] || c.tur));
      li.appendChild(ctl);
      root.appendChild(li);
    }
  }

  async function exportRecordings() {
    const out = { tur: 'ses-testi-kayitlari', ornekleme: ses.SAMPLE_RATE, kayitlar: {} };
    for (const [id, a] of state.recordings) out.kayitlar[id] = b64(new Uint8Array(a.buffer, a.byteOffset, a.byteLength));
    download('ses-testi-kayitlar.json', JSON.stringify(out), 'application/json');
  }
  async function importRecordings(file) {
    const data = JSON.parse(await file.text());
    if (data.tur !== 'ses-testi-kayitlari') throw new Error('Bu bir kayıt dosyası değil.');
    for (const [id, s] of Object.entries(data.kayitlar)) {
      const bytes = unb64(s);
      const a = new Float32Array(bytes.buffer, bytes.byteOffset, bytes.byteLength / 4).slice();
      state.recordings.set(id, a); await db.put(id, a);
    }
    renderRecList();
    toast(Object.keys(data.kayitlar).length + ' kayıt yüklendi.');
  }

  // ---------- 3. Konuşma tanıma ----------
  let sttStop = false;

  async function runStt() {
    const engines = [...state.stt].filter(([, s]) => s.selected && s.ready);
    if (!engines.length) { toast('Önce Hazırlık bölümünde en az bir konuşma tanıma motorunu hazırlayın.', 5000); return; }
    const recs = state.sentences.filter((c) => state.recordings.has(c.id));
    if (!recs.length) { toast('Önce Kayıt bölümünde cümleleri kaydedin.', 5000); return; }
    sttStop = false;
    $('#runStt').disabled = true; $('#stopStt').hidden = false;
    const live = $('#liveMode').checked;
    let done = 0;
    const total = engines.length * recs.length;
    for (const [id, s] of engines) {
      s.engine.live = live && /^tarayici/.test(id);
      const res = state.sttResults[id] = state.sttResults[id] || {};
      for (const c of recs) {
        if (sttStop) break;
        $('#sttProgress').textContent = (++done) + ' / ' + total + ' · ' + s.engine.label + ' · ' + c.id + (s.engine.live ? ' · Şimdi okuyun: "' + c.metin + '"' : '');
        await new Promise((r) => setTimeout(r, 30)); // ekran güncellensin
        const audio = state.recordings.get(c.id);
        try {
          const r = await s.engine.transcribe(audio, { lang: 'tr' });
          res[c.id] = score(c, r, audio, navigator.onLine);
        } catch (e) {
          res[c.id] = { error: friendlyError(e), online: navigator.onLine, at: Date.now() };
        }
        store.set('sttResults', state.sttResults);
        renderStt();
      }
    }
    $('#runStt').disabled = false; $('#stopStt').hidden = true;
    $('#sttProgress').textContent = sttStop ? 'Durduruldu.' : 'Bitti.';
  }

  function score(c, r, audio, online) {
    const w = ses.wer(c.metin, r.text), ch = ses.cer(c.metin, r.text);
    const terms = {};
    for (const t of c.terimler) terms[t] = ses.termHit(t, r.text);
    return {
      text: r.text, raw: r.raw, note: r.note, ms: r.ms, totalMs: r.totalMs, roundTripMs: r.roundTripMs, device: r.device, source: r.source,
      audioMs: audio.length / ses.SAMPLE_RATE * 1000,
      wer: w, cer: ch, terms, online, at: Date.now()
    };
  }

  function summarizeStt(id) {
    const res = state.sttResults[id] || {};
    let we = 0, ww = 0, ce = 0, cc = 0, th = 0, tt = 0, n = 0, errs = 0, offlineOk = 0;
    const lat = [], rtf = [];
    for (const c of state.sentences) {
      const r = res[c.id];
      if (!r) continue;
      if (r.error) { errs++; continue; }
      n++; we += r.wer.errors; ww += r.wer.words; ce += r.cer.errors; cc += r.cer.chars;
      for (const v of Object.values(r.terms)) { tt++; if (v) th++; }
      if (r.ms != null) { lat.push(r.ms); if (r.audioMs) rtf.push(r.ms / r.audioMs); }
      if (r.online === false) offlineOk++;
    }
    const med = (a) => { if (!a.length) return null; const s = [...a].sort((x, y) => x - y); return s[Math.floor(s.length / 2)]; };
    return { n, errs, wer: ww ? we / ww : null, cer: cc ? ce / cc : null, terms: tt ? th / tt : null, termHit: th, termTotal: tt, latency: med(lat), rtf: med(rtf), offlineOk };
  }

  function renderStt() {
    const ids = [...state.stt.keys()].filter((id) => state.sttResults[id]);
    const sum = $('#sttSummary'); sum.replaceChildren();
    if (!ids.length) { sum.appendChild(el('p', 'muted', 'Henüz sonuç yok.')); $('#sttDetail').replaceChildren(); return; }
    sum.appendChild(sttSummaryTable(ids));
    // Ayrıntı: cümle başına her motorun çıktısı.
    const wrap = el('div', 'table-wrap');
    const t = el('table');
    const hr = el('tr'); hr.append(el('th', null, 'Cümle'));
    for (const id of ids) hr.append(el('th', null, state.stt.get(id).engine.label));
    t.appendChild(hr);
    for (const c of state.sentences) {
      if (!ids.some((id) => state.sttResults[id][c.id])) continue;
      const tr = el('tr');
      const td0 = el('td'); td0.append(el('div', null, c.id + '. ' + c.metin));
      tr.appendChild(td0);
      for (const id of ids) {
        const r = state.sttResults[id][c.id];
        const td = el('td', 'hyp');
        if (!r) td.textContent = '–';
        else if (r.error) { td.textContent = r.error; td.classList.add('bad'); }
        else {
          td.appendChild(diffView(c.metin, r.text));
          const meta = el('div', 'muted small', 'WER ' + fmtPct(r.wer.rate) + ' · ' + fmtMs(r.ms) + (r.note ? ' · ' + r.note : ''));
          td.appendChild(meta);
          const miss = Object.entries(r.terms).filter(([, v]) => !v).map(([k]) => k);
          if (miss.length) td.appendChild(el('div', 'bad small', 'Kaçan terim: ' + miss.join(', ')));
        }
        tr.appendChild(td);
      }
      t.appendChild(tr);
    }
    wrap.appendChild(t);
    $('#sttDetail').replaceChildren(el('h3', null, 'Cümle cümle'), wrap);
  }

  function sttSummaryTable(ids) {
    const wrap = el('div', 'table-wrap');
    const t = el('table');
    const head = ['Motor', 'Kelime hata oranı', 'Karakter hata oranı', 'Terim doğruluğu', 'Gecikme (ortanca)', 'Hız (işlem/kayıt)', 'İlk hazırlık', 'Model boyutu', 'İnternetsiz', 'Veri cihazdan çıkar mı', 'Cümle'];
    const hr = el('tr'); head.forEach((h) => hr.append(el('th', null, h))); t.appendChild(hr);
    for (const id of ids) {
      const s = state.stt.get(id), m = summarizeStt(id), info = s.engine.info || {}, prep = s.prep || state.sttPrep[id] || {};
      const tr = el('tr');
      const cell = (v, cls) => { const td = el('td', cls, v); tr.appendChild(td); return td; };
      cell(s.engine.label + (prep.device ? ' · ' + prep.device : ''));
      cell(fmtPct(m.wer), 'num ' + grade(m.wer, 0.1, 0.25));
      cell(fmtPct(m.cer), 'num');
      cell(m.terms == null ? '–' : fmtPct(m.terms) + ' (' + m.termHit + '/' + m.termTotal + ')', 'num ' + grade(m.terms == null ? null : 1 - m.terms, 0.1, 0.3));
      cell(fmtMs(m.latency), 'num');
      cell(m.rtf == null ? '–' : fmtNum(m.rtf, 2) + '×', 'num');
      cell(fmtMs(prep.loadMs), 'num');
      cell(fmtMB(prep.bytes), 'num');
      cell(info.offline + (m.offlineOk ? ' · internetsiz denendi ✓' : ''));
      cell(info.dataLeavesDevice || '–', /^Evet/.test(info.dataLeavesDevice || '') ? 'bad' : null);
      cell(m.n + (m.errs ? ' (+' + m.errs + ' hata)' : ''), 'num');
      t.appendChild(tr);
    }
    wrap.appendChild(t);
    return wrap;
  }

  const grade = (x, good, bad) => x == null ? '' : x <= good ? 'ok' : x >= bad ? 'bad' : 'mid';

  // Kelime düzeyinde hizalama: doğru kelimeler düz, hatalı/fazla kelimeler işaretli, eksikler üstü çizili.
  function diffView(ref, hyp) {
    const r = ses.normalize(ref).split(' ').filter(Boolean), h = ses.normalize(hyp).split(' ').filter(Boolean);
    const m = r.length, n = h.length;
    const d = Array.from({ length: m + 1 }, (_, i) => { const row = new Array(n + 1).fill(0); row[0] = i; return row; });
    for (let j = 0; j <= n; j++) d[0][j] = j;
    for (let i = 1; i <= m; i++) for (let j = 1; j <= n; j++) d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (r[i - 1] === h[j - 1] ? 0 : 1));
    const ops = [];
    let i = m, j = n;
    while (i > 0 || j > 0) {
      if (i > 0 && j > 0 && d[i][j] === d[i - 1][j - 1] + (r[i - 1] === h[j - 1] ? 0 : 1)) { ops.push(r[i - 1] === h[j - 1] ? ['=', h[j - 1]] : ['~', h[j - 1], r[i - 1]]); i--; j--; }
      else if (j > 0 && d[i][j] === d[i][j - 1] + 1) { ops.push(['+', h[j - 1]]); j--; }
      else { ops.push(['-', r[i - 1]]); i--; }
    }
    ops.reverse();
    const div = el('div');
    if (!h.length) { div.appendChild(el('em', 'muted', '(boş)')); }
    for (const op of ops) {
      if (op[0] === '=') div.append(op[1] + ' ');
      else if (op[0] === '-') { div.append(el('del', null, op[1])); div.append(' '); }
      else { const s = el('span', 'err', op[1]); s.title = op[0] === '~' ? 'doğrusu: ' + op[2] : 'fazla kelime'; div.append(s); div.append(' '); }
    }
    return div;
  }

  // ---------- 4. Seslendirme ----------
  let speaking = null;

  function ttsCandidates() {
    return [...state.tts].filter(([, s]) => s.selected && s.ready && s.voice !== null);
  }

  function renderTts() {
    const root = $('#ttsTable');
    root.replaceChildren();
    const cands = ttsCandidates();
    if (!cands.length) { root.appendChild(el('p', 'muted', 'Önce Hazırlık bölümünde en az bir sesi seçip hazırlayın.')); return; }
    const blind = $('#blindMode').checked;
    // Kör modda sesler sabit ama karışık bir sırayla, harfle gösterilir.
    const order = blind ? shuffleStable(cands.map(([k]) => k)) : cands.map(([k]) => k);
    const names = {}; order.forEach((k, i) => { names[k] = blind ? 'Ses ' + String.fromCharCode(65 + i) : state.tts.get(k).label; });
    const wrap = el('div', 'table-wrap');
    const t = el('table');
    const hr = el('tr'); hr.append(el('th', null, 'Cümle'));
    order.forEach((k) => hr.append(el('th', null, names[k])));
    t.appendChild(hr);
    for (const c of state.sentences) {
      const tr = el('tr');
      tr.appendChild(el('td', null, c.id + '. ' + c.metin));
      for (const k of order) tr.appendChild(ttsCell(k, c));
      t.appendChild(tr);
    }
    wrap.appendChild(t);
    root.appendChild(wrap);
  }

  function ttsCell(key, c) {
    const s = state.tts.get(key);
    const r = ((state.ratings[key] = state.ratings[key] || {})[c.id] = state.ratings[key][c.id] || { anl: null, dog: null, yanlis: [] });
    const td = el('td');
    const box = el('div', 'tts-cell');
    const play = el('button', null, '▶ Dinle');
    play.addEventListener('click', async () => {
      if (speaking) speaking.stop();
      speaking = s.engine;
      play.disabled = true;
      ses.setDictionary($('#useDict').checked ? dictRows() : []);
      try {
        const res = await s.engine.speak(c.metin, { voice: s.voice, rate: parseFloat($('#ttsRate').value) });
        if (res && res.firstAudioMs != null && !res.cancelled) {
          (state.ttsTimes[key] = state.ttsTimes[key] || []).push(res.firstAudioMs);
          store.set('ttsTimes', state.ttsTimes);
        }
      } catch (e) { toast('Seslendirme hatası: ' + e.message, 6000); }
      play.disabled = false;
    });
    box.appendChild(play);
    box.appendChild(rateRow('Anlaşılırlık', r, 'anl'));
    box.appendChild(rateRow('Doğallık', r, 'dog'));
    const terms = el('div', 'terms');
    terms.appendChild(el('span', 'lbl', 'Yanlış okunan:'));
    for (const term of c.terimler) {
      const l = el('label', 'check');
      const cb = el('input'); cb.type = 'checkbox'; cb.checked = r.yanlis.includes(term);
      cb.addEventListener('change', () => {
        r.yanlis = cb.checked ? [...new Set([...r.yanlis, term])] : r.yanlis.filter((x) => x !== term);
        store.set('ratings', state.ratings);
      });
      l.append(cb, term);
      terms.appendChild(l);
    }
    box.appendChild(terms);
    td.appendChild(box);
    return td;
  }

  function rateRow(label, r, field) {
    const row = el('div');
    row.appendChild(el('div', 'lbl', label));
    const g = el('div', 'rate');
    for (let i = 1; i <= 5; i++) {
      const b = el('button', r[field] === i ? 'on' : null, String(i));
      b.setAttribute('aria-label', label + ' ' + i);
      b.addEventListener('click', () => {
        r[field] = r[field] === i ? null : i;
        store.set('ratings', state.ratings);
        $$('button', g).forEach((x, k) => x.classList.toggle('on', r[field] === k + 1));
      });
      g.appendChild(b);
    }
    row.appendChild(g);
    return row;
  }

  function shuffleStable(arr) {
    // Oturum boyunca aynı kalan karışık sıra.
    let seed = store.get('blindSeed', null);
    if (seed == null) { seed = Math.floor(Math.random() * 1e9); store.set('blindSeed', seed); }
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) { seed = (seed * 1103515245 + 12345) % 2147483648; const j = seed % (i + 1); [a[i], a[j]] = [a[j], a[i]]; }
    return a;
  }

  function summarizeTts(key) {
    const r = state.ratings[key] || {};
    let a = 0, an = 0, d = 0, dn = 0, wrong = 0, rated = 0;
    const wrongTerms = {};
    for (const v of Object.values(r)) {
      if (v.anl) { a += v.anl; an++; }
      if (v.dog) { d += v.dog; dn++; }
      if (v.anl || v.dog) rated++;
      for (const t of v.yanlis || []) { wrong++; wrongTerms[t] = (wrongTerms[t] || 0) + 1; }
    }
    const times = state.ttsTimes[key] || [];
    const med = times.length ? [...times].sort((x, y) => x - y)[Math.floor(times.length / 2)] : null;
    return { anl: an ? a / an : null, dog: dn ? d / dn : null, rated, wrong, wrongTerms, firstAudio: med };
  }

  function ttsSummaryTable() {
    const keys = [...state.tts.keys()].filter((k) => state.ratings[k] && Object.values(state.ratings[k]).some((v) => v.anl || v.dog || (v.yanlis && v.yanlis.length)));
    if (!keys.length) return el('p', 'muted', 'Henüz puanlama yok.');
    const wrap = el('div', 'table-wrap');
    const t = el('table');
    const hr = el('tr');
    ['Ses', 'Anlaşılırlık (1–5)', 'Doğallık (1–5)', 'Puanlanan cümle', 'Yanlış okunan terim', 'Sese başlama süresi', 'İlk hazırlık', 'Model boyutu', 'İnternetsiz', 'Veri cihazdan çıkar mı'].forEach((h) => hr.append(el('th', null, h)));
    t.appendChild(hr);
    for (const k of keys) {
      const s = state.tts.get(k), m = summarizeTts(k), info = s.engine.info || {}, prep = s.prep || state.ttsPrep[k] || {};
      const tr = el('tr');
      const cell = (v, cls) => tr.appendChild(el('td', cls, v));
      cell(s.label);
      cell(fmtNum(m.anl), 'num'); cell(fmtNum(m.dog), 'num'); cell(String(m.rated), 'num');
      cell(m.wrong ? Object.entries(m.wrongTerms).map(([t, n]) => t + (n > 1 ? ' ×' + n : '')).join(', ') : 'yok');
      cell(fmtMs(m.firstAudio), 'num');
      cell(fmtMs(prep.loadMs), 'num'); cell(fmtMB(prep.bytes), 'num');
      cell(s.engine.id === 'tarayici' ? (/(cihazda)/.test(s.label) ? 'Evet' : 'Hayır') : info.offline);
      cell(s.engine.id === 'tarayici' ? (/(cihazda)/.test(s.label) ? 'Hayır' : 'Evet (sunucu sesi)') : info.dataLeavesDevice);
      t.appendChild(tr);
    }
    wrap.appendChild(t);
    return wrap;
  }

  // ---------- 5. Telaffuz sözlüğü ----------
  let fileDict = [];

  function renderDict(entries) {
    const body = $('#dictBody');
    body.replaceChildren();
    for (const e of entries) body.appendChild(dictRow(e));
    updateDictPreview();
  }
  function dictRow(e) {
    const tr = el('tr');
    const a = el('input'); a.type = 'text'; a.value = e.yazim || ''; a.className = 'yazim';
    const b = el('input'); b.type = 'text'; b.value = e.okunus || ''; b.className = 'okunus';
    const c = el('input'); c.type = 'checkbox'; c.checked = !!e.tam; c.className = 'tam';
    const del = el('button', 'ghost', 'Sil'); del.addEventListener('click', () => { tr.remove(); updateDictPreview(); });
    [a, b].forEach((x) => x.addEventListener('input', updateDictPreview));
    c.addEventListener('change', updateDictPreview);
    for (const x of [a, b, c, del]) { const td = el('td'); td.appendChild(x); tr.appendChild(td); }
    return tr;
  }
  function dictRows() {
    return $$('#dictBody tr').map((tr) => {
      const o = { yazim: $('.yazim', tr).value.trim(), okunus: $('.okunus', tr).value.trim() };
      if ($('.tam', tr).checked) o.tam = true;
      return o;
    }).filter((e) => e.yazim);
  }
  function updateDictPreview() {
    ses.setDictionary(dictRows());
    $('#dictPreview').textContent = 'Seslendiriciye giden metin: ' + ses.pronounce($('#dictTry').value);
  }
  function fillDictVoices() {
    const sel = $('#dictVoice');
    sel.replaceChildren();
    for (const [k, s] of state.tts) { if (s.voice === null) continue; const o = el('option', null, s.label); o.value = k; sel.appendChild(o); }
  }

  // ---------- 6. Sonuçlar ----------
  function renderResults() {
    const root = $('#resultTables');
    root.replaceChildren();
    root.appendChild(el('h3', null, 'Konuşma tanıma'));
    const ids = [...state.stt.keys()].filter((id) => state.sttResults[id]);
    root.appendChild(ids.length ? sttSummaryTable(ids) : el('p', 'muted', 'Henüz sonuç yok.'));
    root.appendChild(el('h3', null, 'Seslendirme'));
    root.appendChild(ttsSummaryTable());
    root.appendChild(el('h3', null, 'Cihaz'));
    root.appendChild(el('p', 'muted small', deviceLine()));
  }

  function deviceLine() {
    const d = state.device || {};
    return [d.tarayici, d.platform, d.cekirdek ? d.cekirdek + ' çekirdek' : null, d.bellekGB ? d.bellekGB + ' GB bellek' : null, d.webgpu ? 'WebGPU: ' + d.webgpu : 'WebGPU yok'].filter(Boolean).join(' · ');
  }

  async function detectDevice() {
    const ua = navigator.userAgentData;
    let brands = null, platform = navigator.platform;
    if (ua) {
      brands = ua.brands.filter((b) => !/Not.?A.?Brand/i.test(b.brand)).map((b) => b.brand + ' ' + b.version).join(', ');
      try { const h = await ua.getHighEntropyValues(['platformVersion', 'fullVersionList']); platform = ua.platform + ' ' + (h.platformVersion || ''); if (h.fullVersionList) brands = h.fullVersionList.filter((b) => !/Not.?A.?Brand/i.test(b.brand)).map((b) => b.brand + ' ' + b.version).join(', '); } catch (e) { /* izin yok */ }
    }
    let webgpu = null;
    if (navigator.gpu) {
      try { const a = await navigator.gpu.requestAdapter(); if (a) { const i = a.info || {}; webgpu = [i.vendor, i.architecture, i.description].filter(Boolean).join(' ') || 'var'; } } catch (e) { /* yok */ }
    }
    state.device = { tarayici: brands || navigator.userAgent, platform, cekirdek: navigator.hardwareConcurrency, bellekGB: navigator.deviceMemory, webgpu, userAgent: navigator.userAgent };
  }

  function buildReport() {
    const stt = {};
    for (const [id, s] of state.stt) {
      if (!state.sttResults[id]) continue;
      stt[id] = { ad: s.engine.label, ozet: summarizeStt(id), hazirlik: s.prep || state.sttPrep[id] || null, bilgi: s.engine.info, cumleler: state.sttResults[id] };
    }
    const tts = {};
    for (const [k, s] of state.tts) {
      if (!state.ratings[k] && !state.ttsTimes[k]) continue;
      tts[k] = { ad: s.label, ozet: summarizeTts(k), hazirlik: s.prep || state.ttsPrep[k] || null, puanlar: state.ratings[k] || {} };
    }
    return {
      tur: 'ses-testi-raporu', surum: 1, tarih: new Date().toISOString(), cihaz: state.device,
      cumleler: state.sentences, sozluk: dictRows(), stt, tts
    };
  }

  function reportMarkdown(rep) {
    const L = ['# Ses testi raporu', '', 'Tarih: ' + rep.tarih, 'Cihaz: ' + deviceLine(), '', '## Konuşma tanıma', '',
      '| Motor | WER | CER | Terim | Gecikme | İlk hazırlık | Boyut | Cümle |', '|---|---|---|---|---|---|---|---|'];
    for (const v of Object.values(rep.stt)) {
      const m = v.ozet, p = v.hazirlik || {};
      L.push(`| ${v.ad}${p.device ? ' (' + p.device + ')' : ''} | ${fmtPct(m.wer)} | ${fmtPct(m.cer)} | ${m.terms == null ? '–' : fmtPct(m.terms)} | ${fmtMs(m.latency)} | ${fmtMs(p.loadMs)} | ${fmtMB(p.bytes)} | ${m.n}${m.errs ? ' (+' + m.errs + ' hata)' : ''} |`);
    }
    L.push('', '## Seslendirme', '', '| Ses | Anlaşılırlık | Doğallık | Puanlanan | Yanlış okunan terimler | Başlama |', '|---|---|---|---|---|---|');
    for (const v of Object.values(rep.tts)) {
      const m = v.ozet;
      L.push(`| ${v.ad} | ${fmtNum(m.anl)} | ${fmtNum(m.dog)} | ${m.rated} | ${Object.keys(m.wrongTerms).join(', ') || 'yok'} | ${fmtMs(m.firstAudio)} |`);
    }
    return L.join('\n');
  }

  // ---------- Yardımcılar ----------
  function download(name, text, type) {
    const u = URL.createObjectURL(new Blob([text], { type }));
    const a = el('a'); a.href = u; a.download = name; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(u), 2000);
  }
  function b64(bytes) { let s = ''; for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000)); return btoa(s); }
  function unb64(s) { const bin = atob(s); const out = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i); return out; }

  // ---------- Başlat ----------
  async function main() {
    if (!window.isSecureContext) $('#originWarn').hidden = false;
    $$('.tabs button').forEach((b) => b.addEventListener('click', () => showTab(b.dataset.tab)));
    state.sentences = (await (await fetch('cumleler.json', { cache: 'no-cache' })).json()).cumleler;

    try { state.recordings = await db.all(); } catch (e) { console.warn('Kayıtlar okunamadı', e); }
    renderRecList();

    const dict = await ses.loadDictionary();
    try { fileDict = (await (await fetch(ses.ROOT + 'ses/telaffuz.json', { cache: 'no-cache' })).json()).entries; } catch (e) { fileDict = []; }
    renderDict(dict.entries);

    detectDevice();
    await setupEngines();
    fillDictVoices();

    $('#prepareAll').addEventListener('click', prepareAll);
    $('#exportRec').addEventListener('click', exportRecordings);
    $('#importRec').addEventListener('change', (e) => { const f = e.target.files[0]; if (f) importRecordings(f).catch((err) => toast(err.message, 6000)); e.target.value = ''; });
    $('#clearRec').addEventListener('click', async () => { if (!confirm('Tüm kayıtlar silinsin mi?')) return; await db.clear(); state.recordings.clear(); renderRecList(); });
    $('#runStt').addEventListener('click', runStt);
    $('#stopStt').addEventListener('click', () => { sttStop = true; });
    $('#ttsRate').addEventListener('input', (e) => { $('#ttsRateVal').textContent = parseFloat(e.target.value).toFixed(2).replace('.', ','); });
    $('#blindMode').addEventListener('change', renderTts);
    $('#dictAdd').addEventListener('click', () => { $('#dictBody').appendChild(dictRow({})); });
    $('#dictSave').addEventListener('click', () => { ses.saveLocalDictionary(dictRows()); toast('Sözlük bu tarayıcıda kaydedildi. Kalıcı olması için "telaffuz.json olarak indir" ile dosyayı da alın.', 6000); });
    $('#dictDownload').addEventListener('click', () => {
      download('telaffuz.json', JSON.stringify({ aciklama: 'Telaffuz sözlüğü (ses testi sayfasından indirildi).', entries: dictRows() }, null, 1), 'application/json');
    });
    $('#dictReset').addEventListener('click', () => { ses.clearLocalDictionary(); renderDict(fileDict); toast('Dosyadaki sözlüğe dönüldü.'); });
    $('#dictTry').addEventListener('input', updateDictPreview);
    $('#dictSpeak').addEventListener('click', async () => {
      const s = state.tts.get($('#dictVoice').value);
      if (!s) return;
      if (s.engine.id === 'piper' && !s.ready) { toast('Bu Piper sesi henüz hazırlanmadı (Hazırlık bölümü).', 5000); return; }
      ses.setDictionary(dictRows());
      try { await s.engine.speak($('#dictTry').value, { voice: s.voice }); } catch (e) { toast(e.message, 6000); }
    });
    $('#downloadReport').addEventListener('click', () => {
      const rep = buildReport();
      download('ses-testi-raporu-' + rep.tarih.slice(0, 10) + '.json', JSON.stringify(rep, null, 1), 'application/json');
    });
    $('#copyReport').addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(reportMarkdown(buildReport())); toast('Rapor metni panoya kopyalandı.'); } catch (e) { toast('Kopyalanamadı: ' + e.message); }
    });
    $('#clearResults').addEventListener('click', () => {
      if (!confirm('Tüm test sonuçları ve puanlar silinsin mi? (Kayıtlar kalır.)')) return;
      state.sttResults = {}; state.ratings = {}; state.ttsTimes = {};
      store.set('sttResults', {}); store.set('ratings', {}); store.set('ttsTimes', {});
      renderResults();
    });

    const start = (location.hash || '').slice(1);
    if (start && $('#' + start)) showTab(start);
  }

  main().catch((e) => { console.error(e); toast('Sayfa başlatılamadı: ' + e.message, 10000); });
})(window.AT = window.AT || {});
