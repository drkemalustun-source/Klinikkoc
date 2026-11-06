#!/usr/bin/env python3
"""Akıllı Tahta yerel sunucusu.

Ne yapar:
  1. Proje klasörünü http://localhost:8800 adresinde yayınlar. Mikrofon, model önbelleği ve
     Piper sesleri tarayıcıda yalnızca "güvenli" bir adreste (localhost dahil) çalışır;
     index.html'e çift tıklayarak açmak bunlar için yetmez.
  2. İsteğe bağlı: Duyu-small konuşma tanıma modelini bu bilgisayarda çalıştırır
     (/api/duyu/...). Ses bilgisayardan çıkmaz.
  3. Canlı tahta (/api/canli/...): Claude masaüstü uygulaması, tools/tahta-mcp.py
     üzerinden tahtaya komut gönderir; canli.html sayfası komutları çizer ve
     ses/ses-ayari.json'daki sesle (Pocket TTS kadın 3; yedek Piper dfki) anlatır. Yalnızca bu bilgisayarın içinden erişilir.

Kullanım:
  python3 tools/sunucu.py              # sunucuyu açar, tarayıcıda ses testini açar
  python3 tools/sunucu.py --port 9000
  python3 tools/sunucu.py --kur-duyu   # Duyu için gereken Python paketlerini kurar
  python3 tools/sunucu.py --sayfa canli.html   # canlı tahtayı açar

Yalnızca Python'un kendi kitaplığı gerekir. Duyu için ayrıca: numpy, onnxruntime,
sentencepiece, huggingface_hub (--kur-duyu bunları kurar). Model (~56 MB, int8) ilk
kullanımda Hugging Face'ten indirilir ve bilgisayarda saklanır.
"""
import argparse
import http.server
import importlib.util
import inspect
import io
import json
import os
import subprocess
import sys
import threading
import time
import urllib.parse
import wave
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pocket_ses  # noqa: E402  (tools/pocket_ses.py)

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DUYU_REPO = "KaanAydinli/Duyu-small"
DUYU_PAKETLER = ["numpy", "onnxruntime", "sentencepiece", "huggingface_hub"]


class Duyu:
    """Duyu-small modelini bir kez yükler, sonra istekleri sırayla yazıya çevirir."""

    def __init__(self):
        self.model = None
        self.quant = None
        self.boyut = None
        self.kilit = threading.Lock()

    def durum(self):
        eksik = []
        for p in DUYU_PAKETLER:
            try:
                __import__(p)
            except Exception:
                eksik.append(p)
        if eksik:
            return {"kurulu": False, "hazir": False,
                    "neden": "Eksik Python paketleri: " + ", ".join(eksik) + ". Kurmak için: python3 tools/sunucu.py --kur-duyu"}
        return {"kurulu": True, "hazir": self.model is not None, "quant": self.quant}

    def yukle(self, quant="int8"):
        with self.kilit:
            if self.model is not None and self.quant == quant:
                return {"yuklemeMs": 0, "boyut": self.boyut, "onbellek": True}
            t0 = time.time()
            from huggingface_hub import snapshot_download
            klasor = snapshot_download(
                DUYU_REPO,
                allow_patterns=[quant + "/*", "*.json", "*.npz", "spm.model", "duyu_small/*.py", "LICENSE"],
            )
            if klasor not in sys.path:
                sys.path.insert(0, klasor)
            os.environ["DUYU_SMALL_DIR"] = klasor
            from duyu_small import DuyuSmall  # model deposundaki motor kodu
            imza = inspect.signature(DuyuSmall)
            kw = {"quant": quant} if "quant" in imza.parameters else {}
            self.model = DuyuSmall(**kw)
            self.quant = quant
            self.boyut = sum(
                os.path.getsize(os.path.join(d, f))
                for d, _, fs in os.walk(os.path.join(klasor, quant)) for f in fs
            )
            return {"yuklemeMs": round((time.time() - t0) * 1000), "boyut": self.boyut, "onbellek": False}

    def yaz(self, veri, lang="mix", beam=5, mode="auto"):
        import numpy as np
        ses = np.frombuffer(veri, dtype="<f4").astype(np.float32)
        if self.model is None:
            self.yukle()
        imza = inspect.signature(self.model.transcribe)
        kw = {}
        for ad, deger in (("lang", lang), ("beam", int(beam)), ("mode", mode)):
            if ad in imza.parameters:
                kw[ad] = deger
        with self.kilit:
            t0 = time.time()
            sonuc = self.model.transcribe(ses, **kw)
            sure = (time.time() - t0) * 1000
        if isinstance(sonuc, tuple):
            sonuc = sonuc[0]
        if isinstance(sonuc, dict):
            sonuc = sonuc.get("text", "")
        return {"metin": str(sonuc), "sureMs": round(sure, 1), "saniye": round(len(ses) / 16000, 2)}


DUYU = Duyu()


class Canli:
    """Claude (tahta-mcp.py) ile canli.html sayfası arasındaki komut kuyruğu.

    Claude bir komut gönderir (gonder); sayfa uzun yoklamayla alır (al), uygular,
    anlatım bitince sonucu bildirir (bitti). Claude sonucu aynı istekte ya da
    sonradan (sonuc) alır. Soru kartında sonuç, tıklanan cevaptır.
    """

    def __init__(self):
        self.kosul = threading.Condition()
        self.kuyruk = []
        self.sayac = 0
        self.sonuclar = {}
        self.bekleyen_sayfa = 0
        self.son_gorulme = 0.0
        self.sayfa_durumu = {}
        self.ses = None
        self.ses_kilit = threading.Lock()
        self.ses_hata = None
        # Dikte: kullanıcının tahtadaki mikrofon tuşuyla söyledikleri (Claude 'dinle' ile alır).
        self.konusmalar = []
        self.dinleyen = 0
        # Duraklat: kullanıcı tahtadaki ⏸ tuşuyla anlatımı bekletti (iptal değil; devam edince sürer).
        self.duraklatildi = False

    def bagli(self):
        return self.bekleyen_sayfa > 0 or time.time() - self.son_gorulme < 6

    def durum(self):
        with self.kosul:
            return {"bagli": self.bagli(), "sayac": self.sayac, "sayfa": self.sayfa_durumu,
                    "bekleyen": [k["no"] for k in self.kuyruk],
                    "konusma_bekleyen": len(self.konusmalar),
                    "duraklatildi": self.duraklatildi,
                    "ses": self.ses_durumu()}

    def _konusma_ekle(self, sonuc):
        # Anlatım ya da soru sırasında kullanıcı konuştuysa Claude bunu sonuçla birlikte görür.
        if self.konusmalar:
            sonuc["kullanici_konustu"] = " ".join(x["metin"] for x in self.konusmalar)
            self.konusmalar = []
        return sonuc

    def _bekle(self, no, sure):
        bitis = time.time() + max(0.0, min(float(sure), 55.0))
        while no not in self.sonuclar:
            kalan = bitis - time.time()
            if kalan <= 0:
                if self.duraklatildi:
                    return self._konusma_ekle({
                        "no": no, "durum": "duraklatildi",
                        "not": "Kullanıcı anlatımı tahtada duraklattı. Hata değil, iptal de değil: yeni komut "
                               "gönderme; tahta_durumu(no) ile beklemeyi sürdür. Devam edince anlatım kaldığı yerden sürer."})
                return self._konusma_ekle({"no": no, "durum": "sürüyor"})
            self.kosul.wait(kalan)
        return self._konusma_ekle(dict(self.sonuclar[no], no=no))

    def soyle(self, metin):
        """Sayfa: kullanıcının mikrofonla söylediği metin."""
        metin = (metin or "").strip()
        with self.kosul:
            if metin:
                self.konusmalar.append({"metin": metin, "saat": time.strftime("%H:%M:%S")})
                self.konusmalar = self.konusmalar[-20:]
            self.son_gorulme = time.time()
            self.kosul.notify_all()
            return {"tamam": True, "claude_dinliyor": self.dinleyen > 0}

    def dinle(self, sure):
        """Claude: kullanıcı konuşana kadar (en çok sure sn) bekler."""
        with self.kosul:
            self.dinleyen += 1
            self.kosul.notify_all()  # sayfa "dinliyorum" işaretini yaksın
            try:
                bitis = time.time() + max(0.0, min(float(sure), 55.0))
                while not self.konusmalar:
                    kalan = bitis - time.time()
                    if kalan <= 0:
                        return {"durum": "sessiz", "bagli": self.bagli()}
                    self.kosul.wait(kalan)
                parcalar = self.konusmalar
                self.konusmalar = []
                return {"durum": "konustu", "metin": " ".join(x["metin"] for x in parcalar), "parcalar": parcalar}
            finally:
                self.dinleyen -= 1
                self.kosul.notify_all()  # sayfa "dinliyorum" işaretini söndürsün

    def gonder(self, komut, sure):
        with self.kosul:
            if not self.bagli():
                return {"durum": "bağlı değil",
                        "hata": "Tahta sayfası açık değil. tahtayi_ac aracını çağırın ya da "
                                "tarayıcıda http://localhost:8800/canli.html adresini açın."}
            self.sayac += 1
            no = self.sayac
            if komut.get("tur") == "dur":
                # Durdurma sıradakileri de iptal eder; sayfa hemen uygular.
                for k in self.kuyruk:
                    self.sonuclar[k["no"]] = {"durum": "iptal"}
                self.kuyruk = []
            self.kuyruk.append(dict(komut, no=no))
            self.kosul.notify_all()
            return self._bekle(no, sure)

    def sonuc(self, no, sure):
        with self.kosul:
            if no not in self.sonuclar and (no > self.sayac or no < 1):
                return {"no": no, "durum": "bilinmiyor"}
            return self._bekle(no, sure)

    def al(self, son_no, sure=20.0, sayfa_dinliyor=None):
        """sayfa_dinliyor: sayfanın bildiği "Claude dinliyor" durumu; değişince hemen döner."""
        with self.kosul:
            self.bekleyen_sayfa += 1
            try:
                bitis = time.time() + sure
                while True:
                    dinliyor = self.dinleyen > 0
                    yeni = [k for k in self.kuyruk if k["no"] > son_no]
                    if yeni or (sayfa_dinliyor is not None and dinliyor != sayfa_dinliyor):
                        return {"komutlar": yeni, "dinliyor": dinliyor}
                    kalan = bitis - time.time()
                    if kalan <= 0:
                        return {"komutlar": [], "dinliyor": dinliyor}
                    self.kosul.wait(kalan)
            finally:
                self.bekleyen_sayfa -= 1
                self.son_gorulme = time.time()

    def duraklat(self, var_, durum=None):
        """Sayfa: kullanıcı anlatımı duraklattı (True) ya da devam ettirdi (False)."""
        with self.kosul:
            self.duraklatildi = bool(var_)
            if durum:
                self.sayfa_durumu = durum
            self.son_gorulme = time.time()
            self.kosul.notify_all()
            return {"tamam": True, "duraklatildi": self.duraklatildi}

    def merhaba(self, durum):
        """Sayfa (yeniden) açıldı: bitmemiş komutlar iptal, sayaç sayfaya bildirilir."""
        with self.kosul:
            self.duraklatildi = False
            for k in self.kuyruk:
                self.sonuclar[k["no"]] = {"durum": "iptal", "not": "Tahta sayfası yeniden yüklendi."}
            self.kuyruk = []
            self.sayfa_durumu = durum or {}
            self.son_gorulme = time.time()
            self.kosul.notify_all()
            return {"sayac": self.sayac}

    def bitti(self, no, sonuc, durum):
        with self.kosul:
            self.sonuclar[no] = sonuc or {"durum": "bitti"}
            self.kuyruk = [k for k in self.kuyruk if k["no"] != no]
            if durum:
                self.sayfa_durumu = durum
            self.son_gorulme = time.time()
            # Kimsenin almadığı eski sonuçlar birikmesin.
            for eski in [n for n in self.sonuclar if n < no - 200]:
                del self.sonuclar[eski]
            self.kosul.notify_all()

    # ---- Seslendirme: ses/ses-ayari.json'daki ses (varsayılan Pocket TTS Türkçe, kadın 3);
    #      Pocket hazır değilken ya da hata verirse Piper (yedek, dfki). Telaffuz sözlüğü ses-uret.py ile aynı.
    def _mod(self):
        if not hasattr(self, "_ses_mod"):
            yol = os.path.join(KOK, "tools", "ses-uret.py")
            spec = importlib.util.spec_from_file_location("ses_uret", yol)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self._ses_mod = mod
        return self._ses_mod

    def pocket_baslat(self):
        """Sunucu açılırken çağrılır: ayarda motor=pocket ise model arka planda yüklenmeye başlar."""
        a = pocket_ses.ayar()
        if a.get("motor") == "pocket":
            POCKET.baslat()

    def ses_durumu(self):
        a = pocket_ses.ayar()
        if a.get("motor") == "pocket":
            return "Pocket %s: %s" % (a.get("ses"), POCKET.durum)
        return "hazır" if self.ses else (self.ses_hata or "ilk anlatımda yüklenecek")

    def _ses_yukle(self):
        if self.ses:
            return self.ses
        mod = self._mod()
        try:
            from piper import PiperVoice
        except ImportError:
            raise RuntimeError("Piper kurulu değil (python tools/ses-uret.py --kur). Tarayıcı sesi kullanılıyor.")
        model = mod.voice_files(pocket_ses.ayar().get("yedek") or "tr_TR-dfki-medium")
        self.ses = {"mod": mod, "voice": PiperVoice.load(model), "sozluk": mod.load_dictionary()}
        return self.ses

    def seslendir(self, metin):
        a = pocket_ses.ayar()
        if a.get("motor") == "pocket":
            try:
                mod = self._mod()
                yazi = mod.pronounce(mod.plain(metin), mod.load_dictionary())
                if yazi.strip():
                    return POCKET.wav(yazi, a.get("ses") or "female_3", a.get("tohum"))
            except Exception as e:  # sessizce Piper'a dön
                sys.stderr.write("  Ses: %s; Piper kullanılıyor.\n" % e)
        with self.ses_kilit:
            try:
                s = self._ses_yukle()
            except Exception as e:
                self.ses_hata = str(e)
                raise
            mod, voice = s["mod"], s["voice"]
            yazi = mod.pronounce(mod.plain(metin), s["sozluk"])
            parcalar = [c.audio_int16_array.tobytes() for c in voice.synthesize(yazi)]
            tampon = io.BytesIO()
            with wave.open(tampon, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(voice.config.sample_rate)
                w.writeframes(b"".join(parcalar))
            return tampon.getvalue()


CANLI = Canli()
POCKET = pocket_ses.PocketIsci()


class Isleyici(http.server.SimpleHTTPRequestHandler):
    # Windows'ta Python dosya türlerini kayıt defterinden okur ve .js'yi "text/plain" verebilir;
    # tarayıcı o zaman kitaplıkları yüklemez. Türleri burada sabitliyoruz.
    extensions_map = dict(http.server.SimpleHTTPRequestHandler.extensions_map, **{
        ".js": "text/javascript", ".mjs": "text/javascript", ".json": "application/json",
        ".wasm": "application/wasm", ".webmanifest": "application/manifest+json",
        ".svg": "image/svg+xml", ".css": "text/css", ".html": "text/html",
    })

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=KOK, **kw)

    def end_headers(self):
        # Geliştirme sunucusu: tarayıcı eski dosyaları tutmasın.
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, fmt, *args):
        p = self.path or ""
        if "/api/" in p and not p.startswith(("/api/canli/al", "/api/canli/bitti", "/api/canli/ses")):
            sys.stderr.write("  %s\n" % (fmt % args))

    def _json(self, kod, veri):
        govde = json.dumps(veri, ensure_ascii=False).encode("utf-8")
        self.send_response(kod)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(govde)))
        self.end_headers()
        self.wfile.write(govde)

    def _api(self, govde=b""):
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        yol = u.path[len("/api/duyu/"):]
        try:
            if yol == "durum":
                return self._json(200, DUYU.durum())
            d = DUYU.durum()
            if not d["kurulu"]:
                return self._json(503, {"hata": d["neden"]})
            if yol == "yukle":
                return self._json(200, DUYU.yukle(q.get("quant", "int8")))
            if yol == "yaz":
                return self._json(200, DUYU.yaz(govde, q.get("lang", "mix"), q.get("beam", 5), q.get("mode", "auto")))
            return self._json(404, {"hata": "Bilinmeyen istek"})
        except Exception as e:  # hata tarayıcıda gösterilir
            return self._json(500, {"hata": "%s: %s" % (type(e).__name__, e)})

    def _yerel_mi(self):
        # Başka bir web sitesi tarayıcı üzerinden tahtaya komut gönderemesin.
        koken = self.headers.get("Origin")
        if not koken:
            return True
        h = urllib.parse.urlparse(koken).hostname or ""
        return h in ("localhost", "127.0.0.1")

    def _canli(self, govde=b""):
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        yol = u.path[len("/api/canli/"):]
        if not self._yerel_mi():
            return self._json(403, {"hata": "Yalnızca bu bilgisayardan"})
        try:
            veri = json.loads(govde.decode("utf-8")) if govde else {}
            if yol == "durum":
                return self._json(200, CANLI.durum())
            if yol == "gonder":
                return self._json(200, CANLI.gonder(veri.get("komut") or {}, float(veri.get("bekle", 50))))
            if yol == "sonuc":
                return self._json(200, CANLI.sonuc(int(q.get("no", 0)), float(q.get("bekle", 50))))
            if yol == "al":
                d = q.get("dinliyor")
                return self._json(200, CANLI.al(int(q.get("son", 0)), sayfa_dinliyor=None if d is None else d == "1"))
            if yol == "soyle":
                return self._json(200, CANLI.soyle(str(veri.get("metin", ""))[:2000]))
            if yol == "dinle":
                return self._json(200, CANLI.dinle(float(q.get("bekle", 40))))
            if yol == "merhaba":
                return self._json(200, CANLI.merhaba(veri.get("durum")))
            if yol == "duraklat":
                return self._json(200, CANLI.duraklat(veri.get("duraklatildi"), veri.get("durum")))
            if yol == "bitti":
                CANLI.bitti(int(veri.get("no", 0)), veri.get("sonuc"), veri.get("durum"))
                return self._json(200, {"tamam": True})
            if yol == "ses":
                wav = CANLI.seslendir(str(veri.get("metin", ""))[:2000])
                self.send_response(200)
                self.send_header("Content-Type", "audio/wav")
                self.send_header("Content-Length", str(len(wav)))
                self.end_headers()
                self.wfile.write(wav)
                return None
            return self._json(404, {"hata": "Bilinmeyen istek"})
        except (BrokenPipeError, ConnectionResetError):
            return None
        except Exception as e:
            return self._json(500, {"hata": "%s: %s" % (type(e).__name__, e)})

    def do_GET(self):
        if self.path.startswith("/api/duyu/"):
            return self._api()
        if self.path.startswith("/api/canli/"):
            return self._canli()
        return super().do_GET()

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        govde = self.rfile.read(n) if n else b""
        if self.path.startswith("/api/canli/"):
            return self._canli(govde)
        if not self.path.startswith("/api/duyu/"):
            return self._json(404, {"hata": "Bilinmeyen istek"})
        return self._api(govde)


def kur_duyu():
    print("Duyu için Python paketleri kuruluyor: " + ", ".join(DUYU_PAKETLER))
    return subprocess.call([sys.executable, "-m", "pip", "install", "--upgrade"] + DUYU_PAKETLER)


def main():
    ap = argparse.ArgumentParser(description="Akıllı Tahta yerel sunucusu")
    ap.add_argument("--port", type=int, default=8800)
    ap.add_argument("--kur-duyu", action="store_true", help="Duyu için gereken paketleri kur ve çık")
    ap.add_argument("--acma", action="store_true", help="tarayıcıyı kendiliğinden açma")
    ap.add_argument("--sayfa", default="ses-testi/", help="açılacak sayfa (varsayılan: ses testi)")
    a = ap.parse_args()
    if a.kur_duyu:
        sys.exit(kur_duyu())
    sunucu = http.server.ThreadingHTTPServer(("127.0.0.1", a.port), Isleyici)
    adres = "http://localhost:%d/%s" % (a.port, a.sayfa)
    print("Akıllı Tahta sunucusu çalışıyor: " + adres)
    print("Kapatmak için bu pencerede Ctrl+C'ye basın.")
    d = DUYU.durum()
    print("Duyu-small: " + ("hazır (ilk kullanımda yüklenecek)" if d["kurulu"] else "kurulu değil. " + d["neden"]))
    CANLI.pocket_baslat()
    print("Ses: " + CANLI.ses_durumu() + " (ayar: ses/ses-ayari.json)")
    if not a.acma:
        threading.Timer(0.8, lambda: webbrowser.open(adres)).start()
    try:
        sunucu.serve_forever()
    except KeyboardInterrupt:
        print("\nKapatıldı.")
    finally:
        POCKET.kapat()


if __name__ == "__main__":
    main()
