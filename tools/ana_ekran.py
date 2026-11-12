"""KlinikKoç ana ekranı (ana.html) için veri: ders ve PDF listesi, çalışma seçimi, programa öneriler.

- ozet()            Derslerim paneli: kurulu dersler (ilerleme, makale durumu), kendi PDF'leri, seçim, sürüm bilgisi.
- secim_yaz/oku     Öğrencinin "Seçilenlerle çalış" dediği dersler ve PDF'ler; Claude calisma_secimi aracıyla okur.
- oneri_ekle/...    Ders sonunda Claude'un PROGRAMIN KENDİSİ için yazdığı geliştirme önerileri. Yalnız bu bilgisayarda
                    durur (isim içermez); kullanıcı isterse metni kopyalar ya da kendisi gönderir.

Yalnız Python'un kendi kitaplığını kullanır.
"""
import json
import os
import re
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ders_sonu  # noqa: E402
import makale_bulucu as mb  # noqa: E402
import surum as surum_  # noqa: E402
import veri_yeri  # noqa: E402

ONERI_TURLERI = {
    "eksik_cizim": "Eksik çizim / animasyon",
    "kaynakta_yok": "Kaynakta bulunamayan konu",
    "arac_hatasi": "Araç hatası",
    "kullanim": "Kullanımı zorlaştıran şey",
    "yeni_ozellik": "Yeni özellik fikri",
    "diger": "Diğer",
}
EN_COK_ONERI = 400
EN_COK_SECIM = 12


def _json_oku(yol, varsayilan=None):
    try:
        with open(yol, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return varsayilan


def _json_yaz(yol, veri):
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    gecici = yol + ".yeni"
    with open(gecici, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=1)
    os.replace(gecici, yol)


def _kisalt(s, n):
    return re.sub(r"\s+", " ", str(s or "")).strip()[:n]


# ---------- Derslerim ----------
def _ilerleme(ders, eg):
    """Bu bilgisayardaki en ileri kayda göre: (yüzde, tamamlandı mı, oturum sayısı)."""
    hedefler = [h.get("id") for h in (eg.get("hedefler") or []) if h.get("id")]
    en_iyi, tamam, oturum = 0, False, 0
    for _, yol in ders_sonu.ders_kayitlari(ders):
        k = _json_oku(yol, {}) or {}
        tamam = tamam or bool(k.get("tamamlandi"))
        oturum = max(oturum, len(k.get("oturumlar") or []))
        hk = k.get("hedefler") or {}
        if hedefler:
            ele = sum(1 for h in hedefler if (hk.get(h) or {}).get("durum") not in (None, "", "ele_alinmadi"))
            en_iyi = max(en_iyi, int(round(100.0 * ele / len(hedefler))))
    if tamam:
        en_iyi = 100
    return en_iyi, tamam, oturum


def _tekrar_karti_sayisi():
    n = 0
    kok = veri_yeri.kayit_kok()
    try:
        kimlikler = [k for k in os.listdir(kok) if os.path.isdir(os.path.join(kok, k)) and not k.startswith(".")]
    except OSError:
        return 0
    for kimlik in kimlikler:
        try:
            n += len(ders_sonu.zamani_gelen_kartlar(kimlik))
        except Exception:
            pass
    return n


def dersler():
    out = []
    for ders in ders_sonu.kurulu_dersler():
        try:
            mb.ders_gecerli(ders)
        except ValueError:
            continue
        if ders == mb.KENDI:
            continue
        klasor = os.path.join(ders_sonu.lessons_kok(), ders)
        eg = _json_oku(os.path.join(klasor, "egitmen.json"), {}) or {}
        dj = _json_oku(os.path.join(klasor, "ders.json"), {}) or {}
        try:
            oz = mb.ozet(ders)
            makale = {"toplam": len(oz["makaleler"]), "hazir": oz["sayilar"].get("hazir", 0),
                      "calisiyor": oz["calisiyor"]}
        except Exception:
            makale = {"toplam": 0, "hazir": 0, "calisiyor": False}
        yuzde, tamam, oturum = _ilerleme(ders, eg)
        vaka = len([f for f in os.listdir(os.path.join(klasor, "vakalar"))
                    if f.endswith(".json")]) if os.path.isdir(os.path.join(klasor, "vakalar")) else 0
        out.append({
            "ders": ders, "baslik": eg.get("baslik") or dj.get("title") or ders,
            "egitmen": {"inci": "İnci", "mercan": "Mercan"}.get(str(eg.get("egitmen") or "").lower(), None),
            "duzey": eg.get("duzey") or dj.get("level"), "sure_dk": eg.get("sure_dk") or dj.get("estimatedMinutes"),
            "hedef": len(eg.get("hedefler") or []) or sum(len(g.get("subgoals") or []) for g in dj.get("goals") or []),
            "vaka": vaka, "makale": makale, "ilerleme": yuzde, "tamamlandi": tamam, "oturum": oturum,
            "ozel": ders.startswith("ozel-"), "kayitli_anlatim": bool(dj.get("sections")) and not dj.get("_canli"),
            "aciklama": eg.get("aciklama"),
        })
    return out


def pdfler():
    """Öğrencinin hiçbir derse bağlı olmayan kendi PDF'leri (Kendi makalelerim)."""
    try:
        mb.kendi_kitaplik_hazirla()
        oz = mb.ozet(mb.KENDI)
    except Exception:
        return []
    return [{"id": m["id"], "baslik": m.get("kisa") or m["id"], "atif": m.get("atif"), "sayfa": m.get("sayfa"),
             "durum": m.get("durum"), "neden": m.get("neden")} for m in oz["makaleler"]]


def secim_yolu():
    return os.path.join(veri_yeri.veri_kok(), "calisma-secimi.json")


def secim_oku():
    s = _json_oku(secim_yolu(), {}) or {}
    kurulu = {d["ders"]: d["baslik"] for d in dersler()}
    var_pdf = {p["id"]: p["baslik"] for p in pdfler()}
    return {"dersler": [d for d in s.get("dersler") or [] if d in kurulu],
            "pdfler": [p for p in s.get("pdfler") or [] if p in var_pdf],
            "tarih": s.get("tarih"), "_adlar": dict(kurulu, **var_pdf)}


def secim_yaz(dersler_, pdfler_):
    kurulu = {d["ders"] for d in dersler()}
    var_pdf = {p["id"] for p in pdfler()}
    s = {"dersler": [d for d in list(dersler_ or [])[:EN_COK_SECIM] if d in kurulu],
         "pdfler": [p for p in list(pdfler_ or [])[:EN_COK_SECIM] if p in var_pdf],
         "tarih": time.strftime("%Y-%m-%d %H:%M")}
    _json_yaz(secim_yolu(), s)
    return secim_metni(s)


def secim_metni(s=None):
    """Seçim + Claude'a söylenecek hazır cümle."""
    s = s or secim_oku()
    adlar = s.get("_adlar") or secim_oku()["_adlar"]
    d_ad = [adlar.get(d, d) for d in s.get("dersler") or []]
    p_ad = [adlar.get(p, p) for p in s.get("pdfler") or []]
    if d_ad and p_ad:
        cumle = "%s dersini çalışalım; şu makalelerimden de yararlan: %s." % (", ".join(d_ad), ", ".join(p_ad))
    elif d_ad:
        cumle = ("%s dersini çalışalım." % d_ad[0]) if len(d_ad) == 1 else \
            ("Şu dersleri birlikte çalışalım: %s." % ", ".join(d_ad))
    elif p_ad:
        cumle = "Kendi makalelerimden çalışalım: %s." % ", ".join(p_ad)
    else:
        cumle = ""
    return {"dersler": s.get("dersler") or [], "pdfler": s.get("pdfler") or [], "tarih": s.get("tarih"),
            "ders_adlari": d_ad, "pdf_adlari": p_ad, "claude_cumlesi": cumle}


def ozet(guncelleme=True):
    out = {"surum": surum_.surum(), "tur": surum_.tur(), "dersler": dersler(), "pdfler": pdfler(),
           "secim": secim_metni(), "tekrar_karti": _tekrar_karti_sayisi(), "oneri_sayisi": len(oneriler())}
    if guncelleme:
        try:
            out["guncelleme"] = surum_.denetle()
        except Exception as e:  # güncelleme denetimi ana ekranı hiç engellemez
            out["guncelleme"] = {"surum": out["surum"], "var": False, "hata": str(e)}
    return out


# ---------- Programa öneriler (Claude'un ders sonu geri bildirimi) ----------
def oneri_yolu():
    return os.path.join(veri_yeri.veri_kok(), "program-onerileri.json")


def oneri_klasoru():
    return os.path.join(veri_yeri.belgeler(), "KlinikKoç Geri Bildirim")


def oneriler():
    v = _json_oku(oneri_yolu(), []) or []
    return v if isinstance(v, list) else []


def oneri_ekle(ders, yeni, kim="claude"):
    """yeni: [{tur, metin, yer?}] — isim ve kişisel bilgi yazılmaz. Aynı öneri ikinci kez eklenmez."""
    var = oneriler()
    gorulen = {(x.get("tur"), x.get("metin")) for x in var}
    baslik = None
    if ders:
        try:
            baslik = mb.ders_basligi(ders)
        except Exception:
            baslik = None
    eklenen = 0
    for ham in yeni or []:
        if not isinstance(ham, dict):
            continue
        metin = _kisalt(ham.get("metin") or ham.get("ayrinti"), 500)
        tur = ham.get("tur") if ham.get("tur") in ONERI_TURLERI else "diger"
        if not metin or (tur, metin) in gorulen:
            continue
        x = {"id": "O%d" % int(time.time() * 1000 + eklenen), "tur": tur, "metin": metin,
             "tarih": time.strftime("%Y-%m-%d"), "surum": surum_.surum(), "kim": kim}
        if ham.get("yer"):
            x["yer"] = _kisalt(ham["yer"], 120)
        if baslik and not str(ders).startswith("ozel-"):
            x["ders"] = baslik  # özel (fakülte) derslerin adı öneriye yazılmaz
        var.append(x)
        gorulen.add((tur, metin))
        eklenen += 1
    var = var[-EN_COK_ONERI:]
    _json_yaz(oneri_yolu(), var)
    try:
        md_yaz(var)
    except OSError:
        pass
    return {"eklenen": eklenen, "toplam": len(var)}


def oneri_sil(kimlik):
    var = [x for x in oneriler() if x.get("id") != kimlik]
    _json_yaz(oneri_yolu(), var)
    try:
        md_yaz(var)
    except OSError:
        pass
    return {"toplam": len(var)}


def oneri_isaretle(kimlikler):
    """Gönderildi diye işaretler (yeniden gönderilmesin)."""
    var = oneriler()
    for x in var:
        if x.get("id") in set(kimlikler or []):
            x["gonderildi"] = time.strftime("%Y-%m-%d")
    _json_yaz(oneri_yolu(), var)
    return {"toplam": len(var)}


def oneri_metni(var=None, yalniz_yeni=False):
    var = oneriler() if var is None else var
    if yalniz_yeni:
        var = [x for x in var if not x.get("gonderildi")]
    y = ["KlinikKoç geliştirme önerileri (sürüm %s, %s sürümü)" % (surum_.surum(),
                                                                 "öğretmen" if surum_.ogretmen_mi() else "öğrenci"), ""]
    for tur, ad in ONERI_TURLERI.items():
        grup = [x for x in var if x.get("tur") == tur]
        if not grup:
            continue
        y.append("## " + ad)
        for x in grup:
            ek = " (%s)" % " · ".join(v for v in (x.get("ders"), x.get("yer"), x.get("tarih")) if v)
            y.append("- %s%s" % (x["metin"], ek if ek != " ()" else ""))
        y.append("")
    if len(y) == 2:
        y.append("Henüz öneri yok.")
    return "\n".join(y).strip() + "\n"


def md_yaz(var=None):
    os.makedirs(oneri_klasoru(), exist_ok=True)
    yol = os.path.join(oneri_klasoru(), "program-onerileri.md")
    with open(yol, "w", encoding="utf-8") as f:
        f.write(oneri_metni(var))
    return yol


def gonderme_adresi():
    """Kullanıcının kendi tarayıcısında açılan, içi dolu 'yeni öneri' sayfası. Göndermek kullanıcının elindedir."""
    metin = oneri_metni(yalniz_yeni=True)
    q = urllib.parse.urlencode({"title": "Geliştirme önerileri (sürüm %s)" % surum_.surum(), "body": metin[:6000]})
    return "https://github.com/%s/issues/new?%s" % (surum_.DEPO, q)


def geri_bildirim():
    """Geri bildirim paneli: programa öneriler + (öğretmende) gelen değerlendirme formlarının özeti."""
    out = {"oneriler": list(reversed(oneriler())), "turler": ONERI_TURLERI, "klasor": oneri_klasoru(),
           "metin": oneri_metni(), "gonderme_adresi": gonderme_adresi()}
    try:
        import degerlendirme
        k = degerlendirme.klasor()
        formlar = degerlendirme.formlari_oku([k]) if os.path.isdir(k) else []
        out["form_sayisi"] = len(formlar)
        out["form_klasoru"] = k
        out["form_ozeti"] = degerlendirme.ozetle(formlar) if formlar else ""
    except Exception as e:
        out["form_sayisi"] = 0
        out["form_hata"] = str(e)
    return out
