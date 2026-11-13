"""Makale bulucu ve ders paketi testleri. Çalıştırma:  python -m unittest discover -s tools/testler -v

İnternete çıkmaz: indirici (Ag) sahte bir nesneyle değiştirilir. PDF okuyucu (pypdf) yoksa PDF'e dayanan
testler atlanır.
"""
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(KOK, "tools"))

import bilgi_bankasi  # noqa: E402
import ders_paketi  # noqa: E402
import makale_bulucu as mb  # noqa: E402

PYPDF = importlib.util.find_spec("pypdf") is not None


def basit_pdf(sayfalar):
    """Her sayfasında verilen metin olan küçük, geçerli bir PDF üretir (yalnız ASCII metin)."""
    nesneler = []
    sayfa_noları = []
    n_font = 3
    nesneler.append(None)  # 1: katalog
    nesneler.append(None)  # 2: sayfalar
    nesneler.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for metin in sayfalar:
        satirlar = []
        y = 760
        for satir in metin.split("\n"):
            guvenli = satir.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            satirlar.append("BT /F1 10 Tf 40 %d Td (%s) Tj ET" % (y, guvenli))
            y -= 14
        akis = "\n".join(satirlar).encode("latin-1")
        nesneler.append(b"<< /Length %d >>\nstream\n" % len(akis) + akis + b"\nendstream")
        icerik_no = len(nesneler)
        nesneler.append(("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents %d 0 R "
                         "/Resources << /Font << /F1 %d 0 R >> >> >>" % (icerik_no, n_font)).encode())
        sayfa_noları.append(len(nesneler))
    nesneler[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    nesneler[1] = ("<< /Type /Pages /Kids [%s] /Count %d >>" % (
        " ".join("%d 0 R" % n for n in sayfa_noları), len(sayfa_noları))).encode()
    cikti = io.BytesIO()
    cikti.write(b"%PDF-1.4\n")
    yerler = []
    for i, n in enumerate(nesneler, 1):
        yerler.append(cikti.tell())
        cikti.write(b"%d 0 obj\n" % i + n + b"\nendobj\n")
    xref = cikti.tell()
    cikti.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(nesneler) + 1))
    for y in yerler:
        cikti.write(b"%010d 00000 n \n" % y)
    cikti.write(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(nesneler) + 1, xref))
    return cikti.getvalue()


def makale_pdf(doi, konu):
    govde = ("Peri-implantitis surgical therapy %s. " % konu) * 6
    return basit_pdf(["Journal of Testing doi:%s\n%s\n%s" % (doi, govde[:110], govde[110:220]),
                      "Results %s\n%s" % (konu, govde[:200]),
                      "REFERENCES\n1. Someone A. Something. 2020."])


class SahteAg:
    """Adres → (gövde, son adres, tür). Bilinmeyen adres 404 gibi hata verir."""

    def __init__(self, yanitlar):
        self.yanitlar = yanitlar
        self.istenen = []
        self.ulasildi = True

    def al(self, url, kabul="*/*", en_cok=None):
        self.istenen.append(url)
        if url not in self.yanitlar:
            raise OSError("404 " + url)
        govde, son, tur = self.yanitlar[url]
        return govde, son or url, tur

    def json(self, url):
        govde, _, _ = self.al(url)
        return json.loads(govde)


class OrtamliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.kok = os.path.join(t, "program")
        os.makedirs(os.path.join(self.kok, "lessons"))
        self.eski = {"mb": mb.KOK, "bb": bilgi_bankasi.KOK, "dp": ders_paketi.KOK}
        mb.KOK = bilgi_bankasi.KOK = ders_paketi.KOK = self.kok
        self.ortam = {k: os.environ.get(k) for k in ("KLINIK_KOC_VERI", "KLINIK_KOC_MAKALE", "KLINIK_KOC_EPOSTA")}
        os.environ["KLINIK_KOC_VERI"] = os.path.join(t, "veri")
        os.environ["KLINIK_KOC_MAKALE"] = os.path.join(t, "Belgeler", "KlinikKoç Makaleler")
        os.environ.pop("KLINIK_KOC_EPOSTA", None)

    def tearDown(self):
        mb.KOK, bilgi_bankasi.KOK, ders_paketi.KOK = self.eski["mb"], self.eski["bb"], self.eski["dp"]
        for k, v in self.ortam.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def ders_kur(self, ders, kaynaklar, baslik="Deneme dersi"):
        k = os.path.join(self.kok, "lessons", ders)
        os.makedirs(os.path.join(k, "kaynaklar"))
        with open(os.path.join(k, "egitmen.json"), "w", encoding="utf-8") as f:
            json.dump({"baslik": baslik, "egitmen": "inci", "hedefler": []}, f)
        with open(os.path.join(k, "kaynaklar", "kaynaklar.json"), "w", encoding="utf-8") as f:
            json.dump({"kaynaklar": kaynaklar}, f)
        return k


class TemelTest(unittest.TestCase):
    def test_doi_temizle(self):
        self.assertEqual(mb.doi_temizle("https://doi.org/10.1111/PRD.70052"), "10.1111/prd.70052")
        self.assertEqual(mb.doi_temizle("doi: 10.1902/jop.2018.170157."), "10.1902/jop.2018.170157")
        self.assertEqual(mb.doi_temizle("http://dx.doi.org/10.1/x)"), "10.1/x")
        self.assertEqual(mb.doi_temizle(None), "")

    def test_guvenli_ad(self):
        self.assertEqual(mb.guvenli_ad('Akut lezyonlar: "NUG"/NUP?'), "Akut lezyonlar_ _NUG__NUP_")
        self.assertEqual(mb.guvenli_ad("..."), "adsiz")

    def test_dosya_adi(self):
        self.assertEqual(mb.dosya_adi({"id": "a", "doi": "10.1111/prd.70052"}), "10.1111_prd.70052.pdf")
        self.assertEqual(mb.dosya_adi({"id": "kitap-1"}), "kitap-1.pdf")

    def test_gecersiz_kimlik(self):
        for kotu in ("../x", "a/b", "", ".gizli"):
            with self.assertRaises(ValueError):
                mb.ders_gecerli(kotu)

    def test_pdf_adresi_bul(self):
        html = ('<html><head><meta name="citation_title" content="X">'
                '<meta content="/doi/pdf/10.1/x?a=1&amp;b=2" name="citation_pdf_url"></head></html>')
        self.assertEqual(mb.pdf_adresi_bul(html, "https://yayinci.org/doi/10.1/x"),
                         "https://yayinci.org/doi/pdf/10.1/x?a=1&b=2")
        self.assertIsNone(mb.pdf_adresi_bul("<html></html>", "https://a"))

    def test_acik_erisim_adresleri(self):
        ag = SahteAg({
            "https://api.openalex.org/works/doi:10.1/x": (json.dumps({
                "best_oa_location": {"pdf_url": "https://oa.org/x.pdf"},
                "oa_locations": [{"pdf_url": "https://oa.org/x.pdf"}, {"pdf_url": None}]}).encode(), None, "json"),
        })
        self.assertEqual(mb.acik_erisim_adresleri("10.1/x", ag), [("https://oa.org/x.pdf", "OpenAlex")])


@unittest.skipUnless(PYPDF, "pypdf kurulu değil")
class BulucuTest(OrtamliTest):
    def test_acik_erisim_yayinci_eksik_ve_aramaya_ekleme(self):
        ders = "deneme"
        self.ders_kur(ders, [
            {"id": "acik", "doi": "10.1/acik", "kisa": "Açık 2024", "rol": "ana"},
            {"id": "abone", "doi": "10.1/abone", "kisa": "Abone 2023"},
            {"id": "yok", "doi": "10.1/yok", "kisa": "Yok 2022"},
        ])
        oa = "https://api.openalex.org/works/doi:"
        ag = SahteAg({
            oa + "10.1/acik": (json.dumps({"best_oa_location": {"pdf_url": "https://oa.org/a.pdf"}}).encode(), None, "j"),
            "https://oa.org/a.pdf": (makale_pdf("10.1/acik", "bone loss"), None, "application/pdf"),
            "https://doi.org/10.1/abone": (b'<meta name="citation_pdf_url" content="https://pub.org/b.pdf">',
                                           "https://pub.org/abone", "text/html"),
            "https://pub.org/b.pdf": (makale_pdf("10.1/abone", "membrane"), None, "application/pdf"),
            "https://doi.org/10.1/yok": (b"<html>Giris yapin</html>", "https://pub.org/yok", "text/html"),
        })
        sonuc = {k["id"]: mb.kaynak_hazirla(ders, k, ag) for k in mb.kaynaklar(ders)}
        self.assertEqual(sonuc["acik"]["durum"], "hazir")
        self.assertEqual(sonuc["acik"]["nereden"], "acik-erisim")
        self.assertEqual(sonuc["abone"]["nereden"], "universite")
        self.assertEqual(sonuc["yok"]["durum"], "eksik")
        self.assertEqual(sonuc["yok"]["sayfa_adresi"], "https://pub.org/yok")
        # PDF öğrencinin gördüğü klasörde, ders başlığıyla
        self.assertTrue(os.path.isfile(os.path.join(os.environ["KLINIK_KOC_MAKALE"], "Deneme dersi", "10.1_acik.pdf")))
        # Kaynakça sayfası metne alınmaz
        metinler = os.listdir(mb.metin_klasoru(ders, "acik"))
        self.assertIn("sayfa-01.txt", metinler)
        self.assertNotIn("sayfa-03.txt", metinler)
        # Bilgi bankası makale sayfalarını bulur
        parcalar = [p for p in bilgi_bankasi.ders_parcalari(ders) if p["tur"] == "kaynak"]
        self.assertTrue(any(p["kaynak"].startswith("Açık 2024, s. ") for p in parcalar))
        dizin = os.path.join(self.tmp.name, "bilgi.sqlite")
        bilgi_bankasi.dizinle([ders], yol=dizin, sessiz=True)
        bulunan = bilgi_bankasi.ara("membrane", ders=ders, yol=dizin)
        self.assertTrue(bulunan and bulunan[0]["kaynak"].startswith("Abone 2023"))

    def test_klasordeki_pdf_yeniden_indirilmez(self):
        ders = "deneme"
        self.ders_kur(ders, [{"id": "a", "doi": "10.1/a", "kisa": "A"}])
        # Başka bir dersin klasöründe (ör. arşivlenen dersten kalan) aynı makale var
        baska = os.path.join(os.environ["KLINIK_KOC_MAKALE"], "Eski ders")
        os.makedirs(baska)
        with open(os.path.join(baska, "10.1_a.pdf"), "wb") as f:
            f.write(makale_pdf("10.1/a", "flap"))
        ag = SahteAg({})
        d = mb.kaynak_hazirla(ders, mb.kaynaklar(ders)[0], ag)
        self.assertEqual((d["durum"], d["nereden"]), ("hazir", "klasor"))
        self.assertEqual(ag.istenen, [])

    def test_hazirla_durum_ve_ozet(self):
        ders = "deneme"
        self.ders_kur(ders, [{"id": "a", "doi": "10.1/a", "kisa": "A"}, {"id": "b", "kisa": "Kitap bölümü"}])
        o = mb.hazirla(ders, ag_kullan=False, dizinle=False)
        self.assertEqual(o["sayilar"], {"eksik": 2})
        self.assertEqual(o["makaleler"][1]["neden"], "DOI yok; PDF'i elle ekleyin.")
        self.assertFalse(o["calisiyor"])
        self.assertEqual(o["makaleler"][0]["sayfa_adresi"], "https://doi.org/10.1/a")

    def test_elle_ekle_doi_ile_eslesir(self):
        ders = "deneme"
        self.ders_kur(ders, [{"id": "a", "doi": "10.1111/aaa.1", "kisa": "A"},
                                {"id": "b", "doi": "10.1111/bbb.2", "kisa": "B"}])
        d = mb.elle_ekle(ders, makale_pdf("10.1111/BBB.2", "suture"), "indirdigim.pdf", dizinle=False)
        self.assertEqual((d["id"], d["durum"], d["nereden"]), ("b", "hazir", "elle"))
        o = mb.ozet(ders)
        self.assertEqual(o["sayilar"], {"denenmedi": 1, "hazir": 1})

    def test_elle_ekle_listede_yoksa_ogrenci_kaynagi(self):
        ders = "deneme"
        self.ders_kur(ders, [{"id": "a", "doi": "10.1/aaa", "kisa": "A"}])
        d = mb.elle_ekle(ders, makale_pdf("10.9/baska", "graft"), "Benim Makalem.pdf", dizinle=False)
        self.assertTrue(d["ogrenci"])
        self.assertEqual(d["id"], "ogrenci-benim-makalem")
        with open(os.path.join(mb.metin_klasoru(ders, d["id"]), "bilgi.json"), encoding="utf-8") as f:
            bilgi = json.load(f)
        self.assertTrue(bilgi["ogrenci"])
        self.assertEqual(len(mb.ozet(ders)["makaleler"]), 2)
        mb.eki_kaldir.__globals__["aramaya_ekle"] = lambda ders: None
        try:
            mb.eki_kaldir(ders, d["id"])
        finally:
            mb.eki_kaldir.__globals__["aramaya_ekle"] = mb.aramaya_ekle
        self.assertEqual(len(mb.ozet(ders)["makaleler"]), 1)
        self.assertFalse(os.path.exists(mb.metin_klasoru(ders, d["id"])))

    def test_pdf_olmayan_reddedilir(self):
        self.ders_kur("deneme", [])
        with self.assertRaises(ValueError):
            mb.elle_ekle("deneme", b"<html>giris</html>", "x.pdf", dizinle=False)

    def test_dersin_kendi_metni_tekrar_indirilmez(self):
        k = self.ders_kur("deneme", [{"id": "ana", "doi": "10.1/ana", "kisa": "Ana"}])
        with open(os.path.join(k, "egitmen.json"), "w", encoding="utf-8") as f:
            json.dump({"baslik": "D", "kaynak": {"doi": "https://doi.org/10.1/ANA"}}, f)
        os.makedirs(os.path.join(k, "kaynak"))
        with open(os.path.join(k, "kaynak", "sayfa-01.txt"), "w", encoding="utf-8") as f:
            f.write("metin")
        d = mb.kaynak_hazirla("deneme", mb.kaynaklar("deneme")[0], SahteAg({}))
        self.assertEqual((d["durum"], d["nereden"]), ("hazir", "ders"))


class AgYokTest(OrtamliTest):
    def test_internet_yoksa_bunu_soyler(self):
        self.ders_kur("deneme", [{"id": "a", "doi": "10.1111/a.1", "kisa": "A"}])
        ag = SahteAg({})
        ag.ulasildi = False
        d = mb.kaynak_hazirla("deneme", mb.kaynaklar("deneme")[0], ag)
        self.assertEqual(d["durum"], "eksik")
        self.assertIn("İnternete ulaşılamadı", d["neden"])


class PaketTest(OrtamliTest):
    def zip_yap(self, dosyalar):
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w") as z:
            for ad, icerik in dosyalar.items():
                z.writestr(ad, icerik)
        yol = os.path.join(self.tmp.name, "paket.zip")
        with open(yol, "wb") as f:
            f.write(b.getvalue())
        return yol

    def test_paket_kurulur_ve_katalog_guncellenir(self):
        yol = self.zip_yap({
            "akut-lezyonlar/egitmen.json": json.dumps({"baslik": "Akut lezyonlar", "duzey": "Lisans"}),
            "akut-lezyonlar/kaynaklar/kaynaklar.json": json.dumps({"kaynaklar": [{"id": "a", "doi": "10.1/a"}]}),
            "akut-lezyonlar/makale-metin/a/sayfa-01.txt": "paketle gelmemeli",
            "__MACOSX/akut-lezyonlar/._egitmen.json": "x",
        })
        r = ders_paketi.yukle(yol)
        self.assertEqual((r["ders"], r["makale"]), ("akut-lezyonlar", 1))
        self.assertFalse(os.path.exists(os.path.join(self.kok, "lessons", "akut-lezyonlar", "makale-metin")))
        with open(os.path.join(self.kok, "lessons", "katalog.json"), encoding="utf-8") as f:
            kat = json.load(f)
        self.assertEqual(kat["lessons"][0]["title"], "Akut lezyonlar")
        with self.assertRaises(FileExistsError):
            ders_paketi.yukle(yol)
        # Güncellemede öğrencinin bilgisayarında üretilen makale metinleri korunur
        mm = os.path.join(self.kok, "lessons", "akut-lezyonlar", "makale-metin", "a")
        os.makedirs(mm)
        ders_paketi.yukle(yol, uzerine=True)
        self.assertTrue(os.path.isdir(mm))

    def test_guvensiz_paketler_reddedilir(self):
        kotuler = [
            {"../kotu/egitmen.json": "{}"},
            {"a/egitmen.json": "{}", "b/egitmen.json": "{}"},
            {"egitmen.json": "{}"},
            {"a/notlar.txt": "ders dosyası yok"},
        ]
        for dosyalar in kotuler:
            with self.subTest(dosyalar=list(dosyalar)):
                with self.assertRaises(ValueError):
                    ders_paketi.yukle(self.zip_yap(dosyalar))
        self.assertEqual(os.listdir(os.path.join(self.kok, "lessons")), [])


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(PYPDF, "pypdf yok")
class SonradanEklenenMakaleTest(OrtamliTest):
    """4.0.2: ders bir kez dizinlendikten sonra eklenen PDF de aramaya girmeli (Kemal'in Mac testi, Sanz 2020)."""

    def test_sonradan_eklenen_pdf_aranir(self):
        yol = os.path.join(self.tmp.name, "dizin.sqlite")
        mb.kendi_kitaplik_hazirla()
        bilgi_bankasi.dizinle([mb.KENDI], sessiz=True, yol=yol)  # kitaplık boşken dizinlendi
        d = mb.elle_ekle(mb.KENDI, makale_pdf("10.5/stage", "staging grading"), "Sanz 2020.pdf", dizinle=False)
        self.assertEqual(d["durum"], "hazir")
        rapor = bilgi_bankasi.dizinle([mb.KENDI], sessiz=True, yol=yol)
        self.assertEqual(rapor[0]["durum"], "dizinlendi")
        sonuc = bilgi_bankasi.ara("staging", mb.KENDI, yol=yol)
        self.assertTrue(sonuc, "makale metni aramada yok")
        self.assertIn(d["kisa"], sonuc[0]["kaynak"])
        self.assertEqual(bilgi_bankasi.makale_parca_sayilari(mb.KENDI, yol=yol).get(d["kisa"], 0) > 0, True)

    def test_anlamsiz_dizinleme_vektorleri_silmez(self):
        yol = os.path.join(self.tmp.name, "dizin.sqlite")
        self.ders_kur("deneme", [])
        bilgi_bankasi.dizinle(["deneme"], sessiz=True, yol=yol)
        db = bilgi_bankasi.baglan(yol)
        taban = bilgi_bankasi.ders_imzasi("deneme")
        db.execute("INSERT OR REPLACE INTO bilgi VALUES (?,?)", ("imza:deneme", taban + "+anlam"))
        db.commit()
        db.close()
        rapor = bilgi_bankasi.dizinle(["deneme"], sessiz=True, yol=yol)  # model yok: anlamlı dizin güncel sayılır
        self.assertEqual(rapor[0]["durum"], "güncel")
