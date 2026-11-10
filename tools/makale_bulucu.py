#!/usr/bin/env python3
"""KlinikKoç makale bulucu: ders paketindeki makale listesinden PDF'leri bulur, metne çevirir ve aramaya ekler.

Ders paketinde makalelerin kendisi değil, yalnız listesi vardır (lessons/<ders>/kaynaklar/kaynaklar.json:
künye ve DOI). Öğrencinin bilgisayarında her makale için sırayla şunlar denenir:

  1. Pakette gelen dosya (yalnız açık lisanslı makaleler pakete konabilir).
  2. Makale klasörü: Belgeler/KlinikKoç Makaleler. Daha önce indirilmiş ya da arşivlenen dersten kalmış
     PDF'ler buradadır; varsa yeniden indirilmez.
  3. Açık erişimli sürüm: OpenAlex, Europe PMC (PubMed Central) ve ayarlanmışsa Unpaywall.
  4. Yayıncının sitesi (doi.org üzerinden). Bilgisayar o anda üniversite ağındaysa (eduroam ya da VPN)
     abonelikli dergiler de çoğu zaman böyle iner. Program hiçbir kullanıcı adı ya da şifre kullanmaz.
  5. Hiçbiri olmazsa makale "eksik" görünür; öğrenci yayıncı sayfasını açıp PDF'i kendisi indirir ve
     makaleler sayfasına sürükleyip bırakır (elle_ekle).

İnen PDF'ler makale klasörüne yazılır, sayfa sayfa metne çevrilir (lessons/<ders>/makale-metin/<kaynak>/)
ve bilgi bankasına eklenir. Bu metinler hiçbir zaman depoya ya da ders paketine girmez.

Kullanım:
  python tools/makale_bulucu.py --hazirla <ders>            makaleleri bul, indir, metne çevir, dizinle
  python tools/makale_bulucu.py --hazirla <ders> --agsiz    yalnız bilgisayardakilere bak (internet yok)
  python tools/makale_bulucu.py --durum <ders>              hangi makale hazır, hangisi eksik
  python tools/makale_bulucu.py --ekle <ders> <dosya.pdf> [--kaynak <id>]   elindeki PDF'i ekle
  python tools/makale_bulucu.py --kur                       PDF okuyucuyu (pypdf) kurar

Ayar (isteğe bağlı): KLINIK_KOC_EPOSTA ortam değişkeni verilirse Unpaywall da sorulur.
"""
import argparse
import glob
import http.cookiejar
import importlib.util
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import veri_yeri  # noqa: E402

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EN_BUYUK_PDF = 80 * 1024 * 1024
ZAMAN = 30
KIBAR_BEKLEME = 1.0  # aynı siteye arka arkaya istek atmamak için (saniye)
TARAYICI = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0 Safari/537.36 KlinikKoc/3")
VARSAYILAN_BITIS = r"^\s*(REFERENCES|References|KAYNAKLAR|Kaynaklar|Bibliography)\s*$"
DOI_KALIBI = re.compile(r"\b(10\.\d{4,9}/[^\s\"<>]+)", re.I)

_KILIT = threading.Lock()


# ---------- Küçük yardımcılar ----------
def _json_oku(yol, varsayilan=None):
    try:
        with open(yol, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return varsayilan


def _json_yaz(yol, veri):
    """Atomik yazma: yarıda kesilen yazma eski dosyayı bozmasın."""
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    fd, gecici = tempfile.mkstemp(dir=os.path.dirname(yol), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=1)
    os.replace(gecici, yol)


def _metin_yaz(yol, metin):
    with open(yol, "w", encoding="utf-8") as f:
        f.write(metin)


def doi_temizle(s):
    """'https://doi.org/10.1111/PRD.70052' → '10.1111/prd.70052' (DOI'ler büyük-küçük harf duyarsızdır)."""
    if not s:
        return ""
    s = str(s).strip()
    s = re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", s, flags=re.I)
    s = re.sub(r"^doi:\s*", "", s, flags=re.I)
    return s.rstrip(".,;)]}").lower()


def guvenli_ad(s, uzunluk=90):
    """Windows ve Mac'te geçerli bir dosya/klasör adı."""
    s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(s or "")).strip(" .")
    return (s[:uzunluk].rstrip(" .") or "adsiz")


def ders_gecerli(ders):
    if not ders or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,80}", ders):
        raise ValueError("Geçersiz ders kimliği: %r" % ders)
    return ders


def kimlik_gecerli(kid):
    if not kid or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}", kid) or ".." in kid:
        raise ValueError("Geçersiz kaynak kimliği: %r" % kid)
    return kid


def ders_klasoru(ders):
    return os.path.join(KOK, "lessons", ders_gecerli(ders))


# ---------- Kendi makalelerim: hiçbir derse bağlı olmayan kişisel kitaplık ----------
# Öğrenci ders yüklemeden de kendi PDF'lerini ekleyip eğitmenle çalışabilsin diye derse benzer bir klasördür
# (lessons/kendi-makalelerim/). Ders listesinde (katalog) görünmez; makaleler sayfasında ve eğitmende görünür.
KENDI = "kendi-makalelerim"
KENDI_BASLIK = "Kendi makalelerim"
KENDI_EGITMEN = {
    "surum": 1, "baslik": KENDI_BASLIK, "duzey": "Serbest çalışma", "egitmen": "mercan",
    "izinliEgitmenler": ["mercan", "inci"], "kendi_kitaplik": True,
    "kaynak": {"baslik": "Öğrencinin eklediği makaleler"},
    "hedefler": [
        {"id": "K1", "baslik": "Seçtiği makalenin sorusunu, yöntemini ve ana bulgusunu kendi cümleleriyle anlatır",
         "bloom": "anla"},
        {"id": "K2", "baslik": "Makalenin kanıt düzeyini ve sınırlılıklarını değerlendirir", "bloom": "degerlendir"}],
    "ogretmenNotlari": [
        {"id": "K-N1", "metin": "Bu bir ders değil: öğrencinin kendi eklediği makalelerle serbest çalışmadır; öğretmen "
                                "onaylı içerik yoktur."},
        {"id": "K-N2", "metin": "Yalnız bu makalelerde bulunan bilgiyle konuş (bilgi_ara, ders='kendi-makalelerim'); "
                                "makalede olmayanı makaleye dayanıyormuş gibi söyleme. Hangi makaleyle çalışmak "
                                "istediğini öğrenciye sor."}],
}


def kendi_kitaplik_hazirla():
    """lessons/kendi-makalelerim/ klasörünü (yoksa) kurar. Klasör yolunu döndürür."""
    k = os.path.join(KOK, "lessons", KENDI)
    if not os.path.isfile(os.path.join(k, "egitmen.json")):
        _json_yaz(os.path.join(k, "egitmen.json"), KENDI_EGITMEN)
    if not os.path.isfile(os.path.join(k, "kaynaklar", "kaynaklar.json")):
        _json_yaz(os.path.join(k, "kaynaklar", "kaynaklar.json"), {"kaynaklar": []})
    return k


def kaynaklar_yolu(ders):
    return os.path.join(ders_klasoru(ders), "kaynaklar", "kaynaklar.json")


def kaynaklar(ders):
    """Dersin makale listesi. Her kayıtta en az id; çoğunda doi, kisa, atif."""
    cfg = _json_oku(kaynaklar_yolu(ders), {}) or {}
    out = []
    for k in cfg.get("kaynaklar") or []:
        if isinstance(k, dict) and k.get("id"):
            out.append(k)
    return out


def ders_basligi(ders):
    if ders == KENDI:
        return KENDI_BASLIK
    for ad in ("ders.json", "egitmen.json"):
        d = _json_oku(os.path.join(ders_klasoru(ders), ad), {}) or {}
        b = d.get("title") or d.get("baslik")
        if b:
            return b
    return ders


def ders_metni_doi(ders):
    """Dersin kendi kaynak/sayfa-NN.txt metni hangi makaleden geliyorsa onun DOI'si (o makale zaten dizinde)."""
    eg = _json_oku(os.path.join(ders_klasoru(ders), "egitmen.json"), {}) or {}
    return doi_temizle((eg.get("kaynak") or {}).get("doi"))


def makale_klasoru(ders):
    """Bu dersin PDF'lerinin durduğu, öğrencinin gördüğü klasör: Belgeler/KlinikKoç Makaleler/<ders başlığı>."""
    return os.path.join(veri_yeri.makale_kok(), guvenli_ad(ders_basligi(ders), 80))


def dosya_adi(k):
    doi = doi_temizle(k.get("doi"))
    taban = doi.replace("/", "_") if doi else k["id"]
    return guvenli_ad(taban, 120) + ".pdf"


def metin_klasoru(ders, kid):
    return os.path.join(ders_klasoru(ders), "makale-metin", kimlik_gecerli(kid))


def durum_yolu(ders):
    return os.path.join(veri_yeri.veri_kok(), "makaleler", ders_gecerli(ders) + ".json")


def durum_oku(ders):
    d = _json_oku(durum_yolu(ders), None)
    if not isinstance(d, dict):
        d = {}
    d.setdefault("ders", ders)
    d.setdefault("kaynaklar", {})
    d.setdefault("ekler", [])
    return d


def durum_yaz(ders, d):
    d["guncelleme"] = time.strftime("%Y-%m-%d %H:%M")
    with _KILIT:
        _json_yaz(durum_yolu(ders), d)


def pdf_mi(veri):
    return bool(veri) and b"%PDF-" in veri[:1024]


# ---------- İnternet ----------
class Ag:
    """Çerezleri tutan basit bir indirici (yayıncı siteleri yönlendirme sırasında çerez ister)."""

    def __init__(self, zaman=ZAMAN):
        self.zaman = zaman
        self.cerez = http.cookiejar.CookieJar()
        self.acici = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cerez))
        self._son = {}
        self.ulasildi = False  # en az bir site yanıt verdi mi (internet var mı)

    def _bekle(self, url):
        host = urllib.parse.urlsplit(url).hostname or ""
        gecen = time.time() - self._son.get(host, 0)
        if gecen < KIBAR_BEKLEME:
            time.sleep(KIBAR_BEKLEME - gecen)
        self._son[host] = time.time()

    def al(self, url, kabul="*/*", en_cok=EN_BUYUK_PDF):
        """(gövde, son adres, içerik türü) döndürür. Hata olursa urllib hatası yükselir."""
        self._bekle(url)
        istek = urllib.request.Request(url, headers={"User-Agent": TARAYICI, "Accept": kabul,
                                                     "Accept-Language": "tr,en;q=0.8"})
        try:
            with self.acici.open(istek, timeout=self.zaman) as y:
                self.ulasildi = True
                tur = (y.headers.get("Content-Type") or "").lower()
                govde = y.read(en_cok + 1)
                if len(govde) > en_cok:
                    raise ValueError("dosya çok büyük")
                return govde, y.geturl(), tur
        except urllib.error.HTTPError:
            self.ulasildi = True   # site yanıt verdi (ör. 403, 404): internet var
            raise

    def json(self, url):
        govde, _, _ = self.al(url, "application/json", 5 * 1024 * 1024)
        return json.loads(govde.decode("utf-8"))


def acik_erisim_adresleri(doi, ag, eposta=None):
    """Açık erişimli PDF adresleri: [(adres, nereden)]. Hata veren kaynak sessizce atlanır."""
    adresler = []
    q = urllib.parse.quote(doi, safe="/")
    try:
        w = ag.json("https://api.openalex.org/works/doi:" + q)
        konumlar = [w.get("best_oa_location") or {}] + list(w.get("oa_locations") or [])
        for k in konumlar:
            if k and k.get("pdf_url"):
                adresler.append((k["pdf_url"], "OpenAlex"))
    except Exception:
        pass
    try:
        e = ag.json("https://www.ebi.ac.uk/europepmc/webservices/rest/search?format=json&resultType=lite&query=DOI:%22"
                    + urllib.parse.quote(doi, safe="") + "%22")
        for r in (e.get("resultList") or {}).get("result") or []:
            pmc = r.get("pmcid")
            if pmc and r.get("isOpenAccess") == "Y":
                adresler.append(("https://europepmc.org/backend/ptpmcrender.fcgi?accid=%s&blobtype=pdf" % pmc,
                                 "Europe PMC"))
    except Exception:
        pass
    eposta = eposta or os.environ.get("KLINIK_KOC_EPOSTA")
    if eposta:
        try:
            u = ag.json("https://api.unpaywall.org/v2/%s?email=%s" % (q, urllib.parse.quote(eposta)))
            for k in [u.get("best_oa_location") or {}] + list(u.get("oa_locations") or []):
                if k and k.get("url_for_pdf"):
                    adresler.append((k["url_for_pdf"], "Unpaywall"))
        except Exception:
            pass
    tekil, gorulen = [], set()
    for a, n in adresler:
        if a not in gorulen:
            gorulen.add(a)
            tekil.append((a, n))
    return tekil


def pdf_adresi_bul(html, taban):
    """Yayıncı sayfasındaki <meta name="citation_pdf_url" content="..."> (Google Akademik etiketi)."""
    for m in re.finditer(r"<meta\b[^>]*>", html, flags=re.I):
        etiket = m.group(0)
        if re.search(r"name\s*=\s*[\"']citation_pdf_url[\"']", etiket, flags=re.I):
            c = re.search(r"content\s*=\s*[\"']([^\"']+)[\"']", etiket, flags=re.I)
            if c:
                return urllib.parse.urljoin(taban, c.group(1).replace("&amp;", "&"))
    return None


def yayinci_dene(doi, ag):
    """doi.org üzerinden yayıncıya gider. (pdf baytları ya da None, yayıncı sayfasının adresi)."""
    sayfa = "https://doi.org/" + urllib.parse.quote(doi, safe="/")
    try:
        govde, son, tur = ag.al(sayfa, "text/html,application/pdf;q=0.9,*/*;q=0.8")
    except Exception:
        return None, sayfa
    if pdf_mi(govde):
        return govde, son
    pdf_url = pdf_adresi_bul(govde[:2_000_000].decode("utf-8", "ignore"), son)
    if pdf_url:
        try:
            veri, _, _ = ag.al(pdf_url, "application/pdf,*/*;q=0.8")
            if pdf_mi(veri):
                return veri, son
        except Exception:
            pass
    return None, son


# ---------- PDF → sayfa metinleri ----------
def _dizin_uret():
    yol = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dizin-uret.py")
    spec = importlib.util.spec_from_file_location("dizin_uret", yol)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def pypdf_var():
    return importlib.util.find_spec("pypdf") is not None


def metne_cevir(ders, kid, pdf_yolu, k=None, ogrenci=False):
    """PDF'i lessons/<ders>/makale-metin/<kid>/sayfa-NN.txt sayfalarına çevirir. Yazılan sayfa sayısını döndürür."""
    k = k or {}
    if not pypdf_var():
        raise RuntimeError("PDF okuyucu kurulu değil. Kurmak için: python tools/makale_bulucu.py --kur")
    from pypdf import PdfReader
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    du = _dizin_uret()
    hedef = metin_klasoru(ders, kid)
    if os.path.isdir(hedef):
        shutil.rmtree(hedef)
    os.makedirs(hedef)
    r = PdfReader(pdf_yolu)
    bitis = k.get("bitis") or VARSAYILAN_BITIS
    yazilan, toplam = 0, 0
    for s in du.sayfa_araligi(k.get("sayfalar"), len(r.pages)):
        t = r.pages[s - 1].extract_text() or ""
        m = re.search(bitis, t, flags=re.M) if bitis else None
        t = du.temizle(t[:m.start()] if m else t, k.get("sil") or ())
        if t.strip():
            _metin_yaz(os.path.join(hedef, "sayfa-%02d.txt" % s), t + "\n")
            yazilan += 1
            toplam += len(t)
        if m and s > 1:
            break
    _json_yaz(os.path.join(hedef, "bilgi.json"), {
        "id": kid, "kisa": k.get("kisa") or k.get("baslik") or kid, "baslik": k.get("baslik"),
        "doi": doi_temizle(k.get("doi")) or None, "ogrenci": bool(ogrenci), "sayfa": yazilan,
        "pdf": os.path.basename(pdf_yolu)})
    if toplam < 200:
        raise ValueError("PDF'te okunabilir metin yok (taranmış bir PDF olabilir)")
    return yazilan


def ilk_sayfa_metni(pdf_yolu, n=2):
    try:
        from pypdf import PdfReader
        logging.getLogger("pypdf").setLevel(logging.ERROR)
        r = PdfReader(pdf_yolu)
        return "\n".join((r.pages[i].extract_text() or "") for i in range(min(n, len(r.pages))))
    except Exception:
        return ""


# ---------- Bir makaleyi bulmak ----------
def yerelde_bul(ders, k):
    """Pakette gelen dosya ya da makale klasöründe daha önce kalmış PDF: (yol, nereden) ya da (None, None)."""
    if k.get("dosya"):
        yol = os.path.join(ders_klasoru(ders), "kaynaklar", os.path.basename(k["dosya"]))
        if os.path.isfile(yol) and yol.lower().endswith(".pdf"):
            return yol, "paket"
    ad = dosya_adi(k)
    kendi = os.path.join(makale_klasoru(ders), ad)
    if os.path.isfile(kendi):
        return kendi, "klasor"
    # Başka bir dersin klasöründe (ya da kökte) aynı makale varsa onu kullan: öğrenci yeniden indirmesin.
    kok = veri_yeri.makale_kok()
    for yol in [os.path.join(kok, ad)] + glob.glob(os.path.join(kok, "*", ad)):
        if os.path.isfile(yol):
            return yol, "klasor"
    return None, None


def _kaydet(ders, k, veri):
    hedef_klasor = makale_klasoru(ders)
    os.makedirs(hedef_klasor, exist_ok=True)
    yol = os.path.join(hedef_klasor, dosya_adi(k))
    gecici = yol + ".iniyor"
    with open(gecici, "wb") as f:
        f.write(veri)
    os.replace(gecici, yol)
    return yol


def kaynak_hazirla(ders, k, ag=None, ag_kullan=True, eposta=None):
    """Tek bir makaleyi bulur ve metne çevirir. Durum sözlüğü döndürür."""
    doi = doi_temizle(k.get("doi"))
    d = {"id": k["id"], "kisa": k.get("kisa") or k.get("baslik") or k["id"], "doi": doi or None,
         "rol": k.get("rol"), "atif": k.get("atif"), "denendi": time.strftime("%Y-%m-%d %H:%M")}
    if doi:
        d["sayfa_adresi"] = "https://doi.org/" + doi
    if doi and doi == ders_metni_doi(ders) and glob.glob(os.path.join(ders_klasoru(ders), "kaynak", "sayfa-*.txt")):
        d.update(durum="hazir", nereden="ders", not_="Dersin kendi metni; zaten aramada.")
        return d
    yol, nereden = yerelde_bul(ders, k)
    denenen = []
    if not yol and ag_kullan and doi:
        ag = ag or Ag()
        for url, kim in acik_erisim_adresleri(doi, ag, eposta):
            denenen.append(kim)
            try:
                veri, _, _ = ag.al(url, "application/pdf,*/*;q=0.8")
            except Exception:
                continue
            if pdf_mi(veri):
                yol, nereden = _kaydet(ders, k, veri), "acik-erisim"
                break
        if not yol:
            denenen.append("yayıncı")
            veri, sayfa = yayinci_dene(doi, ag)
            if sayfa:
                d["sayfa_adresi"] = sayfa
            if veri:
                yol, nereden = _kaydet(ders, k, veri), "universite"
    if not yol:
        if denenen and not getattr(ag, "ulasildi", True):
            neden = "İnternete ulaşılamadı. Bağlantınızı kontrol edip yeniden deneyin."
        elif denenen:
            neden = ("Açık erişimli bir sürümü bulunamadı ve yayıncı indirmeye izin vermedi. Üniversite ağındaysanız "
                     "yayıncı sayfasından indirip buraya bırakın.")
        else:
            neden = "İnternete bakılmadı." if (not ag_kullan and doi) else "DOI yok; PDF'i elle ekleyin."
        d.update(durum="eksik", denenen=denenen, neden=neden)
        return d
    d.update(pdf=yol, nereden=nereden)
    try:
        d["sayfa"] = metne_cevir(ders, k["id"], yol, k)
        d["durum"] = "hazir"
    except Exception as e:
        d.update(durum="hata", neden=str(e))
    return d


def hazirla(ders, ag_kullan=True, ilerleme=None, eposta=None, dizinle=True):
    """Dersin bütün makalelerini dener. ilerleme(sira, toplam, durum) her makaleden sonra çağrılır."""
    liste = kaynaklar(ders)
    durum = durum_oku(ders)
    durum["calisiyor"] = True
    durum_yaz(ders, durum)
    ag = Ag() if ag_kullan else None
    try:
        for i, k in enumerate(liste, 1):
            try:
                kimlik_gecerli(k["id"])
                sonuc = kaynak_hazirla(ders, k, ag, ag_kullan, eposta)
            except Exception as e:
                sonuc = {"id": k.get("id"), "durum": "hata", "neden": str(e)}
            durum["kaynaklar"][str(k.get("id"))] = sonuc
            durum_yaz(ders, durum)
            if ilerleme:
                ilerleme(i, len(liste), sonuc)
        # Listeden çıkarılmış kaynakların eski durumunu ve metnini temizle (öğrencinin ekledikleri kalır).
        gecerli = {str(k.get("id")) for k in liste} | {e["id"] for e in durum["ekler"]}
        for kid in list(durum["kaynaklar"]):
            if kid not in gecerli:
                del durum["kaynaklar"][kid]
        for yol in glob.glob(os.path.join(ders_klasoru(ders), "makale-metin", "*")):
            if os.path.basename(yol) not in gecerli:
                shutil.rmtree(yol, ignore_errors=True)
    finally:
        durum["calisiyor"] = False
        durum_yaz(ders, durum)
    if dizinle:
        aramaya_ekle(ders)
    return ozet(ders)


def aramaya_ekle(ders):
    """Bilgi bankasını (sözcük araması) günceller. Anlam araması kuruluysa eğitmen ilk aramada onu da ekler."""
    try:
        import bilgi_bankasi
        return bilgi_bankasi.dizinle([ders], sessiz=True, yol=bilgi_bankasi.DIZIN)
    except Exception as e:
        return [{"ders": ders, "durum": "dizinlenemedi", "hata": str(e)}]


# ---------- Öğrencinin elle eklediği PDF ----------
def elle_ekle(ders, veri, ad="makale.pdf", kaynak_id=None, dizinle=True):
    """Öğrencinin elindeki PDF. kaynak_id verilmezse PDF'teki DOI listedeki bir makaleyle eşleştirilir;
    eşleşmezse "öğrencinin eklediği" ayrı bir kaynak olur."""
    if not pdf_mi(veri):
        raise ValueError("Bu dosya PDF değil.")
    if not ders or ders == KENDI:
        ders = KENDI
        kendi_kitaplik_hazirla()
    elif not os.path.isdir(ders_klasoru(ders)):
        raise ValueError("Bu ders bu bilgisayarda kurulu değil: %s" % ders)
    if len(veri) > EN_BUYUK_PDF:
        raise ValueError("PDF çok büyük (en çok 80 MB).")
    liste = {str(k["id"]): k for k in kaynaklar(ders)}
    durum = durum_oku(ders)
    k = liste.get(kaynak_id) if kaynak_id else None
    if kaynak_id and not k:
        k = next((e for e in durum["ekler"] if e["id"] == kaynak_id), None)
        if not k:
            raise ValueError("Bu derste böyle bir makale yok: %s" % kaynak_id)
    gecici = None
    if not k:
        fd, gecici = tempfile.mkstemp(suffix=".pdf")
        with os.fdopen(fd, "wb") as f:
            f.write(veri)
        metin = ilk_sayfa_metni(gecici)
        os.remove(gecici)
        bulunan = {doi_temizle(m) for m in DOI_KALIBI.findall(metin)}
        for aday in liste.values():
            if doi_temizle(aday.get("doi")) and doi_temizle(aday.get("doi")) in bulunan:
                k = aday
                break
    ogrenci = False
    if not k:
        ogrenci = True
        taban = re.sub(r"\.pdf$", "", os.path.basename(ad or "makale.pdf"), flags=re.I)
        kid = "ogrenci-" + re.sub(r"[^a-z0-9]+", "-", taban.lower()).strip("-")[:50]
        kid = kid if kid != "ogrenci-" else "ogrenci-%d" % (len(durum["ekler"]) + 1)
        k = {"id": kid, "kisa": taban[:80], "baslik": taban, "ogrenci": True}
        durum["ekler"] = [e for e in durum["ekler"] if e["id"] != kid] + [k]
    yol = os.path.join(makale_klasoru(ders), guvenli_ad(ad, 120) if ogrenci else dosya_adi(k))
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    with open(yol + ".iniyor", "wb") as f:
        f.write(veri)
    os.replace(yol + ".iniyor", yol)
    sonuc = {"id": k["id"], "kisa": k.get("kisa") or k["id"], "doi": doi_temizle(k.get("doi")) or None,
             "pdf": yol, "nereden": "elle", "ogrenci": ogrenci, "denendi": time.strftime("%Y-%m-%d %H:%M")}
    try:
        sonuc["sayfa"] = metne_cevir(ders, k["id"], yol, k, ogrenci=ogrenci)
        sonuc["durum"] = "hazir"
    except Exception as e:
        sonuc.update(durum="hata", neden=str(e))
    durum["kaynaklar"][k["id"]] = sonuc
    durum_yaz(ders, durum)
    if dizinle and sonuc["durum"] == "hazir":
        aramaya_ekle(ders)
    return sonuc


def eki_kaldir(ders, kid):
    """Öğrencinin eklediği bir makaleyi dersten çıkarır (PDF makale klasöründe kalır)."""
    durum = durum_oku(ders)
    if not any(e["id"] == kid for e in durum["ekler"]):
        raise ValueError("Yalnız sizin eklediğiniz makaleler çıkarılabilir.")
    durum["ekler"] = [e for e in durum["ekler"] if e["id"] != kid]
    durum["kaynaklar"].pop(kid, None)
    shutil.rmtree(metin_klasoru(ders, kid), ignore_errors=True)
    durum_yaz(ders, durum)
    aramaya_ekle(ders)
    return {"kaldirildi": kid}


# ---------- Özet ----------
def ozet(ders):
    """Makaleler sayfası ve eğitmen için: her makalenin durumu ve sayılar."""
    durum = durum_oku(ders)
    satirlar = []
    for k in kaynaklar(ders) + durum["ekler"]:
        s = dict(durum["kaynaklar"].get(str(k["id"])) or {})
        s.setdefault("id", k["id"])
        s.setdefault("kisa", k.get("kisa") or k.get("baslik") or k["id"])
        s.setdefault("atif", k.get("atif"))
        s.setdefault("doi", doi_temizle(k.get("doi")) or None)
        s.setdefault("rol", k.get("rol"))
        s.setdefault("ogrenci", bool(k.get("ogrenci")))
        if s.get("doi"):
            s.setdefault("sayfa_adresi", "https://doi.org/" + s["doi"])
        s.setdefault("durum", "denenmedi")
        if s.get("pdf") and not os.path.isfile(s["pdf"]):
            s["durum"], s["neden"] = "eksik", "PDF dosyası yerinden kaldırılmış."
        satirlar.append(s)
    sayi = {}
    for s in satirlar:
        sayi[s["durum"]] = sayi.get(s["durum"], 0) + 1
    return {"ders": ders, "baslik": ders_basligi(ders), "klasor": makale_klasoru(ders),
            "calisiyor": bool(durum.get("calisiyor")), "guncelleme": durum.get("guncelleme"),
            "pdf_okuyucu": pypdf_var(), "sayilar": sayi, "makaleler": satirlar}


def makaleli_dersler():
    """Makaleler sayfasının listesi: makale listesi olan dersler, en sonda her zaman "Kendi makalelerim"."""
    out = []
    for yol in sorted(glob.glob(os.path.join(KOK, "lessons", "*", "kaynaklar", "kaynaklar.json"))):
        ders = os.path.basename(os.path.dirname(os.path.dirname(yol)))
        try:
            ders_gecerli(ders)
        except ValueError:
            continue
        if ders == KENDI:
            continue
        out.append({"ders": ders, "baslik": ders_basligi(ders), "makale": len(kaynaklar(ders))})
    out.append({"ders": KENDI, "baslik": KENDI_BASLIK, "makale": len(durum_oku(KENDI)["ekler"]), "kendi": True})
    return out


# ---------- Arka planda çalıştırma (sunucu ve eğitmen aracı için) ----------
_ISLER = {}


def arka_planda_hazirla(ders, ag_kullan=True):
    """Hazırlamayı ayrı bir iş parçacığında başlatır; zaten çalışıyorsa yenisini başlatmaz."""
    ders_gecerli(ders)
    is_ = _ISLER.get(ders)
    if is_ and is_.is_alive():
        return {"durum": "zaten çalışıyor"}
    t = threading.Thread(target=hazirla, args=(ders, ag_kullan), daemon=True)
    _ISLER[ders] = t
    t.start()
    return {"durum": "başladı"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hazirla", metavar="DERS")
    ap.add_argument("--durum", metavar="DERS")
    ap.add_argument("--ekle", nargs=2, metavar=("DERS", "PDF"))
    ap.add_argument("--kaynak", help="--ekle ile: PDF hangi makalenin (kaynaklar.json'daki id)")
    ap.add_argument("--agsiz", action="store_true", help="internete bakma")
    ap.add_argument("--kur", action="store_true", help="PDF okuyucuyu (pypdf) kur")
    a = ap.parse_args()
    if a.kur:
        if pypdf_var():
            print("PDF okuyucu (pypdf) zaten kurulu.")
            return 0
        return subprocess.call([sys.executable, "-m", "pip", "install", "--upgrade", "pypdf"])
    if a.hazirla:
        def yaz(i, n, s):
            print("%2d/%d  %-8s %-40s %s" % (i, n, s.get("durum"), (s.get("kisa") or s.get("id") or "")[:40],
                                            s.get("nereden") or s.get("neden") or ""))
        o = hazirla(a.hazirla, ag_kullan=not a.agsiz, ilerleme=yaz)
        print("\nMakale klasörü:", o["klasor"])
        print("Özet:", ", ".join("%s %d" % (k, v) for k, v in sorted(o["sayilar"].items())) or "makale yok")
        return 0
    if a.durum:
        print(json.dumps(ozet(a.durum), ensure_ascii=False, indent=1))
        return 0
    if a.ekle:
        with open(a.ekle[1], "rb") as f:
            veri = f.read()
        print(json.dumps(elle_ekle(a.ekle[0], veri, os.path.basename(a.ekle[1]), a.kaynak), ensure_ascii=False, indent=1))
        return 0
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
