/* Kurulum ayarları. Öğrencinin değiştirmesi gerekmez. */
window.AT = window.AT || {};
window.AT.config = {
  appName: 'KlinikKoç',
  version: '3.2.0',  // kök klasördeki SURUM dosyasıyla aynı olmalı (testler denetler)
  // Canlı soru-cevabın başlangıç ayarları (bkz. js/qa/qa.js). Öğrenci Ayarlar'dan değiştirebilir.
  // API anahtarı buraya YAZILMAZ; her kullanıcı kendi anahtarını uygulamada girer.
  // Örn. fakültede Ollama sunucusu varsa: defaults: { mode: 'local', baseURLs: { ollama: 'https://sunucu.ornek' } }
  qa: {
    defaults: {}
  }
};
