# Ses testi: adım adım kullanım

Bu sayfa iki işi karşılaştırır:

- **Konuşma tanıma:** söylediğinizi yazıya çevirme. Adaylar: tarayıcının kendi tanıyıcısı (Google sunucusu ve cihaz içi), Whisper, Duyu-small.
- **Seslendirme:** yazıyı sesli okuma. Adaylar: tarayıcının Türkçe sesi, üç Piper sesi.

Toplam süre yaklaşık 30–45 dakikadır. İlk açılışta modellerin indirilmesi bunun bir kısmını alır.

## 1. Gerekenler

- **Google Chrome**, güncel sürüm (Ayarlar > Chrome hakkında).
- **Python 3.** Sayfayı açan küçük sunucu Python ile çalışır.
  - Mac: Terminal'i açıp `python3 --version` yazın. Bir sürüm numarası görürseniz hazırsınız.
    Görmezseniz python.org'dan "macOS installer" indirip kurun.
  - Windows: python.org'dan "Windows installer" indirin. Kurulumun ilk ekranında
    **"Add python.exe to PATH"** kutusunu işaretleyin.
- **Mikrofon.** Mümkünse kulaklıklı mikrofon kullanın; dizüstünün kendi mikrofonu da olur.
- **Sessiz bir oda** ve **internet**. İlk indirmeler toplam 300–700 MB olabilir: Whisper small yaklaşık 250 MB,
  her Piper sesi yaklaşık 60 MB, Duyu yaklaşık 55 MB.

## 2. Sayfayı açma

1. Zip dosyasını açın. İçinde `akilli-tahta` klasörü var.
2. Terminali bu klasörde açın:
   - Mac: Terminal'e `cd ` yazın (sonunda bir boşluk olsun), `akilli-tahta` klasörünü Terminal penceresine sürükleyip bırakın, Enter'a basın.
   - Windows: Klasörü açın, üstteki adres çubuğuna `cmd` yazıp Enter'a basın.
3. Şu komutu yazıp Enter'a basın:
   - Mac: `python3 tools/sunucu.py`
   - Windows: `python tools\sunucu.py`
4. Tarayıcıda `http://localhost:8800/ses-testi/` açılır. Varsayılan tarayıcınız Chrome değilse bu adresi Chrome'a yapıştırın.
5. Test boyunca Terminal penceresini kapatmayın. İşiniz bitince Terminal'de **Ctrl+C**'ye basarak sunucuyu kapatın.

### Duyu-small için (isteğe bağlı, önerilir)

Duyu'nun motoru Python'da yazıldığı için birkaç Python paketine ihtiyaç duyar. Sunucuyu açmadan önce **bir kez** şunu çalıştırın:

- Mac: `python3 tools/sunucu.py --kur-duyu`
- Windows: `python tools\sunucu.py --kur-duyu`

Sonra sunucuyu yukarıdaki gibi açın. Terminal'de "Duyu-small: hazır" yazmalı.

## 3. Sayfadaki sıra

Sayfanın üstündeki sekmeleri soldan sağa izleyin.

1. **Hazırlık.** Denemek istediğiniz motorları işaretleyip **Seçilenleri hazırla**'ya basın. Modeller iner; her kartta indirme
   süresi ve boyutu görünür. Bir motor bu bilgisayarda çalışmıyorsa nedeni kartında yazar (ör. "Whisper large-v3-turbo"
   güçlü bir ekran kartı ister). Hata alan motoru atlayabilirsiniz.
2. **Kayıt.** 20 cümlenin her birini bir kez okuyun: **Kaydet**'e basın, cümleyi normal hızınızla okuyun, **Durdur**'a basın.
   **Dinle** ile kontrol edebilirsiniz. "Konuşma algılanmadı" yazarsa yeniden kaydedin. Kayıtlar tarayıcıda saklanır;
   sayfayı kapatsanız da kaybolmaz.
3. **Konuşma tanıma.** **Değerlendirmeyi başlat**'a basın. Her motor kayıtların hepsini dinler. Tarayıcının tanıyıcısı
   kaydı gerçek zamanlı dinlediği için onun turu birkaç dakika sürer; bu sırada sekmeyi açık tutun.
   - Tablo, her motorun hata oranını ve terimleri ne kadar doğru yazdığını gösterir. Aşağıda cümle cümle karşılaştırma
     vardır: kırmızı işaretli kelimeler yanlış ya da fazladır, üstü çizili olanlar eksiktir.
   - Tarayıcı tanıyıcısı hep boş sonuç veriyorsa "cümleleri canlı okuyacağım" kutusunu işaretleyip yeniden başlatın.
     Bu durumda cümleleri ekranda sırası gelince yüksek sesle okursunuz.
4. **Seslendirme.** Her cümlede **Dinle**'ye basın, iki puan verin ve yanlış okunan terimleri işaretleyin.
   20 cümlenin hepsi gerekmez; 6–8 cümle yeterli fikir verir. Sesleri tanımadan puanlamak için **Kör puanlama**'yı açın;
   o zaman ses adları "Ses A, Ses B…" diye gösterilir.
5. **Telaffuz sözlüğü.** Bir terim yanlış okunuyorsa buraya nasıl okunması gerektiğini yazıp **Dinle** ile deneyin.
   Beğendiğinizde **Kaydet**'e, kalıcı olması için **telaffuz.json olarak indir**'e basın ve dosyayı bana gönderin.
6. **Sonuçlar.** **Raporu indir**'e basın ve inen dosyayı bana gönderin. Dosyada ses kaydı yoktur; yalnızca sonuçlar ve
   bilgisayarın genel özellikleri (tarayıcı sürümü, işlemci çekirdeği, ekran kartı adı) vardır.

### İnternetsiz çalışmayı denemek (isteğe bağlı)

Hazırlıktan sonra Wi‑Fi'yi kapatın, **Tarayıcı · Google sunucusu** motorunun işaretini kaldırın ve 3. bölümü yeniden başlatın.
Çalışan motorların tablosunda "internetsiz denendi ✓" görünür.

## 4. Gizlilik

| Motor | Ses ya da metin bilgisayardan çıkar mı? |
|---|---|
| Tarayıcı · Google sunucusu | **Evet**, ses Google'a gönderilir. |
| Tarayıcı · cihaz içi | Hayır. |
| Whisper | Hayır. Model bir kez indirilir. |
| Duyu-small | Hayır. Sunucu aynı bilgisayarda çalışır. |
| Tarayıcının Türkçe sesi | Sese bağlı. Adında "Google" geçen sesler metni Google'a gönderir; "(cihazda)" yazanlar göndermez. |
| Piper | Hayır. Ses modeli bir kez indirilir. |

## 5. Sorun giderme

- **Mikrofon izni sorulmadı ya da reddedildi:** Adres çubuğunun solundaki simgeye tıklayıp mikrofona izin verin, sayfayı yenileyin.
- **"Bu sayfa güvenli bir adreste açılmamış":** Sayfayı dosyaya çift tıklayarak açmışsınız. 2. bölümdeki gibi sunucuyla açın.
- **"Python sunucusu bulunamadı" (Duyu kartında):** Sayfa sunucu olmadan açılmış ya da Terminal kapanmış.
- **"Address already in use":** 8800 numaralı kapı dolu. `python3 tools/sunucu.py --port 8801` ile açın.
- **"Model indirilemedi":** İnternet bağlantısını kontrol edin. Üniversite ağı huggingface.co sitesini engelliyorsa
  testi evde ya da telefonun internetiyle yapın.
- **Sayfa çok yavaşladı:** Whisper ekran kartı yoksa işlemcide çalışır ve yavaştır. "small" yerine "base" ile deneyin.
