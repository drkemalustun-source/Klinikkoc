# Web sürümüne geçiş: yapılacaklar

Bu dosya `web` dalının iş listesidir. Amaç, KlinikKoç'un hiçbir şey kurmadan, bir web adresine girerek
çalışmasıdır. `main` dalı ve masaüstü sürümü bu çalışma boyunca değişmez.

## Neden

Bugün kurulum şunları ister: Python, `BASLAT`/`KUR` dosyaları, macOS güvenlik uyarısını geçmek, Claude masaüstü
uygulamasına MCP sunucusu kaydetmek ve uygulamayı yeniden başlatmak. Öğrenciler ve öğretmenler bu adımlarda
takılıyor. Web sürümünde bunların hiçbiri kalmaz.

## Verilen kararlar

| Konu | Karar |
|---|---|
| Barındırma | GitHub Pages, `web` dalından |
| Ders dağıtımı | Bugünkü model: öğrenci öğretmenin `.zip` paketini siteye bırakır, ders yalnız kendi tarayıcısında durur. Sunucuya içerik yüklenmez. |
| Yapay zekâ kaynağı | İki yol da açık kalır, aralarında geçilebilir (aşağıda A ve C). Önce A yapılır. |

**A yolu:** canlı eğitmen sayfanın içinde çalışır; modele kurum anahtarıyla, küçük bir vekil sunucu (Cloudflare
Worker) üzerinden bağlanır. Öğrenci yalnız sınıf kodu girer. İsteyen kendi API anahtarını da girebilir.

**C yolu:** öğrencinin kendi Claude aboneliği kullanılır. Öğrenci claude.ai ayarlarına bir kez bağlayıcı adresi
yapıştırır; küçük bir aktarıcı, Claude'un araç çağrılarını açık duran tahta sekmesine iletir.

**İlke:** araç tanımları ve işleyicileri bir kez, tarayıcı JS'inde, bağlantı biçiminden bağımsız yazılır. A ve C
aynı çekirdeğin iki sürücüsüdür.

## Mimari

```
                    ┌──────────── sayfa ────────────┐
ders paketi (.zip) ─► js/yerel/ders-deposu.js ─► Cache Storage (kk-ders-<id>)
                    │                               │        ▲
                    │  js/yerel/yerel.js (AT.yerel) │        │ lessons/<id>/** istekleri
                    │   /api/... çağrılarını        │      sw.js
                    │   sayfa modüllerine yönlendirir
                    │                               │
                    │  js/yerel/depo.js ─► IndexedDB (kayıtlar, öğrenci defteri, ayarlar)
                    │                               │
                    │  js/egitmen/ (araç çekirdeği) ─► canli.js (tahta, ses)
                    │      ▲                ▲       │
                    └──────┼────────────────┼───────┘
                  sürücü A │                │ sürücü C
              (sayfa-içi ajan döngüsü)   (aktarıcıya WebSocket)
                           │                │
                   vekil ya da kendi     claude.ai bağlayıcısı
                   anahtar → model
```

- **Sunucunun yerine hibrit yapı.** Service Worker yalnız kurulu ders dosyalarını verir. API mantığı sayfa
  modüllerinde yaşar. SW'nin `/api/*` isteklerini yanıtlaması elendi: tarayıcı boşta kalan SW'yi öldürür, 500 MB
  zip açmak ve PDF işlemek tek olaya sığmaz, SW'de DOM yoktur.
- **Yönlendirici `AT.yerel`.** Sayfalardaki `api()` sarmalayıcıları tek satırla buna bağlanır: `js/ana.js:55`,
  `js/makaleler.js:23`, `js/sihirbaz.js:38`, `js/degerlendirme.js:20`, `js/canli.js:54-70`, `js/board.js:360`.
  `fetch` yedeği kalır; aynı dosyalar masaüstü sunucusuyla da çalışır. Kip `config.js` içinde `yerel: true` ile
  açılır.
- **Ders deposu.** Cache Storage; ders başına bir önbellek (`kk-ders-<id>`), ders listesi `kk-katalog`. Dosyalar
  gerçek adresleriyle saklanır (`lessons/<id>/assets/…`), bu yüzden oynatıcının yükleme kodu (`js/core.js:39-74`)
  değişmez.
- **Tek kayıt deposu.** IndexedDB, canlı eğitmen yolunun Türkçe anahtarlı kayıt biçimiyle. Dışa ve içe aktarım
  `tools/kayit_aktar.py` dosya biçimiyle uyumludur; masaüstü öğrencisi kaydını siteye taşıyabilir.
- **Araç çekirdeği.** Tek kaynak `tools/mcp_araclar.py` kalır. `tools/arac_dok.py` bunu `js/egitmen/arac-verisi.js`
  dosyasına döker; CI farkı denetler. `js/egitmen/kuyruk.js`, `sunucu.py`'deki `Canli` sınıfının sayfa-içi
  karşılığıdır; `canli.js`'in çizim ve anlatım döngüsü aynen kalır.
- **Testler.** JS modülleri mevcut üslupla yazılır ve `node --test` ile sınanır (`tools/testler/js/`). Taşınan
  her Python işlevi için eşlik testi yazılır: aynı girdi Python'a ve JS'e verilir, sonuçlar karşılaştırılır.

## Fazlar

Her faz tek başına yayımlanabilir ve doğrulanabilir. Durum: ☐ bekliyor, ◐ sürüyor, ☑ bitti.

### ☑ F0 — Dal, yayın hattı, test iskeleti

Davranış değişmez.

- [x] `web` dalı, bu dosya
- [x] Sürüm `5.0.0`; `config.js` içinde `yerel: true`
- [x] `.nojekyll`, `.github/workflows/web-yayin.yml`
- [x] `tools/testler/js/yukle.mjs`, ilk Node testi, `tools/testler/test_js.py`

**Doğrulama:** `python3 -m unittest discover -s tools/testler` Node testlerini de koşar. Yayın, dal itilip Pages
ayarı açıldıktan sonra doğrulanır (aşağıda "Yayın için gerekenler").

### ◐ F1 — Ders paketi tarayıcıda kurulur

- [ ] `js/yerel/yerel.js`: `AT.yerel`, SW kaydı
- [ ] `js/yerel/zip.js`: zip okuyucu (kitaplık yok; `DecompressionStream`)
- [ ] `js/yerel/ders-deposu.js`: paket denetimi, kurulum, ders listesi
- [ ] `sw.js`: kurulu ders dosyalarını verme, videoda parça isteği (Range), ders önbelleklerini koruma
- [ ] Oynatıcı ana sayfasında "Ders paketi ekle" (dosya seçme ve sürükleyip bırakma)

**Taşınan:** `tools/ders_paketi.py` (`paketi_incele`, `yukle`, `katalog_guncelle`).
**Bırakılan:** kurulumdan sonra otomatik makale arama (F6), ders kaldırma arayüzü (F2).
**Doğrulama:** Python'un ürettiği örnek ders paketini JS aynı ders kimliği ve dosya listesiyle kabul eder; kötü
paketleri Python'la aynı iletiyle reddeder. Düz bir statik sunucuda paket bırakılınca ders kartı çıkar, görselleriyle
oynar, çevrimdışı yenilemede açılır, sürüm artışından sonra yerinde durur.

### ☐ F2 — Tek kayıt deposu ve ana ekran

- [ ] `js/yerel/depo.js`: IndexedDB (`kayitlar`, `ogrenciler`, `dosyalar`, `yedekler`, `ayarlar`)
- [ ] Kayıt dışa ve içe aktarma (`kayit_aktar.py` biçimi); "Kaydımı indir" düğmesi
- [ ] `js/yerel/ana-ekran.js`: `ana/ozet`, `secim`, `geri_bildirim`, `oneri_*`; `makale/paket`, `makale/durum`
- [ ] `ana.html` web'de açılır; ders kaldırma
- [ ] Oynatıcı ilerlemesi (`localStorage`) kayda yansıtılır (`js/core.js` `Progress.save`)
- [ ] Depolama paneli (`navigator.storage.estimate`)

**Taşınan:** `kayit_deposu.py` (`kisalt`, `kimlik_olustur`, `coz`, `yaz`), `kayit_aktar.py`, `ana_ekran.py`.
**Bırakılan:** ortak bulut klasörü, program güncelleyici, klasörü aç, İndirilenler taraması.
**Doğrulama:** Python'un dışa aktardığı dosya JS'e alınıp yeniden dışa aktarılır ve Python `ice_aktar` kabul eder.

### ☐ F3 — Araç çekirdeği ve sunucusuz canlı tahta

Yapay zekâ henüz yok; tahta betikli bir komut dizisiyle sınanır.

- [ ] `tools/arac_dok.py` → `js/egitmen/arac-verisi.js` (CI fark denetimi)
- [ ] `js/egitmen/araclar.js`: araç kaydı, `tanimlar(profil)`, `cagir(ad, girdi)`
- [ ] `js/egitmen/kuyruk.js`: `Canli` sınıfının portu (`gonder`, `soyle`, `dinle`, `al`, `bitti`, `duraklat`)
- [ ] İşleyiciler: ders (`dersler`, `ders_oku`, `gorsel_bak`, `vakalar`, `vaka_oku`, `sablon_bilgisi`, `videolar`),
      kayıt (`egitmen_hazirla`, `kayit_yaz`, `kayit_oku`, `karne`, `rapor_yaz`, `sozlu_prova`, `tekrar_listesi`,
      `tekrar_karti_yaz`, `olcme_testi`, `olcme_kaydet`), tahta (`tahta`, `soru_sor`, `tahta_durumu`,
      `anlatima_devam`, `durdur`)
- [ ] `js/egitmen/karne-hesap.js` (`karne.py` `hesapla`); İlerleme paneli
- [ ] `canli.js:54-70` kuyruğa bağlanır

**Taşınan:** `tahta-mcp.py` veri işleyicileri, `karne.py`, `sunucu.py` `Canli` ve `ders_ilerlemesi`.
**Bırakılan:** `tahtayi_ac`, `ses_yeniden_baslat`, `depolama`, `ortak_klasor`, `eski_surumler*`, otomatik uyandırma.
**Not:** ölçme testinde seçenek sırası (`karisik_sira`) Python'un rastgele üretecine bağlı. Kayda asıl seçenek
yazıldığı için bit-eşit port gerekmez; sıra masaüstündekinden farklı olur ama puanlamayı etkilemez.
**Doğrulama:** aynı `kayit_yaz` çağrı dizisi Python ve JS'te aynı kaydı üretir. `canli.html` betikli bir `tahta` +
`soru_sor` dizisini sunucusuz oynatır.

### ☐ F4a — Sürücü A, kendi anahtarla

- [ ] `js/egitmen/surucu-a.js`: ajan döngüsü (akışlı; araç çağrısı → araç sonucu; geçmiş yalnız sona eklenir)
- [ ] `js/qa/saglayici-anthropic.js`: küçük genişleme (`maxTokens`, `effort`, blok dizisi ileti, ham içerik dönüşü)
- [ ] Sıranın bitmesi: `bekle`/`dinle` gösterilmez; model susunca "dinliyor" ışığı yanar, öğrencinin sözü yeni tur açar
- [ ] Söz kesme: anlatım sürerken konuşulursa bekleyen `tahta` çağrısı `kullanici_konustu` ile döner
- [ ] Ayarlar'da kaynak seçimi; üst çubukta oturum maliyeti
- [ ] Önbellek: araçlar + talimat sabit önek; sistem metnine tarih ya da öğrenci adı konmaz

**Doğrulama:** sahte sağlayıcıyla döngü testleri (birden çok araç çağrısı, `max_tokens`, ret, söz kesme). Gerçek
bir derste ikinci istekten itibaren önbellekten okunan token sayısı sıfırdan büyük olmalı. **Bu fazda gerçek
kullanım ölçülür;** kurum bütçesi bu ölçüme göre verilir.

### ☐ F4b — Kurum vekili

- [ ] `bulut/vekil/isci.js`, `wrangler.toml`, `OKU.md`
- [ ] Sorumluluklar: köken izin listesi (CORS), yalnız `POST /v1/messages`, model ve `max_tokens` sınırı, sınıf
      kodunu doğrulayıp gizli anahtarla değiştirme, kod başına günlük sayaç, gövdeyi hiç kaydetmeme, akışı aynen geçirme

**Doğrulama:** sahte üst akışla vekil testleri; geçersiz kod 401, sınır aşımı 429 döner.

### ☐ F5 — Ses

- [ ] `canli.html`'e `js/ses/` adaptörleri: Piper WASM (seçmeli, ~60 MB indirme), Whisper
- [ ] `canli.js:87-90` `ses.wav()` Piper'a; `:349`, `:360`, `:567` Duyu yuvası Whisper'a bağlanır
- [ ] `js/yerel/terim.js` (`terim_sozlugu.py` portu; `difflib` oranları eşlik testiyle)

**Not:** GitHub Pages özel HTTP başlığı vermez; çok iş parçacıklı WASM için gereken yalıtım hilesi eklenmez
(YouTube gömmelerini bozabilir). Tek iş parçacığı yeterli mi, `ses-testi/` ile ölçülür.

### ☐ F6 — PDF ve makaleler

- [ ] `vendor/` içine pdf.js (`tools/vendor-hazirla.sh`)
- [ ] `js/yerel/pdf.js`: metin çıkarma, sayfa görüntüsü, şekil kırpma
- [ ] `js/yerel/makale.js`: bırakılan PDF'i DOI ya da başlıkla eşleme; açık erişim bağlantıları (OpenAlex,
      Europe PMC, Unpaywall)
- [ ] `js/board.js:360` kaynak düğmesi sayfayı pdf.js ile çizer
- [ ] `bilgi_ara`: tarayıcı araması makale metni, öğretmen notları, soru bankası ve vakalarla genişler

**Bırakılan:** yayınevi sayfasından otomatik indirme, İndirilenler taraması, anlam araması.

### ☐ F7 — Ders sonu ve değerlendirme

- [ ] `ders_bitir`, tekrar kartları, rapor indirme
- [ ] Arşivle ve geri yükle (`zip.js` yazıcısı: CRC32 + `CompressionStream`)
- [ ] `js/yerel/degerlendirme.js`; `degerlendirme.html` web'de açılır

### ☐ F8 — Öğretmen sihirbazı

- [ ] `js/yerel/sihirbaz.js`: taslaklar, DOI künyesi (Crossref, OpenAlex), docx ve PDF notu bölme, kural önerileri,
      denetim, iki zip üretip indirme
- [ ] `sihirbaz_oku` ve `sihirbaz_oner` araçları; sayfada "öneri iste" düğmesi sürücü A'yı kullanır
- [ ] Öğretmen araçları Ayarlar'daki bir seçenekle açılır (`*-ogrenci` dalları web için gereksizdir)

**Doğrulama:** JS'in ürettiği paket Python `paketi_incele`'den ve F1 kurulumundan geçer.

### ☐ F9 — Sürücü C (uzak MCP)

- [ ] `bulut/aktarici/`: Worker + oda başına kalıcı nesne; sekme WebSocket ile bağlanır, araç listesini kendisi yollar
- [ ] `js/egitmen/surucu-c.js`; eşleştirme kodu ve bağlayıcı adresi ekranı

### ☐ F10 — Kapanış

- [ ] Kılavuz (`kilavuz.html`) web kurulumuna göre yeniden yazılır
- [ ] Açılış sayfası; WASM dosyalarının `vendor/` içine alınması
- [ ] `web` → `main` birleşme kararı

## Web'de kötüleşecek ya da gidecek olanlar

| Bugün | Web'de |
|---|---|
| Pocket sesi (~1 GB) | Piper WASM (~60 MB) ya da tarayıcının sesi |
| Duyu dikte motoru | Tarayıcının konuşma tanıması ya da Whisper |
| Yayınevinden otomatik PDF indirme, kampüs ağıyla erişim, İndirilenler taraması | Açık erişim bağlantısı listelenir; öğrenci indirip siteye bırakır |
| Anlam araması (e5 modeli, ~120 MB) | Sözcük araması (BM25 + Türkçe–İngilizce terim eşlemesi) |
| Ortak bulut klasörü, klasörü aç, güncelleyici, eski sürüm temizliği, Claude'u otomatik uyandırma | Yok (web'de gereksiz) |
| Disk üstünde 5 döner yedek | Kayıtlar tarayıcı deposunda; kalıcı depolama izni, "Kaydımı indir" ve ders sonunda hatırlatma |
| Canlı eğitmen ek ücretsiz (öğrencinin aboneliği) | A yolunda kullanım kuruma yazılır; C yolunda bugünkü gibi |

## Riskler

- **Adres değişirse veri görünmez olur.** Tarayıcı depolaması adrese (kökene) bağlıdır. Sonradan özel alan adına
  geçmek bütün dersleri ve kayıtları görünmez kılar. `<hesap>.github.io` altındaki bütün proje siteleri de aynı
  kökeni paylaşır. Kalıcı adres, öğrenciler başlamadan seçilmeli.
- **Tarayıcı veriyi silebilir.** Özellikle Safari, uzun süre açılmayan sitelerin verisini silebilir. Dersler
  yeniden kurulabilir; kayıtlar için dışa aktarma hatırlatması şarttır.
- **Sınıf kodu sızarsa** vekil genel amaçlı bir API'ye dönüşür. Model ve çıktı sınırı, günlük sayaç ve kod yenileme
  bunu daraltır.
- **Maliyet ölçülmedi.** Sabit önek (araçlar + talimat + eğitmen kuralları) kabaca 25–30 bin token; 40 dakikalık
  derste onlarca istek olur. F4a'da ölçülmeden bütçe verilmemeli.
- **Gizlilik.** Kurum anahtarıyla öğrencinin sözleri ve adı kurum hesabı üzerinden modele gider; aydınlatma metni
  gerekir.

## Karar bekleyenler

- [ ] Kalıcı alan adı
- [ ] A yolunda varsayılan model ve bütçe (F4a ölçümünden sonra)
- [ ] Öğrenci adı modele gitsin mi; aydınlatma metni
- [ ] Kök adres oynatıcı mı, ana ekran mı olsun

## Uygulama sırasında doğrulanacaklar

Bunlar varsayım değildir; ilgili fazda güncel belgelerden ve tarayıcıda sınanarak doğrulanacak.

- claude.ai özel bağlayıcı koşulları: yetkilendirme, hangi planlarda açık, araç çağrısı zaman aşımı (F9)
- Safari: depolama silme politikası ve `navigator.storage.persist()` davranışı; `DecompressionStream`; videoda Range (F1)
- Açık erişim PDF sunucularının CORS izni (F6)
- Piper'ın ana iş parçacığını takıp takmadığı (F5)
- `js/qa/qa.js` içindeki fiyat tablosunun güncelliği (F4a)

## Yayın için gerekenler

1. `web` dalı GitHub'a itilir.
2. Depo sahibi **Settings › Pages**'te kaynağı **GitHub Actions** yapar.
3. Depo sahibi **Settings › Environments › github-pages**'te `web` dalına yayın izni verir.

Bundan sonra `web` dalına her itmede `.github/workflows/web-yayin.yml` denetimleri koşar ve siteyi yayımlar.
