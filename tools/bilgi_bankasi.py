#!/usr/bin/env python3
"""KlinikKoç bilgi bankası: derslerin kaynak metinlerini, anlatımlarını, öğretmen notlarını ve
vaka kartlarını tek bir SQLite dosyasında arar.

İki arama birlikte çalışır (karma arama):
  1. Sözcük araması (SQLite FTS5). Hiçbir kurulum gerektirmez, her zaman açıktır.
     Türkçe ekler için sözcüklerin ilk 5 harfiyle önek araması yapılır: "iltihabı" → "iltih*".
  2. Anlam araması (isteğe bağlı). Küçük, çevrimdışı çalışan çok dilli bir model
     (multilingual-e5-small, MIT lisanslı, ~120 MB) her parçayı bir sayı dizisine çevirir;
     sorguya anlamca yakın parçalar, aynı sözcükleri içermese de bulunur.
  İki sıralama "karşılıklı sıra birleştirme" (RRF) ile tek listeye indirilir.

Kullanım:
  python tools/bilgi_bankasi.py --dizinle            bütün dersleri dizinler (.dizin/bilgi.sqlite)
  python tools/bilgi_bankasi.py --ara "nekrotizan"   arama yapar
  python tools/bilgi_bankasi.py --kur-anlam          anlam araması için paketleri ve modeli kurar (bir kez)
  python tools/bilgi_bankasi.py --durum              dizinin ve modelin durumunu gösterir

Dizin her bilgisayarda yeniden üretilir; depoya girmez. Yalnız Python'un kendi kitaplığı
gerekir; anlam araması için ayrıca onnxruntime, tokenizers ve numpy.
"""
import argparse
import glob
import hashlib
import json
import math
import os
import re
import sqlite3
import struct
import subprocess
import sys
import time
import urllib.request


def _metin_yaz(yol, metin, **ek):
    with open(yol, "w", encoding="utf-8", **ek) as f:
        f.write(metin)


KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIZIN = os.environ.get("KLINIK_KOC_DIZIN") or os.path.join(KOK, ".dizin", "bilgi.sqlite")
MODEL_KLASORU = os.environ.get("KLINIK_KOC_MODEL") or os.path.join(KOK, ".modeller", "multilingual-e5-small")
MODEL_ADRESI = "https://huggingface.co/Xenova/multilingual-e5-small/resolve/main/"
MODEL_DOSYALARI = {"model.onnx": "onnx/model_quantized.onnx", "tokenizer.json": "tokenizer.json"}
SURUM = 2              # parçalama kuralı değişince artır: bütün dersler yeniden dizinlenir
PARCA_SOZCUK = 110      # bir parçadaki yaklaşık sözcük sayısı
ORTUSME = 25            # komşu parçalar arasında ortak sözcük (bağlam kopmasın)
RRF_K = 60

TURLER = ("kaynak", "anlatim", "ogretmen_notu", "vaka", "soru")


# ---------- Dayanak etiketi: kaynakta bu soruya gerçekten dayanak var mı? ----------
# RRF puanı yalnız sıradan hesaplanır; sonucun soruyla ne kadar ilgili olduğunu söylemez. Bu yüzden her aramada
# iki ham sinyal de ölçülür ve bunlardan "guclu" | "zayif" | "yok" etiketi türetilir:
#   anlam_benzerligi: sorgu ile parça arasındaki kosinüs benzerliği (yalnız anlam araması açıkken).
#   sozcuk_kapsami:   sorgunun anlamlı sözcüklerinden parçada geçenlerin payı; nadir sözcükler daha ağır sayılır
#                     (dizinde hiç geçmeyen "beyazlatma" gibi bir sözcük eksikse kapsam çok düşer).
# Eşikler ölçülerek bulunur: python tools/dayanak_olc.py. Ortam değişkenleriyle değiştirilebilir.


def _esik(ad, varsayilan):
    try:
        return float(os.environ.get("KLINIK_KOC_" + ad, varsayilan))
    except ValueError:
        return varsayilan


# GEÇİCİ değerler: multilingual-e5-small ile henüz ölçülmedi (bulut ortamı modeli indiremiyor).
# dayanak_olc.py öğretmenin bilgisayarında çalıştırılıp önerilen değerler onaylanınca buraya yazılacak.
DAYANAK_GUCLU = _esik("DAYANAK_GUCLU", 0.84)          # en iyi anlam benzerliği bunun üstündeyse güçlü
DAYANAK_ZAYIF = _esik("DAYANAK_ZAYIF", 0.80)          # bunun altındaysa dayanak yok
DAYANAK_SOZCUK_GUCLU = _esik("DAYANAK_SOZCUK_GUCLU", 0.60)   # en iyi sözcük kapsamı bunun üstündeyse güçlü
DAYANAK_SOZCUK_ZAYIF = _esik("DAYANAK_SOZCUK_ZAYIF", 0.30)   # bunun altındaysa dayanak yok

# Soruların çoğunda geçen, konu söylemeyen sözcükler. Dayanak ölçülürken sayılmaz (sıralamayı etkilemez).
DOLGU_SOZCUKLER = set("""
acaba ama ancak anlat anlatir anlatır açıkla aciklar bana ben bence bir biraz biri bize biz bu bunu bunun buna
böyle çok da daha de değil degil diye en eder edilir edilmeli etmeli fakat gibi göre gore hangi hangisi hangileri
hep her için icin ile ise ister kaç kac kadar ki mi mı mu mü midir mıdır mudur müdür misin mısın nasil nasıl ne
neden nedir neler nelerdir niye nedeni o olabilir olan olarak olmalı olmali olur olursa onu onun ona peki sadece
sen siz şey sey şu şunu söyle soyle sonra önce once ve veya ya yalnız yalniz yani yapılır yapilir yapmalı var yok
zaman lütfen lutfen
""".split())


# ---------- Türkçe metin işleme ----------
_KUCUK = str.maketrans({"I": "ı", "İ": "i"})


def kucuk(s):
    return (s or "").translate(_KUCUK).lower()


def sozcukler(s):
    return re.findall(r"[0-9a-zçğıöşüâîû]+", kucuk(s))


def fts_sorgusu(sorgu):
    """Kullanıcının sorgusunu FTS5 ifadesine çevirir. Uzun sözcükler köküne yakın bir önekle aranır."""
    parca = []
    for w in sozcukler(sorgu):
        if len(w) < 2:
            continue
        w = w.replace('"', "")
        parca.append('"%s"*' % w[:5] if len(w) > 5 else '"%s"*' % w)
    return " OR ".join(parca)


def parcala(metin, n=PARCA_SOZCUK, ortusme=ORTUSME):
    w = (metin or "").split()
    if len(w) <= n:
        return [" ".join(w)] if w else []
    out, i = [], 0
    while i < len(w):
        out.append(" ".join(w[i:i + n]))
        if i + n >= len(w):
            break
        i += n - ortusme
    return out


def duz(say):
    return re.sub(r"\s+", " ", re.sub(r"\{\d+\}", "", say or "")).strip()


# ---------- Ders dosyalarından parça toplama ----------
def ders_kimlikleri():
    yollar = glob.glob(os.path.join(KOK, "lessons", "*", "ders.json")) + \
        glob.glob(os.path.join(KOK, "lessons", "*", "egitmen.json"))
    return sorted({os.path.basename(os.path.dirname(p)) for p in yollar})


def _oku(yol):
    try:
        with open(yol, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _metin(yol):
    with open(yol, encoding="utf-8") as f:
        return f.read()


def ders_parcalari(ders):
    """Bir dersin aranabilir parçalarını üretir: {ders, tur, baslik, metin, sayfa, bolum, hedef, kaynak}."""
    klasor = os.path.join(KOK, "lessons", ders)
    d = _oku(os.path.join(klasor, "ders.json")) or {}
    eg = _oku(os.path.join(klasor, "egitmen.json")) or {}
    out = []

    # 1. Kaynak sayfaları (ders notu ya da makale metni)
    kay = eg.get("kaynak") or {}
    sablon = kay.get("sayfaMetni") or "kaynak/sayfa-{nn}.txt"
    kaynak_ad = kay.get("baslik") or (d.get("source") or {}).get("citation") or "Kaynak"
    for yol in sorted(glob.glob(os.path.join(klasor, "kaynak", "sayfa-*.txt"))):
        m = re.search(r"sayfa-(\d+)\.txt$", yol)
        if not m or not sablon:
            continue
        no = int(m.group(1))
        for i, p in enumerate(parcala(_metin(yol))):
            out.append({"ders": ders, "tur": "kaynak", "baslik": "%s, s. %d" % (kaynak_ad, no),
                        "metin": p, "sayfa": no, "kaynak": "s. %d" % no, "sira": i})

    # 2. Hazır anlatım (ders.json adımları) ve soruları
    for s in d.get("sections", []):
        hedef = ",".join(s.get("goals") or [])
        for st in s.get("steps", []):
            if st.get("say"):
                out.append({"ders": ders, "tur": "anlatim", "baslik": s.get("title") or s["id"],
                            "metin": duz(st["say"]), "bolum": s["id"], "adim": st.get("id"),
                            "hedef": hedef, "kaynak": st.get("sourceRef")})
            q = st.get("question")
            if q:
                parcalar = [q.get("prompt") or "", q.get("scenario") or "", q.get("explanation") or "",
                            q.get("modelAnswer") or ""]
                out.append({"ders": ders, "tur": "soru", "baslik": "Soru: " + (q.get("prompt") or "")[:60],
                            "metin": duz(" ".join(parcalar)), "bolum": s["id"], "adim": st.get("id"),
                            "hedef": q.get("goal") or hedef, "kaynak": q.get("sourceRef")})

    # 3. Öğretmen notları (egitmen.json)
    for n in eg.get("ogretmenNotlari") or []:
        metin = n.get("metin") or n.get("not") or n.get("kural") or ""
        if metin:
            out.append({"ders": ders, "tur": "ogretmen_notu", "baslik": n.get("baslik") or ("Öğretmen notu " + str(n.get("id", ""))),
                        "metin": metin, "sayfa": (n.get("sayfalar") or [None])[0],
                        "hedef": ",".join(n.get("hedefler") or []), "kaynak": "öğretmen notu"})

    # 4. Vaka kartları
    for yol in sorted(glob.glob(os.path.join(klasor, "vakalar", "*.json"))):
        v = _oku(yol)
        if not v:
            continue
        vid = v.get("id") or os.path.splitext(os.path.basename(yol))[0]
        hasta = v.get("hasta") or {}
        basvuru = v.get("basvuru") or {}
        ozet = " ".join(x for x in [v.get("baslik"), basvuru.get("sikayet"), basvuru.get("oyku"),
                                    " ".join(hasta.get("sistemik") or []), (v.get("kapanis") or {}).get("ozet")] if x)
        out.append({"ders": ders, "tur": "vaka", "baslik": "Vaka: " + (v.get("baslik") or vid), "metin": ozet,
                    "vaka": vid, "hedef": ",".join(v.get("hedefler") or []), "kaynak": "vaka " + vid})
        for b in v.get("bulgular") or []:
            out.append({"ders": ders, "tur": "vaka", "baslik": "Vaka %s · bulgu" % vid, "metin": b.get("metin", ""),
                        "vaka": vid, "kaynak": "vaka %s, %s" % (vid, b.get("id", ""))})
    return [p for p in out if p["metin"].strip()]


# ---------- Anlam modeli (isteğe bağlı) ----------
class AnlamModeli:
    """multilingual-e5-small ONNX modeli. Kurulu değilse hazir=False olur ve yalnız sözcük araması yapılır."""

    def __init__(self, klasor=MODEL_KLASORU):
        self.hazir = False
        self.neden = None
        self.ad = os.path.basename(klasor)
        try:
            import numpy as np  # noqa: F401
            import onnxruntime as ort
            from tokenizers import Tokenizer
        except ImportError:
            self.neden = "paketler kurulu değil (python tools/bilgi_bankasi.py --kur-anlam)"
            return
        model = os.path.join(klasor, "model.onnx")
        tok = os.path.join(klasor, "tokenizer.json")
        if not (os.path.exists(model) and os.path.exists(tok)):
            self.neden = "model indirilmemiş (python tools/bilgi_bankasi.py --kur-anlam)"
            return
        self.np = __import__("numpy")
        so = ort.SessionOptions()
        so.intra_op_num_threads = max(1, min(4, os.cpu_count() or 1))
        self.oturum = ort.InferenceSession(model, so, providers=["CPUExecutionProvider"])
        self.girdiler = [i.name for i in self.oturum.get_inputs()]
        self.tok = Tokenizer.from_file(tok)
        self.tok.enable_truncation(max_length=256)
        self.tok.enable_padding()
        self.hazir = True

    def vektorler(self, metinler, onek="passage: ", grup=16):
        np = self.np
        out = []
        for i in range(0, len(metinler), grup):
            kod = self.tok.encode_batch([onek + m for m in metinler[i:i + grup]])
            ids = np.array([k.ids for k in kod], dtype=np.int64)
            maske = np.array([k.attention_mask for k in kod], dtype=np.int64)
            besle = {"input_ids": ids, "attention_mask": maske}
            if "token_type_ids" in self.girdiler:
                besle["token_type_ids"] = np.zeros_like(ids)
            gizli = self.oturum.run(None, {k: v for k, v in besle.items() if k in self.girdiler})[0]
            m = maske[..., None].astype(np.float32)
            ort_ = (gizli * m).sum(1) / np.clip(m.sum(1), 1e-9, None)
            ort_ /= np.clip(np.linalg.norm(ort_, axis=1, keepdims=True), 1e-9, None)
            out.extend(ort_.astype(np.float32))
        return [list(map(float, v)) for v in out]

    def sorgu_vektoru(self, sorgu):
        return self.vektorler([sorgu], onek="query: ")[0]


def vektor_paketle(v):
    return struct.pack("<%df" % len(v), *v)


def vektor_ac(b):
    return struct.unpack("<%df" % (len(b) // 4), b)


def benzerlik(a, b):
    return sum(x * y for x, y in zip(a, b))


# ---------- Dizin ----------
SEMA = """
CREATE TABLE IF NOT EXISTS bilgi (anahtar TEXT PRIMARY KEY, deger TEXT);
CREATE TABLE IF NOT EXISTS parca (
  no INTEGER PRIMARY KEY, ders TEXT, tur TEXT, baslik TEXT, metin TEXT,
  sayfa INTEGER, bolum TEXT, adim TEXT, hedef TEXT, vaka TEXT, kaynak TEXT, ozet TEXT, vektor BLOB);
CREATE INDEX IF NOT EXISTS parca_ders ON parca(ders, tur);
CREATE VIRTUAL TABLE IF NOT EXISTS parca_fts USING fts5(baslik, metin, content='parca', content_rowid='no',
  tokenize='unicode61 remove_diacritics 2');
"""


def baglan(yol=DIZIN):
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    db = sqlite3.connect(yol)
    db.executescript(SEMA)
    return db


def ders_imzasi(ders):
    """Dersin dizine giren dosyalarının değişip değişmediğini anlamak için kısa bir özet."""
    h = hashlib.sha1(("surum %d;" % SURUM).encode())
    klasor = os.path.join(KOK, "lessons", ders)
    for yol in sorted(glob.glob(os.path.join(klasor, "*.json")) + glob.glob(os.path.join(klasor, "kaynak", "*.txt")) +
                      glob.glob(os.path.join(klasor, "vakalar", "*.json"))):
        st = os.stat(yol)
        h.update(("%s|%d|%d;" % (os.path.relpath(yol, klasor), st.st_size, int(st.st_mtime))).encode())
    return h.hexdigest()


def dizinle(dersler=None, model=None, yol=DIZIN, sessiz=False):
    """Dersleri dizinler. Değişmemiş dersler atlanır. model verilirse anlam vektörleri de hesaplanır."""
    db = baglan(yol)
    rapor = []
    hepsi = ders_kimlikleri()
    for ders in (dersler or hepsi):
        imza = ders_imzasi(ders) + ("+anlam" if model and model.hazir else "")
        eski = db.execute("SELECT deger FROM bilgi WHERE anahtar=?", ("imza:" + ders,)).fetchone()
        if eski and eski[0] == imza:
            rapor.append({"ders": ders, "durum": "güncel"})
            continue
        parcalar = ders_parcalari(ders)
        vektorler = model.vektorler([p["metin"] for p in parcalar]) if (model and model.hazir and parcalar) else None
        db.execute("DELETE FROM parca WHERE ders=?", (ders,))
        for i, p in enumerate(parcalar):
            vek = vektor_paketle(vektorler[i]) if vektorler else None
            db.execute("INSERT INTO parca(ders, tur, baslik, metin, sayfa, bolum, adim, hedef, vaka, kaynak, vektor) "
                           "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                           (ders, p["tur"], p.get("baslik"), p["metin"], p.get("sayfa"), p.get("bolum"), p.get("adim"),
                            p.get("hedef"), p.get("vaka"), p.get("kaynak"), vek))
        db.execute("INSERT OR REPLACE INTO bilgi VALUES (?,?)", ("imza:" + ders, imza))
        rapor.append({"ders": ders, "durum": "dizinlendi", "parca": len(parcalar), "anlam": bool(vektorler)})
    # Silinmiş derslerin parçalarını temizle
    for (ders,) in db.execute("SELECT DISTINCT ders FROM parca").fetchall():
        if ders not in hepsi:
            db.execute("DELETE FROM parca WHERE ders=?", (ders,))
            db.execute("DELETE FROM bilgi WHERE anahtar=?", ("imza:" + ders,))
    # Sözcük dizini parça tablosundan baştan kurulur (birkaç bin parça için bir saniyenin altında).
    db.execute("INSERT INTO parca_fts(parca_fts) VALUES('rebuild')")
    db.execute("INSERT OR REPLACE INTO bilgi VALUES ('surum', ?)", (str(SURUM),))
    db.execute("INSERT OR REPLACE INTO bilgi VALUES ('tarih', ?)", (time.strftime("%Y-%m-%d %H:%M"),))
    if model and model.hazir:
        db.execute("INSERT OR REPLACE INTO bilgi VALUES ('model', ?)", (model.ad,))
    db.commit()
    db.close()
    if not sessiz:
        for r in rapor:
            print("%-32s %s%s" % (r["ders"], r["durum"], (" (%d parça%s)" % (r["parca"], ", anlam" if r["anlam"] else ""))
                                  if r.get("parca") is not None else ""))
    return rapor


def _filtre(ders, tur):
    kosul, arg = [], []
    if ders:
        kosul.append("p.ders = ?")
        arg.append(ders)
    if tur:
        turler = [tur] if isinstance(tur, str) else list(tur)
        kosul.append("p.tur IN (%s)" % ",".join("?" * len(turler)))
        arg += turler
    return (" AND " + " AND ".join(kosul)) if kosul else "", arg


def anlamli_sozcukler(sorgu):
    """Dayanak ölçümünde sayılan sözcükler: dolgu sözcükleri ve 3 harften kısa olanlar çıkar; tekrar edenler bir kez."""
    return list(dict.fromkeys(w for w in sozcukler(sorgu) if len(w) >= 3 and w not in DOLGU_SOZCUKLER))


def _onek(w):
    return w[:5] if len(w) > 5 else w


def _agirliklar(db, sozler):
    """Nadir sözcük ağır sayılır (IDF). Dizinde hiç geçmeyen sözcük en ağırdır."""
    n = db.execute("SELECT COUNT(*) FROM parca").fetchone()[0] or 1
    out = {}
    for w in sozler:
        try:
            df = db.execute("SELECT COUNT(*) FROM parca_fts WHERE parca_fts MATCH ?",
                            ['"%s"*' % _onek(w).replace('"', "")]).fetchone()[0]
        except sqlite3.OperationalError:
            df = 0
        out[w] = math.log((n + 1) / (df + 1)) + 1
    return out


def sozcuk_kapsami(metin, agirlik):
    """Sorgunun anlamlı sözcüklerinden metinde (önekle) geçenlerin ağırlıklı payı: 0–1."""
    if not agirlik:
        return None
    var = set(sozcukler(metin))
    toplam = sum(agirlik.values())
    bulunan = sum(a for w, a in agirlik.items() if any(x.startswith(_onek(w)) for x in var))
    return round(bulunan / toplam, 3) if toplam else None


def _etiket(deger, guclu, zayif):
    if deger is None:
        return None
    return "guclu" if deger >= guclu else "zayif" if deger >= zayif else "yok"


_SIRA = {"yok": 0, "zayif": 1, "guclu": 2}


def dayanak(sonuclar, anlam_acik=None, sozler=None):
    """Sonuç listesinin geneli için özet: {dayanak, en_iyi_benzerlik, en_iyi_kapsam, sozcuk_eslesen_sayi, ...}.

    Anlam araması açıksa en iyi anlam benzerliği, her durumda en iyi sözcük kapsamı bakılır; ikisinden yüksek
    olan etiket geçerlidir (anlamca yakın ama farklı sözcüklerle yazılmış parça da, aynı nadir terimleri içeren
    parça da dayanak sayılır). Hiç sonuç yoksa "yok"."""
    if anlam_acik is None:
        anlam_acik = any("anlam_benzerligi" in x for x in sonuclar)
    benz = [x["anlam_benzerligi"] for x in sonuclar if x.get("anlam_benzerligi") is not None]
    kaps = [x["sozcuk_kapsami"] for x in sonuclar if x.get("sozcuk_kapsami") is not None]
    out = {"en_iyi_benzerlik": max(benz) if benz else None,
           "en_iyi_kapsam": max(kaps) if kaps else None,
           "sozcuk_eslesen_sayi": sum(1 for x in sonuclar if x.get("sozcuk_eslesti")),
           "anlam_aramasi": bool(anlam_acik)}
    if sozler is not None:
        out["anlamli_sozcukler"] = sozler
    etiketler = [e for e in (
        _etiket(out["en_iyi_benzerlik"], DAYANAK_GUCLU, DAYANAK_ZAYIF) if anlam_acik else None,
        _etiket(out["en_iyi_kapsam"], DAYANAK_SOZCUK_GUCLU, DAYANAK_SOZCUK_ZAYIF)) if e]
    out["dayanak"] = max(etiketler, key=_SIRA.get) if (sonuclar and etiketler) else "yok"
    out["esikler"] = {"anlam": [DAYANAK_ZAYIF, DAYANAK_GUCLU], "sozcuk": [DAYANAK_SOZCUK_ZAYIF, DAYANAK_SOZCUK_GUCLU]}
    return out


def ara(sorgu, ders=None, tur=None, k=6, model=None, yol=DIZIN):
    """Karma arama. Dönen her sonuçta: ders, tur, baslik, metin, kaynak, sayfa, bolum, hedef, vaka, puan, yontem,
    sozcuk_eslesti, sozcuk_kapsami ve (anlam araması açıksa) anlam_benzerligi."""
    return ara_ve_dayanak(sorgu, ders, tur, k, model, yol)[0]


def ara_ve_dayanak(sorgu, ders=None, tur=None, k=6, model=None, yol=DIZIN):
    """ara() ile aynı sonuçlar ve bütün adaylardan hesaplanan dayanak özeti: (sonuclar, ozet)."""
    if not os.path.exists(yol):
        dizinle(model=model, yol=yol, sessiz=True)
    db = baglan(yol)
    ek, arg = _filtre(ders, tur)
    sira = {}
    yontem = {}
    benzer = {}
    ifade = fts_sorgusu(sorgu)
    if ifade:
        try:
            satirlar = db.execute("SELECT p.no FROM parca_fts f JOIN parca p ON p.no = f.rowid "
                                  "WHERE parca_fts MATCH ?" + ek + " ORDER BY bm25(parca_fts, 2.0, 1.0) LIMIT 50",
                                  [ifade] + arg).fetchall()
        except sqlite3.OperationalError:
            satirlar = []
        for r, (no,) in enumerate(satirlar):
            sira[no] = sira.get(no, 0) + 1.0 / (RRF_K + r + 1)
            yontem.setdefault(no, set()).add("sözcük")
    anlam_acik = bool(model and model.hazir)
    if anlam_acik:
        sv = model.sorgu_vektoru(sorgu)
        adaylar = db.execute("SELECT p.no, p.vektor FROM parca p WHERE p.vektor IS NOT NULL" + ek, arg).fetchall()
        puanli = sorted(((benzerlik(sv, vektor_ac(v)), no) for no, v in adaylar), reverse=True)[:50]
        for p, no in puanli:
            benzer[no] = p
        for r, (p, no) in enumerate(puanli):
            if p < 0.75 and r > 10:  # e5 benzerlikleri sıkışıktır; çok uzak parçaları ekleme
                break
            sira[no] = sira.get(no, 0) + 1.0 / (RRF_K + r + 1)
            yontem.setdefault(no, set()).add("anlam")
    sozler = anlamli_sozcukler(sorgu)
    agirlik = _agirliklar(db, sozler)
    alanlar = ("ders", "tur", "baslik", "metin", "kaynak", "sayfa", "bolum", "adim", "hedef", "vaka")

    def satir(no):
        r = db.execute("SELECT " + ", ".join(alanlar) + " FROM parca WHERE no=?", (no,)).fetchone()
        return dict(zip(alanlar, r))

    def sinyaller(no, metin):
        x = {"sozcuk_eslesti": "sözcük" in yontem.get(no, ()), "sozcuk_kapsami": sozcuk_kapsami(metin, agirlik)}
        if no in benzer:
            x["anlam_benzerligi"] = round(benzer[no], 4)
        return x

    # Özet bütün adaylardan çıkar (yalnız ilk k sonuçtan değil).
    adaylar_sinyal = [sinyaller(no, satir(no)["metin"]) for no in sira]
    ozet = dayanak(adaylar_sinyal, anlam_acik, sozler)

    en_iyi = sorted(sira.items(), key=lambda x: -x[1])[:k]
    out = []
    for no, puan in en_iyi:
        x = {a: b for a, b in satir(no).items() if b not in (None, "")}
        x["puan"] = round(puan * 1000, 1)
        x["yontem"] = "+".join(sorted(yontem[no]))
        x.update(sinyaller(no, x.get("metin", "")))
        out.append(x)
    db.close()
    return out, ozet


def durum(yol=DIZIN, model=None):
    out = {"dizin": os.path.relpath(yol, KOK), "var": os.path.exists(yol)}
    if out["var"]:
        db = baglan(yol)
        out["parca"] = {d: n for d, n in db.execute("SELECT ders, COUNT(*) FROM parca GROUP BY ders")}
        out["anlamli_parca"] = db.execute("SELECT COUNT(*) FROM parca WHERE vektor IS NOT NULL").fetchone()[0]
        out["tarih"] = (db.execute("SELECT deger FROM bilgi WHERE anahtar='tarih'").fetchone() or [None])[0]
        db.close()
    m = model or AnlamModeli()
    out["anlam_aramasi"] = "hazır" if m.hazir else "kapalı: " + (m.neden or "")
    return out


# ---------- Kurulum ----------
def kur_anlam():
    print("1/2 Paketler kuruluyor: onnxruntime, tokenizers, numpy ...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "--upgrade",
                           "onnxruntime", "tokenizers", "numpy"])
    print("2/2 Model indiriliyor (~120 MB, bir kez): multilingual-e5-small (MIT lisanslı)")
    os.makedirs(MODEL_KLASORU, exist_ok=True)
    for yerel, uzak in MODEL_DOSYALARI.items():
        hedef = os.path.join(MODEL_KLASORU, yerel)
        if os.path.exists(hedef) and os.path.getsize(hedef) > 0:
            print("   var:", yerel)
            continue
        gecici = hedef + ".indiriliyor"
        with urllib.request.urlopen(MODEL_ADRESI + uzak, timeout=60) as y, open(gecici, "wb") as f:
            toplam = int(y.headers.get("Content-Length") or 0)
            alinan = 0
            while True:
                b = y.read(1 << 20)
                if not b:
                    break
                f.write(b)
                alinan += len(b)
                if toplam:
                    print("\r   %s: %%%d" % (yerel, alinan * 100 // toplam), end="", flush=True)
        os.replace(gecici, hedef)
        print()
    _metin_yaz(os.path.join(MODEL_KLASORU, "LISANS.txt"), 
        "intfloat/multilingual-e5-small (ONNX: Xenova/multilingual-e5-small), MIT lisansı.\n")
    print("Hazır. Şimdi dizini yenileyin:  python tools/bilgi_bankasi.py --dizinle")


def main():
    ap = argparse.ArgumentParser(description="KlinikKoç bilgi bankası (SQLite karma arama)")
    ap.add_argument("--dizinle", action="store_true", help="dersleri dizinle (değişmeyenler atlanır)")
    ap.add_argument("--yeniden", action="store_true", help="dizini silip baştan kur")
    ap.add_argument("--ara", metavar="SORGU")
    ap.add_argument("--ders")
    ap.add_argument("--tur", choices=TURLER)
    ap.add_argument("-k", type=int, default=6)
    ap.add_argument("--kur-anlam", action="store_true", help="anlam araması için paket ve modeli kur")
    ap.add_argument("--durum", action="store_true")
    a = ap.parse_args()
    if a.kur_anlam:
        kur_anlam()
        return
    model = AnlamModeli()
    if a.yeniden and os.path.exists(DIZIN):
        os.remove(DIZIN)
    if a.dizinle or a.yeniden:
        if not model.hazir:
            print("Not: anlam araması kapalı (%s). Yalnız sözcük dizini kuruluyor." % model.neden)
        dizinle([a.ders] if a.ders else None, model=model)
    if a.ara:
        sonuclar, oz = ara_ve_dayanak(a.ara, a.ders, a.tur, a.k, model=model)
        print("Dayanak: %s (en iyi anlam benzerliği: %s, en iyi sözcük kapsamı: %s)" % (
            oz["dayanak"], oz["en_iyi_benzerlik"], oz["en_iyi_kapsam"]))
        for i, r in enumerate(sonuclar, 1):
            print("%d. [%s · %s · %s] %s" % (i, r["ders"], r["tur"], r["yontem"], r.get("baslik", "")))
            print("   " + r["metin"][:240] + ("…" if len(r["metin"]) > 240 else ""))
    if a.durum or not (a.dizinle or a.yeniden or a.ara):
        print(json.dumps(durum(model=model), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
