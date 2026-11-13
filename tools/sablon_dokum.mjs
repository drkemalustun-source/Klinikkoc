// Şablonların parça ve varyant dökümü → tools/sablonlar.json (geliştirici aracı; Playwright ister).
// Şablon dosyaları (js/anatomi*.js) değişince çalıştırılır: node tools/sablon_dokum.mjs
// MCP sunucusu bu dökümle bilinmeyen varyant/parça adlarını uyarır ve sablon_bilgisi aracını yanıtlar.
import { createRequire } from 'node:module';
const { chromium } = createRequire(import.meta.url)('playwright');
import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const kok = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const b = await chromium.launch();
const s = await b.newPage();
await s.setContent('<!doctype html><meta charset="utf-8"><body></body>');
for (const d of ['anatomi.js', 'anatomi-bolge.js', 'anatomi-kontur.js']) await s.addScriptTag({ path: path.join(kok, 'js', d) });
const dokum = await s.evaluate(() => {
  const NS = 'http://www.w3.org/2000/svg';
  const out = {};
  const S = window.AT.anatomi.SABLONLAR;
  for (const k of Object.keys(S)) {
    const parcalar = {}, ayrinti = [], gorulen = {};
    for (const v of S[k].varyantlar) {
      const p = S[k].ciz(document.createElementNS(NS, 'g'), v, { probe: true, olcu: false }) || {};
      for (const id of Object.keys(p)) {
        if (!(id in parcalar)) { parcalar[id] = p[id].ad; if (p[id].ayrinti) ayrinti.push(id); }
        (gorulen[id] = gorulen[id] || []).push(v);
      }
    }
    const yalniz = {};
    for (const id of Object.keys(gorulen)) if (gorulen[id].length < S[k].varyantlar.length) yalniz[id] = gorulen[id];
    out[k] = { ad: S[k].ad, varyantlar: S[k].varyantlar, parcalar, ayrinti, yalniz };
  }
  return out;
});
await b.close();
writeFileSync(path.join(kok, 'tools', 'sablonlar.json'), JSON.stringify(dokum, null, 1) + '\n');
console.log(Object.keys(dokum).length + ' şablon → tools/sablonlar.json');
