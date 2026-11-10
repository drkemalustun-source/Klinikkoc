# Makaleler ve ders paketleri

Bir ders paketinde makalelerin kendisi değil, **yalnız listesi** vardır: künye ve DOI. KlinikKoç makaleleri
öğrencinin bilgisayarına kendisi indirir, okur ve eğitmenin aramasına ekler. Abonelikli bir makalenin PDF'i
ya da metni hiçbir zaman pakete veya depoya girmez.

## Öğrenci için

1. KlinikKoç ana sayfasında **Makaleler ve ders paketleri** bağlantısını açın
   (ya da Claude'a "makaleler sayfasını aç" deyin).
2. Öğretmeninizin verdiği ders paketini (.zip) **Ders paketi ekle** alanına bırakın. Ders kurulur ve
   makaleler aranmaya başlar.
3. Liste dolunca her makalenin yanında durumu görünür:
   - **Hazır**: indirildi, okundu, eğitmen bu makalede arama yapabilir.
   - **Eksik**: bulunamadı. **Yayıncı sayfasını aç** düğmesiyle makalenin sayfasına gidin, PDF'i indirin
     ve sayfadaki **PDF'leri buraya bırakın** alanına sürükleyin. KlinikKoç PDF'teki DOI'den hangi makale
     olduğunu kendisi bulur.
   - **Okunamadı**: PDF indi ama içinden metin çıkmadı (taranmış bir PDF olabilir).
4. Listede olmayan kendi makalenizi de aynı alana bırakabilirsiniz; "sizin eklediğiniz" diye ayrı görünür
   ve istediğiniz zaman dersten çıkarabilirsiniz.

Makaleler şu sırayla aranır:

| Sıra | Nereden | Not |
|---|---|---|
| 1 | Ders paketi | Yalnız açık lisanslı (ör. CC BY) makaleler pakete konabilir |
| 2 | Makale klasörü | `Belgeler\KlinikKoç Makaleler`. Daha önce inmiş makale yeniden indirilmez |
| 3 | Açık erişim | OpenAlex ve Europe PMC (PubMed Central) |
| 4 | Yayıncı | doi.org üzerinden. Bilgisayar üniversite ağındaysa (eduroam ya da VPN) abonelikli dergiler de çoğu zaman iner |

KlinikKoç hiçbir kullanıcı adı ya da şifre kullanmaz. Bazı yayıncılar otomatik indirmeye izin vermez; o zaman
makale "eksik" görünür ve yukarıdaki gibi elle eklenir.

### Kendi makalelerim (derse bağlı olmayan PDF'ler)

Öğrenci hiç ders yüklemeden de kendi PDF'leriyle çalışabilir. Makaleler sayfasında **Kendi makalelerim** seçiliyken
(hiç ders yoksa zaten seçilidir) bırakılan PDF bu kişisel kitaplığa girer: `lessons/kendi-makalelerim/` klasörü ilk
eklemede kendiliğinden kurulur, PDF `Belgeler\KlinikKoç Makaleler\Kendi makalelerim\` klasörüne kopyalanır, metni
okunup aramaya eklenir. Ana sayfadaki ders listesinde görünmez. Eğitmen `egitmen_hazirla(ders="kendi-makalelerim")`
ile bu makalelerle serbest çalışır (varsayılan Mercan, İnci de seçilebilir); yalnız bu makalelerdeki bilgiyle konuşur.
Claude'dan eklemek için: `makale_ekle(ders="kendi-makalelerim", dosya=...)`.

### Makale klasörü

İnen bütün PDF'ler `Belgeler\KlinikKoç Makaleler\<ders adı>\` klasöründe durur (Mac'te
`Belgeler/KlinikKoç Makaleler`). Bu klasör sizindir: istediğiniz yere yedekleyebilirsiniz. Bir ders
silinse ya da arşivlense de PDF'ler burada kalır; ders yeniden kurulunca KlinikKoç önce buraya bakar.

## Ders bitince: rapor, tekrar kartları ve arşiv

**Tamamlama raporu (her zaman).** Öğrenci dersi bitirince eğitmen `ders_bitir` aracıyla raporu yazar:
hedefler, zorlanılan konular, vakalar, çalışma süresi ve öğrencinin notu. Rapor öğrencinin kayıt klasöründe
(`<kimlik>/raporlar/<ders>_tamamlama.md`) durur, hiçbir yere gönderilmez. Ders yerinde kalır.

**Tekrar kartları.** Öğrencinin zorlandığı sorular (ders başına en çok 10) yalnız metin olarak
`<kimlik>/tekrar/kartlar.json` dosyasına yazılır. Kartlar arşivin dışındadır: ders arşivde olsa bile zamanı
gelince (3, 7, 21, 60 gün aralıklarla) `tekrar_listesi`nde çıkar; sonuç `tekrar_karti_yaz` ile işlenir.

**Depolama sınırı.** Varsayılan 2 GB; "Makaleler ve ders paketleri" sayfasının **Depolama ve arşiv** bölümünden
değiştirilir. Sayılan: ders klasörleri, arama dizini ve derslerin makale PDF'leri. Sınır aşılınca sayfa ve eğitmen
"Hangi dersleri arşive kaldıralım?" diye sorar. **Arşivleme otomatik değildir**; öğrenci seçer.

**Arşivleme.** Sıra şöyledir; bir adım başarısız olursa hiçbir şey silinmez:

1. Her öğrenci için tamamlama raporu (yoksa ya da eskiyse) ve tekrar kartları yazılır.
2. `Belgeler\KlinikKoç Arşiv\<ders>_<tarih>.zip` hazırlanır: ders dosyaları (ses ve video hariç), ilerleme
   kayıtları, raporlar, karneler, makale listesi ve durumu. PDF yoktur; PDF'ler `Belgeler\KlinikKoç Makaleler\<ders>`
   klasöründe kalır.
3. Zip açılıp denetlenir (bozuk mu, ders dosyaları eksiksiz mi).
4. Ancak sonra dersin klasörü (makale metinleri, sesler dahil) ve arama dizinindeki parçaları silinir.
   Öğrenci kayıtları ve tekrar kartları silinmez.

**Geri yükleme.** Arşiv listesindeki **Geri yükle** düğmesi ya da zip'i sayfaya bırakmak. Ders kurulur; ilerleme
kayıtları geri yazılır (bu bilgisayarda daha yeni bir kayıt varsa o korunur); PDF'ler önce makale klasöründe aranır,
olmayanlar yeniden indirilmeye çalışılır; ders yeniden dizinlenir.

## Öğretmen için: makale listesi

Makale listesi `lessons/<ders>/kaynaklar/kaynaklar.json` dosyasındadır:

```json
{
  "kaynaklar": [
    { "id": "herrera-2018", "doi": "10.1111/jcpe.12941", "rol": "ana",
      "kisa": "Herrera ve ark. 2018",
      "atif": "Herrera D, Retamal-Valdes B, Alonso B, Feres M. Acute periodontal lesions ... J Clin Periodontol. 2018;45 Suppl 20:S78–S94." },
    { "id": "ders-notu", "kisa": "Ders notu", "dosya": "ders-notu.pdf", "lisans": "CC BY 4.0", "acik": true }
  ]
}
```

| Alan | Anlamı |
|---|---|
| `id` | Kısa, değişmeyen kimlik (küçük harf, tire) |
| `doi` | Makalenin DOI'si. Makale bulucu bununla arar |
| `rol` | `ana` (derlemenin kendisi) ya da boş (destekleyici makale) |
| `kisa`, `atif` | Öğrenciye ve eğitmene gösterilen künye |
| `dosya` | Yalnız açık lisanslı ise pakete konan PDF'in adı (aynı klasörde) |
| `sayfalar`, `sil`, `bitis` | İsteğe bağlı okuma ayarları; varsayılan olarak "References" başlığından sonrası alınmaz |

Ders paketi, içinde tek bir ders klasörü olan bir zip'tir (`<ders>/egitmen.json`, `<ders>/kaynaklar/...`).
Komut satırından da kurulabilir: `python tools/ders_paketi.py --yukle paket.zip`.

## Komut satırı

```
python tools/ders_sonu.py --depolama
python tools/ders_sonu.py --sinir 5
python tools/ders_sonu.py --rapor <öğrenci kimliği> <ders>
python tools/ders_sonu.py --arsivle <ders>
python tools/ders_sonu.py --geri-yukle "<arşiv.zip>"
```


```sh
python tools/makale_bulucu.py --hazirla <ders>        # bul, indir, oku, aramaya ekle
python tools/makale_bulucu.py --durum <ders>
python tools/makale_bulucu.py --ekle <ders> makale.pdf [--kaynak <id>]
python tools/makale_bulucu.py --kur                   # PDF okuyucu (pypdf); KUR dosyası bunu kendisi yapar
```

`KLINIK_KOC_EPOSTA` ortam değişkenine bir e-posta adresi yazılırsa Unpaywall da sorulur (Unpaywall bir
iletişim adresi ister). `KLINIK_KOC_MAKALE` makale klasörünün yerini değiştirir.

Okunan makale metinleri `lessons/<ders>/makale-metin/` altında durur. Bu klasör her bilgisayarda yeniden
üretilir; yayın denetimi onu depoya sokmaz.
