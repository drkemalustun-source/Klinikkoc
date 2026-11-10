"""Ders sonu testleri: tamamlama raporu, tekrar kartları, depolama sınırı, arşivle → geri yükle.
Çalıştırma:  python -m unittest discover -s tools/testler -v   (internete çıkmaz)
"""
import importlib.util
import json
import os
import sys
import tempfile
import unittest
import zipfile

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(KOK, "tools"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bilgi_bankasi  # noqa: E402
import ders_paketi  # noqa: E402
import ders_sonu as ds  # noqa: E402
import makale_bulucu as mb  # noqa: E402
from test_makale import makale_pdf  # noqa: E402

PYPDF = importlib.util.find_spec("pypdf") is not None
DERS = "akut-ders"
DOI = "10.1111/jcpe.12946"

EGITMEN = {
    "surum": 1, "baslik": "Akut periodontal lezyonlar", "duzey": "Lisans", "egitmen": "inci",
    "kaynak": {"baslik": "Not", "sayfaMetni": "kaynak/sayfa-{nn}.txt", "sayfaSayisi": 1},
    "hedefler": [{"id": "H1", "baslik": "Nekrotizan gingivitisi tanır", "bloom": "anla"},
                 {"id": "H2", "baslik": "Apseyi ayırt eder", "bloom": "cozumle"}],
    "soruBankasi": [{"id": "S1", "metin": "Nekrotizan gingivitisin üç temel bulgusu nedir?", "tur": "acik",
                     "bloom": "hatirla", "hedef": "H1", "ornek_cevap": "Papil nekrozu, ağrı, kanama."},
                    {"id": "S2", "metin": "Kolay soru?", "tur": "acik", "hedef": "H1"}],
}
VAKA = {"id": "v1", "baslik": "Ağrılı diş eti", "basvuru": {"sikayet": "Üç gündür diş etim kanıyor"},
        "dugumler": [{"id": "tani", "tur": "karar", "soru": "En olası tanı hangisi?", "hedef": "H2",
                      "secenekler": [{"metin": "Periodontal apse", "sonuc": "dogru"},
                                     {"metin": "Gingivit", "sonuc": "yanlis"}]}]}


class DersSonuTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.kok = os.path.join(t, "program")
        os.makedirs(os.path.join(self.kok, "lessons"))
        self.eski = (mb.KOK, bilgi_bankasi.KOK, bilgi_bankasi.DIZIN, ders_paketi.KOK)
        mb.KOK = bilgi_bankasi.KOK = ders_paketi.KOK = self.kok
        bilgi_bankasi.DIZIN = os.path.join(self.kok, ".dizin", "bilgi.sqlite")
        anahtarlar = ("KLINIK_KOC_VERI", "KLINIK_KOC_KAYIT", "KLINIK_KOC_MAKALE", "HOME", "OneDrive")
        self.ortam = {k: os.environ.get(k) for k in anahtarlar}
        os.environ["KLINIK_KOC_VERI"] = os.path.join(t, "veri")
        os.environ["KLINIK_KOC_KAYIT"] = os.path.join(t, "veri", "kayitlar")
        os.environ["KLINIK_KOC_MAKALE"] = os.path.join(t, "ev", "Documents", "KlinikKoç Makaleler")
        os.environ["HOME"] = os.path.join(t, "ev")
        os.environ.pop("OneDrive", None)
        os.makedirs(os.path.join(t, "ev", "Documents"))
        self.arsiv = os.path.join(t, "arsiv")
        self.ders_kur()

    def tearDown(self):
        mb.KOK, bilgi_bankasi.KOK, bilgi_bankasi.DIZIN, ders_paketi.KOK = self.eski
        for k, v in self.ortam.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    # --- hazırlık ---
    def ders_kur(self):
        zip_yolu = os.path.join(self.tmp.name, "paket.zip")
        with zipfile.ZipFile(zip_yolu, "w") as z:
            z.writestr(DERS + "/egitmen.json", json.dumps(EGITMEN, ensure_ascii=False))
            z.writestr(DERS + "/kaynak/sayfa-01.txt", "Nekrotizan gingivitis papil nekrozu ağrı ve kanama ile seyreder.")
            z.writestr(DERS + "/kaynaklar/kaynaklar.json", json.dumps(
                {"kaynaklar": [{"id": "herrera", "doi": DOI, "kisa": "Herrera 2018"}]}))
            z.writestr(DERS + "/vakalar/v1.json", json.dumps(VAKA, ensure_ascii=False))
        ders_paketi.yukle(zip_yolu)
        # Bu bilgisayarda üretilenler: makale metni, ses
        mm = os.path.join(self.kok, "lessons", DERS, "makale-metin", "herrera")
        os.makedirs(mm)
        with open(os.path.join(mm, "sayfa-001.txt"), "w", encoding="utf-8") as f:
            f.write("Peri-implant text " * 200)
        os.makedirs(os.path.join(self.kok, "lessons", DERS, "audio"))
        with open(os.path.join(self.kok, "lessons", DERS, "audio", "a.mp3"), "wb") as f:
            f.write(b"\0" * 5000)
        self.pdf = os.path.join(mb.makale_klasoru(DERS), mb.dosya_adi({"doi": DOI}))
        os.makedirs(os.path.dirname(self.pdf))
        with open(self.pdf, "wb") as f:
            f.write(makale_pdf(DOI, "arsiv"))
        d = mb.durum_oku(DERS)
        d["kaynaklar"]["herrera"] = {"durum": "hazir", "nereden": "klasor", "dosya": self.pdf}
        mb.durum_yaz(DERS, d)
        bilgi_bankasi.dizinle([DERS], sessiz=True, yol=bilgi_bankasi.DIZIN)

    def kayit_ac(self):
        dp = ds.depo()
        kimlik = dp.kimlik_olustur("Ayşe Yılmaz", "123")
        c = lambda **x: dict(x, tarih="2026-11-01", en_yuksek=x.get("en_yuksek", 1))  # noqa: E731
        k = {"ogrenci": "Ayşe Yılmaz", "ders": DERS, "hedefler": {"H1": {"durum": "destekle_yapti"}},
             "yanilgilar": {"Y1": {"durum": "acik"}}, "guven": [], "sorular": [{"soru": "Ateş olur mu?"}],
             "testler": [], "vakalar": [{"vaka": "v1", "sonuc": "kotu", "tarih": "2026-11-01"}],
             "oturumlar": [{"tarih": "2026-11-01", "sure_dk": 25}, {"tarih": "2026-11-03", "sure_dk": 50}],
             "cevaplar": [c(soru="S1", hedef="H1", bloom="hatirla", puan=0, en_yuksek=2, ilk_deneme=True, tur="acik"),
                          c(soru="S1", hedef="H1", bloom="hatirla", puan=2, en_yuksek=2, ilk_deneme=False, tur="acik"),
                          c(soru="S2", hedef="H1", puan=1, ilk_deneme=True, tur="acik"),
                          c(vaka="v1", dugum="tani", soru="tani", hedef="H2", bloom="uygula", puan=0, ilk_deneme=True,
                            tur="vaka_karar")]}
        dp.yaz(kimlik, DERS, k)
        return kimlik

    # --- testler ---
    def test_sinir(self):
        self.assertEqual(ds.sinir_gb(), 2.0)
        self.assertEqual(ds.sinir_ayarla("0,5".replace(",", ".")), 0.5)
        self.assertEqual(ds.sinir_gb(), 0.5)
        for kotu in ("abc", 0, 5000):
            with self.assertRaises(ValueError):
                ds.sinir_ayarla(kotu)

    def test_depolama_ve_yerlesik(self):
        d = ds.depolama()
        satir = next(x for x in d["dersler"] if x["ders"] == DERS)
        self.assertGreater(satir["ders_bayt"], 5000)
        self.assertGreater(satir["dizin_bayt"], 0)
        self.assertGreater(satir["pdf_bayt"], 0)
        self.assertFalse(satir["yerlesik"])
        self.assertFalse(d["asildi"])
        self.assertEqual(d["arsiv_adaylari"], [DERS])
        ds.sinir_ayarla(0.1)
        with open(os.path.join(self.kok, "lessons", DERS, "audio", "buyuk.bin"), "wb") as f:
            f.truncate(int(0.11 * 1024 ** 3))  # seyrek dosya: diskte yer kaplamaz
        self.assertTrue(ds.depolama()["asildi"])
        with open(os.path.join(self.kok, "onbellek-listesi.json"), "w") as f:
            json.dump({"files": ["./", "lessons/%s/egitmen.json" % DERS]}, f)
        self.assertTrue(ds.yerlesik_mi(DERS))
        self.assertEqual(ds.depolama()["arsiv_adaylari"], [])
        with self.assertRaises(ValueError):
            ds.arsivle(DERS, cikis=self.arsiv)

    def test_soru_bilgisi(self):
        k = os.path.join(self.kok, "lessons", DERS)
        b = ds.soru_bilgisi(k, {"soru": "S1"})
        self.assertEqual(b["soru"], EGITMEN["soruBankasi"][0]["metin"])
        self.assertEqual(b["ornek_cevap"], "Papil nekrozu, ağrı, kanama.")
        v = ds.soru_bilgisi(k, {"vaka": "v1", "dugum": "tani", "soru": "tani"})
        self.assertEqual((v["soru"], v["dogru"], v["vaka_ozeti"]), ("En olası tanı hangisi?", [0], "Üç gündür diş etim kanıyor"))
        self.assertEqual(ds.soru_bilgisi(k, {"soru": "Bilinmeyen kısa soru"})["soru"], "Bilinmeyen kısa soru")

    def test_tamamlama_raporu_ve_kartlar(self):
        kimlik = self.kayit_ac()
        r = ds.tamamlama_raporu(kimlik, DERS, ogrenci_notu="Apseyi tekrar okuyacağım.")
        self.assertEqual(r["kart_sayisi"], 2)
        with open(r["dosya"], encoding="utf-8") as f:
            md = f.read()
        for parca in ("# Ders tamamlama raporu: Akut periodontal lezyonlar", "2 oturum, 2026-11-01 – 2026-11-03",
                      "toplam 1 saat 15 dakika", "## Zorlandığın konular", "H2 Apseyi ayırt eder",
                      "Açık kalan yanılgılar: Y1", "kötü sonuç", "Ateş olur mu?", "Apseyi tekrar okuyacağım.",
                      "Nekrotizan gingivitisin üç temel bulgusu nedir?"):
            self.assertIn(parca, md)
        k, _ = ds.depo().yukle(kimlik, DERS)
        self.assertTrue(k["tamamlandi"])
        kartlar = ds.kartlari_oku(kimlik)["kartlar"][DERS]
        self.assertEqual({x["soru"] for x in kartlar}, {"En olası tanı hangisi?", EGITMEN["soruBankasi"][0]["metin"]})
        self.assertLess(len(json.dumps(kartlar, ensure_ascii=False)), 3000)  # küçük kalır
        # Kart dosyası ders kaydı sanılmaz
        self.assertEqual(ds.depo().bilgi(kimlik)["dersler"], [DERS])
        # Zamanı gelmeden listede yok, gelince var
        self.assertEqual(ds.zamani_gelen_kartlar(kimlik), [])
        self.assertEqual(len(ds.zamani_gelen_kartlar(kimlik, "2099-01-01")), 2)
        # Tekrar düzeni: doğru → üst kutu, yanlış → 1. kutu; 4. kutuda doğru → öğrenildi
        kid = kartlar[0]["id"]
        self.assertEqual(ds.kart_sonucu(kimlik, DERS, kid, True)["kutu"], 2)
        self.assertEqual(ds.kart_sonucu(kimlik, DERS, kid, False)["kutu"], 1)
        for _ in range(3):
            ds.kart_sonucu(kimlik, DERS, kid, True)
        self.assertTrue(ds.kart_sonucu(kimlik, DERS, kid, True)["ogrenildi"])
        self.assertEqual(len(ds.zamani_gelen_kartlar(kimlik, "2099-01-01")), 1)
        with self.assertRaises(ValueError):
            ds.kart_sonucu(kimlik, DERS, "yok", True)
        # Rapor yeniden yazılınca kartın tekrar düzeni korunur
        ds.tamamlama_raporu(kimlik, DERS)
        self.assertTrue(next(x for x in ds.kartlari_oku(kimlik)["kartlar"][DERS] if x["id"] == kid)["ogrenildi"])

    def test_en_cok_on_kart(self):
        dp = ds.depo()
        kimlik = dp.kimlik_olustur("Can", "9")
        cevaplar = [{"soru": "Soru %d?" % i, "hedef": "H1", "puan": 0, "en_yuksek": 1, "ilk_deneme": True} for i in range(15)]
        dp.yaz(kimlik, DERS, {"ogrenci": "Can", "ders": DERS, "hedefler": {}, "yanilgilar": {}, "cevaplar": cevaplar,
                              "oturumlar": []})
        self.assertEqual(ds.tamamlama_raporu(kimlik, DERS)["kart_sayisi"], 10)

    def test_arsivle_ve_geri_yukle(self):
        kimlik = self.kayit_ac()
        once = ds.depolama()
        r = ds.arsivle(DERS, cikis=self.arsiv)
        self.assertTrue(os.path.exists(r["dosya"]))
        self.assertGreater(r["acilan_yer"], 5000)
        self.assertTrue(any("ses" in u for u in r["uyarilar"]))
        with zipfile.ZipFile(r["dosya"]) as z:
            adlar = set(z.namelist())
            m = json.loads(z.read("arsiv.json"))
        self.assertIn("ders/%s/egitmen.json" % DERS, adlar)
        self.assertIn("kayitlar/%s/%s.json" % (kimlik, DERS), adlar)
        self.assertIn("kayitlar/%s/raporlar/%s_tamamlama.md" % (kimlik, DERS), adlar)
        self.assertIn("makaleler/durum.json", adlar)
        self.assertFalse([a for a in adlar if "makale-metin" in a or "/audio/" in a or a.endswith(".pdf")])
        self.assertEqual(m["pdfler"], [os.path.basename(self.pdf)])
        # Silinenler ve kalanlar
        self.assertFalse(os.path.exists(os.path.join(self.kok, "lessons", DERS)))
        with open(os.path.join(self.kok, "lessons", "katalog.json"), encoding="utf-8") as f:
            self.assertNotIn(DERS, f.read())
        self.assertEqual(ds.dizin_payi(DERS), 0)
        self.assertFalse(os.path.exists(mb.durum_yolu(DERS)))
        self.assertTrue(os.path.exists(self.pdf), "PDF silinmemeli")
        self.assertTrue(os.path.exists(ds.depo().kayit_yolu(kimlik, DERS)), "kayıt silinmemeli")
        sonra = ds.depolama()
        self.assertEqual(sonra["dersler"], [])
        self.assertLess(sonra["toplam_bayt"], once["toplam_bayt"])
        self.assertEqual([a["ders"] for a in sonra["arsiv"]], [DERS])
        self.assertTrue(sonra["arsiv"][0]["dosya_var"])
        # Tekrar kartları arşivin dışında kalır
        kartlar = ds.zamani_gelen_kartlar(kimlik, "2099-01-01")
        self.assertEqual(len(kartlar), 2)
        self.assertTrue(all(k["ders_arsivde"] for k in kartlar))

        # Geri yükleme: kayıt silinmiş olsun (yeni bilgisayar gibi)
        os.remove(ds.depo().kayit_yolu(kimlik, DERS))
        g = ds.geri_yukle(r["dosya"], makale_ara=False)
        self.assertEqual(g["kayit_geri"], [kimlik])
        self.assertTrue(os.path.exists(os.path.join(self.kok, "lessons", DERS, "egitmen.json")))
        with open(os.path.join(self.kok, "lessons", "katalog.json"), encoding="utf-8") as f:
            self.assertIn(DERS, f.read())
        k, _ = ds.depo().yukle(kimlik, DERS)
        self.assertEqual(len(k["cevaplar"]), 4)
        self.assertEqual(ds.arsiv_listesi(), [])
        self.assertTrue(os.path.exists(mb.durum_yolu(DERS)))
        if PYPDF:
            self.assertEqual(mb.ozet(DERS)["makaleler"][0]["durum"], "hazir")
            self.assertGreater(ds.dizin_payi(DERS), 0)

    def test_geri_yuklemede_yeni_kayit_korunur(self):
        kimlik = self.kayit_ac()
        r = ds.arsivle(DERS, cikis=self.arsiv)
        dp = ds.depo()
        k, _ = dp.yukle(kimlik, DERS)
        k["cevaplar"].append({"soru": "yeni", "puan": 1, "en_yuksek": 1})
        dp.yaz(kimlik, DERS, k)  # arşivden sonra çalışılmış
        g = ds.geri_yukle(r["dosya"], makale_ara=False)
        self.assertEqual(g["kayit_korundu"], [kimlik])
        ds.arsivle(DERS, cikis=self.arsiv)
        self.assertEqual(ds.geri_yukle(ds.arsiv_listesi()[0]["dosya"], makale_ara=False)["kayit_ayni"], [kimlik])
        self.assertEqual(len(dp.yukle(kimlik, DERS)[0]["cevaplar"]), 5)

    def test_gecersiz_arsiv(self):
        y = os.path.join(self.tmp.name, "x.zip")
        with zipfile.ZipFile(y, "w") as z:
            z.writestr(DERS + "/egitmen.json", "{}")
        with self.assertRaises(ValueError):
            ds.geri_yukle(y)
        with zipfile.ZipFile(y, "w") as z:
            z.writestr("arsiv.json", json.dumps({"ders": DERS}))
            z.writestr("../kotu.txt", "x")
        with self.assertRaises(ValueError):
            ds.geri_yukle(y)


if __name__ == "__main__":
    unittest.main()
