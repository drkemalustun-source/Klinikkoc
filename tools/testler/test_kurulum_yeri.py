"""Yeni kurulumun yeri (C:\\KlinikKoc) kararları: yalnız yeni indirilen klasör kopyalanır, kurulu olan yerinde kalır,
hedefte KlinikKoç varsa oradaki kullanılır, hedefte başka bir şey varsa dokunulmaz, Mac/Linux'ta değişiklik yok.
Çalıştırma:  python -m unittest discover -s tools/testler -v
"""
import os
import sys
import tempfile
import unittest

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(KOK, "tools"))

import kurulum_yeri as ky  # noqa: E402


def _indirilmis(kok):
    """Yeni indirilmiş (hiç kurulmamış) bir KlinikKoç klasörü."""
    os.makedirs(os.path.join(kok, "tools"))
    os.makedirs(os.path.join(kok, "lessons"))
    os.makedirs(os.path.join(kok, ".python", "cpython-3.12.11-windows-x86_64-none"))
    for ad, icerik in (("tools/tahta-mcp.py", "# imza"), ("SURUM", "4.1.2"), ("KUR-Windows.bat", "@echo off"),
                       ("lessons/katalog.json", "[]"), (".python/cpython-3.12.11-windows-x86_64-none/python.exe", "x")):
        with open(os.path.join(kok, ad), "w", encoding="utf-8") as f:
            f.write(icerik)
    return kok


class KurulumYeri(unittest.TestCase):
    def setUp(self):
        self.gecici = tempfile.TemporaryDirectory()
        self.addCleanup(self.gecici.cleanup)
        self.indirilen = _indirilmis(os.path.join(self.gecici.name, "Masaustu", "Klinikkoc-v4-ogrenci"))
        self.hedef = os.path.join(self.gecici.name, "KlinikKoc")

    def karar(self, **k):
        return ky.karar(self.indirilen, self.hedef, isletim=k.get("isletim", "nt"), claude=k.get("claude", False))

    def test_yeni_indirilen_tasinir(self):
        self.assertEqual(self.karar(), ("TASI", self.hedef))

    def test_mac_ve_linux_degismez(self):
        self.assertEqual(self.karar(isletim="posix"), ("BURADA", None))

    def test_zaten_hedefte(self):
        self.assertEqual(ky.karar(self.hedef, self.hedef, isletim="nt", claude=False), ("BURADA", None))

    def test_var_olan_kurulum_yerinde_kalir(self):
        for iz in (".ses-ortami", os.path.join(".python", "secilen.txt"), os.path.join("tools", ".sesler"), "ozel"):
            with self.subTest(iz=iz):
                yol = os.path.join(self.indirilen, iz)
                if iz.endswith(".txt"):
                    with open(yol, "w") as f:
                        f.write("C:\\py\\python.exe")
                else:
                    os.makedirs(yol)
                self.assertEqual(self.karar(), ("BURADA", None))
                os.remove(yol) if iz.endswith(".txt") else os.rmdir(yol)

    def test_kurulu_ders_varsa_yerinde(self):
        os.makedirs(os.path.join(self.indirilen, "lessons", "ozel-endo-irrigasyon"))
        self.assertEqual(self.karar(), ("BURADA", None))

    def test_claude_bu_klasoru_kullaniyorsa_yerinde(self):
        self.assertEqual(self.karar(claude=True), ("BURADA", None))

    def test_hedefte_klinikkoc_varsa_oradaki(self):
        _indirilmis(self.hedef)
        self.assertEqual(self.karar(), ("ORADA", self.hedef))

    def test_hedefte_baska_sey_varsa_dokunulmaz(self):
        os.makedirs(self.hedef)
        with open(os.path.join(self.hedef, "baska.txt"), "w") as f:
            f.write("x")
        self.assertEqual(self.karar(), ("BURADA", None))

    def test_hedef_bos_klasorse_tasinir(self):
        os.makedirs(self.hedef)
        self.assertEqual(self.karar(), ("TASI", self.hedef))

    def test_kopyala(self):
        os.makedirs(os.path.join(self.indirilen, "__pycache__"))
        os.makedirs(os.path.join(self.indirilen, "tools", ".sesler"))
        ky.kopyala(self.indirilen, self.hedef)
        self.assertTrue(os.path.isfile(os.path.join(self.hedef, "tools", "tahta-mcp.py")))
        self.assertTrue(os.path.isfile(os.path.join(self.hedef, ".python", "cpython-3.12.11-windows-x86_64-none",
                                                    "python.exe")), "indirilen Python da taşınır")
        self.assertFalse(os.path.exists(os.path.join(self.hedef, "__pycache__")))
        self.assertFalse(os.path.exists(os.path.join(self.hedef, "tools", ".sesler")))
        self.assertTrue(os.path.isfile(os.path.join(self.indirilen, "SURUM")), "kaynak yerinde kalır")
        # kopyadan sonra (yeni indirilmiş) kaynak yeniden çalıştırılırsa hedefteki kullanılır
        os.rmdir(os.path.join(self.indirilen, "tools", ".sesler"))
        self.assertEqual(self.karar(), ("ORADA", self.hedef))

    def test_dolu_hedefe_kopyalanmaz(self):
        os.makedirs(self.hedef)
        with open(os.path.join(self.hedef, "baska.txt"), "w") as f:
            f.write("x")
        with self.assertRaises(RuntimeError):
            ky.kopyala(self.indirilen, self.hedef)
        self.assertEqual(os.listdir(self.hedef), ["baska.txt"])

    def test_kur_betigi_karari_python_kaydindan_once_sorar(self):
        with open(os.path.join(KOK, "KUR-Windows.bat"), encoding="ascii") as f:
            k = f.read()
        self.assertLess(k.index("kurulum_yeri.py --karar"), k.index('> "%KOK%.python\\secilen.txt"'))
        self.assertLess(k.index("call :python_bul"), k.index("kurulum_yeri.py --karar"))
        self.assertIn('call "%YERHEDEF%\\KUR-Windows.bat"', k)


if __name__ == "__main__":
    unittest.main()
