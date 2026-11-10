#!/usr/bin/env python3
"""KlinikKoç ders hazırlama sihirbazı (öğretmen tarafı).

Öğretmen bir dersi adım adım tanımlar; sihirbaz taslağı saklar, önerileri getirir ve sonunda ders paketini kurar:

  1. Ders kartı: başlık, düzey, eğitmen (İnci: lisans, Mercan: uzmanlık), süre.
  2. Kaynaklar: DOI listesi yapıştırılır; künye, özet ve açık erişim bilgisi herkese açık kaynaklardan
     (Crossref, OpenAlex) gelir. Ana derleme işaretlenir.
  3. Öğretmenin içeriği: Word/PDF/metin ders notu (bölümlere ayrılır), vaka kartları, hazır sorular,
     "eğitimde dikkat edilecek yerler" ve bilinen yanılgılar. Her not, vaka ve soru bir paylaşım
     kademesi taşır: fakulte (yalnız fakülte paketi), acik (herkese açık, CC BY), paylasilmaz (yalnız bu
     bilgisayar).
  4. Öneriler: hedef taslakları, Bloom düzeyleri, terimler ve soru taslakları. Kural tabanlı öneriler her
     zaman çalışır; Claude (eğitmen aracı sihirbaz_oku/sihirbaz_oner) daha iyilerini yazar. Öğretmen her
     birini kabul eder, düzeltir ya da siler; onaylanmamış öneri pakete girmez.
  5. Paketle: dersi bu bilgisayara kurar (lessons/ozel-<ders>, tam hali) ve iki zip üretir:
     <ders>-acik.zip (yalnız açık içerik) ve <ders>-fakulte.zip (açık + fakülte). "paylasilmaz" hiçbir
     pakete girmez. Paketlerde makalelerin yalnız listesi vardır.

Taslaklar program klasörünün dışında, kalıcı veri klasöründe durur (güncellemede silinmez):
  <veri>/sihirbaz/<ders>/taslak.json   ve   <veri>/sihirbaz/<ders>/dosyalar/

Kullanım:
  python tools/sihirbaz.py --liste
  python tools/sihirbaz.py --yeni <ders-kimligi> --baslik "Akut periodontal lezyonlar"
  python tools/sihirbaz.py --doi <ders> 10.1111/jcpe.12941 10.1111/jcpe.12946
  python tools/sihirbaz.py --not <ders> notum.docx --kademe fakulte
  python tools/sihirbaz.py --oner <ders>          kural tabanlı öneriler
  python tools/sihirbaz.py --paketle <ders>
"""
import argparse
import copy
import glob
import html
import json
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.parse
import zipfile
from xml.etree import ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import makale_bulucu as mb  # noqa: E402
import veri_yeri  # noqa: E402

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KADEMELER = ("fakulte", "acik", "paylasilmaz")
KADEME_ADI = {"fakulte": "Yalnız fakülte", "acik": "Herkese açık (CC BY)", "paylasilmaz": "Hiç paylaşılmaz"}
BLOOM = ("hatirla", "anla", "uygula", "cozumle", "degerlendir", "olustur")
DUZEYLER = ("Lisans", "Uzmanlık")
EGITMENLER = ("inci", "mercan")

# Hedef cümlesindeki fiilden Bloom düzeyi (öneri; öğretmen değiştirir). Sözcük kökleriyle eşlenir.
BLOOM_FIILLERI = [
    ("olustur", ("oluştur", "tasarla", "planla", "geliştir", "kurgula", "plan yap", "plan kur", "tedavi planı")),
    ("degerlendir", ("değerlendir", "savun", "gerekçelendir", "eleştir", "karar ver", "seç", "yargıla", "tartış")),
    ("cozumle", ("ayırt", "ayır", "karşılaştır", "çözümle", "analiz", "ilişkilendir", "ayırıcı tanı", "sorgula")),
    ("uygula", ("uygula", "hesapla", "kullan", "göster", "yorumla", "tanı koy", "muayene")),
    ("anla", ("açıkla", "özetle", "sınıflandır", "örnekle", "betimle", "tarif et", "anlat")),
    ("hatirla", ("tanımla", "say", "listele", "hatırla", "adlandır", "belirt", "sırala")),
]

TIBBI_EKLER = ("itis", "itisi", "oz", "ozis", "emi", "plasti", "ektomi", "patisi", "patiler", "algia", "oma")


# ---------- Dosya yardımcıları ----------
def _json_oku(yol, varsayilan=None):
    try:
        with open(yol, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return varsayilan


def _json_yaz(yol, veri):
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    fd, gecici = tempfile.mkstemp(dir=os.path.dirname(yol), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=1)
    os.replace(gecici, yol)


def kimlik_yap(metin, onek=""):
    tr = str.maketrans("çğıöşüÇĞİÖŞÜâîû", "cgiosuCGIOSUaiu")
    s = re.sub(r"[^a-z0-9]+", "-", (metin or "").translate(tr).lower()).strip("-")[:50].strip("-")
    return (onek + s) if s else ""


def ders_gecerli(ders):
    if not ders or not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,60}", ders) or ders.startswith("ozel-") or ders == "tanitim":
        raise ValueError("Ders kimliği küçük harf, rakam ve tireden oluşmalı (ör. akut-periodontal-lezyonlar); "
                         "'ozel-' ile başlamamalı.")
    return ders


def sihirbaz_kok():
    return os.path.join(veri_yeri.veri_kok(), "sihirbaz")


def taslak_klasoru(ders):
    return os.path.join(sihirbaz_kok(), ders_gecerli(ders))


def taslak_yolu(ders):
    return os.path.join(taslak_klasoru(ders), "taslak.json")


def dosya_klasoru(ders):
    return os.path.join(taslak_klasoru(ders), "dosyalar")


def bos_taslak(ders, baslik=""):
    sablon = _json_oku(os.path.join(KOK, "sablonlar", "ders-taslagi-bos.json"), {}) or {}
    t = copy.deepcopy(sablon)
    t.pop("aciklama", None)
    t.update({"surum": 1, "ders": ders, "baslik": baslik or t.get("baslik") or ders,
              "olusturma": time.strftime("%Y-%m-%d %H:%M")})
    for k, v in (("duzey", "Lisans"), ("egitmen", "inci"), ("sure_dk", 20), ("kaynaklar", []), ("notlar", []),
                 ("vakalar", []), ("sorular", []), ("dikkat", []), ("yanilgilar", []), ("hedefler", []),
                 ("terimler", []), ("oneriler", {})):
        t.setdefault(k, v)
    return t


def taslak_oku(ders):
    t = _json_oku(taslak_yolu(ders))
    if not isinstance(t, dict):
        raise FileNotFoundError("Böyle bir ders taslağı yok: %s" % ders)
    return t


def taslak_yaz(ders, t):
    t["guncelleme"] = time.strftime("%Y-%m-%d %H:%M")
    _json_yaz(taslak_yolu(ders), t)
    return t


def yeni(ders, baslik=""):
    ders_gecerli(ders)
    if os.path.exists(taslak_yolu(ders)):
        raise FileExistsError("Bu kimlikle bir taslak zaten var: %s" % ders)
    return taslak_yaz(ders, bos_taslak(ders, baslik))


def liste():
    out = []
    for yol in sorted(glob.glob(os.path.join(sihirbaz_kok(), "*", "taslak.json"))):
        t = _json_oku(yol) or {}
        out.append({"ders": t.get("ders") or os.path.basename(os.path.dirname(yol)), "baslik": t.get("baslik"),
                    "guncelleme": t.get("guncelleme"), "paket": (t.get("son_paket") or {}).get("tarih")})
    return out


# ---------- Ders kartı ve listeler ----------
ALANLAR = {"baslik": str, "duzey": str, "egitmen": str, "sure_dk": int, "aciklama_ogrenci": str,
           "geri_bildirim_eposta": str}


def kart_guncelle(ders, alanlar):
    t = taslak_oku(ders)
    for k, v in (alanlar or {}).items():
        if k not in ALANLAR:
            continue
        if k == "duzey" and v not in DUZEYLER:
            raise ValueError("Düzey Lisans ya da Uzmanlık olmalı.")
        if k == "egitmen" and v not in EGITMENLER:
            raise ValueError("Eğitmen inci ya da mercan olmalı.")
        if k == "geri_bildirim_eposta" and v and not re.fullmatch(r"[^@\s<>\"]+@[^@\s<>\"]+\.[^@\s<>\"]+", str(v).strip()):
            raise ValueError("Geri bildirim adresi bir e-posta adresi olmalı.")
        if k == "geri_bildirim_eposta" and v:
            v = str(v).strip()
        t[k] = ALANLAR[k](v) if v is not None else None
    return taslak_yaz(ders, t)


LISTELER = {"dikkat", "yanilgilar", "sorular", "hedefler", "terimler", "kaynaklar", "notlar", "vakalar"}


def oge_kaydet(ders, liste_adi, oge):
    """Bir listeye öğe ekler ya da aynı id'li öğeyi günceller (öğretmenin elle yazdığı ya da düzelttiği)."""
    if liste_adi not in LISTELER:
        raise ValueError("Bilinmeyen liste: %s" % liste_adi)
    t = taslak_oku(ders)
    lst = t.setdefault(liste_adi, [])
    if liste_adi == "terimler":
        terim = (oge.get("terim") if isinstance(oge, dict) else str(oge)).strip()
        if terim and terim not in [x.get("terim") for x in lst]:
            lst.append({"terim": terim})
        return taslak_yaz(ders, t)
    oge = dict(oge)
    if "kademe" in oge and oge["kademe"] not in KADEMELER:
        raise ValueError("Kademe fakulte, acik ya da paylasilmaz olmalı.")
    if "bloom" in oge and oge["bloom"] and oge["bloom"] not in BLOOM:
        raise ValueError("Bloom düzeyi şunlardan biri olmalı: " + ", ".join(BLOOM))
    if not oge.get("id"):
        onek = {"dikkat": "D", "yanilgilar": "Y", "sorular": "S", "hedefler": "H"}.get(liste_adi, "X")
        var = {x.get("id") for x in lst}
        n = len(lst) + 1
        while "%s%d" % (onek, n) in var:
            n += 1
        oge["id"] = "%s%d" % (onek, n)
    for i, x in enumerate(lst):
        if x.get("id") == oge["id"]:
            yeni_oge = dict(x)
            yeni_oge.update(oge)
            lst[i] = yeni_oge
            break
    else:
        lst.append(oge)
    return taslak_yaz(ders, t)


def oge_sil(ders, liste_adi, kimlik):
    if liste_adi not in LISTELER:
        raise ValueError("Bilinmeyen liste: %s" % liste_adi)
    t = taslak_oku(ders)
    anahtar = "terim" if liste_adi == "terimler" else "id"
    t[liste_adi] = [x for x in t.get(liste_adi, []) if x.get(anahtar) != kimlik]
    if liste_adi == "notlar":
        shutil.rmtree(os.path.join(dosya_klasoru(ders), "notlar", kimlik), ignore_errors=True)
    if liste_adi == "vakalar":
        shutil.rmtree(os.path.join(dosya_klasoru(ders), "vakalar", kimlik), ignore_errors=True)
    return taslak_yaz(ders, t)


# ---------- Kaynaklar: DOI → künye ----------
def dois_ayikla(metin):
    """Yapıştırılan metinden (DOI listesi, kaynakça, bağlantılar) DOI'leri sırayla, tekrarsız çıkarır."""
    out = []
    for m in mb.DOI_KALIBI.findall(metin or ""):
        d = mb.doi_temizle(m)
        if d and d not in out:
            out.append(d)
    return out


def _yazar_kisaltma(yazar):
    soy = (yazar.get("family") or yazar.get("name") or "").strip()
    ad = (yazar.get("given") or "").strip()
    if re.fullmatch(r"[A-ZÇĞİÖŞÜ]{1,3}", ad):  # zaten baş harfler: "PN"
        bas = ad
    else:
        bas = "".join(p[0] for p in re.split(r"[\s.-]+", ad) if p)
    return (soy + (" " + bas.upper() if bas else "")).strip()


def kisa_ad(soyadlar, yil):
    if not soyadlar:
        return str(yil or "")
    if len(soyadlar) == 1:
        s = soyadlar[0]
    elif len(soyadlar) == 2:
        s = "%s ve %s" % tuple(soyadlar)
    else:
        s = "%s ve ark." % soyadlar[0]
    return ("%s %s" % (s, yil)).strip() if yil else s


def crossref_cevir(m, doi):
    """Crossref 'message' nesnesinden künye kaydı."""
    yazarlar = m.get("author") or []
    adlar = [_yazar_kisaltma(a) for a in yazarlar]
    if len(adlar) > 6:
        adlar = adlar[:6] + ["et al"]
    baslik = html.unescape(re.sub(r"<[^>]+>", "", " ".join(m.get("title") or []))).strip()
    dergi = (m.get("short-container-title") or m.get("container-title") or [""])[0]
    tarih = ((m.get("published-print") or m.get("published-online") or m.get("issued") or {}).get("date-parts") or [[None]])[0]
    yil = tarih[0] if tarih else None
    cilt, sayi, sayfa = m.get("volume"), m.get("issue"), m.get("page")
    atif = "%s. %s. %s." % (", ".join(adlar), baslik.rstrip("."), dergi) if adlar else "%s. %s." % (baslik, dergi)
    if yil:
        atif += " %s" % yil
        if cilt:
            atif += ";%s" % cilt + ("(%s)" % sayi if sayi else "")
        if sayfa:
            atif += ":%s" % sayfa.replace("-", "–")
        atif += "."
    atif += " doi:%s" % doi
    ozet = m.get("abstract")
    if ozet:
        ozet = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", ozet))).strip()
        ozet = re.sub(r"^(Abstract|ABSTRACT)\s*", "", ozet)
    lisans = None
    for lis in m.get("license") or []:
        u = (lis.get("URL") or "").lower()
        if "creativecommons.org/licenses/by/" in u:
            lisans = "CC BY"
        elif "creativecommons.org/licenses/by-nc" in u and not lisans:
            lisans = "CC BY-NC"
    soyadlar = [(a.get("family") or a.get("name") or "").strip() for a in yazarlar if a.get("family") or a.get("name")]
    return {"doi": doi, "baslik": baslik, "dergi": dergi, "yil": yil, "atif": atif,
            "kisa": kisa_ad(soyadlar, yil), "ozet": ozet, "lisans": lisans,
            "tur": m.get("type")}


def openalex_ozet(ters):
    """OpenAlex abstract_inverted_index → düz metin."""
    if not ters:
        return None
    konum = []
    for sozcuk, yerler in ters.items():
        for y in yerler:
            konum.append((y, sozcuk))
    return " ".join(s for _, s in sorted(konum)) or None


def kunye_getir(doi, ag=None):
    """Bir DOI'nin künyesi, özeti ve açık erişim durumu. İnternet yoksa yalnız DOI ile döner."""
    doi = mb.doi_temizle(doi)
    ag = ag or mb.Ag(zaman=20)
    k = {"doi": doi}
    q = urllib.parse.quote(doi, safe="/")
    try:
        cr = ag.json("https://api.crossref.org/works/" + q)
        k.update(crossref_cevir(cr.get("message") or {}, doi))
    except Exception as e:
        k["uyari"] = "Künye alınamadı (%s)." % ("internet yok" if not ag.ulasildi else "DOI bulunamadı")
        k["_hata"] = str(e)[:200]
    try:
        w = ag.json("https://api.openalex.org/works/doi:" + q)
        oa = w.get("open_access") or {}
        k["acik_erisim"] = bool(oa.get("is_oa"))
        k["oa_turu"] = oa.get("oa_status")
        if not k.get("ozet"):
            k["ozet"] = openalex_ozet(w.get("abstract_inverted_index"))
        if not k.get("baslik") and w.get("title"):
            k["baslik"] = w["title"]
            k["yil"] = w.get("publication_year")
    except Exception:
        pass
    k.pop("_hata", None)
    return k


def doi_ekle(ders, metin, ag=None):
    """Yapıştırılan DOI'leri taslağa ekler ve künyelerini getirir. (eklenen, zaten olan) sayıları döner."""
    t = taslak_oku(ders)
    var = {mb.doi_temizle(k.get("doi")) for k in t["kaynaklar"]}
    yeni_dois = [d for d in dois_ayikla(metin) if d not in var]
    ag = ag or mb.Ag(zaman=20)
    kimlikler = {k["id"] for k in t["kaynaklar"]}
    for d in yeni_dois:
        k = kunye_getir(d, ag)
        kid = kimlik_yap(k.get("kisa") or d.replace("/", "-")) or "kaynak"
        n, taban = 2, kid
        while kid in kimlikler:
            kid, n = "%s-%d" % (taban, n), n + 1
        kimlikler.add(kid)
        k["id"] = kid
        k.setdefault("kisa", d)
        if not any(x.get("rol") == "ana" for x in t["kaynaklar"]) and not t["kaynaklar"]:
            k["rol"] = "ana"
        t["kaynaklar"].append(k)
    taslak_yaz(ders, t)
    return {"eklenen": len(yeni_dois), "zaten_vardi": len(dois_ayikla(metin)) - len(yeni_dois),
            "kaynaklar": t["kaynaklar"]}


def kunyeleri_yenile(ders, ag=None):
    """Künyesi eksik kalmış (ör. internet yokken eklenen) kaynakları yeniden sorar."""
    t = taslak_oku(ders)
    ag = ag or mb.Ag(zaman=20)
    for i, k in enumerate(t["kaynaklar"]):
        if k.get("doi") and (k.get("uyari") or not k.get("atif")):
            yeni_k = kunye_getir(k["doi"], ag)
            for alan in ("id", "rol"):
                if k.get(alan):
                    yeni_k[alan] = k[alan]
            t["kaynaklar"][i] = yeni_k
    return taslak_yaz(ders, t)


def ana_kaynak(ders, kid):
    t = taslak_oku(ders)
    for k in t["kaynaklar"]:
        if k["id"] == kid:
            k["rol"] = "ana"
        elif k.get("rol") == "ana":
            k.pop("rol")
    return taslak_yaz(ders, t)


# ---------- Ders notu: Word / PDF / metin → bölümler ----------
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_bolumleri(yol):
    """Word belgesini başlıklara göre bölümlere ayırır: [{baslik, duzey, metin}].
    Başlık: Heading/Başlık biçemli paragraf. Tablolar satır satır metne çevrilir."""
    with zipfile.ZipFile(yol) as z:
        kok = ET.fromstring(z.read("word/document.xml"))
        stiller = {}
        if "word/styles.xml" in z.namelist():
            for s in ET.fromstring(z.read("word/styles.xml")).iter(W + "style"):
                ad = s.find(W + "name")
                stiller[s.get(W + "styleId")] = (ad.get(W + "val") if ad is not None else "") or ""
    govde = kok.find(W + "body")
    bolumler, simdiki = [], {"baslik": "Giriş", "duzey": 1, "satirlar": []}

    def paragraf_metni(p):
        parcalar = []
        for e in p.iter():
            if e.tag == W + "t" and e.text:
                parcalar.append(e.text)
            elif e.tag in (W + "tab",):
                parcalar.append("\t")
            elif e.tag in (W + "br", W + "cr"):
                parcalar.append("\n")
        return "".join(parcalar).strip()

    def baslik_duzeyi(p):
        ppr = p.find(W + "pPr")
        if ppr is None:
            return None
        ol = ppr.find(W + "outlineLvl")
        if ol is not None and ol.get(W + "val", "").isdigit() and int(ol.get(W + "val")) < 3:
            return int(ol.get(W + "val")) + 1
        st = ppr.find(W + "pStyle")
        if st is None:
            return None
        sid = st.get(W + "val") or ""
        ad = (stiller.get(sid) or sid).lower()
        m = re.search(r"(heading|başlık|baslik|title)\s*(\d)?", ad)
        if not m:
            return None
        return int(m.group(2)) if m.group(2) else 1

    for e in list(govde) if govde is not None else []:
        if e.tag == W + "p":
            metin = paragraf_metni(e)
            if not metin:
                continue
            d = baslik_duzeyi(e)
            if d and d <= 2 and len(metin) < 160:
                if simdiki["satirlar"] or simdiki["baslik"] != "Giriş":
                    bolumler.append(simdiki)
                simdiki = {"baslik": metin, "duzey": d, "satirlar": []}
            else:
                simdiki["satirlar"].append(metin)
        elif e.tag == W + "tbl":
            for tr in e.iter(W + "tr"):
                hucreler = [paragraf_metni(tc) for tc in tr.iter(W + "tc")]
                hucreler = [h for h in hucreler if h]
                if hucreler:
                    simdiki["satirlar"].append(" | ".join(hucreler))
    bolumler.append(simdiki)
    return [{"baslik": b["baslik"], "duzey": b["duzey"], "metin": "\n".join(b["satirlar"]).strip()}
            for b in bolumler if b["satirlar"] or b["baslik"] != "Giriş"]


def tr_baslik(s):
    """Türkçe büyük/küçük harf kurallarıyla 'Başlık Biçimi' (TANI ÖLÇÜTLERİ → Tanı Ölçütleri)."""
    kucuk = s.replace("I", "ı").replace("İ", "i").lower()
    return " ".join((w[0].replace("i", "İ").upper() + w[1:]) if w else w for w in kucuk.split(" "))


def metin_bolumleri(metin):
    """Düz metin ya da Markdown: '#' başlıkları ya da tamamı büyük harf kısa satırlar bölüm açar."""
    bolumler, simdiki = [], {"baslik": "Giriş", "duzey": 1, "satirlar": []}
    for satir in metin.splitlines():
        s = satir.strip()
        m = re.match(r"^(#{1,3})\s+(.+)$", s)
        buyuk = len(s) < 80 and len(s.split()) <= 8 and s.upper() == s and re.search(r"[A-ZÇĞİÖŞÜ]{3}", s or "")
        if m or buyuk:
            if simdiki["satirlar"] or simdiki["baslik"] != "Giriş":
                bolumler.append(simdiki)
            simdiki = {"baslik": (m.group(2) if m else tr_baslik(s)), "duzey": len(m.group(1)) if m else 1, "satirlar": []}
        elif s:
            simdiki["satirlar"].append(s)
    bolumler.append(simdiki)
    return [{"baslik": b["baslik"], "duzey": b["duzey"], "metin": "\n".join(b["satirlar"]).strip()}
            for b in bolumler if b["satirlar"] or b["baslik"] != "Giriş"]


def pdf_bolumleri(yol):
    if not mb.pypdf_var():
        raise RuntimeError("PDF okuyucu kurulu değil: python tools/makale_bulucu.py --kur")
    from pypdf import PdfReader
    r = PdfReader(yol)
    du = mb._dizin_uret()
    return [{"baslik": "Sayfa %d" % (i + 1), "duzey": 1, "metin": du.temizle(p.extract_text() or "")}
            for i, p in enumerate(r.pages) if (p.extract_text() or "").strip()]


def notu_donustur(yol):
    uz = os.path.splitext(yol)[1].lower()
    if uz == ".docx":
        return docx_bolumleri(yol)
    if uz == ".pdf":
        return pdf_bolumleri(yol)
    if uz in (".txt", ".md"):
        with open(yol, encoding="utf-8", errors="replace") as f:
            return metin_bolumleri(f.read())
    if uz == ".doc":
        raise ValueError("Eski Word biçimi (.doc) okunamıyor. Word'de 'Farklı kaydet → .docx' ile kaydedip yeniden ekleyin.")
    raise ValueError("Desteklenen not biçimleri: .docx, .pdf, .txt, .md")


YAYIN_IZLERI = (
    (r"\b10\.\d{4,9}/\S+", "DOI numarası"),
    (r"©|\(c\)\s*\d{4}|copyright", "telif notu"),
    (r"all rights reserved|tüm hakları saklıdır|no part of this (article|publication)", "\"tüm hakları saklıdır\" notu"),
    (r"for personal use only|not for (re)?distribution|without (the )?written permission", "\"yalnız kişisel kullanım\" notu"),
    (r"\b(received|submitted)\b[^.]{0,40}\baccepted\b", "dergi geliş/kabul tarihleri"),
    (r"quintessence|elsevier|wiley|springer|taylor & francis|wolters kluwer|thieme|karger|sage publications",
     "yayınevi adı"),
)


def yayin_izi(bolumler, ilk=6000):
    """Not yayımlanmış bir dergi makalesine benziyorsa nedenlerini döner (boş liste: benzemiyor).
    Makalenin kendisi pakete giremez; öğretmene sorulur."""
    metin = " ".join("%s %s" % (b.get("baslik", ""), b.get("metin", "")) for b in bolumler)[:ilk].lower()
    return [ad for desen, ad in YAYIN_IZLERI if re.search(desen, metin)]


def not_ekle(ders, veri, ad, kademe="fakulte"):
    if kademe not in KADEMELER:
        raise ValueError("Kademe fakulte, acik ya da paylasilmaz olmalı.")
    t = taslak_oku(ders)
    nid = kimlik_yap(os.path.splitext(ad)[0], "not-") or "not-%d" % (len(t["notlar"]) + 1)
    var = {n["id"] for n in t["notlar"]}
    n, taban = 2, nid
    while nid in var:
        nid, n = "%s-%d" % (taban, n), n + 1
    klasor = os.path.join(dosya_klasoru(ders), "notlar", nid)
    os.makedirs(klasor, exist_ok=True)
    yol = os.path.join(klasor, mb.guvenli_ad(ad, 120))
    with open(yol, "wb") as f:
        f.write(veri)
    try:
        bolumler = notu_donustur(yol)
    except Exception:
        shutil.rmtree(klasor, ignore_errors=True)
        raise
    if not bolumler or sum(len(b["metin"]) for b in bolumler) < 50:
        shutil.rmtree(klasor, ignore_errors=True)
        raise ValueError("Bu dosyadan metin çıkmadı (taranmış PDF ya da boş belge olabilir).")
    _json_yaz(os.path.join(klasor, "bolumler.json"), bolumler)
    izler = yayin_izi(bolumler)
    t["notlar"].append({"id": nid, "ad": ad, "kademe": kademe, "bolum_sayisi": len(bolumler),
                        "basliklar": [b["baslik"] for b in bolumler],
                        "sozcuk": sum(len(b["metin"].split()) for b in bolumler)})
    if len(izler) >= 2:  # tek iz (ör. kaynakçadaki bir DOI) kendi notunda da olur
        t["notlar"][-1]["yayin_izi"] = izler
    taslak_yaz(ders, t)
    return t["notlar"][-1]


def not_bolumleri(ders, nid):
    return _json_oku(os.path.join(dosya_klasoru(ders), "notlar", nid, "bolumler.json"), []) or []


def tum_bolumler(t):
    """Bütün notların bölümleri sırayla, kalıcı sayfa numaralarıyla: [(sayfa, not, bölüm)]."""
    out, sayfa = [], 0
    for n in t.get("notlar", []):
        for b in not_bolumleri(t["ders"], n["id"]):
            sayfa += 1
            out.append((sayfa, n, b))
    return out


# ---------- Vaka kartları ----------
def vaka_ekle(ders, veri, ad, kademe="fakulte"):
    """Vaka kartı JSON'u ya da bir vaka klasörünün zip'i (kart + görseller)."""
    if kademe not in KADEMELER:
        raise ValueError("Kademe fakulte, acik ya da paylasilmaz olmalı.")
    import vaka_denetle
    t = taslak_oku(ders)
    gecici = tempfile.mkdtemp()
    try:
        if ad.lower().endswith(".zip"):
            with zipfile.ZipFile(_bayt_dosya(veri, gecici, "v.zip")) as z:
                for i in z.infolist():
                    p = i.filename.replace("\\", "/")
                    if i.is_dir() or ".." in p.split("/") or p.startswith("/") or p.startswith("__MACOSX/"):
                        continue
                    hedef = os.path.join(gecici, "ac", *p.split("/"))
                    os.makedirs(os.path.dirname(hedef), exist_ok=True)
                    with z.open(i) as k, open(hedef, "wb") as f:
                        shutil.copyfileobj(k, f)
            kartlar = glob.glob(os.path.join(gecici, "ac", "**", "*.json"), recursive=True)
            if len(kartlar) != 1:
                raise ValueError("Zip'te tam bir vaka kartı (.json) olmalı; bulunan: %d" % len(kartlar))
            kart_yolu = kartlar[0]
            gorsel_kok = os.path.dirname(kart_yolu)
        else:
            kart_yolu = _bayt_dosya(veri, gecici, "kart.json")
            gorsel_kok = None
        kart = _json_oku(kart_yolu)
        if not isinstance(kart, dict):
            raise ValueError("Vaka kartı okunamadı (geçerli bir JSON değil).")
        vid = kart.get("id") or kimlik_yap(os.path.splitext(ad)[0])
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,60}", vid or ""):
            raise ValueError("Vaka kimliği (id) küçük harf, rakam ve tireden oluşmalı.")
        kart["id"] = vid
        hatalar, uyarilar = [], []
        try:
            denetim_yolu = os.path.join(gecici, "denetim", vid + ".json")
            _json_yaz(denetim_yolu, kart)
            hatalar, uyarilar, _ = vaka_denetle.denetle(denetim_yolu)
            # Ders henüz kurulmadığı için derse bağlı denetimler paketlemede yapılır.
            hatalar = [h for h in hatalar if not any(x in str(h) for x in DERSE_BAGLI)]
            uyarilar = [u for u in uyarilar if not any(x in str(u) for x in DERSE_BAGLI)]
        except Exception as e:  # denetleyicinin arayüzü değişirse kartı yine al, uyar
            uyarilar = ["Vaka denetlenemedi: %s" % e]
        klasor = os.path.join(dosya_klasoru(ders), "vakalar", vid)
        shutil.rmtree(klasor, ignore_errors=True)
        os.makedirs(klasor)
        _json_yaz(os.path.join(klasor, "kart.json"), kart)
        if gorsel_kok:
            for yol in glob.glob(os.path.join(gorsel_kok, "**", "*"), recursive=True):
                if os.path.isfile(yol) and yol.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    # Düz klasöre: kartın 'gorsel' yolları paketlemede vakalar/<id>/<dosya adı> olur.
                    hedef = os.path.join(klasor, "gorseller", mb.guvenli_ad(os.path.basename(yol), 120))
                    os.makedirs(os.path.dirname(hedef), exist_ok=True)
                    shutil.copy2(yol, hedef)
    finally:
        shutil.rmtree(gecici, ignore_errors=True)
    t["vakalar"] = [v for v in t["vakalar"] if v["id"] != vid] + [{
        "id": vid, "baslik": kart.get("baslik") or vid, "kademe": kademe, "kurgusal": kart.get("kurgusal"),
        "hata": [str(h) for h in hatalar][:10], "uyari": [str(u) for u in uyarilar][:10]}]
    taslak_yaz(ders, t)
    return t["vakalar"][-1]


# Ders henüz kurulmadan anlamsız olan denetimler (paketlemeden sonra kurulan derste yeniden denetlenir).
DERSE_BAGLI = ("Ders bulunamadı", "derste yok", "Kart lessons/", "görsel dosyası yok", "dosya adıyla")


def _bayt_dosya(veri, klasor, ad):
    yol = os.path.join(klasor, ad)
    with open(yol, "wb") as f:
        f.write(veri)
    return yol


# ---------- Öneriler ----------
def bloom_oner(cumle):
    s = (cumle or "").lower()
    for duzey, kokler in BLOOM_FIILLERI:
        if any(k in s for k in kokler):
            return duzey
    return "anla"


def bilinen_terimler():
    out = set()
    for yol in [os.path.join(KOK, "ses", "terimler.json")] + glob.glob(os.path.join(KOK, "lessons", "*", "terimler.json")):
        j = _json_oku(yol, {}) or {}
        out.update(t for t in j.get("terimler") or [] if isinstance(t, str))
    return out


def kural_onerileri(ders):
    """İnternetsiz, modelsiz öneriler: not başlıklarından hedef taslakları, fiilden Bloom düzeyi,
    notta geçen bilinen terimler ve sık geçen tıbbi sözcük öbekleri. Claude'un önerileri bunların yerini alır."""
    t = taslak_oku(ders)
    bolumler = tum_bolumler(t)
    hedefler = []
    for sayfa, n, b in bolumler:
        bas = b["baslik"].strip()
        if not bas or re.fullmatch(r"(giriş|sayfa \d+|kaynaklar|references)", bas.lower()):
            continue
        hedefler.append({"baslik": bas, "bloom": bloom_oner(bas), "sayfalar": [sayfa],
                         "gerekce": "Not bölümünün başlığından (%s)." % n["ad"]})
    if not hedefler:
        for sayfa, n, b in bolumler[:8]:
            ilk = re.split(r"(?<=[.!?])\s", b["metin"])[0][:120]
            hedefler.append({"baslik": ilk, "bloom": "anla", "sayfalar": [sayfa], "gerekce": "Sayfanın ilk cümlesi."})
    metin = " ".join(b["metin"] for _, _, b in bolumler) + " " + " ".join(k.get("ozet") or "" for k in t["kaynaklar"])
    kucuk = metin.lower()
    terimler = sorted({x for x in bilinen_terimler() if len(x) > 3 and x.lower() in kucuk})
    sayac = {}
    for m in re.finditer(r"\b([a-zçğıöşü]+(?:%s))\b" % "|".join(TIBBI_EKLER), kucuk):
        sayac[m.group(1)] = sayac.get(m.group(1), 0) + 1
    var = {x.lower() for x in terimler} | {x.get("terim", "").lower() for x in t.get("terimler", [])}
    for s, n in sorted(sayac.items(), key=lambda x: -x[1]):
        if n >= 3 and s not in var and len(s) > 5:
            terimler.append(s)
    terimler = [x for x in terimler if x.lower() not in {y.get("terim", "").lower() for y in t.get("terimler", [])}]
    sorular = [{"metin": "%s konusunu kendi sözlerinle açıkla." % h["baslik"], "tur": "acik", "bloom": "anla",
                "hedef_baslik": h["baslik"], "gerekce": "Hedef başına bir açık uçlu soru taslağı."}
               for h in hedefler[:6]]
    return oneri_yaz(ders, {"hedefler": hedefler, "terimler": terimler[:40], "sorular": sorular}, kim="kural")


def oneri_yaz(ders, oneriler, kim="claude"):
    """Önerileri taslağa yazar (önceki aynı türden öneriler değiştirilir). Onaylanmadıkça pakete girmez."""
    t = taslak_oku(ders)
    o = t.setdefault("oneriler", {})
    for tur in ("hedefler", "terimler", "sorular", "yanilgilar"):
        if tur not in oneriler or oneriler[tur] is None:
            continue
        lst = []
        for i, x in enumerate(oneriler[tur], 1):
            if tur == "terimler":
                x = {"terim": x} if isinstance(x, str) else dict(x)
                if not x.get("terim"):
                    continue
            else:
                x = dict(x)
                if x.get("bloom") and x["bloom"] not in BLOOM:
                    x["bloom"] = bloom_oner(x.get("bloom"))
            x["oneri_id"] = "%s-%s-%d" % (kim, tur[0], i)
            x["kim"] = kim
            lst.append(x)
        o[tur] = lst
    o["tarih"] = time.strftime("%Y-%m-%d %H:%M")
    o["kim"] = kim
    taslak_yaz(ders, t)
    return o


def oneri_kabul(ders, tur, oneri_id, duzeltme=None):
    """Bir öneriyi (öğretmenin düzelttiği haliyle) asıl listeye taşır."""
    t = taslak_oku(ders)
    lst = (t.get("oneriler") or {}).get(tur) or []
    x = next((y for y in lst if y.get("oneri_id") == oneri_id), None)
    if not x:
        raise ValueError("Öneri bulunamadı (yenilenmiş olabilir).")
    lst.remove(x)
    taslak_yaz(ders, t)
    oge = {k: v for k, v in x.items() if k not in ("oneri_id", "kim", "gerekce")}
    oge.update(duzeltme or {})
    if tur == "sorular":
        oge.setdefault("kademe", "fakulte")
        hb = oge.pop("hedef_baslik", None)
        if hb and not oge.get("hedef"):
            h = next((h for h in t.get("hedefler", []) if h.get("baslik") == hb), None)
            if h:
                oge["hedef"] = h["id"]
    return oge_kaydet(ders, tur, oge)


def oneri_reddet(ders, tur, oneri_id):
    t = taslak_oku(ders)
    o = t.get("oneriler") or {}
    o[tur] = [y for y in o.get(tur) or [] if y.get("oneri_id") != oneri_id]
    return taslak_yaz(ders, t)


def claude_icin_malzeme(ders, en_cok_sozcuk=6000):
    """Eğitmen aracı sihirbaz_oku için: Claude'un öneri yazması gereken her şey, kısaltılmış olarak."""
    t = taslak_oku(ders)
    bolumler = []
    kalan = en_cok_sozcuk
    for sayfa, n, b in tum_bolumler(t):
        sozler = b["metin"].split()
        al = sozler[:max(0, min(len(sozler), kalan))]
        kalan -= len(al)
        bolumler.append({"sayfa": sayfa, "not": n["ad"], "kademe": n["kademe"], "baslik": b["baslik"],
                         "metin": " ".join(al) + (" …" if len(al) < len(sozler) else "")})
    return {
        "ders": ders, "baslik": t.get("baslik"), "duzey": t.get("duzey"), "egitmen": t.get("egitmen"),
        "sure_dk": t.get("sure_dk"),
        "kaynaklar": [{"id": k["id"], "kisa": k.get("kisa"), "baslik": k.get("baslik"), "rol": k.get("rol"),
                       "ozet": (k.get("ozet") or "")[:1500]} for k in t["kaynaklar"]],
        "not_bolumleri": bolumler,
        "vakalar": [{"id": v["id"], "baslik": v.get("baslik")} for v in t["vakalar"]],
        "ogretmenin_sorulari": t.get("sorular"), "dikkat_edilecekler": t.get("dikkat"),
        "bilinen_yanilgilar": t.get("yanilgilar"),
        "onayli_hedefler": t.get("hedefler"), "onayli_terimler": [x["terim"] for x in t.get("terimler", [])],
        "talimat": ONERI_TALIMAT,
    }


ONERI_TALIMAT = """Öğretmen için ÖNERİ yaz; karar öğretmenindir. sihirbaz_oner aracıyla şunları gönder:
- hedefler: [{baslik, bloom (hatirla|anla|uygula|cozumle|degerlendir|olustur), sayfalar [not sayfa numaraları],
  gerekce (tek cümle)}]. Düzeye ve süreye uygun sayıda (20 dakikalık lisans dersi için 4–8). Başlık, öğrencinin
  yapacağı şeyi söyleyen kısa bir cümle olsun ("Nekrotizan gingivitisi herpetik gingivostomatitten ayırt eder").
  Lisans dersinde ağırlık hatirla/anla/uygula; uzmanlıkta cozumle/degerlendir/olustur. Yalnız notta ve makale
  özetlerinde olan konular. Onaylı hedeflerin aynısını yeniden önerme.
- terimler: [terim] — öğrencinin bilmesi ve konuşma tanımanın doğru yazması gereken alan terimleri (Türkçe; gerekirse
  İngilizcesi ayrı terim olarak).
- sorular: [{metin, tur (secmeli|acik), bloom, hedef_baslik, secenekler [metin] (seçmelide), dogru (seçenek sırası,
  0'dan), ornek_cevap (açıkta), rubrik [{olcut, zorunlu}] (açıkta), gerekce}] — her hedefe en az bir soru;
  vaka/klinik senaryo soruları uygula ve üstü düzeyler için.
- yanilgilar: [{metin, hedef_baslik}] — öğrencilerin bu konuda sık düştüğü yanlışlar (notta ya da dikkat
  edilecekler listesinde dayanağı olanlar).
Öğretmenin "dikkat edilecekler" listesine uy. Makale sonuçlarını kesinleştirme; araştırma ayrıntısı verme.
Bitince öğretmene önerilerin sihirbaz sayfasında onay beklediğini söyle."""


# ---------- Denetim ve paketleme ----------
def denetle(ders):
    """Paketlemeden önce: eksikler (hata) ve dikkat edilecekler (uyarı)."""
    t = taslak_oku(ders)
    hatalar, uyarilar = [], []
    if not t.get("baslik"):
        hatalar.append("Ders başlığı yok.")
    if not t.get("hedefler"):
        hatalar.append("Onaylanmış hedef yok. Öneriler bölümünden hedefleri kabul edin ya da kendiniz yazın.")
    for h in t.get("hedefler", []):
        if not h.get("bloom"):
            hatalar.append("Hedef %s için Bloom düzeyi seçilmemiş." % h.get("id"))
    if not t.get("notlar") and not t.get("kaynaklar"):
        hatalar.append("Ne ders notu ne makale var: eğitmenin dayanacağı bir kaynak yok.")
    for n in t.get("notlar", []):
        if n.get("yayin_izi") and n.get("kademe") != "paylasilmaz" and not n.get("izinli"):
            hatalar.append(
                "Not \"%s\" yayımlanmış bir makaleye benziyor (%s). Abonelikli makalenin metni ve şekilleri pakete "
                "giremez: notu 'Hiç paylaşılmaz' yapın ve makaleyi DOI ile Kaynaklar'a ekleyin; her öğrenci kendi "
                "erişimiyle indirir. Metin sizinse, açık lisanslıysa (CC BY) ya da yayıncı izni varsa notun yanındaki "
                "'Paylaşma hakkım var' kutusunu işaretleyin." % (n["ad"], ", ".join(n["yayin_izi"])))
    for k in t.get("kaynaklar", []):
        if k.get("uyari"):
            uyarilar.append("%s: %s" % (k.get("kisa") or k.get("doi"), k["uyari"]))
    for v in t.get("vakalar", []):
        if v.get("hata"):
            hatalar.append("Vaka %s denetimden geçmedi: %s" % (v["id"], "; ".join(v["hata"][:3])))
        if v.get("kademe") == "acik" and not v.get("kurgusal"):
            uyarilar.append("Vaka %s herkese açık işaretli ama kurgusal değil: hasta görselleri açık pakete girer. "
                            "Hastanın eğitim amaçlı onayı ve kimliksizleştirme tamam mı?" % v["id"])
    for s in t.get("sorular", []):
        if s.get("tur") == "acik" and not s.get("ornek_cevap"):
            uyarilar.append("Soru %s: açık uçlu ama örnek cevap yok." % s.get("id"))
        if s.get("tur") == "secmeli" and (s.get("dogru") is None or not s.get("secenekler")):
            hatalar.append("Soru %s: seçmeli ama seçenekleri ya da doğru cevabı eksik." % s.get("id"))
    bekleyen = sum(len(v or []) for k, v in (t.get("oneriler") or {}).items() if isinstance(v, list))
    if bekleyen:
        uyarilar.append("%d öneri onay bekliyor; onaylanmayanlar pakete girmez." % bekleyen)
    if not any(n["kademe"] == "acik" for n in t.get("notlar", [])) and t.get("notlar"):
        uyarilar.append("Açık pakette ders notu olmayacak (hiçbir not herkese açık değil); başka üniversite "
                        "öğrencileri yalnız makale listesi, açık sorular ve açık vakalarla çalışır.")
    return {"hatalar": hatalar, "uyarilar": uyarilar}


def _ders_klasoru_yaz(t, hedef, kademeler, ders_adi):
    """Taslaktan bir ders klasörü yazar; yalnız verilen kademelerdeki not, vaka ve sorular girer.
    ders_adi: paketteki ders kimliği (açık pakette <ders>, fakültede ozel-<ders>)."""
    ders = t["ders"]
    os.makedirs(os.path.join(hedef, "kaynak"), exist_ok=True)
    sayfa_sayisi = 0
    girmeyen_sayfalar = []
    for sayfa, n, b in tum_bolumler(t):
        sayfa_sayisi = sayfa
        if n["kademe"] in kademeler:
            with open(os.path.join(hedef, "kaynak", "sayfa-%02d.txt" % sayfa), "w", encoding="utf-8") as f:
                f.write("%s\n\n%s\n" % (b["baslik"], b["metin"]))
        else:
            girmeyen_sayfalar.append(sayfa)
    acik_mi = kademeler == ("acik",)
    notlar = [n for n in t.get("notlar", []) if n["kademe"] in kademeler]
    ana = next((k for k in t["kaynaklar"] if k.get("rol") == "ana"), None)
    kaynak = {"baslik": ", ".join(n["ad"] for n in notlar) or (ana or {}).get("atif") or t.get("baslik"),
              "tur": "ders notu" if notlar else "makale listesi", "sayfaSayisi": sayfa_sayisi,
              "sayfaMetni": "kaynak/sayfa-{nn}.txt"}
    if girmeyen_sayfalar and sayfa_sayisi:
        kaynak["okumaNotu"] = ("Bu pakette notun bazı sayfaları yok (%s). O sayfalara dayanan bir şeyi okunmuş sayma; "
                               "'bu kısmı bu pakette okuyamıyorum' de." % ", ".join(map(str, girmeyen_sayfalar)))
    if ana and ana.get("doi") and not notlar:
        kaynak["doi"] = ana["doi"]
    hedefler = []
    for h in t.get("hedefler", []):
        x = {"id": h["id"], "baslik": h.get("baslik"), "bloom": h.get("bloom")}
        if h.get("sayfalar"):
            x["sayfalar"] = h["sayfalar"]
            x["kaynak"] = "Not bölüm " + ", ".join(map(str, h["sayfalar"]))
        if h.get("ogretmenKontrolu"):
            x["ogretmenKontrolu"] = h["ogretmenKontrolu"]
        hedefler.append(x)
    sorular = []
    for s in t.get("sorular", []):
        if s.get("kademe", "fakulte") not in kademeler:
            continue
        sorular.append({k: v for k, v in s.items() if k not in ("kademe", "kim")})
    eg = {
        "surum": 1, "baslik": t.get("baslik"), "duzey": t.get("duzey"),
        "dagitim": "acik" if acik_mi else "fakulte",
        "egitmen": t.get("egitmen"), "izinliEgitmenler": [t.get("egitmen")],
        "sure_dk": t.get("sure_dk"), "kaynak": kaynak, "hedefler": hedefler,
        "ogretmenNotlari": [{"id": d["id"], "kural": d.get("metin")} for d in t.get("dikkat", []) if d.get("metin")],
        "yanilgilar": [{"id": y["id"], "hedef": y.get("hedef"), "metin": y.get("metin")} for y in t.get("yanilgilar", [])],
        "soruBankasi": sorular,
        "hazirlayan": "KlinikKoç ders hazırlama sihirbazı", "hazirlama": time.strftime("%Y-%m-%d"),
    }
    if t.get("aciklama_ogrenci"):
        eg["aciklama"] = t["aciklama_ogrenci"]
    if t.get("geri_bildirim_eposta"):
        eg["geriBildirim"] = {"eposta": t["geri_bildirim_eposta"]}
    _json_yaz(os.path.join(hedef, "egitmen.json"), eg)
    kaynaklar = []
    for k in t["kaynaklar"]:
        x = {a: k[a] for a in ("id", "doi", "kisa", "baslik", "atif", "rol", "lisans") if k.get(a)}
        kaynaklar.append(x)
    _json_yaz(os.path.join(hedef, "kaynaklar", "kaynaklar.json"), {"kaynaklar": kaynaklar})
    if t.get("terimler"):
        _json_yaz(os.path.join(hedef, "terimler.json"), {"terimler": [x["terim"] for x in t["terimler"]]})
    for v in t.get("vakalar", []):
        if v["kademe"] not in kademeler:
            continue
        kaynak_klasor = os.path.join(dosya_klasoru(ders), "vakalar", v["id"])
        kart = _json_oku(os.path.join(kaynak_klasor, "kart.json"), {}) or {}
        vid = v["id"] if acik_mi else ("ozel-" + v["id"] if not v["id"].startswith("ozel-") else v["id"])
        kart["id"] = vid
        kart["ders"] = ders_adi
        kart["dagitim"] = "acik" if acik_mi else "fakulte"
        gor = os.path.join(kaynak_klasor, "gorseller")
        if os.path.isdir(gor):
            shutil.copytree(gor, os.path.join(hedef, "vakalar", vid), dirs_exist_ok=True)
            _gorsel_yollarini_duzelt(kart, vid)
        _json_yaz(os.path.join(hedef, "vakalar", vid + ".json"), kart)
    return eg


def _gorsel_yollarini_duzelt(x, vid):
    """Vaka kartındaki 'gorsel' yollarını paketteki yere (vakalar/<vid>/<dosya>) çevirir."""
    if isinstance(x, dict):
        for k, v in list(x.items()):
            if k == "gorsel" and isinstance(v, str) and v:
                x[k] = "vakalar/%s/%s" % (vid, v.replace("\\", "/").split("/")[-1])
            else:
                _gorsel_yollarini_duzelt(v, vid)
    elif isinstance(x, list):
        for v in x:
            _gorsel_yollarini_duzelt(v, vid)


def _zip_yaz(klasor, ust_ad, zip_yolu):
    with zipfile.ZipFile(zip_yolu, "w", zipfile.ZIP_DEFLATED) as z:
        for yol in sorted(glob.glob(os.path.join(klasor, "**", "*"), recursive=True)):
            if os.path.isfile(yol):
                z.write(yol, "%s/%s" % (ust_ad, os.path.relpath(yol, klasor).replace(os.sep, "/")))


def paketle(ders, cikis=None, kur=True):
    """Dersi bu bilgisayara kurar (lessons/ozel-<ders>, bütün kademeler) ve açık + fakülte zip'lerini üretir."""
    d = denetle(ders)
    if d["hatalar"]:
        raise ValueError("Paketlenemedi:\n- " + "\n- ".join(d["hatalar"]))
    t = taslak_oku(ders)
    cikis = cikis or os.path.join(veri_yeri.belgeler(), "KlinikKoç Ders Paketleri")
    os.makedirs(cikis, exist_ok=True)
    gecici = tempfile.mkdtemp()
    sonuc = {"uyarilar": d["uyarilar"], "paketler": {}}
    try:
        for ad, kademeler, ust in (("acik", ("acik",), ders), ("fakulte", ("acik", "fakulte"), "ozel-" + ders)):
            klasor = os.path.join(gecici, ad)
            _ders_klasoru_yaz(t, klasor, kademeler, ust)
            zip_yolu = os.path.join(cikis, "%s-%s.zip" % (ders, ad))
            _zip_yaz(klasor, ust, zip_yolu)
            sonuc["paketler"][ad] = {"dosya": zip_yolu, "boyut_kb": round(os.path.getsize(zip_yolu) / 1024, 1),
                                     "icerik": _paket_ozeti(klasor)}
        if kur:
            yerel = os.path.join(gecici, "yerel")
            _ders_klasoru_yaz(t, yerel, KADEMELER, "ozel-" + ders)
            yerel_zip = os.path.join(gecici, "yerel.zip")
            _zip_yaz(yerel, "ozel-" + ders, yerel_zip)
            import ders_paketi
            r = ders_paketi.yukle(yerel_zip, uzerine=True)
            sonuc["kuruldu"] = r["ders"]
            import vaka_denetle
            for kart in sorted(glob.glob(os.path.join(ders_paketi.KOK, "lessons", r["ders"], "vakalar", "*.json"))):
                h, _, _ = vaka_denetle.denetle(kart)
                for x in h:
                    sonuc["uyarilar"].append("Vaka %s: %s" % (os.path.basename(kart)[:-5], x))
    finally:
        shutil.rmtree(gecici, ignore_errors=True)
    t["son_paket"] = {"tarih": time.strftime("%Y-%m-%d %H:%M"), "klasor": cikis}
    taslak_yaz(ders, t)
    sonuc["klasor"] = cikis
    return sonuc


def _paket_ozeti(klasor):
    eg = _json_oku(os.path.join(klasor, "egitmen.json"), {}) or {}
    return {"not_sayfasi": len(glob.glob(os.path.join(klasor, "kaynak", "sayfa-*.txt"))),
            "vaka": len(glob.glob(os.path.join(klasor, "vakalar", "*.json"))),
            "soru": len(eg.get("soruBankasi") or []), "hedef": len(eg.get("hedefler") or []),
            "makale": len((_json_oku(os.path.join(klasor, "kaynaklar", "kaynaklar.json"), {}) or {}).get("kaynaklar") or [])}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--liste", action="store_true")
    ap.add_argument("--yeni", metavar="DERS")
    ap.add_argument("--baslik")
    ap.add_argument("--doi", nargs="+", metavar=("DERS", "DOI"))
    ap.add_argument("--not", dest="not_", nargs=2, metavar=("DERS", "DOSYA"))
    ap.add_argument("--kademe", default="fakulte", choices=KADEMELER)
    ap.add_argument("--oner", metavar="DERS")
    ap.add_argument("--denetle", metavar="DERS")
    ap.add_argument("--paketle", metavar="DERS")
    a = ap.parse_args()
    if a.liste:
        print(json.dumps(liste(), ensure_ascii=False, indent=1))
    elif a.yeni:
        yeni(a.yeni, a.baslik or "")
        print("Taslak açıldı:", taslak_yolu(a.yeni))
    elif a.doi:
        r = doi_ekle(a.doi[0], " ".join(a.doi[1:]))
        print("%d eklendi, %d zaten vardı." % (r["eklenen"], r["zaten_vardi"]))
    elif a.not_:
        with open(a.not_[1], "rb") as f:
            n = not_ekle(a.not_[0], f.read(), os.path.basename(a.not_[1]), a.kademe)
        print("Not eklendi: %d bölüm, %d sözcük." % (n["bolum_sayisi"], n["sozcuk"]))
    elif a.oner:
        o = kural_onerileri(a.oner)
        print("%d hedef, %d terim, %d soru önerisi." % (len(o.get("hedefler", [])), len(o.get("terimler", [])),
                                                       len(o.get("sorular", []))))
    elif a.denetle:
        print(json.dumps(denetle(a.denetle), ensure_ascii=False, indent=1))
    elif a.paketle:
        print(json.dumps(paketle(a.paketle), ensure_ascii=False, indent=1))
    else:
        ap.print_help()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
