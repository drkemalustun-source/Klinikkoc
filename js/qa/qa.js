/* Canlı soru-cevap çekirdeği. Sağlayıcıdan bağımsızdır; sağlayıcılar ayrı dosyalarda kaydolur.
 *
 * Üç kip:
 *   none  : model yok (varsayılan). Soru, ders anlatımında ve kaynak dizininde aranır;
 *           ilgili parçalar "Dinle" bağlantılarıyla gösterilir. Hiçbir ağ çağrısı yapılmaz.
 *   local : bilgisayarda ya da fakülte sunucusunda çalışan model (Ollama, OpenAI uyumlu sunucu).
 *   api   : bulut API (Anthropic). Anahtarı kullanıcı kendisi girer; anahtar yalnız bu
 *           tarayıcıda (localStorage) saklanır, koda ve depoya hiç yazılmaz.
 *
 * Sağlayıcı eklemek tek dosyadır:
 *   AT.qa.registerProvider('kimlik', {
 *     label, kind: 'local' | 'api', needsKey, defaultModel, defaultBaseURL?, tools: true|false,
 *     async chat({ system, messages, tools, onText, signal, model, baseURL, key })
 *       -> { text, toolInput, usage: { input, output, cacheRead, cacheWrite }, model, stop }
 *   });
 *   system   : sabit metin (önbelleğe alınabilir), messages: [{ role, content: string }],
 *   tools    : [{ name, description, parameters (JSON Schema) }] — sağlayıcı kendi biçimine çevirir.
 *
 * Modele giden bilgi: ders başlığı, hedefler, görsel listesi, o anki bölüm ve anlatım, bulunan
 * kaynak parçaları ve soru. Öğrencinin adı, cevapları, ilerlemesi ya da cihaz bilgisi gönderilmez. */
(function (AT) {
  'use strict';

  const store = {
    get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* özel pencere */ } },
    del(k) { try { localStorage.removeItem(k); } catch (e) { /* yok */ } }
  };
  const SETTINGS = 'at:qa:ayar', USAGE = 'at:qa:kullanim', KEY = (id) => 'at:qa:key:' + id;

  // 1M token başına dolar. Önbelleğe yazma girdinin ~1,25 katıdır.
  const PRICES = [
    [/^claude-opus-5-5/, { in: 4, out: 20, cacheRead: 0.2 }],
    [/^claude-sonnet-5-5/, { in: 2, out: 10, cacheRead: 0.2 }],
    [/^claude-haiku-5-5/, { in: 0.1, out: 0.5, cacheRead: 0.01 }]
  ];
  function priceOf(model) {
    const hit = PRICES.find(([re]) => re.test(model || ''));
    return hit ? hit[1] : null;
  }
  function costOf(model, u) {
    const p = priceOf(model);
    if (!p || !u) return null;
    return ((u.input || 0) * p.in + (u.output || 0) * p.out + (u.cacheRead || 0) * p.cacheRead
      + (u.cacheWrite || 0) * p.in * 1.25) / 1e6;
  }

  const providers = {};

  // ---------- Tahta aracı ----------
  const BOARD_TYPES = ['title', 'bullets', 'text', 'term', 'table', 'flow', 'compare', 'image', 'highlight', 'draw'];
  const BOARD_TOOL = {
    name: 'tahtaya_yaz',
    description: 'Cevabı tahtada göstermek için komutlar. Yalnız görsel bir anlatım cevabı gerçekten '
      + 'kolaylaştırıyorsa bir kez çağır. Metinler kısa olsun (madde başına en çok ~12 sözcük). '
      + 'Tahtada tek görsel alan vardır: image, table, flow, compare ve draw komutlarından yalnız birini kullan; '
      + 'yanına not olarak title, bullets, term ya da text eklenebilir.',
    parameters: {
      type: 'object',
      properties: {
        komutlar: {
          type: 'array', maxItems: 8,
          items: {
            type: 'object',
            properties: {
              type: { type: 'string', enum: BOARD_TYPES },
              text: { type: 'string', description: 'title, text için' },
              items: { type: 'array', items: { type: 'string' }, description: 'bullets için' },
              title: { type: 'string' },
              term: { type: 'string' }, definition: { type: 'string' },
              headers: { type: 'array', items: { type: 'string' } },
              rows: { type: 'array', items: { type: 'array', items: { type: 'string' } } },
              nodes: { type: 'array', items: { type: 'string' }, description: 'flow için' },
              columns: { type: 'array', items: { type: 'object', properties: {
                title: { type: 'string' }, items: { type: 'array', items: { type: 'string' } } } } },
              asset: { type: 'string', description: 'image için: yalnız görsel listesindeki kimlikler' },
              region: { type: 'array', items: { type: 'number' }, description: 'highlight için [x,y,g,y] 0–1 arası' },
              label: { type: 'string' },
              viewBox: { type: 'string', description: 'draw için, varsayılan "0 0 160 90"' },
              shapes: { type: 'array', items: { type: 'object', properties: {
                kind: { type: 'string', enum: ['line', 'arrow', 'rect', 'ellipse', 'text'] },
                x: { type: 'number' }, y: { type: 'number' }, w: { type: 'number' }, h: { type: 'number' },
                x1: { type: 'number' }, y1: { type: 'number' }, x2: { type: 'number' }, y2: { type: 'number' },
                cx: { type: 'number' }, cy: { type: 'number' }, rx: { type: 'number' }, ry: { type: 'number' },
                text: { type: 'string' }, color: { type: 'string', enum: ['chalk', 'accent', 'warn', 'ok'] } } } },
              kaynak: { type: 'string', description: 'draw bir kaynaktaki şekle dayanıyorsa o parçanın numarası, ör. K2' }
            },
            required: ['type']
          }
        }
      },
      required: ['komutlar']
    }
  };

  const str = (v, n = 300) => (typeof v === 'string' ? v.slice(0, n) : '');
  const strs = (a, k = 8, n = 200) => (Array.isArray(a) ? a.slice(0, k).map((x) => str(x, n)).filter(Boolean) : []);
  const num = (v) => (typeof v === 'number' && isFinite(v) ? v : 0);

  // Modelden gelen komutları doğrula: bilinmeyen alanlar atılır, görsel yalnız dersin açık
  // lisanslı görsellerinden olabilir; kaynaktan uyarlanan çizime kaynak notu eklenir.
  function cleanBoard(cmds, lesson, passages) {
    const out = [], notes = [];
    const assets = lesson.assets || {};
    let hasImage = false;
    for (const c of (Array.isArray(cmds) ? cmds : []).slice(0, 8)) {
      if (!c || !BOARD_TYPES.includes(c.type)) continue;
      switch (c.type) {
        case 'title': case 'text':
          if (str(c.text)) out.push({ type: c.type, text: str(c.text) }); break;
        case 'bullets': {
          const items = strs(c.items);
          if (items.length) out.push({ type: 'bullets', title: str(c.title, 120) || undefined, items });
          break;
        }
        case 'term':
          if (str(c.term)) out.push({ type: 'term', term: str(c.term, 120), definition: str(c.definition) }); break;
        case 'table': {
          const headers = strs(c.headers, 5, 60);
          const rows = (Array.isArray(c.rows) ? c.rows.slice(0, 8) : []).map((r) => strs(r, headers.length, 120));
          if (headers.length && rows.length) out.push({ type: 'table', title: str(c.title, 120) || undefined, headers, rows });
          break;
        }
        case 'flow': {
          const nodes = strs(c.nodes, 6, 80);
          if (nodes.length > 1) out.push({ type: 'flow', title: str(c.title, 120) || undefined, nodes });
          break;
        }
        case 'compare': {
          const columns = (Array.isArray(c.columns) ? c.columns.slice(0, 3) : [])
            .map((col, i) => ({ title: str(col && col.title, 80), items: strs(col && col.items, 6, 120), color: ['accent', 'warn', 'ok'][i] }))
            .filter((col) => col.title);
          if (columns.length > 1) out.push({ type: 'compare', title: str(c.title, 120) || undefined, columns });
          break;
        }
        case 'image': {
          const a = assets[c.asset];
          if (!a) { notes.push('Model derste olmayan bir görsel istedi; gösterilmedi.'); break; }
          if (a.open === false) { notes.push('"' + c.asset + '" açık lisanslı değil; doğrudan gösterilmez.'); break; }
          out.push({ type: 'image', asset: c.asset });
          hasImage = true;
          break;
        }
        case 'highlight': {
          const r = Array.isArray(c.region) ? c.region.slice(0, 4).map((v) => Math.max(0, Math.min(1, num(v)))) : [];
          if (hasImage && r.length === 4) out.push({ type: 'highlight', region: r, label: str(c.label, 40) || undefined });
          break;
        }
        case 'draw': {
          const shapes = (Array.isArray(c.shapes) ? c.shapes.slice(0, 40) : []).map((s) => {
            if (!s || !['line', 'arrow', 'rect', 'ellipse', 'text'].includes(s.kind)) return null;
            const o = { kind: s.kind, color: ['chalk', 'accent', 'warn', 'ok'].includes(s.color) ? s.color : 'chalk' };
            for (const k of ['x', 'y', 'w', 'h', 'x1', 'y1', 'x2', 'y2', 'cx', 'cy', 'rx', 'ry']) if (k in s) o[k] = num(s[k]);
            if (s.kind === 'text') o.text = str(s.text, 40);
            return o;
          }).filter(Boolean);
          if (!shapes.length) break;
          const vb = /^\s*-?\d+(\.\d+)?(\s+-?\d+(\.\d+)?){3}\s*$/.test(c.viewBox || '') ? c.viewBox : '0 0 160 90';
          out.push({ type: 'draw', title: str(c.title, 120) || undefined, viewBox: vb, shapes });
          const m = /K(\d+)/i.exec(c.kaynak || '');
          const p = m && passages[Number(m[1]) - 1];
          if (p) {
            out.push({ type: 'text', style: 'credit', text: (p.open ? 'Uyarlanmıştır: ' : 'Kaynaktan uyarlanmıştır (özgün şekil gösterilmez): ')
              + p.ref + (p.license ? ' · ' + p.license.split('·')[0].trim() : '') });
          } else {
            out.push({ type: 'text', style: 'credit', text: 'Şematik çizim; yapay zekâ tarafından hazırlanmıştır.' });
          }
          break;
        }
      }
    }
    return { commands: out, notes };
  }

  // ---------- İstem ----------
  // Sabit kısım: ders boyunca değişmez, bu yüzden önbelleğe alınır (her soruda yeniden ücret ödenmez).
  function systemPrompt(lesson, withTools) {
    const goals = (lesson.goals || []).map((g) => g.id + '. ' + g.title + '\n'
      + (g.subgoals || []).map((s) => '   ' + s.id + ' ' + s.text).join('\n')).join('\n');
    const assets = Object.entries(lesson.assets || {}).map(([id, a]) =>
      '- ' + id + (a.open === false ? ' (açık lisanslı değil: gösterilemez, yalnız çizimle uyarlanabilir)' : '')
      + ': ' + (a.caption || a.alt || '')).join('\n');
    const src = lesson.source || {};
    return [
      'Sen "KlinikKoç" adlı çalışma uygulamasında diş hekimliği öğrencilerine yardım eden bir öğretim asistanısın.',
      'Ders: ' + lesson.title + (lesson.subtitle ? ' — ' + lesson.subtitle : ''),
      'Ana kaynak: ' + (src.citation || '') + (src.doi ? ' doi:' + src.doi : ''),
      '',
      'Kurallar:',
      '1. Yalnız kullanıcı mesajındaki [K1], [K2]… parçalarına dayanarak cevap ver. Genel bilgini kaynak yerine koyma.',
      '2. Her bilgi cümlesinin sonuna dayandığı parçayı yaz, ör. [K2]. Parçalarda olmayan bir şey sorulursa '
        + '"Bu sorunun cevabı ders kaynaklarında yok." de ve öğrenciyi öğretim üyesine yönlendir.',
      '3. Kesinlik derecesini koru: kaynak "olabilir" diyorsa "olur" deme; kanıt düzeyini abartma.',
      '4. Sade, akademik Türkçe yaz. Kısa tut: en çok 6 cümle. Terimleri dersin kullandığı biçimde kullan.',
      '5. Hasta tedavisi için kişisel öneri verme; bu bir ders çalışma aracıdır.',
      '6. Not verme ya da öğrenciyi değerlendirme.',
      withTools
        ? '7. Tahtada göstermek cevabı belirgin biçimde kolaylaştırıyorsa, metni yazdıktan sonra tahtaya_yaz aracını bir kez çağır. '
          + 'Görsel yalnız aşağıdaki listeden seçilebilir. Bir kaynaktaki şekli yeniden çiziyorsan "kaynak" alanına parça numarasını yaz.'
        : '7. Cevabını yalnız şu JSON biçiminde ver, başka hiçbir şey yazma: '
          + '{"cevap": "metin [K1]…", "tahta": [ {"type":"bullets","items":["…"]} ]}. Tahta gerekmezse "tahta": [].',
      '',
      'Öğrenme hedefleri:', goals,
      '',
      'Tahtada gösterilebilecek görseller:', assets || '(yok)'
    ].join('\n');
  }

  // Değişen kısım: o anki bölüm, bulunan parçalar ve soru.
  function userPrompt(question, ctx, passages) {
    const blocks = passages.map((p, i) => '[K' + (i + 1) + '] ' + (p.kind === 'kaynak' ? 'Kaynak' : 'Ders anlatımı')
      + ' · ' + (p.ref || p.title) + (p.license ? ' · lisans: ' + p.license.split('·')[0].trim() : '')
      + (p.open ? '' : ' · açık lisanslı değil') + '\n' + p.text);
    return [
      'Öğrencinin şu an dinlediği bölüm: ' + (ctx.sectionTitle || ''),
      ctx.narration ? 'Son anlatım: ' + ctx.narration : '',
      '',
      'Kaynak parçaları:',
      blocks.join('\n\n') || '(ilgili parça bulunamadı)',
      '',
      'Öğrencinin sorusu: ' + question
    ].filter((x) => x !== '').join('\n');
  }

  // JSON yedeği: araç çağrısı desteklemeyen modeller için. Metindeki ilk { … } bloğu okunur.
  function parseJsonAnswer(text) {
    const s = text.indexOf('{'), e = text.lastIndexOf('}');
    if (s < 0 || e <= s) return { text, board: [] };
    try {
      const o = JSON.parse(text.slice(s, e + 1));
      return { text: str(o.cevap, 4000) || text, board: Array.isArray(o.tahta) ? o.tahta : [] };
    } catch (err) { return { text, board: [] }; }
  }

  // ---------- Ayarlar ----------
  function settings() {
    return Object.assign({ mode: 'none', provider: { local: 'ollama', api: 'anthropic' }, models: {}, baseURLs: {}, tools: {} },
      (AT.config && AT.config.qa && AT.config.qa.defaults) || {}, store.get(SETTINGS, {}));
  }

  const qa = {
    PRICES, costOf, providers, BOARD_TOOL, cleanBoard, systemPrompt, userPrompt, parseJsonAnswer,

    registerProvider(id, def) { providers[id] = Object.assign({ id }, def); },

    settings,
    saveSettings(patch) { store.set(SETTINGS, Object.assign(settings(), patch)); },
    get mode() { return settings().mode; },

    // O anki kipin sağlayıcısı ve ayarları.
    current() {
      const s = settings();
      if (s.mode === 'none') return null;
      const id = s.provider[s.mode];
      const p = providers[id];
      if (!p) return null;
      return {
        provider: p,
        model: s.models[id] || p.defaultModel,
        baseURL: s.baseURLs[id] || p.defaultBaseURL || '',
        tools: id in s.tools ? !!s.tools[id] : p.tools !== false
      };
    },

    // Anahtar yalnız bu tarayıcıda saklanır.
    getKey(id) { return store.get(KEY(id), ''); },
    setKey(id, key) { if (key) store.set(KEY(id), String(key).trim()); else store.del(KEY(id)); },

    usage() { return store.get(USAGE, { questions: 0, input: 0, output: 0, cacheRead: 0, cacheWrite: 0, cost: 0 }); },
    resetUsage() { store.del(USAGE); },
    _addUsage(u, cost) {
      const t = this.usage();
      t.questions++;
      for (const k of ['input', 'output', 'cacheRead', 'cacheWrite']) t[k] += u[k] || 0;
      t.cost += cost || 0;
      store.set(USAGE, t);
    },

    // Model kullanmadan: ders ve kaynak dizininde ara.
    async search(question, ctx) {
      const retriever = await ctx.retriever;
      return retriever.search(question, { limit: 4 });
    },

    // Soruyu sor. ctx = { lesson, retriever (Promise), sectionTitle, narration, history: [{q, a}] }
    // Dönüş: { text, board: { commands, notes }, passages, usage, cost, model, ms, mode }
    async ask(question, ctx, opts = {}) {
      const t0 = performance.now();
      const passages = await this.search(question, ctx);
      const cur = opts.override || this.current();
      if (!cur) return { mode: 'none', text: '', passages, board: { commands: [], notes: [] }, ms: performance.now() - t0 };

      const p = cur.provider;
      const key = p.needsKey ? this.getKey(p.id) : '';
      if (p.needsKey && !key) throw new Error('Bu sağlayıcı için API anahtarı girilmemiş (Ayarlar → Soru-cevap).');

      const messages = [];
      for (const h of (ctx.history || []).slice(-4)) {
        messages.push({ role: 'user', content: h.q }, { role: 'assistant', content: h.a });
      }
      messages.push({ role: 'user', content: userPrompt(question, ctx, passages) });

      const res = await p.chat({
        system: systemPrompt(ctx.lesson, cur.tools),
        messages,
        tools: cur.tools ? [BOARD_TOOL] : [],
        onText: cur.tools ? opts.onText : null,
        signal: opts.signal,
        model: cur.model, baseURL: cur.baseURL, key
      });

      let text = res.text || '', raw = res.toolInput ? res.toolInput.komutlar : [];
      if (!cur.tools) { const j = parseJsonAnswer(text); text = j.text; raw = j.board; }
      const usage = res.usage || {};
      const cost = costOf(res.model || cur.model, usage);
      if (!opts.noTotals) this._addUsage(usage, cost);
      return {
        mode: p.kind, provider: p.id, model: res.model || cur.model, stop: res.stop,
        text: text.trim(), board: cleanBoard(raw, ctx.lesson, passages), passages,
        usage, cost, ms: performance.now() - t0
      };
    }
  };

  AT.qa = qa;
})(window.AT = window.AT || {});
