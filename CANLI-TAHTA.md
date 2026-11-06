# Canlı tahta: Claude'un yönettiği tahta

Claude masaüstü uygulaması, sizin Claude aboneliğinizle bu bilgisayardaki tahtayı canlı yönetir.
API anahtarı gerekmez, ek ücret yoktur. Aboneliğinizin kullanım sınırları geçerlidir; uzun bir
canlı derste sınıra yaklaşılabilir. İnternet gerekir (Claude bulutta çalışır). Ses ve görseller
bilgisayarınızda üretilir ve gösterilir.

## Nasıl çalışır

```
Claude masaüstü  →  tools/tahta-mcp.py  →  tools/sunucu.py (localhost:8800)  →  canli.html (tarayıcı)
 (siz yazarsınız)    (tahta araçları)       (komut kuyruğu, Piper sesi)          (tahta + ses + soru kartı)
```

- `tahta-mcp.py` Claude'a tahtayı yönetecek araçlar verir. Claude uygulaması onu kendisi başlatır.
- `sunucu.py` komutları tahtaya iletir; yalnızca bu bilgisayarın içinden erişilir (127.0.0.1).
  Başka bir web sitesinden gelen istekleri reddeder.
- `canli.html` komutları ders dosyalarındaki tahta komutlarıyla aynı biçimde çizer (`js/board.js`).

## Kurulum (bir kez)

1. Bu klasörde bir komut istemi açın (klasörün adres çubuğuna `cmd` yazıp Enter).
2. `python tools/tahta-mcp.py --kur` yazın. Claude'un ayar dosyasına "akilli-tahta" eklenir
   (eski ayar `.yedek` olarak saklanır).
3. Claude masaüstü uygulamasını **tamamen** kapatın: saatin yanındaki Claude simgesine sağ tık → Çık (Quit).
   Yeniden açın.
4. Yeni bir sohbette yazın: **"Tahtayı aç ve bana Şekil 2'yi anlat."**
   Claude araçları ilk kullanırken izin ister; "Her zaman izin ver" demeniz işinizi kolaylaştırır.
5. Tarayıcıda canlı tahta açılır. Bir kez **"Tam ekran başlat"**a dokunun (tarayıcı, sesin çalması için bunu ister).

Denetim: `python tools/tahta-mcp.py --dene` dersleri ve araçları listeler.
Kaldırma: `python tools/tahta-mcp.py --kaldir`.

## Claude'un araçları

| Araç | Ne yapar |
|---|---|
| `egitmen_hazirla` | Dersin eğitmenini (İnci ya da Mercan), kurallarını, hedeflerini ve öğrencinin kaydını yükler |
| `kayit_yaz` / `kayit_oku` | Öğrencinin ilerlemesini bu bilgisayardaki `kayitlar/` klasörüne yazar ve okur |
| `rapor_yaz` | Öğretmen için Markdown rapor yazar (`kayitlar/<ad>/raporlar/`) |
| `olcme_testi` / `olcme_kaydet` | Öğretmenin onayladığı pilot testi (ön / son / gecikmeli) seçenekleri karıştırarak verir; yanıtları puanlayıp kayda yazar |
| `tahtayi_ac` | Yerel sunucu kapalıysa açar, tahta sayfasını açar ve bağlanmasını bekler |
| `dersler` | Bilgisayardaki dersleri, bölümlerini ve görsellerini listeler |
| `ders_oku` | Ders planını ya da bir bölümün anlatımını, tahta komutlarını ve sorularını okur |
| `gorsel_bak` | Ders görselini Claude'a gösterir (işaretleyeceği yeri seçmek için) |
| `tahta` | Adım adım: önce tahtaya yazar/çizer, sonra o adımı sesli anlatır |
| `soru_sor` | Tahtada soru kartı açar, dokunduğunuz cevabı Claude'a iletir |
| `tahta_durumu` | Tahtanın durumu; süren bir anlatımın ya da sorunun bitmesini bekler |
| `dinle` | Mikrofon tuşuyla söylediğinizi bekler ve yazı olarak alır (sesli sohbet) |
| `durdur` | Anlatımı hemen keser |

Tahta komutları: başlık, madde, terim, not, tablo, akış, karşılaştırma, ders görseli,
görselde işaretleme ve yakınlaştırma, serbest çizim (çizgi, ok, kutu, elips, yazı).

## Eğitmenler: İnci ve Mercan

Her dersin bir eğitmeni vardır; hangisi olduğunu dersin `egitmen.json` dosyası belirler.

- **İnci** lisans dersleri içindir: ders kitabı dili, kısa turlar, "bilmiyorum" denince önce anlatır,
  klinik akıl yürütmeyi (karşılaştır-ayır, karışık olgular) çalıştırır.
- **Mercan** uzmanlık içindir: makale inceleme, kanıt düzeyi, yöntem ve istatistik tartışması.

İkisinin ortak kuralları `egitmenler/ortak.md`, kişilikleri `egitmenler/inci.md` ve `egitmenler/mercan.md`
dosyalarındadır. Ortak kurallar: kaynağın dışına çıkmamak, öğretmen notlarına uymak, Bloom basamaklarıyla
soru seçmek, açık uçlu yanıtı SOLO'ya göre değerlendirmek, yalnız olgu sorularında "ne kadar eminsin?" diye
sormak, cevabı erken vermemek, ısrara boyun eğmemek, mola/devam ve rapor.

Başlamak için Claude'a yazın: **"Tahtayı aç, akut periodontal lezyonlar dersine başlayalım. Adım Ayşe."**
Claude önce eğitmeni yükler, kaydınızda tekrar zamanı gelen konu varsa kısa bir tekrarla başlar.

Öğrenci kaydı ve raporlar yalnız bu bilgisayardaki `kayitlar/` klasöründe durur; hiçbir yere gönderilmez.
Rapor, öğrenci isterse öğretmenine kendisi tarafından iletilir.

## Sesli sohbet (dikte)

Tahtanın üst çubuğunda **mikrofon** tuşu var (klavyede **M**).

1. Tuşa dokunun ve konuşun. Söyledikleriniz altyazıda görünür.
2. 2,5 saniye susunca konuşmanız Claude'a gönderilir (ya da tuşa yeniden dokunun).
3. Claude tahtada sesli cevap verir, sonra sizi yeniden dinler.

- Tahta konuşurken tuşa dokunmak anlatımı keser: söz almış olursunuz.
- Konuşma tanıma tarayıcının kendi Türkçe tanıyıcısıdır (Chrome/Edge). İnternet gerekir;
  ses yazıya çevrilmek için Google'a (Edge'de Microsoft'a) gider. Firefox'ta çalışmaz.
- İlk kullanımda tarayıcı mikrofon izni ister; "İzin ver" deyin.
- Claude yalnızca bir iş yaparken dinler. Uzun süre konuşmazsanız dinlemeyi bırakır; o zaman
  sohbete bir mesaj yazmanız (ya da dikteyle söylemeniz) yeterli. Bu arada söyledikleriniz
  kaybolmaz, Claude ilk fırsatta görür.

## Kullanım ipuçları

- Konuyu siz seçersiniz: "Defekt morfolojisi bölümünü 10 dakikada anlat", "Şekil 4'teki farkı göster",
  "Bana bu bölümden iki soru sor", "Daha yavaş anlat", "Bu kısmı tahtaya çizerek anlat".
- **Duraklat** (⏸, mikrofonun yanında; klavyede **P** ya da **Boşluk**): anlatımı kısa süre bekletir.
  Hiçbir şey iptal olmaz; ses olduğu yerde durur, sıradaki adımlar bekler ve ekranda "Duraklatıldı"
  yazar. Yeniden basınca (▶) aynı cümlenin kaldığı yerinden sürer. Tuş yalnız anlatım sürerken
  etkindir (soru kartında ve mikrofon dinlerken sönüktür). Claude bu sırada "duraklatildi" görür ve
  bekler. Duraklatılmışken mikrofona, kare düğmeye ya da Esc'e basmak anlatımı keser (duraklama kalkar).
- Tahtadaki **kare** düğme ya da **Esc** anlatımı keser. **F** tam ekran. Hız düğmesi 1,0 / 1,2 / 1,4.
- Sesi bu bilgisayardaki Pocket TTS Türkçe kadın 3 sesi üretir (ayar: `ses/ses-ayari.json`). Sunucu
  açılırken ~10–30 sn yüklenir; o sırada ya da hata olursa Piper dfki, o da yoksa tarayıcının Türkçe sesi.
- Bu mod öğretim üyesi içindir. Öğrenci sürümü (index.html) değişmedi; öğrenciye maliyet yine sıfırdır.

## Sorun giderme

| Belirti | Çözüm |
|---|---|
| Claude'da "akilli-tahta" araçları görünmüyor | Claude'u sistem tepsisinden tamamen kapatıp açın; `--kur` komutunu yeniden çalıştırın |
| "Tahta sayfası açık değil" | Claude'a "tahtayı aç" deyin ya da tarayıcıda `http://localhost:8800/canli.html` açın |
| Yazılar geliyor, ses yok | Tahtada "başlat" düğmesine dokunun; bilgisayarın sesini denetleyin |
| Sol üstteki nokta kırmızı | Sunucu penceresi kapanmış; Claude'a "tahtayı aç" deyin |
