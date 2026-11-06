# KlinikKoç'a katkı

Teşekkürler! KlinikKoç gönüllülerle gelişen, kâr amacı gütmeyen bir eğitim projesidir.

## Nasıl katkı verebilirsiniz?

- **Hata bildirin ya da öneri yazın:** GitHub'da "Issues" sekmesi. Ne yaptığınızı, ne beklediğinizi ve ne
  olduğunu yazın; ekran görüntüsü çok yardımcı olur.
- **Kurgusal örnek vaka:** `sablonlar/vaka-karti-bos.json`'dan başlayın, `"kurgusal": true` ve
  `"dagitim": "acik"` yazın, `python tools/vaka_denetle.py` ile denetleyin. Gerçek hasta bilgisi
  **göndermeyin**; gerçek vakalar yalnız kendi fakültenizde kalır.
- **Tahta şablonu** (ör. furkasyon, kemik içi defekt duvarları): `js/anatomi.js`.
- **Kod:** küçük ve tek amaçlı değişiklikler (pull request) en kolay incelenir.

## Kurallar

1. **Hasta verisi yok.** Ad, tarih, fotoğraf, radyografi, gerçek vaka göndermeyin. Yayın denetimi
   bunları büyük ölçüde yakalar ama son sorumluluk gönderendedir.
2. **Telifli içerik yok.** Ders kitabından görsel ya da metin eklemeyin. Yalnız açık lisanslı (CC BY, CC0)
   kaynaklar; her görselde `credit` alanına kaynak ve lisansı yazın.
3. Göndermeden önce:
   ```sh
   python tools/yayin_denetimi.py
   node tools/paketle.mjs
   python tools/vaka_denetle.py
   python -m unittest discover -s tools/testler
   ```
4. Arayüz ve belgeler Türkçedir. Kodda Türkçe adlar kullanılır (`ders`, `vaka`, `karne` ...).
5. Klinik içerik öğretmen onayından geçmeden "onaylandı" diye işaretlenmez.

Katkılarınız MIT (kod) ve CC BY 4.0 (içerik) lisansıyla yayımlanır.
