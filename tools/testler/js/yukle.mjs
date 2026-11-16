/* Tarayıcı için yazılmış dosyaları ((function (AT) {…})(window.AT = …) üslubu) Node testlerinde yükler.
 * Kaynak dosyalar değişmez: window, genel nesnenin kendisi yapılır ve dosya o bağlamda çalıştırılır.
 * Çalıştırma: python3 -m unittest tools/testler/test_js.py   (ya da: node --test tools/testler/js/*.test.mjs) */
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

export const KOK = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..');

globalThis.window = globalThis;

export function yukle(...dosyalar) {
  for (const d of dosyalar) vm.runInThisContext(readFileSync(join(KOK, d), 'utf8'), { filename: d });
  return globalThis.AT;
}
