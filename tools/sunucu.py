#!/usr/bin/env python3
"""KlinikKoç yerel sunucusu.

Ne yapar:
  1. Proje klasörünü http://localhost:8810 adresinde yayınlar. Mikrofon, model önbelleği ve
     Piper sesleri tarayıcıda yalnızca "güvenli" bir adreste (localhost dahil) çalışır;
     index.html'e çift tıklayarak açmak bunlar için yetmez.
  2. İsteğe bağlı: Duyu-small konuşma tanıma modelini bu bilgisayarda çalıştırır
     (/api/duyu/...). Ses bilgisayardan çıkmaz.
  3. Canlı tahta (/api/canli/...): Claude masaüstü uygulaması, tools/tahta-mcp.py
     üzerinden tahtaya komut gönderir; canli.html sayfası komutları çizer ve
     ses/ses-ayari.json'daki sesle (Pocket TTS kadın 3; yedek Piper dfki) anlatır. Yalnızca bu bilgisayarın içinden erişilir.
  4. Makaleler (/api/makale/...): ders paketindeki makaleleri bulup indirir, öğrencinin sürükleyip bıraktığı
     PDF'leri ve ders paketlerini kurar (makaleler.html). Yalnızca bu bilgisayarın içinden erişilir.
  5. Ders hazırlama sihirbazı (/api/sihirbaz/..., sihirbaz.html): öğretmenin ders taslakları, öneriler ve paketleme.

Kullanım:
  python3 tools/sunucu.py              # sunucuyu açar, tarayıcıda ses testini açar
  python3 tools/sunucu.py --port 9000
  python3 tools/sunucu.py --kur-duyu   # Duyu için gereken Python paketlerini kurar
  python3 tools/sunucu.py --sayfa canli.html   # canlı tahtayı açar

Yalnızca Python'un kendi kitaplığı gerekir. Duyu için ayrıca: numpy, onnxruntime,
sentencepiece, huggingface_hub. --kur-duyu bunları ve modeli (~56 MB, int8) kalıcı veri klasörüne
(Mac: ~/Library/Application Support/KlinikKoc/duyu, Windows: %APPDATA%\\KlinikKoc\\duyu) kurar;
program güncellenince silinmez. Model indirildikten sonra internet gerekmez.
"""
import argparse
import collections
import http.server
import importlib.util
import inspect
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import wave
import webbrowser
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pocket_ses  # noqa: E402  (tools/pocket_ses.py)
import terim_sozlugu  # noqa: E402
import ders_paketi  # noqa: E402
import ders_sonu  # noqa: E402
import degerlendirme  # noqa: E402
import makale_bulucu  # noqa: E402
try:
    import sihirbaz  # noqa: E402  (yalnız öğretmen sürümünde vardır)
except ImportError:
    sihirbaz = None
import ana_ekran  # noqa: E402
import surum as surum_  # noqa: E402
import uyandirma  # noqa: E402
import veri_yeri  # noqa: E402

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DUYU_REPO = "KaanAydinli/Duyu-small"
DUYU_PAKETLER = ["numpy", "onnxruntime", "sentencepiece", "huggingface_hub"]
KUR_KOMUTU = ("py tools\\sunucu.py --kur-duyu" if os.name == "nt" else "python3 tools/sunucu.py --kur-duyu")
# Duyu'nun paketleri ve modeli program klasörünün dışında, kalıcı veri klasöründe durur (güncellemede silinmez).
DUYU_KLASORU = os.path.join(veri_yeri.veri_kok(), "duyu")
DUYU_PAKET_KLASORU = os.path.join(DUYU_KLASORU, "paketler")
DUYU_MODEL_KLASORU = os.path.join(DUYU_KLASORU, "model")
TESLIM_SN = 20.0  # Claude'a verilen söz, tahta aracı onaylamazsa bu kadar saniye sonra kuyruğa geri döner
PARCA_SN = 24.0  # uzun konuşma bu süreyi aşmayan parçalara, sessiz yerlerden bölünerek yazıya çevrilir


def duyu_yolunu_ekle():
    if os.path.isdir(DUYU_PAKET_KLASORU) and DUYU_PAKET_KLASORU not in sys.path:
        sys.path.insert(0, DUYU_PAKET_KLASORU)


duyu_yolunu_ekle()


def bolumle(ses, ornekleme=16000, en_uzun=PARCA_SN):
    """Uzun sesi en çok en_uzun saniyelik parçalara böler; kesim noktası parçanın son yarısındaki en sessiz
    30 ms'lik penceredir (sözcük ortasından kesmemek için). Kısa ses tek parça döner."""
    import numpy as np
    n = len(ses)
    sinir = int(en_uzun * ornekleme)
    if n <= sinir:
        return [ses]
    pencere = int(0.03 * ornekleme)
    parcalar, bas = [], 0
    while n - bas > sinir:
        ara_bas = bas + sinir // 2
        ara_son = bas + sinir
        bolge = ses[ara_bas:ara_son]
        k = len(bolge) // pencere
        enerji = (bolge[:k * pencere].reshape(k, pencere) ** 2).mean(axis=1)
        # tek bir sessiz pencere yerine 5 pencerelik (150 ms) ortalamada en sessiz yer
        if k >= 5:
            enerji = np.convolve(enerji, np.ones(5) / 5, mode="same")
        kes = ara_bas + int(np.argmin(enerji)) * pencere + pencere // 2
        parcalar.append(ses[bas:kes])
        bas = kes
    parcalar.append(ses[bas:])
    return parcalar


class Duyu:
    """Duyu-small modelini bir kez yükler, sonra istekleri sırayla yazıya çevirir."""

    def __init__(self):
        self.model = None
        self.quant = None
        self.boyut = None
        self.klasor = None
        self.kilit = threading.Lock()

    def eksik_paketler(self):
        duyu_yolunu_ekle()
        eksik = []
        for p in DUYU_PAKETLER:
            try:
                __import__(p)
            except Exception:
                eksik.append(p)
        return eksik

    def _yerel_model(self):
        """Model daha önce indirildiyse klasörü (internete çıkmadan); yoksa None."""
        from huggingface_hub import snapshot_download
        for cache in (DUYU_MODEL_KLASORU, None):  # önce kalıcı klasör, sonra eski Hugging Face önbelleği
            try:
                kw = {"cache_dir": cache} if cache else {}
                return snapshot_download(DUYU_REPO, local_files_only=True, **kw)
            except Exception:
                continue
        return None

    def durum(self):
        eksik = self.eksik_paketler()
        if eksik:
            return {"kurulu": False, "hazir": False, "model_indirildi": False, "komut": KUR_KOMUTU,
                    "veri_klasoru": DUYU_KLASORU,
                    "neden": "Duyu kurulu değil (eksik Python paketleri: " + ", ".join(eksik) + "). Kurmak için: "
                             + KUR_KOMUTU}
        try:
            indirildi = self.model is not None or self._yerel_model() is not None
        except Exception:
            indirildi = False
        d = {"kurulu": True, "hazir": self.model is not None, "quant": self.quant, "model_indirildi": indirildi,
             "veri_klasoru": DUYU_KLASORU, "komut": KUR_KOMUTU}
        if not indirildi:
            d["not"] = ("Model henüz indirilmedi; ilk kullanımda bir kez internetten (~56 MB) indirilir. "
                        "Önceden indirmek için: " + KUR_KOMUTU)
        return d

    def indir(self, quant="int8"):
        from huggingface_hub import snapshot_download
        os.makedirs(DUYU_MODEL_KLASORU, exist_ok=True)
        return snapshot_download(
            DUYU_REPO, cache_dir=DUYU_MODEL_KLASORU,
            allow_patterns=[quant + "/*", "*.json", "*.npz", "spm.model", "duyu_small/*.py", "LICENSE"])

    def yukle(self, quant="int8"):
        with self.kilit:
            if self.model is not None and self.quant == quant:
                return {"yuklemeMs": 0, "boyut": self.boyut, "onbellek": True}
            t0 = time.time()
            klasor = self._yerel_model()
            if not klasor or not os.path.isdir(os.path.join(klasor, quant)):
                klasor = self.indir(quant)
            if klasor not in sys.path:
                sys.path.insert(0, klasor)
            os.environ["DUYU_SMALL_DIR"] = klasor
            from duyu_small import DuyuSmall  # model deposundaki motor kodu
            imza = inspect.signature(DuyuSmall)
            kw = {"quant": quant} if "quant" in imza.parameters else {}
            self.model = DuyuSmall(**kw)
            self.quant = quant
            self.klasor = klasor
            self.boyut = sum(
                os.path.getsize(os.path.join(d, f))
                for d, _, fs in os.walk(os.path.join(klasor, quant)) for f in fs
            )
            return {"yuklemeMs": round((time.time() - t0) * 1000), "boyut": self.boyut, "onbellek": False}

    def _cevir(self, ses, kw):
        sonuc = self.model.transcribe(ses, **kw)
        if isinstance(sonuc, tuple):
            sonuc = sonuc[0]
        if isinstance(sonuc, dict):
            sonuc = sonuc.get("text", "")
        return str(sonuc).strip()

    def yaz(self, veri, lang="mix", beam=5, mode="auto", duzelt=False):
        import numpy as np
        ses = np.frombuffer(veri, dtype="<f4").astype(np.float32)
        if self.model is None:
            self.yukle()
        imza = inspect.signature(self.model.transcribe)
        kw = {}
        for ad, deger in (("lang", lang), ("beam", int(beam)), ("mode", mode)):
            if ad in imza.parameters:
                kw[ad] = deger
        parcalar = bolumle(ses)
        with self.kilit:
            t0 = time.time()
            metinler = [self._cevir(p, kw) for p in parcalar if len(p) > 1600]  # 0,1 sn'den kısa artıkları atla
            sure = (time.time() - t0) * 1000
        metin = " ".join(m for m in metinler if m)
        out = {"metin": metin, "sureMs": round(sure, 1), "saniye": round(len(ses) / 16000, 2), "parca": len(parcalar)}
        if duzelt:
            d = TERIMLER.duzelt(metin)
            out.update(metin=d["metin"], ham_metin=d["ham_metin"], duzeltmeler=d["duzeltmeler"])
        return out


DUYU = Duyu()
TERIMLER = terim_sozlugu.Onbellek(KOK, veri_yeri.veri_kok())


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
        self.turler = {}  # komut no → tür (adimlar, soru, ...): söz kesilince Claude'a doğru not verilsin
        self.bekleyen_sayfa = 0
        self.son_gorulme = 0.0
        self.sayfa_durumu = {}
        self.ses = None
        self.ses_kilit = threading.Lock()
        self._onb_kilit = threading.Lock()
        self._ses_onbellek = collections.OrderedDict()
        self.ses_hata = None
        # Dikte: kullanıcının tahtadaki mikrofon tuşuyla söyledikleri (Claude 'dinle' ile alır).
        self.konusmalar = []
        self.dinleyen = 0
        # Duraklat: kullanıcı tahtadaki ⏸ tuşuyla anlatımı bekletti (iptal değil; devam edince sürer).
        self.duraklatildi = False
        # Claude'un tahta/soru_sor/tahta_durumu(no) ile sonuç beklediği çağrı sayısı. Bu çağrılar da
        # kullanıcı konuşunca hemen döner; yani Claude o sırada "dinliyor" sayılır.
        self.claude_bekliyor = 0
        # Claude Code kanalı (tahta-mcp.py --kanal): konuşmayı sohbete yeni mesaj olarak iletir.
        self.kanal_bekleyen = 0
        self.kanal_son = 0.0
        # Teslim onayı: Claude'a verilen söz, tahta aracı onu Claude'a yazdığını onaylayana (teslim_onay) kadar
        # silinmez, burada ayrılmış durur. Çağrı yarıda kaldıysa (iptal, zaman aşımı, Claude kapandı) söz geri konur;
        # böylece "Claude'a iletildi" denip kaybolan söz kalmaz.
        self.ayrilan = {}  # teslim no → {"parcalar": [...], "son": zaman}
        self.teslim_sayac = 0
        # Tahta aracının yarıda bıraktığı (iptal ettiği) beklemeler: bekleyen o çağrı sözü almadan hemen döner.
        self.iptaller = {}  # bekleme kimliği → zaman
        # Claude'un son araç etkinliği (herhangi bir araç çağrısı): otomatik uyandırma Claude'un sırası bitti mi diye bakar.
        self.son_arac = 0.0
        self.uyandirma = {}  # son otomatik uyandırmanın durumu (sayfa gösterir)

    def bagli(self):
        return self.bekleyen_sayfa > 0 or time.time() - self.son_gorulme < 6

    def dinliyor(self):
        """Claude kullanıcının sözünü şu anda hemen alır mı? (dinle, bekleyen bir tahta çağrısı ya da kanal)"""
        kanal = self.kanal_bekleyen > 0 or time.time() - self.kanal_son < 5
        return self.dinleyen > 0 or self.claude_bekliyor > 0 or kanal

    def durum(self, al=False, teslim=False):
        """al=True (tahta_durumu, no'suz): bekleyen konuşmanın metni de verilir ve Claude'a teslim edilmiş sayılır."""
        with self.kosul:
            self._sureleri_denetle()
            d = {"bagli": self.bagli(), "sayac": self.sayac, "sayfa": self.sayfa_durumu,
                 "bekleyen": [k["no"] for k in self.kuyruk],
                 "konusma_bekleyen": len(self.konusmalar),
                 "duraklatildi": self.duraklatildi,
                 "claude_dinliyor": self.dinliyor(),
                 "ses": self.ses_durumu(),
                 "kok": KOK, "surum": degerlendirme.program_surumu()}  # hangi kurulumdan çalıştığı: tahta aracı kendi klasörüyle karşılaştırır
            if al and self.konusmalar:
                d["bekleyen_konusmalar"] = [{k: v for k, v in x.items() if k != "t"} for x in self.konusmalar]
                self._konusma_ekle(d, teslim)
                self.kosul.notify_all()  # sayfadaki "Sorunuz bekliyor" uyarısı kalksın
            return d

    @staticmethod
    def _ham_ekle(sonuc, parcalar):
        """Dikteyle gelen sözde tanıyıcının ham çıktısı ve motoru da Claude'a gider."""
        if any("ham_metin" in x for x in parcalar):
            sonuc["ham_metin"] = " ".join(x.get("ham_metin") or x["metin"] for x in parcalar)
        motorlar = list(dict.fromkeys(x["motor"] for x in parcalar if x.get("motor")))
        if motorlar:
            sonuc["motor"] = ", ".join(motorlar)
        return sonuc

    # ---- Teslim onayı ve iptal ----
    def _konusmalari_al(self, teslim=False):
        """Bekleyen sözleri Claude'a vermek üzere kuyruktan çıkarır. teslim=True ise (yeni tahta aracı) söz hemen
        silinmez, ayrılır: döner (parçalar, teslim no). Onay gelmezse TESLIM_SN sonra kuyruğa geri döner."""
        parcalar = self.konusmalar
        self.konusmalar = []
        tno = None
        if teslim and parcalar:
            self.teslim_sayac += 1
            tno = self.teslim_sayac
            self.ayrilan[tno] = {"parcalar": parcalar, "son": time.time() + TESLIM_SN}
        return parcalar, tno

    def _geri_koy(self, tno):
        x = self.ayrilan.pop(tno, None)
        if x:
            self.konusmalar = x["parcalar"] + self.konusmalar
            self.kosul.notify_all()
        return bool(x)

    def _sureleri_denetle(self):
        simdi = time.time()
        for tno in [n for n, x in self.ayrilan.items() if x["son"] <= simdi]:
            self._geri_koy(tno)
        for b in [b for b, t in self.iptaller.items() if simdi - t > 120]:
            del self.iptaller[b]

    def teslim_et(self, tno, onay):
        """Tahta aracı: onay=True sözü Claude'a yazdı (silinir); onay=False yazamadı (kuyruğa geri konur)."""
        with self.kosul:
            if onay:
                return {"tamam": self.ayrilan.pop(tno, None) is not None}
            return {"tamam": self._geri_koy(tno)}

    def iptal(self, bekleme):
        """Tahta aracı: Claude bu çağrıyı iptal etti; o bekleme sözü almadan hemen dönsün."""
        with self.kosul:
            if bekleme:
                self.iptaller[str(bekleme)] = time.time()
            self.kosul.notify_all()
            return {"tamam": True}

    def _iptal_mi(self, bekleme):
        return bool(bekleme) and str(bekleme) in self.iptaller

    def arac_etkin(self):
        with self.kosul:
            self.son_arac = time.time()

    def _konusma_ekle(self, sonuc, teslim=False):
        # Anlatım ya da soru sırasında kullanıcı konuştuysa Claude bunu sonuçla birlikte görür.
        if self.konusmalar:
            parcalar, tno = self._konusmalari_al(teslim)
            sonuc["kullanici_konustu"] = " ".join(x["metin"] for x in parcalar)
            self._ham_ekle(sonuc, parcalar)
            if tno:
                sonuc["teslim"] = tno
        return sonuc

    def _soz_kesti(self, no, teslim=False):
        """Komut sürerken kullanıcı konuştu: Claude anlatımın bitmesini beklemeden sözü alır."""
        sonuc = {"no": no, "durum": "kullanici_konustu", "duraklatildi": self.duraklatildi}
        if self.turler.get(no) == "soru":
            sonuc["not"] = ("Kullanıcı soru kartı açıkken konuştu; kart kapandı, seçenek işaretlenmedi. Önce söylediğine "
                            "cevap ver; gerekirse soruyu soru_sor ile yeniden sor.")
        else:
            sonuc["not"] = ("Kullanıcı söz aldı; anlatım tahtada duraklatıldı ve kaldığı yer korunuyor. Önce kullanıcıya "
                            "cevap ver (tahta aracıyla sesli ya da sohbette). Sonra anlatima_devam ile kaldığı yerden "
                            "sürdür; sürdürmeyeceksen anlatima_devam(birak=true) çağır.")
            k = self.sayfa_durumu.get("kaldigi_yer") if isinstance(self.sayfa_durumu, dict) else None
            if k:
                sonuc["kaldigi_yer"] = k
        return self._konusma_ekle(sonuc, teslim)

    def _bekle(self, no, sure, bekleme=None, teslim=False):
        bitis = time.time() + max(0.0, min(float(sure), 55.0))
        self.claude_bekliyor += 1
        self.kosul.notify_all()  # sayfadaki "Claude dinliyor" ışığı yansın
        try:
            while no not in self.sonuclar:
                if self._iptal_mi(bekleme):
                    return {"no": no, "durum": "iptal_edildi"}
                if self.konusmalar:
                    return self._soz_kesti(no, teslim)
                self._sureleri_denetle()
                kalan = bitis - time.time()
                if kalan <= 0:
                    if self.duraklatildi:
                        return {
                            "no": no, "durum": "duraklatildi",
                            "not": "Kullanıcı anlatımı tahtada duraklattı. Hata değil, iptal de değil: yeni komut "
                                   "gönderme; tahta_durumu(no) ile beklemeyi sürdür. Devam edince anlatım kaldığı yerden sürer."}
                    return {"no": no, "durum": "sürüyor"}
                self.kosul.wait(min(kalan, 2.0))
            return self._konusma_ekle(dict(self.sonuclar[no], no=no), teslim)
        finally:
            self.claude_bekliyor -= 1
            self.kosul.notify_all()

    def soyle(self, metin, ham_metin=None, motor=None):
        """Sayfa: kullanıcının mikrofonla söylediği (ya da yazdığı) metin. ham_metin: tanıyıcının terim
        sözlüğünden önceki çıktısı; motor: duyu | tarayici | yazi."""
        metin = (metin or "").strip()
        with self.kosul:
            if metin:
                x = {"metin": metin, "saat": time.strftime("%H:%M:%S")}
                if motor:
                    x["motor"] = str(motor)[:20]
                if ham_metin and ham_metin.strip():
                    x["ham_metin"] = ham_metin.strip()[:2000]
                self.konusmalar.append(x)
                self.konusmalar = self.konusmalar[-20:]
                self.konusmalar[-1]["t"] = time.time()
            self.son_gorulme = time.time()
            dinliyor = self.dinliyor()
            self.kosul.notify_all()
            return {"tamam": True, "claude_dinliyor": dinliyor}

    def birak_konusmalari(self):
        """Sayfa: kullanıcı bekleyen sözünü "Sohbete kopyala" ile sohbete taşıdı; Claude'a ikinci kez verilmez."""
        with self.kosul:
            metin = " ".join(x["metin"] for x in self.konusmalar)
            self.konusmalar = []
            self.kosul.notify_all()
            return {"tamam": True, "metin": metin}

    def kanal(self, sure):
        """Claude Code kanalı (tahta-mcp.py --kanal) için: Claude başka bir çağrıyla beklemiyorsa
        kullanıcının sözünü alır; tahta-mcp.py onu sohbete yeni mesaj olarak iletir."""
        with self.kosul:
            self.kanal_bekleyen += 1
            self.kosul.notify_all()
            try:
                bitis = time.time() + max(0.0, min(float(sure), 55.0))
                while True:
                    simdi = time.time()
                    # Kısa bir pay: Claude o anda bir araçla bekliyorsa söz oradan gitsin (iki kez gelmesin).
                    if self.konusmalar and self.dinleyen == 0 and self.claude_bekliyor == 0 \
                            and simdi - self.konusmalar[-1].get("t", 0) >= 0.8:
                        parcalar = self.konusmalar
                        self.konusmalar = []
                        self.kosul.notify_all()
                        return self._ham_ekle({"durum": "konustu", "metin": " ".join(x["metin"] for x in parcalar),
                                               "sayfa": self.sayfa_durumu}, parcalar)
                    if simdi >= bitis:
                        return {"durum": "sessiz"}
                    self.kosul.wait(min(bitis - simdi, 0.3))
            finally:
                self.kanal_bekleyen -= 1
                self.kanal_son = time.time()

    def dinle(self, sure, bekleme=None, teslim=False):
        """Claude: kullanıcı konuşana kadar (en çok sure sn) bekler."""
        with self.kosul:
            self.dinleyen += 1
            self.kosul.notify_all()  # sayfa "dinliyorum" işaretini yaksın
            try:
                bitis = time.time() + max(0.0, min(float(sure), 55.0))
                while not self.konusmalar:
                    if self._iptal_mi(bekleme):
                        return {"durum": "iptal_edildi"}
                    self._sureleri_denetle()
                    kalan = bitis - time.time()
                    if kalan <= 0:
                        return {"durum": "sessiz", "bagli": self.bagli(), "uyandirma": self.uyandirma_acik()}
                    self.kosul.wait(min(kalan, 2.0))
                tum, tno = self._konusmalari_al(teslim)
                parcalar = [{"metin": x["metin"], "saat": x["saat"]} for x in tum]
                y = self._ham_ekle({"durum": "konustu", "metin": " ".join(x["metin"] for x in parcalar),
                                    "parcalar": parcalar}, tum)
                if tno:
                    y["teslim"] = tno
                return y
            finally:
                self.dinleyen -= 1
                self.kosul.notify_all()  # sayfa "dinliyorum" işaretini söndürsün

    def gonder(self, komut, sure, bekleme=None, teslim=False):
        with self.kosul:
            if not self.bagli():
                return {"durum": "bağlı değil",
                        "hata": "Tahta sayfası açık değil. tahtayi_ac aracını çağırın ya da "
                                "tarayıcıda http://localhost:8810/canli.html adresini açın."}
            if self.konusmalar and komut.get("tur") not in ("dur", "devam"):
                # Kullanıcının cevaplanmamış sözü var: yeni anlatım onu ezmesin, önce o cevaplansın.
                return self._konusma_ekle({
                    "durum": "kullanici_konustu", "gonderilmedi": True,
                    "not": "Komut tahtaya gönderilmedi; kullanıcı konuşmuş. Önce ona cevap ver, sonra komutu yeniden gönder."},
                    teslim)
            self.sayac += 1
            no = self.sayac
            self.turler[no] = komut.get("tur")
            if komut.get("tur") == "dur":
                # Durdurma sıradakileri de iptal eder; sayfa hemen uygular.
                for k in self.kuyruk:
                    self.sonuclar[k["no"]] = {"durum": "iptal"}
                self.kuyruk = []
            self.kuyruk.append(dict(komut, no=no))
            self.kosul.notify_all()
            return self._bekle(no, sure, bekleme, teslim)

    def sonuc(self, no, sure, bekleme=None, teslim=False):
        with self.kosul:
            if no not in self.sonuclar and (no > self.sayac or no < 1):
                return {"no": no, "durum": "bilinmiyor"}
            return self._bekle(no, sure, bekleme, teslim)

    def al(self, son_no, sure=20.0, sayfa_dinliyor=None, sayfa_bekleyen=None, sayfa_uyandirma=None):
        """sayfa_dinliyor / sayfa_bekleyen: sayfanın bildiği "Claude dinliyor" durumu ve bekleyen söz sayısı;
        biri değişince hemen döner (sayfa ışığı ve "Sorunuz bekliyor" uyarısını günceller)."""
        with self.kosul:
            self.bekleyen_sayfa += 1
            try:
                bitis = time.time() + sure
                while True:
                    self._sureleri_denetle()
                    dinliyor = self.dinliyor()
                    yeni = [k for k in self.kuyruk if k["no"] > son_no]
                    degisti = (sayfa_dinliyor is not None and dinliyor != sayfa_dinliyor) or \
                        (sayfa_bekleyen is not None and len(self.konusmalar) != sayfa_bekleyen) or \
                        (sayfa_uyandirma is not None and str(self.uyandirma.get("t", "")) != sayfa_uyandirma)
                    kalan = bitis - time.time()
                    if yeni or degisti or kalan <= 0:
                        return {"komutlar": yeni, "dinliyor": dinliyor,
                                "bekleyen_konusma": [x["metin"] for x in self.konusmalar],
                                "uyandirma": self.uyandirma, "ses": self.ses_bilgisi()}
                    # Kanal yoklaması kısa aralarla yenilenir; ışık titremesin diye ara ara bakılır.
                    self.kosul.wait(min(kalan, 2.0))
            finally:
                self.bekleyen_sayfa -= 1
                self.son_gorulme = time.time()

    # ---- Otomatik uyandırma (tools/uyandirma.py) ----
    # Claude dinlemiyorken söylenen söz bir süre bekler (Claude o arada kendisi alabilir). Claude'un hiçbir aracı
    # bir süredir çalışmıyorsa sırası bitmiş demektir: söz Claude sohbetine yazılıp gönderilir.
    UYANDIR_SOZ_SN = 6.0     # söz en az bu kadar beklemiş olmalı
    UYANDIR_ARAC_SN = 15.0   # Claude'un son araç etkinliğinin üzerinden en az bu kadar geçmiş olmalı
    UYANDIR_ARA_SN = 25.0    # iki uyandırma arasında en az bu kadar

    @staticmethod
    def uyandirma_acik():
        try:
            return bool(ders_sonu.ayarlar().get("otomatik_uyandirma", True)) and uyandirma.destekleniyor()
        except Exception:
            return False

    def uyandirma_ayarla(self, acik):
        a = ders_sonu.ayarlar()
        a["otomatik_uyandirma"] = bool(acik)
        ders_sonu._json_yaz(ders_sonu.ayar_yolu(), a)
        with self.kosul:
            self.uyandirma = dict(self.uyandirma, acik=self.uyandirma_acik())
            self.kosul.notify_all()
            return dict(self.uyandirma)

    def _uyandirilacak(self, simdi):
        if not self.konusmalar or self.dinliyor():
            return None
        # Tahta sayfası kapalıysa (öğrenci çalışmıyor) Claude penceresine dokunulmaz.
        if not self.bagli():
            return None
        # Aynı söz için yalnız bir kez denenir: gönderilemediyse (Claude kapalı, izin yok) yeni bir söz gelene
        # kadar yeniden denenmez. Yoksa her 25 saniyede Claude penceresi öne gelir.
        if self.konusmalar[-1].get("t") == getattr(self, "uyandirma_olmadi_t", None):
            return None
        if simdi - self.konusmalar[-1].get("t", simdi) < self.UYANDIR_SOZ_SN:
            return None
        if simdi - self.son_arac < self.UYANDIR_ARAC_SN or simdi - self.uyandirma.get("t", 0) < self.UYANDIR_ARA_SN:
            return None
        return True

    def uyandir_bir_kez(self, gonderici=None):
        """Gerekirse bir kez uyandırır. Döner: None (gerek yok) ya da (başarılı, açıklama)."""
        gonderici = gonderici or uyandirma.gonder
        with self.kosul:
            simdi = time.time()
            if not self._uyandirilacak(simdi):
                return None
            parcalar, tno = self._konusmalari_al(teslim=True)
            self.uyandirma = {"durum": "gonderiliyor", "t": simdi, "acik": True}
            self.kosul.notify_all()
        ok, neden = gonderici(" ".join(x["metin"] for x in parcalar))
        with self.kosul:
            if ok:
                self.ayrilan.pop(tno, None)  # söz sohbete gitti; Claude onu bir araçtan ikinci kez almasın
            else:
                self._geri_koy(tno)
                self.uyandirma_olmadi_t = parcalar[-1].get("t") if parcalar else None
            self.uyandirma = {"durum": "gonderildi" if ok else "olmadi", "neden": neden, "t": time.time(),
                              "saat": time.strftime("%H:%M:%S"), "acik": True}
            if ok:
                self.son_arac = time.time()  # Claude şimdi cevap yazmaya başlayacak: hemen yeniden uyandırma
            self.kosul.notify_all()
        return ok, neden

    def uyandirma_dongusu(self):
        while True:
            time.sleep(1.0)
            try:
                if self.uyandirma_acik():
                    self.uyandir_bir_kez()
            except Exception as e:  # döngü hiç durmasın
                sys.stderr.write("  Uyandırma: %s\n" % e)

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
            return {"sayac": self.sayac, "ses": self.ses_bilgisi(),
                    "uyandirma": dict(self.uyandirma, acik=self.uyandirma_acik(), destek=uyandirma.destekleniyor())}

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
            for eski in [n for n in self.turler if n < no - 200]:
                del self.turler[eski]
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
        """Sunucu açılırken çağrılır: ayarda motor=pocket ise model arka planda yüklenmeye başlar.
        Pocket kurulu değilse (ya da motor=piper ise) yedek Piper sesi arka planda hazırlanır; böylece ilk cümle
        model indirmesini (~63 MB) beklemez."""
        a = pocket_ses.ayar()
        if a.get("motor") == "pocket":
            POCKET.baslat()
        if a.get("motor") != "pocket" or not pocket_ses.ortam_python():
            threading.Thread(target=self._piper_isit, daemon=True).start()

    def _piper_isit(self):
        with self.ses_kilit:
            try:
                self._ses_yukle()
            except BaseException as e:  # voice_files sys.exit ile de çıkabilir
                self.ses_hata = str(e)

    def piper_durumu(self):
        """'hazır' | 'yüklenecek' | hata metni (Piper kurulu değil vb.)."""
        if self.ses:
            return "hazır"
        if self.ses_hata:
            return self.ses_hata
        try:
            import importlib.util as iu
            if iu.find_spec("piper") is None:
                return "Piper kurulu değil (python tools/ses-uret.py --kur)"
        except Exception:
            pass
        return "yüklenecek"

    def ses_bilgisi(self):
        """Hangi sesin GERÇEKTEN kullanılacağı: {"motor": pocket|piper|tarayici, "yazi": kısa açıklama, "ayrinti": ...}."""
        a = pocket_ses.ayar()
        yedek = (a.get("yedek") or "tr_TR-dfki-medium").replace("tr_TR-", "").replace("-medium", "")
        piper = self.piper_durumu()
        piper_olur = piper in ("hazır", "yüklenecek")
        if a.get("motor") == "pocket":
            POCKET.baslat()  # önceki deneme başarısızsa (ve bekleme süresi geçtiyse) yeniden dener
            if POCKET.durum == "hazır":
                return {"motor": "pocket", "yazi": "Pocket (%s)" % a.get("ses"), "ayrinti": "Pocket %s: hazır" % a.get("ses")}
            if POCKET.durum == "yükleniyor" and piper_olur:
                return {"motor": "piper", "yazi": "Pocket yükleniyor · şimdilik Piper",
                        "ayrinti": "Pocket %s yükleniyor (~1 dk); o zamana kadar Piper %s (yedek)" % (a.get("ses"), yedek)}
            neden = "Pocket %s: %s" % (a.get("ses"), POCKET.durum)
        else:
            neden = "ayarda motor=piper"
        if piper_olur:
            return {"motor": "piper", "yazi": "Piper %s (yedek)" % yedek if a.get("motor") == "pocket" else "Piper %s" % yedek,
                    "ayrinti": "%s → Piper %s kullanılıyor (%s)" % (neden, yedek, piper)}
        return {"motor": "tarayici", "yazi": "tarayıcı sesi (yedek)",
                "ayrinti": "%s; Piper: %s → tarayıcının Türkçe sesi kullanılıyor (daha basit ses). "
                           "Doğal ses için KUR'u yeniden çalıştırın." % (neden, piper)}

    def ses_durumu(self):
        return self.ses_bilgisi()["ayrinti"]

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

    # Aynı cümle (selamlama, "Doğru.", sık geçen tanımlar) yeniden seslendirilmesin: son SES_ONBELLEK cümle bellekte.
    SES_ONBELLEK = 120

    def seslendir(self, metin):
        a = pocket_ses.ayar()
        anahtar = (a.get("motor"), a.get("ses"), a.get("tohum"), a.get("yedek"), POCKET.durum == "hazır", metin)
        onb = self._ses_onbellek
        with self._onb_kilit:
            if anahtar in onb:
                onb.move_to_end(anahtar)
                return onb[anahtar]
        wav = self._seslendir(metin, a)
        with self._onb_kilit:
            onb[anahtar] = wav
            while len(onb) > self.SES_ONBELLEK:
                onb.popitem(last=False)
        return wav

    def _seslendir(self, metin, a):
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
            except BaseException as e:  # model indirilemezse voice_files sys.exit ile çıkabilir
                self.ses_hata = str(e)
                raise RuntimeError(self.ses_hata)
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
        ".mp4": "video/mp4", ".m4v": "video/mp4", ".webm": "video/webm", ".ogv": "video/ogg", ".mov": "video/quicktime",
    })
    VIDEO = (".mp4", ".m4v", ".webm", ".ogv", ".mov")

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=KOK, **kw)

    def end_headers(self):
        # Geliştirme sunucusu: tarayıcı eski dosyaları tutmasın.
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, fmt, *args):
        p = self.path or ""
        if "/api/" in p and not p.startswith(("/api/canli/al", "/api/canli/bitti", "/api/canli/ses", "/api/canli/kanal")):
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
        if not self._yerel_mi():
            return self._json(403, {"hata": "Yalnızca bu bilgisayardan"})
        try:
            if yol == "durum":
                return self._json(200, DUYU.durum())
            d = DUYU.durum()
            if not d["kurulu"]:
                return self._json(503, {"hata": d["neden"]})
            if yol == "yukle":
                return self._json(200, DUYU.yukle(q.get("quant", "int8")))
            if yol == "yaz":
                return self._json(200, DUYU.yaz(govde, q.get("lang", "mix"), q.get("beam", 5), q.get("mode", "auto"),
                                                q.get("duzelt") == "1"))
            return self._json(404, {"hata": "Bilinmeyen istek"})
        except Exception as e:  # hata tarayıcıda gösterilir
            return self._json(500, {"hata": "%s: %s" % (type(e).__name__, e)})

    YEREL = ("localhost", "127.0.0.1", "::1")

    def _yerel_mi(self):
        """Başka bir web sitesi, öğrencinin tarayıcısı üzerinden tahtaya komut gönderemesin ve kuyruğu okuyamasın.
        Üç denetim: (1) Host başlığı bu bilgisayar olmalı (DNS yeniden bağlama saldırısına karşı); (2) tarayıcının
        kendiliğinden eklediği Sec-Fetch-Site başka siteden geldiğini söylüyorsa red (Origin göndermeyen <img>,
        <script> gibi istekler de bunu taşır); (3) Origin varsa bu bilgisayar olmalı. Eğitmen aracı (Python) bu
        başlıkları göndermez; yalnız Host'u gönderir."""
        if not self._host_yerel_mi():
            return False
        site = (self.headers.get("Sec-Fetch-Site") or "").lower()
        if site and site not in ("same-origin", "none"):
            return False
        koken = self.headers.get("Origin")
        if not koken:
            return True
        h = urllib.parse.urlparse(koken).hostname or ""
        return h in self.YEREL

    def _canli(self, govde=b""):
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        yol = u.path[len("/api/canli/"):]
        if not self._yerel_mi():
            return self._json(403, {"hata": "Yalnızca bu bilgisayardan"})
        try:
            veri = json.loads(govde.decode("utf-8")) if govde else {}
            # Tahta aracı (tahta-mcp.py) her istekte bekleme kimliğini ve teslim onayı verdiğini söyler.
            bekleme, teslim = q.get("bekleme"), q.get("teslim") == "1"
            if self.headers.get("X-KlinikKoc-Arac"):
                CANLI.arac_etkin()
            if yol == "durum":
                return self._json(200, CANLI.durum(al=q.get("al") == "1", teslim=teslim))
            if yol == "gonder":
                return self._json(200, CANLI.gonder(veri.get("komut") or {}, float(veri.get("bekle", 50)), bekleme, teslim))
            if yol == "sonuc":
                return self._json(200, CANLI.sonuc(int(q.get("no", 0)), float(q.get("bekle", 50)), bekleme, teslim))
            if yol == "teslim":
                return self._json(200, CANLI.teslim_et(int(q.get("no", 0)), q.get("onay") == "1"))
            if yol == "iptal":
                return self._json(200, CANLI.iptal(q.get("bekleme")))
            if yol == "etkin":
                CANLI.arac_etkin()
                return self._json(200, {"tamam": True})
            if yol == "al":
                d = q.get("dinliyor")
                b = q.get("bekleyen")
                return self._json(200, CANLI.al(int(q.get("son", 0)), sayfa_dinliyor=None if d is None else d == "1",
                                                sayfa_bekleyen=None if b is None else int(b),
                                                sayfa_uyandirma=q.get("uy")))
            if yol == "soyle":
                return self._json(200, CANLI.soyle(str(veri.get("metin", ""))[:2000], veri.get("ham_metin"),
                                                   veri.get("motor")))
            if yol == "duzelt":
                return self._json(200, TERIMLER.duzelt(str(veri.get("metin", ""))[:4000]))
            if yol == "dinle":
                return self._json(200, CANLI.dinle(float(q.get("bekle", 40)), bekleme, teslim))
            if yol == "kanal":
                return self._json(200, CANLI.kanal(float(q.get("bekle", 25))))
            if yol == "kapat" and self.command == "POST":
                # Başka bir kurulumun tahta aracı bu sunucuyu kendi sunucusuyla değiştirmek istediğinde (bkz. tahtayi_ac).
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return self._json(200, {"durum": "kapanıyor", "kok": KOK})
            if yol == "ses_yeniden":
                POCKET.baslat(zorla=True)  # Pocket işçisini kapatıp yeniden açar (ör. ses kurulumu düzeltildikten sonra)
                return self._json(200, {"durum": "yeniden başlatılıyor", "ses": CANLI.ses_durumu()})
            if yol == "uyandirma":
                if self.command == "POST":
                    return self._json(200, CANLI.uyandirma_ayarla(veri.get("acik", True)))
                return self._json(200, dict(CANLI.uyandirma, acik=CANLI.uyandirma_acik(),
                                            destek=uyandirma.destekleniyor()))
            if yol == "birak":
                return self._json(200, CANLI.birak_konusmalari())
            if yol == "merhaba":
                m = dict(CANLI.merhaba(veri.get("durum")) or {})
                try:  # öğretmen bilgisayarı mı: tahtadaki Sihirbaz tuşu yalnızca o zaman görünür
                    m["ogretmen"] = ders_sonu.ayarlar().get("profil") == "ogretmen"
                except Exception:
                    m["ogretmen"] = False
                return self._json(200, m)
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

    def _makale(self, govde=b""):
        """Makaleler sayfası: durum, makale bulma, elle PDF ekleme, ders paketi kurma."""
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        yol = u.path[len("/api/makale/"):]
        if not self._yerel_mi():
            return self._json(403, {"hata": "Yalnızca bu bilgisayardan"})
        try:
            if yol == "dersler":
                return self._json(200, {"dersler": makale_bulucu.makaleli_dersler(),
                                        "klasor": veri_yeri.makale_kok(), "pdf_okuyucu": makale_bulucu.pypdf_var()})
            if yol == "durum":
                return self._json(200, makale_bulucu.ozet(q.get("ders", "")))
            if yol == "depolama":
                return self._json(200, ders_sonu.depolama())
            if yol == "degerlendirme":
                return self._json(200, degerlendirme.form(q.get("ders", ""), q.get("ogrenci") or None))
            if self.command != "POST":
                return self._json(405, {"hata": "POST gerekli"})
            if yol == "hazirla":
                veri = json.loads(govde.decode("utf-8")) if govde else {}
                return self._json(200, makale_bulucu.arka_planda_hazirla(str(veri.get("ders", "")),
                                                                         not veri.get("agsiz")))
            if yol == "ekle":
                return self._json(200, makale_bulucu.elle_ekle(q.get("ders", ""), govde, q.get("ad") or "makale.pdf",
                                                               q.get("kaynak") or None))
            if yol == "tara":
                veri = json.loads(govde.decode("utf-8")) if govde else {}
                return self._json(200, makale_bulucu.indirilenlerden_tara(str(veri.get("ders", ""))))
            if yol == "kaldir":
                veri = json.loads(govde.decode("utf-8")) if govde else {}
                return self._json(200, makale_bulucu.eki_kaldir(str(veri.get("ders", "")), str(veri.get("id", ""))))
            if yol == "paket":
                fd, gecici = tempfile.mkstemp(suffix=".zip")
                with os.fdopen(fd, "wb") as f:
                    f.write(govde)
                try:
                    r = ders_paketi.yukle(gecici, q.get("uzerine") == "1")
                finally:
                    os.remove(gecici)
                if r["makale"]:
                    makale_bulucu.arka_planda_hazirla(r["ders"])
                return self._json(200, r)
            if yol == "sinir":
                veri = json.loads(govde.decode("utf-8")) if govde else {}
                return self._json(200, {"sinir_gb": ders_sonu.sinir_ayarla(veri.get("gb"))})
            if yol == "arsivle":
                veri = json.loads(govde.decode("utf-8")) if govde else {}
                return self._json(200, ders_sonu.arsivle(str(veri.get("ders", ""))))
            if yol == "geri_yukle":
                veri = None
                if govde[:2] == b"PK":  # zip gövdesi: bırakılan arşiv dosyası
                    fd, gecici = tempfile.mkstemp(suffix=".zip")
                    with os.fdopen(fd, "wb") as f:
                        f.write(govde)
                    try:
                        return self._json(200, ders_sonu.geri_yukle(gecici))
                    finally:
                        os.remove(gecici)
                veri = json.loads(govde.decode("utf-8")) if govde else {}
                g = next((x for x in ders_sonu.arsiv_listesi() if x["ders"] == veri.get("ders")), None)
                if not g or not g.get("dosya_var"):
                    raise ValueError("Bu dersin arşiv dosyası bulunamadı; zip'i buraya sürükleyip bırakın.")
                return self._json(200, ders_sonu.geri_yukle(g["dosya"]))
            if yol == "degerlendirme_kaydet":
                veri = json.loads(govde.decode("utf-8")) if govde else {}
                r = degerlendirme.kaydet(str(veri.get("ders", "")), veri.get("cevaplar") or {},
                                         veri.get("ogrenci") or None, veri.get("tespitler") or [],
                                         bool(veri.get("ozet_ekle", True)))
                r.pop("form", None)
                return self._json(200, r)
            if yol == "degerlendirme_klasoru_ac":
                k = degerlendirme.klasor()
                os.makedirs(k, exist_ok=True)
                klasoru_ac(k)
                return self._json(200, {"acildi": k})
            if yol == "arsiv_klasoru_ac":
                k = ders_sonu.arsiv_kok()
                os.makedirs(k, exist_ok=True)
                klasoru_ac(k)
                return self._json(200, {"acildi": k})
            if yol == "klasor_ac":
                veri = json.loads(govde.decode("utf-8")) if govde else {}
                ders = str(veri.get("ders", ""))
                k = makale_bulucu.makale_klasoru(ders) if ders else veri_yeri.makale_kok()
                os.makedirs(k, exist_ok=True)
                klasoru_ac(k)
                return self._json(200, {"acildi": k})
            return self._json(404, {"hata": "Bilinmeyen istek"})
        except FileExistsError as e:
            return self._json(409, {"hata": str(e)})
        except FileNotFoundError as e:
            return self._json(404, {"hata": str(e)})
        except (ValueError, KeyError, zipfile.BadZipFile, RuntimeError) as e:
            return self._json(400, {"hata": str(e)})
        except Exception as e:
            return self._json(500, {"hata": "%s: %s" % (type(e).__name__, e)})

    def _sihirbaz(self, govde=b""):
        """Öğretmen ekranı: ders taslakları, künyeler, notlar, vakalar, öneriler, paketleme."""
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        yol = u.path[len("/api/sihirbaz/"):]
        if not self._yerel_mi():
            return self._json(403, {"hata": "Yalnızca bu bilgisayardan"})
        S = sihirbaz
        if S is None or not surum_.ogretmen_mi():
            return self._json(404, {"hata": "Ders hazırlama yalnız öğretmen sürümünde vardır."})
        ogretmen_profili_isaretle()
        try:
            if yol == "liste":
                return self._json(200, {"taslaklar": S.liste(), "kademeler": S.KADEME_ADI, "bloom": S.BLOOM})
            if yol == "taslak":
                return self._json(200, S.taslak_oku(q.get("ders", "")))
            if yol == "bolumler":
                return self._json(200, {"bolumler": S.not_bolumleri(q.get("ders", ""), q.get("not", ""))})
            if yol == "denetle":
                return self._json(200, S.denetle(q.get("ders", "")))
            if self.command != "POST":
                return self._json(405, {"hata": "POST gerekli"})
            ders = q.get("ders", "")
            if yol == "not":
                return self._json(200, S.not_ekle(ders, govde, q.get("ad") or "not.docx", q.get("kademe") or "fakulte"))
            if yol == "video":
                return self._json(200, S.video_ekle(ders, govde, q.get("ad") or "video.mp4", q.get("kademe") or "fakulte"))
            if yol == "vaka":
                return self._json(200, S.vaka_ekle(ders, govde, q.get("ad") or "vaka.json", q.get("kademe") or "fakulte"))
            v = json.loads(govde.decode("utf-8")) if govde else {}
            ders = str(v.get("ders") or ders)
            if yol == "yeni":
                return self._json(200, S.yeni(ders, v.get("baslik") or ""))
            if yol == "kart":
                return self._json(200, S.kart_guncelle(ders, v.get("alanlar") or {}))
            if yol == "doi":
                return self._json(200, S.doi_ekle(ders, str(v.get("metin", ""))))
            if yol == "kunye_yenile":
                return self._json(200, S.kunyeleri_yenile(ders))
            if yol == "ana":
                return self._json(200, S.ana_kaynak(ders, str(v.get("id", ""))))
            if yol == "oge":
                return self._json(200, S.oge_kaydet(ders, str(v.get("liste", "")), v.get("oge") or {}))
            if yol == "sil":
                return self._json(200, S.oge_sil(ders, str(v.get("liste", "")), str(v.get("id", ""))))
            if yol == "oner_kural":
                return self._json(200, S.kural_onerileri(ders))
            if yol == "kabul":
                return self._json(200, S.oneri_kabul(ders, str(v.get("tur", "")), str(v.get("oneri_id", "")),
                                                     v.get("duzeltme") or None))
            if yol == "reddet":
                return self._json(200, S.oneri_reddet(ders, str(v.get("tur", "")), str(v.get("oneri_id", ""))))
            if yol == "paketle":
                return self._json(200, S.paketle(ders))
            if yol == "klasor_ac":
                k = os.path.join(veri_yeri.belgeler(), "KlinikKoç Ders Paketleri")
                os.makedirs(k, exist_ok=True)
                klasoru_ac(k)
                return self._json(200, {"acildi": k})
            return self._json(404, {"hata": "Bilinmeyen istek"})
        except FileExistsError as e:
            return self._json(409, {"hata": str(e)})
        except FileNotFoundError as e:
            return self._json(404, {"hata": str(e)})
        except (ValueError, KeyError, zipfile.BadZipFile, RuntimeError) as e:
            return self._json(400, {"hata": str(e)})
        except Exception as e:
            return self._json(500, {"hata": "%s: %s" % (type(e).__name__, e)})

    def _ana(self, govde=b""):
        """Ana ekran (ana.html): dersler ve PDF'ler, çalışma seçimi, güncelleme, programa öneriler."""
        u = urllib.parse.urlparse(self.path)
        yol = u.path[len("/api/ana/"):]
        if not self._yerel_mi():
            return self._json(403, {"hata": "Yalnızca bu bilgisayardan"})
        A = ana_ekran
        try:
            if yol == "ozet":
                return self._json(200, A.ozet())
            if yol == "geri_bildirim":
                return self._json(200, A.geri_bildirim())
            if self.command != "POST":
                return self._json(405, {"hata": "POST gerekli"})
            v = json.loads(govde.decode("utf-8")) if govde else {}
            if yol == "secim":
                return self._json(200, A.secim_yaz(v.get("dersler"), v.get("pdfler")))
            if yol == "guncelleme_denetle":
                return self._json(200, surum_.denetle(zorla=True))
            if yol == "guncelle":
                r = surum_.guncelle()
                if r.get("guncellendi"):
                    yeniden_baslat()
                return self._json(200, r)
            if yol == "geri_al":
                r = surum_.geri_al()
                yeniden_baslat()
                return self._json(200, r)
            if yol == "oneri_sil":
                return self._json(200, A.oneri_sil(str(v.get("id", ""))))
            if yol == "oneri_gonderildi":
                return self._json(200, A.oneri_isaretle(v.get("idler") or []))
            if yol == "klasor_ac":
                k = {"oneri": A.oneri_klasoru(), "form": degerlendirme.klasor(),
                     "paket": os.path.join(veri_yeri.belgeler(), "KlinikKoç Ders Paketleri")}.get(str(v.get("hangi")))
                if not k:
                    raise ValueError("Bilinmeyen klasör")
                os.makedirs(k, exist_ok=True)
                klasoru_ac(k)
                return self._json(200, {"acildi": k})
            return self._json(404, {"hata": "Bilinmeyen istek"})
        except FileNotFoundError as e:
            return self._json(404, {"hata": str(e)})
        except (ValueError, KeyError, RuntimeError, zipfile.BadZipFile) as e:
            return self._json(400, {"hata": str(e)})
        except Exception as e:
            return self._json(500, {"hata": "%s: %s" % (type(e).__name__, e)})

    def _host_yerel_mi(self):
        host = self.headers.get("Host") or ""
        return not host or (urllib.parse.urlsplit("//" + host).hostname or "") in self.YEREL

    def do_GET(self):
        # DNS yeniden bağlama: başka bir alan adı bu sunucuya yönlendirilip ders dosyaları okunamasın.
        if not self._host_yerel_mi():
            return self.send_error(403, "Yalnızca bu bilgisayardan")
        if self.path.startswith("/api/duyu/"):
            return self._api()
        if self.path.startswith("/api/canli/"):
            return self._canli()
        if self.path.startswith("/api/makale/"):
            return self._makale()
        if self.path.startswith("/api/sihirbaz/"):
            return self._sihirbaz()
        if self.path.startswith("/api/ana/"):
            return self._ana()
        if urllib.parse.urlparse(self.path).path in ("/", ""):
            self.send_response(302)
            self.send_header("Location", "/ana.html")
            self.end_headers()
            return None
        if urllib.parse.urlparse(self.path).path.lower().endswith(self.VIDEO):
            return self._video()
        return super().do_GET()

    def _video(self):
        """Video dosyaları parça parça (Range) verilir; tarayıcı videoyu ileri-geri sarabilsin."""
        yol = self.translate_path(self.path)
        if not os.path.isfile(yol):
            return self.send_error(404, "Video bulunamadı")
        boyut = os.path.getsize(yol)
        bas, son = 0, boyut - 1
        aralik = self.headers.get("Range", "")
        kismi = aralik.startswith("bytes=")
        if kismi:
            try:
                a, b = aralik[6:].split(",")[0].split("-")
                if a:
                    bas = int(a)
                    son = int(b) if b else boyut - 1
                else:
                    bas = max(0, boyut - int(b))
                son = min(son, boyut - 1)
                if bas > son:
                    raise ValueError
            except ValueError:
                self.send_response(416)
                self.send_header("Content-Range", "bytes */%d" % boyut)
                self.end_headers()
                return None
        self.send_response(206 if kismi else 200)
        self.send_header("Content-Type", self.guess_type(yol))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(son - bas + 1))
        if kismi:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (bas, son, boyut))
        self.end_headers()
        try:
            with open(yol, "rb") as f:
                f.seek(bas)
                kalan = son - bas + 1
                while kalan > 0:
                    parca = f.read(min(1 << 16, kalan))
                    if not parca:
                        break
                    self.wfile.write(parca)
                    kalan -= len(parca)
        except (BrokenPipeError, ConnectionResetError):
            pass
        return None

    def _olcum_kaydet(self, govde):
        if not self._yerel_mi():
            return self._json(403, {"hata": "Yalnızca bu bilgisayardan"})
        if len(govde) > 20 * 1024 * 1024:
            return self._json(413, {"hata": "Sonuç çok büyük"})
        try:
            veri = json.loads(govde.decode("utf-8"))
            if not isinstance(veri, dict) or not isinstance(veri.get("sonuc"), dict):
                raise ValueError("sonuc yok")
            return self._json(200, {"dosya": olcum_kaydet(veri)})
        except Exception as e:
            return self._json(400, {"hata": "%s: %s" % (type(e).__name__, e)})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > 600 * 1024 * 1024:
            return self._json(413, {"hata": "Dosya çok büyük"})
        if self.path.startswith(("/api/makale/", "/api/sihirbaz/", "/api/ana/")) and not self._yerel_mi():
            return self._json(403, {"hata": "Yalnızca bu bilgisayardan"})
        govde = self.rfile.read(n) if n else b""
        if self.path.startswith("/api/makale/"):
            return self._makale(govde)
        if self.path.startswith("/api/sihirbaz/"):
            return self._sihirbaz(govde)
        if self.path.startswith("/api/ana/"):
            return self._ana(govde)
        if self.path.startswith("/api/canli/"):
            return self._canli(govde)
        if self.path.startswith("/api/ses-testi/kaydet"):
            return self._olcum_kaydet(govde)
        if not self.path.startswith("/api/duyu/"):
            return self._json(404, {"hata": "Bilinmeyen istek"})
        return self._api(govde)


def ogretmen_profili_isaretle():
    """Ders sihirbazını açan kişi öğretmendir: Claude'a öğretmen araçları da gösterilsin (ayarlar.json "profil").
    Elle "ogrenci" yazılmışsa dokunulmaz. Claude'un yeni araç listesini görmesi için bir kez yeniden açılması gerekir."""
    try:
        a = ders_sonu.ayarlar()
        if not a.get("profil"):
            a["profil"] = "ogretmen"
            ders_sonu._json_yaz(ders_sonu.ayar_yolu(), a)
    except Exception:
        pass


_PORT = [8810]


def yeniden_baslat(gecikme=1.2):
    """Güncellemeden sonra: yeni dosyalarla yeni bir sunucu başlatır ve bu süreci kapatır (yanıt gittikten sonra)."""
    arg = [sys.executable, os.path.join(KOK, "tools", "sunucu.py"), "--acma", "--bekle", "--port", str(_PORT[0])]

    def calis():
        try:
            if os.name == "nt":
                subprocess.Popen(arg, cwd=KOK, creationflags=subprocess.CREATE_NEW_CONSOLE,
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.Popen(arg, cwd=KOK, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, start_new_session=True)
        finally:
            try:
                POCKET.kapat()
            except Exception:
                pass
            os._exit(0)
    threading.Timer(gecikme, calis).start()


def klasoru_ac(yol):
    """Klasörü bilgisayarın dosya gezgininde açar."""
    if os.name == "nt":
        os.startfile(yol)  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", yol])
    else:
        subprocess.Popen(["xdg-open", yol])


def olcum_kaydet(veri, klasor=None):
    """Ses testi sayfasının dikte karşılaştırmasını kalıcı veri klasörüne yazar (JSON + Markdown)."""
    klasor = klasor or os.path.join(veri_yeri.veri_kok(), "olcumler")
    os.makedirs(klasor, exist_ok=True)
    ad = "dikte-karsilastirma-" + time.strftime("%Y-%m-%d_%H%M%S")
    yol = os.path.join(klasor, ad + ".json")
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(veri.get("sonuc"), f, ensure_ascii=False, indent=1)
    if isinstance(veri.get("md"), str):
        with open(os.path.join(klasor, ad + ".md"), "w", encoding="utf-8") as f:
            f.write(veri["md"] + "\n")
    return yol


def kur_duyu():
    """Duyu'nun paketlerini ve modelini kalıcı veri klasörüne kurar (program klasörüne değil)."""
    os.makedirs(DUYU_PAKET_KLASORU, exist_ok=True)
    print("Duyu kuruluyor. Yer (güncellemede silinmez): " + DUYU_KLASORU)
    print("1/2 Python paketleri: " + ", ".join(DUYU_PAKETLER))
    kod = subprocess.call([sys.executable, "-m", "pip", "install", "--upgrade", "--target", DUYU_PAKET_KLASORU]
                          + DUYU_PAKETLER)
    if kod != 0:
        print("Paketler kurulamadı. İnternet bağlantısını denetleyip yeniden deneyin.")
        return kod
    importlib.invalidate_caches()
    duyu_yolunu_ekle()
    print("2/2 Model indiriliyor (~56 MB, bir kez)...")
    try:
        DUYU.indir()
    except Exception as e:
        print("Model indirilemedi (%s). İlk kullanımda yeniden denenecek." % e)
        return 1
    print("Duyu hazır. Ses bilgisayardan çıkmaz; bundan sonra internetsiz çalışır.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="KlinikKoç yerel sunucusu")
    ap.add_argument("--port", type=int, default=8810)
    ap.add_argument("--kur-duyu", action="store_true", help="Duyu için gereken paketleri kur ve çık")
    ap.add_argument("--acma", action="store_true", help="tarayıcıyı kendiliğinden açma")
    ap.add_argument("--sayfa", default="ana.html", help="açılacak sayfa (varsayılan: ana ekran)")
    ap.add_argument("--bekle", action="store_true", help="kapı doluysa boşalmasını bekle (güncelleme sonrası)")
    a = ap.parse_args()
    _PORT[0] = a.port
    if a.kur_duyu:
        sys.exit(kur_duyu())
    adres = "http://localhost:%d/%s" % (a.port, a.sayfa)
    sunucu = None
    for _ in range(40 if a.bekle else 1):
        try:
            sunucu = http.server.ThreadingHTTPServer(("127.0.0.1", a.port), Isleyici)
            break
        except OSError:
            if a.bekle:
                time.sleep(0.5)
    if sunucu is None:
        # Sunucu zaten açık (ör. Claude başlattı): yalnız sayfayı açarız.
        print("KlinikKoç zaten açık: " + adres)
        if not a.acma:
            webbrowser.open(adres)
        return
    print("KlinikKoç sunucusu çalışıyor: " + adres)
    print("Kapatmak için bu pencerede Ctrl+C'ye basın.")
    d = DUYU.durum()
    print("Duyu-small: " + ("hazır (ilk kullanımda yüklenecek)" if d["kurulu"] else d["neden"]))
    CANLI.pocket_baslat()
    CANLI.uyandirma = {"acik": CANLI.uyandirma_acik()}
    threading.Thread(target=CANLI.uyandirma_dongusu, daemon=True).start()
    print("Otomatik uyandırma: " + ("açık (Claude dinlemiyorken söylenenler sohbete gönderilir)"
                                    if CANLI.uyandirma["acik"] else "kapalı"))
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
