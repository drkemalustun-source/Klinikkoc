# Özel içeriğinizi nerede tutarsınız?

KlinikKoç'un açık deposu bilerek boştur. Kendi ders notlarınız, vakalarınız ve hasta görselleriniz
yalnız sizin bilgisayarınızda (ve kendi seçtiğiniz özel yedekte) durur.

| Ne | Nereye | Depoya girer mi? |
|---|---|---|
| Kendi notunuzdan yapılan ders | `lessons/ozel-<ad>/` | Hayır (`.gitignore`) |
| Gerçek hastadan uyarlanan vaka | `lessons/<ders>/vakalar/ozel-<ad>.json` | Hayır |
| O vakanın görselleri | `lessons/<ders>/vakalar/ozel-<ad>/...` | Hayır |
| Ham malzeme (fotoğraflar, Word, PDF) | `ozel/` | Hayır |
| Öğrenci kayıtları, karneler, raporlar | program dışındaki kalıcı kayıt klasörü (eski sürümlerde `kayitlar/`) | Hayır |
| Arama dizini, indirilen modeller | `.dizin/`, `.modeller/` | Hayır (her bilgisayarda yeniden üretilir) |
| Genel kod, şablonlar, kurgusal örnek vakalar | her yer | Evet |

## Güvenlik ağı

`python tools/yayin_denetimi.py` depoya girecek bütün dosyalara bakar ve şunlarda durur:

- `distribution: faculty` ya da `dagitim: fakulte` yazan bir ders,
- fakülteye özel ya da denetimden geçmeyen bir vaka kartı, hiçbir karta bağlı olmayan vaka görseli,
- `kayitlar/`, `ozel/`, `.dizin/`, `.modeller/` içinden bir dosya,
- depoya girmeyen bir dersi anan ders listesi (ör. `paketle.mjs --fakulte` sonrası),
- lisansı yazılmamış bir ders, 20 MB'tan büyük bir dosya.

Bir kez `python tools/yayin_denetimi.py --kanca` çalıştırırsanız bu denetim her commit'ten önce
kendiliğinden yapılır. GitHub'da da her yüklemede aynı denetim çalışır.
