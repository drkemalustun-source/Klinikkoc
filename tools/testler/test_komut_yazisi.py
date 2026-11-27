"""Kullanıcıya gösterilen komutlar programın kendi Python'unu ve tam yolları kullanır (Ali'nin Öneri 1, 27 Kasım 2026).
Çalıştırma:  python -m unittest discover -s tools/testler -v
"""
import os
import re
import sys
import unittest

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(KOK, "tools"))
os.environ.setdefault("KLINIK_KOC_ANLAM_KURMA", "1")

import komut  # noqa: E402


class KomutYazisi(unittest.TestCase):
    def test_kendi_python_ve_tam_yol(self):
        y = komut.yazi("ses-uret.py", "--kur-pocket")
        self.assertIn(sys.executable, y)
        self.assertIn(os.path.join(KOK, "tools", "ses-uret.py"), y)
        self.assertTrue(y.endswith(" --kur-pocket"))

    def test_duyu_komutu(self):
        import sunucu
        self.assertIn(sys.executable, sunucu.KUR_KOMUTU)
        self.assertIn(os.path.join(KOK, "tools", "sunucu.py"), sunucu.KUR_KOMUTU)

    def test_kisa_komut_kalmadi(self):
        """Çalışırken gösterilen iletilerde kısa 'python tools/...' kalmasın (belge dizeleri ve yorumlar hariç)."""
        desen = re.compile(r'"[^"\n]*\b(?:python3?|py) tools[\\/]')
        for ad in ("sunucu.py", "pocket_ses.py", "bilgi_bankasi.py", "tahta-mcp.py", "claude_ayari.py"):
            with open(os.path.join(KOK, "tools", ad), encoding="utf-8") as f:
                satirlar = f.read().split("\n")
            belge = False
            for i, satir in enumerate(satirlar, 1):
                if satir.count('"""') % 2:
                    belge = not belge
                    continue
                if belge or satir.lstrip().startswith("#"):
                    continue
                self.assertIsNone(desen.search(satir), "%s:%d %s" % (ad, i, satir.strip()))


if __name__ == "__main__":
    unittest.main()
