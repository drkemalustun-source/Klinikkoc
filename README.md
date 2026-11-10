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
| Nasıl açılır | `index.html` (tarayıcıda) | Claude masaüstü uygulaması + `KUR-Windows.bat` ya da `KUR-Mac.command` |
| Maliyet | Ücretsiz, internetsiz çalışır | Öğrencinin kendi Claude aboneliği; ek ücret yok, API anahtarı gerekmez |
| Ne yapar | Hazır anlatım, sorular, açık uçlu soru + öz değerlendirme, karne | Yukarıdakilere ek olarak: sohbet, sesli konuşma, dallanan vaka, rubrikle puanlama, kaynakta arama |
| Ayrıntı | [belgeler/oynatici.md](belgeler/oynatici.md) | [belgeler/canli-tahta.md](belgeler/canli-tahta.md) |

## Hızlı başlangıç

**Öğrenci (Windows ya da Mac):** Depoyu indirin (yeşil "Code" düğmesi → "Download ZIP"), açın.

- Yalnız oynatıcı: `index.html` dosyasına çift tıklayın.
- Canlı eğitmen: [Python](https://www.python.org/downloads/) ve Claude masaüstü uygulaması kurulu olmalı.
  `KUR-Windows` dosyasına çift tıklayın, Claude uygulamasını tamamen kapatıp açın, sonra yazın:
  **"Tahtayı aç, peri-implantitis dersine başlayalım. Adım Ayşe, numaramın son üç hanesi 123."**
  Windows dosya uzantılarını gizleyebilir; adı yalnız **KUR-Windows** görünen dosyaya çift tıklayın.
  Başarıyı denetlemek için: Claude'da **Ayarlar › Geliştirici** ekranında "klinik-koc" **Çalışıyor** görünmeli.
- Ses: KUR, doğal Türkçe kadın sesini (~1 GB) isteğe bağlı kurar; kurulmazsa daha basit bir yedek ses kullanılır.
  Hangi sesin çaldığı tahtanın üst çubuğunda yazar.
- Mac'te `KUR-Windows` yerine `KUR-Mac` dosyasına çift tıklayın. macOS ilk açılışta "geliştiricisi doğrulanamadı"
  derse dosyaya sağ tıklayıp **Aç → Aç** deyin. Python 3 yoksa kurulum bunu söyler
  ([python.org](https://www.python.org/downloads/macos/)). Claude'u kapatmak için Cmd+Q.

**Öğretmen:** Dersi ekrandan adım adım hazırlamak için ders hazırlama sihirbazı: [belgeler/sihirbaz.md](belgeler/sihirbaz.md).
Dosyaları elle yazmak isterseniz [belgeler/ogretmen-kilavuzu.md](belgeler/ogretmen-kilavuzu.md).

**Makaleler ve ders paketleri:** Ders paketinde makalelerin yalnız listesi (künye ve DOI) vardır; KlinikKoç
makaleleri öğrencinin bilgisayarına kendisi indirir, inmeyenleri öğrenci sürükleyip bırakır. Ayrıntı:
[belgeler/makaleler.md](belgeler/makaleler.md).

## Öğrenci kayıtları nerede, nasıl silinir?

Kayıtlarınız (ilerlemeniz, karneleriniz, raporlarınız) **yalnız bu bilgisayarda** durur. Program
onları hiçbir yere kendiliğinden göndermez; internete de çıkarmaz. Program klasörünün dışında
tutulur, bu yüzden programın yeni sürümünü indirip eskisini sildiğinizde kayıtlarınız kaybolmaz.

| Bilgisayar | Kayıt klasörü |
|---|---|
| Mac | `~/Library/Application Support/KlinikKoc/kayitlar` (Finder → Git → Klasöre Git… yazıp yapıştırın) |
| Windows | `%APPDATA%\KlinikKoc\kayitlar` (Dosya Gezgini'nin adres çubuğuna yazın) |

- İlk girişte koç adınızı ve kısa bir ayırt ediciyi (öğrenci numaranızın son 3 hanesi ya da bir
  takma ad) sorar. Böylece aynı adlı iki öğrencinin kaydı karışmaz. Her öğrencinin kendi klasörü olur.
- Her kayıt önce geçici bir dosyaya yazılır, sonra yerine konur; önceki 5 sürüm `yedekler/`
  klasöründe saklanır. Bir dosya bozulursa (ör. elektrik kesilirse) en yeni yedekten açılır.
- Eski sürümlerde kayıtlar program klasöründeki `kayitlar/` içindeydi. Yeni sürüm ilk açılışta
  onları bir kez yeni yere kopyalar; eski dosyalara dokunmaz.
- **Başka bilgisayara taşımak:** Claude'a "kayıtlarımı dışa aktar" deyin; masaüstüne tek bir dosya
  yazılır. Öbür bilgisayarda "şu dosyadaki kayıtlarımı içe al" deyin (ya da
  `python tools/kayit_aktar.py ice <dosya>`).
- **Silmek:** Claude'u kapatın ve yukarıdaki klasörü (ya da içindeki kendi adınızla başlayan
  klasörü) çöp kutusuna atın. Hepsi budur; başka bir yerde kopyası yoktur.
- **Öğretmen denemesi:** Öğretmen kendini denerken adını "deneme" verir; bu kayıtlar karnede
  "DENEME KAYDI" diye görünür ve araştırma aktarımına katılmaz.
- **Araştırma için (öğretmen):** `python tools/kayit_aktar.py anonim --dosya <öğrencilerin gönderdiği dosyalar>`
  ad, numara ve serbest metin içermeyen tek bir dosya üretir; öğrenciye rastgele kod verilir, tarih
  yerine gün farkı yazılır ([belgeler/anonimlestirme.md](belgeler/anonimlestirme.md) ile uyumlu).
  Öğrenci kendi dosyasını öğretmene yalnız isterse kendisi verir.
- Kayıt yerini değiştirmek isteyen ileri kullanıcılar `KLINIK_KOC_KAYIT` ortam değişkenini kullanabilir.

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
