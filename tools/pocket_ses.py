"""Tahta sesinin ayarı ve Pocket TTS Türkçe işçisiyle konuşma (yalnız Python'un kendi kitaplığı).

Ayar: ses/ses-ayari.json (motor, ses, tohum, yedek, tarayici_ses). Pocket ayrı bir Python ortamında
(.ses-ortami) çalışır çünkü torch ister; bu modül o ortamdaki tools/pocket-isci.py'yi bir kez başlatır,
model arka planda yüklenir. Hazır olmadan ya da hata verdiğinde çağıran taraf Piper'a döner.

Ses ortamını kurmak (bir kez):  python tools/ses-uret.py --kur-pocket
"""
import base64
import json
import os
import subprocess
import sys
import threading
import time

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AYAR_DOSYASI = os.path.join(KOK, "ses", "ses-ayari.json")
ORTAM = os.path.join(KOK, ".ses-ortami")
VARSAYILAN = {"motor": "piper", "ses": "female_3", "tohum": 1,
              "yedek": "tr_TR-dfki-medium", "tarayici_ses": "tr_TR-ilkiz-medium"}


def ayar():
    a = dict(VARSAYILAN)
    try:
        a.update(json.load(open(AYAR_DOSYASI, encoding="utf-8")))
    except Exception:
        pass
    return a


def ortam_python():
    for p in (os.path.join(ORTAM, "Scripts", "python.exe"), os.path.join(ORTAM, "bin", "python")):
        if os.path.exists(p):
            return p
    return None


class PocketIsci:
    """Tek bir işçi süreci; istekler sırayla gider. durum: 'yükleniyor' | 'hazır' | hata metni."""

    def __init__(self):
        self.surec = None
        self.durum = "başlatılmadı"
        self.hazir = threading.Event()
        self.kilit = threading.Lock()
        self.sayac = 0

    def baslat(self):
        if self.surec is not None:
            return
        py = ortam_python()
        if not py:
            self.durum = "Pocket ses ortamı yok (python tools/ses-uret.py --kur-pocket)"
            self.hazir.set()
            return
        bayrak = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self.durum = "yükleniyor"
        self.surec = subprocess.Popen(
            [py, "-I", os.path.join(KOK, "tools", "pocket-isci.py")], cwd=KOK,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            encoding="utf-8", bufsize=1, creationflags=bayrak)
        threading.Thread(target=self._ilk_yanit, daemon=True).start()

    def _oku(self):
        while True:
            satir = self.surec.stdout.readline()
            if not satir:
                raise RuntimeError("Pocket işçisi kapandı")
            if satir.startswith("@@"):
                return json.loads(satir[2:])

    def _ilk_yanit(self):
        try:
            y = self._oku()
            self.durum = "hazır" if y.get("hazir") else ("Pocket yüklenemedi: " + str(y.get("hata")))
            self.yukleme_sn = y.get("sure")
        except Exception as e:
            self.durum = "Pocket yüklenemedi: %s" % e
        self.hazir.set()

    def wav(self, metin, ses="female_3", tohum=1, bekle=0.0):
        """WAV baytları döner. Model hazır değilse (bekle sn içinde) RuntimeError."""
        self.baslat()
        if not self.hazir.wait(bekle) or self.durum != "hazır":
            raise RuntimeError("Pocket hazır değil: " + self.durum)
        with self.kilit:
            if self.surec.poll() is not None:
                self.durum = "Pocket işçisi kapandı"
                raise RuntimeError(self.durum)
            self.sayac += 1
            try:
                # ensure_ascii: boruda yalnız ASCII gider, kod sayfası farkı Türkçe harfleri bozamaz.
                self.surec.stdin.write(json.dumps({"no": self.sayac, "metin": metin, "ses": ses, "tohum": tohum}) + "\n")
                self.surec.stdin.flush()
                y = self._oku()
            except Exception as e:
                self.durum = "Pocket işçisi kapandı: %s" % e
                raise RuntimeError(self.durum)
        if "hata" in y:
            raise RuntimeError("Pocket: " + y["hata"])
        return base64.b64decode(y["wav"])

    def kapat(self):
        if self.surec and self.surec.poll() is None:
            try:
                self.surec.stdin.close()
                self.surec.wait(5)
            except Exception:
                self.surec.kill()


def kur(python=None):
    """Ses ortamını (.ses-ortami) kurar: CPU torch + pocket-tts-turkish. Python 3.10–3.13 önerilir."""
    py = python or sys.executable
    adimlar = [
        [py, "-m", "venv", ORTAM],
        ["@", "-m", "pip", "install", "--upgrade", "pip"],
        ["@", "-m", "pip", "install", "torch", "--index-url", "https://download.pytorch.org/whl/cpu"],
        ["@", "-m", "pip", "install", "pocket-tts-turkish"],
    ]
    for adim in adimlar:
        if adim[0] == "@":
            adim = [ortam_python()] + adim[1:]
        print(">", " ".join(adim))
        kod = subprocess.call(adim)
        if kod:
            return kod
    print("Hazır. İlk kullanımda model (~420 MB) iner: tools/.sesler/hf")
    return 0
