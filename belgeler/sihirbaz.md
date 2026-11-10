# Ders hazırlama sihirbazı

Sihirbaz, öğretmenin bir dersi dosya yazmadan, ekrandan adım adım tanımlamasını sağlar. **Sihirbaz önerir,
öğretmen onaylar**: onaylanmayan hiçbir şey derse girmez. Sonunda iki zip paketi çıkar.

Açmak için: KlinikKoç'u başlatın, ana sayfanın altındaki **Öğretmen: ders hazırlama sihirbazı** bağlantısına
basın (ya da `http://localhost:8810/sihirbaz.html`). Sayfa yalnız bu bilgisayardaki KlinikKoç sunucusuyla çalışır.

## Adımlar

1. **Ders kartı**: başlık, süre, düzey (Lisans/Uzmanlık), eğitmen (İnci lisans, Mercan uzmanlık).
2. **Makaleler**: DOI'leri ya da kaynakçayı yapıştırın. Künye, özet ve açık erişim bilgisi Crossref ve
   OpenAlex'ten gelir. İnternet yoksa makale yine eklenir; sonra **Eksik künyeleri yeniden sor**.
   Bir makale "ana kaynak" yapılabilir. Pakete makalenin kendisi değil, yalnız künyesi girer
   (bkz. [makaleler.md](makaleler.md)).
3. **Ders notu ve vakalar**: Word (.docx), PDF, .txt ya da .md not bırakın; başlıklarından (Word'de
   Başlık 1/Başlık 2 biçemi) bölümlere ayrılır. Eski .doc biçimi okunmaz, Word'de .docx olarak kaydedin.
   Vaka kartı (.json) ya da kart ve görsellerinin zip'i bırakılabilir ([vaka-karti.md](vaka-karti.md)).
4. **Sorular ve eğitimde dikkat edilecekler**: eğitmenin uyacağı notlar, bilinen yanılgılar, kendi sorularınız.
5. **Öneriler ve onay**:
   - **Hızlı öneriler (internetsiz)**: not başlıklarından hedef taslakları, fiilden Bloom düzeyi, notta geçen
     terimler, hedef başına bir açık uçlu soru. Kaba bir başlangıçtır.
   - **Claude'un önerileri**: Claude masaüstünde canlı tahta kuruluysa *"… dersi için sihirbaz önerilerini
     hazırla"* yazın. Claude notu ve makale özetlerini okur (`sihirbaz_oku`), hedef, Bloom, terim, seçmeli/açık
     soru, örnek cevap, rubrik ve yanılgı önerir (`sihirbaz_oner`). Öneriler sayfaya gelir.
   - Her öneriyi **düzeltip kabul edin** ya da **silin**.
6. **Denetle ve paketle**: eksikler kırmızı, dikkat edilecekler sarı görünür. Kırmızı kalmayınca **Paketle**.

## Paylaşım kademeleri

Her not, vaka ve soru için bir kademe seçilir:

| Kademe | Açık paket (`<ders>-acik.zip`) | Fakülte paketi (`<ders>-fakulte.zip`) | Bu bilgisayar |
|---|---|---|---|
| Herkese açık (CC BY) | var | var | var |
| Yalnız fakülte | yok | var | var |
| Hiç paylaşılmaz | yok | yok | var |

- Fakülte paketi `ozel-<ders>` adıyla kurulur ve açık depoya hiç girmez; vakaları `ozel-` önekini alır.
- Pakette olmayan not bölümleri için eğitmene "bu kısmı bu pakette okuyamıyorum" demesi söylenir.
- Paketlerken ders bu bilgisayara bütün kademeleriyle (`lessons/ozel-<ders>`) kurulur; canlı tahtada hemen
  denenebilir.

## Nerede durur?

- Taslaklar: KlinikKoç veri klasöründe `sihirbaz/<ders>/` (taslak, notların bölümleri, vakalar).
- Paketler: `Belgeler\KlinikKoç Ders Paketleri\`.

Öğrenci paketi **Makaleler ve ders paketleri** sayfasından yükler.

## Komut satırı

```
python tools/sihirbaz.py --liste
python tools/sihirbaz.py --yeni akut-lezyonlar --baslik "Akut periodontal lezyonlar"
python tools/sihirbaz.py --doi akut-lezyonlar 10.1111/jcpe.12946
python tools/sihirbaz.py --not akut-lezyonlar not.docx --kademe fakulte
python tools/sihirbaz.py --oner akut-lezyonlar
python tools/sihirbaz.py --denetle akut-lezyonlar
python tools/sihirbaz.py --paketle akut-lezyonlar
```
