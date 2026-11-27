"""Şablon canlandırmasının sırası (4.1.2): neden önce, sonuç sonra.

Kemal'in onayı (27 Kasım 2026): plak → iltihap → şişlik → cep → kemik; son anda kısa duruş.
js/anatomi.js içindeki kademeliDurum Node ile denetlenir; Node yoksa test atlanır.
"""
import json
import os
import shutil
import subprocess
import unittest

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BETIK = r"""
global.window = {};
require(process.argv[1]);
const A = window.AT.anatomi;
const K = (s, a, b, t) => A.kademeliDurum(s, A.durum(s, a), A.durum(s, b), t);
console.log(JSON.stringify({
  bas: K('dis', 'gingivitis', 'periodontitis', 0),
  son: K('dis', 'gingivitis', 'periodontitis', 1),
  hedef: A.durum('dis', 'periodontitis'),
  erken: K('dis', 'gingivitis', 'periodontitis', 0.3),
  orta: K('dis', 'gingivitis', 'periodontitis', 0.6),
  durus: K('dis', 'gingivitis', 'periodontitis', 0.93),
  plakErken: K('dis', 'saglikli', 'gingivitis', 0.2),
  iyilesme: K('dis', 'gingivitis', 'saglikli', 0.2),
  cekilme: K('dis', 'saglikli', 'cekilme', 0.3),
  implant: K('implant', 'mukozitis', 'peri-implantitis', 0.5),
  saglikliPlak: A.durum('dis', 'saglikli').plak,
  baskaSablon: A.kademeliDurum('kontur-fasiyal', {x: 0}, {x: 1}, 0.5)
}));
"""


@unittest.skipUnless(shutil.which("node"), "Node yok")
class KademeliCanlandirma(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cikti = subprocess.run(["node", "-e", BETIK, os.path.join(KOK, "js", "anatomi.js")],
                               capture_output=True, text=True, check=True).stdout
        cls.d = json.loads(cikti)

    def test_uclar_degismez(self):
        for k, v in self.d["hedef"].items():
            self.assertAlmostEqual(self.d["son"][k], v, places=6)
        self.assertEqual(self.d["bas"]["cY"], 41)

    def test_once_iltihap_sonra_cep_en_son_kemik(self):
        e, o = self.d["erken"], self.d["orta"]
        self.assertGreater(e["inflam"], 1)          # iltihap başladı
        self.assertEqual(e["sY"], 32)               # cep henüz derinleşmedi
        self.assertEqual(e["cY"], 41)               # kemik yerinde
        self.assertGreater(o["sY"], 40)             # cep derinleşiyor
        cep = (o["sY"] - 32) / (51 - 32)
        kemik = (o["cY"] - 41) / (59.5 - 41)
        self.assertGreater(cep, kemik)              # kemik cepten geride

    def test_son_anda_durus(self):
        for k, v in self.d["hedef"].items():
            self.assertAlmostEqual(self.d["durus"][k], v, places=6)

    def test_plak_iltihaptan_once(self):
        p = self.d["plakErken"]
        self.assertGreater(p["plak"], 0.5)
        self.assertLess(p["inflam"], 0.3)
        self.assertEqual(self.d["saglikliPlak"], 0)
        i = self.d["iyilesme"]                      # tedavide önce plak kalkar
        self.assertLess(i["plak"], 0.5)
        self.assertGreater(i["inflam"], 0.7)

    def test_cekilmede_kenar_atasmanla_birlikte(self):
        c = self.d["cekilme"]
        self.assertEqual(c["mY"], 28)               # şişlik yok: kenar erken kaymaz

    def test_implant_ve_baska_sablonlar(self):
        self.assertIn("crater", self.d["implant"])
        self.assertAlmostEqual(self.d["baskaSablon"]["x"], 0.5)  # bölge/kontur eskisi gibi

    def test_tahta_ve_galeri_kademeli_kullanir(self):
        for ad in ("board.js", "sablon-galerisi.js"):
            with open(os.path.join(KOK, "js", ad), encoding="utf-8") as f:
                self.assertIn("kademeliDurum", f.read(), ad)


if __name__ == "__main__":
    unittest.main()
