/* Kurulum ayarları. Öğrencinin değiştirmesi gerekmez. */
window.AT = window.AT || {};
window.AT.config = {
  appName: 'KlinikKoç',
  version: '5.0.0',  // kök klasördeki SURUM dosyasıyla aynı olmalı (testler denetler)
  // Web sürümü: yerel sunucu (tools/sunucu.py) yoktur; /api/ çağrıları tarayıcıdaki modüllere (js/yerel/) gider.
  yerel: true,
  // Canlı soru-cevabın başlangıç ayarları (bkz. js/qa/qa.js). Öğrenci Ayarlar'dan değiştirebilir.
  // API anahtarı buraya YAZILMAZ; her kullanıcı kendi anahtarını uygulamada girer.
  // Örn. fakültede Ollama sunucusu varsa: defaults: { mode: 'local', baseURLs: { ollama: 'https://sunucu.ornek' } }
  qa: {
    defaults: {}
  }
};
