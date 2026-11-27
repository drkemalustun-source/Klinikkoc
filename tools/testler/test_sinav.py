"""Nilgün'ün sınavı: plan denetimi, uyarlamalı sıra, hedef başına puan, araç akışı ve gizlilik.
Çalıştırma:  python -m unittest discover -s tools/testler -v   (internete çıkmaz)
"""
import importlib.util
import json
import os
import sys
import tempfile
import unittest
os.environ.setdefault("KLINIK_KOC_ANLAM_KURMA", "1")

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(KOK, "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ornek_ders  # noqa: E402
import sinav  # noqa: E402

DERS = ornek_ders.DERS


def setUpModule():
    ornek_ders.kur()


def tearDownModule():
    ornek_ders.kaldir()


def oku(*yol):
    with open(os.path.join(KOK, *yol), encoding="utf-8") as f:
        return f.read()


def soru(hedef, duzey, metin=None, zorunlu=(0,), n=3, ders="d", sayfa=3):
    return {"ders": ders, "hedef": hedef, "duzey": duzey, "soru": metin or "%s hedefi için %s düzeyinde soru?" % (hedef, duzey),
            "anahtar": [{"madde": "%s %s beklenen cevap maddesi" % (hedef, duzey), "sayfa": sayfa}],
            "olcutler": [{"metin": "ölçüt %d" % i, "zorunlu": i in zorunlu} for i in range(n)]}


HEDEFLER = [{"ders": "d", "id": "H1", "baslik": "Bir", "bloom": "anla"},
            {"ders": "d", "id": "H2", "baslik": "İki", "bloom": "cozumle"}]


def guclu(ders, madde):
    return "guclu", [3]


class PlanDenetimi(unittest.TestCase):
    def plan(self, sorular, **ek):
        ek.setdefault("dayanak_fn", guclu)
        return sinav.plan_denetle(sorular, HEDEFLER, {"d": 10}, **ek)

    def test_tam_plan_kabul(self):
        r = self.plan([soru(h, z) for h in ("H1", "H2") for z in ("hedef", "alt", "ust")])
        self.assertEqual((len(r["sorular"]), r["reddedilen"], r["eksik_hedefler"]), (6, [], []))
        self.assertEqual([q["no"] for q in r["sorular"]], [1, 2, 3, 4, 5, 6])
        q = r["sorular"][0]
        self.assertEqual([o["id"] for o in q["olcutler"]], ["o1", "o2", "o3"])
        self.assertEqual(q["tam_icin"], 2)  # üç ölçütün üçte ikisi
        self.assertEqual((q["kaynak"], q["dayanak"]), ("nilgun", "guclu"))

    def test_onaylanan_ornek_dort_olcut(self):
        """Kemal'in onayladığı örnek: altı ölçüt, ikisi zorunlu → tam cevap için dört ölçüt."""
        self.assertEqual(sinav.tam_icin_varsayilan([{"zorunlu": i in (0, 4)} for i in range(6)]), 4)

    def test_hedef_duzeyi_sorusu_olmayan_hedef_eksik(self):
        r = self.plan([soru("H1", "hedef"), soru("H2", "alt")])
        self.assertEqual([e["hedef"] for e in r["eksik_hedefler"]], ["H2"])

    def test_sayfasiz_anahtar_ve_olcutsuz_soru_reddedilir(self):
        a = soru("H1", "hedef", sayfa=None)
        b = soru("H2", "hedef")
        b["olcutler"] = []
        c = soru("H1", "alt", sayfa=99)
        r = self.plan([a, b, c])
        self.assertEqual(len(r["reddedilen"]), 3)
        self.assertEqual(r["sorular"], [])

    def test_dayanagi_olmayan_ve_zayif_olan_soru_girmez(self):
        def fn(ders, madde):
            return ("yok", []) if "H1" in madde else ("zayif", [4])
        r = self.plan([soru("H1", "hedef"), soru("H2", "hedef")], dayanak_fn=fn)
        self.assertEqual(r["sorular"], [])
        self.assertIn("kaynakta bulunamadı", r["reddedilen"][0]["nedenler"][0])
        self.assertIn("dayanağı zayıf", r["reddedilen"][1]["nedenler"][0])
        eski = sinav.ZAYIF_KABUL
        sinav.ZAYIF_KABUL = True
        try:
            r = self.plan([soru("H1", "hedef"), soru("H2", "hedef")], dayanak_fn=fn)
            self.assertEqual([(q["hedef"], q["dayanak"]) for q in r["sorular"]], [("H2", "zayif")])  # "yok" yine girmez
        finally:
            sinav.ZAYIF_KABUL = eski

    def test_ogretmen_sorusu_dayanak_denetimine_girmez(self):
        metin = "Peri-implantitiste cerrahi kararı hangi bulgulara dayanır?"
        r = self.plan([soru("H1", "hedef", metin), soru("H2", "hedef")], onayli={"d": [metin]},
                      dayanak_fn=lambda d, m: ("yok", []) if "H1" in m else ("guclu", [3]))
        self.assertEqual([(q["hedef"], q["kaynak"]) for q in r["sorular"]], [("H1", "ogretmen"), ("H2", "nilgun")])

    def test_olcme_sorusuna_benzeyen_soru_reddedilir(self):
        olcme = "NG tedavisinin 3. gününde ağrısı geçen hasta artık gelmeme gerek yok diyor. En uygun yaklaşım hangisidir?"
        r = self.plan([soru("H1", "hedef", olcme.replace("3. gününde", "üçüncü gününde")), soru("H2", "hedef")],
                      olcme={"d": [olcme]})
        self.assertEqual([x["hedef"] for x in r["reddedilen"]], ["H1"])
        self.assertIn("pilot ölçme", r["reddedilen"][0]["nedenler"][0])

    def test_cikarilan_hedef_eksik_sayilmaz(self):
        r = self.plan([soru("H1", "hedef")], cikarilan=[{"ders": "d", "hedef": "H2", "neden": "Kaynakta yeterli bilgi yok"}])
        self.assertEqual((r["eksik_hedefler"], [c["hedef"] for c in r["cikarilan"]]), ([], ["H2"]))

    def test_kisa_secim(self):
        h = [{"ders": "d", "id": "H%d" % i} for i in range(1, 13)]
        self.assertEqual([x["id"] for x in sinav.kisa_secim(h)], ["H1", "H3", "H5", "H7", "H9", "H11"])
        s = [x["id"] for x in sinav.kisa_secim(h, oncelik=["d/H12", "d/H8"], ikincil=["d/H1", "d/H2"])]
        self.assertEqual(len(s), 6)
        self.assertTrue({"H12", "H8", "H1", "H2"} <= set(s))
        self.assertEqual(len(sinav.kisa_secim(h[:4])), 4)


class AkisVePuan(unittest.TestCase):
    def sinav(self, sure="tam"):
        r = sinav.plan_denetle([soru(h, z) for h in ("H1", "H2") for z in ("hedef", "alt", "ust")], HEDEFLER, {"d": 10})
        return {"sure": sure, "hedefler": HEDEFLER, "sorular": r["sorular"], "cevaplar": [], "tahmin": 80}

    def sor(self, s, karsilanan, guven=None):
        q = sinav.sonraki(s)
        sinav.cevap_isle(s, q["no"], karsilanan, guven, "cevap")
        return (q["hedef"], q["duzey"])

    def test_tam_cevap_uste_cikar_eksik_cevap_alta_iner(self):
        s = self.sinav()
        self.assertEqual(self.sor(s, ["o1", "o2"]), ("H1", "hedef"))      # tam → üst
        self.assertEqual(self.sor(s, ["o1", "o2", "o3"]), ("H1", "ust"))
        self.assertEqual(self.sor(s, ["o2"]), ("H2", "hedef"))            # zorunlu eksik → kısmi → alt
        self.assertEqual(self.sor(s, ["o1", "o2"]), ("H2", "alt"))
        self.assertIsNone(sinav.sonraki(s))
        r = sinav.sonuc(s)
        self.assertEqual([(h["hedef"], h["puan"], h["hedefin_ustunde"]) for h in r["hedefler"]],
                         [("H1", 2, True), ("H2", 1, False)])
        self.assertEqual((r["puan"], r["en_yuksek"], r["yuzde"]), (3, 4, 75))
        self.assertEqual(r["tahmin"], {"beklenen": 80, "gercek": 75, "fark": -5})
        self.assertTrue(r["tamamlandi"])

    def test_puan_kurali(self):
        """Hedef düzeyinde tam 2; kısmen ya da yalnız alt düzeyde tam 1; hiçbiri 0. Üst düzey puanı değiştirmez."""
        s = self.sinav()
        self.sor(s, ["o1", "o2"])  # H1 hedef tam
        self.sor(s, [])            # H1 üst boş → puan yine 2
        self.sor(s, [])            # H2 hedef yok
        self.sor(s, ["o1", "o2"])  # H2 alt tam → 1
        self.assertEqual([h["puan"] for h in sinav.sonuc(s)["hedefler"]], [2, 1])
        s = self.sinav()
        self.sor(s, ["o1", "o2"]); self.sor(s, [])
        self.sor(s, []); self.sor(s, ["o2"])  # H2: hedef yok, alt kısmi → 0
        self.assertEqual([h["puan"] for h in sinav.sonuc(s)["hedefler"]], [2, 0])

    def test_kisa_sinavda_ust_sorulmaz(self):
        s = self.sinav("kisa")
        self.assertEqual(self.sor(s, ["o1", "o2"]), ("H1", "hedef"))
        self.assertEqual(self.sor(s, ["o1", "o2"]), ("H2", "hedef"))
        self.assertIsNone(sinav.sonraki(s))

    def test_sira_disi_ve_bilinmeyen_olcut(self):
        s = self.sinav()
        with self.assertRaises(ValueError):
            sinav.cevap_isle(s, 4, ["o1"])
        with self.assertRaises(ValueError):
            sinav.cevap_isle(s, 1, ["o9"])
        with self.assertRaises(ValueError):
            sinav.cevap_isle(s, 1, ["o1"], "çok eminim")

    def test_emin_ama_yanlis_ve_yarim(self):
        s = self.sinav()
        self.sor(s, ["o2"], "emin")
        r = sinav.sonuc(s)
        self.assertEqual([x["hedef"] for x in r["emin_ama_yanlis"]], ["H1"])
        self.assertFalse(r["tamamlandi"])
        self.assertEqual((r["puan"], r["en_yuksek"]), (1, 2))  # yalnız cevaplanan hedef sayılır
        self.assertEqual([h["hedef"] for h in r["sorulmayan_hedefler"]], ["H2"])
        md = sinav.rapor_md(dict(s, dersler=["d"], tarih="2026-11-27"), r, {"d": "Deneme dersi"}, None, "- H1: İnci ile çalış.")
        for parca in ("not için değildir", "yarıda bırakıldı", "Emin olduğun ama eksik kalan", "ölçüt 0 (zorunlu)", "İnci ile çalış"):
            self.assertIn(parca, md)

    def test_onceki_sinavla_karsilastirma(self):
        simdi = {"yuzde": 75, "hedefler": [{"ders": "d", "hedef": "H1", "puan": 2}, {"ders": "d", "hedef": "H2", "puan": 0}]}
        once = {"yuzde": 50, "tarih": "2026-11-20", "hedefler": [{"ders": "d", "hedef": "H1", "puan": 1}, {"ders": "d", "hedef": "H2", "puan": 1}]}
        k = sinav.karsilastir(simdi, once)
        self.assertEqual((k["ilerleyen_hedefler"], k["gerileyen_hedefler"], k["onceki_yuzde"]), (["d/H1"], ["d/H2"], 50))
        self.assertIsNone(sinav.karsilastir(simdi, None))


class Araclar(unittest.TestCase):
    """sinav_hazirla → sinav_plani_kaydet → sinav_baslat → sinav_cevap → sinav_bitir (örnek dersle)."""

    def setUp(self):
        import kayit_aktar
        self.ka = kayit_aktar
        self.gecici = tempfile.TemporaryDirectory()
        spec = importlib.util.spec_from_file_location("tahta_mcp_sinav", os.path.join(KOK, "tools", "tahta-mcp.py"))
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.m.KAYIT_KOK = os.path.join(self.gecici.name, "kayitlar")
        self.m.ESKI_KAYIT_KOK = os.path.join(self.gecici.name, "eski")
        self.m._DEPO = None
        self.m._sinav_dayanak = lambda ders, madde: (("yok", []) if "UYDURMA" in madde else ("guclu", [3]))
        self.m.sinav_modu = lambda *a, **k: self.modlar.append((a, k))
        # bilgi_bankasi ve ders_sonu öteki testlerle ortak modüllerdir: değişiklik tearDown'da geri alınır
        self._eski = (self.m.bilgi_bankasi.dizinle, self.m.ders_sonu.depo)
        self.m.bilgi_bankasi.dizinle = lambda *a, **k: None
        self.m.ders_sonu.depo = self.m.depo
        self.modlar = []
        self.eski_ortam = os.environ.pop("KLINIK_KOC_KAYIT", None)

    def tearDown(self):
        self.m.bilgi_bankasi.dizinle, self.m.ders_sonu.depo = self._eski
        if self.eski_ortam is not None:
            os.environ["KLINIK_KOC_KAYIT"] = self.eski_ortam
        self.gecici.cleanup()

    def arac(self, ad, **a):
        r = self.m.ISLEYICILER[ad](a)
        t = r["content"][0]["text"]
        if r.get("isError"):
            raise AssertionError(t)
        return json.loads(t)

    def hazirla(self, sure="kisa"):
        h = self.arac("sinav_hazirla", dersler=[DERS], ogrenci="Ada Gün", ayirt="271", sure=sure)
        return h["ogrenci"]["kimlik"], h

    def sorular(self, hedefler, ust=False):
        duzeyler = ("hedef", "alt") + (("ust",) if ust else ())
        return [soru(h["id"], z, ders=DERS) for h in hedefler for z in duzeyler]

    def test_hazirlik(self):
        kim, h = self.hazirla()
        self.assertIn("Nilgün", h["egitmen"])
        self.assertIn("Sen Nilgün'sün", h["kurallar"])
        self.assertNotIn("Ortak eğitmen çekirdeği", h["kurallar"])  # Nilgün ortak çekirdeği yüklemez
        s = h["sinav"]
        self.assertEqual((s["hedef_sayisi"], len(s["hedefler"])), (6, 6))
        self.assertTrue(s["bu_sinavda_sorulmayan_hedefler"])
        self.assertTrue(all(x.get("bloom") for x in s["hedefler"]))
        self.assertTrue(s["dersler"][0]["onayli_sorular"])
        self.assertNotIn("formlar", json.dumps(h, ensure_ascii=False))  # pilot ölçme formları hiç verilmez
        tam = self.arac("sinav_hazirla", dersler=[DERS], ogrenci_kimligi=kim, sure="tam")["sinav"]
        self.assertEqual(tam["hedef_sayisi"], 22)
        self.assertIsNone(tam["bu_sinavda_sorulmayan_hedefler"])
        with self.assertRaises(Exception):
            self.arac("sinav_hazirla", dersler=["kendi-makalelerim"], ogrenci_kimligi=kim)

    def test_tam_akis_puan_rapor_kart_ve_gizlilik(self):
        kim, h = self.hazirla()
        no, hedefler = h["sinav"]["sinav"], h["sinav"]["hedefler"]
        # dayanağı olmayan anahtar: plan kaydedilmez
        kotu = self.sorular(hedefler)
        kotu[0]["anahtar"] = [{"madde": "UYDURMA bilgi", "sayfa": 3}]
        r = self.arac("sinav_plani_kaydet", ogrenci=kim, sinav=no, sorular=kotu)
        self.assertEqual((r["durum"], r["kaydedilmedi"]), ("eksik", True))
        self.assertEqual(r["eksik_hedefler"][0]["hedef"], hedefler[0]["id"])
        # düzeltilmiş plan kaydedilir ve artık değişmez
        r = self.arac("sinav_plani_kaydet", ogrenci=kim, sinav=no, sorular=self.sorular(hedefler))
        self.assertEqual((r["durum"], r["hedef_sayisi"], r["soru_sayisi"]), ("hazir", 6, 12))
        with self.assertRaises(Exception):
            self.arac("sinav_plani_kaydet", ogrenci=kim, sinav=no, sorular=self.sorular(hedefler))
        b = self.arac("sinav_baslat", ogrenci=kim, sinav=no, tahmin=70)
        self.assertEqual((b["soru"]["no"], b["soru"]["duzey"], b["soru"]["hedef_sirasi"]), (1, "hedef", "1 / 6"))
        self.assertEqual(self.modlar[-1], (("Hedef 1 / 6",), {}))
        # ilk hedef: eksik cevap → alt düzey soru; sonra bütün hedefler tam
        c = self.arac("sinav_cevap", ogrenci=kim, sinav=no, no=1, cevap="bilmiyorum", karsilanan=[], guven="emin")
        self.assertEqual((c["soru"]["hedef"], c["soru"]["duzey"]), (hedefler[0]["id"], "alt"))
        with self.assertRaises(Exception):
            self.arac("sinav_bitir", ogrenci=kim, sinav=no)  # bitmeden bitirilemez (yarim değilse)
        c = self.arac("sinav_cevap", ogrenci=kim, sinav=no, no=c["soru"]["no"], cevap="alt cevap", karsilanan=["o1", "o2"])
        while not c["bitti"]:
            self.assertEqual(c["soru"]["duzey"], "hedef")
            c = self.arac("sinav_cevap", ogrenci=kim, sinav=no, no=c["soru"]["no"], cevap="tam cevap",
                          karsilanan=["o1", "o2", "o3"], guven="biraz")
        s = self.arac("sinav_bitir", ogrenci=kim, sinav=no)
        r = s["sonuc"]
        self.assertEqual((r["puan"], r["en_yuksek"], r["yuzde"]), (11, 12, 92))
        self.assertEqual(r["tahmin"]["fark"], 22)
        self.assertEqual([x["hedef"] for x in r["emin_ama_yanlis"]], [hedefler[0]["id"]])
        self.assertEqual([x["hedef"] for x in r["zayif_hedefler"]], [hedefler[0]["id"]])
        self.assertEqual(s["tavsiye"]["calisilacak"][0]["egitmen"], "Mercan")
        self.assertEqual(s["tekrar_karti"], 1)
        self.assertEqual(self.modlar[-1], ((), {"kapat": True}))
        rapor = oku(s["rapor_dosyasi"])
        self.assertIn("**92 / 100**", rapor)
        self.assertIn("Mercan ile çalış", rapor)
        # sınav dosyası alt klasörde: ders kaydı sanılmaz
        self.assertIn(os.sep + "sinavlar" + os.sep, s["rapor_dosyasi"])
        # ders kaydı: eğitmen yalnız zayıf hedefi görür, puanı görmez; hedef düzeyleri değişmez
        oz = self.arac("kayit_oku", ogrenci=kim, ders=DERS)
        self.assertEqual(oz["son_sinav"]["zayif_hedefler"], [hedefler[0]["id"]])
        self.assertNotIn("92", json.dumps(oz["son_sinav"]))
        self.assertTrue(all(v["durum"] == "ele_alinmadi" for v in oz["hedefler"].values()))
        # tekrar kartı zamanı gelince listede
        kartlar = self.m.ders_sonu.kartlari_oku(kim)["kartlar"][DERS]
        self.assertEqual((len(kartlar), kartlar[0]["hedef"]), (1, hedefler[0]["id"]))
        self.assertIn("Nilgün", kartlar[0]["kaynak"])
        # anonim araştırma aktarımına sınavdan hiçbir şey girmez
        anonim = json.dumps(self.ka.anonim(self.m.depo()), ensure_ascii=False)
        for yasak in ("sinav", "bilmiyorum", "tam cevap", "zayif"):
            self.assertNotIn(yasak, anonim)
        # ikinci sınav: önceki zayıf hedef önce gelir ve kendi önceki sonucuyla karşılaştırılır
        h2 = self.arac("sinav_hazirla", dersler=[DERS], ogrenci_kimligi=kim, sure="kisa")["sinav"]
        self.assertIn(hedefler[0]["id"], [x["id"] for x in h2["hedefler"]])
        self.assertEqual(h2["onceki_sinav"]["yuzde"], 92)
        # bitmiş sınav yeniden başlatılamaz
        with self.assertRaises(Exception):
            self.arac("sinav_baslat", ogrenci=kim, sinav=no)

    def test_yarim_birakma(self):
        kim, h = self.hazirla()
        no, hedefler = h["sinav"]["sinav"], h["sinav"]["hedefler"]
        self.arac("sinav_plani_kaydet", ogrenci=kim, sinav=no, sorular=self.sorular(hedefler))
        self.arac("sinav_baslat", ogrenci=kim, sinav=no)
        self.arac("sinav_cevap", ogrenci=kim, sinav=no, no=1, cevap="c", karsilanan=["o1", "o2", "o3"])
        s = self.arac("sinav_bitir", ogrenci=kim, sinav=no, yarim=True)
        self.assertEqual((s["durum"], s["sonuc"]["yuzde"], len(s["sonuc"]["sorulmayan_hedefler"])), ("yarim", 100, 5))

    def test_gecersiz_sinav_numarasi(self):
        kim, _ = self.hazirla()
        for no in ("../../x", "yok", ""):
            with self.assertRaises(Exception):
                self.arac("sinav_baslat", ogrenci=kim, sinav=no)

    def test_nilgun_kural_izi_ve_damga(self):
        kim, h = self.hazirla()
        yol = os.path.join(self.m.sinav_klasoru(kim), h["sinav"]["sinav"] + ".json")
        s = json.loads(oku(yol))
        self.assertEqual(s["surum_damgasi"], {"program": self.m.SURUM, "egitmen": "nilgun", "kural_izi": self.m.kural_izi("nilgun")})
        self.assertNotEqual(self.m.kural_izi("nilgun"), self.m.kural_izi("inci"))


class MetinlerVeAraclar(unittest.TestCase):
    def test_sozlu_prova_araci_kalkti_sinav_araclari_var(self):
        import mcp_araclar
        adlar = {a["name"] for a in mcp_araclar.ARACLAR}
        self.assertNotIn("sozlu_prova", adlar)
        self.assertTrue({"sinav_hazirla", "sinav_plani_kaydet", "sinav_baslat", "sinav_cevap", "sinav_bitir"} <= adlar)
        self.assertIn("Sınavı sen önerme", mcp_araclar.TALIMAT)

    def test_ortak_cekirdekte_sinav_bolumu(self):
        m = oku("egitmenler", "ortak.md")
        self.assertIn("## 11. Sınav (Nilgün)", m)
        self.assertIn("Sınavı kendin yapma; sınav önerme.", m)
        self.assertIn("Sınav puanını gündeme getirme; yalnız hedefi söyle.", m)

    def test_nilgun_metni(self):
        m = oku("egitmenler", "nilgun.md")
        for parca in ("Öğretmezsin; yoklar, ölçer ve sonunda yol gösterirsin.", "**Anahtar önce yazılır.**",
                      "Yüz üzerinden kaç bekliyorsun?", "puanı program hesaplar", "Pilot ölçme testlerinin sorularını kullanma"):
            self.assertIn(parca, m)


class Arayuz(unittest.TestCase):
    """Görünüşünü Kemal Üstün'ün 27 Kasım 2026'da onayladığı arayüz: ana ekranda düğme, tahtada sınav görünümü."""

    def test_ana_ekranda_sozlu_sinav_dugmesi(self):
        js = oku("js", "ana.js")
        for parca in ("Sözlü sınav ol", "sinavaBasla", "Sözlü sınav: Nilgün", "Kısa · yaklaşık 15 dk", "Tam · bütün hedefler",
                      "sonuç yalnız bu bilgisayarda kalır", "sinavDugme.disabled = !secili.dersler.size"):
            self.assertIn(parca, js)
        self.assertIn(".k-sinav-sure", oku("css", "kil.css"))

    def test_secim_sinav_istegini_tasir(self):
        import ana_ekran as A
        with tempfile.TemporaryDirectory() as g:
            eski = (A.secim_yolu, A.dersler, A.pdfler)
            A.secim_yolu = lambda: os.path.join(g, "secim.json")
            A.dersler = lambda: [{"ders": "d1", "baslik": "Bir"}, {"ders": "d2", "baslik": "İki"}]
            A.pdfler = lambda: [{"id": "p1", "baslik": "Makalem"}]
            try:
                s = A.secim_yaz(["d1"], ["p1"], {"sure": "kisa"})
                self.assertEqual((s["sinav"], s["pdfler"]), ({"sure": "kisa"}, []))  # PDF sınava girmez
                self.assertEqual(s["claude_cumlesi"], "Seçtiğim dersten kısa bir sözlü sınav olmak istiyorum.")
                self.assertEqual(A.secim_yaz(["d1", "d2"], [], {"sure": "tam"})["claude_cumlesi"],
                                 "Seçtiğim derslerden tam bir sözlü sınav olmak istiyorum.")
                self.assertEqual(A.secim_oku()["sinav"], {"sure": "tam"})
                # "Seçilenlerle çalış" sınav isteğini siler
                s = A.secim_yaz(["d1"], ["p1"])
                self.assertIsNone(s["sinav"])
                self.assertIn("dersini çalışalım", s["claude_cumlesi"])
                self.assertIsNone(A.secim_yaz([], ["p1"], {"sure": "kisa"})["sinav"])  # ders yoksa sınav da yok
            finally:
                A.secim_yolu, A.dersler, A.pdfler = eski

    def test_calisma_secimi_sinava_yonlendirir(self):
        spec = importlib.util.spec_from_file_location("tahta_mcp_secim", os.path.join(KOK, "tools", "tahta-mcp.py"))
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        eski = m.ana_ekran.secim_metni
        m.ana_ekran.secim_metni = lambda: {"dersler": [DERS], "pdfler": [], "ders_adlari": ["Peri"], "pdf_adlari": [],
                                           "tarih": "2026-11-27 18:00", "sinav": {"sure": "tam"}, "claude_cumlesi": "x"}
        try:
            r = json.loads(m.ISLEYICILER["calisma_secimi"]({})["content"][0]["text"])
        finally:
            m.ana_ekran.secim_metni = eski
        self.assertTrue(r["sinav"])
        self.assertIn("sinav_hazirla", r["not"])
        self.assertIn("sure='tam'", r["not"])
        self.assertNotIn("egitmen_hazirla", r["not"])

    def test_tahtada_sinav_gorunumu(self):
        html, js, css = oku("canli.html"), oku("js", "canli.js"), oku("css", "canli.css")
        self.assertIn('<textarea id="yazi" rows="1"', html)
        self.assertIn('id="sinavRozet"', html)
        self.assertIn('<span class="canli-gonder-yazi">Cevapla</span>', html)
        self.assertIn("Cevabınız kendiliğinden gönderilmez.", html)
        for parca in ("function sinavModu(k)", "k.tur === 'sinav'", "if (sinav.acik) {", "SINAV_GONDER",
                      "(cevapla|gönder|gonder)", "Sözlü sınav · Nilgün"):
            self.assertIn(parca, js)
        # sınavda süre sayacı kurulmaz: sınav dalı, ONAY_MS zamanlayıcısından önce döner
        baslat = js[js.index("    baslat(metin, ham, motor, duzeltmeler, guven) {"):js.index("    // Öğrenci kutuya dokundu")]
        self.assertLess(baslat.index("if (sinav.acik) {"), baslat.index("setTimeout(() => this.gonder(), ONAY_MS)"))
        self.assertIn(".canli.sinav-modu .canli-kutu textarea", css)
        self.assertIn(".canli-gonder-yazi { display: none; }", css)
        # derste kutu tek satır kalır
        self.assertIn(".canli-kutu textarea { resize: none; padding: 0; margin: 0; line-height: 1.4; height: 1.4em;", css)


if __name__ == "__main__":
    unittest.main()
