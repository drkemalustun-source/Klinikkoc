#!/usr/bin/env node
/* Dersleri denetler ve yayına hazırlar. Bağımlılık yok; Node 18+ yeterli.
 *
 *   node tools/paketle.mjs            açık paket (depoya giren hâli)
 *   node tools/paketle.mjs --fakulte  fakülteye özel dersleri de kataloğa ekler
 *
 * Yaptıkları:
 *  1. lessons/<id>/ders.json dosyalarını şemaya ve iç tutarlılığa göre denetler
 *     (adım kimlikleri benzersiz mi, sorular var olan alt hedeflere mi bağlı,
 *     görseller var mı, {n} işaretleri komutlarla eşleşiyor mu ...).
 *  2. Dosyadan doğrudan açma (file://) için ders.js ve katalog.js kopyalarını yazar.
 *  3. lessons/katalog.json'u üretir.
 *  4. Çevrimdışı önbellek listesini (onbellek-listesi.json) üretir. */
import { readFileSync, writeFileSync, existsSync, readdirSync, statSync } from 'node:fs';
import { join, dirname, relative } from 'node:path';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const LESSONS = join(ROOT, 'lessons');
const errors = [];
const warnings = [];
const FAKULTE = process.argv.includes('--fakulte');
const err = (l, m) => errors.push(`[${l}] ${m}`);
const warn = (l, m) => warnings.push(`[${l}] ${m}`);

// ---- Şema denetimi (JSON Schema'nın burada kullanılan alt kümesi) ----
const schema = JSON.parse(readFileSync(join(ROOT, 'schema/ders.schema.json'), 'utf8'));
function resolve(s) { return s.$ref ? schema.$defs[s.$ref.split('/').pop()] : s; }
function check(value, s, path, out) {
  s = resolve(s);
  if (s.const !== undefined && value !== s.const) out.push(`${path}: ${JSON.stringify(s.const)} olmalı`);
  if (s.enum && !s.enum.includes(value)) out.push(`${path}: ${s.enum.join('|')} değerlerinden biri olmalı (gelen: ${value})`);
  const t = s.type;
  const typeOk = !t || (t === 'array' ? Array.isArray(value)
    : t === 'integer' ? Number.isInteger(value)
    : t === 'object' ? value && typeof value === 'object' && !Array.isArray(value)
    : typeof value === t);
  if (!typeOk) { out.push(`${path}: ${t} olmalı`); return; }
  if (s.pattern && !new RegExp(s.pattern).test(value)) out.push(`${path}: biçim ${s.pattern} değil`);
  if (s.minimum !== undefined && value < s.minimum) out.push(`${path}: en az ${s.minimum}`);
  if (Array.isArray(value)) {
    if (s.minItems && value.length < s.minItems) out.push(`${path}: en az ${s.minItems} öğe`);
    if (s.items) value.forEach((v, i) => check(v, s.items, `${path}[${i}]`, out));
  } else if (value && typeof value === 'object') {
    for (const r of s.required || []) if (!(r in value)) out.push(`${path}: '${r}' eksik`);
    for (const [k, v] of Object.entries(value)) {
      if (s.properties && s.properties[k]) check(v, s.properties[k], `${path}.${k}`, out);
      else if (s.additionalProperties === false) out.push(`${path}: tanımsız alan '${k}'`);
      else if (typeof s.additionalProperties === 'object') check(v, s.additionalProperties, `${path}.${k}`, out);
    }
    for (const cond of s.allOf || []) {
      const sub = [];
      check(value, cond.if, path, sub);
      if (!sub.length) check(value, cond.then, path, out);
    }
  }
}

// ---- İç tutarlılık ----
function lint(id, lesson, dir) {
  if (lesson.id !== id) err(id, `id '${lesson.id}' klasör adıyla aynı olmalı`);
  const subgoals = new Set();
  for (const g of lesson.goals) for (const s of g.subgoals || []) {
    if (subgoals.has(s.id)) err(id, `alt hedef tekrarı: ${s.id}`);
    subgoals.add(s.id);
  }
  const covered = new Set();
  const asked = new Set();
  const stepIds = new Set();
  for (const sec of lesson.sections) {
    for (const g of sec.goals || []) {
      if (!subgoals.has(g)) err(id, `bölüm ${sec.id}: bilinmeyen alt hedef ${g}`);
      covered.add(g);
    }
    for (const st of sec.steps) {
      const where = `${sec.id}/${st.id}`;
      if (stepIds.has(st.id)) err(id, `adım kimliği tekrarı: ${st.id}`);
      stepIds.add(st.id);
      if (!st.say && !st.question && !(st.board || []).length) warn(id, `${where}: boş adım`);
      const cues = new Set([0, ...[...(st.say || '').matchAll(/\{(\d+)\}/g)].map((m) => Number(m[1]))]);
      for (const c of st.board || []) {
        if (c.cue && !cues.has(c.cue)) warn(id, `${where}: cue ${c.cue} metinde {${c.cue}} olarak geçmiyor (adım sonunda gösterilecek)`);
        if (c.asset && !(lesson.assets || {})[c.asset]) err(id, `${where}: tanımsız görsel '${c.asset}'`);
        for (const k of ['region']) if (c[k] && (c[k].length !== 4 || c[k].some((v) => v < 0 || v > 1))) err(id, `${where}: region [x,y,w,h] 0–1 aralığında olmalı`);
      }
      const q = st.question;
      if (q) {
        if (!subgoals.has(q.goal)) err(id, `${where}: soru bilinmeyen alt hedefe bağlı (${q.goal})`);
        asked.add(q.goal);
        if (q.type === 'truefalse' && typeof q.answer !== 'boolean') err(id, `${where}: truefalse sorusunda 'answer' true/false olmalı`);
        if (q.type !== 'truefalse') {
          const n = (q.options || []).filter((o) => o.correct).length;
          if ((q.options || []).length < 2) err(id, `${where}: en az iki seçenek olmalı`);
          if (q.type === 'single' && n !== 1) err(id, `${where}: tek cevaplı soruda tam bir doğru seçenek olmalı (${n} var)`);
          if (q.type === 'multiple' && n < 1) err(id, `${where}: çok cevaplı soruda en az bir doğru seçenek olmalı`);
        }
      }
    }
  }
  const miscIds = new Set((lesson.misconceptions || []).map((m) => m.id));
  for (const m of lesson.misconceptions || []) if (!subgoals.has(m.goal)) err(id, `yanılgı ${m.id}: bilinmeyen alt hedef ${m.goal}`);
  const miscOpened = new Set(), miscTargeted = new Set();
  for (const sec of lesson.sections) for (const st of sec.steps) {
    const q = st.question;
    if (!q) continue;
    for (const o of q.options || []) if (o.misconception) {
      if (!miscIds.has(o.misconception)) err(id, `${st.id}: tanımsız yanılgı ${o.misconception}`);
      miscOpened.add(o.misconception);
    }
    for (const t of q.targets || []) { if (!miscIds.has(t)) err(id, `${st.id}: tanımsız yanılgı hedefi ${t}`); miscTargeted.add(t); }
    if (q.review && !stepIds.has(q.review)) err(id, `${st.id}: 'review' bilinmeyen adıma işaret ediyor (${q.review})`);
    if (q.kind === 'application' && !q.scenario) warn(id, `${st.id}: uygulama sorusunda kurgusal olgu (scenario) yok`);
  }
  for (const m of miscIds) {
    if (!miscOpened.has(m)) warn(id, `yanılgı ${m} hiçbir çeldiriciye bağlı değil`);
    if (!miscTargeted.has(m)) warn(id, `yanılgı ${m} için kapatıcı soru (targets) yok; açılırsa hiç kapanmaz`);
  }
  const secIds = new Set(lesson.sections.map((s) => s.id));
  if (lesson.sessions) {
    const inSession = new Set();
    for (const g of lesson.sessions) for (const s of g.sections) {
      if (!secIds.has(s)) err(id, `dilim ${g.id}: bilinmeyen bölüm ${s}`);
      if (inSession.has(s)) err(id, `bölüm ${s} iki dilimde`);
      inSession.add(s);
    }
    for (const s of secIds) if (!inSession.has(s)) warn(id, `bölüm ${s} hiçbir dilimde değil`);
  }
  for (const g of subgoals) {
    if (!covered.has(g)) warn(id, `alt hedef ${g} hiçbir bölümde işlenmiyor`);
    if (!asked.has(g)) warn(id, `alt hedef ${g} için soru yok`);
  }
  for (const [k, a] of Object.entries(lesson.assets || {})) {
    if (!/^(https?:|data:)/.test(a.src) && !existsSync(join(dir, a.src))) err(id, `görsel dosyası yok: ${k} -> ${a.src}`);
  }
}

// ---- Çalıştır ----
const catalog = [];
const cacheFiles = [];
const ids = readdirSync(LESSONS).filter((d) => statSync(join(LESSONS, d)).isDirectory()).sort();
for (const id of ids) {
  const dir = join(LESSONS, id);
  const file = join(dir, 'ders.json');
  if (!existsSync(file)) continue;
  let lesson;
  try { lesson = JSON.parse(readFileSync(file, 'utf8')); }
  catch (e) { err(id, 'JSON okunamadı: ' + e.message); continue; }
  const out = [];
  check(lesson, schema, 'ders', out);
  out.forEach((m) => err(id, m));
  if (out.length) continue;
  lint(id, lesson, dir);
  // Fakülteye özel ders (telifli görseller): denetlenir ama açık pakete girmez.
  if (lesson.distribution === 'faculty' && !FAKULTE) {
    console.log(`– ${id}: fakülteye özel, açık pakete alınmadı (--fakulte ile eklenir)`);
    continue;
  }

  writeFileSync(join(dir, 'ders.js'), `/* Otomatik üretildi: tools/paketle.mjs. Düzenlemeyin; ders.json'u düzenleyin. */\nAT.registerLesson(${JSON.stringify(lesson)});\n`);
  const nSteps = lesson.sections.reduce((a, s) => a + s.steps.length, 0);
  const nQ = lesson.sections.reduce((a, s) => a + s.steps.filter((x) => x.question).length, 0);
  catalog.push({
    id, title: lesson.title, subtitle: lesson.subtitle, level: lesson.level,
    estimatedMinutes: lesson.estimatedMinutes, path: `lessons/${id}/`, steps: nSteps, questions: nQ
  });
  cacheFiles.push(`lessons/${id}/ders.json`, `lessons/${id}/ders.js`);
  for (const a of Object.values(lesson.assets || {})) if (!/^(https?:|data:)/.test(a.src)) cacheFiles.push(`lessons/${id}/${a.src}`);

  // Kaynak dizini (tools/dizin-uret.py): canlı soru-cevap ve model kapalıyken arama için.
  const idx = (lesson.knowledge && lesson.knowledge.index) || 'kaynak-dizini.json';
  if (existsSync(join(dir, idx))) {
    const d = JSON.parse(readFileSync(join(dir, idx), 'utf8'));
    for (const k of d.kaynaklar || []) if (!k.lisans) warn(id, `kaynak dizini: "${k.id}" için lisans yazılmamış`);
    writeFileSync(join(dir, idx.replace(/\.json$/, '.js')), `/* tools/paketle.mjs üretti; elle düzenlemeyin. */\nAT.registerLessonData(${JSON.stringify(id + ':dizin')}, ${JSON.stringify(d)});\n`);
    cacheFiles.push(`lessons/${id}/${idx}`, `lessons/${id}/${idx.replace(/\.json$/, '.js')}`);
  }

  if (lesson.audio && lesson.audio.manifest) {
    const mf = join(dir, lesson.audio.manifest);
    if (existsSync(mf)) {
      const m = JSON.parse(readFileSync(mf, 'utf8'));
      writeFileSync(mf.replace(/\.json$/, '.js'), `/* tools/paketle.mjs üretti; elle düzenlemeyin. */\nAT.registerAudioManifest(${JSON.stringify(id)}, ${JSON.stringify(m)});\n`);
      cacheFiles.push(`lessons/${id}/${lesson.audio.manifest}`, `lessons/${id}/${lesson.audio.manifest.replace(/\.json$/, '.js')}`);
      for (const list of Object.values(m.steps)) for (const f of list) if (f) cacheFiles.push(`lessons/${id}/${typeof f === 'string' ? f : f.src}`);
    } else warn(id, `ses manifesti yok (${lesson.audio.manifest}); tarayıcı seslendirmesi kullanılacak`);
  }
  console.log(`✓ ${id}: ${lesson.sections.length} bölüm, ${nSteps} adım, ${nQ} soru`);
}

const cat = { lessons: catalog };
writeFileSync(join(LESSONS, 'katalog.json'), JSON.stringify(cat, null, 2) + '\n');
writeFileSync(join(LESSONS, 'katalog.js'), `/* Otomatik üretildi: tools/paketle.mjs */\nAT.registerCatalog(${JSON.stringify(cat)});\n`);

const shell = ['./', 'index.html', 'config.js', 'manifest.webmanifest', 'css/tahta.css',
  'js/core.js', 'js/speech.js', 'js/anatomi.js', 'js/board.js', 'js/player.js', 'js/qa/qa.js', 'js/qa/bilgi.js', 'js/qa/saglayici-anthropic.js', 'js/qa/saglayici-ollama.js', 'js/qa/saglayici-openai.js', 'js/app.js',
  'icons/icon.svg', 'icons/icon-192.png', 'icons/icon-512.png', 'lessons/katalog.json', 'lessons/katalog.js'];
const files = [...new Set([...shell, ...cacheFiles])];
const hash = createHash('sha256');
for (const f of files) {
  const p = join(ROOT, f === './' ? 'index.html' : f);
  if (existsSync(p)) hash.update(f).update(readFileSync(p));
  else if (f !== './') warn('önbellek', `dosya yok: ${relative(ROOT, p)}`);
}
writeFileSync(join(ROOT, 'onbellek-listesi.json'), JSON.stringify({ version: hash.digest('hex').slice(0, 12), files }, null, 2) + '\n');

for (const w of warnings) console.warn('uyarı ' + w);
for (const e of errors) console.error('HATA  ' + e);
console.log(`${catalog.length} ders paketlendi, ${errors.length} hata, ${warnings.length} uyarı.`);
process.exit(errors.length ? 1 : 0);
