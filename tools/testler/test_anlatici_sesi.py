"""⚙ Anlatıcı sesi (Kadın 3 / Erkek 2) testleri: tahtanın seçimi sunucuya geçer, yalnız izinli sesler kabul edilir,
ses/ses-ayari.json değişmez, Erkek 2'nin düzeyi eşitlenir.
Çalıştırma:  python -m unittest discover -s tools/testler -v
"""
import io
import os
import struct
import sys
import unittest
import wave

os.environ.setdefault("KLINIK_KOC_ANLAM_KURMA", "1")
KOK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(KOK, "tools"))

import pocket_ses  # noqa: E402
import sunucu  # noqa: E402


def _wav(ornekler, oran=24000):
    t = io.BytesIO()
    with wave.open(t, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(oran)
        w.writeframes(struct.pack("<%dh" % len(ornekler), *ornekler))
    return t.getvalue()


def _ornekler(wav):
    with wave.open(io.BytesIO(wav), "rb") as g:
        ham = g.readframes(g.getnframes())
        return list(struct.unpack("<%dh" % (len(ham) // 2), ham)), g.getframerate()


class AnlaticiSesi(unittest.TestCase):
    def test_izinli_sesler(self):
        self.assertEqual(set(sunucu.ANLATICI_SESLER), {"female_3", "male_2"})
        self.assertEqual(sunucu.ANLATICI_SESLER["female_3"], 1.0)

    def test_duzey_olcekler(self):
        wav = _wav([1000, -1000, 32767, -32768, 0])
        self.assertIs(sunucu.wav_duzey(wav, 1.0), wav)
        orn, oran = _ornekler(sunucu.wav_duzey(wav, 0.7))
        self.assertEqual(oran, 24000)
        self.assertEqual(orn, [700, -700, 22936, -22937, 0])

    def _seslendir_dene(self, istek_sesi):
        """Pocket hazırmış gibi davranır; işçiye giden sesi ve dönen wav'ı yakalar."""
        canli = sunucu.Canli()
        giden = {}

        class SahtePocket:
            durum = "hazır"

            def wav(self, metin, ses="female_3", tohum=1, bekle=0.0):
                giden["ses"] = ses
                return _wav([10000])

        class SahteMod:
            plain = staticmethod(lambda m: m)
            pronounce = staticmethod(lambda m, s: m)
            load_dictionary = staticmethod(lambda: {})

        eski_pocket, eski_ayar = sunucu.POCKET, pocket_ses.ayar
        sunucu.POCKET = SahtePocket()
        pocket_ses.ayar = lambda: {"motor": "pocket", "ses": "female_3", "tohum": 1}
        canli._mod = lambda: SahteMod
        try:
            wav = canli.seslendir("Merhaba.", istek_sesi)
        finally:
            sunucu.POCKET, pocket_ses.ayar = eski_pocket, eski_ayar
        return giden.get("ses"), _ornekler(wav)[0][0]

    def test_secim_gecer_ve_duzey_esitlenir(self):
        self.assertEqual(self._seslendir_dene("male_2"), ("male_2", 7000))

    def test_secim_yoksa_ayar_dosyasi(self):
        self.assertEqual(self._seslendir_dene(None), ("female_3", 10000))

    def test_izinsiz_ses_kabul_edilmez(self):
        self.assertEqual(self._seslendir_dene("male_1")[0], "female_3")
        self.assertEqual(self._seslendir_dene("../x")[0], "female_3")

    def test_ses_bilgisi_ayar_sesini_bildirir(self):
        b = sunucu.Canli().ses_bilgisi()
        self.assertIn("ses", b)
        self.assertIn("motor", b)

    def test_tahta_secici_var(self):
        with open(os.path.join(KOK, "canli.html"), encoding="utf-8") as f:
            html = f.read()
        self.assertIn('value="female_3" id="sesKadin"', html)
        self.assertIn('value="male_2" id="sesErkek"', html)
        with open(os.path.join(KOK, "js", "canli.js"), encoding="utf-8") as f:
            js = f.read()
        self.assertIn("{ metin, ses }", js)


if __name__ == "__main__":
    unittest.main()
