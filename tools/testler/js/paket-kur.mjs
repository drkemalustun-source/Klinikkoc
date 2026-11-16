/* Eşlik testi yardımcısı (tools/testler/test_js.py çağırır): bir ya da birkaç zip'i sırayla tarayıcı koduyla kurar,
 * sonucu JSON olarak yazar. Kullanım: node paket-kur.mjs [--uzerine] <paket.zip> [<paket2.zip> ...]
 * Çıktı: { hata } ya da { ders, incelenen: [yol], sonuc, katalog, dosyalar: { yol: sha256 } } */
import { createHash } from 'node:crypto';
import { openAsBlob } from 'node:fs';
import { sahteDepo } from './sahte-depo.mjs';
import { yukle } from './yukle.mjs';

const depolar = sahteDepo();
globalThis.AT = { config: { yerel: true } };
const AT = yukle('js/yerel/yerel.js', 'js/yerel/zip.js', 'js/yerel/ders-deposu.js');

const secenek = { uzerine: process.argv.includes('--uzerine') };
const zipler = process.argv.slice(2).filter((a) => !a.startsWith('--'));
let cikti;
try {
  let sonuc, incelenen;
  for (const yol of zipler) {
    const dosya = await openAsBlob(yol);
    incelenen = AT.yerel.paketiIncele(await AT.yerel.zipOku(dosya)).alinacak.map((a) => a.ic);
    sonuc = await AT.yerel.dersKur(dosya, secenek);
  }
  const kok = 'https://ornek.test/kk/lessons/' + sonuc.ders + '/';
  const dosyalar = {};
  for (const [adres, yanit] of depolar.get('kk-ders-' + sonuc.ders)) {
    const veri = Buffer.from(await yanit.clone().arrayBuffer());
    dosyalar[decodeURIComponent(adres.slice(kok.length))] = createHash('sha256').update(veri).digest('hex');
  }
  cikti = { ders: sonuc.ders, incelenen, sonuc, katalog: await AT.yerel.katalog(), dosyalar };
} catch (e) {
  cikti = { hata: e.message, kod: e.kod || null };
}
process.stdout.write(JSON.stringify(cikti));
