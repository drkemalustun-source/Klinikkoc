"""Öğrenci kayıtlarının güvenli ve kalıcı deposu.

- Yer: program klasörünün dışında kalıcı veri klasörü (bkz. veri_yeri.py); KLINIK_KOC_KAYIT önce gelir.
  Eski yerde (program klasörü/kayitlar) kayıt varsa ilk açılışta bir kez kopyalanır; eski dosyalar silinmez.
- Atomik yazma: önce geçici dosyaya yazılır, diske işlenir, sonra yerine konur. Her yazımdan önce önceki
  sürüm yedekler/ klasörüne .yedek olarak kopyalanır; son 5 yedek kalır.
- Bozuk JSON: bozuk dosya .bozuk-<zaman> adıyla saklanır, en yeni sağlam yedekten açılır, uyarı döner.
- Kalıcı öğrenci kimliği: ad + kısa ayırt edici (öğrenci numarasının son 3 hanesi ya da takma ad).
  Eski, yalnız ada göre açılmış klasörler aynen okunur.
- Deneme kaydı: öğretmenin denemeleri (ad "deneme" ya da deneme bayrağı) ayrı işaretlenir.

Kayıtlar yalnız bu bilgisayarda durur; bu modül hiçbir yere ağ bağlantısı kurmaz.
"""
import datetime
import glob
import json
import os
import shutil
import tempfile
import time

YEDEK_SAYISI = 5
KAYIT_DEFTERI = "ogrenciler.json"
TASIMA_DOSYASI = ".tasima.json"
YEDEK_KLASORU = "yedekler"
_TR = str.maketrans("çğıöşüÇĞİÖŞÜ ", "cgiosuCGIOSU-")


class KayitHatasi(ValueError):
    pass


class AyniAdBelirsiz(KayitHatasi):
    def __init__(self, ad, adaylar):
        self.ad, self.adaylar = ad, adaylar
        super().__init__("Bu adla birden çok kayıt var (%s): %s. ogrenci alanına kimliği yaz." % (
            ad, ", ".join(a["kimlik"] for a in adaylar)))


def kisalt(metin, uzunluk=60):
    metin = (metin or "").strip().replace("İ", "i").translate(_TR).lower()
    kisa = "".join(c for c in metin if c.isalnum() or c == "-")
    while "--" in kisa:
        kisa = kisa.replace("--", "-")
    return kisa.strip("-")[:uzunluk]


def ad_anahtari(ad):
    return kisalt(ad, 200)


def deneme_adi_mi(ad):
    a = ad_anahtari(ad)
    return a == "deneme" or a.startswith("deneme-") or a.startswith("ogretmen-deneme")


def zaman_damgasi():
    t = time.time()
    return time.strftime("%Y%m%d-%H%M%S", time.localtime(t)) + "-%06d" % int((t % 1) * 1e6)


# ---------- Dosya düzeyi: atomik yazma, yedek, kurtarma ----------
def _yerine_koy(kaynak, hedef):
    for deneme in range(10):  # Windows'ta virüs tarayıcı dosyayı kısa süre tutabilir
        try:
            os.replace(kaynak, hedef)
            return
        except PermissionError:
            if deneme == 9:
                raise
            time.sleep(0.1 * (deneme + 1))


def yedek_klasoru(yol):
    return os.path.join(os.path.dirname(yol), YEDEK_KLASORU)


def yedekler(yol):
    """Bu dosyanın yedekleri, en yeniden eskiye."""
    desen = os.path.join(glob.escape(yedek_klasoru(yol)), glob.escape(os.path.basename(yol)) + ".*.yedek")
    return sorted(glob.glob(desen), reverse=True)


def atomik_yaz(yol, veri, yedekle=True, yedek_sayisi=YEDEK_SAYISI):
    """JSON'u önce geçici dosyaya yazar, diske işler, sonra yerine koyar. Önceki sürüm yedeklenir."""
    klasor = os.path.dirname(yol)
    os.makedirs(klasor, exist_ok=True)
    if yedekle and os.path.exists(yol):
        yk = yedek_klasoru(yol)
        os.makedirs(yk, exist_ok=True)
        shutil.copy2(yol, os.path.join(yk, "%s.%s.yedek" % (os.path.basename(yol), zaman_damgasi())))
        for eski in yedekler(yol)[yedek_sayisi:]:
            try:
                os.remove(eski)
            except OSError:
                pass
    fd, gecici = tempfile.mkstemp(prefix="." + os.path.basename(yol) + ".", suffix=".tmp", dir=klasor)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(veri, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())
        _yerine_koy(gecici, yol)
    except BaseException:
        try:
            os.remove(gecici)
        except OSError:
            pass
        raise
    return yol


def _json_oku(yol):
    with open(yol, encoding="utf-8") as f:
        veri = json.load(f)
    if not isinstance(veri, dict):
        raise ValueError("kayıt bir nesne değil")
    return veri


def guvenli_oku(yol):
    """(veri ya da None, uyarılar). Dosya bozuksa en yeni sağlam yedekten açar ve onu geri yazar."""
    if not os.path.exists(yol):
        return None, []
    try:
        return _json_oku(yol), []
    except (ValueError, OSError) as e:
        hata = e
    bozuk = "%s.bozuk-%s" % (yol, zaman_damgasi())
    try:
        os.replace(yol, bozuk)
    except OSError:
        bozuk = yol
    for y in yedekler(yol):
        try:
            veri = _json_oku(y)
        except (ValueError, OSError):
            continue
        atomik_yaz(yol, veri, yedekle=False)
        tarih = os.path.basename(y).rsplit(".", 2)[-2][:15]
        return veri, ["Kayıt dosyası bozuk bulundu (%s); %s tarihli yedekten açıldı. Bozuk dosya silinmedi: %s" % (
            type(hata).__name__, "%s-%s-%s %s:%s" % (tarih[:4], tarih[4:6], tarih[6:8], tarih[9:11], tarih[11:13]),
            os.path.basename(bozuk))]
    return None, ["Kayıt dosyası bozuk ve sağlam yedeği yok; yeni kayıt başlatıldı. Bozuk dosya silinmedi: %s"
                  % os.path.basename(bozuk)]


# ---------- Depo ----------
class Depo:
    def __init__(self, kok, eski_kok=None):
        self.kok = os.path.abspath(kok)
        self.eski_kok = eski_kok
        self._hazir = False
        self.tasima_raporu = None

    # --- açılış ve eski yerden taşıma ---
    def hazirla(self):
        if self._hazir:
            return
        os.makedirs(self.kok, exist_ok=True)
        self._hazir = True
        if self.eski_kok:
            self.tasima_raporu = self.tasi(self.eski_kok)

    def tasi(self, eski):
        """Eski yerdeki kayıtları bir kez yeni yere kopyalar. Eski dosyalara dokunmaz (silmez)."""
        os.makedirs(self.kok, exist_ok=True)
        eski = os.path.abspath(eski)
        if not os.path.isdir(eski) or os.path.normcase(os.path.realpath(eski)) == os.path.normcase(os.path.realpath(self.kok)):
            return None
        durum_yolu = os.path.join(self.kok, TASIMA_DOSYASI)
        durum, _ = guvenli_oku(durum_yolu)
        durum = durum or {"tasinanlar": []}
        if any(os.path.normcase(t.get("kaynak", "")) == os.path.normcase(eski) for t in durum["tasinanlar"]):
            return None
        kopyalanan, cakisan = [], []
        for kok_, klasorler, dosyalar in os.walk(eski):
            klasorler[:] = [k for k in klasorler if not k.startswith(".")]
            for ad in dosyalar:
                if ad.endswith(".tmp") or ad == "TASINDI.txt" or ad.startswith("."):
                    continue
                kaynak = os.path.join(kok_, ad)
                goreli = os.path.relpath(kaynak, eski)
                hedef = os.path.join(self.kok, goreli)
                os.makedirs(os.path.dirname(hedef), exist_ok=True)
                if not os.path.exists(hedef):
                    shutil.copy2(kaynak, hedef)
                    kopyalanan.append(goreli)
                elif open(kaynak, "rb").read() != open(hedef, "rb").read():
                    govde, uzanti = os.path.splitext(hedef)
                    alt = "%s.eski-yerden-%s%s" % (govde, zaman_damgasi(), uzanti)
                    if uzanti == ".json":  # ders kaydı gibi okunmasın, yedek sırasında da silinmesin
                        alt = os.path.join(yedek_klasoru(hedef), "%s.eski-yerden-%s.kopya" % (
                            os.path.basename(hedef), zaman_damgasi()))
                        os.makedirs(os.path.dirname(alt), exist_ok=True)
                    shutil.copy2(kaynak, alt)
                    cakisan.append(goreli)
        rapor = {"kaynak": eski, "tarih": time.strftime("%Y-%m-%d %H:%M"), "kopyalanan": len(kopyalanan),
                 "cakisan": cakisan}
        durum["tasinanlar"].append(rapor)
        atomik_yaz(durum_yolu, durum, yedekle=False)
        if kopyalanan or cakisan:
            try:
                with open(os.path.join(eski, "TASINDI.txt"), "w", encoding="utf-8") as f:
                    f.write("Bu klasördeki öğrenci kayıtları %s tarihinde kalıcı kayıt klasörüne kopyalandı:\n%s\n\n"
                            "Buradaki dosyalar silinmedi, ama artık kullanılmıyor. Yeni yerdeki kayıtları "
                            "denetledikten sonra bu klasörü isterseniz silebilirsiniz.\n" % (rapor["tarih"], self.kok))
            except OSError:
                pass
        return rapor

    # --- öğrenci defteri ---
    def _defter_yolu(self):
        return os.path.join(self.kok, KAYIT_DEFTERI)

    def defter(self):
        self.hazirla()
        d, _ = guvenli_oku(self._defter_yolu())
        d = d or {}
        d.setdefault("surum", 1)
        d.setdefault("ogrenciler", {})
        return d

    def _defteri_yaz(self, d):
        atomik_yaz(self._defter_yolu(), d)

    def klasor(self, kimlik):
        kimlik = (kimlik or "").strip()
        if not kimlik or kisalt(kimlik) != kimlik:
            raise KayitHatasi("Geçersiz öğrenci kimliği: %r" % kimlik)
        return os.path.join(self.kok, kimlik)

    def _klasor_kimlikleri(self):
        if not os.path.isdir(self.kok):
            return []
        return sorted(a for a in os.listdir(self.kok)
                      if not a.startswith(".") and a != YEDEK_KLASORU and os.path.isdir(os.path.join(self.kok, a)))

    def _ders_kayitlari(self, kimlik):
        return sorted(glob.glob(os.path.join(glob.escape(os.path.join(self.kok, kimlik)), "*.json")))

    def bilgi(self, kimlik):
        """{kimlik, ad, ayirt, deneme, eski, dersler, son_calisma} — kayıtların özeti (yalnız bu bilgisayar)."""
        d = self.defter()["ogrenciler"].get(kimlik)
        dersler, son, ad, deneme = [], None, None, False
        for y in self._ders_kayitlari(kimlik):
            dersler.append(os.path.splitext(os.path.basename(y))[0])
            try:
                k = _json_oku(y)
            except (ValueError, OSError):
                continue
            ad = ad or k.get("ogrenci")
            deneme = deneme or bool(k.get("deneme"))
            t = k.get("guncelleme") or ((k.get("oturumlar") or [{}])[-1].get("tarih")) or k.get("olusturma")
            son = max(son or "", t or "") or None
        if d:
            ad = d.get("ad") or ad
            deneme = bool(d.get("deneme")) or deneme
        return {"kimlik": kimlik, "ad": ad or kimlik, "ayirt": (d or {}).get("ayirt"),
                "deneme": deneme or deneme_adi_mi(ad or kimlik), "eski": not d or not d.get("ayirt"),
                "dersler": dersler, "son_calisma": (son or "")[:10] or None}

    def ogrenciler(self):
        kimlikler = set(self.defter()["ogrenciler"]) | set(self._klasor_kimlikleri())
        return [self.bilgi(k) for k in sorted(kimlikler)]

    def adaylar(self, ad):
        """Aynı adı taşıyan kayıtlar (defterdekiler ve eski, ada göre açılmış klasörler)."""
        anahtar = ad_anahtari(ad)
        if not anahtar:
            return []
        bulunan = set()
        for kimlik, v in self.defter()["ogrenciler"].items():
            if ad_anahtari(v.get("ad")) == anahtar:
                bulunan.add(kimlik)
        eski = kisalt(ad)
        if eski and os.path.isdir(os.path.join(self.kok, eski)):
            bulunan.add(eski)
        return [self.bilgi(k) for k in sorted(bulunan)]

    def var_mi(self, kimlik):
        return kimlik in self.defter()["ogrenciler"] or (
            kisalt(kimlik) == kimlik and bool(kimlik) and os.path.isdir(os.path.join(self.kok, kimlik)))

    def kimlik_olustur(self, ad, ayirt, deneme=False):
        """Ad + ayırt ediciden kalıcı kimlik açar (varsa olanı döndürür)."""
        ad = (ad or "").strip()
        ayirt = (ayirt or "").strip()
        if not ad:
            raise KayitHatasi("ogrenci (öğrencinin adı) gerekli")
        if not ayirt:
            raise KayitHatasi("ayirt gerekli: öğrenci numarasının son 3 hanesi ya da bir takma ad")
        d = self.defter()
        for kimlik, v in d["ogrenciler"].items():
            if ad_anahtari(v.get("ad")) == ad_anahtari(ad) and kisalt(v.get("ayirt")) == kisalt(ayirt):
                if deneme and not v.get("deneme"):
                    v["deneme"] = True
                    self._defteri_yaz(d)
                return kimlik
        taban = "%s-%s" % (kisalt(ad, 40) or "ogrenci", kisalt(ayirt, 20) or "x")
        kimlik, n = taban, 2
        while kimlik in d["ogrenciler"] or os.path.exists(os.path.join(self.kok, kimlik)):
            kimlik, n = "%s-%d" % (taban, n), n + 1
        d["ogrenciler"][kimlik] = {"ad": ad, "ayirt": ayirt, "olusturma": time.strftime("%Y-%m-%d"),
                                   "deneme": bool(deneme or deneme_adi_mi(ad))}
        self._defteri_yaz(d)
        return kimlik

    def eskiyi_bagla(self, kimlik, ayirt=None, deneme=False):
        """Eski (yalnız ada göre) kaydı deftere işler; ayırt edici verilirse ona bağlar. Klasör aynı kalır."""
        d = self.defter()
        v = d["ogrenciler"].get(kimlik)
        degisti = v is None
        if v is None:
            b = self.bilgi(kimlik)
            v = d["ogrenciler"][kimlik] = {"ad": b["ad"], "ayirt": None, "olusturma": time.strftime("%Y-%m-%d"),
                                           "deneme": b["deneme"], "eski_kayit": True}
        if ayirt and not v.get("ayirt"):
            v["ayirt"], degisti = ayirt.strip(), True
        if deneme and not v.get("deneme"):
            v["deneme"], degisti = True, True
        if degisti:
            self._defteri_yaz(d)
        return kimlik

    def deneme_mi(self, kimlik):
        v = self.defter()["ogrenciler"].get(kimlik) or {}
        return bool(v.get("deneme")) or deneme_adi_mi(v.get("ad") or kimlik)

    def coz(self, ogrenci):
        """Araçların ogrenci alanını kimliğe çevirir: kimlik → kendisi; tek eşleşen ad → o kayıt;
        birden çok eşleşme → AyniAdBelirsiz; hiç yoksa eski usul (ada göre) yeni kimlik."""
        metin = (ogrenci or "").strip()
        if not metin:
            raise KayitHatasi("ogrenci (öğrencinin adı ya da kimliği) gerekli")
        self.hazirla()
        if self.var_mi(metin):
            return metin
        adaylar = self.adaylar(metin)
        if len(adaylar) == 1:
            return adaylar[0]["kimlik"]
        if len(adaylar) > 1:
            raise AyniAdBelirsiz(metin, adaylar)
        return kisalt(metin) or "ogrenci"

    # --- ders kayıtları ---
    def kayit_yolu(self, kimlik, ders):
        return os.path.join(self.klasor(kimlik), ders + ".json")

    def yukle(self, kimlik, ders):
        """(kayıt ya da None, uyarılar)"""
        self.hazirla()
        return guvenli_oku(self.kayit_yolu(kimlik, ders))

    def yaz(self, kimlik, ders, veri):
        self.hazirla()
        veri = {k: v for k, v in veri.items() if not k.startswith("_")}
        veri["guncelleme"] = datetime.datetime.now().isoformat(timespec="microseconds")
        yol = atomik_yaz(self.kayit_yolu(kimlik, ders), veri)
        d = self.defter()
        if kimlik not in d["ogrenciler"]:
            d["ogrenciler"][kimlik] = {"ad": veri.get("ogrenci") or kimlik, "ayirt": None,
                                       "olusturma": time.strftime("%Y-%m-%d"),
                                       "deneme": bool(veri.get("deneme")), "eski_kayit": True}
            self._defteri_yaz(d)
        return yol

    def metin_yaz(self, kimlik, alt_klasor, ad, metin):
        klasor = os.path.join(self.klasor(kimlik), alt_klasor)
        os.makedirs(klasor, exist_ok=True)
        yol = os.path.join(klasor, ad)
        gecici = yol + ".tmp"
        with open(gecici, "w", encoding="utf-8") as f:
            f.write(metin)
            f.flush()
            os.fsync(f.fileno())
        _yerine_koy(gecici, yol)
        return yol
