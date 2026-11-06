# Vaka kartı

Bir vaka kartı, bir hastanın başvurusundan kapanışına kadar öğrencinin vereceği kararları sıralayan
tek bir JSON dosyasıdır: `lessons/<ders>/vakalar/<vaka>.json`. Şema: [`schema/vaka.schema.json`](../schema/vaka.schema.json).
Çalışan örnek: [`lessons/peri-implantitis-cerrahi/vakalar/ornek-implant-kanama.json`](../lessons/peri-implantitis-cerrahi/vakalar/ornek-implant-kanama.json) (kurgusal).
Boş şablon: [`sablonlar/vaka-karti-bos.json`](../sablonlar/vaka-karti-bos.json).

## Bölümler

| Alan | Ne yazılır |
|---|---|
| `baslik` | Tanıyı ele vermeyen kısa başlık ("Ağrılı dişeti ve ateş") |
| `kurgusal` | Uydurma vaka `true`; gerçek hastadan uyarlanmışsa `false` (o zaman `anonimlik` zorunlu) |
| `dagitim` | `acik` (paylaşılabilir) ya da `fakulte` (yalnız fakülte paketi; açık depoya giremez) |
| `hedefler` | Vakanın yokladığı alt hedefler (dersteki kimlikler) |
| `hasta` | Yaş **aralığı** (`40-49`), cinsiyet, sistemik durum, alışkanlıklar. Ad, tam yaş, tarih yok |
| `basvuru` | Şikâyet (hastanın sözleriyle) ve öykü |
| `bulgular` | Bütün bilgiler. `acilis: baslangic` olanlar vaka açılınca söylenir; ötekiler ancak öğrenci o muayeneyi isterse verilir |
| `dugumler` | Kararlar (aşağıda) |
| `kapanis` | Doğru akıl yürütmenin özeti ve öğrenme noktaları |

## Düğüm türleri

| Tür | Öğrenci ne yapar | Zorunlu alanlar |
|---|---|---|
| `veri` | Hangi muayeneleri isteyeceğini söyler | `gerekli_bulgular`, `sonraki` |
| `karar` | Seçeneklerden birini seçer, gerekçesini söyler | `soru`, `secenekler` (en az biri `dogru`) |
| `acik` | Kendi cümleleriyle cevaplar; rubrikle puanlanır | `soru`, `rubrik`, `ornek_cevap`, `sonraki` |
| `bilgi` | Dinler (gidişat, yeni bilgi) | `anlat`, `sonraki` |
| `son` | Vaka biter | `sonuc`: `iyi`, `kabul` ya da `kotu` |

Seçeneklerin `sonuc` değeri: `dogru`, `kabul` (savunulabilir ama en iyisi değil), `yanlis` ya da
`tehlikeli` (hastaya zarar verebilir; karnede ayrıca gösterilir). Yanlış bir seçimde `sonraki` yazılmazsa
öğrenci aynı düğümde ipucuyla yeniden dener. Farklı sonlara giden dallar kurabilirsiniz: ör. yanlış
tedavi seçimi `son-kotu` düğümüne gider ve gidişatı anlatır.

Her düğümde:
- `bloom`: düğümün düşünme düzeyi,
- `ipuclari`: hafiften belirgine kademeli ipuçları,
- `takilirsa`: öğrenci iki denemede ilerleyemezse eğitmenin yeniden anlatacağı ders bölümü (`bolum`)
  ya da not sayfası (`sayfa`) ve neye odaklanacağı (`not`).

## Denetim

```sh
python tools/vaka_denetle.py
```

Denetlenenler: zorunlu alanlar, düğüm bağlantıları, başlangıçtan her yolun bir sona varması,
hedeflerin ve bölümlerin derste bulunması, görsellerin varlığı, gerçek vakada anonimlik ve onam kaydı,
metinde kimlik ele verebilecek izler (tam tarih, telefon, 11 haneli numara, protokol no). Hatalı bir kart
canlı eğitmende açılmaz.

## Oynatıcıda vaka akışı

`node tools/paketle.mjs` dersin vaka kartlarını `vaka-paketi.json` dosyasında toplar. Bu dosyaya yalnız
`"dagitim": "acik"` olan ve adı `ozel-` ile başlamayan kartlar girer. Fakülteye özel kartlar yalnız `--fakulte` ile eklenir;
yayın denetimi, fakülteye özel kart içeren bir paketin depoya girmesine izin vermez.

Ders ekranındaki **Vakalar** düğmesi ders kartlarını listeler. Öğrenci şu adımlardan geçer:

1. Muayene ister. İstemediği gerekli bulgular ona gösterilir.
2. Karar verir. Yanlış seçimde ipucu açılır. İki yanlıştan sonra `takilirsa` bölümünü yeniden dinlemesi önerilir ve "Vakaya dön" düğmesiyle kaldığı yere döner.
3. Açık uçlu sorulara cevap verir ve kendini rubrikle puanlar.

Seçtiği yol, tahtada karar ağacı olarak büyür. Sonuçlar karneye, hastaya zarar verebilecek seçimler de karnede ayrı bir listeye geçer.
Yetersiz kalan vaka adımlarının aralıklı tekrar zamanı gelince vakayı yeniden çözmesi önerilir.

## Sözlü sınav provası ve dersler arası tekrar

- **Sözlü prova**, Hedefler ekranından ya da canlı modda `sozlu_prova` aracıyla açılır. Dersin ve vakaların açık uçlu soruları
  zayıf hedeflerden başlayarak sorulur. Öğrenci sesli cevap verir; bir soru için 90 sn önerilir. Sonra örnek cevap ve rubrik gelir,
  en sonda da sınav tarzı geri bildirim.
- **Bugünkü tekrar**, ders listesinin üstünde görünür. Bütün derslerde tekrar zamanı gelen soruları ve zayıf vaka adımlarını
  sırayla sorar. Canlı modda `tekrar_listesi` aracı aynı listeyi İnci'ye verir.
