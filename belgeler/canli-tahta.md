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

1. Bu klasörde bir komut istemi açın (klasörün adres çubuğuna `cmd` yazıp Enter).
2. `python tools/tahta-mcp.py --kur` yazın. Claude'un ayar dosyasına "klinik-koc" eklenir
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
| `kayit_yaz` / `kayit_oku` | Öğrencinin ilerlemesini, her cevabın Bloom düzeyini ve rubrik puanını bu bilgisayardaki `kayitlar/` klasörüne yazar ve okur |
| `bilgi_ara` | Derslerin kaynak sayfalarında, anlatımında, öğretmen notlarında ve vakalarında arar (sözcük + isteğe bağlı anlam araması; bkz. [bilgi-bankasi.md](bilgi-bankasi.md)) |
| `vakalar` / `vaka_oku` | Dersin vaka kartlarını listeler; bir vakayı eğitmen için açar (bkz. [vaka-karti.md](vaka-karti.md)) |
| `karne` | Öğrencinin karnesini hesaplar: hedef ve Bloom düzeyine göre başarı, soru güçlüğü, vaka sonuçları |
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
| `anlatima_devam` | Siz söz alınca duraklayan anlatımı, Claude cevap verdikten sonra kaldığı cümleden sürdürür |
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

Başlamak için Claude'a yazın: **"Tahtayı aç, peri-implantitis dersine başlayalım. Adım Ayşe."**
Vaka çalışmak için: **"Bu dersin vakasını çözelim."** Karne için: **"Karnemi göster."**
Claude önce eğitmeni yükler, kaydınızda tekrar zamanı gelen konu varsa kısa bir tekrarla başlar.

Öğrenci kaydı ve raporlar yalnız bu bilgisayardaki `kayitlar/` klasöründe durur; hiçbir yere gönderilmez.
Rapor, öğrenci isterse öğretmenine kendisi tarafından iletilir.

## Sesli sohbet (dikte)

Tahtanın üst çubuğunda **mikrofon** tuşu var (klavyede **M**).

1. Tuşa dokunun ve konuşun. Söyledikleriniz altyazıda görünür.
2. 2,5 saniye susunca konuşmanız Claude'a gönderilir (ya da tuşa yeniden dokunun).
3. Claude tahtada sesli cevap verir, sonra sizi yeniden dinler.

- **Söz alma:** Tahta anlatırken tuşa dokunursanız anlatım kaldığı yerde duraklar ("Söz sizde" yazar).
  Konuşmanız bitince Claude anlatımın bitmesini beklemeden hemen duyar ve cevap verir. Cevabını tahtada
  çizerek verirse tahta cevaptan sonra eski hâline döner ve anlatım kesilen cümleden sürer. Bir şey
  söylemeden susarsanız anlatım kendiliğinden sürer; ▶ ile de siz sürdürebilirsiniz.
- Soru kartı açıkken konuşursanız kart kapanır; Claude önce sizi cevaplar, gerekirse soruyu yeniden sorar.
- Konuşma tanıma tarayıcının kendi Türkçe tanıyıcısıdır (Chrome/Edge). İnternet gerekir;
  ses yazıya çevrilmek için Google'a (Edge'de Microsoft'a) gider. Firefox'ta çalışmaz.
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
  açılırken ~10–30 sn yüklenir; o sırada ya da hata olursa Piper dfki, o da yoksa tarayıcının Türkçe sesi.
- Bu mod öğretim üyesi içindir. Öğrenci sürümü (index.html) değişmedi; öğrenciye maliyet yine sıfırdır.

## Sorun giderme

| Belirti | Çözüm |
|---|---|
| Claude'da "klinik-koc" araçları görünmüyor | Claude'u sistem tepsisinden tamamen kapatıp açın; `--kur` komutunu yeniden çalıştırın |
| "Tahta sayfası açık değil" | Claude'a "tahtayı aç" deyin ya da tarayıcıda `http://localhost:8810/canli.html` açın |
| Yazılar geliyor, ses yok | Tahtada "başlat" düğmesine dokunun; bilgisayarın sesini denetleyin |
| Sol üstteki nokta kırmızı | Sunucu penceresi kapanmış; Claude'a "tahtayı aç" deyin |
