import test from 'node:test';
import assert from 'node:assert/strict';
import { yukle } from './yukle.mjs';

globalThis.AT = { config: { yerel: true } };
const { yerel } = yukle('js/yerel/yerel.js', 'js/yerel/zip.js', 'js/yerel/ders-deposu.js');

const girdi = (ad, boyut = 10) => ({ ad, boyut });

test('paketiIncele: tek ders klasörü; üretilen klasörler ve işletim sistemi artıkları atlanır', () => {
  const r = yerel.paketiIncele([
    girdi('ornek/'), girdi('ornek/ders.json'), girdi('ornek/assets/fig1.png'),
    girdi('ornek/audio/a.mp3'), girdi('ornek/makale-metin/k1/sayfa-01.txt'),
    girdi('__MACOSX/ornek/._ders.json'), girdi('ornek/.DS_Store')
  ]);
  assert.equal(r.ders, 'ornek');
  assert.deepEqual(r.alinacak.map((a) => a.ic), ['ders.json', 'assets/fig1.png']);
});

test('paketiIncele: uygun olmayan paketler açıklamasıyla reddedilir', () => {
  const red = (girdiler, ileti) => assert.throws(() => yerel.paketiIncele(girdiler), { message: ileti });
  red([], 'Paket boş.');
  red([girdi('ornek/../../kotu.txt')], /güvensiz bir dosya yolu/);
  red([girdi('C:\\kotu\\ders.json')], /güvensiz bir dosya yolu/);
  red([girdi('ders.json')], /dosya kökte: ders\.json/);
  red([girdi('b/ders.json'), girdi('a/ders.json')], 'Paketin içinde tek bir ders klasörü olmalı; bulunan: a, b');
  red([girdi('kötü ad/ders.json')], 'Ders kimliği uygun değil: kötü ad');
  red([girdi('ornek/notlar.txt')], /ders\.json ya da egitmen\.json yok/);
  red([girdi('ornek/ders.json'), girdi('ornek/buyuk.bin', 501 * 1024 * 1024)], 'Paket açılınca çok büyük (en çok 500 MB).');
});

test('katalogGirisi: başlık ders.json, yoksa egitmen.json, yoksa kimlikten gelir', () => {
  assert.deepEqual(yerel.katalogGirisi('x', { title: 'Ders', level: '4. sınıf', subtitle: 'Alt', estimatedMinutes: 40 }, {}),
    { id: 'x', title: 'Ders', level: '4. sınıf', path: 'lessons/x/', subtitle: 'Alt', estimatedMinutes: 40 });
  assert.deepEqual(yerel.katalogGirisi('x', {}, { baslik: 'Eğitmen dersi', duzey: 'uzmanlık' }),
    { id: 'x', title: 'Eğitmen dersi', level: 'uzmanlık', path: 'lessons/x/' });
  assert.deepEqual(yerel.katalogGirisi('x', {}, {}), { id: 'x', title: 'x', level: null, path: 'lessons/x/' });
});
