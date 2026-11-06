"""KlinikKoç temel testleri. Çalıştırma:  python -m unittest discover -s tools/testler -v

Yalnız Python'un kendi kitaplığını kullanır; anlam araması sahte bir modelle denenir.
"""
import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(KOK, "tools"))

import bilgi_bankasi  # noqa: E402
import karne  # noqa: E402
import vaka_denetle  # noqa: E402

ORNEK_VAKA = os.path.join(KOK, "lessons", "peri-implantitis-cerrahi", "vakalar", "ornek-implant-kanama.json")


class SahteModel:
    """Harf üçlülerinden vektör: anlamı değil, yazım benzerliğini yakalar. Karma aramanın akışını sınamaya yeter."""
    hazir = True
    ad = "sahte"
    BOYUT = 64

    def _v(self, m):
        v = [0.0] * self.BOYUT
        m = bilgi_bankasi.kucuk(m)
        for i in range(len(m) - 2):
            v[hash(m[i:i + 3]) % self.BOYUT] += 1
        n = sum(x * x for x in v) ** 0.5 or 1
        return [x / n for x in v]

    def vektorler(self, metinler):
        return [self._v(m) for m in metinler]

    def sorgu_vektoru(self, s):
        return self._v(s)


class BilgiBankasi(unittest.TestCase):
    def setUp(self):
        self.gecici = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.gecici.name, "bilgi.sqlite")

    def tearDown(self):
        self.gecici.cleanup()

    def test_turkce_kucuk_harf_ve_sorgu(self):
        self.assertEqual(bilgi_bankasi.kucuk("IŞIK İltihabı"), "ışık iltihabı")
        self.assertEqual(bilgi_bankasi.fts_sorgusu("İltihabı"), '"iltih"*')
        self.assertEqual(bilgi_bankasi.fts_sorgusu("a"), "")

    def test_parcalama_ortusur(self):
        p = bilgi_bankasi.parcala(" ".join(str(i) for i in range(250)), n=100, ortusme=20)
        self.assertEqual(len(p), 3)
        self.assertTrue(p[1].startswith("80 "))

    def test_sozcuk_aramasi_ve_kaynak(self):
        bilgi_bankasi.dizinle(yol=self.db, sessiz=True)
        r = bilgi_bankasi.ara("keratinize mukoza", yol=self.db, k=5)
        self.assertTrue(r)
        self.assertTrue(any("eratinize" in x["metin"] for x in r))
        self.assertEqual(r[0]["yontem"], "sözcük")

    def test_suzgec_ders_ve_tur(self):
        bilgi_bankasi.dizinle(yol=self.db, sessiz=True)
        r = bilgi_bankasi.ara("implant", ders="peri-implantitis-cerrahi", tur="vaka", yol=self.db)
        self.assertTrue(r)
        self.assertTrue(all(x["tur"] == "vaka" and x["ders"] == "peri-implantitis-cerrahi" for x in r))

    def test_karma_arama_anlam_ile(self):
        m = SahteModel()
        bilgi_bankasi.dizinle(model=m, yol=self.db, sessiz=True)
        r = bilgi_bankasi.ara("destekleyici bakıma uyum", model=m, yol=self.db, k=5)
        self.assertTrue(any("anlam" in x["yontem"] for x in r))
        self.assertTrue(any(set(x["yontem"].split("+")) == {"sözcük", "anlam"} for x in r))

    def test_degismeyen_ders_atlanir(self):
        bilgi_bankasi.dizinle(yol=self.db, sessiz=True)
        r = bilgi_bankasi.dizinle(yol=self.db, sessiz=True)
        self.assertTrue(all(x["durum"] == "güncel" for x in r))


class VakaDenetimi(unittest.TestCase):
    def kart(self, degistir):
        v = json.load(open(ORNEK_VAKA, encoding="utf-8"))
        degistir(v)
        klasor = tempfile.mkdtemp()
        yol = os.path.join(klasor, v["id"] + ".json")
        json.dump(v, open(yol, "w", encoding="utf-8"), ensure_ascii=False)
        return vaka_denetle.denetle(yol)

    def test_ornek_vaka_gecer(self):
        H, U, _ = vaka_denetle.denetle(ORNEK_VAKA)
        self.assertEqual(H, [])

    def test_gercek_vakada_anonimlik_zorunlu(self):
        H, _, _ = self.kart(lambda v: v.update(kurgusal=False))
        self.assertTrue(any("anonimlik" in h for h in H))

    def test_tam_yas_ve_tarih_yakalanir(self):
        def d(v):
            v["kurgusal"] = False
            v["anonimlik"] = {"kimliksizlestirildi": True, "egitim_onayi": True, "denetleyen": "KÜ", "tarih": "2026-11-06"}
            v["hasta"]["yas_araligi"] = "54"
            v["basvuru"]["oyku"] = "03.05.2025 tarihinde başvurdu."
        H, _, _ = self.kart(d)
        self.assertTrue(any("yas_araligi" in h for h in H))
        self.assertTrue(any("tarih" in h for h in H))

    def test_kopuk_baglanti_ve_sonsuz_yol(self):
        def d(v):
            v["dugumler"][1]["secenekler"][1]["sonraki"] = "olmayan"
        H, _, _ = self.kart(d)
        self.assertTrue(any("olmayan düğüme" in h for h in H))
        self.assertTrue(any("sona varılamıyor" in h for h in H))

    def test_acik_uclu_rubrik_ister(self):
        H, _, _ = self.kart(lambda v: v["dugumler"][2].pop("rubrik"))
        self.assertTrue(any("rubrik" in h for h in H))


class Karne(unittest.TestCase):
    def test_hesap(self):
        kayit = {"ogrenci": "Deneme", "ders": "x", "hedefler": {}, "cevaplar": [
            {"soru": "a", "hedef": "H1", "bloom": "hatirla", "puan": 1, "en_yuksek": 1, "ilk_deneme": True},
            {"soru": "b", "hedef": "H1", "bloom": "hatirla", "puan": 1, "en_yuksek": 1, "ilk_deneme": True},
            {"soru": "c", "hedef": "H2", "bloom": "cozumle", "puan": 1, "en_yuksek": 4, "ilk_deneme": True,
             "eksik_olcutler": ["gerekçe"]},
            {"soru": "d", "hedef": "H2", "bloom": "cozumle", "puan": 0, "en_yuksek": 1, "tehlikeli": True, "vaka": "v1", "dugum": "n"}]}
        hed = [{"id": "H1", "baslik": "bir", "bloom": "hatirla"}, {"id": "H2", "baslik": "iki", "bloom": "cozumle"},
               {"id": "H3", "baslik": "üç"}]
        k = karne.hesapla(kayit, hed, "2026-11-06")
        self.assertEqual(k["guclu"], ["H1"])
        self.assertEqual(k["gelistirilecek"], ["H2"])
        self.assertEqual(k["yoklanmayan"], ["H3"])
        self.assertEqual([b["duzey"] for b in k["bloom"]], ["hatirla", "cozumle"])
        self.assertAlmostEqual(k["bloom"][1]["oran"], 0.2)
        self.assertEqual(len(k["tehlikeli_secimler"]), 1)
        self.assertEqual(k["sorular"][0]["gucluk"], "zor")
        md = karne.markdown(k, "Ders", "2026-11-06")
        self.assertIn("Çözümle", md)
        self.assertIn("zarar verebilecek", md)


class McpSunucusu(unittest.TestCase):
    def test_araclar_ve_karne(self):
        with tempfile.TemporaryDirectory() as d:
            ortam = dict(os.environ, KLINIK_KOC_KAYIT=os.path.join(d, "kayit"), KLINIK_KOC_DIZIN=os.path.join(d, "b.sqlite"))
            p = subprocess.Popen([sys.executable, os.path.join(KOK, "tools", "tahta-mcp.py")], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, env=ortam)
            no = [0]

            def cagir(yontem, params=None):
                no[0] += 1
                p.stdin.write((json.dumps({"jsonrpc": "2.0", "id": no[0], "method": yontem, "params": params or {}}) + "\n").encode())
                p.stdin.flush()
                return json.loads(p.stdout.readline())["result"]

            def arac(ad, **arg):
                r = cagir("tools/call", {"name": ad, "arguments": arg})
                self.assertFalse(r.get("isError"), r)
                return json.loads(r["content"][-1]["text"])

            try:
                self.assertEqual(cagir("initialize")["serverInfo"]["name"], "klinik-koc")
                adlar = {t["name"] for t in cagir("tools/list")["tools"]}
                self.assertTrue({"bilgi_ara", "vakalar", "vaka_oku", "karne", "kayit_yaz"} <= adlar)
                self.assertTrue(arac("bilgi_ara", sorgu="süpürasyon", k=3)["sonuclar"])
                self.assertEqual(arac("vakalar", ders="peri-implantitis-cerrahi")["vakalar"][0]["vaka"], "ornek-implant-kanama")
                self.assertIn("talimat", arac("vaka_oku", ders="peri-implantitis-cerrahi", vaka="ornek-implant-kanama"))
                arac("kayit_yaz", ogrenci="Test Öğrenci", ders="peri-implantitis-cerrahi", cevaplar=[
                    {"soru": "Tanı", "vaka": "ornek-implant-kanama", "dugum": "tani", "hedef": "H2.b", "bloom": "uygula",
                     "tur": "vaka_karar", "puan": 1, "en_yuksek": 1, "ilk_deneme": True}])
                k = arac("karne", ogrenci="Test Öğrenci", ders="peri-implantitis-cerrahi", yaz=True)
                self.assertEqual(k["karne"]["cevap_sayisi"], 1)
                self.assertTrue(os.path.exists(os.path.join(d, "kayit", "test-ogrenci", "karneler")))
            finally:
                p.stdin.close()
                p.wait(timeout=10)


class YayinDenetimi(unittest.TestCase):
    def test_depo_temiz(self):
        r = subprocess.run([sys.executable, os.path.join(KOK, "tools", "yayin_denetimi.py")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()
