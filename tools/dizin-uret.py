#!/usr/bin/env python3
"""Bir dersin kaynak dizinini üretir (kurulumsuz arama; vektör veritabanı gerekmez).

Canlı soru-cevapta model yalnız bu dizinde ve ders anlatımında bulunan parçalara dayanır.
Model kapalıyken de "Soru sor" aynı dizinde arama yapar.

Kurulum (bir kez):  python tools/dizin-uret.py --kur      (pypdf)
Kullanım:           python tools/dizin-uret.py peri-implantitis-cerrahi

Girdi: lessons/<id>/kaynaklar/kaynaklar.json
  { "kaynaklar": [
      { "id": "ramanauskaite-2026",
        "baslik": "Factors influencing the effectiveness of surgical therapy of peri-implantitis",
        "kisa": "Ramanauskaite ve ark. 2026",
        "atif": "Ramanauskaite A, ... Periodontol 2000. 2026. doi:10.1111/prd.70052",
        "lisans": "CC BY 4.0",
        "acik": true,
        "dosya": "MAKALE.pdf",          # aynı klasörde PDF ya da .txt/.md
        "sayfalar": "1-17",              # isteğe bağlı: kaynakça sayfalarını dışarıda bırakmak için
        "sil": ["^RAMANAUSKAITE +et al\\.$"],  # isteğe bağlı: sayfa başlığı gibi atılacak satırlar (düzenli ifade)
        "bitis": "^REFERENCES" }           # isteğe bağlı: bu satırdan sonrası (kaynakça) alınmaz
  ],
  "sozluk": { "çevrili defekt": "contained defect", ... } }   # isteğe bağlı

"sozluk": Türkçe soruyu İngilizce kaynakta bulmak için terim karşılıkları. Soruda geçen
Türkçe terimin İngilizcesi aramaya eklenir. Ayrıca ders anlatımında bulunan yerin
sayfa numarası (sourceRef "s. 6") kaynağın aynı sayfasını öne çıkarır.

"acik": false olan kaynakların metni yine aranır ve modele verilir, ama şekilleri
tahtada doğrudan gösterilmez; yalnız "uyarlanmıştır" notuyla yeniden çizilebilir.
Lisansı izin vermeyen bir kaynağın metnini dizine koymadan önce hak sahibine danışın:
dizin dersle birlikte yayımlanır.

Çıktı: lessons/<id>/kaynak-dizini.json (+ dosyadan açma için kaynak-dizini.js)
"""
import argparse
import json
import logging
import os
import re
import subprocess
import sys


def _metin_yaz(yol, metin, **ek):
    with open(yol, "w", encoding="utf-8", **ek) as f:
        f.write(metin)


def _metin_oku(yol):
    """Dosyayı okuyup hemen kapatır (açık kalan dosya Windows'ta kilitlenmeye yol açar)."""
    with open(yol, encoding="utf-8") as f:
        return f.read()


def _json_oku(yol):
    with open(yol, encoding="utf-8") as f:
        return json.load(f)


KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARCA = 900       # hedef parça uzunluğu (karakter)
ORTUSME = 150     # parçalar arası örtüşme


def sayfa_araligi(spec, n):
    if not spec:
        return list(range(1, n + 1))
    out = []
    for part in str(spec).split(","):
        a, _, b = part.strip().partition("-")
        out += list(range(int(a), int(b or a) + 1))
    return [p for p in out if 1 <= p <= n]


def temizle(t, sil=()):
    t = t.replace("\u00ad", "")
    t = re.sub(r"[\u2000-\u200a\u202f\u00a0]", " ", t)    # ince/geniş boşluklar
    for kalip in sil:                                  # sayfa başlıkları, sayfa numaraları
        t = re.sub(kalip, "", t, flags=re.M)
    t = re.sub(r"(\w) -\n(\w)", r"\1\2", t)               # yumuşak tireleme: "influ -\nence"
    t = re.sub(r"(\w)-\n(\w)", r"\1\2", t)
    t = re.sub(r"(\w)- +(\w)", r"\1-\2", t)                # "peri-  implantitis"
    t = re.sub(r"[ \t]*\n[ \t]*", "\n", t)
    t = re.sub(r"(?<![.:;!?])\n(?!\n)", " ", t)              # paragraf içi satır kırılması
    t = re.sub(r"[ \t]{2,}", " ", t)
    return t.strip()


def bol(metin):
    """Cümle sınırlarına göre ~PARCA karakterlik, ORTUSME kadar örtüşen parçalar."""
    cumleler = re.findall(r"[^.!?]+[.!?]+[\"')\]]*\s*|[^.!?]+$", metin)
    parcalar, cur = [], ""
    for c in cumleler:
        if len(cur) + len(c) > PARCA and cur:
            parcalar.append(cur.strip())
            cur = cur[-ORTUSME:].split(" ", 1)[-1] if ORTUSME else ""
        cur += c
    if cur.strip():
        parcalar.append(cur.strip())
    return [p for p in parcalar if len(p) > 80]


def oku(yol, spec, sil=(), bitis=None):
    if yol.lower().endswith(".pdf"):
        try:
            from pypdf import PdfReader
        except ImportError:
            sys.exit("pypdf yok. Önce: python tools/dizin-uret.py --kur")
        logging.getLogger("pypdf").setLevel(logging.ERROR)
        r = PdfReader(yol)
        for s in sayfa_araligi(spec, len(r.pages)):
            t = r.pages[s - 1].extract_text() or ""
            m = re.search(bitis, t, flags=re.M) if bitis else None
            yield s, temizle(t[:m.start()] if m else t, sil)
            if m:
                return
    else:
        yield 0, temizle(_metin_oku(yol), sil)


def main():
    ap = argparse.ArgumentParser(description="Ders kaynak dizinini üretir.")
    ap.add_argument("ders", nargs="?")
    ap.add_argument("--kur", action="store_true", help="pypdf'i kur ve çık")
    a = ap.parse_args()
    if a.kur:
        sys.exit(subprocess.call([sys.executable, "-m", "pip", "install", "--upgrade", "pypdf"]))
    if not a.ders:
        ap.error("ders kimliği gerekli")

    ders_dir = os.path.join(KOK, "lessons", a.ders)
    kdir = os.path.join(ders_dir, "kaynaklar")
    cfg = _json_oku(os.path.join(kdir, "kaynaklar.json"))
    kaynaklar, parcalar = [], []
    for i, k in enumerate(cfg["kaynaklar"]):
        if not k.get("lisans"):
            sys.exit('"%s" için lisans yazılmamış. Lisansı bilinmeyen kaynak dizine eklenmez.' % k.get("id"))
        kaynaklar.append({x: k[x] for x in ("id", "baslik", "kisa", "atif", "lisans", "acik") if x in k})
        n = 0
        for sayfa, metin in oku(os.path.join(kdir, k["dosya"]), k.get("sayfalar"), k.get("sil", []), k.get("bitis")):
            for p in bol(metin):
                parcalar.append({"k": i, "s": sayfa, "t": p})
                n += 1
        print("%s: %d parça" % (k["id"], n))

    out = {"surum": 1, "kaynaklar": kaynaklar, "sozluk": cfg.get("sozluk", {}), "parcalar": parcalar}
    body = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    _metin_yaz(os.path.join(ders_dir, "kaynak-dizini.json"), body + "\n")
    _metin_yaz(os.path.join(ders_dir, "kaynak-dizini.js"), 
        "/* tools/dizin-uret.py üretti; elle düzenlemeyin. */\nAT.registerLessonData(%s, %s);\n"
        % (json.dumps(a.ders + ":dizin"), body))
    print("Dizin hazır: %d kaynak, %d parça, %.0f KB." % (len(kaynaklar), len(parcalar), len(body.encode()) / 1024))


if __name__ == "__main__":
    main()
