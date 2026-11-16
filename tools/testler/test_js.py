"""Tarayıcı JS'inin testleri. Çalıştırma:  python -m unittest discover -s tools/testler -v

- JsTestleri: tools/testler/js/*.test.mjs dosyalarını Node ile koşar (tek komut yetsin diye buradan).
- PaketEsligi: tarayıcıdaki ders paketi kurucusu (js/yerel/) ile tools/ders_paketi.py aynı zip'e aynı sonucu verir.

Node yoksa ya da eskiyse (zip okuyucu Node 20.12+ ister) testler atlanır.
"""
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(KOK, "tools"))

import ders_paketi  # noqa: E402

JS = os.path.join(KOK, "tools", "testler", "js")


def node_bul():
    """(node yolu, None) ya da (None, atlama nedeni)."""
    node = shutil.which("node")
    if not node:
        return None, "Node kurulu değil"
    surum = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip().lstrip("v")
    if tuple(int(x) for x in surum.split(".")[:2]) < (20, 12):
        return None, "Node %s eski (20.12+ gerekir)" % surum
    return node, None


class NodeTesti(unittest.TestCase):
    def setUp(self):
        self.node, neden = node_bul()
        if not self.node:
            self.skipTest(neden)


class JsTestleri(NodeTesti):
    def test_node_testleri(self):
        dosyalar = sorted(os.path.join(JS, a) for a in os.listdir(JS) if a.endswith(".test.mjs"))
        self.assertTrue(dosyalar, "JS testi bulunamadı")
        r = subprocess.run([self.node, "--test"] + dosyalar, capture_output=True, text=True, cwd=KOK)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class PaketEsligi(NodeTesti):
    """Aynı ders paketi Python'da (tools/ders_paketi.py) ve tarayıcı kodunda (js/yerel/) aynı biçimde kurulur."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.kok = os.path.join(self.tmp.name, "program")
        os.makedirs(os.path.join(self.kok, "lessons"))
        eski = ders_paketi.KOK
        ders_paketi.KOK = self.kok
        self.addCleanup(setattr, ders_paketi, "KOK", eski)

    def js(self, *zipler, uzerine=False):
        komut = [self.node, os.path.join(JS, "paket-kur.mjs")] + (["--uzerine"] if uzerine else []) + list(zipler)
        r = subprocess.run(komut, capture_output=True, text=True, cwd=KOK)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def zip_yap(self, dosyalar, ad="paket.zip"):
        yol = os.path.join(self.tmp.name, ad)
        with zipfile.ZipFile(yol, "w", zipfile.ZIP_DEFLATED) as z:
            for ic, icerik in dosyalar.items():
                z.writestr(ic, icerik)
        return yol

    def kurulu_dosyalar(self, ders):
        """Python'un kurduğu dersin dosyaları: {yol: sha256}. Tarayıcı .js kopyalarını saklamaz."""
        hedef = os.path.join(self.kok, "lessons", ders)
        out = {}
        for kok, _, adlar in os.walk(hedef):
            for ad in adlar:
                yol = os.path.join(kok, ad)
                ic = os.path.relpath(yol, hedef).replace(os.sep, "/")
                if not ic.lower().endswith(".js"):
                    with open(yol, "rb") as f:
                        out[ic] = hashlib.sha256(f.read()).hexdigest()
        return out

    def katalog(self):
        with open(os.path.join(self.kok, "lessons", "katalog.json"), encoding="utf-8") as f:
            return json.load(f)

    def test_ornek_ders_ayni_kurulur(self):
        yol = ders_paketi.paket_olustur(os.path.join(KOK, "ornek-dersler", "peri-implantitis-cerrahi"),
                                        os.path.join(self.tmp.name, "ornek.zip"))
        with zipfile.ZipFile(yol) as z:
            ders, alinacak = ders_paketi.paketi_incele(z)
        py = ders_paketi.yukle(yol)
        j = self.js(yol)
        self.assertNotIn("hata", j)
        self.assertEqual(j["ders"], ders)
        self.assertEqual(j["incelenen"], [ic for _, ic in alinacak])
        self.assertEqual(j["sonuc"], {"ders": py["ders"], "baslik": py["baslik"], "makale": py["makale"]})
        self.assertEqual(j["katalog"], self.katalog())
        beklenen = self.kurulu_dosyalar(ders)
        self.assertGreater(len(beklenen), 10)
        self.assertEqual(j["dosyalar"], beklenen)

    def test_uygun_olmayan_paketler_ayni_iletiyle_reddedilir(self):
        kotuler = [
            {},
            {"../kotu/egitmen.json": "{}"},
            {"a/egitmen.json": "{}", "b/egitmen.json": "{}"},
            {"egitmen.json": "{}"},
            {"a/notlar.txt": "ders dosyası yok"},
            {"kötü ad/ders.json": "{}"},
            {"tanitim/ders.json": "{}"},
            {"a/ders.json": "{}", "a/alt/../../disari.txt": "x"},
        ]
        for dosyalar in kotuler:
            with self.subTest(dosyalar=list(dosyalar)):
                yol = self.zip_yap(dosyalar)
                with zipfile.ZipFile(yol) as z, self.assertRaises(ValueError) as hata:
                    ders_paketi.paketi_incele(z)
                self.assertEqual(self.js(yol).get("hata"), str(hata.exception))

    def test_kurulu_ders_uzerine_yazilmadan_degismez(self):
        yol = self.zip_yap({"d1/ders.json": json.dumps({"title": "Bir"})})
        ders_paketi.yukle(yol)
        with self.assertRaises(FileExistsError) as hata:
            ders_paketi.yukle(yol)
        j = self.js(yol, yol)
        self.assertEqual((j.get("hata"), j.get("kod")), (str(hata.exception), 409))

    def test_guncelleme_eskiyi_siler_videoyu_korur(self):
        v1 = self.zip_yap({"d1/ders.json": json.dumps({"title": "Bir"}), "d1/assets/eski.png": "eski",
                           "d1/videolar/a.mp4": "video", "d1/ders.js": "AT.registerLesson({})"}, "v1.zip")
        v2 = self.zip_yap({"d1/ders.json": json.dumps({"title": "İki", "subtitle": "Alt", "estimatedMinutes": 20}),
                           "d1/assets/yeni.png": "yeni"}, "v2.zip")
        ders_paketi.yukle(v1)
        ders_paketi.yukle(v2, uzerine=True)
        j = self.js(v1, v2, uzerine=True)
        self.assertNotIn("hata", j)
        self.assertEqual(sorted(j["dosyalar"]), ["assets/yeni.png", "ders.json", "videolar/a.mp4"])
        self.assertEqual(j["dosyalar"], self.kurulu_dosyalar("d1"))
        self.assertEqual(j["katalog"], self.katalog())

    def test_boyutu_yanlis_bildirilen_girdi_acilmaz(self):
        # Zip bombası: dizinde 10 bayt diye bildirilen girdi açılınca 200 000 bayt çıkıyor.
        b = io.BytesIO()
        with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("d1/ders.json", "{}")
            z.writestr("d1/buyuk.txt", "a" * 200000)
        veri = bytearray(b.getvalue())
        dizin = veri.rindex(b"PK\x01\x02")          # son girdinin (buyuk.txt) dizin kaydı
        veri[dizin + 24:dizin + 28] = (10).to_bytes(4, "little")
        yol = os.path.join(self.tmp.name, "bomba.zip")
        with open(yol, "wb") as f:
            f.write(veri)
        self.assertEqual(self.js(yol).get("hata"), "Paket bozuk: d1/buyuk.txt")


if __name__ == "__main__":
    unittest.main()
