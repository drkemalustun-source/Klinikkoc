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


class EskiSurumler(unittest.TestCase):
    def test_bul_yedekle_sil(self):
        import eski_surumler as es
        with tempfile.TemporaryDirectory() as t:
            def kur(yol, surum=None, dersler=()):
                os.makedirs(os.path.join(yol, "tools"))
                open(os.path.join(yol, "tools", "tahta-mcp.py"), "w").close()
                if surum:
                    with open(os.path.join(yol, "SURUM"), "w") as f:
                        f.write(surum)
                for d in dersler:
                    os.makedirs(os.path.join(yol, "lessons", d))
                    with open(os.path.join(yol, "lessons", d, "ders.json"), "w") as f:
                        f.write("{}")
                os.makedirs(os.path.join(yol, ".ses-ortami"))
                with open(os.path.join(yol, ".ses-ortami", "buyuk"), "wb") as f:
                    f.write(b"0" * 1000)
            yeni = os.path.join(t, "Belgeler", "KlinikKoc")
            eski = os.path.join(t, "Belgeler", "deneme", "klinikkoc-v3")
            kur(yeni, "4.1.0", ["ortak"])
            kur(eski, "3.1.0", ["ortak", "benim-dersim"])
            bulunan = es.bul([t], kendisi=yeni)
            self.assertEqual([x["yol"] for x in bulunan], [eski])  # çalışan kurulum listede yok
            self.assertEqual(bulunan[0]["yeni_kurulumda_olmayan_dersler"], ["benim-dersim"])
            yedek = os.path.join(t, "yedek")
            # bulunmayan / çalışan klasör silinmez
            s = es.temizle([yeni, os.path.join(t, "Belgeler")], kendisi=yeni, kokler=[t], yedek_yeri=yedek)
            self.assertTrue(all(x["durum"] == "atlandı" for x in s))
            self.assertTrue(os.path.isdir(yeni))
            s = es.temizle([eski], kendisi=yeni, kokler=[t], yedek_yeri=yedek)[0]
            self.assertEqual(s["durum"], "silindi")
            self.assertFalse(os.path.exists(eski))
            self.assertTrue(os.path.exists(os.path.join(yeni, "lessons", "benim-dersim", "ders.json")))
            import zipfile
            with zipfile.ZipFile(s["yedek"]) as z:
                adlar = z.namelist()
            self.assertIn("lessons/benim-dersim/ders.json", adlar)
            self.assertFalse(any(a.startswith(".ses-ortami") for a in adlar))


class OrtakKlasor(unittest.TestCase):
    def setUp(self):
        self.t = tempfile.TemporaryDirectory()
        self.eski = {k: os.environ.get(k) for k in ("HOME", "KLINIK_KOC_VERI", "KLINIK_KOC_KAYIT", "KLINIK_KOC_MAKALE",
                                                     "KLINIK_KOC_ORTAK", "USERPROFILE")}
        for k in self.eski:
            os.environ.pop(k, None)
        os.environ["HOME"] = os.environ["USERPROFILE"] = os.path.join(self.t.name, "ev")
        os.makedirs(os.path.join(self.t.name, "ev", "Documents"))
        os.environ["KLINIK_KOC_VERI"] = os.path.join(self.t.name, "veri")

    def tearDown(self):
        for k, v in self.eski.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.t.cleanup()

    def test_ayarla_kilit_kapat(self):
        import json
        import time
        import veri_yeri
        import ortak_klasor as ok
        import makale_bulucu as mb
        yerel_kayit = veri_yeri.kayit_kok()
        os.makedirs(os.path.join(yerel_kayit, "ali"))
        with open(os.path.join(yerel_kayit, "ali", "k.json"), "w") as f:
            f.write('{"a": 1}')
        pdf_klasor = os.path.join(veri_yeri.makale_kok(), "Kendi makalelerim")
        os.makedirs(pdf_klasor)
        with open(os.path.join(pdf_klasor, "sanz.pdf"), "wb") as f:
            f.write(b"%PDF-1.4")
        os.makedirs(os.path.join(veri_yeri.veri_kok(), "makaleler"))
        with open(os.path.join(veri_yeri.veri_kok(), "makaleler", "kendi-makalelerim.json"), "w") as f:
            json.dump({"kaynaklar": {"x": {"durum": "hazir", "pdf": "C:\\\\Users\\\\K\\\\Documents\\\\sanz.pdf"}}}, f)
        bulut = os.path.join(self.t.name, "OneDrive")
        os.makedirs(bulut)
        r = ok.ayarla(bulut)
        ortak = r["ortak_klasor"]
        self.assertEqual(veri_yeri.kayit_kok(), os.path.join(ortak, "kayitlar"))
        self.assertTrue(os.path.exists(os.path.join(ortak, "kayitlar", "ali", "k.json")))
        self.assertTrue(os.path.exists(r["yedek"]))
        self.assertTrue(os.path.exists(os.path.join(yerel_kayit, "ali", "k.json")))  # yerelde de kalır
        # Öbür bilgisayarın (Windows) yolu bu bilgisayardaki PDF'e çevrilir
        self.assertEqual(mb.durum_oku("kendi-makalelerim")["kaynaklar"]["x"]["pdf"],
                         os.path.join(ortak, "Makaleler", "Kendi makalelerim", "sanz.pdf"))
        self.assertIsNone(ok.durum().get("uyari"))
        with open(os.path.join(ortak, "kilit.json"), "w") as f:
            json.dump({"bilgisayar": "baska-pc", "zaman": time.time(), "saat": "12:00"}, f)
        self.assertIn("baska-pc", ok.durum()["uyari"])
        ok.kilit_tazele(zorla=True)  # başkasının taze kilidinin üstüne yazmaz
        with open(os.path.join(ortak, "kilit.json")) as f:
            self.assertEqual(json.load(f)["bilgisayar"], "baska-pc")
        os.rename(bulut, bulut + "-yok")  # bulut sürücüsü bağlı değil: yerel klasör + uyarı
        self.assertIn("ulaşılamıyor", ok.durum()["uyari"])
        self.assertEqual(veri_yeri.kayit_kok(), yerel_kayit)
        os.rename(bulut + "-yok", bulut)
        with open(os.path.join(ortak, "kayitlar", "ali", "yeni.json"), "w") as f:
            f.write("{}")
        self.assertEqual(ok.kapat()["durum"], "kapatıldı")
        self.assertEqual(veri_yeri.kayit_kok(), yerel_kayit)
        self.assertTrue(os.path.exists(os.path.join(yerel_kayit, "ali", "yeni.json")))  # geri kopyalandı


class RaporDuzeltmeleri(unittest.TestCase):
    """v4.0.2 deneme raporu (2026-11-13) düzeltmeleri."""

    def test_cizim_uyarilari(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("tahta_mcp_t", os.path.join(KOK, "tools", "tahta-mcp.py"))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        u = m.cizim_uyarilari([{"komutlar": [{"type": "draw", "shapes": [
            {"kind": "arrow", "x1": 1, "y1": 2, "x2": 3, "y2": 4},
            {"kind": "text", "x": 1, "y": 2, "text": "a", "font": 3},
            {"kind": "rect", "x": 1, "y": 2, "w": 3},
            {"kind": "kare"}]}]}])
        self.assertEqual(len(u), 3)
        self.assertIn("font", u[0])
        self.assertIn("eksik alan h", u[1])
        self.assertIn("bilinmeyen kind", u[2])

    def test_kendi_pdf_hazir_ders_eslemesi(self):
        import json
        import makale_bulucu as mb
        eski_kok, eski_veri = mb.KOK, os.environ.get("KLINIK_KOC_VERI")
        with tempfile.TemporaryDirectory() as t:
            try:
                mb.KOK = t
                os.environ["KLINIK_KOC_VERI"] = os.path.join(t, "veri")
                os.makedirs(os.path.join(t, "lessons", "kontur-dersi"))
                with open(os.path.join(t, "lessons", "kontur-dersi", "egitmen.json"), "w", encoding="utf-8") as f:
                    json.dump({"baslik": "Kontur", "kaynak": {"baslik": "Su H, Lee E. Considerations of implant abutment "
                               "and crown contour: critical contour and subcritical contour. Int J Periodontics "
                               "Restorative Dent. 2010;30:335-343."}}, f)
                mb.kendi_kitaplik_hazirla()
                mk = mb.metin_klasoru(mb.KENDI, "ogrenci-su")
                os.makedirs(mk)
                with open(os.path.join(mk, "sayfa-01.txt"), "w", encoding="utf-8") as f:
                    f.write("Considerations of Implant Abutment and Crown Contour: Critical Contour and Subcritical Contour")
                self.assertEqual(mb.hazir_ders_bul("ogrenci-su")["ders"], "kontur-dersi")
                with open(os.path.join(mk, "sayfa-01.txt"), "w", encoding="utf-8") as f:
                    f.write("Gingival recession in orthodontic patients")
                self.assertIsNone(mb.hazir_ders_bul("ogrenci-su"))
            finally:
                mb.KOK = eski_kok
                if eski_veri is None:
                    os.environ.pop("KLINIK_KOC_VERI", None)
                else:
                    os.environ["KLINIK_KOC_VERI"] = eski_veri


def _mcp():
    import importlib.util
    spec = importlib.util.spec_from_file_location("tahta_mcp_t2", os.path.join(KOK, "tools", "tahta-mcp.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class IkinciRaporDuzeltmeleri(Gecici):
    """v4.1.0 deneme raporu (2026-11-13) düzeltmeleri."""

    def test_sablon_uyarilari(self):
        m = _mcp()
        ciz = lambda **c: m.cizim_uyarilari([{"komutlar": [dict(type="draw", **c)]}])
        self.assertEqual(ciz(template="kontur-fasiyal", variant="kritik-fazla", labels="hepsi", highlight=["kritik"]), [])
        u = ciz(template="kontur-fasiyal", variant="konveks", gecis=3)
        self.assertEqual(len(u), 1)
        self.assertIn("'konveks' varyantı yok", u[0])
        self.assertIn("kritik-alti-konveks", u[0])
        u = ciz(template="kontur-fasiyal", etiket_surukle={"etiketler": ["kritik-kontur", "kritik-alti-kontur", "mukoza-kenari"]})
        self.assertEqual(len(u), 2)
        self.assertIn("kritik-alti", u[0])           # geçerli adlar listelenir
        self.assertIn("GÖSTERİLMEDİ", u[1])
        u = ciz(template="kontur-fasiyal", variant="duz", labels=["kayma", {"part": "kritik"}])
        self.assertIn("varyantında bu parçalar yok", u[0])
        self.assertIn("yok; hiçbir şey çizilmedi", ciz(template="kontur")[0])
        self.assertEqual(ciz(template="dis", variant="saglikli", isaretle={"soru": "?", "dogru": ["sement"]},
                             etiket_surukle={"etiketler": ["mine", "sement", "kemik"]}), [])

    def test_sablon_bilgisi_ve_dokum_guncel(self):
        import json
        import re
        m = _mcp()
        o = json.loads(m.ar_sablon_bilgisi({"template": "kontur-fasiyal", "variant": "duz"})["content"][0]["text"])
        self.assertEqual(o["parcalar"]["kritik"], "Kritik kontur")
        self.assertNotIn("kayma", o["bu_varyantta"])
        tum = json.loads(m.ar_sablon_bilgisi({})["content"][0]["text"])["sablonlar"]
        # Döküm js dosyalarıyla aynı şablonları içermeli (yeni şablon eklenince node tools/sablon_dokum.mjs unutulmasın).
        js = "".join(open(os.path.join(KOK, "js", d), encoding="utf-8").read()
                     for d in ("anatomi.js", "anatomi-bolge.js", "anatomi-kontur.js"))
        for ad in tum:
            self.assertRegex(js, r"['\"]?%s['\"]?\s*:\s*\{\s*ad:" % re.escape(ad))
        self.assertEqual(len(tum), len(re.findall(r"\n\s+['\"]?[a-z-]+['\"]?:\s*\{\s*ad:\s*'[^']+',\s*varyantlar:", js)))
        self.assertNotIn("kuron", json.dumps(list(v for s in m.sablonlar().values() for v in s["parcalar"].values()), ensure_ascii=False).lower())
        ilgili = m.dersle_ilgili_sablonlar("x", {"baslik": "İmplant dayanağı ve kron konturu: kritik ve kritik altı kontur"}, {})
        self.assertIn("kontur-fasiyal", ilgili)

    def _ders_kur(self, t, mb, sayfalar):
        import json
        dk = os.path.join(t, "lessons", "kontur-dersi")
        os.makedirs(os.path.join(dk, "kaynak"))
        os.makedirs(os.path.join(dk, "kaynaklar"))
        with open(os.path.join(dk, "egitmen.json"), "w", encoding="utf-8") as f:
            json.dump({"baslik": "Kontur", "kaynak": {"baslik": "Su H, Lee E. Considerations of implant abutment and "
                       "crown contour: critical contour and subcritical contour. IJPRD 2010."}}, f)
        with open(os.path.join(dk, "kaynaklar", "kaynaklar.json"), "w", encoding="utf-8") as f:
            json.dump({"kaynaklar": [{"id": "su-2010", "kisa": "Su ve ark. 2010", "rol": "ana", "pmid": "20664835",
                                      "atif": "Su H, Lee E. Considerations of implant abutment and crown contour: critical contour."}]}, f)
        for n, mt in sayfalar.items():
            with open(os.path.join(dk, "kaynak", "sayfa-%02d.txt" % n), "w", encoding="utf-8") as f:
                f.write(mt)

    def _kitaplik_kur(self, mb, sayfalar, ad="Su- critical.pdf"):
        mb.kendi_kitaplik_hazirla()
        pdf = os.path.join(mb.makale_klasoru(mb.KENDI), ad)
        os.makedirs(os.path.dirname(pdf), exist_ok=True)
        with open(pdf, "wb") as f:
            f.write(b"%PDF-1.4 sahte")
        mk = mb.metin_klasoru(mb.KENDI, "ogrenci-su")
        os.makedirs(mk)
        for n, mt in sayfalar.items():
            with open(os.path.join(mk, "sayfa-%02d.txt" % n), "w", encoding="utf-8") as f:
                f.write(mt)
        d = mb.durum_oku(mb.KENDI)
        d["ekler"] = [{"id": "ogrenci-su", "kisa": "Su- critical", "ogrenci": True}]
        d["kaynaklar"] = {"ogrenci-su": {"id": "ogrenci-su", "durum": "hazir", "pdf": pdf}}
        mb.durum_yaz(mb.KENDI, d)
        return pdf

    @staticmethod
    def _metin(n):
        import random
        r = random.Random(n)
        soz = ["contour", "margin", "papilla", "implant", "tissue", "gingival", "crown", "abutment", "critical", "bone",
               "facial", "profile", "zenith", "convex", "concave", "restoration", "height", "level", "apical", "coronal"]
        return " ".join(r.choice(soz) + str(r.randint(0, 9)).replace("0", "") for _ in range(400)).replace("1", "a").replace(
            "2", "b").replace("3", "c").replace("4", "d").replace("5", "e").replace("6", "f").replace("7", "g").replace("8", "h").replace("9", "i")

    def test_kendi_makalelerimden_bulur(self):
        import makale_bulucu as mb
        import makale_sekil
        eski = mb.KOK
        t = self.tmp.name
        try:
            mb.KOK = t
            ders = {1: "kapak", **{n: self._metin(n) for n in range(2, 11)}, 11: "telif"}
            self._ders_kur(t, mb, ders)
            # Aynı baskı, son iki sayfası eksik (Kemal'in kopyası): bağlanır, eksik sayfalar bildirilir.
            pdf = self._kitaplik_kur(mb, {n: ders[n] for n in range(1, 10)})
            hd = mb.hazir_ders_bul("ogrenci-su")
            self.assertEqual((hd["ders"], hd["eslesme"]), ("kontur-dersi", "icerik"))
            self.assertEqual(hd["sayfa_uyumu"]["kayma"], 0)
            k = mb.kaynaklar("kontur-dersi")[0]
            d = mb.kaynak_hazirla("kontur-dersi", k, ag_kullan=False)
            self.assertEqual((d["durum"], d["nereden"], d["pdf"]), ("hazir", "kendi-makalelerim", pdf))
            self.assertEqual(d["eksik_sayfalar"], [10])
            self.assertNotIn("sayfa_kaymasi", d)
            s = mb.durum_oku("kontur-dersi")
            s["kaynaklar"] = {"su-2010": d}
            mb.durum_yaz("kontur-dersi", s)
            self.assertEqual(makale_sekil.pdf_sayfasi("kontur-dersi", "su-2010", 4), 4)
            with self.assertRaises(ValueError):
                makale_sekil.pdf_sayfasi("kontur-dersi", "su-2010", 10)
        finally:
            mb.KOK = eski

    def test_kaymis_ve_baska_baski(self):
        import shutil
        import makale_bulucu as mb
        import makale_sekil
        eski = mb.KOK
        t = self.tmp.name
        try:
            mb.KOK = t
            ders = {1: "kapak", **{n: self._metin(n) for n in range(2, 11)}}
            self._ders_kur(t, mb, ders)
            k = mb.kaynaklar("kontur-dersi")[0]
            # Kapaksız kopya: her sayfa bir önde. Kayma ölçülür ve sayfa açarken uygulanır.
            self._kitaplik_kur(mb, {n - 1: ders[n] for n in range(2, 11)})
            d = mb.kaynak_hazirla("kontur-dersi", k, ag_kullan=False)
            self.assertEqual((d["durum"], d["sayfa_kaymasi"]), ("hazir", -1))
            s = mb.durum_oku("kontur-dersi")
            s["kaynaklar"] = {"su-2010": d}
            mb.durum_yaz("kontur-dersi", s)
            self.assertEqual(makale_sekil.pdf_sayfasi("kontur-dersi", "su-2010", 4), 3)
            # Sayfaları karışık (başka dizgi): bağlanmaz, nedeni söylenir.
            shutil.rmtree(mb.metin_klasoru(mb.KENDI, "ogrenci-su"))
            self._kitaplik_kur(mb, {1: ders[5], 2: ders[2], 3: ders[9], 4: ders[3]})
            d = mb.kaynak_hazirla("kontur-dersi", k, ag_kullan=False)
            self.assertEqual(d["durum"], "eksik")
            self.assertIn("başka bir baskısı", d["neden"])
            # İçeriği tutmayan PDF, dosya adı uysa da sayfa metni olan derse bağlanmaz.
            shutil.rmtree(mb.metin_klasoru(mb.KENDI, "ogrenci-su"))
            self._kitaplik_kur(mb, {1: self._metin(77), 2: self._metin(78)})
            d = mb.kaynak_hazirla("kontur-dersi", k, ag_kullan=False)
            self.assertEqual(d["durum"], "eksik")
            self.assertIn("Kendi makalelerim", d["denenen"])
        finally:
            mb.KOK = eski

    def test_pmid_ile_doi(self):
        import makale_bulucu as mb

        class Ag:
            def json(self, url):
                assert "20664835" in url
                return {"records": [{"pmid": 20664835, "doi": "10.1000/ABC.1"}]}
        self.assertEqual(mb.pmid_ile_doi("PMID: 20664835", Ag()), "10.1000/abc.1")

        class Bos:
            def json(self, url):
                return {"records": [{"pmid": 20664835, "status": "error"}]}
        self.assertIsNone(mb.pmid_ile_doi("20664835", Bos()))
