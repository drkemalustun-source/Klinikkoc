# Öğretmen kılavuzu

> Bu kılavuz iskelettir; 1. aşama bitince adım adım ekran görüntüleriyle tamamlanacak.

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
  Örnek: `lessons/tanitim/ders.json` içindeki `y5b` adımı.

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
Öğrenci zip'i açar, `KUR.bat`'a (Mac'te `KUR.command`'a) çift tıklar. Karnesi ve kaydı öğrencinin bilgisayarında kalır;
isterse raporunu size kendisi gönderir.
