"""Sürüm damgası ve 27 Kasım 2026 eğitmen metni değişiklikleri.
Çalıştırma:  python -m unittest discover -s tools/testler -v   (internete çıkmaz)
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
os.environ.setdefault("KLINIK_KOC_ANLAM_KURMA", "1")

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(KOK, "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ornek_ders  # noqa: E402

DERS = ornek_ders.DERS


def setUpModule():
    ornek_ders.kur()


def tearDownModule():
    ornek_ders.kaldir()


def oku(*yol):
    with open(os.path.join(KOK, *yol), encoding="utf-8") as f:
        return f.read()


class SurumDamgasi(unittest.TestCase):
    def setUp(self):
        import kayit_aktar
        self.ka = kayit_aktar
        self.gecici = tempfile.TemporaryDirectory()
        spec = importlib.util.spec_from_file_location("tahta_mcp_damga", os.path.join(KOK, "tools", "tahta-mcp.py"))
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.m.KAYIT_KOK = os.path.join(self.gecici.name, "kayitlar")
        self.m.ESKI_KAYIT_KOK = os.path.join(self.gecici.name, "eski")
        self.m._DEPO = None
        self.eski_ortam = os.environ.pop("KLINIK_KOC_KAYIT", None)

    def tearDown(self):
        if self.eski_ortam is not None:
            os.environ["KLINIK_KOC_KAYIT"] = self.eski_ortam
        self.gecici.cleanup()

    def arac(self, ad, **a):
        r = self.m.ISLEYICILER[ad](a)
        t = r["content"][0]["text"]
        if r.get("isError"):
            raise AssertionError(t)
        return json.loads(t)

    def test_iz_metne_bagli_satir_sonuna_degil(self):
        """Metin değişince iz değişir; Windows satır sonu ya da satır sonu boşluğu izi değiştirmez."""
        asil = self.m.KOK
        kopya = os.path.join(self.gecici.name, "program")
        os.makedirs(os.path.join(kopya, "egitmenler"))
        for ad in ("ortak.md", "inci.md", "mercan.md"):
            shutil.copy(os.path.join(asil, "egitmenler", ad), os.path.join(kopya, "egitmenler", ad))
        try:
            inci, mercan = self.m.kural_izi("inci"), self.m.kural_izi("mercan")
            self.assertRegex(inci, r"^[0-9a-f]{10}$")
            self.assertNotEqual(inci, mercan)
            self.m.KOK = kopya
            self.assertEqual(self.m.kural_izi("inci"), inci)
            yol = os.path.join(kopya, "egitmenler", "inci.md")
            m = oku("egitmenler", "inci.md")
            with open(yol, "w", encoding="utf-8", newline="") as f:
                f.write(m.replace("\n", "  \r\n"))
            self.assertEqual(self.m.kural_izi("inci"), inci)
            with open(yol, "w", encoding="utf-8") as f:
                f.write(m + "\n- Yeni kural.\n")
            self.assertNotEqual(self.m.kural_izi("inci"), inci)
            # ortak çekirdek değişirse iki eğitmenin izi de değişir
            with open(os.path.join(kopya, "egitmenler", "ortak.md"), "a", encoding="utf-8") as f:
                f.write("\n- Ek.\n")
            self.assertNotEqual(self.m.kural_izi("mercan"), mercan)
        finally:
            self.m.KOK = asil

    def test_kayda_ve_oturuma_yazilir(self):
        kim = self.arac("egitmen_hazirla", ders=DERS, ogrenci="Ada Gün", ayirt="271")["ogrenci"]["kimlik"]
        self.arac("kayit_yaz", ogrenci=kim, ders=DERS, mola="m1")
        self.arac("kayit_yaz", ogrenci=kim, ders=DERS, oturum={"egitmen": "Mercan", "ozet": "ilk", "sure_dk": 20})
        k = self.arac("kayit_oku", ogrenci=kim, ders=DERS, ayrinti=True)["kayit"]
        beklenen = {"program": self.m.SURUM, "egitmen": "mercan", "kural_izi": self.m.kural_izi("mercan")}
        self.assertEqual(len(k["surumler"]), 1, "aynı damga yinelenmemeli")
        self.assertEqual({x: k["surumler"][0][x] for x in beklenen}, beklenen)
        self.assertTrue(k["surumler"][0]["tarih"])
        self.assertEqual(k["oturumlar"][-1]["surum"], beklenen)
        self.assertEqual(k["oturumlar"][-1]["egitmen"], "Mercan", "eğitmenin yazdığı alan ezilmemeli")

    def test_degisince_yeni_satir(self):
        kim = self.arac("egitmen_hazirla", ders=DERS, ogrenci="Ada Gün", ayirt="271")["ogrenci"]["kimlik"]
        self.arac("kayit_yaz", ogrenci=kim, ders=DERS, mola="m1")
        self.m.SURUM = "9.9.9"
        self.arac("kayit_yaz", ogrenci=kim, ders=DERS, mola="m2")
        self.arac("kayit_yaz", ogrenci=kim, ders=DERS, mola="m3")
        k = self.arac("kayit_oku", ogrenci=kim, ders=DERS, ayrinti=True)["kayit"]
        self.assertEqual([x["program"] for x in k["surumler"]][-1], "9.9.9")
        self.assertEqual(len(k["surumler"]), 2)

    def test_secilen_egitmen_damgaya_girer(self):
        """İki eğitmene açık derste damga, dersin varsayılanını değil seçilen eğitmeni yazar."""
        ders = "kendi-makalelerim"
        r = self.arac("egitmen_hazirla", ders=ders, ogrenci="Ada Gün", ayirt="271", egitmen="inci")
        self.assertIn("İnci", r["egitmen"])
        self.arac("kayit_yaz", ogrenci=r["ogrenci"]["kimlik"], ders=ders, mola="m")
        k = self.arac("kayit_oku", ogrenci=r["ogrenci"]["kimlik"], ders=ders, ayrinti=True)["kayit"]
        self.assertEqual(k["surumler"][-1]["egitmen"], "inci")

    def test_raporda_ve_anonim_aktarimda(self):
        kim = self.arac("egitmen_hazirla", ders=DERS, ogrenci="Ada Gün", ayirt="271")["ogrenci"]["kimlik"]
        self.arac("kayit_yaz", ogrenci=kim, ders=DERS, guven=[{"hedef": "H1.a", "soru": "s", "guven": "emin", "dogru": False}])
        r = self.arac("rapor_yaz", ogrenci=kim, ders=DERS, ogretmen_ozeti="Özet.")
        rapor = open(r["dosya"], encoding="utf-8").read() if r.get("dosya") else json.dumps(r, ensure_ascii=False)
        self.assertIn("Program sürümü: %s · Eğitmen metni: %s" % (self.m.SURUM, self.m.kural_izi("mercan")), rapor)
        self.assertIn("Güven ve doğruluk (olgu ve yanılgı soruları)", rapor)
        self.assertNotIn("olgu sorusu;", rapor)
        a = self.ka.anonim(self.m.depo())
        s = a["kayitlar"][0]["dersler"][0]["surumler"]
        self.assertEqual(s, [{"program": self.m.SURUM, "egitmen": "mercan", "kural_izi": self.m.kural_izi("mercan"), "gun": 0}])
        self.assertNotIn("tarih", json.dumps(s))

    def test_zorlanilan_konu_sonraki_oturuma_tasinir(self):
        kim = self.arac("egitmen_hazirla", ders=DERS, ogrenci="Ada Gün", ayirt="271")["ogrenci"]["kimlik"]
        self.assertIsNone(self.arac("kayit_oku", ogrenci=kim, ders=DERS)["son_zorlandigi"])
        r = self.arac("kayit_yaz", ogrenci=kim, ders=DERS, oturum={"ozet": "o", "zorlandigi": "Rezektif ile rejeneratif ayrımı"})
        self.assertEqual(r["ozet"]["son_zorlandigi"]["metin"], "Rezektif ile rejeneratif ayrımı")
        r = self.arac("egitmen_hazirla", ders=DERS, ogrenci_kimligi=kim)
        self.assertEqual(r["ogrenci"]["kayit"]["son_zorlandigi"]["metin"], "Rezektif ile rejeneratif ayrımı")
        # serbest metin anonim aktarıma girmez
        self.assertNotIn("Rezektif", json.dumps(self.ka.anonim(self.m.depo()), ensure_ascii=False))


class EgitmenMetinleri27Kasim(unittest.TestCase):
    """Kemal'in 27 Kasım 2026'da tek tek onayladığı metinler yerinde mi (yanlışlıkla silinmesin)."""

    def test_ortak(self):
        m = oku("egitmenler", "ortak.md")
        self.assertIn("Senin çalışmak istediğin bir konu var mı, yoksa ben mi seçeyim?", m)
        self.assertIn("Yaklaşık 20. dakikada, doğal bir durakta, bir kez mola ya da bitiş öner.", m)
        self.assertIn("kendisi mola isteyene kadar yeniden önerme", m)
        self.assertIn("Öneriyi cevapla aynı cümlede verme", m)
        self.assertNotIn("20–30 dakikada", m)
        self.assertIn("## 6. Güven sorusu (olgu sorularında ve yanılgı sorularında)", m)
        self.assertIn("Aynı yanılgı için bir oturumda en çok bir kez sor.", m)
        self.assertIn("Bugün anlamakta en çok zorlandığın neydi?", m)
        # oturum akışı numaraları sıralı kalmalı
        akis = m.split("## 2. Oturum akışı")[1].split("## 3.")[0]
        self.assertEqual([s.split(".")[0] for s in akis.strip().splitlines()], [str(i) for i in range(1, 9)])

    def test_inci_ve_mercan(self):
        inci, mercan = oku("egitmenler", "inci.md"), oku("egitmenler", "mercan.md")
        self.assertIn("**Tedavi kararı (kural ve istisna):**", inci)
        self.assertIn("amaç → ilk basamak → kural ve istisnalar → yeniden bakı", inci)
        self.assertIn("## Konu ve klinik protokol araç seti (ikinci araç seti)", mercan)
        self.assertIn("## Makale inceleme araç seti (ilk araç seti)", mercan)
        self.assertIn("Laboratuvar bulgusunu klinik sonuç gibi sunma.", mercan)

    def test_degisiklik_gunlugu(self):
        g = oku("egitmenler", "DEGISIKLIKLER.md")
        self.assertIn("2026-11-27", g)
        for ad in ("ortak.md", "inci.md", "mercan.md"):
            self.assertIn(ad, g)


if __name__ == "__main__":
    unittest.main()
