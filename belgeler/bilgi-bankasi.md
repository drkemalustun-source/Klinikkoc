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
