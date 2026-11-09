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


def _json_oku(yol):
    with open(yol, encoding="utf-8") as f:
        return json.load(f)


KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AYAR_DOSYASI = os.path.join(KOK, "ses", "ses-ayari.json")
ORTAM = os.path.join(KOK, ".ses-ortami")
VARSAYILAN = {"motor": "piper", "ses": "female_3", "tohum": 1,
              "yedek": "tr_TR-dfki-medium", "tarayici_ses": "tr_TR-ilkiz-medium"}


def ayar():
    a = dict(VARSAYILAN)
    try:
        a.update(_json_oku(AYAR_DOSYASI))
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


UYGUN = ((3, 10), (3, 13))   # pocket-tts-turkish (torch) bu Python sürümleriyle kurulabiliyor


def _surum(komut):
    """[komut] ile açılan Python'un ((ana, alt), yol) bilgisi; açılamazsa None."""
    try:
        r = subprocess.run(komut + ["-c", "import sys;print(sys.version_info[0], sys.version_info[1]);print(sys.executable)"],
                           capture_output=True, text=True, timeout=30,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode:
            return None
        satir = r.stdout.strip().splitlines()
        ana, alt = (int(x) for x in satir[0].split())
        return (ana, alt), satir[1].strip()
    except Exception:
        return None


def _uygun_mu(surum):
    return UYGUN[0] <= surum <= UYGUN[1]


def _uv():
    import shutil
    for p in (shutil.which("uv"), os.path.expanduser("~/.local/bin/uv"), os.path.expanduser("~/.local/bin/uv.exe"),
              os.path.expanduser("~/.cargo/bin/uv")):
        if p and os.path.exists(p):
            return p
    return None


def uygun_python(yaz=print):
    """Pocket için Python 3.10–3.13 bulur (yol döner) ya da None.

    Sıra: bu Python → Windows'ta py -3.13 … -3.10, Mac/Linux'ta python3.13 … python3.10 →
    uv kuruluysa uv'nin Python'u (gerekirse uv bir 3.12 indirir).
    """
    import shutil
    adaylar = [[sys.executable]]
    alt_surumler = range(UYGUN[1][1], UYGUN[0][1] - 1, -1)
    if os.name == "nt":
        adaylar += [["py", "-3.%d" % n] for n in alt_surumler]
    else:
        adaylar += [[p] for p in (shutil.which("python3.%d" % n) for n in alt_surumler) if p]
    for komut in adaylar:
        s = _surum(komut)
        if s and _uygun_mu(s[0]):
            return s[1]
    uv = _uv()
    if uv:
        for _ in range(2):
            try:
                r = subprocess.run([uv, "python", "find", "3.12"], capture_output=True, text=True, timeout=60)
                yol = r.stdout.strip()
                if r.returncode == 0 and yol:
                    s = _surum([yol])
                    if s and _uygun_mu(s[0]):
                        return s[1]
            except Exception:
                break
            yaz("Uygun Python yok; uv ile Python 3.12 indiriliyor...")
            if subprocess.call([uv, "python", "install", "3.12"]):
                break
    return None


PYTHON_YOK = ("Pocket sesi için Python 3.10–3.13 gerekir (bu bilgisayardaki Python: %d.%d).\n"
              "python.org/downloads adresinden Python 3.12'yi kurup KUR'u yeniden çalıştırın.\n"
              "Şimdilik daha basit bir yedek ses kullanılacak; ders yine çalışır.")


def ortam_kurulu():
    """Ses ortamı var ve içinde pocket_tts_turkish açılabiliyor mu?"""
    py = ortam_python()
    if not py:
        return False
    try:
        return subprocess.run([py, "-I", "-c", "import pocket_tts_turkish"], capture_output=True, timeout=300,
                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).returncode == 0
    except Exception:
        return False


def kur(python=None):
    """Ses ortamını (.ses-ortami) kurar: CPU torch + pocket-tts-turkish. Python 3.10–3.13 gerekir.

    python verilmezse uygun bir Python aranır (uygun_python). 0: kuruldu, 2: uygun Python yok, öteki: hata.
    """
    py = python or uygun_python()
    if not py:
        print(PYTHON_YOK % sys.version_info[:2])
        return 2
    s = _surum([py])
    if not s:
        print("Python açılamadı: %s" % py)
        return 2
    if not _uygun_mu(s[0]):
        print(PYTHON_YOK % s[0])
        return 2
    print("Pocket ses ortamı Python %d.%d ile kuruluyor: %s" % (s[0] + (s[1],)))
    venv = [py, "-m", "venv", ORTAM]
    if os.path.isdir(ORTAM):
        venv.insert(4, "--clear")   # yarım kalmış eski kurulum temizlenir
    adimlar = [
        venv,
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
            print("Pocket ses ortamı kurulamadı (adım hata verdi). Yedek ses kullanılacak.")
            return kod
    print("Ses ortamı kuruldu. İlk kullanımda model (~420 MB) iner: tools/.sesler/hf")
    return 0


def sesi_dene(cumle="Ses hazır. Tahta konuşmaya hazır.", sure=900, cal=True):
    """Pocket'i açıp kısa bir cümle seslendirir; 0 başarı. İlk seferde model indiği için uzun sürebilir."""
    if not ortam_python():
        print("Pocket ses ortamı yok; yedek ses kullanılacak.")
        return 1
    print("Pocket sesi deneniyor (ilk seferde model ~420 MB iner, birkaç dakika sürebilir)...")
    isci = PocketIsci()
    t0 = time.time()
    try:
        isci.baslat()
        while not isci.hazir.wait(15):
            if time.time() - t0 > sure:
                print("Pocket açılamadı: %d sn içinde hazır olmadı." % sure)
                return 1
            print("  ...yükleniyor (%d sn)" % (time.time() - t0))
        if isci.durum != "hazır":
            print("Pocket açılamadı: " + isci.durum)
            return 1
        wav = isci.wav(cumle, **_ses_secimi())
        print("Ses hazır (Pocket %s, %.0f sn)." % (_ses_secimi()["ses"], time.time() - t0))
        if cal:
            _cal(wav)
        return 0
    except Exception as e:
        print("Pocket açılamadı: %s" % e)
        return 1
    finally:
        isci.kapat()


def _ses_secimi():
    a = ayar()
    return {"ses": a.get("ses") or "female_3", "tohum": a.get("tohum", 1)}


def _cal(wav):
    """Deneme sesini hoparlörden çalar (Windows: winsound, Mac: afplay); olmazsa sessizce geçer."""
    try:
        if os.name == "nt":
            import winsound
            winsound.PlaySound(wav, winsound.SND_MEMORY)
        elif sys.platform == "darwin":
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(wav)
            subprocess.call(["afplay", f.name])
            os.unlink(f.name)
    except Exception:
        pass
