# Öğretmen kılavuzu

> Bu kılavuz iskelettir; 1. aşama bitince adım adım ekran görüntüleriyle tamamlanacak.

> **Kolay yol:** Dersi dosya yazmadan, ekrandan hazırlamak için [ders hazırlama sihirbazı](sihirbaz.md).
> Bu kılavuz dosyaları elle yazmak isteyenler içindir.

KlinikKoç'ta bir konu üç parçadan oluşur:

1. **Ders** (`lessons/<ders>/`): kısa temel anlatım, hedefler, sorular. Öğrenci vakada takılınca buraya döner.
2. **Kaynak** (`lessons/<ders>/kaynak/sayfa-01.txt` ...): ders notunuzun sayfa sayfa metni. Eğitmen
   bilgiyi buradan alır, sayfa numarasıyla gösterir ve bunun dışına çıkmaz.
3. **Vakalar** (`lessons/<ders>/vakalar/*.json`): dallanan klinik vakalar.

## 1. Ders klasörünü açın

Kendi notunuzdan yapılan dersin klasör adını `ozel-` ile başlatın, ör. `lessons/ozel-akut-lezyonlar/`.
Böylece hiçbir zaman açık depoya girmez ([ozel-icerik.md](ozel-icerik.md)).

## 2. Hedefleri ve Bloom düzeylerini yazın

Her alt hedefe bir hedef düzey verin (`"bloom": "uygula"` gibi). Düzeyler:

| Düzey | Öğrenci ne yapar? | Soru örneği |
|---|---|---|
| hatirla | Tanımı, sınıflamayı hatırlar | "Nekrotizan hastalıkların üç tipik bulgusu nedir?" |
| anla | Kendi sözleriyle açıklar | "Ateşin bu tabloda ne anlama geldiğini açıkla." |
| uygula | Bilgiyi yeni bir hastaya uygular | "Bu hastada hangi muayeneyi istersin?" |
| cozumle | Benzer tabloları ayırt eder | "Bu iki tabloyu ayıran tek bulgu hangisi?" |
| degerlendir | Bir kararı gerekçelendirir, savunur | "Antibiyotik vermek bu hastada doğru mu? Neden?" |
| olustur | Tedavi ya da izlem planı kurar | "Bu hasta için izlem planını yaz." |

## 3. Sorular: seçmeli ve açık uçlu

- Seçmeli sorularda her yanlış seçeneğe neden yanlış olduğunu (`why`) yazın.
- Açık uçlu sorularda (`"type": "open"`) **rubrik** ve **örnek cevap** zorunludur. Rubrikte her satır
  cevapta aranan tek bir öğedir; olmazsa olmaz öğeleri `"required": true` ile işaretleyin.
  Örnek:

```json
{
  "id": "y5b",
  "question": {
    "type": "open",
    "goal": "T2.1",
    "bloom": "uygula",
    "prompt": "Kendi dersinizden bir adım düşünün: anlatıcı \"kök yüzeyi\" dediği anda tahtada bir şeklin o bölgesi işaretlensin. Bu adımı nasıl yazardınız? Kendi cümlelerinizle anlatın.",
    "rubric": [
      {
        "criterion": "Anlatım metnine (say) bir işaret koyar, ör. {1}",
        "points": 1,
        "required": true
      },
      {
        "criterion": "Tahtaya önce görseli gösteren bir image komutu ekler",
        "points": 1
      },
      {
        "criterion": "Bölgeyi işaretleyen highlight komutuna aynı işaret numarasını (cue: 1) verir",
        "points": 1,
        "required": true
      }
    ],
    "modelAnswer": "Adımın anlatım metnine işaretin yerini koyarım: \"Şimdi {1}kök yüzeyine bakalım.\" Tahta komutlarına önce şekli açan bir image komutu, sonra cue değeri 1 olan bir highlight komutu eklerim. Anlatıcı {1} işaretine geldiği anda vurgu belirir.",
    "explanation": "Metindeki {1} işareti ile komuttaki cue: 1 eşleşir; anlatıcı o noktaya gelince komut çalışır."
  }
}
```

## 4. Vaka kartları

Şablon: [`sablonlar/vaka-karti-bos.json`](../sablonlar/vaka-karti-bos.json). Ayrıntı ve örnek:
[vaka-karti.md](vaka-karti.md). Gerçek hastadan uyarlanan her vaka için önce
[anonimlestirme.md](anonimlestirme.md) listesini doldurun.

## 5. Denetleyin

```sh
node tools/paketle.mjs            # dersleri denetler, ders listesini günceller
python tools/vaka_denetle.py      # vaka kartlarını denetler
python tools/bilgi_bankasi.py --dizinle   # arama dizinini günceller (canlı eğitmen bunu kendisi de yapar)
```

## 6. Öğrenciye verin

Fakülteye özel paket için `node tools/paketle.mjs --fakulte` çalıştırıp klasörü zip'leyin.
Öğrenci zip'i açar, `KUR-Windows`'a (Mac'te `KUR-Mac`'e) çift tıklar. Karnesi ve kaydı öğrencinin bilgisayarında kalır;
isterse raporunu size kendisi gönderir.

## 7. Pilot ölçme testleri (isteğe bağlı)

Araştırma için ön test, son test ve gecikmeli test `egitmen.json` → `olcme` alanında tanımlanır. Sorular siz
onaylayana kadar (`"durum": "onaylandi"`) eğitmen test yapmaz.

```json
"olcme": {
  "durum": "onaylandi",
  "plan": {"on": "A", "son": "B", "gecikmeli": "A", "gecikmeli_en_erken_gun": 21, "capraz": true},
  "formlar": {"A": [ ... ], "B": [ ... ]}
}
```

- **Çapraz formlar** (`"capraz": true`, iki form olmalı): öğrencilerin yarısı planı olduğu gibi (A→B→A), öbür yarısı
  formları yer değiştirmiş olarak (B→A→B) alır. Böylece iki formun zorluk farkı sonuçları bozmaz. Grup öğrenci
  numarasının son hanesinden belirlenir (çift: 1. grup, tek: 2. grup); numara verilmemişse kimlikten türetilir.
  Grup bir kez belirlenir, kayda ve her testin kaydına (`grup`) yazılır.
- **Kısa yazılı cevaplar** eğitmen tarafından ölçüte göre 0–2 puanlanır. Öğrencinin cevabı ayrıca kelimesi
  kelimesine (`ham_yanit`) kaydedilir; böylece Claude'un puanlarını sonradan körlemeli insan puanlamasıyla
  karşılaştırabilirsiniz (ör. Cohen kappa).
- **Araştırma dosyası:** `python tools/kayit_aktar.py anonim --hepsi` kimliksiz tek dosya üretir. Ham kısa cevapları da
  eklemek için `--ham-yanitlar` verin; bu serbest metindir, dosyayı paylaşmadan önce içinde ad ya da kimlik
  geçmediğini kontrol edin.
