"""Tarayıcı JS'inin testleri (tools/testler/js/*.test.mjs) Node ile koşulur.

Böylece tek komut yeter:  python -m unittest discover -s tools/testler -v
Node yoksa ya da eskiyse (zip okuyucu Node 20.12+ ister) test atlanır.
"""
import glob
import os
import shutil
import subprocess
import unittest

KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class JsTestleri(unittest.TestCase):
    def test_node_testleri(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node kurulu değil")
        surum = subprocess.run([node, "--version"], capture_output=True, text=True).stdout.strip().lstrip("v")
        buyuk, kucuk = (int(x) for x in surum.split(".")[:2])
        if (buyuk, kucuk) < (20, 12):
            self.skipTest("Node %s eski (20.12+ gerekir)" % surum)
        dosyalar = sorted(glob.glob(os.path.join(KOK, "tools", "testler", "js", "*.test.mjs")))
        self.assertTrue(dosyalar, "JS testi bulunamadı")
        r = subprocess.run([node, "--test"] + dosyalar, capture_output=True, text=True, cwd=KOK)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
