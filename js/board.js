/* Tahta: ders dosyasındaki komutları ekrana çizer.
 * Komutlar iki bölgeye düşer: görsel alan (image, video, draw, table, flow, compare, tree)
 * ve not alanı (bullets, point, text, term). title üst başlığı yazar. */
(function (AT) {
  'use strict';

  const SVG_NS = 'http://www.w3.org/2000/svg';

  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function svg(tag, attrs) {
    const n = document.createElementNS(SVG_NS, tag);
    for (const k in attrs) if (attrs[k] != null) n.setAttribute(k, attrs[k]);
    return n;
  }

  // **kalın** ve _italik_ dışında biçim desteklenmez; metin her zaman textContent olarak kalır.
  function rich(parent, text) {
    const parts = String(text).split(/(\*\*[^*]+\*\*|_[^_]+_)/g);
    for (const p of parts) {
      if (!p) continue;
      if (p.startsWith('**') && p.endsWith('**')) parent.appendChild(el('strong', null, p.slice(2, -2)));
      else if (p.length > 2 && p.startsWith('_') && p.endsWith('_')) parent.appendChild(el('em', null, p.slice(1, -1)));
      else parent.appendChild(document.createTextNode(p));
    }
    return parent;
  }

  // Ortak video denetimi: oynat, duraklat, git(sn), bitti (söz verilir), durum ('bekliyor'|'oynuyor'|'durdu'|'bitti'|'hata').
  function denetim() {
    let coz;
    const d = { durum: 'bekliyor', hata: null, bitti: null, kapat() {} };
    d.bitti = new Promise((r) => { coz = r; });
    d._bitir = (durum, hata) => { if (d.durum === 'bitti' || d.durum === 'hata') return; d.durum = durum || 'bitti'; d.hata = hata || null; coz(d.durum); };
    return d;
  }

  // Tarayıcı kendiliğinden oynatmayı engellerse videonun üstünde büyük ▶ (dokununca oynar).
  function oynatDugmesi(sahne, d, oynat) {
    const b = el('button', 'video-oynat');
    b.type = 'button';
    b.hidden = true;
    b.setAttribute('aria-label', 'Videoyu oynat');
    b.innerHTML = '<svg viewBox="0 0 24 24"><path d="M8 5l11 7-11 7z"/></svg>';
    b.addEventListener('click', () => { b.hidden = true; d.dugmeAcik = false; oynat(); });
    sahne.appendChild(b);
    d.dugmeAcik = false;
    d.dugmeGoster = () => { if (d.durum === 'oynuyor' || d.durum === 'bitti' || d.durum === 'hata') return; b.hidden = false; d.dugmeAcik = true; };
    d.dugmeGizle = () => { b.hidden = true; d.dugmeAcik = false; };
  }

  function dosyaOynatici(sahne, url, bas, bit, c) {
    const d = denetim();
    const v = el('video');
    v.controls = true;
    v.playsInline = true;
    v.preload = 'auto';
    v.muted = !!c.sessiz;
    v.src = url;
    sahne.appendChild(v);
    let hazir = false;
    v.addEventListener('loadedmetadata', () => { hazir = true; if (bas) v.currentTime = bas; });
    v.addEventListener('playing', () => { if (d.durum !== 'bitti') d.durum = 'oynuyor'; d.engellendi = false; d.dugmeGizle(); });
    v.addEventListener('pause', () => { if (d.durum === 'oynuyor') d.durum = 'durdu'; });
    v.addEventListener('ended', () => d._bitir('bitti'));
    v.addEventListener('timeupdate', () => { if (bit != null && v.currentTime >= bit) { v.pause(); d._bitir('bitti'); } });
    v.addEventListener('error', () => {
      sahne.appendChild(el('p', 'video-hata', 'Video açılamadı: ' + decodeURIComponent(url.split('/').pop())));
      d._bitir('hata', 'açılamadı');
      d.dugmeGizle();
    });
    d.oynat = () => {
      if (d.durum === 'bitti' && bit != null) return;
      const p = v.play();
      if (p && p.catch) p.catch((e) => {
        // Tarayıcı engelledi: büyük ▶ gösterilir; durum 'bekliyor' kalır ki anlatım beklesin ve Claude'a söylensin.
        if (e && e.name === 'NotAllowedError' && d.durum === 'bekliyor') { d.engellendi = true; d.dugmeGoster(); } else if (d.durum !== 'bekliyor') d.durum = 'durdu';
      });
    };
    d.duraklat = () => v.pause();
    d.git = (sn) => { const t = Math.max(0, sn); if (hazir) v.currentTime = t; else v.addEventListener('loadedmetadata', () => { v.currentTime = t; }, { once: true }); if (d.durum === 'bitti') d.durum = 'durdu'; };
    d.kapat = () => { v.pause(); v.removeAttribute('src'); v.load(); };
    d.el = v;
    oynatDugmesi(sahne, d, () => { const p = v.play(); if (p && p.catch) p.catch(() => {}); });
    return d;
  }

  // YouTube bağlantısından kimlik: youtu.be/ID, watch?v=ID, embed/ID, shorts/ID ya da yalnız ID. t=90 başlangıçtır.
  function youtubeKimligi(x) {
    const s = String(x || '').trim();
    if (/^[\w-]{11}$/.test(s)) return { id: s };
    try {
      const u = new URL(s);
      let id = u.searchParams.get('v');
      if (!id) { const m = u.pathname.match(/(?:embed|shorts|live|v)\/([\w-]{11})/) || (u.hostname.endsWith('youtu.be') && u.pathname.match(/^\/([\w-]{11})/)); if (m) id = m[1]; }
      const t = u.searchParams.get('t') || u.searchParams.get('start');
      const sn = t ? (/^\d+$/.test(t) ? Number(t) : ((t.match(/(\d+)h/) || [0, 0])[1] * 3600 + (t.match(/(\d+)m/) || [0, 0])[1] * 60 + Number((t.match(/(\d+)s/) || [0, 0])[1]))) : 0;
      return id && /^[\w-]{11}$/.test(id) ? { id, t: sn } : null;
    } catch (e) { return null; }
  }
  AT.youtubeKimligi = youtubeKimligi;

  function youtubeOynatici(sahne, kaynak, bas, bit, c) {
    const d = denetim();
    const k = youtubeKimligi(kaynak);
    if (!k) { sahne.appendChild(el('p', 'video-hata', 'YouTube bağlantısı anlaşılamadı.')); d._bitir('hata', 'bağlantı'); return Object.assign(d, { oynat() {}, duraklat() {}, git() {} }); }
    if (!bas && k.t) bas = k.t;
    if (navigator.onLine === false) {
      sahne.appendChild(el('p', 'video-hata', 'YouTube videosu internet ister; bu bilgisayar şu an çevrimdışı.'));
      d._bitir('hata', 'çevrimdışı');
      return Object.assign(d, { oynat() {}, duraklat() {}, git() {} });
    }
    const q = new URLSearchParams({ enablejsapi: '1', rel: '0', playsinline: '1', modestbranding: '1', origin: location.origin });
    if (bas) q.set('start', String(Math.floor(bas)));
    if (bit != null) q.set('end', String(Math.ceil(bit)));
    if (c.oynat !== false) q.set('autoplay', '1');
    if (c.sessiz) q.set('mute', '1');
    const f = el('iframe');
    f.src = 'https://www.youtube-nocookie.com/embed/' + k.id + '?' + q.toString();
    f.title = c.caption || 'YouTube videosu';
    f.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen';
    f.allowFullscreen = true;
    f.referrerPolicy = 'strict-origin-when-cross-origin';
    sahne.appendChild(f);
    const gonder = (func, args) => { try { f.contentWindow.postMessage(JSON.stringify({ event: 'command', func, args: args || [] }), '*'); } catch (e) { /* yok */ } };
    let haber = false;
    const dinle = (e) => {
      if (e.source !== f.contentWindow) return;
      let m;
      try { m = typeof e.data === 'string' ? JSON.parse(e.data) : e.data; } catch (_) { return; }
      const st = m && (m.event === 'onStateChange' ? m.info : (m.info && m.info.playerState));
      if (st == null) return;
      haber = true;
      if (st === 1) { d.durum = 'oynuyor'; d.dugmeGizle(); }
      else if (st === 2 && d.durum === 'oynuyor') d.durum = 'durdu';
      else if (st === 0) d._bitir('bitti');
    };
    window.addEventListener('message', dinle);
    f.addEventListener('load', () => {
      // Oynatıcıdan durum haberi iste (bitti mi, oynuyor mu).
      try { f.contentWindow.postMessage(JSON.stringify({ event: 'listening', id: k.id, channel: 'widget' }), '*'); } catch (e) { /* yok */ }
      gonder('addEventListener', ['onStateChange']);
    });
    // 20 sn içinde oynatıcıdan hiç haber gelmezse (internet yok, video kapalı) bekleme bırakılır.
    setTimeout(() => { if (!haber) d._bitir('hata', 'yanıt yok'); }, 20000);
    d.oynat = () => gonder('playVideo');
    d.duraklat = () => gonder('pauseVideo');
    d.git = (sn) => gonder('seekTo', [Math.max(0, sn), true]);
    d.kapat = () => { gonder('pauseVideo'); window.removeEventListener('message', dinle); };
    d.el = f;
    // Dokunuştan sonra oynatıcıya yeniden "oynat" denir; olmazsa düğme kalkar ve YouTube'un kendi ▶'ı kullanılır.
    oynatDugmesi(sahne, d, () => gonder('playVideo'));
    return d;
  }

  class Board {
    constructor(root, lesson) {
      this.root = root;
      this.lesson = lesson;
      this.header = root.querySelector('.board-title');
      this.visual = root.querySelector('.board-visual');
      this.notes = root.querySelector('.board-notes');
      this.clear();
    }

    clear() {
      this._videoBirak();
      this.header.replaceChildren();
      this.visual.replaceChildren();
      this.notes.replaceChildren();
      this.figure = null;
      this.lastList = null;
      this._layout();
    }

    _layout() {
      const hasVisual = this.visual.childElementCount > 0;
      const hasNotes = this.notes.childElementCount > 0;
      this.root.dataset.layout = hasVisual && hasNotes ? 'split' : hasVisual ? 'visual' : 'notes';
    }

    // instant=true: geçmiş adımları yeniden kurarken animasyon yapılmaz.
    run(cmd, instant) {
      const fn = this['cmd_' + cmd.type];
      if (!fn) { console.warn('Bilinmeyen tahta komutu:', cmd.type); return; }
      const node = fn.call(this, cmd, instant);
      if (node && !instant) {
        node.classList.add('enter');
        node.addEventListener('animationend', () => node.classList.remove('enter'), { once: true });
      }
      this._layout();
    }

    _setVisual(node) {
      this._videoBirak();
      this.visual.replaceChildren(node);
      this.figure = null;
    }

    _videoBirak() {
      if (this.video) { try { this.video.duraklat(); } catch (e) { /* yok */ } this.video.kapat(); }
      this.video = null;
    }

    // ---------- Video ----------
    // { type: "video", video: "<ders videosu kimliği>" | src: "videolar/klip.mp4" | youtube: "<bağlantı ya da kimlik>",
    //   baslangic?: sn, bitis?: sn, oynat?: true, sessiz?: false, caption? }
    // Klasördeki video internetsiz oynar; YouTube internet ister. this.video denetim nesnesidir.
    cmd_video(c) {
      const a = c.video ? ((this.lesson.videos || {})[c.video] || (this.lesson.assets || {})[c.video]) : null;
      if (c.video && !a) { console.warn('Video tanımlı değil:', c.video); return null; }
      const yt = c.youtube || (a && a.youtube);
      const src = c.src || (a && a.src);
      const bas = Math.max(0, Number(c.baslangic != null ? c.baslangic : (a && a.baslangic)) || 0);
      const bitRaw = c.bitis != null ? c.bitis : (a && a.bitis);
      const bit = bitRaw != null && Number(bitRaw) > bas ? Number(bitRaw) : null;
      const fig = el('figure', 'board-figure board-video');
      const sahne = el('div', 'video-stage');
      fig.appendChild(sahne);
      const capText = c.caption || (a && (a.caption || a.baslik));
      const kredi = c.credit || (a && a.credit);
      if (capText || kredi) {
        const cap = el('figcaption');
        if (capText) rich(cap, capText);
        if (kredi) cap.appendChild(el('span', 'credit', kredi));
        fig.appendChild(cap);
      }
      const v = yt ? youtubeOynatici(sahne, yt, bas, bit, c) : (src ? dosyaOynatici(sahne, AT.lessonUrl(this.lesson, src), bas, bit, c) : null);
      if (!v) { sahne.appendChild(el('p', 'video-hata', 'Video bulunamadı.')); return fig; }
      this._setVisual(fig);
      this.video = v;
      if (c.oynat !== false) v.oynat();
      return fig;
    }

    // { type: "video_kontrol", eylem: "oynat" | "duraklat" | "git", saniye? }
    cmd_video_kontrol(c) {
      if (!this.video) return null;
      if (c.eylem === 'duraklat') this.video.duraklat();
      else if (c.eylem === 'git') { this.video.git(Number(c.saniye) || 0); if (c.oynat !== false) this.video.oynat(); }
      else this.video.oynat();
      return null;
    }

    cmd_clear() { this.clear(); }

    cmd_title(c) {
      this.header.replaceChildren();
      const h = rich(el('h2'), c.text);
      this.header.appendChild(h);
      if (c.subtitle) this.header.appendChild(rich(el('p', 'subtitle'), c.subtitle));
      return this.header;
    }

    cmd_bullets(c, instant) {
      const box = el('div', 'note-block');
      if (c.title) box.appendChild(rich(el('h3'), c.title));
      const ul = el('ul', 'bullets');
      box.appendChild(ul);
      this.notes.appendChild(box);
      this.lastList = ul;
      for (const it of c.items) this._addPoint(it, instant);
      return box;
    }

    cmd_point(c, instant) {
      if (!this.lastList) this.cmd_bullets({ items: [] }, true);
      return this._addPoint(c.text, instant);
    }

    _addPoint(text, instant) {
      const li = rich(el('li'), text);
      this.lastList.appendChild(li);
      if (!instant) { li.classList.add('enter'); }
      return null;
    }

    cmd_text(c) {
      const p = rich(el('div', 'note-text ' + (c.style || 'note')), c.text);
      this.notes.appendChild(p);
      return p;
    }

    cmd_term(c) {
      const d = el('div', 'note-term');
      d.appendChild(rich(el('dt'), c.term));
      d.appendChild(rich(el('dd'), c.definition));
      this.notes.appendChild(d);
      return d;
    }

    cmd_image(c) {
      const a = (this.lesson.assets || {})[c.asset];
      if (!a) { console.warn('Görsel tanımlı değil:', c.asset); return null; }
      const fig = el('figure', 'board-figure');
      const stage = el('div', 'figure-stage');
      const frame = el('div', 'figure-frame');
      const inner = el('div', 'figure-inner');
      const img = el('img');
      img.alt = a.alt || '';
      img.draggable = false;
      const overlay = svg('svg', { class: 'figure-overlay', viewBox: '0 0 1000 1000', preserveAspectRatio: 'none' });
      inner.append(img, overlay);
      frame.appendChild(inner);
      stage.appendChild(frame);
      fig.appendChild(stage);
      // Çerçeveyi görselin en-boy oranında, alana sığacak en büyük boyutta tut;
      // böylece vurgu koordinatları (0–1) görselle birebir örtüşür.
      const fit = () => {
        const ar = img.naturalWidth && img.naturalHeight ? img.naturalWidth / img.naturalHeight : 4 / 3;
        const w = stage.clientWidth, h = stage.clientHeight;
        if (!w || !h) return;
        const fw = Math.min(w, h * ar);
        frame.style.width = fw + 'px';
        frame.style.height = (fw / ar) + 'px';
      };
      img.addEventListener('load', fit);
      if (a.makaleden) {
        // Şekil pakette yok; öğrencinin kendi makale PDF'inden çıkarılır (tools/makale_sekil.py).
        // Makale henüz eklenmediyse boş kare yerine nereye bakılacağını söyle.
        img.addEventListener('error', () => {
          const m = a.makaleden;
          const not = el('div', 'figure-missing');
          not.appendChild(el('strong', null, (c.caption || a.caption || 'Şekil').split('.')[0] + ' makalede'));
          not.appendChild(el('span', null, 'Makalenin ' + (m.sayfa ? m.sayfa + '. sayfasına' : 'ilgili şekline') +
            ' bakın. Makaleyi "Ders paketleri ve makaleler" sayfasından bu derse eklerseniz şekil burada görünür.'));
          frame.replaceWith(not);
          this.figure = null;
        }, { once: true });
      }
      if ('ResizeObserver' in window) new ResizeObserver(fit).observe(stage);
      else window.addEventListener('resize', fit);
      img.src = AT.lessonUrl(this.lesson, a.src);
      const capText = c.caption || a.caption;
      if (capText || a.credit) {
        const cap = el('figcaption');
        if (capText) rich(cap, capText);
        if (a.credit) cap.appendChild(el('span', 'credit', a.credit));
        fig.appendChild(cap);
      }
      this._setVisual(fig);
      this.figure = { fig, inner, overlay };
      // Tam ekran görüntüleme: dokununca büyür.
      frame.addEventListener('click', () => fig.classList.toggle('expanded'));
      return fig;
    }

    _region(r) {
      return r.map((v) => v * 1000);
    }

    cmd_highlight(c, instant) {
      if (!this.figure) return null;
      const [x, y, w, h] = this._region(c.region);
      const g = svg('g', { class: 'hl ' + (c.color || 'accent'), 'data-id': c.id || '' });
      const shape = c.shape === 'ellipse'
        ? svg('ellipse', { cx: x + w / 2, cy: y + h / 2, rx: w / 2, ry: h / 2 })
        : svg('rect', { x, y, width: w, height: h, rx: 6 });
      shape.setAttribute('vector-effect', 'non-scaling-stroke');
      g.appendChild(shape);
      this.figure.overlay.appendChild(g);
      if (c.label) {
        const lab = el('span', 'hl-label ' + (c.color || 'accent'), c.label);
        lab.style.left = (c.region[0] * 100) + '%';
        // Bölge görselin altına yakınsa etiketi üstüne yaz, yoksa altına.
        const below = c.region[1] + c.region[3];
        if (below > 0.88) { lab.style.top = (c.region[1] * 100) + '%'; lab.classList.add('above'); }
        else lab.style.top = (below * 100) + '%';
        lab.dataset.id = c.id || '';
        this.figure.inner.appendChild(lab);
      }
      if (!instant) g.classList.add('draw-in');
      return null;
    }

    cmd_unhighlight(c) {
      if (!this.figure) return null;
      const sel = c.id ? `[data-id="${CSS.escape(c.id)}"]` : '.hl, .hl-label';
      this.figure.inner.querySelectorAll(sel).forEach((n) => n.remove());
      return null;
    }

    cmd_zoom(c) {
      if (!this.figure) return null;
      const [x, y, w, h] = c.region;
      const s = Math.min(4, 1 / Math.max(w, h));
      const cx = x + w / 2, cy = y + h / 2;
      // Bölgenin merkezini çerçevenin merkezine getir.
      this.figure.inner.style.transform =
        `translate(${(0.5 - cx) * 100 * s}%, ${(0.5 - cy) * 100 * s}%) scale(${s})`;
      this.figure.fig.classList.add('zoomed');
      return null;
    }

    cmd_unzoom() {
      if (!this.figure) return null;
      this.figure.inner.style.transform = '';
      this.figure.fig.classList.remove('zoomed');
      return null;
    }

    cmd_table(c) {
      const wrap = el('div', 'board-table');
      if (c.title) wrap.appendChild(rich(el('h3'), c.title));
      const t = el('table');
      const thead = el('thead');
      const hr = el('tr');
      for (const h of c.headers) hr.appendChild(rich(el('th'), h));
      thead.appendChild(hr);
      const tb = el('tbody');
      for (const row of c.rows) {
        const tr = el('tr');
        for (const cell of row) tr.appendChild(rich(el('td'), cell));
        tb.appendChild(tr);
      }
      t.append(thead, tb);
      wrap.appendChild(t);
      if (c.caption) wrap.appendChild(rich(el('p', 'table-caption'), c.caption));
      this._setVisual(wrap);
      return wrap;
    }

    cmd_flow(c) {
      const wrap = el('div', 'board-flow ' + (c.direction === 'column' ? 'column' : 'row'));
      if (c.title) wrap.appendChild(rich(el('h3'), c.title));
      const line = el('div', 'flow-line');
      c.nodes.forEach((n, i) => {
        if (i > 0) line.appendChild(el('span', 'flow-arrow', c.direction === 'column' ? '↓' : '→'));
        const node = rich(el('div', 'flow-node'), n);
        node.style.animationDelay = (i * 0.35) + 's';
        line.appendChild(node);
      });
      wrap.appendChild(line);
      this._setVisual(wrap);
      return wrap;
    }

    cmd_compare(c) {
      const wrap = el('div', 'board-compare');
      if (c.title) wrap.appendChild(rich(el('h3'), c.title));
      const cols = el('div', 'compare-cols');
      let gorsel = false;
      for (const col of c.columns) {
        const box = el('div', 'compare-col ' + (col.color || ''));
        box.appendChild(rich(el('h4'), col.title));
        // Görsel karşılaştırma: sütunda asset varsa fotoğraf sütunun başında gösterilir (ör. NG ve PHG yan yana).
        const a = col.asset ? (this.lesson.assets || {})[col.asset] : null;
        if (col.asset && !a) console.warn('Görsel tanımlı değil:', col.asset);
        if (a) {
          gorsel = true;
          const fig = el('figure', 'compare-figure');
          const img = el('img');
          img.alt = a.alt || '';
          img.draggable = false;
          img.src = AT.lessonUrl(this.lesson, a.src);
          fig.appendChild(img);
          if (col.caption || a.credit) {
            const cap = el('figcaption');
            if (col.caption) rich(cap, col.caption);
            if (a.credit) cap.appendChild(el('span', 'credit', a.credit));
            fig.appendChild(cap);
          }
          fig.addEventListener('click', () => fig.classList.toggle('expanded'));
          box.appendChild(fig);
        }
        if ((col.items || []).length) {
          const ul = el('ul');
          for (const it of col.items) ul.appendChild(rich(el('li'), it));
          box.appendChild(ul);
        }
        cols.appendChild(box);
      }
      if (gorsel) wrap.classList.add('gorselli');
      wrap.appendChild(cols);
      this._setVisual(wrap);
      return wrap;
    }

    // Klinik karar ağacı. nodes düz listedir: {id, text, parent?, edge?, state?: ok|warn|accent|danger|dim}.
    // path (kimlik listesi) seçilen yolu vurgular. Aynı başlıklı ağaç yeniden gönderilirse yalnız yeni düğümler canlanır.
    cmd_tree(c, instant) {
      const nodes = (c.nodes || []).filter((n) => n && n.id != null);
      const byParent = new Map();
      const ids = new Set(nodes.map((n) => String(n.id)));
      for (const n of nodes) {
        const p = n.parent != null && ids.has(String(n.parent)) ? String(n.parent) : '';
        if (!byParent.has(p)) byParent.set(p, []);
        byParent.get(p).push(n);
      }
      const path = new Set([].concat(c.path || []).map(String));
      const key = 'tree|' + (c.title || '');
      const prev = this.visual.querySelector('.board-tree');
      const old = prev && prev.dataset.key === key ? prev._ids || new Set() : null;
      const wrap = el('div', 'board-tree');
      wrap.dataset.key = key;
      wrap._ids = ids;
      if (c.title) wrap.appendChild(rich(el('h3'), c.title));
      let delay = 0;
      const build = (pid, depth) => {
        const kids = byParent.get(pid) || [];
        if (!kids.length || depth > 12) return null;
        const ul = el('ul', 'tree-level');
        for (const n of kids) {
          const li = el('li', 'tree-item' + (path.has(String(n.id)) ? ' on-path' : ''));
          if (n.edge) li.appendChild(rich(el('span', 'tree-edge'), n.edge));
          const box = rich(el('div', 'tree-node ' + (n.state || '')), n.text || '');
          box.dataset.id = n.id;
          if (!instant && !(old && old.has(String(n.id)))) {
            box.classList.add('tree-new');
            box.style.animationDelay = delay + 's';
            delay += 0.25;
          }
          li.appendChild(box);
          const sub = build(String(n.id), depth + 1);
          if (sub) li.appendChild(sub);
          ul.appendChild(li);
        }
        return ul;
      };
      const root = build('', 0);
      if (root) { root.classList.add('tree-root'); wrap.appendChild(root); }
      if (c.caption) wrap.appendChild(rich(el('p', 'table-caption'), c.caption));
      this._setVisual(wrap);
      // Uzun ağaçta son eklenen düğüm görünsün.
      requestAnimationFrame(() => { const v = this.visual; v.scrollTop = v.scrollHeight; wrap.scrollTop = wrap.scrollHeight; });
      return old ? null : wrap;
    }

    // Basit vektör çizimi; şekiller sırayla "elle çiziliyormuş" gibi belirir.
    cmd_draw(c, instant) {
      const wrap = el('div', 'board-draw');
      if (c.title) wrap.appendChild(rich(el('h3'), c.title));
      const s = svg('svg', { viewBox: c.viewBox || '0 0 160 90', class: 'draw-svg' });
      const defs = svg('defs', {});
      const marker = svg('marker', { id: 'ok-ucu', viewBox: '0 0 10 10', refX: 8, refY: 5, markerWidth: 6, markerHeight: 6, orient: 'auto-start-reverse' });
      marker.appendChild(svg('path', { d: 'M0,0 L10,5 L0,10 z', fill: 'context-stroke' }));
      defs.appendChild(marker);
      s.appendChild(defs);
      wrap.appendChild(s);
      // Anatomik şablon: aynı şablon zaten tahtadaysa yeniden canlandırma, yalnız yeni etiketler belirsin.
      let tplInstant = instant;
      if (c.template && AT.anatomi) {
        const key = [c.template, c.variant || '', c.probe ? 1 : 0].join('|');
        const prev = this.visual.querySelector('.board-draw');
        if (prev && prev.dataset.tpl === key) tplInstant = true;
        wrap.dataset.tpl = key;
        const old = prev && prev.dataset.tpl === key && !instant ? prev._etiketler || new Set() : null;
        AT.anatomi.ciz(s, c, tplInstant, old);
        wrap._etiketler = new Set([].concat(c.labels || []).map((l) => (typeof l === 'string' ? l : l.part)));
        wrap.classList.add('anatomik');
      }
      this._setVisual(wrap);

      let delay = 0;
      for (const sh of c.shapes || []) {
        const node = this._shape(sh);
        if (!node) continue;
        s.appendChild(node);
        if (!instant) {
          node.style.animationDelay = delay + 's';
          node.classList.add(sh.kind === 'text' ? 'fade-in' : 'stroke-in');
          delay += sh.kind === 'text' ? 0.2 : 0.5;
        }
      }
      return wrap;
    }

    _shape(sh) {
      const cls = 'shape ' + (sh.color || 'chalk') + (sh.dashed ? ' dashed' : '') + (sh.fill ? ' filled' : '');
      switch (sh.kind) {
        case 'line':
        case 'arrow':
          return svg('line', {
            x1: sh.x1, y1: sh.y1, x2: sh.x2, y2: sh.y2, class: cls, pathLength: 1,
            'marker-end': sh.kind === 'arrow' ? 'url(#ok-ucu)' : null
          });
        case 'rect':
          return svg('rect', { x: sh.x, y: sh.y, width: sh.w, height: sh.h, rx: sh.r || 0, class: cls, pathLength: 1 });
        case 'ellipse':
          return svg('ellipse', { cx: sh.cx, cy: sh.cy, rx: sh.rx, ry: sh.ry || sh.rx, class: cls, pathLength: 1 });
        case 'path':
          return svg('path', { d: sh.d, class: cls, pathLength: 1 });
        case 'text': {
          const t = svg('text', { x: sh.x, y: sh.y, class: 'shape-text ' + (sh.color || 'chalk'), 'text-anchor': sh.anchor || 'middle', 'font-size': sh.size || 5 });
          t.textContent = sh.text;
          return t;
        }
        default:
          console.warn('Bilinmeyen şekil:', sh.kind);
          return null;
      }
    }
  }

  AT.Board = Board;
})(window.AT = window.AT || {});
