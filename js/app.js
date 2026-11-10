/* Arayüz: ders listesi, ders ekranı, sorular, çekmece (içindekiler / hedefler / ayarlar). */
(function (AT) {
  'use strict';
  { const sv = document.getElementById('surum'); if (sv && AT.config && AT.config.version) sv.textContent = 'Sürüm ' + AT.config.version; }

  const $ = (s, r = document) => r.querySelector(s);
  const home = $('#home');
  const lessonScreen = $('#lesson');
  const boardEl = $('#board');
  const qEl = $('#question');
  const captionEl = $('#caption');
  const drawer = $('#drawer');
  let player = null;
  let catalog = [];
  let qaState = null;
  let currentCase = null;

  function el(tag, cls, text) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }

  function toast(msg, ms = 3500) {
    const t = $('#toast');
    t.textContent = msg;
    t.hidden = false;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => { t.hidden = true; }, ms);
  }

  // ---------- Ders listesi ----------
  async function showHome() {
    if (player) { player.destroy(); player = null; }
    lessonScreen.hidden = true;
    home.hidden = false;
    document.title = 'KlinikKoç';
    if (location.hash) history.replaceState(null, '', location.pathname);
    const box = $('#catalog');
    if (!catalog.length) {
      try { catalog = (await AT.loadCatalog()).lessons || []; }
      catch (e) { box.textContent = 'Ders listesi yüklenemedi: ' + e.message; return; }
    }
    box.replaceChildren();
    renderTodayReview();
    if (!catalog.length) {
      // Program derssiz gelir: dersler öğretmenin verdiği ders paketleriyle eklenir.
      const bos = el('div', 'empty-home');
      bos.appendChild(el('h2', null, 'Henüz ders yok'));
      bos.appendChild(el('p', null, 'Öğretmeninizden aldığınız ders paketini (.zip) ekleyin; ders bu listede belirir ve makaleleri kendiliğinden aranır.'));
      const dug = el('div', 'empty-actions');
      const ekle = el('a', 'btn primary', 'Ders paketi ekle');
      ekle.href = 'makaleler.html#paketKutu';
      const kil = el('a', 'btn', 'Kılavuzu okuyun');
      kil.href = 'kilavuz.html';
      dug.append(ekle, kil);
      bos.appendChild(dug);
      box.appendChild(bos);
      return;
    }
    for (const entry of catalog) {
      const card = el('button', 'lesson-card');
      card.appendChild(el('h2', null, entry.title));
      if (entry.subtitle) card.appendChild(el('p', 'sub', entry.subtitle));
      const meta = el('p', 'meta');
      meta.textContent = [entry.level, entry.estimatedMinutes ? '~' + entry.estimatedMinutes + ' dk' : null].filter(Boolean).join(' · ');
      card.appendChild(meta);
      const p = AT.prefs.get('progress-hint:' + entry.id);
      if (p) card.appendChild(el('p', 'resume', 'Kaldığınız yer: ' + p));
      const due = new AT.Progress(entry.id).dueSteps().filter((x) => !x.startsWith('vaka:')).length;
      if (due) card.appendChild(el('p', 'resume due', 'Tekrar zamanı gelen ' + due + ' soru var'));
      card.addEventListener('click', () => openLesson(entry));
      box.appendChild(card);
    }
  }

  // ---------- Dersler arası tekrar ----------
  // Bütün derslerin bu cihazdaki kayıtlarından tekrar zamanı gelen sorular ve vaka adımları, en eskisi önce.
  function dueAcross() {
    const out = [];
    for (const entry of catalog) {
      const pr = new AT.Progress(entry.id);
      const ids = pr.dueSteps();
      const srs = pr.data.srs || {};
      const cases = [...new Set(ids.filter((x) => x.startsWith('vaka:') && !(pr.data.answers[x] || {}).correct).map((x) => x.split(':')[1]))];
      const questions = ids.filter((x) => !x.startsWith('vaka:')).length;
      if (!questions && !cases.length) continue;
      out.push({ entry, questions, cases,
        oldest: Math.min(...ids.map((x) => srs[x].due)) });
    }
    return out.sort((a, b) => a.oldest - b.oldest);
  }
  let reviewTour = [];

  function renderTodayReview() {
    const old = $('#todayReview');
    if (old) old.remove();
    const list = dueAcross();
    if (!list.length) return;
    const nq = list.reduce((a, x) => a + x.questions, 0), nc = list.reduce((a, x) => a + x.cases.length, 0);
    const box = el('section', 'today-review');
    box.id = 'todayReview';
    box.appendChild(el('h2', null, 'Bugünkü tekrar'));
    box.appendChild(el('p', null, [nq ? nq + ' soru' : null, nc ? nc + ' vaka' : null].filter(Boolean).join(' ve ') + ', ' + list.length + ' dersten. Önce en çok bekleyenler gelir; birkaç dakika sürer, not verilmez.'));
    const ul = el('ul');
    for (const x of list) ul.appendChild(el('li', null, x.entry.title + ': ' + [x.questions ? x.questions + ' soru' : null, x.cases.length ? x.cases.length + ' vaka' : null].filter(Boolean).join(', ')));
    box.appendChild(ul);
    const go = el('button', 'btn primary', 'Tekrara başla');
    go.addEventListener('click', () => { reviewTour = list.slice(1).map((x) => x.entry.id); openLesson(list[0].entry, { review: true }); });
    box.appendChild(go);
    $('#catalog').before(box);
  }

  // Vakada zayıf kalan adımı tekrar zamanı gelmişse vakayı yeniden çözmeyi öner.
  function dueCaseCards(p) {
    // Yalnız son denemesi yetersiz kalan adımlar: doğru çözülmüş bir vakayı her gün baştan çözdürmeyelim.
    const ids = new Set(p.progress.dueSteps().filter((x) => x.startsWith('vaka:') && !(p.progress.data.answers[x] || {}).correct).map((x) => x.split(':')[1]));
    return (p.lesson._cases || []).filter((c) => ids.has(c.id));
  }

  function showCaseReviewOffer(p, cards) {
    qEl.replaceChildren();
    qEl.hidden = false;
    boardEl.classList.add('has-question');
    const card = el('div', 'q-card');
    card.appendChild(el('div', 'q-tag', 'Aralıklı tekrar · vaka'));
    card.appendChild(el('h3', 'q-prompt', 'Daha önce zorlandığın vaka adımlarının tekrar zamanı geldi.'));
    const actions = el('div', 'q-actions');
    const later = el('button', 'btn ghost', 'Sonra');
    later.addEventListener('click', () => { qEl.hidden = true; boardEl.classList.remove('has-question'); nextInTour(); });
    actions.appendChild(later);
    for (const c of cards) {
      const b = el('button', 'btn primary', 'Yeniden çöz: ' + c.baslik);
      b.addEventListener('click', () => startCase(c));
      actions.appendChild(b);
    }
    card.appendChild(actions);
    qEl.appendChild(card);
  }

  function nextInTour() {
    if (!reviewTour.length) return false;
    const id = reviewTour.shift();
    const entry = catalog.find((c) => c.id === id);
    if (!entry) return nextInTour();
    qEl.replaceChildren();
    qEl.hidden = false;
    boardEl.classList.add('has-question');
    const card = el('div', 'q-card');
    card.appendChild(el('div', 'q-tag', 'Bugünkü tekrar'));
    card.appendChild(el('h3', 'q-prompt', 'Sıradaki ders: ' + entry.title));
    const actions = el('div', 'q-actions');
    const stop = el('button', 'btn ghost', 'Bugünlük yeter');
    stop.addEventListener('click', () => { reviewTour = []; qEl.hidden = true; boardEl.classList.remove('has-question'); });
    const go = el('button', 'btn primary', 'Devam et');
    go.addEventListener('click', () => openLesson(entry, { review: true }));
    actions.append(stop, go);
    card.appendChild(actions);
    qEl.appendChild(card);
    return true;
  }

  // ---------- Ders ekranı ----------
  async function openLesson(entry, opts = {}) {
    let lesson;
    try { lesson = await AT.loadLesson(entry); }
    catch (e) { toast('Ders açılamadı: ' + e.message); return; }

    lesson._cases = await AT.loadCases(lesson);
    currentCase = null;
    $('.cases-btn').hidden = !lesson._cases.length;
    $('#caseReturn').hidden = true;
    home.hidden = true;
    lessonScreen.hidden = false;
    document.title = lesson.title + ' · KlinikKoç';
    history.replaceState(null, '', '#' + lesson.id);
    $('.lesson-name').textContent = lesson.title;
    $('.qa-btn').hidden = false;
    qaState = { retriever: null, history: [], last: null, busy: null };

    player = new AT.Player(lesson, ui);
    buildTrack();
    const last = player.progress.data.lastStep || 0;
    player.goTo(Math.min(last, player.steps.length - 1), { play: false });

    if (!player.webSpeech.hasLanguageVoice && !lesson._audioManifest && !AT.prefs.get('muted', false)) {
      // Ses listesi bazı tarayıcılarda geç gelir; kısa süre sonra yeniden bak.
      setTimeout(() => {
        if (player && !player.webSpeech.hasLanguageVoice) {
          toast('Bu tarayıcıda Türkçe ses bulunamadı. Anlatım altyazıyla ilerleyecek; Ayarlar\'dan sessiz moda geçebilirsiniz.', 7000);
        }
      }, 1500);
    }
    updateSpeedLabel();
    const due = player.dueQuestions().length;
    const dueCases = dueCaseCards(player);
    if (!opts.review) reviewTour = [];
    if (opts.review && due) player.startReview(player.dueQuestions());
    else if (opts.review && dueCases.length) showCaseReviewOffer(player, dueCases);
    else if (opts.review) nextInTour();
    else if (hasProbes(lesson) && !player.progress.data.mode) showModeChoice(player);
    else if (due) showReviewOffer(player, due);
    else if (dueCases.length) showCaseReviewOffer(player, dueCases);
    else if (last > 0) toast('Kaldığınız yerden devam: ' + (last + 1) + '. adım. Baştan başlamak için İçindekiler\'i kullanın.');
  }

  const hasProbes = (lesson) => lesson.sections.some((s) => s.steps.some((st) => st.question && st.question.probe));

  const MODES = {
    learn: { title: 'Öğrenerek ilerleyelim', text: 'Kaynağı önceden okumanız gerekmez. Önce anlatım gelir, sonra birlikte yoklarız.' },
    answer: { title: 'Önce ben yanıtlayayım', text: 'Kaynağı çalıştıysanız her bölümde önce sizin cevabınızı alırız, ardından anlatım gelir.' }
  };

  // Mercan'dan alınan iki modlu başlangıç. Seçim ders boyunca saklanır; Ayarlar'dan değişir.
  function showModeChoice(p) {
    qEl.replaceChildren();
    qEl.hidden = false;
    boardEl.classList.add('has-question');
    const card = el('div', 'q-card');
    card.appendChild(el('div', 'q-tag', 'Nasıl çalışalım?'));
    card.appendChild(el('h3', 'q-prompt', 'Bu derste iki yol var. İstediğiniz zaman Ayarlar\'dan değiştirebilirsiniz.'));
    const list = el('div', 'q-options');
    for (const [key, m] of Object.entries(MODES)) {
      const b = el('button', 'q-opt mode-opt');
      const t = el('span', 'q-text');
      t.appendChild(el('strong', null, m.title));
      t.appendChild(el('span', 'mode-desc', m.text));
      b.appendChild(t);
      b.addEventListener('click', () => {
        qEl.hidden = true;
        boardEl.classList.remove('has-question');
        p.setMode(key);
        toast(m.title + ' seçildi. Başlamak için oynat düğmesine dokunun.');
      });
      list.appendChild(b);
    }
    card.appendChild(list);
    qEl.appendChild(card);
  }

  // Ders açılınca: tekrar zamanı gelen sorular varsa önce onları öner.
  function showReviewOffer(p, n) {
    qEl.replaceChildren();
    qEl.hidden = false;
    boardEl.classList.add('has-question');
    const card = el('div', 'q-card');
    card.appendChild(el('div', 'q-tag', 'Aralıklı tekrar'));
    card.appendChild(el('h3', 'q-prompt', 'Tekrar zamanı gelen ' + n + ' soru var.'));
    card.appendChild(el('p', 'q-hint', 'Daha önce cevapladığınız soruları aralıklarla yeniden sormak, bilginin kalıcı olmasına yardım eder. Birkaç dakika sürer; not verilmez.'));
    const actions = el('div', 'q-actions');
    const later = el('button', 'btn ghost', 'Sonra');
    later.addEventListener('click', () => { qEl.hidden = true; boardEl.classList.remove('has-question'); });
    const go = el('button', 'btn primary', 'Tekrara başla');
    go.addEventListener('click', () => p.startReview(p.dueQuestions()));
    actions.append(later, go);
    card.appendChild(actions);
    qEl.appendChild(card);
  }

  function showSessionEnd(p, done, next) {
    qEl.replaceChildren();
    qEl.hidden = false;
    boardEl.classList.add('has-question');
    const card = el('div', 'q-card');
    card.appendChild(el('div', 'q-tag', 'Çalışma dilimi bitti'));
    card.appendChild(el('h3', 'q-prompt', '"' + done.title + '" bölümlerini tamamladınız.'));
    card.appendChild(el('p', 'q-hint', 'Sıradaki dilim: ' + next.title + (next.minutes ? ' (yaklaşık ' + next.minutes + ' dk)' : '') + '. Ara verebilirsiniz; ders kaldığınız yerden açılır.'));
    const actions = el('div', 'q-actions');
    const goals = el('button', 'btn', 'Hedeflerime bak');
    goals.addEventListener('click', () => openDrawer('goals'));
    const go = el('button', 'btn primary', 'Devam et');
    go.addEventListener('click', () => { qEl.hidden = true; boardEl.classList.remove('has-question'); p.play(); });
    actions.append(goals, go);
    card.appendChild(actions);
    qEl.appendChild(card);
  }

  const ui = {
    board: boardEl,

    onStep(p) {
      const st = p.step;
      const sec = p.lesson.sections[st._section];
      $('.section-name').textContent = sec.title;
      $('#stepCount').textContent = (p.index + 1) + ' / ' + p.steps.length;
      $('.track-fill').style.width = ((p.index + 1) / p.steps.length * 100) + '%';
      $('#track').setAttribute('aria-valuenow', p.index + 1);
      qEl.hidden = true;
      boardEl.classList.remove('has-question');
      renderSourceBadge(st);
      AT.prefs.set('progress-hint:' + p.lesson.id, sec.title);
      if (!drawer.hidden && !['settings', 'qa'].includes(drawer.dataset.kind)) openDrawer(drawer.dataset.kind);
    },

    onPlayState(playing) {
      lessonScreen.classList.toggle('playing', playing);
      $('[data-act="play"]').setAttribute('aria-label', playing ? 'Duraklat' : 'Oynat');
    },

    caption(text, full) {
      if (!AT.prefs.get('captions', true)) { captionEl.hidden = true; return; }
      captionEl.hidden = !text && !full;
      captionEl.textContent = text || full || '';
    },

    showQuestion(step, p) { renderQuestion(step, p); },

    showSummary(p) { openDrawer('goals', true); },

    onSessionEnd(done, next) { showSessionEnd(player, done, next); },

    onReviewEnd(r) {
      toast('Tekrar bitti: ' + r.queue.length + ' sorudan ' + r.right + ' tanesi ilk denemede doğru.'
        + (r.right < r.queue.length ? ' Yanlış olanlar 10 dakika sonra yeniden sorulabilir.' : ' Sıradaki tekrar Hedefler ekranında görünür.'), 6000);
      // Oynatıcı bu çağrıdan hemen sonra dersteki yerine döner; öneriyi ondan sonra göster.
      setTimeout(() => {
        const cards = player ? dueCaseCards(player) : [];
        if (cards.length) showCaseReviewOffer(player, cards);
        else nextInTour();
      }, 0);
    }
  };

  // Tahtanın köşesinde: bu adım kaynağın hangi yerine dayanıyor, yoksa öğretici yorumu mu?
  // Kaynağın adı dersten gelir (source.label: "Makale", "Ders notu"...).
  const BASIS = { inference: 'Öğretici yorumu', example: 'Kurgusal örnek' };
  const sourceLabel = () => (player && player.lesson.source && player.lesson.source.label) || 'Makale';
  function renderSourceBadge(st) {
    const b = $('.board-source');
    b.replaceChildren();
    const basis = st.basis || (st.sourceRef ? 'source' : null);
    if (!basis && !st.sourceRef) { b.hidden = true; return; }
    b.hidden = false;
    b.dataset.basis = basis || 'source';
    b.appendChild(el('span', 'src-kind', BASIS[basis] || sourceLabel()));
    if (st.sourceRef) b.appendChild(el('span', 'src-ref', st.sourceRef));
  }

  // ---------- Sorular ----------
  const BLOOM = ['hatirla', 'anla', 'uygula', 'cozumle', 'degerlendir', 'olustur'];
  const BLOOM_AD = { hatirla: 'Hatırla', anla: 'Anla', uygula: 'Uygula', cozumle: 'Çözümle', degerlendir: 'Değerlendir', olustur: 'Oluştur' };
  // Sorunun Bloom düzeyi; soruda yoksa yokladığı alt hedefin düzeyi.
  const bloomOf = (lesson, q) => q.bloom || ((findSubgoal(lesson, q.goal) || {}).bloom) || null;
  const bloomTag = (lesson, q) => { const b = bloomOf(lesson, q); return b ? ' · ' + BLOOM_AD[b] : ''; };

  function renderQuestion(step, p) {
    const q = step.question;
    if (q.type === 'open') return renderOpenQuestion(step, p);
    qEl.replaceChildren();
    qEl.hidden = false;
    boardEl.classList.add('has-question');
    const phase = p.phaseOf(step);
    let hintsUsed = 0;

    const card = el('div', 'q-card');
    const rv = p.review;
    const tag = rv ? 'Tekrar ' + (rv.i + 1) + '/' + rv.queue.length
      : q.kind === 'application' ? 'Yeni örnekte uygula'
      : q.probe && phase === 'once' ? 'Önce sizin yorumunuz'
      : 'Kendini yokla';
    card.appendChild(el('div', 'q-tag', tag + ' · ' + q.goal + bloomTag(p.lesson, q)));
    if (q.scenario) {
      const sc = el('div', 'q-scenario');
      sc.appendChild(el('span', 'q-fiction', 'KURGUSAL OLGU'));
      sc.appendChild(el('p', null, q.scenario));
      card.appendChild(sc);
    }
    card.appendChild(el('h3', 'q-prompt', q.prompt));
    if (q.type === 'multiple') card.appendChild(el('p', 'q-hint', 'Birden fazla doğru olabilir. Seçip "Kontrol et"e dokunun.'));

    const opts = q.type === 'truefalse'
      ? [{ text: 'Doğru', correct: q.answer === true }, { text: 'Yanlış', correct: q.answer === false }]
      : q.options;

    const list = el('div', 'q-options' + (q.type === 'truefalse' ? ' tf' : ''));
    const buttons = opts.map((o, i) => {
      const b = el('button', 'q-opt');
      b.appendChild(el('span', 'q-letter', q.type === 'truefalse' ? '' : String.fromCharCode(65 + i)));
      b.appendChild(el('span', 'q-text', o.text));
      b.addEventListener('click', () => {
        if (card.classList.contains('answered')) return;
        if (q.type === 'multiple') { b.classList.toggle('selected'); return; }
        buttons.forEach((x) => x.classList.remove('selected'));
        b.classList.add('selected');
        check();
      });
      list.appendChild(b);
      return b;
    });
    card.appendChild(list);

    // Kademeli ipucu: her dokunuş bir sonrakini açar; kaç ipucu kullanıldığı kayda geçer.
    const hintBox = el('div', 'q-hints');
    card.appendChild(hintBox);

    const feedback = el('div', 'q-feedback');
    feedback.hidden = true;
    card.appendChild(feedback);

    const actions = el('div', 'q-actions');
    const hintBtn = el('button', 'btn ghost', 'İpucu');
    hintBtn.hidden = !(q.hints && q.hints.length);
    hintBtn.addEventListener('click', () => {
      if (hintsUsed >= q.hints.length) return;
      hintBox.appendChild(el('p', 'q-hint-item', q.hints[hintsUsed]));
      hintsUsed++;
      hintBtn.textContent = hintsUsed < q.hints.length ? 'Bir ipucu daha' : 'İpucu';
      hintBtn.hidden = hintsUsed >= q.hints.length;
    });
    const checkBtn = el('button', 'btn primary', 'Kontrol et');
    checkBtn.hidden = q.type !== 'multiple';
    checkBtn.addEventListener('click', check);
    const retryBtn = el('button', 'btn', 'Tekrar dene');
    retryBtn.hidden = true;
    retryBtn.addEventListener('click', () => renderQuestion(step, p));
    // Yanlış cevapta: konunun anlatıldığı yeri (çoğu zaman ilgili şekli) dinlet, sonra soruya dön.
    const target = p.steps[p.reviewTarget(step)];
    const reviewBtn = el('button', 'btn', 'İlgili yeri dinle' + (target && target.sourceRef ? ' (' + shortRef(target.sourceRef) + ')' : ''));
    reviewBtn.hidden = true;
    reviewBtn.addEventListener('click', () => p.listenFor(step));
    const nextBtn = el('button', 'btn primary', 'Devam');
    nextBtn.addEventListener('click', () => {
      qEl.hidden = true;
      boardEl.classList.remove('has-question');
      // Duraklatılmış olsa da "Devam" anlatımı sürdürür.
      if (!p.playing) { p.playing = true; ui.onPlayState(true); }
      p.next();
    });
    const skipBtn = el('button', 'btn ghost', 'Şimdilik geç');
    skipBtn.addEventListener('click', () => nextBtn.click());
    nextBtn.hidden = true;
    actions.append(hintBtn, checkBtn, retryBtn, reviewBtn, skipBtn, nextBtn);
    card.appendChild(actions);
    qEl.appendChild(card);

    function check() {
      const chosen = buttons.map((b) => b.classList.contains('selected'));
      if (!chosen.some(Boolean)) { toast('Önce bir seçenek seçin.'); return; }
      const correct = opts.every((o, i) => !!o.correct === chosen[i]);
      card.classList.add('answered', correct ? 'is-correct' : 'is-wrong');
      buttons.forEach((b, i) => {
        if (opts[i].correct) b.classList.add('right');
        else if (chosen[i]) b.classList.add('wrong');
        b.disabled = true;
      });
      const misconceptions = opts.filter((o, i) => chosen[i] && o.misconception).map((o) => o.misconception);
      p.progress.record(step.id, {
        goal: q.goal, correct, phase, hints: hintsUsed, kind: q.kind || 'check',
        chosen: misconceptions, targets: q.targets || [], review: !!rv,
        bloom: bloomOf(p.lesson, q), type: q.type, score: correct ? 1 : 0, max: 1
      });
      if (rv && rv.counted !== rv.i) { rv.counted = rv.i; if (correct) rv.right++; }

      feedback.hidden = false;
      feedback.replaceChildren(el('strong', null, correct ? 'Doğru.' : 'Tam değil.'));
      const whys = opts.map((o, i) => (chosen[i] && o.why ? o.why : null)).filter(Boolean);
      for (const w of whys) feedback.appendChild(el('p', null, w));
      if (q.explanation) feedback.appendChild(el('p', 'q-expl', q.explanation));
      if (q.modelAnswer) {
        feedback.appendChild(el('p', 'q-model-h', 'Örnek cevap'));
        feedback.appendChild(el('p', 'q-model', q.modelAnswer));
      }
      if (misconceptions.length) {
        const m = (p.lesson.misconceptions || []).filter((x) => misconceptions.includes(x.id));
        for (const x of m) feedback.appendChild(el('p', 'q-misc', 'Not edildi: "' + x.text + '" çıkarımı. Hedefler tablosunda açık kalır; aynı ayrımı yoklayan bir soruyu doğru cevaplayınca kapanır.'));
      }
      if (q.sourceRef) feedback.appendChild(el('p', 'q-src', 'Kaynak: ' + q.sourceRef));

      hintBtn.hidden = true;
      checkBtn.hidden = true;
      skipBtn.hidden = true;
      nextBtn.hidden = false;
      retryBtn.hidden = correct;
      reviewBtn.hidden = correct || (phase === 'once' && !rv);
      nextBtn.focus();
      p.speakFeedback(AT.feedbackText(q, correct), correct);
    }
  }

  // Açık uçlu soru: öğrenci cevabını yazar (ya da aklından söyler), sonra örnek cevabı görür ve
  // rubrik ölçütlerinden hangilerini karşıladığını kendisi işaretler. Puan yalnız bu cihazda kalır.
  function renderOpenQuestion(step, p) {
    const q = step.question;
    qEl.replaceChildren();
    qEl.hidden = false;
    boardEl.classList.add('has-question');
    const phase = p.phaseOf(step);
    const rv = p.review;
    let hintsUsed = 0;
    const card = el('div', 'q-card q-open');
    const tag = rv ? 'Tekrar ' + (rv.i + 1) + '/' + rv.queue.length : 'Kendi cümlelerinle';
    card.appendChild(el('div', 'q-tag', tag + ' · ' + q.goal + bloomTag(p.lesson, q)));
    if (q.scenario) {
      const sc = el('div', 'q-scenario');
      sc.appendChild(el('span', 'q-fiction', 'KURGUSAL OLGU'));
      sc.appendChild(el('p', null, q.scenario));
      card.appendChild(sc);
    }
    card.appendChild(el('h3', 'q-prompt', q.prompt));
    const ta = el('textarea', 'q-text-answer');
    ta.rows = 4;
    ta.placeholder = 'Cevabını buraya yaz. İstersen yazmadan, aklından da cevaplayabilirsin.';
    try { ta.value = sessionStorage.getItem('at:taslak:' + p.lesson.id + ':' + step.id) || ''; } catch (e) { /* özel pencere */ }
    ta.addEventListener('input', () => { try { sessionStorage.setItem('at:taslak:' + p.lesson.id + ':' + step.id, ta.value); } catch (e) { /* yok */ } });
    card.appendChild(ta);
    const hintBox = el('div', 'q-hints');
    card.appendChild(hintBox);
    const result = el('div', 'q-feedback');
    result.hidden = true;
    card.appendChild(result);

    const actions = el('div', 'q-actions');
    const hintBtn = el('button', 'btn ghost', 'İpucu');
    hintBtn.hidden = !(q.hints && q.hints.length);
    hintBtn.addEventListener('click', () => {
      if (hintsUsed >= q.hints.length) return;
      hintBox.appendChild(el('p', 'q-hint-item', q.hints[hintsUsed]));
      hintsUsed++;
      hintBtn.hidden = hintsUsed >= q.hints.length;
    });
    const showBtn = el('button', 'btn primary', 'Örnek cevabı göster');
    const saveBtn = el('button', 'btn primary', 'Puanımı kaydet');
    saveBtn.hidden = true;
    const skipBtn = el('button', 'btn ghost', 'Şimdilik geç');
    const nextBtn = el('button', 'btn primary', 'Devam');
    nextBtn.hidden = true;
    const go = () => {
      qEl.hidden = true;
      boardEl.classList.remove('has-question');
      if (!p.playing) { p.playing = true; ui.onPlayState(true); }
      p.next();
    };
    nextBtn.addEventListener('click', go);
    skipBtn.addEventListener('click', go);
    actions.append(hintBtn, showBtn, saveBtn, skipBtn, nextBtn);
    card.appendChild(actions);
    qEl.appendChild(card);
    ta.focus();

    const rubric = q.rubric || [];
    const boxes = [];
    showBtn.addEventListener('click', () => {
      ta.readOnly = true;
      result.hidden = false;
      result.replaceChildren(el('p', 'q-model-h', 'Öğretmenin örnek cevabı'), el('p', 'q-model', q.modelAnswer || ''));
      result.appendChild(el('p', 'q-model-h', 'Cevabında bunlar var mıydı? Olanları işaretle.'));
      const list = el('div', 'q-rubric');
      for (const r of rubric) {
        const row = el('label', 'q-rubric-row');
        const cb = el('input');
        cb.type = 'checkbox';
        boxes.push(cb);
        row.append(cb, el('span', null, r.criterion + (r.required ? ' (olmazsa olmaz)' : '')), el('span', 'q-pts', r.points + ' puan'));
        list.appendChild(row);
      }
      result.appendChild(list);
      showBtn.hidden = true;
      hintBtn.hidden = true;
      saveBtn.hidden = false;
      saveBtn.focus();
    });
    saveBtn.addEventListener('click', () => {
      const max = rubric.reduce((a, r) => a + r.points, 0) || 1;
      const score = rubric.reduce((a, r, i) => a + (boxes[i].checked ? r.points : 0), 0);
      const missed = rubric.filter((r, i) => !boxes[i].checked).map((r) => r.criterion);
      const requiredOk = rubric.every((r, i) => !r.required || boxes[i].checked);
      const correct = requiredOk && score / max >= (q.passRatio == null ? 0.6 : q.passRatio);
      boxes.forEach((b) => { b.disabled = true; });
      card.classList.add('answered', correct ? 'is-correct' : 'is-wrong');
      p.progress.record(step.id, {
        goal: q.goal, correct, phase, hints: hintsUsed, kind: q.kind || 'check', chosen: [], targets: q.targets || [],
        review: !!rv, bloom: bloomOf(p.lesson, q), type: 'open', score, max, missed
      });
      if (rv && rv.counted !== rv.i) { rv.counted = rv.i; if (correct) rv.right++; }
      try { sessionStorage.removeItem('at:taslak:' + p.lesson.id + ':' + step.id); } catch (e) { /* yok */ }
      const verdict = el('p', 'q-score', (correct ? 'Yeterli. ' : 'Henüz yeterli değil. ') + score + ' / ' + max + ' puan');
      result.prepend(verdict);
      if (!requiredOk) result.appendChild(el('p', null, 'Olmazsa olmaz bir ölçüt eksik kaldı; bu soru aralıklı tekrarda yeniden gelecek.'));
      if (q.explanation) result.appendChild(el('p', 'q-expl', q.explanation));
      if (q.sourceRef) result.appendChild(el('p', 'q-src', 'Kaynak: ' + q.sourceRef));
      saveBtn.hidden = true;
      skipBtn.hidden = true;
      nextBtn.hidden = false;
      nextBtn.focus();
      p.speakFeedback(AT.feedbackText(q, correct), correct);
    });
  }

  // ---------- Vaka ----------
  const caseCtx = () => ({
    player, qEl, boardEl, toast,
    onExit: () => { currentCase = null; lessonScreen.classList.remove('case-active'); $('#caseReturn').hidden = true; player.goTo(player.index, { play: false }); },
    restart: (card) => startCase(card),
    onReteach: (t, run) => {
      const si = player.lesson.sections.findIndex((s) => s.id === t.bolum);
      if (si < 0) { toast('Bu bölüm derste bulunamadı.'); return; }
      qEl.hidden = true;
      boardEl.classList.remove('has-question', 'case-mode', 'case-peek');
      lessonScreen.classList.remove('case-active');
      currentCase = run;
      $('#caseReturn').hidden = false;
      player.goTo(player.sectionStart(si), { play: true });
      toast('Bölümü dinledikten sonra üstteki "Vakaya dön" düğmesine bas.', 5000);
    }
  });

  function startCase(card) {
    if (!player) return;
    $('#caseReturn').hidden = true;
    currentCase = new AT.CaseRun(card, caseCtx());
    lessonScreen.classList.add('case-active');
    $('.section-name').textContent = 'Vaka: ' + card.baslik;
    currentCase.start();
  }

  function startOral(n = 5) {
    if (!player) return;
    const pool = AT.sozluHavuzu(player.lesson, player.progress);
    if (!pool.length) { toast('Bu derste sözlü prova için açık uçlu soru yok.'); return; }
    lessonScreen.classList.add('case-active');
    $('.section-name').textContent = 'Sözlü sınav provası';
    new AT.OralRun(pool.slice(0, n), {
      player, qEl, boardEl, toast,
      onExit: () => { lessonScreen.classList.remove('case-active'); player.goTo(player.index, { play: false }); }
    }).start();
  }

  function resumeCase() {
    if (!currentCase) return;
    $('#caseReturn').hidden = true;
    lessonScreen.classList.add('case-active');
    $('.section-name').textContent = 'Vaka: ' + currentCase.card.baslik;
    currentCase.resume();
  }

  function findSubgoal(lesson, id) {
    for (const g of lesson.goals || []) {
      if (g.id === id) return g;
      for (const s of g.subgoals || []) if (s.id === id) return s;
    }
    return null;
  }

  // ---------- Çekmece ----------
  function openDrawer(kind, isSummary) {
    if (!player) return;
    drawer.dataset.kind = kind;
    drawer.hidden = false;
    const body = $('.drawer-body', drawer);
    body.replaceChildren();
    const h = $('.drawer-head h2', drawer);

    if (kind === 'toc') {
      h.textContent = 'İçindekiler';
      const L = player.lesson;
      const groups = (L.sessions && L.sessions.length)
        ? L.sessions.map((g) => ({ title: g.title, minutes: g.minutes, ids: g.sections }))
        : [{ title: null, ids: L.sections.map((s) => s.id) }];
      for (const g of groups) {
        if (g.title) body.appendChild(el('h3', 'toc-session', g.title + (g.minutes ? ' · ~' + g.minutes + ' dk' : '')));
        const ol = el('ol', 'toc');
        for (const id of g.ids) {
          const si = L.sections.findIndex((s) => s.id === id);
          if (si < 0) continue;
          const sec = L.sections[si];
          const li = el('li');
          const b = el('button', 'toc-item' + (player.step._section === si ? ' current' : ''));
          b.appendChild(el('span', 'toc-title', (player.progress.data.heard[sec.id] ? '✓ ' : '') + sec.title));
          if (sec.goals && sec.goals.length) b.appendChild(el('span', 'toc-goals', sec.goals.join(' · ')));
          b.addEventListener('click', () => { closeDrawer(); player.goTo(player.sectionStart(si)); });
          li.appendChild(b);
          ol.appendChild(li);
        }
        body.appendChild(ol);
      }
      const restart = el('button', 'btn', 'Dersi baştan başlat');
      restart.addEventListener('click', () => { closeDrawer(); player.goTo(0); });
      body.appendChild(restart);
    }

    if (kind === 'cases') {
      h.textContent = 'Vakalar';
      body.appendChild(el('p', 'drawer-note', 'Bir hastanın başvurusundan kapanışına kadar kararları sen verirsin: hangi muayeneyi isteyeceğini, tanıyı, tedaviyi. Seçtiğin yol tahtada karar ağacı olarak büyür. Takılırsan ilgili ders bölümünü yeniden dinleyebilirsin.'));
      for (const c of player.lesson._cases) {
        const son = AT.vakaSonuclari(player.progress, c.id);
        const last = son[son.length - 1];
        const box = el('div', 'goal case-item');
        box.appendChild(el('h3', null, c.baslik));
        const meta = [c.duzey, c.sure_dk ? '~' + c.sure_dk + ' dk' : null, c.kurgusal ? 'kurgusal' : 'gerçek hastadan, kimliksiz',
          (c.ogretmen_onayi && c.ogretmen_onayi.onaylandi) ? 'öğretmen onaylı' : 'öğretmen onayı bekliyor'].filter(Boolean).join(' · ');
        box.appendChild(el('p', 'drawer-note', meta));
        if (c.hedefler && c.hedefler.length) box.appendChild(el('p', 'drawer-note', 'Hedefler: ' + c.hedefler.join(', ')));
        if (last) box.appendChild(el('p', 'drawer-note', son.length + ' kez çözdün · son sonuç: ' + (AT.karneHelpers.SON[last.sonuc] || last.sonuc)
          + (last.tehlikeli ? ' · zarar verebilecek seçim: ' + last.tehlikeli : '')));
        const go = el('button', 'btn primary small', last ? 'Yeniden çöz' : 'Vakayı başlat');
        go.addEventListener('click', () => { closeDrawer(); startCase(c); });
        box.appendChild(go);
        body.appendChild(box);
      }
    }

    if (kind === 'karne') {
      h.textContent = 'Karnem';
      const k = AT.karne(player.lesson, player.progress.data);
      const { pct, difficulty } = AT.karneHelpers;
      body.appendChild(el('p', 'drawer-note', 'Karne not için değildir. Yalnız bu cihazdaki cevaplarından hesaplanır ve hiçbir yere gönderilmez. Amacı, nerede güçlü olduğunu ve neyi tekrar etmen gerektiğini göstermek.'));
      if (!k.n) {
        body.appendChild(el('p', null, 'Henüz cevapladığın soru yok. Bölüm sonlarındaki soruları cevapladıkça karnen burada oluşur.'));
      } else {
        const head = el('div', 'karne-head');
        head.appendChild(el('div', 'karne-big', pct(k.total)));
        head.appendChild(el('div', 'karne-sub', k.n + ' cevap · ' + k.strong.length + ' güçlü hedef · ' + k.weak.length + ' geliştirilecek hedef'));
        body.appendChild(head);
        if (k.weak.length) {
          const box = el('div', 'goal');
          box.appendChild(el('h3', null, 'Sıradaki adımın'));
          for (const id of k.weak) {
            const g = k.goals.find((x) => x.id === id);
            const row = el('div', 'subgoal review');
            row.appendChild(el('span', 'sg-dot'));
            const t = el('div', 'sg-text');
            t.appendChild(el('span', 'sg-id', id));
            t.appendChild(document.createTextNode(' ' + g.text + ' · başarı ' + pct(g.rate)));
            row.appendChild(t);
            const si = player.lesson.sections.findIndex((sec) => (sec.goals || []).includes(id));
            if (si >= 0) {
              const go = el('button', 'btn small', 'Yeniden dinle');
              go.addEventListener('click', () => { closeDrawer(); player.goTo(player.sectionStart(si)); });
              row.appendChild(go);
            }
            box.appendChild(row);
          }
          body.appendChild(box);
        }
        const table = (title, headers, rows, note) => {
          const box = el('div', 'goal');
          box.appendChild(el('h3', null, title));
          const tb = el('table', 'karne-table');
          const tr = el('tr');
          for (const x of headers) tr.appendChild(el('th', null, x));
          tb.appendChild(tr);
          for (const r of rows) {
            const row = el('tr');
            for (const x of r) row.appendChild(el('td', null, String(x)));
            tb.appendChild(row);
          }
          box.appendChild(tb);
          if (note) box.appendChild(el('p', 'drawer-note', note));
          body.appendChild(box);
        };
        if (k.bloom.length) table('Düşünme düzeyine göre (Bloom)', ['Düzey', 'Cevap', 'Başarı'],
          k.bloom.map((b) => [AT.BLOOM_AD[b.level], b.n, pct(b.rate)]),
          'Üst düzeylerde (çözümle, değerlendir, oluştur) başarın belirgin düşükse bilgiyi biliyor ama uygulamakta zorlanıyorsun demektir.');
        table('Hedefler', ['Hedef', 'Düzey', 'Cevap', 'Başarı', 'İlk denemede'],
          k.goals.filter((g) => g.n).map((g) => [g.id, AT.BLOOM_AD[g.bloom] || '–', g.n, pct(g.rate), pct(g.first)]));
        table('Senin için en zor sorular', ['Soru', 'Deneme', 'Başarı', 'Güçlük'],
          k.items.slice(0, 8).map((it) => [it.prompt.slice(0, 70) + (it.prompt.length > 70 ? '…' : ''), it.n, pct(it.rate), difficulty(it.rate)]),
          'Güçlük senin cevaplarına göredir; sorunun herkes için zorluğunu göstermez.');
        if (k.missed.length) table('Açık uçlu cevaplarda en sık eksik kalanlar', ['Ölçüt', 'Kez'], k.missed);
        if (k.cases.length) table('Vakalar', ['Vaka', 'Çözülme', 'Son sonuç', 'En iyi'],
          k.cases.map((c) => [c.title, c.n, AT.karneHelpers.SON[c.last.sonuc] || c.last.sonuc, pct(c.best)]));
        if (k.danger.length) table('Hastaya zarar verebilecek seçimler', ['Nerede', 'Seçimin'], k.danger.map((d) => [d.prompt, d.answer]),
          'Bu seçimler ayrıca gösterilir; vakayı yeniden çözerken bunlara dikkat et.');
      }
      const acts = el('div', 'drawer-actions');
      const dl = el('button', 'btn', 'Karnemi indir (.md)');
      dl.addEventListener('click', () => {
        const blob = new Blob([AT.karneMarkdown(player.lesson, k)], { type: 'text/markdown;charset=utf-8' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'karne-' + player.lesson.id + '.md';
        document.body.appendChild(a);
        a.click();
        setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
      });
      const back = el('button', 'btn ghost', 'Hedeflere dön');
      back.addEventListener('click', () => openDrawer('goals'));
      acts.append(dl, back);
      body.appendChild(acts);
    }

    if (kind === 'goals') {
      h.textContent = isSummary ? 'Ders bitti: hedeflere bakış' : 'Öğrenme hedefleri';
      body.appendChild(el('p', 'drawer-note', 'Bu tablo yalnızca sizin içindir ve bu cihazda saklanır. Not verilmez. "Dinlendi" ile "doğru cevaplandı" ayrı gösterilir; anlatım tek başına öğrenme sayılmaz.'));
      body.appendChild(reviewBox(player));
      const legend = el('p', 'drawer-note ev-legend');
      for (const [k, t] of EVIDENCE) legend.appendChild(el('span', 'ev on ' + k, t));
      body.appendChild(legend);
      const labels = { ok: 'Ulaşıldı', review: 'Tekrar edin', partial: 'Yarım', none: 'Yoklanmadı', noquestion: '' };
      for (const g of player.lesson.goals || []) {
        const box = el('div', 'goal');
        box.appendChild(el('h3', null, g.id + '. ' + g.title));
        for (const sg of g.subgoals || []) {
          const st = player.goalStatus(sg.id);
          const row = el('div', 'subgoal ' + st.status);
          row.appendChild(el('span', 'sg-dot'));
          const txt = el('div', 'sg-text');
          txt.appendChild(el('span', 'sg-id', sg.id));
          txt.appendChild(document.createTextNode(' ' + sg.text));
          const evs = el('div', 'sg-ev');
          for (const [k, t] of EVIDENCE) evs.appendChild(el('span', 'ev ' + k + (st[k] ? ' on' : ''), t));
          txt.appendChild(evs);
          row.appendChild(txt);
          const side = el('div', 'sg-side');
          if (labels[st.status]) side.appendChild(el('span', 'sg-status', labels[st.status] + (st.total ? ` (${st.correct}/${st.total})` : '')));
          const si = player.lesson.sections.findIndex((s) => (s.goals || []).includes(sg.id));
          if (si >= 0) {
            const go = el('button', 'btn small', 'Dinle');
            go.addEventListener('click', () => { closeDrawer(); player.goTo(player.sectionStart(si)); });
            side.appendChild(go);
          }
          row.appendChild(side);
          box.appendChild(row);
        }
        body.appendChild(box);
      }
      const open = openMisconceptions(player);
      if (open.length) {
        const box = el('div', 'goal misc-box');
        box.appendChild(el('h3', null, 'Açık kalan çıkarımlar'));
        box.appendChild(el('p', 'drawer-note', 'Bir çeldiricide seçtiğiniz çıkarım, aynı ayrımı yoklayan bir soruyu doğru cevaplayana kadar burada durur.'));
        for (const m of open) {
          const row = el('div', 'subgoal review');
          row.appendChild(el('span', 'sg-dot'));
          const t = el('div', 'sg-text');
          t.appendChild(el('span', 'sg-id', m.goal));
          t.appendChild(document.createTextNode(' ' + m.text));
          row.appendChild(t);
          box.appendChild(row);
        }
        body.appendChild(box);
      }
      const acts = el('div', 'drawer-actions');
      const krn = el('button', 'btn primary', 'Karnemi göster');
      krn.addEventListener('click', () => openDrawer('karne'));
      acts.appendChild(krn);
      const oral = el('button', 'btn', 'Sözlü sınav provası');
      oral.addEventListener('click', () => { closeDrawer(); startOral(); });
      acts.appendChild(oral);
      const exp = el('button', 'btn', 'Çalışma özetimi indir (.md)');
      exp.addEventListener('click', () => downloadSummary(player));
      const reset = el('button', 'btn ghost', 'Cevaplarımı sıfırla');
      reset.addEventListener('click', () => { player.progress.reset(); openDrawer('goals'); });
      acts.append(exp, reset);
      body.appendChild(acts);
      body.appendChild(el('p', 'drawer-note', 'Özet dosyası yalnızca sizin cihazınıza iner. Hiçbir yere gönderilmez; paylaşıp paylaşmamak size kalmıştır.'));
      if (player.lesson.source) {
        const s = player.lesson.source;
        const src = el('p', 'drawer-source');
        src.textContent = 'Kaynak: ' + [s.citation, s.doi ? 'doi:' + s.doi : null, s.license].filter(Boolean).join(' · ');
        body.appendChild(src);
      }
    }

    if (kind === 'qa') {
      h.textContent = 'Soru sor';
      renderQa(body);
    }

    if (kind === 'settings') {
      h.textContent = 'Ayarlar';
      if (hasProbes(player.lesson)) {
        const modeRow = el('label', 'set-row');
        modeRow.appendChild(el('span', null, 'Çalışma yolu'));
        const ms = el('select');
        for (const [k, m] of Object.entries(MODES)) {
          const o = el('option', null, m.title);
          o.value = k;
          if (player.mode === k) o.selected = true;
          ms.appendChild(o);
        }
        ms.addEventListener('change', () => { player.setMode(ms.value); toast(MODES[ms.value].text, 5000); });
        modeRow.appendChild(ms);
        body.appendChild(modeRow);
      }
      // Ses
      const ws = player.webSpeech;
      const voiceRow = el('label', 'set-row');
      voiceRow.appendChild(el('span', null, 'Ses'));
      const sel = el('select');
      if (!ws.voices.length) sel.appendChild(el('option', null, 'Türkçe ses bulunamadı'));
      for (const v of ws.voices) {
        const o = el('option', null, v.name + (v.localService ? '' : ' (çevrimiçi)'));
        o.value = v.voiceURI;
        if (ws.voice && v.voiceURI === ws.voice.voiceURI) o.selected = true;
        sel.appendChild(o);
      }
      sel.addEventListener('change', () => ws.setVoice(sel.value));
      voiceRow.appendChild(sel);
      body.appendChild(voiceRow);

      const rateRow = el('label', 'set-row');
      rateRow.appendChild(el('span', null, 'Hız'));
      const rate = el('input');
      Object.assign(rate, { type: 'range', min: 0.6, max: 1.6, step: 0.1, value: player.rate });
      const rv = el('output', null, player.rate.toFixed(1) + '×');
      rate.addEventListener('input', () => { player.setRate(Number(rate.value)); rv.textContent = Number(rate.value).toFixed(1) + '×'; updateSpeedLabel(); });
      rateRow.append(rate, rv);
      body.appendChild(rateRow);

      body.appendChild(toggleRow('Altyazı', AT.prefs.get('captions', true), (v) => {
        AT.prefs.set('captions', v);
        ui.caption(AT.plainSay(player.step.say));
      }));
      body.appendChild(toggleRow('Sessiz (yalnız altyazı)', AT.prefs.get('muted', false), (v) => player.setMuted(v)));

      const test = el('button', 'btn', 'Sesi dene');
      test.addEventListener('click', () => { player.engine.stop(); player.webSpeech.speak('Merhaba, ben akıllı tahtanın anlatıcısıyım.'); });
      body.appendChild(test);

      const info = el('p', 'drawer-note');
      info.textContent = player.lesson._audioManifest
        ? 'Bu ders önceden kaydedilmiş seslerle anlatılıyor.'
        : 'Anlatım tarayıcınızın ücretsiz Türkçe sesiyle yapılıyor. Ses kalitesi cihaza göre değişir.';
      body.appendChild(info);
      body.appendChild(qaSettings());
      const keys = el('p', 'drawer-note', 'Klavye: Boşluk oynat/duraklat · ← → adım · R cümleyi tekrarla · F tam ekran. Dokunmatik: tahtada sağa/sola kaydırın.');
      body.appendChild(keys);
    }
  }

  function reviewBox(p) {
    const box = el('div', 'review-box');
    const due = p.dueQuestions();
    const srs = Object.values(p.progress.data.srs || {});
    if (due.length) {
      box.appendChild(el('p', null, 'Tekrar zamanı gelen ' + due.length + ' soru var.'));
      const b = el('button', 'btn primary', 'Tekrar et (' + due.length + ' soru)');
      b.addEventListener('click', () => { closeDrawer(); p.startReview(due); });
      box.appendChild(b);
    } else if (srs.length) {
      const next = Math.min(...srs.map((v) => v.due));
      box.appendChild(el('p', null, 'Şu an tekrar edilecek soru yok. Sıradaki tekrar: ' + new Date(next).toLocaleString('tr-TR', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' }) + '.'));
    } else {
      box.appendChild(el('p', null, 'Cevapladığınız sorular aralıklarla (10 dk, 1 gün, 3 gün, 1 hafta, 3 hafta) yeniden sorulur.'));
    }
    return box;
  }

  // "s. 6 · 3.5.1, Şekil 2" -> "Şekil 2" ya da "s. 6"
  function shortRef(ref) {
    const f = String(ref).match(/Şekil\s*\d+[A-Za-z]?/);
    if (f) return f[0];
    const pg = String(ref).match(/s\.\s*[\d–-]+/);
    return pg ? pg[0] : ref;
  }

  const SPEEDS = [0.8, 1, 1.2, 1.4, 1.6];
  function updateSpeedLabel() {
    const b = $('[data-act="speed"]');
    if (b && player) b.textContent = player.rate.toFixed(1).replace('.', ',') + '×';
  }

  const EVIDENCE = [['heard', 'Dinlendi'], ['before', 'Anlatımdan önce doğru'], ['after', 'Anlatımdan sonra doğru'], ['applied', 'Yeni örnekte uygulandı']];

  function openMisconceptions(p) {
    const st = p.progress.misconceptions();
    return (p.lesson.misconceptions || []).filter((m) => st[m.id] && st[m.id].open);
  }

  // Mercan'ın sonuç raporundan esinlenen, öğrencinin kendi isteğiyle indirdiği özet.
  function downloadSummary(p) {
    const L = p.lesson;
    const yes = (b) => (b ? 'evet' : '—');
    const lines = [
      '# Çalışma özeti: ' + L.title, '',
      'Tarih: ' + new Date().toLocaleString('tr-TR'),
      'Çalışma yolu: ' + (MODES[p.mode] ? MODES[p.mode].title : '—'),
      'Kaynak: ' + (L.source ? [L.source.citation, L.source.doi ? 'doi:' + L.source.doi : ''].join(' ') : '—'), '',
      'Bu özet notlandırma için değildir. "Dinlendi", anlatımın sonuna ulaşıldığını gösterir; öğrenildiği anlamına gelmez.', '',
      '| Alt hedef | Dinlendi | Anlatımdan önce doğru | Anlatımdan sonra doğru | Yeni örnekte uygulandı | Son cevaplar | Kullanılan ipucu |',
      '|---|---|---|---|---|---|---|'
    ];
    for (const g of L.goals || []) for (const sg of g.subgoals || []) {
      const st = p.goalStatus(sg.id);
      lines.push(`| ${sg.id} ${sg.text} | ${yes(st.heard)} | ${yes(st.before)} | ${yes(st.after)} | ${yes(st.applied)} | ${st.total ? st.correct + '/' + st.total : '—'} | ${st.hints || 0} |`);
    }
    const open = openMisconceptions(p);
    lines.push('', '## Açık kalan çıkarımlar', '');
    if (open.length) for (const m of open) lines.push(`- ${m.goal}: ${m.text}`);
    else lines.push('Yok.');
    const blob = new Blob([lines.join('\n') + '\n'], { type: 'text/markdown;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'calisma-ozeti-' + L.id + '.md';
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  }

  function toggleRow(label, value, onChange) {
    const row = el('label', 'set-row');
    row.appendChild(el('span', null, label));
    const cb = el('input');
    cb.type = 'checkbox';
    cb.checked = value;
    cb.addEventListener('change', () => onChange(cb.checked));
    row.appendChild(cb);
    return row;
  }

  // ---------- Soru sor ----------
  const QA_MODES = { none: 'Model yok (yalnız arama)', local: 'Yerel model', api: 'Bulut API (Claude)' };

  function qaContext() {
    if (!qaState.retriever) qaState.retriever = AT.createRetriever(player.lesson);
    const st = player.step;
    return {
      lesson: player.lesson, retriever: qaState.retriever,
      sectionTitle: player.lesson.sections[st._section].title,
      narration: AT.plainSay(st.say || (st.question && st.question.prompt) || '').slice(0, 600),
      history: qaState.history
    };
  }

  function qaModeLine() {
    const cur = AT.qa.current();
    if (!cur) return 'Model kapalı: sorunuz yalnız ders anlatımında ve kaynakta aranır, hiçbir yere gönderilmez.';
    const where = cur.provider.kind === 'api' ? 'Soru ve ilgili ders parçaları Anthropic\'e gönderilir; adınız ve cevaplarınız gönderilmez.'
      : 'Soru yerel modele (' + cur.baseURL + ') gönderilir.';
    return cur.provider.label + ' · ' + cur.model + '. ' + where + ' Ayarlar\'dan değiştirebilirsiniz.';
  }

  function renderQa(body) {
    body.appendChild(el('p', 'drawer-note', qaModeLine()));
    const form = el('form', 'qa-form');
    const input = el('textarea');
    Object.assign(input, { rows: 2, maxLength: 500, placeholder: 'Örn. Çevrili defekt neden rekonstrüksiyona daha uygun?' });
    input.setAttribute('aria-label', 'Sorunuz');
    const send = el('button', 'btn primary', 'Sor');
    send.type = 'submit';
    form.append(input, send);
    body.appendChild(form);
    const out = el('div', 'qa-out');
    body.appendChild(out);
    if (qaState.last) renderAnswer(out, qaState.last);
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); } });
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      const q = input.value.trim();
      if (q.length < 3) { toast('Önce sorunuzu yazın.'); return; }
      askQa(q, out, send);
    });
    setTimeout(() => input.focus(), 50);
  }

  async function askQa(q, out, send) {
    if (qaState.busy) qaState.busy.abort();
    const ctrl = new AbortController();
    qaState.busy = ctrl;
    if (player.playing) player.pause();
    out.replaceChildren(el('p', 'qa-q', q));
    const live = el('div', 'qa-answer streaming', AT.qa.current() ? 'Düşünüyor…' : 'Aranıyor…');
    out.appendChild(live);
    const stop = el('button', 'btn ghost small', 'Durdur');
    stop.type = 'button';
    stop.addEventListener('click', () => ctrl.abort());
    out.appendChild(stop);
    send.disabled = true;
    try {
      const r = await AT.qa.ask(q, qaContext(), { signal: ctrl.signal, onText: (t) => { live.textContent = t; } });
      r.question = q;
      qaState.last = r;
      if (r.text) qaState.history = qaState.history.concat({ q, a: r.text }).slice(-4);
      renderAnswer(out, r);
      if (r.board.commands.length) showOnBoard(r);
    } catch (e) {
      out.replaceChildren(el('p', 'qa-q', q), el('p', 'qa-error', e.name === 'AbortError' ? 'Durduruldu.' : e.message));
    } finally {
      send.disabled = false;
      if (qaState.busy === ctrl) qaState.busy = null;
    }
  }

  // [K1] işaretlerini küçük kaynak etiketlerine çevir (metin her zaman textContent kalır).
  function citedText(parent, text) {
    for (const part of String(text).split(/(\[K\d+\](?:\s*\[K\d+\])*)/g)) {
      if (!part) continue;
      if (/^\[K\d+\]/.test(part)) for (const m of part.match(/K\d+/g)) parent.appendChild(el('sup', 'qa-cite', m));
      else parent.appendChild(document.createTextNode(part));
    }
    return parent;
  }

  function renderAnswer(out, r) {
    out.replaceChildren();
    if (r.question) out.appendChild(el('p', 'qa-q', r.question));
    if (r.mode !== 'none') {
      for (const para of r.text.split(/\n{2,}/)) out.appendChild(citedText(el('p', 'qa-answer'), para));
      out.appendChild(el('p', 'drawer-note', 'Yapay zekâ cevabıdır; yanlış olabilir. Etiketli kaynak parçalarıyla karşılaştırın.'));
      for (const n of r.board.notes) out.appendChild(el('p', 'drawer-note', n));
      if (r.board.commands.length) {
        const b = el('button', 'btn small', 'Tahtada göster');
        b.addEventListener('click', () => showOnBoard(r));
        const back = el('button', 'btn small', 'Derse dön');
        back.dataset.act = 'back-to-lesson';
        const row = el('div', 'drawer-actions');
        row.append(b, back);
        out.appendChild(row);
      }
    } else if (!r.passages.length) {
      out.appendChild(el('p', 'qa-answer', 'Ders anlatımında ve kaynakta bu soruyla eşleşen bir yer bulunamadı. Başka sözcüklerle deneyin.'));
    } else {
      out.appendChild(el('p', 'drawer-note', 'Model kapalı. Sorunuzla en çok örtüşen yerler:'));
    }
    const cited = new Set((r.text.match(/K\d+/g) || []).map((k) => Number(k.slice(1))));
    const list = el('ol', 'qa-sources');
    r.passages.forEach((p, i) => {
      if (r.mode !== 'none' && cited.size && !cited.has(i + 1)) return;
      const li = el('li');
      li.value = i + 1;
      const head = el('div', 'qa-src-head');
      head.appendChild(el('span', 'qa-cite', 'K' + (i + 1)));
      head.appendChild(el('span', 'qa-src-ref', (p.kind === 'kaynak' ? 'Kaynak' : 'Ders') + ' · ' + (p.ref || p.title)));
      if (p.stepId) {
        const go = el('button', 'btn small', 'Dinle');
        go.addEventListener('click', () => {
          const i2 = player.steps.findIndex((s) => s.id === p.stepId);
          if (i2 >= 0) { closeDrawer(); player.goTo(i2); }
        });
        head.appendChild(go);
      }
      li.appendChild(head);
      li.appendChild(el('p', 'qa-src-text', p.text.length > 320 ? p.text.slice(0, 320) + '…' : p.text));
      list.appendChild(li);
    });
    if (list.childElementCount) out.appendChild(list);
    if (r.mode !== 'none') {
      const u = r.usage || {};
      const parts = [(r.ms / 1000).toFixed(1).replace('.', ',') + ' sn', (u.input || 0) + ' girdi + ' + (u.output || 0) + ' çıktı token'];
      if (u.cacheRead) parts.push(u.cacheRead + ' önbellekten');
      if (r.cost != null) parts.push('≈ $' + r.cost.toFixed(4).replace('.', ','));
      out.appendChild(el('p', 'qa-cost', parts.join(' · ')));
    }
  }

  // Modelin tahta komutlarını çiz; ders tahtası "Derse dön" ile geri gelir.
  function showOnBoard(r) {
    if (player.playing) player.pause();
    player.board.clear();
    for (const c of r.board.commands) player.board.run(c, false);
    const b = $('.board-source');
    b.replaceChildren();
    b.hidden = false;
    b.dataset.basis = 'ai';
    b.appendChild(el('span', 'src-kind', 'Yapay zekâ cevabı · kontrol edin'));
    const back = el('button', 'btn small', 'Derse dön');
    back.dataset.act = 'back-to-lesson';
    b.appendChild(back);
    if (window.matchMedia('(max-width: 900px)').matches) closeDrawer();
  }

  function backToLesson() { player.goTo(player.index, { play: false }); }

  function qaSettings() {
    const box = el('div', 'qa-settings');
    box.appendChild(el('h3', null, 'Soru-cevap'));
    const s = AT.qa.settings();
    const provs = Object.values(AT.qa.providers);

    const modeRow = el('label', 'set-row');
    modeRow.appendChild(el('span', null, 'Kip'));
    const ms = el('select');
    for (const [k, t] of Object.entries(QA_MODES)) {
      const o = el('option', null, t);
      o.value = k;
      o.selected = s.mode === k;
      ms.appendChild(o);
    }
    ms.addEventListener('change', () => { AT.qa.saveSettings({ mode: ms.value }); openDrawer('settings'); });
    modeRow.appendChild(ms);
    box.appendChild(modeRow);

    if (s.mode === 'none') {
      box.appendChild(el('p', 'drawer-note', 'Model kullanılmaz, ücret yoktur, internet gerekmez. "Soru sor" sorunuzu ders anlatımında ve makalede arayıp ilgili yerleri gösterir.'));
    } else {
      const choices = provs.filter((p) => p.kind === s.mode);
      const id = s.provider[s.mode] && AT.qa.providers[s.provider[s.mode]] ? s.provider[s.mode] : (choices[0] || {}).id;
      const p = AT.qa.providers[id];
      if (choices.length > 1) {
        const r = el('label', 'set-row');
        r.appendChild(el('span', null, 'Sağlayıcı'));
        const ps = el('select');
        for (const c of choices) { const o = el('option', null, c.label); o.value = c.id; o.selected = c.id === id; ps.appendChild(o); }
        ps.addEventListener('change', () => { AT.qa.saveSettings({ provider: Object.assign(s.provider, { [s.mode]: ps.value }) }); openDrawer('settings'); });
        r.appendChild(ps);
        box.appendChild(r);
      }
      const textRow = (label, value, ph, onSave, type = 'text') => {
        const r = el('label', 'set-row');
        r.appendChild(el('span', null, label));
        const inp = el('input');
        Object.assign(inp, { type, value: value || '', placeholder: ph || '', autocomplete: 'off', spellcheck: false });
        inp.addEventListener('change', () => onSave(inp.value.trim()));
        r.appendChild(inp);
        return { r, inp };
      };
      const model = textRow('Model', s.models[id] || p.defaultModel, p.defaultModel, (v) => AT.qa.saveSettings({ models: Object.assign(s.models, { [id]: v }) }));
      if (p.models) {
        const dl = el('datalist');
        dl.id = 'qa-models-' + id;
        for (const m of p.models) { const o = el('option'); o.value = m; dl.appendChild(o); }
        model.r.appendChild(dl);
        model.inp.setAttribute('list', dl.id);
      }
      box.appendChild(model.r);
      if (p.kind === 'local') {
        box.appendChild(textRow('Adres', s.baseURLs[id] || p.defaultBaseURL, p.defaultBaseURL, (v) => AT.qa.saveSettings({ baseURLs: Object.assign(s.baseURLs, { [id]: v }) })).r);
        box.appendChild(toggleRow('Tahta aracı (model destekliyorsa)', id in s.tools ? s.tools[id] : p.tools !== false,
          (v) => AT.qa.saveSettings({ tools: Object.assign(s.tools, { [id]: v }) })));
      }
      if (p.needsKey || p.optionalKey) {
        const has = !!AT.qa.getKey(id);
        const key = textRow('API anahtarı', '', has ? 'kayıtlı (değiştirmek için yazın)' : 'anahtarınızı yapıştırın', (v) => {
          if (v) { AT.qa.setKey(id, v); toast('Anahtar yalnız bu tarayıcıya kaydedildi.'); openDrawer('settings'); }
        }, 'password');
        box.appendChild(key.r);
        if (has) {
          const del = el('button', 'btn ghost small', 'Anahtarı bu cihazdan sil');
          del.addEventListener('click', () => { AT.qa.setKey(id, ''); toast('Anahtar silindi.'); openDrawer('settings'); });
          box.appendChild(del);
        }
        box.appendChild(el('p', 'drawer-note', 'Anahtar yalnız bu tarayıcıda saklanır; uygulamanın koduna ya da başka bir yere yazılmaz. Ortak bilgisayarda işiniz bitince silin. Ücretler anahtarın sahibine yansır.'));
      }
      const u = AT.qa.usage();
      if (u.questions) {
        const line = el('p', 'drawer-note', 'Bu cihazda şimdiye kadar: ' + u.questions + ' soru, ' + u.input + ' girdi + ' + u.output + ' çıktı token'
          + (u.cacheRead ? ', ' + u.cacheRead + ' önbellekten' : '') + (u.cost ? ' · ≈ $' + u.cost.toFixed(3).replace('.', ',') : '') + '. ');
        const reset = el('button', 'btn ghost small', 'Sıfırla');
        reset.addEventListener('click', () => { AT.qa.resetUsage(); openDrawer('settings'); });
        line.appendChild(reset);
        box.appendChild(line);
      }
    }
    return box;
  }

  function closeDrawer() { drawer.hidden = true; }

  // ---------- İlerleme çubuğu ----------
  function buildTrack() {
    const secBox = $('.track-sections');
    secBox.replaceChildren();
    const n = player.steps.length;
    player.lesson.sections.forEach((sec, si) => {
      const start = player.sectionStart(si);
      const m = el('span', 'track-mark');
      m.style.left = (start / n * 100) + '%';
      m.title = sec.title;
      secBox.appendChild(m);
    });
    $('#track').setAttribute('aria-valuemax', n);
  }

  function seekFromEvent(e) {
    const r = $('#track').getBoundingClientRect();
    const x = (e.touches ? e.touches[0].clientX : e.clientX) - r.left;
    const i = Math.floor(Math.max(0, Math.min(0.999, x / r.width)) * player.steps.length);
    player.goTo(i);
  }

  // ---------- Olaylar ----------
  document.addEventListener('click', (e) => {
    const b = e.target.closest('[data-act]');
    if (!b) return;
    const act = b.dataset.act;
    if (act === 'home') return showHome();
    if (!player) return;
    switch (act) {
      case 'play': player.toggle(); break;
      case 'next': player.next(); break;
      case 'prev': player.prev(); break;
      case 'replay': player.replay(); break;
      case 'speed': {
        const k = SPEEDS.findIndex((v) => v > player.rate + 0.01);
        player.setRate(SPEEDS[k < 0 ? 0 : k]);
        updateSpeedLabel();
        toast('Hız: ' + player.rate.toFixed(1).replace('.', ',') + '×', 1500);
        break;
      }
      case 'case-return': resumeCase(); break;
      case 'toc': case 'goals': case 'settings': case 'qa': case 'cases':
        if (!drawer.hidden && drawer.dataset.kind === act) closeDrawer(); else openDrawer(act);
        break;
      case 'close-drawer': closeDrawer(); break;
      case 'fullscreen': toggleFullscreen(); break;
      case 'back-to-lesson': backToLesson(); break;
    }
  });

  $('#track').addEventListener('click', (e) => player && seekFromEvent(e));
  $('#track').addEventListener('keydown', (e) => {
    if (!player) return;
    if (e.key === 'ArrowRight') { player.next(); e.preventDefault(); }
    if (e.key === 'ArrowLeft') { player.prev(); e.preventDefault(); }
  });

  function toggleFullscreen() {
    const d = document;
    if (d.fullscreenElement || d.webkitFullscreenElement) (d.exitFullscreen || d.webkitExitFullscreen).call(d);
    else {
      const r = d.documentElement;
      const req = r.requestFullscreen || r.webkitRequestFullscreen;
      if (req) req.call(r).catch?.(() => toast('Tarayıcı tam ekrana izin vermedi.'));
      else toast('Bu cihaz tam ekranı desteklemiyor. Ana ekrana ekleyerek tam ekran açabilirsiniz.');
    }
  }

  document.addEventListener('keydown', (e) => {
    if (!player || lessonScreen.hidden) return;
    if (e.target.matches('input, select, textarea')) return;
    if (boardEl.classList.contains('case-mode')) { if (e.key === 'Escape') closeDrawer(); return; }
    if (e.key === ' ' && !e.target.matches('button')) { player.toggle(); e.preventDefault(); }
    else if (e.key === 'ArrowRight' && e.target.id !== 'track') player.next();
    else if (e.key === 'ArrowLeft' && e.target.id !== 'track') player.prev();
    else if (e.key === 'f' || e.key === 'F') toggleFullscreen();
    else if (e.key === 'r' || e.key === 'R') player.replay();
    else if (e.key === 'Escape') closeDrawer();
  });

  // Dokunmatik kaydırma: sola kaydır = sonraki, sağa kaydır = önceki.
  let touch0 = null;
  boardEl.addEventListener('touchstart', (e) => {
    if (e.touches.length === 1) touch0 = { x: e.touches[0].clientX, y: e.touches[0].clientY, t: Date.now() };
  }, { passive: true });
  boardEl.addEventListener('touchend', (e) => {
    if (!touch0 || !player) return;
    const t = e.changedTouches[0];
    const dx = t.clientX - touch0.x, dy = t.clientY - touch0.y;
    if (Math.abs(dx) > 70 && Math.abs(dx) > Math.abs(dy) * 1.5 && Date.now() - touch0.t < 800 && !boardEl.classList.contains('has-question')) {
      dx < 0 ? player.next() : player.prev();
    }
    touch0 = null;
  }, { passive: true });

  // Sekme gizlenince anlatımı durdur (telefonda arka planda konuşmasın).
  document.addEventListener('visibilitychange', () => {
    if (document.hidden && player && player.playing) player.pause();
  });

  // ---------- Çevrimdışı ----------
  if ('serviceWorker' in navigator && location.protocol.startsWith('http')) {
    navigator.serviceWorker.register('sw.js').catch((e) => console.info('Service worker kaydedilemedi:', e));
  }

  // Açılış: adres #ders-kimligi ise o dersi doğrudan aç.
  (async () => {
    const id = location.hash.slice(1) || new URLSearchParams(location.search).get('ders');
    await showHome();
    const entry = catalog.find((c) => c.id === id);
    if (entry) openLesson(entry);
  })();
})(window.AT = window.AT || {});
