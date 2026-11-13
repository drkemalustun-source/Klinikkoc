"""3.5.0 testleri: tek tuşla güncelleme, öğrenci/öğretmen sürümü, ana ekran seçimi, program önerileri,
sihirbazın yeni listeleri. İnternete çıkmaz.  Çalıştırma:  python -m unittest discover -s tools/testler -v
"""
import io
import os
import sys
import tempfile
import unittest
os.environ.setdefault("KLINIK_KOC_ANLAM_KURMA", "1")  # testler anlam aramasını arka planda kurmaya kalkmasın
import zipfile

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(KOK, "tools"))

import ana_ekran  # noqa: E402
import sihirbaz as sh  # noqa: E402
import surum  # noqa: E402

ORTAM = ("KLINIK_KOC_VERI", "KLINIK_KOC_KAYIT", "KLINIK_KOC_MAKALE", "KLINIK_KOC_TUR", "HOME", "OneDrive")


class Gecici(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.ortam = {k: os.environ.get(k) for k in ORTAM}
        os.environ["KLINIK_KOC_VERI"] = os.path.join(t, "veri")
        os.environ["KLINIK_KOC_KAYIT"] = os.path.join(t, "veri", "kayitlar")
        os.environ["KLINIK_KOC_MAKALE"] = os.path.join(t, "ev", "Documents", "KlinikKoç Makaleler")
        os.environ["HOME"] = os.path.join(t, "ev")
        os.environ.pop("OneDrive", None)
        os.environ.pop("KLINIK_KOC_TUR", None)
        os.makedirs(os.path.join(t, "ev", "Documents"))

    def tearDown(self):
        for k, v in self.ortam.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()


def surum_zipi(surum_no, ek=None, eksik=()):
    dosyalar = {"SURUM": surum_no + "\n", "tools/sunucu.py": "# sunucu " + surum_no, "ana.html": "<ana %s>" % surum_no,
                "canli.html": "<canli>", "sihirbaz.html": "<sihirbaz>", "js/sihirbaz.js": "// s",
                "lessons/katalog.json": "[]", "ses/ses-ayari.json": '{"yeni": true}', "BASLAT-Mac.command": "#!/bin/sh\n"}
    dosyalar.update(ek or {})
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for ad, icerik in dosyalar.items():
            if ad not in eksik:
                z.writestr("Klinikkoc-main/" + ad, icerik)
    return b.getvalue()


class Guncelleme(Gecici):
    def kur(self, ogrenci=False):
        kok = os.path.join(self.tmp.name, "program")
        for ad, icerik in {"SURUM": "3.4.0\n", "tools/sunucu.py": "# eski", "ana.html": "<eski>", "canli.html": "<c>",
                           "eski-dosya.txt": "artık yok", "lessons/dersim/ders.json": "{}", "lessons/katalog.json": "[1]",
                           "ses/ses-ayari.json": '{"benim": 1}'}.items():
            yol = os.path.join(kok, *ad.split("/"))
            os.makedirs(os.path.dirname(yol), exist_ok=True)
            with open(yol, "w", encoding="utf-8") as f:
                f.write(icerik)
        if ogrenci:
            with open(os.path.join(kok, "SURUM-TURU"), "w", encoding="utf-8") as f:
                f.write("ogrenci\n")
        else:
            with open(os.path.join(kok, "sihirbaz.html"), "w", encoding="utf-8") as f:
                f.write("<eski sihirbaz>")
        return kok

    def oku(self, kok, ad):
        with open(os.path.join(kok, *ad.split("/")), encoding="utf-8") as f:
            return f.read()

    def test_surum_karsilastirma(self):
        self.assertTrue(surum.yeni_mi("3.5.0", "3.4.0"))
        self.assertTrue(surum.yeni_mi("3.10.0", "3.9.9"))
        self.assertFalse(surum.yeni_mi("3.4.0", "3.4.0"))
        self.assertFalse(surum.yeni_mi("3.3.9", "3.4.0"))

    def test_guncelleme_dersleri_ve_ayarlari_korur(self):
        kok = self.kur()
        r = surum.uygula(surum_zipi("3.5.0"), kok=kok)
        self.assertTrue(r["guncellendi"])
        self.assertEqual(self.oku(kok, "SURUM").strip(), "3.5.0")
        self.assertEqual(self.oku(kok, "ana.html"), "<ana 3.5.0>")
        self.assertEqual(self.oku(kok, "lessons/katalog.json"), "[1]")          # kurulu dersler durur
        self.assertTrue(os.path.isfile(os.path.join(kok, "lessons", "dersim", "ders.json")))
        self.assertEqual(self.oku(kok, "ses/ses-ayari.json"), '{"benim": 1}')  # kullanıcının ayarı durur
        self.assertFalse(os.path.exists(os.path.join(kok, "eski-dosya.txt")))   # artık olmayan dosya gider
        self.assertTrue(os.path.isfile(r["yedek"]))

    def test_ayni_surum_kurulmaz(self):
        kok = self.kur()
        r = surum.uygula(surum_zipi("3.4.0"), kok=kok)
        self.assertFalse(r["guncellendi"])
        self.assertEqual(self.oku(kok, "ana.html"), "<eski>")

    def test_ogrenci_surumu_ogretmen_dosyasi_almaz(self):
        kok = self.kur(ogrenci=True)
        surum.uygula(surum_zipi("3.5.0"), kok=kok)
        self.assertFalse(os.path.exists(os.path.join(kok, "sihirbaz.html")))
        self.assertFalse(os.path.exists(os.path.join(kok, "js", "sihirbaz.js")))
        self.assertEqual(self.oku(kok, "SURUM-TURU").strip(), "ogrenci")

    def test_bozuk_zip_reddedilir(self):
        kok = self.kur()
        with self.assertRaises(ValueError):
            surum.uygula(surum_zipi("3.5.0", eksik=("canli.html",)), kok=kok)
        with self.assertRaises(ValueError):
            surum.uygula(surum_zipi("3.5.0", ek={"../disari.txt": "x"}), kok=kok)
        self.assertEqual(self.oku(kok, "SURUM").strip(), "3.4.0")
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "disari.txt")))

    def test_yarida_kalan_guncelleme_geri_doner(self):
        kok = self.kur()
        asil = surum._yaz

        def bozuk(k, goreli, veri, calistirilabilir=False):
            if goreli == "canli.html" and veri == b"<canli>":
                raise OSError("disk doldu")
            return asil(k, goreli, veri, calistirilabilir)
        surum._yaz = bozuk
        try:
            with self.assertRaises(RuntimeError):
                surum.uygula(surum_zipi("3.5.0"), kok=kok)
        finally:
            surum._yaz = asil
        self.assertEqual(self.oku(kok, "SURUM").strip(), "3.4.0")
        self.assertEqual(self.oku(kok, "ana.html"), "<eski>")
        self.assertEqual(self.oku(kok, "eski-dosya.txt"), "artık yok")

    def test_ogrenci_surumu_yap(self):
        kok = self.kur()
        surum.ogrenci_surumu_yap(kok)
        self.assertFalse(os.path.exists(os.path.join(kok, "sihirbaz.html")))
        self.assertEqual(self.oku(kok, "SURUM-TURU").strip(), "ogrenci")

    def test_denetim_internetsiz_sorun_cikarmaz(self):
        def yok(*a, **k):
            raise OSError("ağ yok")
        d = surum.denetle(zorla=True, indir=yok)
        self.assertFalse(d["var"])
        self.assertIn("hata", d)
        d = surum.denetle(zorla=True, indir=lambda *a, **k: b"99.0.0\n")
        self.assertTrue(d["var"])
        self.assertEqual(d["yeni_surum"], "99.0.0")

    def test_tur_ortam_degiskeniyle(self):
        os.environ["KLINIK_KOC_TUR"] = "ogrenci"
        self.assertEqual(surum.tur(), "ogrenci")
        os.environ["KLINIK_KOC_TUR"] = "ogretmen"
        self.assertTrue(surum.ogretmen_mi())


class AnaEkran(Gecici):
    def test_ozet_ve_secim(self):
        o = ana_ekran.ozet(guncelleme=False)
        for alan in ("surum", "tur", "dersler", "pdfler", "secim"):
            self.assertIn(alan, o)
        s = ana_ekran.secim_yaz(["olmayan-ders"], ["olmayan-pdf"])
        self.assertEqual(s["dersler"], [])   # kurulu olmayan seçilemez
        self.assertEqual(s["pdfler"], [])

    def test_program_onerisi(self):
        r = ana_ekran.oneri_ekle(None, [{"tur": "eksik_cizim", "metin": "Furkasyon için hazır şablon yok."},
                                        {"tur": "bilinmeyen", "metin": "Altyazı daha büyük olabilir."},
                                        {"tur": "eksik_cizim", "metin": "Furkasyon için hazır şablon yok."},
                                        {"tur": "diger", "metin": ""}])
        self.assertEqual(r["eklenen"], 2)                      # yinelenen ve boş olan eklenmez
        var = ana_ekran.oneriler()
        self.assertEqual({x["tur"] for x in var}, {"eksik_cizim", "diger"})
        self.assertNotIn("ders", var[0])
        adres = ana_ekran.gonderme_adresi()
        self.assertTrue(adres.startswith("https://github.com/%s/issues/new?" % surum.DEPO))
        self.assertIn("Furkasyon", ana_ekran.oneri_metni())
        ana_ekran.oneri_isaretle([var[0]["id"]])
        ana_ekran.oneri_sil(var[1]["id"])
        self.assertEqual(len(ana_ekran.oneriler()), 1)
        self.assertTrue(os.path.isfile(os.path.join(ana_ekran.oneri_klasoru(), "program-onerileri.md")))


class SihirbazYeniListeler(Gecici):
    def test_onemli_cizim_video(self):
        d = "deneme-yeni"
        sh.yeni(d, "Deneme")
        sh.oge_kaydet(d, "hedefler", {"baslik": "Cebi tanımlar", "bloom": "anla"})
        sh.oge_kaydet(d, "onemli", {"metin": "Sondalamada kanama iltihabı gösterir.", "hedef": "H1"})
        sh.oge_kaydet(d, "cizimler", {"sablon": "dis", "varyant": "saglikli", "bitis": "periodontitis", "sure_sn": 99})
        sh.oge_kaydet(d, "videolar", {"adres": "https://youtu.be/abcdefghijk", "baslik": "Sondalama", "baslangic": "2:10"})
        with self.assertRaises(ValueError):
            sh.oge_kaydet(d, "videolar", {"adres": "https://ornek.com/video"})
        t = sh.taslak_oku(d)
        self.assertEqual(t["onemli"][0]["id"], "N1")
        self.assertEqual(t["cizimler"][0]["id"], "C1")
        self.assertEqual(t["cizimler"][0]["sure_sn"], 20)     # süre 1–20 sn arasında tutulur
        self.assertEqual(t["videolar"][0]["tur"], "youtube")
        self.assertEqual(t["videolar"][0]["baslangic"], 130)
        sh.oge_sil(d, "videolar", "V1")
        self.assertEqual(sh.taslak_oku(d)["videolar"], [])

    def test_youtube_kimligi_ve_saniye(self):
        self.assertEqual(sh.youtube_kimligi("https://www.youtube.com/watch?v=abcdefghijk&t=3"), "abcdefghijk")
        self.assertEqual(sh.youtube_kimligi("https://www.youtube.com/shorts/abcdefghijk"), "abcdefghijk")
        self.assertIsNone(sh.youtube_kimligi("https://vimeo.com/123"))
        self.assertEqual(sh.saniye("1:02:03"), 3723)
        self.assertEqual(sh.saniye("45"), 45)


if __name__ == "__main__":
    unittest.main()
