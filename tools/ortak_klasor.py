#!/usr/bin/env python3
"""Ortak veri klasörü: iki bilgisayarda (ör. Mac ve Windows) aynı kayıtlar ve makalelerle çalışmak için.

Kullanıcı bir bulut klasörü seçer (OneDrive, Google Drive, iCloud Drive, Dropbox). İçinde "KlinikKoç Ortak"
klasörü açılır; öğrenci kayıtları (kayitlar/), makale PDF'leri (Makaleler/) ve makale durumları (makaleler/)
oraya taşınır. Her bilgisayar kendi ayarlarını, arama dizinini, seslerini ve programını ayrı tutar.

Kilit ve uyarı: tahta ya da ana ekran açıkken bu bilgisayar ortak klasördeki kilit.json'a "buradayım" yazar
(dakikada bir tazelenir). Başka bir bilgisayarın kilidi tazeyse (son 3 dakika) ana ekran ve Claude uyarır:
aynı anda iki bilgisayarda çalışmak kayıtları çakıştırabilir. Kilit engel değildir; yalnız uyarır.
Bulut eşitlemesi gecikebilir; bir bilgisayarda bitirdikten sonra eşitlemenin tamamlanmasını beklemek gerekir.

Taşıma hiçbir şeyi silmez: ayarlarken bu bilgisayardaki veriler ortak klasöre kopyalanır (aynı dosya ikisinde
de varsa yenisi kalır, eskisi yedek zip'te durur); kapatırken ortak klasördeki veriler buraya geri kopyalanır.

Kullanım:
  python tools/ortak_klasor.py --durum
  python tools/ortak_klasor.py --adaylar
  python tools/ortak_klasor.py --ayarla "<bulut klasörü>"
  python tools/ortak_klasor.py --kapat
Yalnız Python'un kendi kitaplığını kullanır.
"""
import argparse
import glob
import json
import os
import platform
import shutil
import sys
import time
import uuid
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import veri_yeri  # noqa: E402

ALT_KLASOR = "KlinikKoç Ortak"
KILIT_ADI = "kilit.json"
KILIT_TAZE = 180          # saniye: bundan yeni kilit "o bilgisayar şu an açık" sayılır
KILIT_ARALIGI = 60        # saniye: kilit en çok bu sıklıkla tazelenir
OTURUM = uuid.uuid4().hex[:12]
_SON_TAZELEME = [0.0]


def bilgisayar_adi():
    return platform.node() or "bu bilgisayar"


# ---------- Bulut klasörü adayları ----------
def adaylar():
    """Bu bilgisayarda bulunan bulut klasörleri: [{ad, yol}]."""
    ev = os.path.expanduser("~")
    out = []

    def ekle(ad, yol):
        if yol and os.path.isdir(yol) and all(os.path.realpath(yol) != os.path.realpath(x["yol"]) for x in out):
            out.append({"ad": ad, "yol": yol})

    for degisken in ("OneDriveCommercial", "OneDriveConsumer", "OneDrive"):
        ekle("OneDrive", os.environ.get(degisken))
    for y in sorted(glob.glob(os.path.join(ev, "OneDrive*"))):
        ekle("OneDrive", y)
    ekle("iCloud Drive", os.path.join(ev, "Library", "Mobile Documents", "com~apple~CloudDocs"))
    ekle("iCloud Drive", os.path.join(ev, "iCloudDrive"))  # Windows için iCloud
    bulut = os.path.join(ev, "Library", "CloudStorage")  # macOS: Google Drive, OneDrive, Dropbox burada
    for y in sorted(glob.glob(os.path.join(bulut, "*"))):
        ad = os.path.basename(y).split("-")[0]
        ic = [os.path.join(y, "My Drive"), os.path.join(y, "Drive'ım"), os.path.join(y, "Il mio Drive")]
        ekle({"GoogleDrive": "Google Drive"}.get(ad, ad), next((i for i in ic if os.path.isdir(i)), y))
    for y in (os.path.join(ev, "Google Drive", "My Drive"), os.path.join(ev, "Google Drive"),
              os.path.join(ev, "My Drive")):
        ekle("Google Drive", y)
    if os.name == "nt":
        for harf in "GHIJKLMNOPQRSTUVWXYZ":
            for ic in ("My Drive", "Drive'ım"):
                ekle("Google Drive", "%s:\\%s" % (harf, ic))
    ekle("Dropbox", os.path.join(ev, "Dropbox"))
    return out


# ---------- Kopyalama ----------
def _birlestir(kaynak, hedef, yenisi_kalsin=True):
    """kaynak klasördeki dosyaları hedefe kopyalar. Hedefte yoksa kopyalanır; varsa ve farklıysa yenisi kalır
    (yenisi_kalsin) ya da dokunulmaz. Hiçbir şey silinmez. (kopyalanan, üzerine_yazilan) sayısı döner."""
    kopya = ustune = 0
    if not os.path.isdir(kaynak):
        return 0, 0
    for kok, dizinler, dosyalar in os.walk(kaynak):
        dizinler[:] = [d for d in dizinler if d not in ("__pycache__",)]
        for f in dosyalar:
            if f.endswith((".yaziliyor", ".iniyor", ".gecici")) or f == KILIT_ADI:
                continue
            k = os.path.join(kok, f)
            h = os.path.join(hedef, os.path.relpath(k, kaynak))
            try:
                if not os.path.exists(h):
                    os.makedirs(os.path.dirname(h), exist_ok=True)
                    shutil.copy2(k, h)
                    kopya += 1
                elif yenisi_kalsin and os.path.getmtime(k) > os.path.getmtime(h) + 1 and (
                        os.path.getsize(k) != os.path.getsize(h) or _farkli(k, h)):
                    shutil.copy2(k, h)
                    ustune += 1
            except OSError:
                continue
    return kopya, ustune


def _farkli(a, b):
    with open(a, "rb") as x, open(b, "rb") as y:
        return x.read() != y.read()


def _yedek_zip(kaynaklar, ad):
    """Taşımadan önce bu bilgisayardaki kayıtların ve makale durumlarının yedeği (PDF'ler hariç)."""
    klasor = os.path.join(veri_yeri.veri_kok(), "ortak-yedek")
    os.makedirs(klasor, exist_ok=True)
    yol = os.path.join(klasor, "%s-%s.zip" % (ad, time.strftime("%Y%m%d-%H%M%S")))
    with zipfile.ZipFile(yol, "w", zipfile.ZIP_DEFLATED) as z:
        for etiket, k in kaynaklar:
            for kok, _, dosyalar in os.walk(k):
                for f in dosyalar:
                    tam = os.path.join(kok, f)
                    z.write(tam, os.path.join(etiket, os.path.relpath(tam, k)).replace(os.sep, "/"))
    return yol


def _yerel_yerler():
    v = veri_yeri.veri_kok()
    return {"kayitlar": os.path.join(v, "kayitlar"), "makaleler": os.path.join(v, "makaleler"),
            "Makaleler": veri_yeri.yerel_makale_kok()}


def _ortak_yerler(ortak):
    return {"kayitlar": os.path.join(ortak, "kayitlar"), "makaleler": os.path.join(ortak, "makaleler"),
            "Makaleler": os.path.join(ortak, "Makaleler")}


def _ayar_yaz(yol):
    ayar = os.path.join(veri_yeri.veri_kok(), veri_yeri.ORTAK_AYAR_ADI)
    os.makedirs(os.path.dirname(ayar), exist_ok=True)
    if yol is None:
        if os.path.exists(ayar):
            os.remove(ayar)
        return
    with open(ayar + ".yaziliyor", "w", encoding="utf-8") as f:
        json.dump({"yol": yol, "secildi": time.strftime("%Y-%m-%d %H:%M"), "bilgisayar": bilgisayar_adi()},
                  f, ensure_ascii=False, indent=1)
    os.replace(ayar + ".yaziliyor", ayar)


# ---------- Ayarlama / kapatma ----------
def ayarla(bulut):
    """Bulut klasörünü (ya da içindeki KlinikKoç Ortak klasörünü) ortak klasör yapar ve bu bilgisayarın
    verisini oraya kopyalar. Öbür bilgisayar aynı klasörü seçince iki tarafın verisi birleşir."""
    if os.environ.get("KLINIK_KOC_KAYIT") or os.environ.get("KLINIK_KOC_MAKALE"):
        raise ValueError("Kayıt/makale yeri ortam değişkeniyle sabitlenmiş; ortak klasör kullanılamaz.")
    bulut = os.path.abspath(os.path.expanduser((bulut or "").strip().strip('"')))
    if not os.path.isdir(bulut):
        raise ValueError("Klasör bulunamadı: %s" % bulut)
    hedef = bulut if os.path.basename(bulut) == ALT_KLASOR else os.path.join(bulut, ALT_KLASOR)
    yerel = os.path.realpath(veri_yeri.veri_kok())
    if os.path.realpath(hedef).startswith(yerel + os.sep) or os.path.realpath(hedef) == yerel:
        raise ValueError("Ortak klasör programın kendi veri klasörünün içinde olamaz.")
    os.makedirs(hedef, exist_ok=True)
    deneme = os.path.join(hedef, ".yazma-denemesi")
    try:
        with open(deneme, "w") as f:
            f.write("ok")
        os.remove(deneme)
    except OSError as e:
        raise ValueError("Bu klasöre yazılamıyor: %s" % e)
    onceki = veri_yeri.ortak_klasor()
    kaynak = _ortak_yerler(onceki) if onceki else _yerel_yerler()
    yedek = _yedek_zip([("kayitlar", kaynak["kayitlar"]), ("makaleler", kaynak["makaleler"])], "ortaga-tasima-oncesi")
    sayilar = {}
    for ad, k in kaynak.items():
        sayilar[ad] = _birlestir(k, _ortak_yerler(hedef)[ad])
    _ayar_yaz(hedef)
    with open(os.path.join(hedef, "BENİOKU.txt"), "w", encoding="utf-8") as f:
        f.write("Bu klasör KlinikKoç'un ortak veri klasörüdür (öğrenci kayıtları ve makaleler).\n"
                "İçindeki dosyaları elle değiştirmeyin. Aynı anda iki bilgisayarda çalışmayın: bir bilgisayarda bitirip\n"
                "bulut eşitlemesi tamamlanınca öbüründe açın.\n")
    kilit_tazele(zorla=True)
    return {"ortak_klasor": hedef, "yedek": yedek,
            "kopyalanan": {a: b[0] for a, b in sayilar.items()}, "guncellenen": {a: b[1] for a, b in sayilar.items()}}


def kapat():
    """Ortak klasörü bırakır: oradaki veriler bu bilgisayara kopyalanır (ortak klasördekiler silinmez)."""
    ortak = veri_yeri.ortak_klasor()
    ayar = veri_yeri.ortak_ayari()
    if not ayar:
        return {"durum": "zaten kapalı"}
    sayilar = {}
    if ortak:
        kilit_birak()
        for ad, k in _ortak_yerler(ortak).items():
            sayilar[ad] = _birlestir(k, _yerel_yerler()[ad])
    _ayar_yaz(None)
    return {"durum": "kapatıldı", "ortak_klasor": ayar, "erisilebilir_miydi": bool(ortak),
            "geri_kopyalanan": {a: b[0] for a, b in sayilar.items()}}


# ---------- Kilit ----------
def _kilit_yolu(ortak=None):
    ortak = ortak or veri_yeri.ortak_klasor()
    return os.path.join(ortak, KILIT_ADI) if ortak else None


def _kilit_oku(yol):
    try:
        with open(yol, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def kilit_tazele(zorla=False):
    """Bu bilgisayar ortak klasörü kullanıyor: kilidi tazeler (en çok dakikada bir). Başka bilgisayarın taze kilidi
    varsa üzerine yazmaz (o bilgisayar kapanınca ya da kilidi bayatlayınca bu bilgisayar alır)."""
    yol = _kilit_yolu()
    simdi = time.time()
    if not yol or (not zorla and simdi - _SON_TAZELEME[0] < KILIT_ARALIGI):
        return
    _SON_TAZELEME[0] = simdi
    d = _kilit_oku(yol)
    if d and d.get("bilgisayar") != bilgisayar_adi() and simdi - float(d.get("zaman") or 0) < KILIT_TAZE:
        return
    try:
        with open(yol + ".yaziliyor", "w", encoding="utf-8") as f:
            json.dump({"bilgisayar": bilgisayar_adi(), "oturum": OTURUM, "zaman": simdi,
                       "saat": time.strftime("%Y-%m-%d %H:%M")}, f, ensure_ascii=False)
        os.replace(yol + ".yaziliyor", yol)
    except OSError:
        pass


def kilit_birak():
    yol = _kilit_yolu()
    if yol and _kilit_oku(yol).get("bilgisayar") == bilgisayar_adi():
        try:
            os.remove(yol)
        except OSError:
            pass


def durum():
    """Ana ekran ve Claude için: ortak klasör açık mı, erişilebilir mi, başka bilgisayar şu an kullanıyor mu."""
    ayar = veri_yeri.ortak_ayari()
    out = {"acik": bool(ayar), "yol": ayar, "bilgisayar": bilgisayar_adi(), "kayit_yeri": veri_yeri.kayit_kok(),
           "makale_yeri": veri_yeri.makale_kok()}
    if not ayar:
        return out
    ortak = veri_yeri.ortak_klasor()
    out["erisilebilir"] = bool(ortak)
    if not ortak:
        out["uyari"] = ("Ortak klasöre şu an ulaşılamıyor (%s). Bulut uygulaması kapalı ya da sürücü bağlı değil olabilir. "
                        "Bu sırada yapılan çalışma yalnız bu bilgisayara kaydedilir ve öbür bilgisayara geçmez. "
                        "Bulut uygulamasını açıp programı yeniden başlatın." % ayar)
        return out
    d = _kilit_oku(_kilit_yolu(ortak))
    if d and d.get("bilgisayar") != bilgisayar_adi() and time.time() - float(d.get("zaman") or 0) < KILIT_TAZE:
        out["baska_bilgisayar"] = {"ad": d.get("bilgisayar"), "son_etkinlik": d.get("saat")}
        out["uyari"] = ("KlinikKoç şu an \"%s\" bilgisayarında da açık görünüyor (son etkinlik %s). Aynı anda iki "
                        "bilgisayarda çalışırsanız kayıtlar çakışabilir. Öbür bilgisayarda tahtayı kapatın ve bulut "
                        "eşitlemesinin bitmesini bekleyin." % (d.get("bilgisayar"), d.get("saat")))
    return out


def main():
    ap = argparse.ArgumentParser(description="KlinikKoç ortak veri klasörü")
    ap.add_argument("--durum", action="store_true")
    ap.add_argument("--adaylar", action="store_true")
    ap.add_argument("--ayarla", metavar="KLASOR")
    ap.add_argument("--kapat", action="store_true")
    a = ap.parse_args()
    if a.ayarla:
        sonuc = ayarla(a.ayarla)
    elif a.kapat:
        sonuc = kapat()
    elif a.adaylar:
        sonuc = adaylar()
    else:
        sonuc = durum()
    print(json.dumps(sonuc, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
