# Bilgi bankası: kaynakta arama

Canlı eğitmen, bir cevaptan emin olmadığında ya da öğrenci ders dışı görünen bir şey sorduğunda
`bilgi_ara` aracıyla dersin kendi kaynaklarında arar ve bulduğu yerin sayfasını söyler.
Dizin tek bir SQLite dosyasıdır (`.dizin/bilgi.sqlite`); her bilgisayarda yeniden üretilir.

## Neler aranır?

| Tür | Nereden |
|---|---|
| `kaynak` | `lessons/<ders>/kaynak/sayfa-NN.txt` (ders notu ya da makale sayfaları; ~110 sözcüklük örtüşen parçalar) |
| `anlatim` | `ders.json` adımlarının anlatım metni |
| `soru` | Sorular, açıklamalar ve örnek cevaplar |
| `ogretmen_notu` | `egitmen.json` öğretmen notları |
| `vaka` | Vaka kartlarının özeti ve bulguları |

Her parça ders, tür, sayfa, bölüm, hedef ve vaka etiketleriyle saklanır; arama bunlarla süzülebilir.

## İki arama birlikte

1. **Sözcük araması** (SQLite FTS5): kurulum gerektirmez, her zaman açıktır. Türkçe ekler için uzun
   sözcüklerin ilk 5 harfiyle önek araması yapılır ("iltihabı" → "iltih*"); büyük İ/ı doğru küçültülür.
2. **Anlam araması** (isteğe bağlı): `multilingual-e5-small` (MIT lisanslı, ~120 MB, internetsiz çalışır)
   her parçayı bir sayı dizisine çevirir. Sorguya anlamca yakın parçalar aynı sözcükleri içermese de bulunur
   ("ateş ve halsizlik" → "sistemik tutulum").

İki sıralama "karşılıklı sıra birleştirme" (RRF) ile tek listeye indirilir. Anlam araması kurulu değilse
yalnız sözcük araması kullanılır; eğitmen yine çalışır.

## Kurulum ve kullanım

```sh
python tools/bilgi_bankasi.py --kur-anlam     # bir kez: onnxruntime, tokenizers, numpy + model (~120 MB)
python tools/bilgi_bankasi.py --dizinle       # değişen dersleri dizinler (eğitmen bunu kendisi de yapar)
python tools/bilgi_bankasi.py --ara "nekrotizan dişeti ateş" --ders ozel-akut-lezyonlar
python tools/bilgi_bankasi.py --durum
```

8 GB belleği olan sıradan bir dizüstünde dizinleme birkaç yüz parça için bir dakikanın altında sürer;
arama bir saniyenin altındadır.

## Dayanak etiketi

Arama her zaman bir sonuç listesi döndürür; "Diş beyazlatmada hangi jel daha etkili?" gibi ders dışı bir soruda
bile. Listedeki sıra puanı (RRF) yalnız sıradan hesaplanır, sonucun soruyla gerçekten ilgili olup olmadığını
söylemez. Bu yüzden `bilgi_ara` her sonucun yanında bir de **dayanak** etiketi verir:

| Etiket | Anlamı | Eğitmene giden talimat |
|---|---|---|
| `guclu` | Kaynakta bu soruya açıkça değinen bir parça var. | yok |
| `zayif` | İlgili olabilecek parça var ama soruyu tam karşılamıyor. | Yalnız parçanın açıkça söylediğini aktar; kalanını "kaynakta yok" diye ayır. |
| `yok` | Kaynakta bu soruya dayanak yok. | Ders dışı bilgi verme; "Bu sorunun cevabı ders kaynağında yer almıyor." de. |

### Ne ölçer?

- **Anlam benzerliği** (anlam araması açıksa): sorgu ile en yakın parça arasındaki benzerlik (kosinüs).
  multilingual-e5 benzerlikleri dar bir aralıkta (yaklaşık 0,75–0,90) toplanır; ayrım küçük farklarla olur.
- **Sözcük kapsamı** (her zaman): sorgunun anlamlı sözcüklerinden en iyi parçada geçenlerin payı (0–1).
  "hangi, daha, nasıl, nedir" gibi konu söylemeyen sözcükler sayılmaz. Nadir sözcükler daha ağır sayılır:
  derslerde hiç geçmeyen "beyazlatma" eksikse kapsam çok düşer.

Anlam araması açıksa iki etiketten yüksek olanı geçerlidir; kapalıysa yalnız sözcük kapsamına bakılır.
Etiket bütün adaylardan hesaplanır, yalnız gösterilen ilk sonuçlardan değil.

### Eşikler nasıl bulunur?

Eşikler tahminle değil ölçülerek konur:

```sh
python tools/dayanak_olc.py --ayrinti
```

Betik iki grup soru sorar: **ders içi** (her dersin `ders.json` soruları, `egitmen.json` hedef başlıkları ve
onaylı ölçme soruları) ve **ders dışı** (beyazlatma, ortodonti, kanal tedavisi, yemek, futbol gibi 20 soru).
Her iki sinyal için iki grubun dağılımını (en az, çeyrekler, en çok) yazar ve eşik önerir:

- **güçlü eşiği**: hiçbir ders dışı sorunun ulaşamadığı değer (en yüksek ders dışı değer + 0,02 pay);
- **zayıf eşiği**: ders dışı soruların en az %90'ının altında kaldığı değer.

Ders içeriği ekrana yazılmaz; yalnız sayılar. Özel dersler de ölçüme katılır, bu yüzden betik öğretmenin
bilgisayarında, anlam modeli kuruluyken çalıştırılmalıdır. Önerilen eşikler kendiliğinden yazılmaz; öğretmen
onaylarsa `tools/bilgi_bankasi.py` içindeki `DAYANAK_*` sabitlerine işlenir.

Şu anki değerler: anlam benzerliği zayıf ≥ 0,80, güçlü ≥ 0,84 (**geçici, henüz ölçülmedi**); sözcük kapsamı
zayıf ≥ 0,30, güçlü ≥ 0,60.

### Nasıl değiştirilir?

Kodu değiştirmeden ortam değişkenleriyle:

| Değişken | Ne |
|---|---|
| `KLINIK_KOC_DAYANAK_GUCLU` | anlam benzerliği güçlü eşiği |
| `KLINIK_KOC_DAYANAK_ZAYIF` | anlam benzerliği zayıf eşiği |
| `KLINIK_KOC_DAYANAK_SOZCUK_GUCLU` | sözcük kapsamı güçlü eşiği |
| `KLINIK_KOC_DAYANAK_SOZCUK_ZAYIF` | sözcük kapsamı zayıf eşiği |

Tarayıcıdaki oynatıcının soru-cevap araması (`js/qa/`) bu etiketi henüz kullanmaz.
