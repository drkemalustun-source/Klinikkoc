"""Ders sonu değerlendirme formu: öğrenci dersi bitirince doldurur, isterse öğretmenine gönderir.

Form iki bölümdür:
  1. Öğrencinin cevapları: ölçekli sorular (1–5), seçmeli sorular ve açık uçlu sorular.
  2. Eğitmenin (Claude) tespitleri: ders sırasında Claude'un fark ettiği sorunlar (yanlış ya da eksik
     bilgi, kaynakta olmayan sorular, teknik hata, dikte hatası, anlaşılmayan adım). Claude bunları ders
     sırasında degerlendirme_notu ile yazar; ayrıca kayıttan otomatik tespitler eklenir. Öğrenci göndermeden
     önce hepsini görür, istemediğini siler.

Gizlilik: gönderilen formda ad, öğrenci kimliği ya da numara yoktur; tarih yalnız ay olarak yazılır.
Form yalnız öğrenci "Kaydet" deyince Belgeler/KlinikKoç Değerlendirmeler klasörüne yazılır; hiçbir yere
kendiliğinden gönderilmez. Öğrenci isterse e-postayla gönderir.

Öğretmen: gelen formları (.json, .md ya da e-postadan kaydedilmiş .txt) bir klasöre koyup
    python tools/degerlendirme.py --topla <klasör>
ile özet çıkarır (ortalamalar, dağılımlar, açık uçlu cevaplar, Claude tespitleri).

Yalnız Python'un kendi kitaplığı.
"""
import argparse
import datetime
import glob
import json
import os
import platform
import re
import secrets
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import karne as karne_  # noqa: E402
import kayit_deposu as kd  # noqa: E402
import makale_bulucu as mb  # noqa: E402
import veri_yeri  # noqa: E402

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SURUM = 1
TUR = "klinikkoc-degerlendirme"
ISARET = "KLINIKKOC-FORM"  # e-posta gövdesinde formun makinece okunur kısmı bu satırdan sonra gelir

OLCEK = ["Kesinlikle katılmıyorum", "Katılmıyorum", "Kararsızım", "Katılıyorum", "Kesinlikle katılıyorum"]
SORULAR = [
    {"id": "hedef_acik", "tur": "olcek", "metin": "Dersin hedefleri açıktı."},
    {"id": "anlatim", "tur": "olcek", "metin": "Anlatım anlaşılırdı."},
    {"id": "egitmen_yardim", "tur": "olcek", "metin": "Eğitmenin cevapları sorularıma yardımcı oldu."},
    {"id": "kaynak_guven", "tur": "olcek", "metin": "Cevaplar kaynağa dayanıyordu; güvenilir buldum."},
    {"id": "vaka_katki", "tur": "olcek", "metin": "Vaka(lar) klinikte karar vermeme katkı sağladı.", "bos": "Vaka yoktu"},
    {"id": "ogrendim", "tur": "olcek", "metin": "Bu dersten sonra konuyu daha iyi biliyorum."},
    {"id": "kolay_kullanim", "tur": "olcek", "metin": "Programı kurmak ve kullanmak kolaydı."},
    {"id": "yine_isterim", "tur": "olcek", "metin": "Başka dersler için de bu yöntemi isterim."},
    {"id": "sure", "tur": "secim", "metin": "Dersin uzunluğu", "secenekler": ["Kısa", "Uygun", "Uzun"]},
    {"id": "zorluk", "tur": "secim", "metin": "Soruların zorluğu", "secenekler": ["Kolay", "Düzeyime uygun", "Zor"]},
    {"id": "ses", "tur": "secim", "metin": "Sesli anlatım ve mikrofon",
     "secenekler": ["İyi çalıştı", "Arada sorun oldu", "Çalışmadı", "Kullanmadım"]},
    {"id": "begendim", "tur": "metin", "metin": "En çok neyi beğendin?"},
    {"id": "degistir", "tur": "metin", "metin": "Neyi değiştirelim?"},
    {"id": "yanlis_bilgi", "tur": "metin", "metin": "Yanlış ya da eksik bulduğun bir bilgi oldu mu? Hangi konuda?"},
    {"id": "teknik", "tur": "metin", "metin": "Teknik bir sorun yaşadın mı? (kurulum, ses, makale indirme…)"},
]
TESPIT_TURLERI = {
    "yanlis_bilgi": "Derste yanlış ya da çelişkili bilgi",
    "eksik_kaynak": "Kaynakta olmayan ya da eksik konu",
    "anlatim": "Anlaşılmayan ya da yeniden anlatılan adım",
    "soru": "Sorunlu soru ya da cevap anahtarı",
    "teknik": "Teknik sorun",
    "dikte": "Dikte (mikrofon) hatası",
    "diger": "Diğer",
}
EN_COK_TESPIT = 40
EN_COK_METIN = 2000


def _json_oku(yol, varsayilan=None):
    try:
        with open(yol, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return varsayilan


def _json_yaz(yol, veri):
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    gecici = yol + ".tmp"
    with open(gecici, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=1)
    os.replace(gecici, yol)


def program_surumu():
    try:
        with open(os.path.join(KOK, "SURUM"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return None


def klasor():
    """Kaydedilen formların durduğu, öğrencinin gördüğü klasör."""
    return os.path.join(veri_yeri.belgeler(), "KlinikKoç Değerlendirmeler")


def ders_klasoru(ders):
    mb.ders_gecerli(ders)
    return os.path.join(mb.KOK, "lessons", ders)


def egitmen_bilgisi(ders):
    return _json_oku(os.path.join(ders_klasoru(ders), "egitmen.json"), {}) or {}


def depo():
    return kd.Depo(veri_yeri.kayit_kok())


def _taslak_yolu(kimlik, ders):
    return os.path.join(depo().klasor(kimlik), "degerlendirme", ders + ".json")


def _kisalt(s, n=EN_COK_METIN):
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return s[:n]


def _tespit(t):
    tur = t.get("tur") if t.get("tur") in TESPIT_TURLERI else "diger"
    x = {"tur": tur, "ayrinti": _kisalt(t.get("ayrinti"), 600)}
    if t.get("yer"):
        x["yer"] = _kisalt(t["yer"], 120)
    if t.get("kaynak"):
        x["kaynak"] = t["kaynak"] if t["kaynak"] in ("claude", "otomatik", "ogrenci") else "claude"
    return x if x["ayrinti"] else None


def taslak(kimlik, ders):
    return _json_oku(_taslak_yolu(kimlik, ders), {}) or {}


def taslak_yaz(kimlik, ders, veri):
    veri = dict(veri)
    veri["guncelleme"] = datetime.datetime.now().isoformat(timespec="seconds")
    _json_yaz(_taslak_yolu(kimlik, ders), veri)
    return veri


def claude_notu(kimlik, ders, tespitler):
    """Claude'un ders sırasında fark ettiği sorunları taslağa ekler (aynısı ikinci kez yazılmaz)."""
    ders_klasoru(ders)
    t = taslak(kimlik, ders)
    var = t.setdefault("claude_tespitleri", [])
    gorulen = {(x["tur"], x["ayrinti"]) for x in var}
    for ham in tespitler or []:
        x = _tespit(dict(ham, kaynak="claude")) if isinstance(ham, dict) else None
        if x and (x["tur"], x["ayrinti"]) not in gorulen and len(var) < EN_COK_TESPIT:
            var.append(x)
            gorulen.add((x["tur"], x["ayrinti"]))
    taslak_yaz(kimlik, ders, t)
    return var


def otomatik_not(kimlik, ders, tespit):
    """Programın kendiliğinden yazdığı tespit (ör. araç hatası); Claude'un hatırlamasına bağlı değildir."""
    ders_klasoru(ders)
    t = taslak(kimlik, ders)
    var = t.setdefault("otomatik_tespitler", [])
    x = _tespit(dict(tespit, kaynak="otomatik"))
    if x and all((y["tur"], y["ayrinti"]) != (x["tur"], x["ayrinti"]) for y in var) and len(var) < EN_COK_TESPIT:
        var.append(x)
        taslak_yaz(kimlik, ders, t)
    return var


def otomatik_tespitler(kimlik, ders):
    """Kayıttan çıkan, dersin kendisiyle ilgili sorunlar (öğrencinin başarısı değil)."""
    out = list(taslak(kimlik, ders).get("otomatik_tespitler") or []) if kimlik else []
    k, _ = depo().yukle(kimlik, ders) if kimlik else (None, None)
    for s in (k or {}).get("sorular") or []:
        if s.get("kaynakta_yok") and s.get("soru"):
            out.append({"tur": "eksik_kaynak", "ayrinti": "Kaynakta cevabı olmayan soru: " + _kisalt(s["soru"], 300),
                        "kaynak": "otomatik"})
    try:
        oz = mb.ozet(ders)
        eksik = [m.get("kisa") or m.get("baslik") for m in oz.get("makaleler", []) if m.get("durum") in ("eksik", "hata")]
        if eksik:
            out.append({"tur": "eksik_kaynak", "ayrinti": "İnmeyen makaleler: " + ", ".join(x for x in eksik if x)[:500],
                        "kaynak": "otomatik"})
    except Exception:
        pass
    return out[:EN_COK_TESPIT]


def calisma_ozeti(kimlik, ders):
    """Kimliksiz çalışma özeti: oturum sayısı, süre, genel başarı, hedef durumları."""
    k, _ = depo().yukle(kimlik, ders) if kimlik else (None, None)
    if not k:
        return None
    hedefler = karne_.ders_hedefleri(ders_klasoru(ders))
    kr = karne_.hesapla(k, hedefler, datetime.date.today().isoformat())
    dk = int(round(sum(float(o.get("sure_dk") or 0) for o in k.get("oturumlar") or [])))
    return {"oturum": len(k.get("oturumlar") or []), "dakika": dk or None,
            "genel_basari": kr.get("genel_oran"), "cevap": kr.get("cevap_sayisi"),
            "hedefler": [{"id": h["id"], "durum": h["durum"]} for h in kr.get("hedefler", [])],
            "deneme": bool(k.get("deneme"))}


def sorular(ders):
    """Ortak sorular + öğretmenin bu ders için eklediği sorular (egitmen.json geriBildirim.sorular)."""
    ek = (egitmen_bilgisi(ders).get("geriBildirim") or {}).get("sorular") or []
    out = [dict(s) for s in SORULAR]
    for i, s in enumerate(ek[:10], 1):
        metin = s.get("metin") if isinstance(s, dict) else s
        if metin:
            out.append({"id": "ek%d" % i, "tur": (s.get("tur") if isinstance(s, dict) else None) or "metin",
                        "metin": _kisalt(metin, 300), "ders_ozel": True,
                        **({"secenekler": s["secenekler"]} if isinstance(s, dict) and s.get("secenekler") else {})})
    return out


def form(ders, kimlik=None):
    """Form sayfasının ihtiyacı: sorular, öğretmen e-postası, taslak (cevaplar + tespitler), özet önizlemesi."""
    ders_klasoru(ders)
    eg = egitmen_bilgisi(ders)
    t = taslak(kimlik, ders) if kimlik else {}
    tespitler = list(t.get("claude_tespitleri") or [])
    gorulen = {(x["tur"], x["ayrinti"]) for x in tespitler}
    for x in otomatik_tespitler(kimlik, ders) if kimlik else []:
        if (x["tur"], x["ayrinti"]) not in gorulen:
            tespitler.append(x)
    return {"ders": ders, "baslik": mb.ders_basligi(ders), "egitmen": eg.get("egitmen"),
            "eposta": (eg.get("geriBildirim") or {}).get("eposta") or None,
            "sorular": sorular(ders), "olcek": OLCEK, "tespit_turleri": TESPIT_TURLERI,
            "cevaplar": t.get("cevaplar") or {}, "tespitler": tespitler,
            "ozet": calisma_ozeti(kimlik, ders) if kimlik else None,
            "gonderildi": t.get("kaydedildi"), "klasor": klasor()}


def _cevaplari_temizle(ders, cevaplar):
    temiz = {}
    for s in sorular(ders):
        v = (cevaplar or {}).get(s["id"])
        if v in (None, ""):
            continue
        if s["tur"] == "olcek":
            try:
                v = int(v)
            except (TypeError, ValueError):
                continue
            if 1 <= v <= 5:
                temiz[s["id"]] = v
            elif v == 0 and s.get("bos"):
                temiz[s["id"]] = 0  # "uygulanmaz" (ör. vaka yoktu)
        elif s["tur"] == "secim":
            if v in (s.get("secenekler") or []):
                temiz[s["id"]] = v
        else:
            v = _kisalt(v)
            if v:
                temiz[s["id"]] = v
    return temiz


def md_metni(f):
    """Formun okunur hâli; sonunda makinece okunur JSON (öğretmenin --topla aracı için)."""
    soru = {s["id"]: s for s in sorular(f["ders"])} if os.path.isdir(ders_klasoru(f["ders"])) else \
        {s["id"]: s for s in SORULAR}
    y = ["KlinikKoç ders değerlendirmesi: %s" % (f.get("ders_basligi") or f["ders"]),
         "Ay: %s · Eğitmen: %s · Bilgisayar: %s · Program sürümü: %s" % (
             f.get("ay"), f.get("egitmen") or "-", f.get("cihaz") or "-", f.get("program_surumu") or "-"), ""]
    for sid, v in f.get("cevaplar", {}).items():
        s = soru.get(sid, {"metin": sid, "tur": "metin"})
        if s["tur"] == "olcek":
            v = (s.get("bos") or "uygulanmaz") if v == 0 else "%d/5 (%s)" % (v, OLCEK[v - 1])
        y.append("- %s: %s" % (s["metin"], v))
    if f.get("tespitler"):
        y += ["", "Eğitmenin (Claude) tespitleri:"]
        y += ["- [%s] %s%s" % (TESPIT_TURLERI.get(t["tur"], t["tur"]), t["ayrinti"],
                               (" (yer: %s)" % t["yer"]) if t.get("yer") else "") for t in f["tespitler"]]
    oz = f.get("calisma_ozeti")
    if oz:
        y += ["", "Çalışma özeti: %d oturum%s, genel başarı %s" % (
            oz["oturum"], (", %d dk" % oz["dakika"]) if oz.get("dakika") else "", karne_.yuzde(oz.get("genel_basari")))]
    y += ["", ISARET, json.dumps(f, ensure_ascii=False, separators=(",", ":"))]
    return "\n".join(y) + "\n"


def kaydet(ders, cevaplar, kimlik=None, tespitler=None, ozet_ekle=True):
    """Öğrencinin onayladığı formu kimliksiz olarak Belgeler/KlinikKoç Değerlendirmeler'e yazar."""
    ders_klasoru(ders)
    eg = egitmen_bilgisi(ders)
    temiz_tespit = [x for x in (_tespit(t) for t in (tespitler or []) if isinstance(t, dict)) if x][:EN_COK_TESPIT]
    f = {"tur": TUR, "surum": SURUM, "form": secrets.token_hex(4), "ders": ders,
         "ders_basligi": mb.ders_basligi(ders), "paket_tarihi": eg.get("hazirlama"), "program_surumu": program_surumu(),
         "dagitim": eg.get("dagitim"), "egitmen": eg.get("egitmen"),
         "ay": datetime.date.today().strftime("%Y-%m"),
         "cihaz": {"Windows": "Windows", "Darwin": "Mac"}.get(platform.system(), platform.system()),
         "cevaplar": _cevaplari_temizle(ders, cevaplar), "tespitler": temiz_tespit}
    if ozet_ekle and kimlik:
        oz = calisma_ozeti(kimlik, ders)
        if oz:
            f["calisma_ozeti"] = oz
    if not f["cevaplar"] and not f["tespitler"]:
        raise ValueError("Form boş: en az bir soruyu cevaplayın.")
    k = klasor()
    os.makedirs(k, exist_ok=True)
    ad = "%s_%s_%s" % (ders, datetime.date.today().isoformat(), f["form"])
    yol_json = os.path.join(k, ad + ".json")
    _json_yaz(yol_json, f)
    metin = md_metni(f)
    yol_md = os.path.join(k, ad + ".txt")
    with open(yol_md, "w", encoding="utf-8") as fh:
        fh.write(metin)
    if kimlik:
        t = taslak(kimlik, ders)
        t.update({"cevaplar": cevaplar or {}, "kaydedildi": datetime.date.today().isoformat(), "dosya": yol_json})
        taslak_yaz(kimlik, ders, t)
    eposta = (eg.get("geriBildirim") or {}).get("eposta")
    konu = "KlinikKoç değerlendirme: %s" % f["ders_basligi"]
    mailto = None
    if eposta:
        mailto = "mailto:%s?subject=%s&body=%s" % (urllib.parse.quote(eposta, safe="@"), urllib.parse.quote(konu),
                                                   urllib.parse.quote(metin))
        if len(mailto) > 1900:  # bazı e-posta programları uzun bağlantıyı keser: dosyayı eklemesini söyleriz
            mailto = "mailto:%s?subject=%s&body=%s" % (
                urllib.parse.quote(eposta, safe="@"), urllib.parse.quote(konu),
                urllib.parse.quote("Değerlendirme formum ekte (%s).\n" % os.path.basename(yol_md)))
    return {"dosya": yol_json, "metin_dosyasi": yol_md, "klasor": k, "eposta": eposta, "mailto": mailto,
            "metin": metin, "form": f}


# ---------- Öğretmen: formları topla ----------
def formlari_oku(yollar):
    """Klasör(ler)deki .json/.txt/.md/.eml dosyalarından formları okur; aynı form iki kez sayılmaz."""
    dosyalar = []
    for y in yollar:
        if os.path.isdir(y):
            for uz in ("json", "txt", "md", "eml"):
                dosyalar += glob.glob(os.path.join(y, "**", "*." + uz), recursive=True)
        else:
            dosyalar.append(y)
    formlar, gorulen = [], set()
    for d in sorted(dosyalar):
        try:
            with open(d, encoding="utf-8", errors="replace") as fh:
                icerik = fh.read()
        except OSError:
            continue
        adaylar = []
        if d.endswith(".json"):
            try:
                adaylar.append(json.loads(icerik))
            except ValueError:
                pass
        for m in re.finditer(re.escape(ISARET) + r"\s*\n\s*(\{.*\})", icerik):
            try:
                adaylar.append(json.loads(m.group(1)))
            except ValueError:
                pass
        for f in adaylar:
            if isinstance(f, dict) and f.get("tur") == TUR and f.get("form") not in gorulen:
                gorulen.add(f.get("form"))
                formlar.append(f)
    return formlar


def ozetle(formlar, deneme_dahil=False):
    if not deneme_dahil:
        formlar = [f for f in formlar if not (f.get("calisma_ozeti") or {}).get("deneme")]
    soru = {s["id"]: s for s in SORULAR}
    dersler = sorted({f.get("ders_basligi") or f.get("ders") for f in formlar})
    y = ["# KlinikKoç değerlendirme özeti", "",
         "%d form · dersler: %s · aylar: %s" % (len(formlar), ", ".join(dersler) or "-",
                                                 ", ".join(sorted({f.get("ay") or "-" for f in formlar})) or "-"), ""]
    y += ["## Ölçekli sorular (1–5)", "", "| Soru | Cevap | Ortalama | 1 | 2 | 3 | 4 | 5 |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for s in SORULAR:
        if s["tur"] != "olcek":
            continue
        v = [f["cevaplar"][s["id"]] for f in formlar if isinstance(f.get("cevaplar", {}).get(s["id"]), int)
             and f["cevaplar"][s["id"]] > 0]
        ort = "%.1f" % (sum(v) / len(v)) if v else "-"
        y.append("| %s | %d | %s | %s |" % (s["metin"], len(v), ort, " | ".join(str(v.count(i)) for i in range(1, 6))))
    y += ["", "## Seçmeli sorular", ""]
    for s in SORULAR:
        if s["tur"] != "secim":
            continue
        say = {o: 0 for o in s["secenekler"]}
        for f in formlar:
            c = f.get("cevaplar", {}).get(s["id"])
            if c in say:
                say[c] += 1
        y.append("- %s: %s" % (s["metin"], ", ".join("%s %d" % (o, n) for o, n in say.items())))
    y += ["", "## Açık uçlu cevaplar", ""]
    for s in SORULAR:
        if s["tur"] != "metin":
            continue
        cev = [(f.get("ders_basligi"), f["cevaplar"][s["id"]]) for f in formlar if f.get("cevaplar", {}).get(s["id"])]
        if cev:
            y += ["### " + s["metin"], ""] + ["- %s (%s)" % (c, d) for d, c in cev] + [""]
    ek = [(f.get("ders_basligi"), k, v) for f in formlar for k, v in (f.get("cevaplar") or {}).items() if k not in soru]
    if ek:
        y += ["### Derse özel sorular", ""] + ["- %s · %s: %s" % (d, k, v) for d, k, v in ek] + [""]
    y += ["## Eğitmenin (Claude) tespitleri", ""]
    tum = [(f.get("ders_basligi"), t) for f in formlar for t in f.get("tespitler") or []]
    if not tum:
        y.append("Tespit yok.")
    for tur, ad in TESPIT_TURLERI.items():
        grup = [(d, t) for d, t in tum if t.get("tur") == tur]
        if grup:
            y += ["### %s (%d)" % (ad, len(grup)), ""]
            y += ["- %s%s (%s)" % (t["ayrinti"], (" · yer: %s" % t["yer"]) if t.get("yer") else "", d) for d, t in grup]
            y.append("")
    oz = [f["calisma_ozeti"] for f in formlar if f.get("calisma_ozeti")]
    if oz:
        basari = [o["genel_basari"] for o in oz if o.get("genel_basari") is not None]
        y += ["## Çalışma özetleri", "",
              "%d form çalışma özetiyle geldi. Ortalama %.1f oturum%s%s." % (
                  len(oz), sum(o["oturum"] for o in oz) / len(oz),
                  (", %.0f dk" % (sum(o["dakika"] for o in oz if o.get("dakika")) / max(1, len([o for o in oz if o.get("dakika")]))))
                  if any(o.get("dakika") for o in oz) else "",
                  (", genel başarı ortalaması %s" % karne_.yuzde(sum(basari) / len(basari))) if basari else "")]
        durum = {}
        for o in oz:
            for h in o.get("hedefler", []):
                durum.setdefault(h["id"], {}).setdefault(h["durum"], 0)
                durum[h["id"]][h["durum"]] += 1
        if durum:
            y += ["", "| Hedef | " + " | ".join(karne_.DURUM_AD.get(d, d) for d in karne_.DURUM_AD) + " |",
                  "| --- |" + " --- |" * len(karne_.DURUM_AD)]
            for hid in sorted(durum):
                y.append("| %s | %s |" % (hid, " | ".join(str(durum[hid].get(d, 0)) for d in karne_.DURUM_AD)))
    return "\n".join(y) + "\n"


def topla(yollar, cikis=None, deneme_dahil=False):
    formlar = formlari_oku(yollar)
    metin = ozetle(formlar, deneme_dahil)
    if cikis:
        with open(cikis, "w", encoding="utf-8") as fh:
            fh.write(metin)
    return {"form_sayisi": len(formlar), "metin": metin, "dosya": cikis}


def main():
    ap = argparse.ArgumentParser(description="KlinikKoç ders sonu değerlendirme formları")
    ap.add_argument("--topla", nargs="+", metavar="KLASÖR", help="formları topla ve özet yaz")
    ap.add_argument("--cikis", help="özetin yazılacağı .md dosyası")
    ap.add_argument("--deneme-dahil", action="store_true", help="öğretmen deneme kayıtlarını da say")
    a = ap.parse_args()
    if a.topla:
        r = topla(a.topla, a.cikis, a.deneme_dahil)
        print(r["metin"] if not a.cikis else "%d form özetlendi: %s" % (r["form_sayisi"], a.cikis))
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
