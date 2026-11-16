/* Küçük zip okuyucu: ders paketlerini tarayıcıda açmak için (tools/ders_paketi.py'nin zipfile kullanımı kadar).
 * Dosya belleğe bütün alınmaz; dizin sondan okunur, her girdi kendi diliminden açılır.
 * Desteklenen: sıkıştırmasız ve deflate. ZIP64 ve parolalı paketler açık bir hatayla reddedilir. */
(function (AT) {
  'use strict';
  const yerel = AT.yerel;
  if (!yerel) return;

  const SON = 0x06054b50, MERKEZ = 0x02014b50, YEREL = 0x04034b50;

  // blob: File ya da Blob. Dönen: [{ ad, boyut, sikisik, yontem, konum, sifreli }] (klasör girdileri dahil).
  yerel.zipOku = async (blob) => {
    // Dizin sonu kaydı: 22 bayt + en çok 65535 baytlık yorum.
    const kuyruk = new DataView(await blob.slice(Math.max(0, blob.size - 65557)).arrayBuffer());
    let i = kuyruk.byteLength - 22;
    while (i >= 0 && kuyruk.getUint32(i, true) !== SON) i--;
    if (i < 0) throw new Error('Bu bir zip dosyası değil.');
    const adet = kuyruk.getUint16(i + 10, true);
    const boy = kuyruk.getUint32(i + 12, true);
    const bas = kuyruk.getUint32(i + 16, true);
    if (adet === 0xffff || boy === 0xffffffff || bas === 0xffffffff) throw new Error('Paket çok büyük (bu zip türü desteklenmiyor).');
    const d = new DataView(await blob.slice(bas, bas + boy).arrayBuffer());
    const coz = new TextDecoder('utf-8');
    const girdiler = [];
    let p = 0;
    for (let n = 0; n < adet; n++) {
      if (p + 46 > d.byteLength || d.getUint32(p, true) !== MERKEZ) throw new Error('Zip dizini bozuk.');
      const adBoy = d.getUint16(p + 28, true);
      girdiler.push({
        ad: coz.decode(new Uint8Array(d.buffer, p + 46, adBoy)),
        sifreli: (d.getUint16(p + 8, true) & 1) === 1,
        yontem: d.getUint16(p + 10, true),
        sikisik: d.getUint32(p + 20, true),
        boyut: d.getUint32(p + 24, true),
        konum: d.getUint32(p + 42, true)
      });
      p += 46 + adBoy + d.getUint16(p + 30, true) + d.getUint16(p + 32, true);
    }
    return girdiler;
  };

  // Bir girdinin açılmış içeriğini Blob olarak verir. Bildirilen boyuttan fazlası açılmaz (zip bombası).
  yerel.zipAc = async (blob, g) => {
    if (g.sifreli) throw new Error('Paket parolalı: ' + g.ad);
    const b = new DataView(await blob.slice(g.konum, g.konum + 30).arrayBuffer());
    if (b.byteLength < 30 || b.getUint32(0, true) !== YEREL) throw new Error('Paket bozuk: ' + g.ad);
    const bas = g.konum + 30 + b.getUint16(26, true) + b.getUint16(28, true);
    const ham = blob.slice(bas, bas + g.sikisik);
    if (g.yontem === 0) return ham;
    if (g.yontem !== 8) throw new Error('Desteklenmeyen sıkıştırma: ' + g.ad);
    let kalan = g.boyut;
    const sinir = new TransformStream({
      transform(parca, c) {
        kalan -= parca.byteLength;
        if (kalan < 0) c.error(new Error('Paket bozuk: ' + g.ad)); else c.enqueue(parca);
      }
    });
    let acik;
    try {
      acik = await new Response(ham.stream().pipeThrough(new DecompressionStream('deflate-raw')).pipeThrough(sinir)).blob();
    } catch (e) { throw new Error('Paket bozuk: ' + g.ad); }
    if (acik.size !== g.boyut) throw new Error('Paket bozuk: ' + g.ad);
    return acik;
  };
})(window.AT = window.AT || {});
