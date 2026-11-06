/* Karne: öğrencinin bu cihazdaki cevaplarından hesaplanır (tools/karne.py'nin tarayıcı karşılığı).
   Not için değildir; hangi hedefte güçlü olduğunu ve neyi tekrar etmesi gerektiğini gösterir. */
(function (AT) {
  'use strict';

  const BLOOM = ['hatirla', 'anla', 'uygula', 'cozumle', 'degerlendir', 'olustur'];
  const BLOOM_AD = { hatirla: 'Hatırla', anla: 'Anla', uygula: 'Uygula', cozumle: 'Çözümle', degerlendir: 'Değerlendir', olustur: 'Oluştur' };
  AT.BLOOM = BLOOM;
  AT.BLOOM_AD = BLOOM_AD;

  const ratio = (p, m) => (m ? p / m : null);
  const pct = (x) => (x == null ? '–' : '%' + Math.round(x * 100));
  const difficulty = (p) => (p == null ? '–' : p >= 0.8 ? 'kolay' : p >= 0.5 ? 'orta' : 'zor');
  // Eski kayıtlarda puan alanı yok: doğruysa 1/1, yanlışsa 0/1 sayılır.
  const score = (a) => (a.score != null ? a.score : a.correct ? 1 : 0);
  const max = (a) => a.max || 1;

  AT.karne = (lesson, data) => {
    const steps = {};
    const goalBloom = {};
    for (const g of lesson.goals || []) for (const s of g.subgoals || []) goalBloom[s.id] = s.bloom;
    for (const sec of lesson.sections) for (const st of sec.steps) if (st.question) steps[st.id] = { q: st.question, sec };
    const attempts = (data.attempts || []).filter((a) => steps[a.step]);
    const sum = (xs, f) => xs.reduce((t, x) => t + f(x), 0);

    const goals = [];
    for (const g of lesson.goals || []) for (const sg of g.subgoals || []) {
      const as = attempts.filter((a) => a.goal === sg.id);
      const firsts = {};
      for (const a of as) if (!(a.step in firsts)) firsts[a.step] = a;
      const f = Object.values(firsts);
      goals.push({
        id: sg.id, text: sg.text, bloom: sg.bloom, n: as.length,
        rate: ratio(sum(as, score), sum(as, max)),
        first: f.length ? f.filter((a) => score(a) >= max(a)).length / f.length : null
      });
    }

    const bloom = [];
    for (const b of BLOOM) {
      const as = attempts.filter((a) => (a.bloom || steps[a.step].q.bloom || goalBloom[a.goal]) === b);
      if (as.length) bloom.push({ level: b, n: as.length, rate: ratio(sum(as, score), sum(as, max)) });
    }

    const items = {};
    for (const a of attempts) {
      const it = items[a.step] || (items[a.step] = { step: a.step, prompt: steps[a.step].q.prompt, goal: a.goal, type: steps[a.step].q.type, n: 0, p: 0, m: 0, hints: 0, firstOk: null });
      it.n++; it.p += score(a); it.m += max(a); it.hints += a.hints || 0;
      if (it.firstOk == null) it.firstOk = score(a) >= max(a);
    }
    const itemList = Object.values(items).map((it) => Object.assign(it, { rate: ratio(it.p, it.m) }))
      .sort((x, y) => x.rate - y.rate);

    const missed = {};
    for (const a of attempts) for (const c of a.missed || []) missed[c] = (missed[c] || 0) + 1;

    const total = ratio(sum(attempts, score), sum(attempts, max));
    return {
      total, n: attempts.length, goals, bloom, items: itemList,
      missed: Object.entries(missed).sort((x, y) => y[1] - x[1]).slice(0, 8),
      strong: goals.filter((g) => g.n >= 2 && g.rate >= 0.8).map((g) => g.id),
      weak: goals.filter((g) => g.n >= 1 && g.rate != null && g.rate < 0.6).map((g) => g.id),
      untested: goals.filter((g) => !g.n).map((g) => g.id)
    };
  };

  AT.karneMarkdown = (lesson, k) => {
    const L = [
      '# Karne: ' + lesson.title, '',
      'Tarih: ' + new Date().toLocaleString('tr-TR') + ' · Cevap sayısı: ' + k.n + ' · Genel başarı: ' + pct(k.total), '',
      '> Bu karne not için değildir. Yalnız bu cihazda hesaplandı ve hiçbir yere gönderilmedi.', ''
    ];
    if (k.weak.length) L.push('Geliştirilecek hedefler: ' + k.weak.join(', '), '');
    if (k.strong.length) L.push('Güçlü hedefler: ' + k.strong.join(', '), '');
    L.push('## Hedefler', '', '| Alt hedef | Hedef düzey | Cevap | Başarı | İlk denemede tam |', '|---|---|---|---|---|');
    for (const g of k.goals) L.push(`| ${g.id} ${g.text} | ${BLOOM_AD[g.bloom] || '–'} | ${g.n} | ${pct(g.rate)} | ${pct(g.first)} |`);
    if (k.bloom.length) {
      L.push('', '## Düşünme düzeyine göre (Bloom)', '', '| Düzey | Cevap | Başarı |', '|---|---|---|');
      for (const b of k.bloom) L.push(`| ${BLOOM_AD[b.level]} | ${b.n} | ${pct(b.rate)} |`);
    }
    if (k.items.length) {
      L.push('', '## Soru güçlüğü (senin cevaplarına göre)', '', '| Soru | Hedef | Deneme | p | Güçlük | İpucu |', '|---|---|---|---|---|---|');
      for (const it of k.items) L.push(`| ${it.prompt.replace(/\|/g, '/').slice(0, 80)} | ${it.goal} | ${it.n} | ${it.rate == null ? '–' : it.rate.toFixed(2)} | ${difficulty(it.rate)} | ${it.hints} |`);
    }
    if (k.missed.length) {
      L.push('', '## Açık uçlu cevaplarda en sık eksik kalanlar', '');
      for (const [c, n] of k.missed) L.push(`- ${c} (${n} kez)`);
    }
    return L.join('\n') + '\n';
  };

  AT.karneHelpers = { pct, difficulty };
})(window.AT = window.AT || {});
