"""Windows kurulumu: uygun Python (3.10–3.13) seçimi ve gerekirse KlinikKoç'un kendi Python'unu indirmesi.
Betik Windows'ta denenir; bu testler yalnız metnin bozulmadığını ve indirilen Python'un korunduğunu denetler.
Çalıştırma:  python -m unittest discover -s tools/testler -v
"""
import os
import sys
import unittest

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(KOK, "tools"))


def _oku(ad):
    with open(os.path.join(KOK, ad), "rb") as f:
        return f.read()


class KurulumPython(unittest.TestCase):
    def setUp(self):
        self.kur = _oku("KUR-Windows.bat").decode("ascii")

    def test_satir_sonlari_ve_ascii(self):
        for ad in ("KUR-Windows.bat", "BASLAT-Windows.bat"):
            ham = _oku(ad)
            ham.decode("ascii")  # cmd UTF-8 olmayan harfte bozulur
            self.assertNotIn(b"\n", ham.replace(b"\r\n", b""), ad + ": yalnız CRLF")

    def test_once_bilgisayardaki_uygun_python(self):
        k = self.kur
        self.assertIn("for %%v in (3.13 3.12 3.11 3.10)", k)
        self.assertLess(k.index("for %%v in (3.13 3.12 3.11 3.10)"), k.index("Invoke-WebRequest"))
        self.assertIn("(3, 10) <= sys.version_info[:2] <= (3, 13)", k)
        self.assertLess(k.index("set \"PY=python\")"), k.index("Invoke-WebRequest"))

    def test_indirme_sabit_surum_ve_sisteme_dokunmaz(self):
        k = self.kur
        self.assertIn("astral-sh/uv/releases/download/0.9.0/", k)
        self.assertNotIn("latest", k)
        self.assertNotIn("| iex", k)
        self.assertIn('--install-dir "%KOK%.python" --no-bin --no-registry', k)

    def test_alt_yordam_ana_akistan_ayri(self):
        k = self.kur
        self.assertIn("call :python_bul", k)
        self.assertLess(k.index("exit /b 0\r\n\r\n:python_bul"), len(k))
        # indirme başarısız olursa eski "3.12 kurun" mesajına düşer
        self.assertIn("if not defined PY (", k)
        self.assertIn("python.org/downloads", k)

    def test_secilen_python_kaydedilir_ve_baslat_kullanir(self):
        self.assertIn('> "%KOK%.python\\secilen.txt"', self.kur)
        b = _oku("BASLAT-Windows.bat").decode("ascii")
        self.assertIn('set /p PYYOL=<".python\\secilen.txt"', b)
        self.assertIn('if defined PYYOL if exist "%PYYOL%" set PY="%PYYOL%"', b)

    def test_surum_araligi_pocket_ile_ayni(self):
        import pocket_ses
        (a1, a2), (u1, u2) = pocket_ses.UYGUN
        surumler = " ".join("%d.%d" % (a1, n) for n in range(u2, a2 - 1, -1))
        self.assertIn("for %%%%v in (%s)" % surumler, self.kur)
        self.assertIn("(%d, %d) <= sys.version_info[:2] <= (%d, %d)" % (a1, a2, u1, u2), self.kur)

    def test_python_klasoru_korunur(self):
        import eski_surumler
        import surum
        import yayin_denetimi
        self.assertIn(".python/", surum.KORUNAN)
        self.assertIn(".python", eski_surumler.YEDEGE_GIRMEZ)
        self.assertIn(".python", eski_surumler.ATLA)
        self.assertIn(".python/", yayin_denetimi.YASAK_KLASORLER)
        with open(os.path.join(KOK, ".gitignore"), encoding="utf-8") as f:
            self.assertIn(".python/", f.read().split())


if __name__ == "__main__":
    unittest.main()
