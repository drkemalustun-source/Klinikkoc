# Canlı tahta: Claude'un yönettiği eğitmen

Claude masaüstü uygulaması, sizin Claude aboneliğinizle bu bilgisayardaki tahtayı canlı yönetir.
API anahtarı gerekmez, ek ücret yoktur. Aboneliğinizin kullanım sınırları geçerlidir; uzun bir
canlı derste sınıra yaklaşılabilir. İnternet gerekir (Claude bulutta çalışır). Ses ve görseller
bilgisayarınızda üretilir ve gösterilir.

## Nasıl çalışır

```
Claude masaüstü  →  tools/tahta-mcp.py  →  tools/sunucu.py (localhost:8810)  →  canli.html (tarayıcı)
 (siz yazarsınız)    (tahta araçları)       (komut kuyruğu, Piper sesi)          (tahta + ses + soru kartı)
```

- `tahta-mcp.py` Claude'a tahtayı yönetecek araçlar verir. Claude uygulaması onu kendisi başlatır.
- `sunucu.py` komutları tahtaya iletir; yalnızca bu bilgisayarın içinden erişilir (127.0.0.1).
  Başka bir web sitesinden gelen istekleri reddeder.
- `canli.html` komutları ders dosyalarındaki tahta komutlarıyla aynı biçimde çizer (`js/board.js`).

## Kurulum (bir kez)

1. Klasördeki **KUR-Windows** dosyasına çift tıklayın (Mac'te **KUR-Mac**). Windows dosya uzantılarını
   gizleyebilir; dosyanın adı yalnız "KUR-Windows" görünebilir. Kurulum üç adımdır:
   1. Piper ses paketleri ve yedek ses dosyası (~63 MB).
   2. Claude'un ayar dosyasına "klinik-koc" eklenir (eski ayar `.yedek` olarak saklanır). Kurulum,
      Claude'un **gerçekten okuduğu** dosyayı bulur: Microsoft Store sürümünde
      `%LOCALAPPDATA%\Claude-Data\claude_<paket>\claude_desktop_config.json`, .exe sürümünde
      `%APPDATA%\Claude\`, Mac'te `~/Library/Application Support/Claude/`. Claude'un artık okumadığı eski
      yerler "atlandı" diye yazılır.
   3. İsteğe bağlı doğal Türkçe kadın sesi (Pocket, ~1 GB indirme). Kurulum sorar (E/H). Pocket,
      Python 3.10–3.13 ister; kurulum uygun sürümü kendi arar (bilgisayardaki Python 3.14 ise başka bir sürüm
      ya da `uv` aranır). Bulamazsa "python.org'dan 3.12 kurun" der; o zamana kadar yedek ses kullanılır.
      Kurulumun sonunda Pocket kısa bir cümle söyler; sesi duyuyorsanız hazırdır.
2. Claude masaüstü uygulamasını **tamamen** kapatın: saatin yanındaki **^** → Claude simgesi → sağ tık → **Çık**
   (Mac'te Cmd+Q). Yeniden açın.
3. **Denetim:** Claude'da **Ayarlar › Geliştirici** ekranında "klinik-koc" **Çalışıyor** görünmeli.
4. Yeni bir sohbette yazın: **"Tahtayı aç ve bana Şekil 2'yi anlat."**
   Claude araçları ilk kullanırken izin ister; "Her zaman izin ver" demeniz işinizi kolaylaştırır.
5. Tarayıcıda canlı tahta açılır. Bir kez **"Tam ekran başlat"**a dokunun (tarayıcı, sesin çalması için bunu ister).

Komutla kurulum (aynı adımlar): `python tools/ses-uret.py --kur`, `python tools/tahta-mcp.py --kur`,
`python tools/ses-uret.py --kur-pocket`. Pocket kurulu mu: `--pocket-durum`; sesi dene: `--dene-pocket`.

Denetim: `python tools/tahta-mcp.py --dene` dersleri, araçları ve bulduğu her Claude ayar dosyasını
("asıl" / "eski") listeler; Claude'un okuduğu dosyada "klinik-koc" yoksa açıkça uyarır.
Ayar dosyası bulunamazsa: Claude'da **Ayarlar › Geliştirici › "Yapılandırmayı düzenle"**ye basın, açılan dosyanın
yolunu kopyalayıp `python tools/tahta-mcp.py --kur --ayar "<yol>"` yazın.
Kaldırma: `python tools/tahta-mcp.py --kaldir` (gerekirse `--ayar "<yol>"` ile).

## Claude'un araçları

| Araç | Ne yapar |
|---|---|
| `egitmen_hazirla` | Dersin eğitmenini (İnci ya da Mercan), kurallarını, hedeflerini ve öğrencinin kaydını yükler |
| `kayit_yaz` / `kayit_oku` | Öğrencinin ilerlemesini, her cevabın Bloom düzeyini ve rubrik puanını bu bilgisayardaki kalıcı kayıt klasörüne yazar ve okur (bkz. README, "Öğrenci kayıtları") |
| `bilgi_ara` | Derslerin kaynak sayfalarında, anlatımında, öğretmen notlarında ve vakalarında arar (sözcük + isteğe bağlı anlam araması; bkz. [bilgi-bankasi.md](bilgi-bankasi.md)) |
| `vakalar` / `vaka_oku` | Dersin vaka kartlarını listeler; bir vakayı eğitmen için açar (bkz. [vaka-karti.md](vaka-karti.md)) |
| `karne` | Öğrencinin karnesini hesaplar: hedef ve Bloom düzeyine göre başarı, soru güçlüğü, vaka sonuçları |
| `rapor_yaz` | Öğretmen için Markdown rapor yazar (kayıt klasöründe `<kimlik>/raporlar/`) |
| `kayit_disa_aktar` / `kayit_ice_aktar` | Öğrencinin bütün kaydını tek dosyaya yazar / başka bilgisayarda içe alır |
| `kayit_anonim_aktar` | Yalnız öğretmen: seçilen öğrencilerin kimliksiz araştırma dosyası (deneme kayıtları hariç) |
| `olcme_testi` / `olcme_kaydet` | Öğretmenin onayladığı pilot testi (ön / son / gecikmeli) seçenekleri karıştırarak verir; yanıtları puanlayıp kayda yazar |
| `tahtayi_ac` | Yerel sunucu kapalıysa açar, tahta sayfasını açar ve bağlanmasını bekler; açık sunucu başka bir KlinikKoç klasöründense onu kapatıp bu klasörden açar |
| `dersler` | Bilgisayardaki dersleri, bölümlerini ve görsellerini listeler |
| `ders_paketi_ekle` | Öğretmenin verdiği ders paketini (.zip) kurar ve makalelerini aramaya başlar; yol verilmezse paket sayfasını açar |
| `ders_oku` | Ders planını ya da bir bölümün anlatımını, tahta komutlarını ve sorularını okur |
| `gorsel_bak` | Ders görselini Claude'a gösterir (işaretleyeceği yeri seçmek için) |
| `tahta` | Adım adım: önce tahtaya yazar/çizer, sonra o adımı sesli anlatır |
| `soru_sor` | Tahtada soru kartı açar, dokunduğunuz cevabı Claude'a iletir |
| `tahta_durumu` | Tahtanın durumu; süren bir anlatımın ya da sorunun bitmesini bekler |
| `dinle` | Mikrofon tuşuyla söylediğinizi bekler ve yazı olarak alır (sesli sohbet) |
| `videolar` | Dersin videolarını listeler (klasördeki dosyalar ve YouTube bağlantıları) |
| `anlatima_devam` | Siz söz alınca duraklayan anlatımı, Claude cevap verdikten sonra kaldığı cümleden sürdürür |
| `durdur` | Anlatımı hemen keser |
| `ses_yeniden_baslat` | Pocket sesi açılamadıysa ya da durduysa beklemeden yeniden başlatır (kendiliğinden de bir dakikada bir dener) |

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

Program derssiz gelir; önce öğretmenin verdiği ders paketini ekleyin (Claude'a **"İndirilenler'deki ders paketini kur"**
deyin ya da paketi **Ders paketleri ve makaleler** sayfasına bırakın). Sonra Claude'a yazın:
**"Tahtayı aç, akut periodontal lezyonlar dersine başlayalım. Adım Ayşe."**
Vaka çalışmak için: **"Bu dersin vakasını çözelim."** Karne için: **"Karnemi göster."**
Claude önce eğitmeni yükler, kaydınızda tekrar zamanı gelen konu varsa kısa bir tekrarla başlar.

Öğrenci kaydı ve raporlar yalnız bu bilgisayardaki kalıcı kayıt klasöründe durur (Mac: `~/Library/Application Support/KlinikKoc/kayitlar`, Windows: `%APPDATA%\KlinikKoc\kayitlar`); hiçbir yere gönderilmez. Öğrenci isterse `kayit_disa_aktar` ile tek dosyaya alıp başka bilgisayarda `kayit_ice_aktar` ile açar.
Rapor, öğrenci isterse öğretmenine kendisi tarafından iletilir.

## Sesli sohbet (dikte)

Tahtanın altında bir konuşma bölümü var: solda **duraklat/oynat** ile **mikrofon** tuşu yan yana (klavyede
**P** ve **M**), ortada yazma kutusu, sağda durdur tuşu. Kutunun üstünde son iki ileti görünür
(Claude'un okuduğu cümle ve sizin söyledikleriniz ya da yazdıklarınız).

**Yazarak:** Mikrofon kullanamadığınızda kutuya yazıp Enter'a (ya da ↑ okuna) basın. Yazmaya başlamak da
söz almaktır: anlatım kaldığı yerde duraklar. Vazgeçip kutuyu boş bırakırsanız anlatım sürer.

**Sesle:**

1. Tuşa dokunun ve konuşun. En az 1 dakikalık uzun bir konuşma da tek parça yazıya döner.
2. Susunca (ya da tuşa yeniden dokununca) konuşmanız yazıya çevrilir ve **2–3 saniye kutuda görünür**.
   Bir terim yanlış yazılmışsa kutuya dokunup düzeltin, sonra Enter'a basın; hemen göndermek için ↑.
   Dokunmazsanız kendiliğinden gönderilir.
3. Claude tahtada sesli cevap verir, sonra sizi yeniden dinler.

**Konuşmayı yazıya çeviren (dikte motoru):** Mikrofonun yanındaki küçük etiket hangisinin kullanıldığını
gösterir; dokunup değiştirebilirsiniz, seçim saklanır.

| | Duyu-small (yerel) | Tarayıcı |
|---|---|---|
| Nerede çalışır | Bu bilgisayarda (yerel sunucu) | Chrome/Edge'in kendi tanıyıcısı |
| Ses dışarı çıkar mı | Hayır | Evet (Google'a ya da Microsoft'a gider) |
| İnternet | Gerekmez (model bir kez indirildikten sonra) | Gerekir |
| Tıbbi terimler | Daha doğru | Sık bozar ("nekrotizan gingivitis" → "nekrotizangin gibi test") |
| Kurulum | Bir kez: `python3 tools/sunucu.py --kur-duyu` (Windows: `py tools\sunucu.py --kur-duyu`) | Yok |

Duyu kuruluysa varsayılan odur; kurulu değilse tahta tarayıcıya düşer, etiket sarı yanar ve menüde kurulum
komutu görünür. Duyu'nun paketleri ve modeli program klasörünün dışında, kalıcı veri klasöründe durur
(Mac: `~/Library/Application Support/KlinikKoc/duyu`, Windows: `%APPDATA%\KlinikKoc\duyu`); programı
güncellediğinizde silinmez. Mikrofon, tahta konuşmaya başlayınca kendiliğinden kapanır; tahtanın kendi
sesini almaz.

**Terim sözlüğü:** Yazıya çevrilen metin alan terimleri sözlüğünden geçer: bozuk biçim doğru terime
çevrilir (ör. "birleşim epiteliği" → "birleşim epiteli"). Sözlük `ses/terimler.json`, `ses/telaffuz.json`'un
ters yönü ve derslerin terimlerinden (term komutları, kısa hedef başlıkları) beslenir. Kendi terimlerinizi
kalıcı veri klasöründeki `terimler.json` dosyasına ekleyin (biçim `ses/terimler.json`'daki gibi; güncellemede
silinmez). Claude düzeltilmiş metni ve tanıyıcının ham çıktısını (`ham_metin`) birlikte görür; belirsizse sorar.
Hangi tanıyıcının daha iyi olduğunu ses testi sayfasındaki **Duyu ile tarayıcı karşılaştırması** ölçer
(bkz. `ses-testi/KILAVUZ.md`).

- **Söz alma:** Tahta anlatırken tuşa dokunursanız anlatım kaldığı yerde duraklar ("Söz sizde" yazar).
  Konuşmanız bitince Claude anlatımın bitmesini beklemeden hemen duyar ve cevap verir. Cevabını tahtada
  çizerek verirse tahta cevaptan sonra eski hâline döner ve anlatım kesilen cümleden sürer. Bir şey
  söylemeden susarsanız anlatım kendiliğinden sürer; ▶ ile de siz sürdürebilirsiniz.
- Soru kartı açıkken konuşursanız kart kapanır; Claude önce sizi cevaplar, gerekirse soruyu yeniden sorar.
- Tarayıcı tanıyıcısı Firefox'ta yoktur; orada Duyu ya da yazı kutusu kullanılır.
- İlk kullanımda tarayıcı mikrofon izni ister; "İzin ver" deyin.
- Üst çubuktaki ışık Claude'un dinleyip dinlemediğini gösterir: **yeşil** "Claude dinliyor", **gri**
  "Claude dinlemiyor". Claude masaüstü uygulaması, Claude cevabını bitirip beklemeye geçtiğinde
  kendiliğinden yeni bir iş başlatamaz; o sırada ışık gridir.
- Işık griyken konuşursanız sorunuz kaybolmaz; tahtada sarı bir uyarı çıkar: "Sorunuz bekliyor".
  İki yol var: Claude sohbetine **tahtaya bak** yazın (Claude sorunuzu tahtadan alır) ya da
  **Sohbete kopyala** düğmesine basıp sohbete yapıştırın (Mac'te Cmd+V, Windows'ta Ctrl+V).

### Claude Code ile (isteğe bağlı): sorular sohbete kendiliğinden düşsün

Claude masaüstü uygulamasında bir aracın sohbete kendiliğinden mesaj göndermesinin yolu yoktur.
Claude Code'da (terminaldeki Claude) ise "channels" adlı, henüz deneme aşamasındaki bir özellik bunu
yapar ([belge](https://code.claude.com/docs/en/channels-reference)). Claude Code kullanıyorsanız:

1. KlinikKoç klasöründe bir `.mcp.json` dosyası oluşturun:
   ```json
   {"mcpServers": {"klinik-koc": {"command": "python3", "args": ["tools/tahta-mcp.py", "--kanal"]}}}
   ```
   (Windows'ta `python3` yerine `python`.)
2. Claude Code'u o klasörde şöyle başlatın:
   `claude --dangerously-load-development-channels server:klinik-koc`
3. Artık Claude dinlemezken söyledikleriniz sohbete yeni bir ileti olarak düşer ve ışık hep yeşildir.

Bu yol claude.ai hesabıyla giriş ister; Team/Enterprise hesaplarında yöneticinin "channels"ı açması
gerekir. Özellik deneme aşamasında olduğu için ileride değişebilir.

## Video

Claude tahtada video gösterebilir. İki yol var:

1. **Bilgisayardaki video (internetsiz):** Videoyu dersin klasöründe `videolar` adlı bir klasöre koyun:
   `lessons/<ders>/videolar/nug-muayene.mp4`. Claude `videolar` aracıyla listeyi görür ve tahtada oynatır.
   İsterseniz aynı klasöre `videolar.json` koyup başlık ve kaynak yazabilirsiniz:
   ```json
   {"nug-muayene.mp4": {"baslik": "NUG'da ilk muayene", "credit": "K. Üstün, Akdeniz Üniv."}}
   ```
   Uygun biçimler: mp4 (Chrome ve Edge'de), webm, mov (Mac'te Safari). En güvenlisi mp4 (H.264).
2. **YouTube (internet gerekir):** Sohbette Claude'a bağlantıyı verin ("Şu videoyu 1:30'dan 3:00'e kadar
   göster: https://youtu.be/..."). Ders dosyasında hazır durması için `egitmen.json`'a da yazabilirsiniz:
   ```json
   "videolar": {"nug-anlatim": {"youtube": "https://youtu.be/XXXXXXXXXXX", "baslangic": 90, "bitis": 180, "baslik": "NUG"}}
   ```

Nasıl oynar: Claude önce ne izleneceğini söyler, video oynar, bitince (ya da bitiş saniyesinde) anlatıma
döner. Duraklat (⏸) ve mikrofon videoyu da durdurur; ▶ ile kaldığı yerden sürer. Videonun kendi
düğmeleriyle de ileri-geri sarabilirsiniz.

**Telif ve gizlilik:** `videolar` klasörü ve bütün video dosyaları açık depoya hiçbir zaman girmez
(`.gitignore` ve yayın denetimi bunu engeller). Hasta görüntüsü içeren videolar yalnız fakülte
bilgisayarında kalır. Herkesle paylaşılacak bir video için YouTube bağlantısı kullanın.

## Kullanım ipuçları

- Konuyu siz seçersiniz: "Defekt morfolojisi bölümünü 10 dakikada anlat", "Şekil 4'teki farkı göster",
  "Bana bu bölümden iki soru sor", "Daha yavaş anlat", "Bu kısmı tahtaya çizerek anlat".
- **Duraklat** (⏸, mikrofonun yanında; klavyede **P** ya da **Boşluk**): anlatımı kısa süre bekletir.
  Hiçbir şey iptal olmaz; ses olduğu yerde durur, sıradaki adımlar bekler ve ekranda "Duraklatıldı"
  yazar. Yeniden basınca (▶) aynı cümlenin kaldığı yerinden sürer. Tuş yalnız anlatım sürerken
  etkindir (soru kartında ve mikrofon dinlerken sönüktür). Claude bu sırada "duraklatildi" görür ve
  bekler. Duraklatılmışken mikrofona basarsanız söz alırsınız; kare düğme ya da Esc anlatımı keser.
- Tahtadaki **kare** düğme ya da **Esc** anlatımı keser. **F** tam ekran. Hız düğmesi 1,0 / 1,2 / 1,4.
- Sesi bu bilgisayardaki Pocket TTS Türkçe kadın 3 sesi üretir (ayar: `ses/ses-ayari.json`). Sunucu
  açılırken ~10–60 sn yüklenir; o sırada ya da Pocket kurulu değilse Piper dfki (yedek), o da yoksa
  tarayıcının Türkçe sesi. **Hangi sesin çaldığı tahtanın üst çubuğunda yazar** ("Ses: Pocket",
  "Ses: Piper (yedek)", "Ses: tarayıcı sesi (yedek)"; yedekte sarı). Claude da `tahtayi_ac` sonucunda görür.
- Tarayıcı sesi kendiliğinden çalmaya izin vermezse anlatım o cümlede bekler ve ekranda büyük
  **"🔊 Sesi açmak için dokunun"** düğmesi çıkar; dokununca aynı cümleden sürer.
- Tahtayı ikinci bir sekmede açarsanız eski sekme "Bu tahta başka bir sekmede açık" der ve bağlantıyı bırakır.
- Bu mod öğretim üyesi içindir. Öğrenci sürümü (index.html) değişmedi; öğrenciye maliyet yine sıfırdır.

## Sorun giderme

| Belirti | Çözüm |
|---|---|
| Claude'da "klinik-koc" araçları görünmüyor | Claude'u tepsiden tamamen kapatıp açın (^ → Claude → sağ tık → Çık). **Ayarlar › Geliştirici**'de listede mi? Değilse `python tools/tahta-mcp.py --dene` ne diyor bakın; "Yapılandırmayı düzenle" ile açılan dosyanın yolunu `--kur --ayar "<yol>"` ile verin |
| Listede "klinik-koc" var ama hata veriyor | `--dene` çıktısında "dosyası yok" yazıyorsa program klasörü taşınmıştır: KUR'u yeni klasörden yeniden çalıştırın |
| Üst çubukta "Ses: tarayıcı sesi (yedek)" | Doğal ses kurulu değil ya da açılamadı. KUR'u yeniden çalıştırıp Pocket'e "E" deyin; Python 3.14 ise python.org'dan 3.12 kurun |
| Ekranda "Sesi açmak için dokunun" | Tarayıcı sesi engelledi; düğmeye dokunun, anlatım kaldığı cümleden sürer |
| Videonun üstünde büyük ▶ | Tarayıcı videonun kendiliğinden başlamasını engelledi; ▶'e dokunun |
| "Bu tahta başka bir sekmede açık" | Aynı tahta iki sekmede açılmış; eski sekmeyi kapatın |
| "Tahta sayfası açık değil" | Claude'a "tahtayı aç" deyin ya da tarayıcıda `http://localhost:8810/canli.html` açın |
| Yazılar geliyor, ses yok | Tahtada "başlat" düğmesine dokunun; bilgisayarın sesini denetleyin |
| Sol üstteki nokta kırmızı | Sunucu penceresi kapanmış; Claude'a "tahtayı aç" deyin |
