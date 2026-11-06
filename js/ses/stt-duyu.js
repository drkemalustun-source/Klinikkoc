/* Konuşma tanıma adaptörü: Duyu-small (Türkçe + İngilizce karışık konuşmada güçlü, Apache 2.0).
 * Model ONNX biçiminde ama onu çalıştıran motor Python'da yazılmış (özel kod çözme, üç geçişli
 * kodlayıcı, bellek tablosu). Şimdilik bu yüzden kendi bilgisayarınızda çalışan küçük bir Python
 * sunucusu (tools/sunucu.py) üzerinden kullanılıyor. Ses yine cihazdan çıkmaz: sunucu aynı
 * bilgisayarda (localhost) çalışır. İleride motor JavaScript'e taşınırsa yalnız bu dosya değişir. */
(function (AT) {
  'use strict';
  const ses = AT.ses;
  const API = ses.ROOT + 'api/duyu/';

  async function call(path, body, params) {
    const url = new URL(API + path);
    for (const [k, v] of Object.entries(params || {})) url.searchParams.set(k, v);
    const res = await fetch(url, body ? { method: 'POST', body, headers: { 'Content-Type': 'application/octet-stream' } } : { method: 'GET' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.hata) throw new Error(data.hata || ('Sunucu yanıtı: ' + res.status));
    return data;
  }

  function make(id, label, params) {
    ses.registerSTT(id, () => ({
      id,
      label,
      info: {
        offline: 'Evet',
        dataLeavesDevice: 'Hayır (sunucu aynı bilgisayarda)',
        note: 'tools/sunucu.py ile çalışır; Python gerekir.'
      },
      async status() {
        try {
          const d = await call('durum');
          return d.kurulu
            ? { ok: true, message: d.hazir ? 'Model yüklü.' : 'Python sunucusu hazır; model hazırlıkta yüklenecek.' }
            : { ok: false, message: 'Sunucu çalışıyor ama Duyu kurulu değil: ' + (d.neden || '') };
        } catch (e) {
          return { ok: false, message: 'Python sunucusu bulunamadı. Sayfayı "python3 tools/sunucu.py" ile açın.' };
        }
      },
      async init() {
        const d = await call('yukle', new Uint8Array(0), { quant: params.quant });
        return { loadMs: d.yuklemeMs, bytes: d.boyut, device: 'cpu (' + params.quant + ')' };
      },
      async transcribe(audio16k) {
        const t0 = performance.now();
        const d = await call('yaz', new Uint8Array(audio16k.buffer, audio16k.byteOffset, audio16k.byteLength), params);
        return { text: d.metin || '', ms: d.sureMs != null ? d.sureMs : performance.now() - t0, roundTripMs: performance.now() - t0 };
      }
    }));
  }

  make('duyu', 'Duyu-small (yerel sunucu)', { quant: 'int8', lang: 'mix', mode: 'auto', beam: 5 });
})(window.AT = window.AT || {});
