"""Ders hazırlama sihirbazı testleri. Çalıştırma:  python -m unittest discover -s tools/testler -v

İnternete çıkmaz: künye sorguları sahte bir ağ nesnesiyle yanıtlanır. Word belgesi test içinde üretilir.
"""
import copy
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(KOK, "tools"))

import ders_paketi  # noqa: E402
import makale_bulucu as mb  # noqa: E402
import sihirbaz as sh  # noqa: E402
import vaka_denetle  # noqa: E402

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def docx_yap(paragraflar):
    """[(biçem ya da None, metin)] → en küçük geçerli .docx baytları. 'TABLO' biçemi iki hücreli satır yazar."""
    govde = []
    for bicem, metin in paragraflar:
        if bicem == "TABLO":
            a, b = metin
            govde.append('<w:tbl><w:tr><w:tc><w:p><w:r><w:t>%s</w:t></w:r></w:p></w:tc>'
                         '<w:tc><w:p><w:r><w:t>%s</w:t></w:r></w:p></w:tc></w:tr></w:tbl>' % (a, b))
            continue
        ppr = '<w:pPr><w:pStyle w:val="%s"/></w:pPr>' % bicem if bicem else ""
        govde.append("<w:p>%s<w:r><w:t>%s</w:t></w:r></w:p>" % (ppr, metin))
    belge = ('<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="%s"><w:body>%s</w:body></w:document>'
             % (W_NS, "".join(govde)))
    stiller = ('<?xml version="1.0" encoding="UTF-8"?><w:styles xmlns:w="%s">'
               '<w:style w:styleId="Balk1"><w:name w:val="heading 1"/></w:style>'
               '<w:style w:styleId="Balk2"><w:name w:val="heading 2"/></w:style></w:styles>' % W_NS)
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
        z.writestr("word/document.xml", belge)
        z.writestr("word/styles.xml", stiller)
    return b.getvalue()


UZUN = "Plak birikimi ve konak yanıtı birlikte değerlendirilir; klinik tablo hastadan hastaya değişir. "
NOT_DOCX = [
    (None, "Bu notun giriş paragrafı. " + UZUN),
    ("Balk1", "Nekrotizan gingivitisi ayırt et"),
    (None, "Papil nekrozu, ağrı ve kanama üçlüsü tanı koydurur. " + UZUN),
    ("Balk2", "Herpetik gingivostomatitle karşılaştır"),
    (None, "Ateş ve veziküller herpetik tabloyu düşündürür. " + UZUN),
    ("TABLO", ("Bulgu", "Anlamı")),
    ("Balk1", "Tedaviyi açıkla"),
    (None, "Mekanik temizlik ve ağız gargarası ilk basamaktır. " + UZUN),
]


def kunye_yaniti(doi, soyad, yil, lisans=None):
    m = {"title": ["A <i>test</i> article about gingivitis"], "container-title": ["J Clin Periodontol"],
         "author": [{"family": soyad, "given": "Ayşe B."}, {"family": "Ikinci", "given": "C"}],
         "issued": {"date-parts": [[yil, 5]]}, "volume": "45", "issue": "S20", "page": "1-10",
         "abstract": "<jats:p>Abstract Background text.</jats:p>"}
    if lisans:
        m["license"] = [{"URL": lisans}]
    return json.dumps({"message": m}).encode()


class SahteAg:
    def __init__(self, yanitlar, ulasildi=True):
        self.yanitlar = yanitlar
        self.istenen = []
        self.ulasildi = ulasildi

    def json(self, url):
        self.istenen.append(url)
        if url not in self.yanitlar:
            raise OSError("404 " + url)
        return json.loads(self.yanitlar[url])


class SihirbazTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.kok = os.path.join(t, "program")
        os.makedirs(os.path.join(self.kok, "lessons"))
        self.eski = (ders_paketi.KOK, vaka_denetle.KOK)
        ders_paketi.KOK = vaka_denetle.KOK = self.kok
        self.ortam = {k: os.environ.get(k) for k in ("KLINIK_KOC_VERI", "KLINIK_KOC_MAKALE")}
        os.environ["KLINIK_KOC_VERI"] = os.path.join(t, "veri")
        os.environ["KLINIK_KOC_MAKALE"] = os.path.join(t, "Makaleler")
        self.cikis = os.path.join(t, "paketler")

    def tearDown(self):
        ders_paketi.KOK, vaka_denetle.KOK = self.eski
        for k, v in self.ortam.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    # --- Küçük yardımcılar ---
    def test_kimlik_ve_ders_gecerli(self):
        self.assertEqual(sh.kimlik_yap("Akut Periodontal Lezyonlar"), "akut-periodontal-lezyonlar")
        self.assertEqual(sh.kimlik_yap("Çiğdem Öğüt", "not-"), "not-cigdem-ogut")
        for kotu in ("ozel-x", "tanitim", "A-b", "x", "../x"):
            with self.assertRaises(ValueError):
                sh.ders_gecerli(kotu)

    def test_dois_ayikla(self):
        metin = ("1. Papapanou PN. Periodontitis. J Clin Periodontol. 2018. doi:10.1111/jcpe.12946.\n"
                 "https://doi.org/10.1111/JCPE.12941 ve yine 10.1111/jcpe.12946")
        self.assertEqual(sh.dois_ayikla(metin), ["10.1111/jcpe.12946", "10.1111/jcpe.12941"])

    def test_kisa_ad(self):
        self.assertEqual(sh.kisa_ad(["Herrera"], 2018), "Herrera 2018")
        self.assertEqual(sh.kisa_ad(["Herrera", "Retamal"], 2018), "Herrera ve Retamal 2018")
        self.assertEqual(sh.kisa_ad(["Herrera", "A", "B"], 2018), "Herrera ve ark. 2018")

    def test_crossref_cevir(self):
        k = sh.crossref_cevir(json.loads(kunye_yaniti("10.1111/jcpe.12946", "Herrera", 2018,
                                                      "https://creativecommons.org/licenses/by/4.0/"))["message"],
                              "10.1111/jcpe.12946")
        self.assertEqual(k["baslik"], "A test article about gingivitis")
        self.assertEqual(k["yil"], 2018)
        self.assertEqual(k["lisans"], "CC BY")
        self.assertIn("Herrera AB, Ikinci C.", k["atif"])
        self.assertIn("2018;45(S20):1–10.", k["atif"])
        self.assertTrue(k["ozet"].startswith("Background"))

    def test_bloom_oner(self):
        self.assertEqual(sh.bloom_oner("Nekrotizan gingivitisi herpetikten ayırt eder"), "cozumle")
        self.assertEqual(sh.bloom_oner("Tedaviyi açıkla"), "anla")
        self.assertEqual(sh.bloom_oner("Belirtileri listele"), "hatirla")
        self.assertEqual(sh.bloom_oner("Ne bileyim"), "anla")

    def test_metin_bolumleri(self):
        b = sh.metin_bolumleri("# Giriş başlığı\nbir iki\n\nTANI ÖLÇÜTLERİ\nüç dört\n## Alt\nbeş")
        self.assertEqual([x["baslik"] for x in b], ["Giriş başlığı", "Tanı Ölçütleri", "Alt"])
        self.assertEqual(b[2]["duzey"], 2)

    # --- Taslak akışı ---
    def taslak(self):
        sh.yeni("akut-lezyon", "Akut periodontal lezyonlar")
        return "akut-lezyon"

    def test_yeni_liste_kart(self):
        d = self.taslak()
        with self.assertRaises(FileExistsError):
            sh.yeni(d)
        self.assertEqual([x["ders"] for x in sh.liste()], [d])
        t = sh.kart_guncelle(d, {"sure_dk": "25", "duzey": "Uzmanlık", "bilinmeyen": 1})
        self.assertEqual((t["sure_dk"], t["duzey"]), (25, "Uzmanlık"))
        self.assertNotIn("bilinmeyen", t)
        with self.assertRaises(ValueError):
            sh.kart_guncelle(d, {"egitmen": "baskasi"})

    def test_oge_kaydet_ve_sil(self):
        d = self.taslak()
        sh.oge_kaydet(d, "dikkat", {"metin": "Ateşi sorgulat"})
        sh.oge_kaydet(d, "dikkat", {"metin": "İkinci"})
        t = sh.oge_kaydet(d, "dikkat", {"id": "D1", "metin": "Ateşin yerini sorgulat"})
        self.assertEqual([(x["id"], x["metin"]) for x in t["dikkat"]], [("D1", "Ateşin yerini sorgulat"), ("D2", "İkinci")])
        t = sh.oge_sil(d, "dikkat", "D1")
        self.assertEqual([x["id"] for x in t["dikkat"]], ["D2"])
        sh.oge_kaydet(d, "terimler", {"terim": "nekrotizan"})
        t = sh.oge_kaydet(d, "terimler", "nekrotizan")
        self.assertEqual(t["terimler"], [{"terim": "nekrotizan"}])
        with self.assertRaises(ValueError):
            sh.oge_kaydet(d, "sorular", {"metin": "x", "kademe": "herkes"})
        with self.assertRaises(ValueError):
            sh.oge_kaydet(d, "baska", {})

    def test_doi_ekle_kunye_ve_internetsiz(self):
        d = self.taslak()
        q = "10.1111/jcpe.12946"
        ag = SahteAg({"https://api.crossref.org/works/" + q: kunye_yaniti(q, "Herrera", 2018),
                      "https://api.openalex.org/works/doi:" + q: json.dumps({"open_access": {"is_oa": True, "oa_status": "hybrid"}})})
        r = sh.doi_ekle(d, "doi:10.1111/jcpe.12946 10.1111/jcpe.99999", ag=ag)
        self.assertEqual(r["eklenen"], 2)
        ana, eksik = r["kaynaklar"]
        self.assertEqual((ana["id"], ana["rol"], ana["acik_erisim"]), ("herrera-ve-ikinci-2018", "ana", True))
        self.assertIn("uyari", eksik)
        self.assertNotIn("rol", eksik)
        # aynı DOI ikinci kez eklenmez
        self.assertEqual(sh.doi_ekle(d, q, ag=ag)["zaten_vardi"], 1)
        # künye sonradan gelir
        q2 = "10.1111/jcpe.99999"
        ag.yanitlar["https://api.crossref.org/works/" + q2] = kunye_yaniti(q2, "Papapanou", 2018)
        t = sh.kunyeleri_yenile(d, ag=ag)
        self.assertNotIn("uyari", t["kaynaklar"][1])
        self.assertEqual(t["kaynaklar"][1]["id"], eksik["id"])
        t = sh.ana_kaynak(d, eksik["id"])
        self.assertEqual([k.get("rol") for k in t["kaynaklar"]], [None, "ana"])

    def test_docx_bolumleri(self):
        d = self.taslak()
        n = sh.not_ekle(d, docx_yap(NOT_DOCX), "Akut lezyonlar notu.docx", "acik")
        self.assertEqual(n["id"], "not-akut-lezyonlar-notu")
        self.assertEqual(n["basliklar"], ["Giriş", "Nekrotizan gingivitisi ayırt et",
                                          "Herpetik gingivostomatitle karşılaştır", "Tedaviyi açıkla"])
        b = sh.not_bolumleri(d, n["id"])
        self.assertIn("Bulgu | Anlamı", b[2]["metin"])
        self.assertEqual(b[2]["duzey"], 2)

    def test_yayimlanmis_makale_notu(self):
        d = self.taslak()
        makale = ("Int J Periodontics Restorative Dent 2010. doi:10.11607/prd.0001\n"
                  "Copyright 2010 by Quintessence Publishing Co Inc. No part of this article may be reproduced "
                  "without written permission. Received March 2009; accepted June 2009.\n" + "Kritik kontur metni. " * 20)
        n = sh.not_ekle(d, makale.encode(), "su-2010.txt", "fakulte")
        self.assertIn("yayınevi adı", n["yayin_izi"])
        self.assertTrue(any("yayımlanmış bir makaleye" in h for h in sh.denetle(d)["hatalar"]))
        sh.oge_kaydet(d, "notlar", {"id": n["id"], "kademe": "paylasilmaz"})
        self.assertFalse(any("yayımlanmış bir makaleye" in h for h in sh.denetle(d)["hatalar"]))
        sh.oge_kaydet(d, "notlar", {"id": n["id"], "kademe": "fakulte", "izinli": True})
        self.assertFalse(any("yayımlanmış bir makaleye" in h for h in sh.denetle(d)["hatalar"]))
        # kendi notu (kaynakçada bir DOI olsa da) işaretlenmez
        k = sh.not_ekle(d, docx_yap(NOT_DOCX), "kendi notum.docx", "fakulte")
        self.assertNotIn("yayin_izi", k)

    def test_not_reddi(self):
        d = self.taslak()
        with self.assertRaises(ValueError):
            sh.not_ekle(d, b"x", "eski.doc")
        with self.assertRaises(ValueError):
            sh.not_ekle(d, "kısa".encode(), "bos.txt")
        with self.assertRaises(ValueError):
            sh.not_ekle(d, docx_yap(NOT_DOCX), "n.docx", "herkes")
        self.assertEqual(sh.taslak_oku(d)["notlar"], [])
        self.assertFalse(os.listdir(os.path.join(sh.dosya_klasoru(d), "notlar")))

    def test_kural_onerileri_ve_onay(self):
        d = self.taslak()
        sh.not_ekle(d, docx_yap(NOT_DOCX), "not.docx", "fakulte")
        o = sh.kural_onerileri(d)
        basliklar = [h["baslik"] for h in o["hedefler"]]
        self.assertEqual(basliklar, ["Nekrotizan gingivitisi ayırt et", "Herpetik gingivostomatitle karşılaştır",
                                     "Tedaviyi açıkla"])
        self.assertEqual([h["bloom"] for h in o["hedefler"]], ["cozumle", "cozumle", "anla"])
        self.assertEqual(o["hedefler"][0]["sayfalar"], [2])
        self.assertEqual(len(o["sorular"]), 3)
        # öneri onaylanmadan taslağa girmez
        self.assertEqual(sh.taslak_oku(d)["hedefler"], [])
        h1 = o["hedefler"][0]["oneri_id"]
        t = sh.oneri_kabul(d, "hedefler", h1, {"baslik": "NG'yi ayırt eder"})
        self.assertEqual([(h["id"], h["baslik"], h["bloom"]) for h in t["hedefler"]], [("H1", "NG'yi ayırt eder", "cozumle")])
        self.assertNotIn("gerekce", t["hedefler"][0])
        t = sh.oneri_reddet(d, "hedefler", o["hedefler"][1]["oneri_id"])
        self.assertEqual(len(t["oneriler"]["hedefler"]), 1)
        with self.assertRaises(ValueError):
            sh.oneri_kabul(d, "hedefler", h1)
        # soru, kabul edilen hedefe bağlanır (başlık düzeltildiyse bağlanamaz ama yine eklenir)
        s = next(x for x in sh.taslak_oku(d)["oneriler"]["sorular"] if x["hedef_baslik"] == "Tedaviyi açıkla")
        sh.oneri_kabul(d, "hedefler", sh.taslak_oku(d)["oneriler"]["hedefler"][0]["oneri_id"])
        t = sh.oneri_kabul(d, "sorular", s["oneri_id"])
        self.assertEqual((t["sorular"][0]["hedef"], t["sorular"][0]["kademe"]), ("H2", "fakulte"))

    def test_claude_onerisi_ve_malzeme(self):
        d = self.taslak()
        sh.not_ekle(d, docx_yap(NOT_DOCX), "not.docx", "fakulte")
        m = sh.claude_icin_malzeme(d, en_cok_sozcuk=5)
        self.assertEqual(m["not_bolumleri"][0]["sayfa"], 1)
        self.assertTrue(m["not_bolumleri"][0]["metin"].endswith("…"))
        self.assertIn("sihirbaz_oner", m["talimat"])
        o = sh.oneri_yaz(d, {"hedefler": [{"baslik": "X eder", "bloom": "değerlendir"}], "terimler": ["nekroz", ""]})
        self.assertEqual(o["hedefler"][0]["bloom"], "degerlendir")
        self.assertEqual(o["hedefler"][0]["oneri_id"], "claude-h-1")
        self.assertEqual([x["terim"] for x in o["terimler"]], ["nekroz"])

    def test_denetle(self):
        d = self.taslak()
        h = sh.denetle(d)["hatalar"]
        self.assertTrue(any("hedef" in x for x in h))
        self.assertTrue(any("kaynak" in x for x in h))
        sh.oge_kaydet(d, "hedefler", {"baslik": "Ayırt eder", "bloom": "cozumle"})
        sh.not_ekle(d, docx_yap(NOT_DOCX), "not.docx", "fakulte")
        sh.oge_kaydet(d, "sorular", {"metin": "Hangisi?", "tur": "secmeli"})
        sh.oge_kaydet(d, "sorular", {"metin": "Açıkla", "tur": "acik"})
        r = sh.denetle(d)
        self.assertEqual(len(r["hatalar"]), 1)
        self.assertIn("seçmeli", r["hatalar"][0])
        self.assertTrue(any("örnek cevap" in x for x in r["uyarilar"]))
        self.assertTrue(any("Açık pakette ders notu olmayacak" in x for x in r["uyarilar"]))
        with self.assertRaises(ValueError):
            sh.paketle(d, cikis=self.cikis)

    # --- Paketleme: kademeler ---
    def vaka_zip(self, kimlik="ng-vakasi"):
        with open(os.path.join(KOK, "ornek-dersler", "peri-implantitis-cerrahi", "vakalar", "ornek-implant-kanama.json"),
                  encoding="utf-8") as f:
            v = json.load(f)
        v = copy.deepcopy(v)
        v["id"] = kimlik
        v["hedefler"] = ["H1"]
        for d in v["dugumler"]:
            if d.get("hedef"):
                d["hedef"] = "H1"
        v["bulgular"][0]["gorsel"] = "gorseller/foto-1.jpg"
        v["bulgular"][0]["gorsel_aciklama"] = "Papil uçlarında nekroz"
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w") as z:
            z.writestr("vaka/kart.json", json.dumps(v, ensure_ascii=False))
            z.writestr("vaka/gorseller/foto-1.jpg", b"\xff\xd8\xff\xe0sahte")
            z.writestr("__MACOSX/vaka/._kart.json", b"x")
        return b.getvalue()

    def test_vaka_ekle(self):
        d = self.taslak()
        v = sh.vaka_ekle(d, self.vaka_zip(), "vaka.zip", "fakulte")
        self.assertEqual((v["id"], v["kademe"], v["hata"]), ("ng-vakasi", "fakulte", []))
        self.assertTrue(os.path.exists(os.path.join(sh.dosya_klasoru(d), "vakalar", "ng-vakasi", "gorseller", "foto-1.jpg")))
        with self.assertRaises(ValueError):
            sh.vaka_ekle(d, b"{bozuk", "kart.json")

    def test_paketle_kademeler(self):
        d = self.taslak()
        sh.kart_guncelle(d, {"aciklama_ogrenci": "Kısa açıklama"})
        sh.not_ekle(d, docx_yap(NOT_DOCX), "acik-not.docx", "acik")
        sh.not_ekle(d, docx_yap(NOT_DOCX[:3]), "fakulte-not.docx", "fakulte")
        sh.not_ekle(d, docx_yap(NOT_DOCX[:3]), "gizli-not.docx", "paylasilmaz")
        sh.vaka_ekle(d, self.vaka_zip("ng-vakasi"), "vaka.zip", "fakulte")
        sh.vaka_ekle(d, self.vaka_zip("acik-vaka"), "vaka2.zip", "acik")
        sh.oge_kaydet(d, "hedefler", {"baslik": "Ayırt eder", "bloom": "cozumle", "sayfalar": [2]})
        sh.oge_kaydet(d, "dikkat", {"metin": "Ateşi sorgulat"})
        sh.oge_kaydet(d, "yanilgilar", {"metin": "Her kanama periodontitistir", "hedef": "H1"})
        sh.oge_kaydet(d, "terimler", "nekrotizan")
        sh.oge_kaydet(d, "sorular", {"metin": "Açık soru", "tur": "acik", "ornek_cevap": "c", "kademe": "acik"})
        sh.oge_kaydet(d, "sorular", {"metin": "Fakülte sorusu", "tur": "acik", "ornek_cevap": "c", "kademe": "fakulte"})
        sh.oge_kaydet(d, "sorular", {"metin": "Gizli soru", "tur": "acik", "ornek_cevap": "c", "kademe": "paylasilmaz"})

        r = sh.paketle(d, cikis=self.cikis)
        self.assertEqual(r["kuruldu"], "ozel-akut-lezyon")

        def oku(zip_yolu):
            with zipfile.ZipFile(zip_yolu) as z:
                return {n: z.read(n) for n in z.namelist()}

        acik = oku(r["paketler"]["acik"]["dosya"])
        fak = oku(r["paketler"]["fakulte"]["dosya"])
        self.assertTrue(all(n.startswith("akut-lezyon/") for n in acik))
        self.assertTrue(all(n.startswith("ozel-akut-lezyon/") for n in fak))
        # Not sayfaları: açık not 4 bölüm (1–4), fakülte notu 2 (5–6), gizli not 2 (7–8)
        sayfalar = lambda p, on: sorted(n.split("/")[-1] for n in p if n.startswith(on + "/kaynak/"))  # noqa: E731
        self.assertEqual(sayfalar(acik, "akut-lezyon"), ["sayfa-%02d.txt" % i for i in (1, 2, 3, 4)])
        self.assertEqual(sayfalar(fak, "ozel-akut-lezyon"), ["sayfa-%02d.txt" % i for i in range(1, 7)])
        eg_a = json.loads(acik["akut-lezyon/egitmen.json"])
        eg_f = json.loads(fak["ozel-akut-lezyon/egitmen.json"])
        self.assertEqual((eg_a["dagitim"], eg_f["dagitim"]), ("acik", "fakulte"))
        self.assertEqual([s["metin"] for s in eg_a["soruBankasi"]], ["Açık soru"])
        self.assertEqual([s["metin"] for s in eg_f["soruBankasi"]], ["Açık soru", "Fakülte sorusu"])
        self.assertNotIn("kademe", eg_f["soruBankasi"][0])
        self.assertIn("5, 6, 7, 8", eg_a["kaynak"]["okumaNotu"])
        self.assertIn("7, 8", eg_f["kaynak"]["okumaNotu"])
        self.assertEqual(eg_a["ogretmenNotlari"], [{"id": "D1", "kural": "Ateşi sorgulat"}])
        self.assertEqual(eg_a["aciklama"], "Kısa açıklama")
        tum = b"".join(acik.values()) + b"".join(fak.values())
        self.assertNotIn("Gizli soru".encode(), tum)
        self.assertNotIn("gizli-not".encode(), tum)
        # Vakalar: açık pakette yalnız açık vaka; fakülte paketinde ikisi de 'ozel-' önekiyle, görsel yolu düzeltilmiş
        self.assertIn("akut-lezyon/vakalar/acik-vaka.json", acik)
        self.assertNotIn("akut-lezyon/vakalar/ng-vakasi.json", acik)
        kart = json.loads(fak["ozel-akut-lezyon/vakalar/ozel-ng-vakasi.json"])
        self.assertEqual((kart["id"], kart["ders"], kart["dagitim"]), ("ozel-ng-vakasi", "ozel-akut-lezyon", "fakulte"))
        self.assertEqual(kart["bulgular"][0]["gorsel"], "vakalar/ozel-ng-vakasi/foto-1.jpg")
        self.assertIn("ozel-akut-lezyon/vakalar/ozel-ng-vakasi/foto-1.jpg", fak)
        self.assertEqual(json.loads(fak["ozel-akut-lezyon/terimler.json"]), {"terimler": ["nekrotizan"]})
        # Bu bilgisayara kurulan sürüm bütün kademeleri içerir ve vakaları denetimden geçer
        kurulu = os.path.join(self.kok, "lessons", "ozel-akut-lezyon")
        self.assertEqual(len(os.listdir(os.path.join(kurulu, "kaynak"))), 8)
        self.assertFalse([u for u in r["uyarilar"] if u.startswith("Vaka ") and "onay" not in u], r["uyarilar"])
        self.assertTrue(sh.taslak_oku(d)["son_paket"]["tarih"])


if __name__ == "__main__":
    unittest.main()
