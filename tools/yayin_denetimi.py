#!/usr/bin/env python3
"""Açık depoya yüklemeden önce güvenlik denetimi: özel içerik yanlışlıkla yayımlanmasın.

  python tools/yayin_denetimi.py          denetler; sorun varsa çıkış kodu 1
  python tools/yayin_denetimi.py --kanca  bu depoya git "pre-commit" kancası kurar: her commit'ten
                                          önce denetim kendiliğinden çalışır, sorun varsa commit durur

Engellenenler:
  - fakülteye özel dersler (ders.json "distribution": "faculty" ya da egitmen.json "dagitim": "fakulte")
  - fakülteye özel ya da denetimden geçmeyen vaka kartları
  - öğrenci kayıtları (kayitlar/), özel klasör (ozel/), arama dizini ve modeller
  - lisansı belirtilmemiş ders ve kaynak bilgisi olmayan ders görselleri
  - 20 MB'tan büyük dosyalar
Git yoksa klasördeki bütün dosyalara, git varsa yalnız depoya girecek dosyalara bakılır.
"""
import glob
import json
import re
import os
import subprocess
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KOK, "tools"))
import vaka_denetle  # noqa: E402

YASAK_KLASORLER = ("kayitlar/", "ozel/", ".dizin/", ".modeller/", ".ses-ortami/", "tools/.sesler/")
EN_BUYUK = 20 * 1024 * 1024


def depo_dosyalari():
    """Commit'e girecek dosyalar: izlenen + eklenmiş, git'in yok saydıkları hariç."""
    try:
        r = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=KOK,
                           capture_output=True, text=True, check=True)
        return [x for x in r.stdout.splitlines() if x and os.path.exists(os.path.join(KOK, x))]
    except (OSError, subprocess.CalledProcessError):
        out = []
        for kok, klasorler, dosyalar in os.walk(KOK):
            klasorler[:] = [k for k in klasorler if k not in (".git", "__pycache__", "node_modules")]
            out += [os.path.relpath(os.path.join(kok, d), KOK).replace(os.sep, "/") for d in dosyalar]
        return out


def denetle():
    H, U = [], []
    dosyalar = depo_dosyalari()
    kume = set(dosyalar)
    for d in dosyalar:
        if d.startswith(YASAK_KLASORLER):
            H.append("Depoya girmemeli: %s" % d)
        try:
            if os.path.getsize(os.path.join(KOK, d)) > EN_BUYUK:
                H.append("20 MB'tan büyük dosya: %s" % d)
        except OSError:
            pass

    for klasor in sorted(glob.glob(os.path.join(KOK, "lessons", "*", ""))):
        ders = os.path.basename(os.path.dirname(klasor))
        on = "lessons/%s/" % ders
        if not any(x.startswith(on) for x in kume):
            continue  # derse ait hiçbir dosya depoya girmiyor (ör. .gitignore ile dışarıda)
        dj = os.path.join(klasor, "ders.json")
        ej = os.path.join(klasor, "egitmen.json")
        d = json.load(open(dj, encoding="utf-8")) if os.path.exists(dj) else {}
        e = json.load(open(ej, encoding="utf-8")) if os.path.exists(ej) else {}
        if d.get("distribution") == "faculty" or e.get("dagitim") == "fakulte":
            H.append("Fakülteye özel ders depoya giriyor: %s (klasörün adını ozel-... ile başlatın; o zaman depoya hiç girmez)" % on)
            continue
        if d and not (d.get("source") or {}).get("license"):
            H.append("%sders.json: source.license (içerik lisansı) yazılmamış" % on)
        for k, a in (d.get("assets") or {}).items():
            if not a.get("credit"):
                U.append("%s görsel %s: credit (kaynak ve lisans) yazılmamış" % (on, k))
        for v in sorted(glob.glob(os.path.join(klasor, "vakalar", "*.json"))):
            rel = os.path.relpath(v, KOK).replace(os.sep, "/")
            if rel not in kume:
                continue
            hatalar, _, kart = vaka_denetle.denetle(v)
            if hatalar:
                H.append("Vaka kartı denetimden geçmiyor: %s (python tools/vaka_denetle.py %s)" % (rel, rel))
            if kart and kart.get("dagitim") != "acik":
                H.append("Fakülteye özel vaka depoya giriyor: %s (dosya adını ozel-... ile başlatın)" % rel)
            if kart and kart.get("kurgusal") is not True:
                U.append("Gerçek hastadan uyarlanmış vaka açık depoda: %s — öğretmen onayı ve anonimlik kaydını "
                         "yeniden gözden geçirin" % rel)
        # Oynatıcının vaka paketi (paketle.mjs üretir): --fakulte sonrası özel kart içermemeli
        for paket in ("vaka-paketi.json", "vaka-paketi.js"):
            rel = on + paket
            yol = os.path.join(klasor, paket)
            if rel not in kume or not os.path.exists(yol):
                continue
            metin = open(yol, encoding="utf-8").read()
            if re.search(r'"dagitim"\s*:\s*"fakulte"', metin) or re.search(r'"id"\s*:\s*"ozel-', metin):
                H.append("%s fakülteye özel vaka içeriyor: 'node tools/paketle.mjs' (--fakulte olmadan) çalıştırın" % rel)
        # Vaka görselleri yalnız denetimden geçmiş bir karta bağlıysa yayımlanabilir
        bagli = set()
        for v in glob.glob(os.path.join(klasor, "vakalar", "*.json")):
            try:
                kart = json.load(open(v, encoding="utf-8"))
            except ValueError:
                continue
            bagli |= {b.get("gorsel") for b in kart.get("bulgular") or [] if b.get("gorsel")}
        for x in kume:
            if x.startswith(on + "vakalar/") and not x.endswith(".json"):
                if x[len(on):] not in bagli:
                    H.append("Hiçbir vaka kartına bağlı olmayan vaka görseli: %s" % x)
    # Katalog ve önbellek listesi, depoya girmeyen bir dersin adını ya da dosyasını içermemeli
    # (ör. fakülte bilgisayarında "paketle --fakulte" çalıştırıldıktan sonra).
    for liste in ("lessons/katalog.json", "lessons/katalog.js", "onbellek-listesi.json"):
        yol = os.path.join(KOK, liste)
        if liste not in kume or not os.path.exists(yol):
            continue
        metin = open(yol, encoding="utf-8").read()
        for klasor in glob.glob(os.path.join(KOK, "lessons", "*", "")):
            ders = os.path.basename(os.path.dirname(klasor))
            if not any(x.startswith("lessons/%s/" % ders) for x in kume) and ('"%s"' % ders in metin or "lessons/%s/" % ders in metin):
                H.append("%s depoya girmeyen '%s' dersini anıyor: 'node tools/paketle.mjs' (--fakulte olmadan) çalıştırın" % (liste, ders))
    return H, U


KANCA = """#!/bin/sh
# KlinikKoç: açık depoya özel içerik girmesin (tools/yayin_denetimi.py --kanca ile kuruldu)
PY=python3
command -v $PY >/dev/null 2>&1 || PY=python
exec $PY tools/yayin_denetimi.py
"""


def kanca_kur():
    git = os.path.join(KOK, ".git")
    if not os.path.isdir(git):
        sys.exit("Bu klasör bir git deposu değil.")
    yol = os.path.join(git, "hooks", "pre-commit")
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    open(yol, "w", newline="\n").write(KANCA)
    os.chmod(yol, 0o755)
    print("Kuruldu: %s\nArtık her commit'ten önce yayın denetimi çalışır." % os.path.relpath(yol, KOK))


def main():
    if "--kanca" in sys.argv:
        kanca_kur()
        return 0
    H, U = denetle()
    for u in U:
        print("uyarı: " + u)
    for h in H:
        print("HATA:  " + h)
    print("Yayın denetimi: %s (%d hata, %d uyarı)" % ("geçti" if not H else "GEÇMEDİ", len(H), len(U)))
    return 1 if H else 0


if __name__ == "__main__":
    sys.exit(main())
