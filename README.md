# KlinikKoç

Diş hekimliği öğrencileri için açık kaynaklı, kâr amacı gütmeyen bir **klinik akıl yürütme koçu**.
Kısa bir dersle temeli anlatır, ardından öğrenciyi dallanan klinik vakalarda adım adım karar
vermeye çalıştırır. Öğrenci bir vakada takılırsa koç, dersin ilgili bölümünü yeniden anlatıp
vakaya geri döner. Sorular not için değildir; karne yalnız öğrencinin kendi cihazında durur.

> **Durum:** 1. aşama (temel) yapım aşamasındadır. Aşağıdaki "Yol haritası"na bakın.
> Bu depo bilerek **boş** gelir: içinde yalnız genel sistem, bir tanıtım dersi ve CC BY 4.0
> lisanslı bir örnek ders (peri-implantitis) vardır. Her öğretmen kendi notunu ve vakalarını
> kendi bilgisayarında ekler; bunlar depoya girmez.

## Ne yapar?

- **Ders anlatır.** Tahtada görsel gösterir, işaretler, çizer ve Türkçe sesli anlatır.
- **Vaka çalıştırır.** Öğrenci muayene ister, bulguları yorumlar, tanı ve tedavi kararı verir,
  gerekçesini söyler. Yanlış yolda ipucu, takıldığı yerde kısa bir yeniden anlatım gelir.
- **Düşünme düzeyini izler.** Her soru ve vaka adımı bir Bloom düzeyine (hatırla, anla, uygula,
  çözümle, değerlendir, oluştur) bağlıdır. Açık uçlu cevaplar puanlama ölçütüyle (rubrik)
  değerlendirilir ve öğretmenin örnek cevabı gösterilir.
- **Karne çıkarır.** Hedef başına başarı, düşünme düzeyine göre başarı, en zorlanılan sorular,
  rubrikte en sık eksik kalanlar ve vakalardaki tehlikeli seçimler. Karne öğrencinin kendisi
  içindir; hiçbir yere gönderilmez.
- **Kaynakta arar.** Ders notu sayfalarında, anlatımda, öğretmen notlarında ve vakalarda
  hem sözcükle hem anlamla arar (çevrimdışı, bilgisayarda çalışan küçük bir model).

## İki kullanım biçimi

| | Oynatıcı | Canlı eğitmen |
|---|---|---|
| Nasıl açılır | `index.html` (tarayıcıda) | Claude masaüstü uygulaması + `KUR.bat` |
| Maliyet | Ücretsiz, internetsiz çalışır | Öğrencinin kendi Claude aboneliği; ek ücret yok, API anahtarı gerekmez |
| Ne yapar | Hazır anlatım, sorular, açık uçlu soru + öz değerlendirme, karne | Yukarıdakilere ek olarak: sohbet, sesli konuşma, dallanan vaka, rubrikle puanlama, kaynakta arama |
| Ayrıntı | [belgeler/oynatici.md](belgeler/oynatici.md) | [belgeler/canli-tahta.md](belgeler/canli-tahta.md) |

## Hızlı başlangıç

**Öğrenci (Windows):** Depoyu indirin (yeşil "Code" düğmesi → "Download ZIP"), açın.

- Yalnız oynatıcı: `index.html` dosyasına çift tıklayın.
- Canlı eğitmen: [Python](https://www.python.org/downloads/) ve Claude masaüstü uygulaması kurulu olmalı.
  `KUR.bat` dosyasına çift tıklayın, Claude uygulamasını tamamen kapatıp açın, sonra yazın:
  **"Tahtayı aç, peri-implantitis dersine başlayalım. Adım Ayşe."**

**Öğretmen:** Kendi dersinizi ve vakalarınızı eklemek için [belgeler/ogretmen-kilavuzu.md](belgeler/ogretmen-kilavuzu.md).

## Kendi içeriğiniz depoya girmez

Hasta fotoğrafları, kendi ders notlarınız ve gerçek hastalardan uyarlanmış vakalar **yalnız sizin
bilgisayarınızda** kalır:

- Adı `ozel-` ile başlayan ders klasörleri (`lessons/ozel-.../`) ve vaka kartları
  (`lessons/<ders>/vakalar/ozel-...`) ile `ozel/` klasörü git tarafından hiç görülmez.
- `python tools/yayin_denetimi.py` depoya girecek her şeyi denetler: fakülteye özel ders, denetimden
  geçmeyen vaka kartı, öğrenci kaydı ya da lisanssız görsel varsa durur. `--kanca` ile bu denetim her
  commit'ten önce kendiliğinden çalışır. GitHub'da da her yüklemede aynı denetim çalışır.

Ayrıntı: [belgeler/ozel-icerik.md](belgeler/ozel-icerik.md) ve [belgeler/anonimlestirme.md](belgeler/anonimlestirme.md).

## Yol haritası

1. **Temel** (sürüyor): vaka kartı şablonu ve denetleyicisi, SQLite karma arama, her soruya Bloom
   düzeyi ve rubrik, örnek cevap gösterimi, öğrenci cihazında karne, yayın denetimi.
2. **Öğrenci deneyimi:** kısa ders + dallanan vaka akışı, tahtada klinik karar ağacı, sözlü sınav
   provası (sesli soru-cevap, sınav tarzı geri bildirim), zayıf konuların aralıklı tekrarı.
3. **Pilot:** bir konu, üç vaka, 5–10 gönüllü öğrenci; ön test, son test, gecikmeli test.
4. **Paylaşım:** tek tıkla kurulum, kurulum sihirbazı, kısa videolar, isteğe bağlı anonim sınıf
   analizi, meslektaşlar için anonim vaka havuzu.

## Katkı

Katkılarınızı bekliyoruz: hata bildirimi, yeni bir tahta şablonu, kurgusal örnek vaka, çeviri ya da
kod. Nasıl katkı verileceği: [KATKI.md](KATKI.md).

## Lisans

- **Kod:** MIT lisansı ([LICENSE](LICENSE)).
- **İçerik** (ders metinleri, sorular, vaka kartları, belgeler): CC BY 4.0 ([LISANS-ICERIK.md](LISANS-ICERIK.md)).
- Örnek dersin kaynağı Ramanauskaite ve ark., *Periodontology 2000*, 2026, CC BY 4.0 lisanslıdır;
  Türkçe anlatım yazarların onayı anlamına gelmez. Üçüncü taraf kitaplıklar: [vendor/LISANSLAR.md](vendor/LISANSLAR.md).

KlinikKoç bir eğitim aracıdır; tanı ya da tedavi kararı için kullanılmaz.
