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
