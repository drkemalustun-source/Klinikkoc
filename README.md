# Akıllı Tahta

Dersi sesli anlatan, anlatırken ilgili görseli tahtada gösteren ve öğrenme hedeflerini
notlandırmadan sorularla yoklayan, açık kaynak ve kâr amacı gütmeyen bir çalışma aracı.

- **Öğrenciye maliyeti yok.** Ders içeriği önceden, bir kez hazırlanır. Varsayılan ayarlarla hiçbir ücretli servis çağrılmaz.
  Canlı soru-cevapta model isteğe bağlıdır: yerel model ücretsizdir; bulut API'yi seçen kendi anahtarını kullanır.
- **Statik web uygulaması.** Derleme adımı ve framework yok; HTML, CSS ve düz JavaScript.
- **Her yerde açılır.** Akıllı tahtada tam ekran ve dokunmatik, dizüstünde, telefonda. İnternet olmadan da çalışır.
- **Ses.** Tarayıcının ücretsiz Türkçe seslendirmesi (Web Speech, tr-TR). İstenirse Piper ile önceden üretilmiş doğal ses dosyaları eklenir.
- **İçerik oynatıcıdan ayrı.** Her ders `lessons/<kimlik>/ders.json` dosyasıdır ve `schema/ders.schema.json` şemasına uyar.

## Çalıştırma

En kolayı: `index.html` dosyasını tarayıcıda açın. Dosyadan açıldığında da çalışır.

Çevrimdışı kurulum (ana ekrana ekleme, internetsiz açılış) için klasörün bir web sunucusundan
yayımlanması gerekir. Herhangi bir statik sunucu yeterlidir:

```sh
python3 -m http.server 8000      # sonra http://localhost:8000
```

Kalıcı yayın için GitHub Pages, fakültenin web sunucusu ya da herhangi bir statik barındırma kullanılabilir.
İlk açılışta tüm dersler, görseller ve sesler cihaza indirilir; sonra internet gerekmez.

## Ses testi (1. aşama)

Konuşma tanıma ve seslendirme motorlarını aynı cümlelerle karşılaştıran ayrı bir sayfa.
Adım adım kullanım: [`ses-testi/KILAVUZ.md`](ses-testi/KILAVUZ.md). Kısaca:

```sh
python3 tools/sunucu.py            # http://localhost:8810/ses-testi/ açılır
python3 tools/sunucu.py --kur-duyu # isteğe bağlı: Duyu-small için Python paketleri
```

Mikrofon ve model önbelleği tarayıcıda yalnızca güvenli adreste (localhost dahil) çalıştığı için
sayfa dosyadan değil, bu sunucuyla açılır.

## Kullanım

| Ne | Tahta / telefon | Klavye |
|---|---|---|
| Oynat / duraklat | Sarı düğme | Boşluk |
| Sonraki / önceki adım | Tahtada sola / sağa kaydır, ileri / geri düğmeleri | → / ← |
| Bölüme atla | İçindekiler | |
| Hedeflere bakış | Hedef simgesi (ders sonunda kendiliğinden açılır) | |
| Ses, hız, altyazı, sessiz mod | Ayarlar | |
| Tam ekran | Tam ekran simgesi | F |
| Şekli büyüt | Şekle dokunun | |

Sorular not vermez. Cevaplar yalnızca öğrencinin kendi cihazında saklanır ve hedefler tablosunda
"Ulaşıldı / Tekrar edin / Yoklanmadı" olarak görünür. Hiçbir yere gönderilmez.

Derste yoklama sorusu varsa başta iki yol sunulur (Ayarlar'dan değişir):

- **Öğrenerek ilerleyelim:** önce anlatım, sonra soru.
- **Önce ben yanıtlayayım:** makaleyi çalışmış öğrenci için her bölümde önce soru, sonra anlatım.

Hedefler tablosu her alt hedef için kanıtı ayrı gösterir: *dinlendi*, *anlatımdan önce doğru*,
*anlatımdan sonra doğru*, *yeni örnekte uygulandı*. Belirli bir yanlış çıkarımı gösteren çeldirici
seçilirse "açık yanılgı" olarak not edilir; aynı ayrımı yoklayan bir soru doğru cevaplanınca kapanır.
Tablonun altından çalışma özeti (.md) indirilebilir. Uzun dersler yaklaşık 30 dakikalık dilimlere
bölünür; dilim sonunda oynatıcı durur ve mola önerir.

## Yeni ders eklemek

1. `lessons/<yeni-kimlik>/` klasörü açın. Görselleri `assets/` altına koyun.
2. `ders.json` yazın. Örnek olarak `lessons/tanitim/ders.json`'a, komut listesi için `MIMARI.md`'ye bakın.
3. Denetleyip paketleyin:
   ```sh
   node tools/paketle.mjs
   ```
   Bu komut dersi şemaya ve iç tutarlılığa göre denetler (her alt hedefin bir bölümü ve sorusu var mı,
   görseller yerinde mi, `{n}` işaretleri komutlarla eşleşiyor mu), ders listesini ve çevrimdışı
   önbellek listesini günceller. Ders listesinde görünmesi için bu adım gereklidir.

**Fakülteye özel dersler.** Telifli görsel (ör. ders kitabı fotoğrafı) içeren bir derste
`"distribution": "faculty"` yazın. Böyle bir ders denetlenir ama açık pakete, ders listesine ve
çevrimdışı önbellek listesine girmez. Fakülte içi paket için `node tools/paketle.mjs --fakulte`
kullanın; ardından depoya göndermeden önce `node tools/paketle.mjs` ile açık hâline dönün.
Bu derslerin klasörleri `.gitignore`'da tutulur. Tahta köşesindeki kaynak etiketi `source.label`
alanından gelir (yoksa "Makale").

Peri-implantitis pilot dersi elle değil, `tools/ders-uret/peri-implantitis-cerrahi.py` betiğiyle
üretilir (`python3 tools/ders-uret/peri-implantitis-cerrahi.py`, ardından `node tools/paketle.mjs`).
Bu derste düzeltme yaparken `ders.json`'u değil betiği düzenleyin; yoksa betik yeniden çalışınca
değişiklik kaybolur.

## Doğal ses (önceden üretilir)

Seçilen ses (5 Kasım 2026): **Pocket TTS Türkçe, kadın 3 (female_3)**, 1,2 hız. Ayar tek dosyada:
`ses/ses-ayari.json` (`"motor": "pocket"`; eski erkek Piper sesine dönmek için `"piper"` yazın).
Ders hazırlayan bilgisayarda bir kez çalıştırılır; öğrenciler yalnızca hazır MP3 dosyalarını indirir,
cihazlarında model çalışmaz. Pocket torch istediği için ayrı bir Python ortamında (`.ses-ortami/`) çalışır;
model ilk kullanımda `tools/.sesler/hf/` altına iner (~420 MB). Pocket hazır değilse canlı tahta Piper dfki'ye döner.

```sh
python tools/ses-uret.py --kur                        # bir kez: piper-tts, soundfile, numpy
python tools/ses-uret.py --kur-pocket [python3.11]    # bir kez: .ses-ortami (CPU torch + pocket-tts-turkish)
python tools/ses-uret.py peri-implantitis-cerrahi     # ayardaki sesle üretir
python tools/ses-uret.py peri-implantitis-cerrahi --motor piper   # eski Piper dfki sesi
node tools/paketle.mjs                                # önbellek listesine sesleri ekler
```

- Metin seslendirilmeden önce `ses/telaffuz.json` sözlüğünden geçer (ses testi sayfasında düzenlenir).
- Her parçanın cümle başlangıç zamanları manifestte tutulur; oynatıcı altyazıyı cümle cümle eşler
  ve "cümleyi tekrarla" düğmesi o cümlenin başına sarar.
- Sesler normal hızda üretilir; `--hiz` (varsayılan 1.2) oynatıcının başlangıç hızıdır. Öğrenci hızı
  kendi değiştirebilir. Başka ses için `--ses tr_TR-fahrettin-medium`.
- Metni değişmeyen parçalar yeniden üretilmez. Ses dosyası olmayan parçada oynatıcı tarayıcı sesine döner.
- Ders dosyasında `"audio": {"manifest": "audio/manifest.json"}` alanı bulunmalıdır.

## Öğrenme özellikleri

- **Yanlış cevapta ilgili yere dönüş:** "İlgili yeri dinle" düğmesi, konunun anlatıldığı adımı (çoğu zaman
  ilgili şekli) yeniden dinletir, sonra soruya geri getirir. Adım, sorunun `review` alanıyla elle verilebilir;
  verilmezse oynatıcı sorunun kaynağına (`sourceRef`: şekil > alt bölüm > sayfa) en çok uyan adımı seçer.
- **Aralıklı tekrar:** Cevaplanan her soru bir kutuya girer (Leitner). Yanlış: 10 dakika sonra; doğru:
  1 gün, 3 gün, 1 hafta, 3 hafta sonra yeniden sorulur. Ders açılınca ve Hedefler ekranında "Tekrar et" çıkar.
  Yanlıştan hemen sonraki "Tekrar dene" doğrusu hatırlama sayılmaz.
- **İlerleme anonimdir:** cevaplar, tekrar takvimi ve kaldığı yer yalnız öğrencinin tarayıcısında
  (`localStorage`) tutulur; hiçbir sunucuya gönderilmez, ad ya da kimlik sorulmaz.

## Soru sor (canlı soru-cevap, 3. aşama)

Tahtanın üst çubuğundaki konuşma balonu düğmesi. Üç kip vardır (Ayarlar → Soru-cevap):

| Kip | Ne yapar | Maliyet | Soru nereye gider? |
|---|---|---|---|
| **Model yok** (varsayılan) | Soruyu ders anlatımında ve makalede arar, ilgili yerleri "Dinle" düğmesiyle gösterir | Yok | Hiçbir yere; cihazda aranır |
| **Yerel model** | Ollama ya da OpenAI uyumlu bir sunucudaki açık model cevap yazar | Yok | Bilgisayardaki ya da fakülte sunucusundaki modele |
| **Bulut API** | Claude (Anthropic) cevap yazar ve gerekirse tahtaya çizer | Anahtar sahibine yansır; soru başına ~0,5–1 sent | Anthropic'e |

- **Cevaplar kaynağa dayanır.** Model yalnız bulunan ders ve makale parçalarını görür (`[K1]`, `[K2]` etiketleriyle);
  her cümlede dayandığı parçayı yazar. Parçalarda yoksa "Bu sorunun cevabı ders kaynaklarında yok" der.
  Öğrenci etiketli parçaları cevabın altında görür ve "Dinle" ile dersteki yere gidebilir.
- **Tahta.** Model, cevabı tahtada göstermek için tek bir araç (`tahtaya_yaz`) kullanır: madde, tablo, akış, karşılaştırma,
  dersin kendi görselleri ve basit çizim. Komutlar cihazda denetlenir; görsel yalnız dersin açık lisanslı görsellerinden olabilir.
  Kaynaktaki bir şekli yeniden çizerse altına "Uyarlanmıştır: …" (açık lisanslı değilse "Kaynaktan uyarlanmıştır") yazılır.
  "Derse dön" ders tahtasını geri getirir. Araç çağıramayan modeller için cevap JSON olarak istenir.
- **Gizlilik.** Modele giden: ders başlığı, hedefler, görsel listesi, o anki bölüm ve anlatım, bulunan parçalar ve soru.
  Öğrencinin adı, cevapları, ilerlemesi gönderilmez.
- **API anahtarı** koda ya da depoya hiç yazılmaz. Kullanıcı Ayarlar'da kendisi girer; yalnız o tarayıcıda (`localStorage`)
  saklanır ve "Anahtarı bu cihazdan sil" ile silinir. Ortak bilgisayarda kullanım sonrası silinmelidir.
- **Maliyet ve önbellek.** Her cevabın altında süre, token sayısı ve yaklaşık maliyet yazar; Ayarlar'da toplam durur.
  Ders boyunca değişmeyen talimat bölümü önbelleğe alınır, ikinci sorudan itibaren o kısım çok daha ucuzdur.

**Kaynak dizini** (vektör veritabanı gerekmez): makale metni parçalara bölünüp ders klasörüne konur, arama tarayıcıda yapılır.

```sh
python tools/dizin-uret.py --kur                       # bir kez: pypdf
python tools/dizin-uret.py peri-implantitis-cerrahi    # lessons/<id>/kaynaklar/kaynaklar.json'dan üretir
```

`kaynaklar.json` her kaynağın lisansını ister (lisansı yazılmayan kaynak dizine girmez) ve Türkçe soruyu İngilizce
makalede bulmak için küçük bir terim sözlüğü taşır. İleride bir vektör veritabanı aynı arayüzle (`search`) eklenebilir.

**Yerel model (Ollama)** için tarayıcının erişebilmesi gerekir: Ollama'yı `OLLAMA_ORIGINS=*` ortam değişkeniyle başlatın
(ya da yalnız uygulamanın adresini yazın). 8 GB bellekli bir bilgisayarda `qwen2.5:3b` gibi küçük bir model çalışır.

**Karşılaştırma sayfası** (`qa-testi/`): aynı soruları iki modele sorar; süre, token, maliyet ve 1–5 puanlarla rapor çıkarır.
`python3 tools/sunucu.py` ile açıp `http://localhost:8810/qa-testi/` adresine gidin.

**Sağlayıcı eklemek** tek dosyadır: `js/qa/saglayici-*.js` örneklerine bakın (`AT.qa.registerProvider`).

## Canlı tahta (Claude masaüstü ile, API anahtarsız)

Öğretim üyesinin kendi kullanımı için ek bir mod. Claude, masaüstü uygulamasında sizin
aboneliğinizle çalışır ve tahtayı canlı yönetir: konuyu anlatır, ders görsellerini gösterip
işaretler, çizer, soru sorar. API anahtarı ve ek ücret yoktur; aboneliğin kullanım sınırları geçerlidir.
Öğrenci sürümü bundan etkilenmez.

Kurulum (bir kez, Windows'ta komut isteminde, bu klasörün içinde):

```sh
python tools/tahta-mcp.py --kur     # Claude masaüstü ayarına "akilli-tahta" aracını ekler
```

Sonra Claude masaüstü uygulamasını tamamen kapatıp (sistem tepsisi → Çık) yeniden açın ve yeni
bir sohbette yazın: *"Tahtayı aç ve bana Şekil 2'yi anlat."* Claude yerel sunucuyu ve
`canli.html` sayfasını kendisi açar; sayfada bir kez "başlat"a dokunmanız yeterlidir.

- Ses: bu bilgisayardaki Pocket TTS Türkçe kadın 3 sesi (sunucu açılınca ~1 dk'da yüklenir; o sırada ve hata
  olursa Piper dfki), Piper de yoksa tarayıcının Türkçe sesi (varsa kadın sesi seçilir).
- Durdurmak: tahtadaki kare düğme ya da Esc. Claude'a "dur" demek de olur.
- Ayrıntılar ve araç listesi: [`CANLI-TAHTA.md`](CANLI-TAHTA.md). Kaldırmak için: `python tools/tahta-mcp.py --kaldir`.

## Klasörler

```
index.html, config.js, sw.js, manifest.webmanifest   uygulama kabuğu
css/tahta.css                                        görünüm
js/core.js      ayarlar, ders yükleme, ilerleme kaydı
js/speech.js    ses motorları (Web Speech, hazır ses dosyası, sessiz)
js/board.js     tahta komutları
js/player.js    adım akışı, işaret zamanlaması
js/app.js       arayüz, sorular, çekmeceler
js/qa/          canlı soru-cevap: çekirdek (qa.js), bilgi bulma (bilgi.js), sağlayıcılar (saglayici-*.js)
schema/         ders şeması
lessons/        dersler (her biri kendi klasöründe)
js/ses/         ses katmanı: konuşma tanıma ve seslendirme adaptörleri (1. aşama)
ses/            telaffuz sözlüğü
ses-testi/      ses motorları karşılaştırma sayfası
qa-testi/       soru-cevap modelleri karşılaştırma sayfası
vendor/         üçüncü taraf kitaplıkları (Piper, Transformers.js, Anthropic SDK); bkz. vendor/LISANSLAR.md
tools/          paketleme, Piper ses üretimi, kaynak dizini (dizin-uret.py), ders üretim betikleri, yerel sunucu (sunucu.py)
```

## Lisans

Kod: MIT (bkz. `LICENSE`). Her dersin içeriği, ders dosyasındaki `source.license` alanında belirtilen
lisansa tabidir; kaynak makalelerden alınan şekillerde atıf satırı tahtada gösterilir.

Sesler:
- Anlatım sesi: **Pocket TTS Türkçe** (wite-tech, https://huggingface.co/wite-tech/pocket-tts-turkish),
  ses female_3, **CC-BY-4.0**. Üretilen ders sesleri bu modelle üretilmiş yapay seslerdir.
- Tarayıcı sesi (ses testi sayfası): **Piper İlkiz** (ilkeraktuna, https://huggingface.co/ilkeraktuna/piper-tts-tr-ilkiz-medium), **MIT**.
- Yedek ses: Piper tr_TR-dfki-medium (rhasspy/piper-voices), MIT.
