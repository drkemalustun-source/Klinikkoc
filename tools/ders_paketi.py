#!/usr/bin/env python3
"""KlinikKoç ders paketi: öğretmenin hazırladığı tek bir dersin zip'ini bu bilgisayara kurar.

Bir ders paketi, içinde tek bir ders klasörü olan bir zip'tir:
  <ders-kimligi>/ders.json ya da egitmen.json   (en az biri)
  <ders-kimligi>/kaynaklar/kaynaklar.json        (makale listesi: künye + DOI; abonelikli PDF yoktur)
  <ders-kimligi>/vakalar/..., assets/..., ...

Kurulunca ders lessons/<ders-kimligi>/ klasörüne açılır ve ders listesine eklenir. Sonra makale bulucu
listedeki makaleleri indirmeye başlar (tools/makale_bulucu.py).

Kullanım:
  python tools/ders_paketi.py --yukle <paket.zip> [--uzerine]
"""
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EN_BUYUK = 500 * 1024 * 1024     # açılmış toplam boyut sınırı
EN_COK_DOSYA = 5000
# Pakete hiç girmemesi gereken, öğrencinin bilgisayarında üretilen klasörler: gelirse atlanır.
ATLA = ("makale-metin/", "audio/")


def _json_oku(yol):
    try:
        with open(yol, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def paketi_incele(z):
    """Zip'i açmadan denetler. (ders kimliği, alınacak dosyalar) döndürür; uygun değilse ValueError."""
    adlar = [i for i in z.infolist() if not i.is_dir()]
    if not adlar:
        raise ValueError("Paket boş.")
    if len(adlar) > EN_COK_DOSYA:
        raise ValueError("Pakette çok fazla dosya var.")
    kokler = set()
    toplam = 0
    alinacak = []
    for i in adlar:
        ad = i.filename.replace("\\", "/")
        if ad.startswith("/") or re.match(r"^[A-Za-z]:", ad) or ".." in ad.split("/"):
            raise ValueError("Pakette güvensiz bir dosya yolu var: %s" % ad)
        if ad.startswith("__MACOSX/") or os.path.basename(ad) in (".DS_Store", "Thumbs.db"):
            continue
        parca = ad.split("/", 1)
        if len(parca) < 2:
            raise ValueError("Paketin içinde tek bir ders klasörü olmalı (dosya kökte: %s)." % ad)
        kokler.add(parca[0])
        if any(parca[1].startswith(a) for a in ATLA):
            continue
        toplam += i.file_size
        alinacak.append((i, parca[1]))
    if toplam > EN_BUYUK:
        raise ValueError("Paket açılınca çok büyük (en çok 500 MB).")
    if len(kokler) != 1:
        raise ValueError("Paketin içinde tek bir ders klasörü olmalı; bulunan: %s" % ", ".join(sorted(kokler)))
    ders = kokler.pop()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,80}", ders) or ders in ("tanitim",):
        raise ValueError("Ders kimliği uygun değil: %s" % ders)
    if not any(ic in ("ders.json", "egitmen.json") for _, ic in alinacak):
        raise ValueError("Bu bir KlinikKoç ders paketi değil (ders.json ya da egitmen.json yok).")
    return ders, alinacak


def katalog_guncelle(ders, klasor):
    """lessons/katalog.json (ve dosyadan açma için katalog.js) listesine dersi ekler ya da günceller."""
    yol = os.path.join(KOK, "lessons", "katalog.json")
    kat = _json_oku(yol) or {"lessons": []}
    d = _json_oku(os.path.join(klasor, "ders.json")) or {}
    eg = _json_oku(os.path.join(klasor, "egitmen.json")) or {}
    giris = {"id": ders, "title": d.get("title") or eg.get("baslik") or ders,
             "level": d.get("level") or eg.get("duzey"), "path": "lessons/%s/" % ders}
    if d.get("subtitle"):
        giris["subtitle"] = d["subtitle"]
    if d.get("estimatedMinutes"):
        giris["estimatedMinutes"] = d["estimatedMinutes"]
    kat["lessons"] = [g for g in kat.get("lessons", []) if g.get("id") != ders] + [giris]
    with open(yol, "w", encoding="utf-8") as f:
        f.write(json.dumps(kat, ensure_ascii=False, indent=2) + "\n")
    with open(os.path.join(KOK, "lessons", "katalog.js"), "w", encoding="utf-8") as f:
        f.write("/* Otomatik üretildi: tools/paketle.mjs */\nAT.registerCatalog(%s);\n" % json.dumps(kat, ensure_ascii=False))
    return giris


def _katalog_yaz(kat):
    with open(os.path.join(KOK, "lessons", "katalog.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps(kat, ensure_ascii=False, indent=2) + "\n")
    with open(os.path.join(KOK, "lessons", "katalog.js"), "w", encoding="utf-8") as f:
        f.write("/* Otomatik üretildi: tools/paketle.mjs */\nAT.registerCatalog(%s);\n" % json.dumps(kat, ensure_ascii=False))


def katalog_kaldir(ders):
    """Arşive kaldırılan dersi ders listesinden çıkarır."""
    yol = os.path.join(KOK, "lessons", "katalog.json")
    kat = _json_oku(yol)
    if not kat or not any(g.get("id") == ders for g in kat.get("lessons", [])):
        return False
    kat["lessons"] = [g for g in kat["lessons"] if g.get("id") != ders]
    _katalog_yaz(kat)
    return True


def yukle(zip_yolu, uzerine=False):
    """Paketi lessons/<ders>/ klasörüne kurar. Önce geçici klasöre açılır; yarıda kalırsa eski ders bozulmaz."""
    with zipfile.ZipFile(zip_yolu) as z:
        ders, alinacak = paketi_incele(z)
        hedef = os.path.join(KOK, "lessons", ders)
        if os.path.exists(hedef) and not uzerine:
            raise FileExistsError("'%s' dersi zaten kurulu. Güncellemek için üzerine yazmayı seçin." % ders)
        gecici = tempfile.mkdtemp(prefix=".kur-" + ders + "-", dir=os.path.join(KOK, "lessons"))
        try:
            for i, ic in alinacak:
                yol = os.path.join(gecici, *ic.split("/"))
                os.makedirs(os.path.dirname(yol), exist_ok=True)
                with z.open(i) as kaynak, open(yol, "wb") as f:
                    shutil.copyfileobj(kaynak, f)
            eski = None
            if os.path.exists(hedef):
                # Öğrencinin bilgisayarında üretilen makale metinleri ve sesler korunur.
                for ic in ("makale-metin", "audio", "videolar"):
                    if os.path.isdir(os.path.join(hedef, ic)) and not os.path.exists(os.path.join(gecici, ic)):
                        shutil.move(os.path.join(hedef, ic), os.path.join(gecici, ic))
                eski = hedef + ".eski"
                shutil.rmtree(eski, ignore_errors=True)
                os.replace(hedef, eski)
            os.replace(gecici, hedef)
            if eski:
                shutil.rmtree(eski, ignore_errors=True)
        except BaseException:
            shutil.rmtree(gecici, ignore_errors=True)
            raise
    giris = katalog_guncelle(ders, hedef)
    makale = 0
    kj = _json_oku(os.path.join(hedef, "kaynaklar", "kaynaklar.json")) or {}
    makale = len(kj.get("kaynaklar") or [])
    return {"ders": ders, "baslik": giris["title"], "makale": makale, "yer": hedef}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--yukle", metavar="ZIP", required=True)
    ap.add_argument("--uzerine", action="store_true", help="ders kuruluysa güncelle")
    ap.add_argument("--makalesiz", action="store_true", help="kurduktan sonra makaleleri indirme")
    a = ap.parse_args()
    try:
        r = yukle(a.yukle, a.uzerine)
    except (ValueError, FileExistsError, zipfile.BadZipFile) as e:
        print("Kurulamadı:", e)
        return 1
    print("Kuruldu: %s (%s), %d makale." % (r["baslik"], r["ders"], r["makale"]))
    if r["makale"] and not a.makalesiz:
        import makale_bulucu
        print("Makaleler aranıyor...")
        o = makale_bulucu.hazirla(r["ders"], ilerleme=lambda i, n, s: print(
            "%2d/%d  %-8s %s" % (i, n, s.get("durum"), s.get("kisa") or s.get("id"))))
        print("Makale klasörü:", o["klasor"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
