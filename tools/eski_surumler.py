#!/usr/bin/env python3
"""Bilgisayardaki eski KlinikKoç (ve eski akıllı tahta) klasörlerini bulur; kullanıcı onaylarsa yedekleyip siler.

Hiçbir şey kendiliğinden silinmez. Akış:
  1. bul()     Belgeler, Masaüstü, İndirilenler ve ev klasöründe (en çok 4 kat derinlikte) tools/tahta-mcp.py
               bulunan klasörleri listeler: sürüm, boyut, son değişiklik, içindeki dersler, yeni kurulumda
               olmayan dersler, Claude'un bu klasörü kullanıp kullanmadığı.
  2. temizle() Yalnız açıkça verilen klasörler için: (a) yeni kurulumda olmayan dersleri buraya kopyalar,
               (b) klasörün yedeğini Belgeler/KlinikKoç Yedekler/ içine zip olarak alır (yeniden indirilebilen
               ses ortamı, model ve dizin hariç), (c) yedek doğrulanınca klasörü siler.
               Çalışan kurulum ve Claude'un kullandığı klasör hiçbir zaman silinmez.

Kullanım:
  python tools/eski_surumler.py --listele
  python tools/eski_surumler.py --sor          (kurulum betiği: her klasör için E/H sorar)
  python tools/eski_surumler.py --sil "<klasör>" ["<klasör>" ...]

Yalnız Python'un kendi kitaplığını kullanır.
"""
import argparse
import json
import os
import shutil
import sys
import time
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import veri_yeri  # noqa: E402

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DERINLIK = 4
ATLA = {"node_modules", "AppData", "Library", "Applications", ".git", ".ses-ortami", ".modeller", ".dizin",
        "__pycache__", "vendor", "lessons", "ozel", "kayitlar", "$RECYCLE.BIN", "OneDriveTemp", "Pictures",
        "Music", "Movies", "Videos", "Resimler", "Müzik", "Filmler", "Videolar"}
YEDEGE_GIRMEZ = (".ses-ortami", ".modeller", ".dizin", "__pycache__", "tools/.sesler", ".git")


def _gercek(yol):
    return os.path.normcase(os.path.realpath(yol))


def arama_kokleri():
    ev = os.path.expanduser("~")
    adaylar = [veri_yeri.belgeler(), veri_yeri.masaustu(), veri_yeri.indirilenler(), ev]
    if os.environ.get("OneDrive"):
        adaylar.append(os.environ["OneDrive"])
    out = []
    for a in adaylar:
        if a and os.path.isdir(a) and _gercek(a) not in {_gercek(x) for x in out}:
            out.append(a)
    return out


def _imza_mi(klasor):
    return os.path.isfile(os.path.join(klasor, "tools", "tahta-mcp.py"))


def _klasorleri_tara(kokler, derinlik=DERINLIK):
    goruldu, out = set(), []
    for kok in kokler:
        yigin = [(kok, 0)]
        while yigin:
            yol, d = yigin.pop()
            g = _gercek(yol)
            if g in goruldu:
                continue
            goruldu.add(g)
            if _imza_mi(yol):
                out.append(yol)
                continue  # bir kurulumun içine inilmez
            if d >= derinlik:
                continue
            try:
                girdiler = list(os.scandir(yol))
            except OSError:
                continue
            for e in girdiler:
                try:
                    if e.is_dir(follow_symlinks=False) and not e.name.startswith(".") and e.name not in ATLA:
                        yigin.append((e.path, d + 1))
                except OSError:
                    continue
    return out


def _boyut(klasor):
    toplam = 0
    for kok, dizinler, dosyalar in os.walk(klasor):
        for f in dosyalar:
            try:
                toplam += os.path.getsize(os.path.join(kok, f))
            except OSError:
                pass
    return toplam


def _son_degisim(klasor):
    en = 0
    for ad in ("SURUM", "config.js", "canli.html", os.path.join("tools", "tahta-mcp.py")):
        try:
            en = max(en, os.path.getmtime(os.path.join(klasor, ad)))
        except OSError:
            pass
    return en


def _dersler(klasor):
    d = os.path.join(klasor, "lessons")
    try:
        return sorted(x for x in os.listdir(d) if os.path.isdir(os.path.join(d, x)) and not x.startswith("."))
    except OSError:
        return []


def _claude_kullaniyor():
    """Claude ayar dosyalarında tahta-mcp.py'si kayıtlı klasörler."""
    out = set()
    try:
        import claude_ayari
        for yol in claude_ayari.ayar_dosyalari():
            try:
                with open(yol, encoding="utf-8") as f:
                    sunucular = (json.load(f) or {}).get("mcpServers") or {}
            except (OSError, ValueError):
                continue
            for g in sunucular.values():
                for arg in (g or {}).get("args") or []:
                    if str(arg).endswith("tahta-mcp.py"):
                        out.add(_gercek(os.path.dirname(os.path.dirname(str(arg)))))
    except Exception:
        pass
    return out


def _tanim(klasor):
    surum = None
    try:
        with open(os.path.join(klasor, "SURUM"), encoding="utf-8") as f:
            surum = f.read().strip()
    except OSError:
        pass
    if surum:
        return "KlinikKoç " + surum, surum
    if os.path.exists(os.path.join(klasor, "ana.html")) or os.path.exists(os.path.join(klasor, "kilavuz.html")):
        return "KlinikKoç (sürümü yazmıyor, 3.x ya da öncesi)", None
    return "Akıllı tahta (KlinikKoç'tan önceki program)", None


def bul(kokler=None, kendisi=KOK):
    kendi = _gercek(kendisi)
    kullanilan = _claude_kullaniyor()
    yeni_dersler = set(_dersler(kendisi))
    out = []
    for k in _klasorleri_tara(kokler or arama_kokleri()):
        if _gercek(k) == kendi:
            continue
        ad, surum = _tanim(k)
        dersler = _dersler(k)
        out.append({
            "yol": k, "ad": ad, "surum": surum,
            "boyut_mb": round(_boyut(k) / 1048576, 1),
            "son_degisim": time.strftime("%Y-%m-%d", time.localtime(_son_degisim(k))) if _son_degisim(k) else None,
            "dersler": dersler,
            "yeni_kurulumda_olmayan_dersler": [d for d in dersler if d not in yeni_dersler],
            "kayit_var": os.path.isdir(os.path.join(k, "kayitlar")),
            "claude_kullaniyor": _gercek(k) in kullanilan,
        })
    out.sort(key=lambda x: x["son_degisim"] or "")
    return out


def yedek_klasoru():
    return os.path.join(veri_yeri.belgeler(), "KlinikKoç Yedekler")


def _yedege_girer(goreli):
    g = goreli.replace(os.sep, "/")
    return not any(g == x or g.startswith(x + "/") or ("/" + x + "/") in ("/" + g + "/") for x in YEDEGE_GIRMEZ)


def yedekle(klasor, hedef_klasor=None):
    hedef_klasor = hedef_klasor or yedek_klasoru()
    os.makedirs(hedef_klasor, exist_ok=True)
    ad = "eski-surum-%s-%s.zip" % (os.path.basename(os.path.normpath(klasor)).replace(" ", "-"),
                                   time.strftime("%Y%m%d-%H%M%S"))
    hedef = os.path.join(hedef_klasor, ad)
    sayi = 0
    with zipfile.ZipFile(hedef + ".yaziliyor", "w", zipfile.ZIP_DEFLATED) as z:
        for kok, dizinler, dosyalar in os.walk(klasor):
            goreli_kok = os.path.relpath(kok, klasor)
            dizinler[:] = [d for d in dizinler if _yedege_girer(os.path.normpath(os.path.join(goreli_kok, d)))]
            for f in dosyalar:
                goreli = os.path.normpath(os.path.join(goreli_kok, f))
                if not _yedege_girer(goreli):
                    continue
                try:
                    z.write(os.path.join(kok, f), goreli.replace(os.sep, "/"))
                    sayi += 1
                except OSError:
                    pass
    with zipfile.ZipFile(hedef + ".yaziliyor") as z:  # yedek okunamıyorsa silme yapılmaz
        if z.testzip() is not None or len(z.namelist()) != sayi:
            raise RuntimeError("yedek doğrulanamadı")
    os.replace(hedef + ".yaziliyor", hedef)
    return hedef, sayi


def _salt_okunuru_sil(islev, yol, _):
    """Windows'ta salt okunur dosyalar (ör. .git içindekiler) rmtree'yi durdurmasın."""
    import stat
    os.chmod(yol, stat.S_IWRITE)
    islev(yol)


def temizle(klasorler, dersleri_aktar=True, kendisi=KOK, kokler=None, yedek_yeri=None):
    """Verilen klasörleri (yalnız bul()'un da bulduğu eski kurulumları) yedekleyip siler."""
    bilinen = {_gercek(x["yol"]): x for x in bul(kokler, kendisi)}
    sonuc = []
    for k in klasorler:
        g = _gercek(k)
        x = bilinen.get(g)
        if not x:
            sonuc.append({"yol": k, "durum": "atlandı", "neden": "eski KlinikKoç klasörü olarak bulunmadı"})
            continue
        if x["claude_kullaniyor"]:
            sonuc.append({"yol": k, "durum": "atlandı",
                          "neden": "Claude bu klasörü kullanıyor; önce yeni kurulumda KUR'u çalıştırın"})
            continue
        try:
            aktarilan = []
            if dersleri_aktar:
                for d in x["yeni_kurulumda_olmayan_dersler"]:
                    shutil.copytree(os.path.join(k, "lessons", d), os.path.join(kendisi, "lessons", d))
                    aktarilan.append(d)
            yedek, sayi = yedekle(k, yedek_yeri)
            if sys.version_info >= (3, 12):
                shutil.rmtree(k, onexc=_salt_okunuru_sil)
            else:
                shutil.rmtree(k, onerror=_salt_okunuru_sil)
            sonuc.append({"yol": k, "durum": "silindi", "yedek": yedek, "yedekteki_dosya": sayi,
                          "aktarilan_dersler": aktarilan})
        except Exception as e:
            sonuc.append({"yol": k, "durum": "hata", "neden": str(e)})
    return sonuc


def _yaz(x):
    print("  %s\n    %s\n    %s MB, son değişiklik %s%s%s" % (
        x["ad"], x["yol"], x["boyut_mb"], x["son_degisim"] or "?",
        ("\n    Bu klasördeki dersler yeni kuruluma taşınacak: " + ", ".join(x["yeni_kurulumda_olmayan_dersler"]))
        if x["yeni_kurulumda_olmayan_dersler"] else "",
        "\n    Claude bu klasörü kullanıyor: silinemez." if x["claude_kullaniyor"] else ""))


def main():
    ap = argparse.ArgumentParser(description="Eski KlinikKoç klasörlerini bul, onayla yedekleyip sil")
    ap.add_argument("--listele", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--sor", action="store_true", help="her eski klasör için E/H sor")
    ap.add_argument("--sil", nargs="+", metavar="KLASOR")
    a = ap.parse_args()
    if a.sil:
        print(json.dumps(temizle(a.sil), ensure_ascii=False, indent=1))
        return
    eski = bul()
    if a.json:
        print(json.dumps(eski, ensure_ascii=False, indent=1))
        return
    if not eski:
        print("Eski KlinikKoç klasörü bulunmadı.")
        return
    print("Bu bilgisayarda %d eski klasör bulundu:" % len(eski))
    for x in eski:
        _yaz(x)
    if not a.sor:
        return
    print("\nSilmeden önce her klasörün yedeği şuraya alınır: " + yedek_klasoru())
    print("(Yedekte dersleriniz, kayıtlarınız ve notlarınız durur; yalnız yeniden indirilebilen ses/model dosyaları girmez.)")
    for x in eski:
        if x["claude_kullaniyor"]:
            continue
        try:
            cevap = input("\nSilinsin mi?  %s\n  %s\n(E/H) " % (x["ad"], x["yol"])).strip().lower()
        except EOFError:
            return
        if cevap[:1] in ("e", "y"):
            for s in temizle([x["yol"]]):
                if s["durum"] == "silindi":
                    print("  Silindi. Yedek: " + s["yedek"])
                    if s["aktarilan_dersler"]:
                        print("  Yeni kuruluma taşınan dersler: " + ", ".join(s["aktarilan_dersler"]))
                else:
                    print("  Silinmedi: " + s.get("neden", s["durum"]))
        else:
            print("  Dokunulmadı.")


if __name__ == "__main__":
    main()
