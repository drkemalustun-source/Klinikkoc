"""KlinikKoç sürümü, sürüm türü (öğrenci / öğretmen) ve tek tuşla güncelleme.

Sürüm türü
  Kod tektir; iki indirme dosyası vardır. Öğrenci sürümünde ders hazırlama dosyaları (OGRETMEN_DOSYALARI) bulunmaz
  ve program klasöründeki SURUM-TURU dosyasında "ogrenci" yazar. Dosya yoksa: sihirbaz.html varsa öğretmen sürümüdür.
  KLINIK_KOC_TUR ortam değişkeni her şeyden önce gelir.

Güncelleme
  denetle()  GitHub'daki SURUM dosyasına bakar (en çok 6 saatte bir; internet yoksa sessizce "yok" der).
  guncelle() 1) çalışan sürümün yedeğini alır (veri klasörü/surum-yedek), 2) yeni sürümü indirir ve doğrular,
             3) program dosyalarını yenisiyle değiştirir, 4) bir sorun çıkarsa yedekten geri döner.
  Dersler (lessons/), kayıtlar, makaleler, ses ayarı ve öğretmenin özel içeriği güncellemede hiç dokunulmaz.
  Öğrenciye yalnız ana dala (main) alınmış, yani onaylanmış sürümler gider.

Yalnız Python'un kendi kitaplığını kullanır.
"""
import io
import json
import os
import shutil
import sys
import time
import urllib.request
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import veri_yeri  # noqa: E402

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPO = os.environ.get("KLINIK_KOC_DEPO") or "drkemalustun-source/klinikkoc"
DAL = os.environ.get("KLINIK_KOC_DAL") or "main"
SURUM_ADRESI = "https://raw.githubusercontent.com/%s/%s/SURUM" % (DEPO, DAL)
ZIP_ADRESI = "https://github.com/%s/archive/refs/heads/%s.zip" % (DEPO, DAL)
DENETIM_ARALIGI = 6 * 3600
YEDEK_SAYISI = 3
EN_BUYUK_ZIP = 300 * 1024 * 1024

# Yalnız öğretmen sürümünde bulunan dosyalar (öğrenci indirme dosyasına ve öğrenci güncellemesine girmez).
OGRETMEN_DOSYALARI = (
    "sihirbaz.html", "js/sihirbaz.js", "css/sihirbaz.css", "tools/sihirbaz.py",
    "sablonlar/ders-taslagi-bos.json", "belgeler/sihirbaz.md", "belgeler/ogretmen-kilavuzu.md",
)
# Güncellemenin hiç dokunmadığı yerler (kullanıcının kendi verisi ya da bilgisayarda üretilenler).
KORUNAN = ("lessons/", "ozel/", "kayitlar/", ".git/", ".dizin/", ".modeller/", ".ses-ortami/", "tools/.sesler/",
           "__pycache__/", "SURUM-TURU")
# Varsa üzerine yazılmayan ayar dosyaları (kullanıcı değiştirmiş olabilir).
AYAR_DOSYALARI = ("ses/ses-ayari.json",)


def _oku(yol, varsayilan=""):
    try:
        with open(yol, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return varsayilan


def surum():
    return _oku(os.path.join(KOK, "SURUM"), "0")


def tur():
    """'ogretmen' ya da 'ogrenci'."""
    t = (os.environ.get("KLINIK_KOC_TUR") or _oku(os.path.join(KOK, "SURUM-TURU"))).lower()
    if t in ("ogrenci", "ogretmen"):
        return t
    return "ogretmen" if os.path.isfile(os.path.join(KOK, "sihirbaz.html")) else "ogrenci"


def ogretmen_mi():
    return tur() == "ogretmen"


def _sayilar(s):
    out = []
    for p in str(s).strip().split("."):
        rakam = "".join(c for c in p if c.isdigit())
        out.append(int(rakam) if rakam else 0)
    return tuple(out + [0] * (3 - len(out)))


def yeni_mi(aday, simdiki=None):
    return _sayilar(aday) > _sayilar(simdiki if simdiki is not None else surum())


def _durum_yolu():
    return os.path.join(veri_yeri.veri_kok(), "guncelleme.json")


def _durum_oku():
    try:
        with open(_durum_yolu(), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _durum_yaz(d):
    os.makedirs(os.path.dirname(_durum_yolu()), exist_ok=True)
    gecici = _durum_yolu() + ".yeni"
    with open(gecici, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(gecici, _durum_yolu())


def _indir(adres, zaman=8, en_cok=EN_BUYUK_ZIP):
    istek = urllib.request.Request(adres, headers={"User-Agent": "KlinikKoc-guncelleme"})
    with urllib.request.urlopen(istek, timeout=zaman) as y:  # noqa: S310 (sabit https adresi)
        veri = y.read(en_cok + 1)
    if len(veri) > en_cok:
        raise ValueError("İndirilen dosya beklenenden büyük.")
    return veri


def gelistirici_kopyasi():
    """Program klasörü bir git deposuysa güncelleme elle (git ile) yapılır; tek tuş dosyaların üzerine yazmaz."""
    return os.path.isdir(os.path.join(KOK, ".git"))


def denetle(zorla=False, indir=_indir):
    """{surum, tur, yeni_surum, var, denetim, hata?, son?} — internet yoksa var=False ve hata kısa bir cümledir."""
    d = _durum_oku()
    simdi = time.time()
    if zorla or simdi - float(d.get("denetim_zamani") or 0) > DENETIM_ARALIGI:
        d["denetim_zamani"] = simdi
        try:
            d["yeni_surum"] = indir(SURUM_ADRESI, 6, 200).decode("utf-8").strip()[:20]
            d.pop("hata", None)
        except Exception as e:  # internet yok, GitHub'a ulaşılamadı: sorun değil
            d["hata"] = "Yeni sürüme bakılamadı (internet yok olabilir): %s" % type(e).__name__
        try:
            _durum_yaz(d)
        except OSError:
            pass
    yeni = d.get("yeni_surum") or ""
    out = {"surum": surum(), "tur": tur(), "yeni_surum": yeni or None, "var": bool(yeni) and yeni_mi(yeni),
           "denetim": time.strftime("%Y-%m-%d %H:%M", time.localtime(d.get("denetim_zamani") or simdi)),
           "gelistirici": gelistirici_kopyasi()}
    if d.get("hata"):
        out["hata"] = d["hata"]
    if d.get("son"):
        out["son"] = d["son"]
    return out


def _korunan_mi(yol):
    yol = yol.replace("\\", "/")
    if "__pycache__" in yol.split("/") or yol.endswith(".pyc"):
        return True
    for k in KORUNAN:
        if k.endswith("/"):
            if (yol.rstrip("/") + "/").startswith(k):
                return True
        elif yol == k:
            return True
    return False


def program_dosyalari(kok=None):
    """Program klasöründeki, güncellemenin sorumlu olduğu dosyalar (korunan yerler dışında), göreli yollarla."""
    kok = kok or KOK
    out = []
    for klasor, altlar, dosyalar in os.walk(kok):
        goreli = os.path.relpath(klasor, kok).replace(os.sep, "/")
        goreli = "" if goreli == "." else goreli + "/"
        altlar[:] = [a for a in altlar if not _korunan_mi(goreli + a + "/")]
        for ad in dosyalar:
            if not _korunan_mi(goreli + ad):
                out.append(goreli + ad)
    return sorted(out)


def yedek_klasoru():
    return os.path.join(veri_yeri.veri_kok(), "surum-yedek")


def yedek_al(kok=None):
    kok = kok or KOK
    os.makedirs(yedek_klasoru(), exist_ok=True)
    yol = os.path.join(yedek_klasoru(), "klinikkoc-%s-%s.zip" % (_oku(os.path.join(kok, "SURUM"), "0"),
                                                               time.strftime("%Y%m%d-%H%M%S")))
    with zipfile.ZipFile(yol, "w", zipfile.ZIP_DEFLATED) as z:
        for d in program_dosyalari(kok):
            z.write(os.path.join(kok, d), d)
    eskiler = sorted(f for f in os.listdir(yedek_klasoru()) if f.startswith("klinikkoc-") and f.endswith(".zip"))
    for f in eskiler[:-YEDEK_SAYISI]:
        try:
            os.remove(os.path.join(yedek_klasoru(), f))
        except OSError:
            pass
    return yol


def _zip_icerigi(veri):
    """İndirilen zip'i doğrular; (ZipFile, üst klasör öneki, yeni sürüm, göreli dosya adları) döner."""
    z = zipfile.ZipFile(io.BytesIO(veri))
    adlar = [a for a in z.namelist() if not a.endswith("/")]
    ustler = {a.split("/", 1)[0] for a in adlar if "/" in a}
    if len(ustler) != 1 or any("/" not in a for a in adlar):
        raise ValueError("İndirilen dosya bir KlinikKoç sürümü değil.")
    onek = ustler.pop() + "/"
    goreli = [a[len(onek):] for a in adlar]
    for a in goreli:
        if a.startswith(("/", "\\")) or ".." in a.replace("\\", "/").split("/") or ":" in a:
            raise ValueError("İndirilen dosyada güvenli olmayan bir yol var.")
    for gerekli in ("SURUM", "tools/sunucu.py", "ana.html", "canli.html"):
        if gerekli not in goreli:
            raise ValueError("İndirilen dosya eksik (%s yok)." % gerekli)
    return z, onek, z.read(onek + "SURUM").decode("utf-8").strip(), goreli


def _yaz(kok, goreli, veri, calistirilabilir=False):
    hedef = os.path.join(kok, *goreli.split("/"))
    os.makedirs(os.path.dirname(hedef), exist_ok=True)
    gecici = hedef + ".yeni"
    with open(gecici, "wb") as f:
        f.write(veri)
    if calistirilabilir and os.name != "nt":
        os.chmod(gecici, 0o755)
    os.replace(gecici, hedef)


def _geri_don(kok, yedek):
    """Yedekteki dosyaları geri yazar; yedekte olmayan (yeni gelen) program dosyalarını siler."""
    with zipfile.ZipFile(yedek) as z:
        eski = set(z.namelist())
        for d in program_dosyalari(kok):
            if d not in eski:
                try:
                    os.remove(os.path.join(kok, *d.split("/")))
                except OSError:
                    pass
        for a in eski:
            _yaz(kok, a, z.read(a), a.endswith((".command", ".sh")))


def uygula(veri, kok=None, zorla=False):
    """İndirilmiş sürüm zip'ini program klasörüne kurar. Hata olursa yedekten geri döner ve hatayı yükseltir."""
    kok = kok or KOK
    z, onek, yeni, goreli = _zip_icerigi(veri)
    eski = _oku(os.path.join(kok, "SURUM"), "0")
    if not zorla and not yeni_mi(yeni, eski):
        return {"guncellendi": False, "surum": eski, "neden": "Zaten en yeni sürüm kurulu."}
    ogrenci = (os.environ.get("KLINIK_KOC_TUR") or _oku(os.path.join(kok, "SURUM-TURU"))).lower() == "ogrenci" \
        or (not os.path.isfile(os.path.join(kok, "sihirbaz.html")) and os.path.isfile(os.path.join(kok, "canli.html")))
    yazilacak = [a for a in goreli if not _korunan_mi(a) and not (ogrenci and a in OGRETMEN_DOSYALARI)]
    yedek = yedek_al(kok)
    try:
        for a in yazilacak:
            if a in AYAR_DOSYALARI and os.path.isfile(os.path.join(kok, *a.split("/"))):
                continue
            _yaz(kok, a, z.read(onek + a), a.endswith((".command", ".sh")))
        # Yeni sürümde artık olmayan eski program dosyaları kalmasın.
        yeni_kume = set(yazilacak)
        with zipfile.ZipFile(yedek) as y:
            for a in y.namelist():
                if a not in yeni_kume and a not in AYAR_DOSYALARI:
                    try:
                        os.remove(os.path.join(kok, *a.split("/")))
                    except OSError:
                        pass
        if _oku(os.path.join(kok, "SURUM")) != yeni:
            raise RuntimeError("Sürüm dosyası yazılamadı.")
    except Exception as e:
        _geri_don(kok, yedek)
        raise RuntimeError("Güncelleme yarıda kaldı, eski sürüme (%s) dönüldü: %s" % (eski, e))
    return {"guncellendi": True, "onceki": eski, "surum": yeni, "yedek": yedek, "dosya": len(yazilacak)}


def guncelle(indir=_indir, zorla=False):
    """Tek tuş: indir, yedekle, kur. Sonuç guncelleme.json'a da yazılır (ana ekran gösterir)."""
    if gelistirici_kopyasi():
        raise RuntimeError("Bu klasör bir geliştirici kopyası (git deposu); güncelleme 'git pull' ile yapılır.")
    veri = indir(ZIP_ADRESI, 120)
    r = uygula(veri, zorla=zorla)
    d = _durum_oku()
    d["son"] = dict(r, tarih=time.strftime("%Y-%m-%d %H:%M"))
    if r.get("guncellendi"):
        d["yeni_surum"] = r["surum"]
    _durum_yaz(d)
    return r


def geri_al():
    """Son yedeğe döner (güncellemeden sonra bir sorun çıkarsa)."""
    if gelistirici_kopyasi():
        raise RuntimeError("Geliştirici kopyasında geri alma yapılmaz.")
    try:
        eskiler = sorted(f for f in os.listdir(yedek_klasoru()) if f.startswith("klinikkoc-") and f.endswith(".zip"))
    except OSError:
        eskiler = []
    if not eskiler:
        raise FileNotFoundError("Geri dönülecek bir yedek yok.")
    yedek = os.path.join(yedek_klasoru(), eskiler[-1])
    simdiki = surum()
    _geri_don(KOK, yedek)
    d = _durum_oku()
    d["son"] = {"guncellendi": False, "geri_alindi": True, "onceki": simdiki, "surum": surum(),
                "tarih": time.strftime("%Y-%m-%d %H:%M")}
    _durum_yaz(d)
    return d["son"]


def ogrenci_surumu_yap(klasor):
    """Bir program kopyasını öğrenci sürümüne çevirir (paketleme için): öğretmen dosyalarını siler, türü yazar."""
    for a in OGRETMEN_DOSYALARI:
        try:
            os.remove(os.path.join(klasor, *a.split("/")))
        except OSError:
            pass
    with open(os.path.join(klasor, "SURUM-TURU"), "w", encoding="utf-8") as f:
        f.write("ogrenci\n")
    return klasor


def indirme_paketleri(cikis, kok=None):
    """İki indirme dosyasını üretir: klinikkoc-<sürüm>-ogretmen.zip ve klinikkoc-<sürüm>-ogrenci.zip.

    Kaynak, git deposunun son kaydıdır (git archive): örnek dersler ve kurulu dersler pakete girmez.
    Öğrenci paketi aynı dosyalardan öğretmen dosyaları çıkarılıp SURUM-TURU eklenerek yazılır."""
    import subprocess
    kok = kok or KOK
    os.makedirs(cikis, exist_ok=True)
    s = _oku(os.path.join(kok, "SURUM")).strip() or "0"
    ust = "klinikkoc-%s" % s
    ogretmen = os.path.join(cikis, ust + "-ogretmen.zip")
    ogrenci = os.path.join(cikis, ust + "-ogrenci.zip")
    subprocess.run(["git", "-C", kok, "archive", "--format=zip", "--prefix=%s/" % ust, "-o", ogretmen, "HEAD"], check=True)
    atla = {"%s/%s" % (ust, a) for a in OGRETMEN_DOSYALARI}
    with zipfile.ZipFile(ogretmen) as kaynak, zipfile.ZipFile(ogrenci, "w", zipfile.ZIP_DEFLATED) as hedef:
        for b in kaynak.infolist():
            if b.filename in atla:
                continue
            hedef.writestr(b, kaynak.read(b.filename))  # ZipInfo ile: çalıştırma izinleri (.command) korunur
        hedef.writestr("%s/SURUM-TURU" % ust, "ogrenci\n")
    return {"ogretmen": ogretmen, "ogrenci": ogrenci}


def main():
    import argparse
    ap = argparse.ArgumentParser(description="KlinikKoç sürüm ve güncelleme")
    ap.add_argument("--denetle", action="store_true", help="yeni sürüm var mı?")
    ap.add_argument("--guncelle", action="store_true", help="yeni sürümü indir ve kur")
    ap.add_argument("--geri-al", action="store_true", help="son yedeğe dön")
    ap.add_argument("--ogrenci-surumu", metavar="KLASOR", help="klasördeki kopyayı öğrenci sürümüne çevir")
    ap.add_argument("--paketler", metavar="KLASOR", help="öğretmen ve öğrenci indirme zip'lerini bu klasöre yaz")
    a = ap.parse_args()
    if a.paketler:
        print(json.dumps(indirme_paketleri(a.paketler), ensure_ascii=False, indent=1))
    elif a.ogrenci_surumu:
        print(ogrenci_surumu_yap(a.ogrenci_surumu))
    elif a.guncelle:
        print(json.dumps(guncelle(), ensure_ascii=False, indent=1))
    elif a.geri_al:
        print(json.dumps(geri_al(), ensure_ascii=False, indent=1))
    else:
        print(json.dumps(denetle(zorla=a.denetle), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
