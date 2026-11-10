#!/usr/bin/env python3
"""KlinikKoç ders sonu: tamamlama raporu, tekrar kartları, depolama sınırı, arşiv ve geri yükleme.

Kararlar (Kemal, 10 Kasım 2026):
  - Ders bitince tamamlama raporu HER ZAMAN yazılır; ders yerinde kalır.
  - Arşivleme otomatik DEĞİL. Ders verisi sınırı (varsayılan 2 GB, öğrenci değiştirebilir) aşılınca KlinikKoç
    "Hangi dersleri arşive kaldıralım?" diye sorar; öğrenci seçer. Öğrenci istediği an kendisi de arşivleyebilir.
  - Arşiv zip'i = ders paketi (ses ve video hariç) + tamamlama raporları + ilerleme kayıtları + makale listesi.
    PDF yoktur: PDF'ler zaten Belgeler/KlinikKoç Makaleler/<ders> klasöründe, öğrencinin elindedir ve silinmez.
  - Zip yazılıp denetlendikten SONRA dersin klasörü (makale metinleri, sesler dahil) ve arama dizinindeki
    parçaları silinir. Öğrenci kayıtları silinmez (küçüktür, zip'te de bir kopyası vardır).
  - Geri yükleme: zip'ten ders kurulur, kayıtlar (yerelde daha yenisi yoksa) geri yazılır, PDF'ler önce makale
    klasöründe aranır, olmayanlar yeniden indirilmeye çalışılır, ders yeniden dizinlenir.
  - Tekrar kartları arşivin DIŞINDA kalır: öğrencinin zorlandığı sorular, ders başına en çok 10, yalnız metin.

Komut satırı:
  python tools/ders_sonu.py --depolama
  python tools/ders_sonu.py --sinir 5               (GB)
  python tools/ders_sonu.py --rapor <öğrenci kimliği> <ders>
  python tools/ders_sonu.py --arsivle <ders>
  python tools/ders_sonu.py --geri-yukle <arsiv.zip>
"""
import argparse
import datetime
import glob
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import time
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bilgi_bankasi  # noqa: E402
import ders_paketi  # noqa: E402
import karne as karne_  # noqa: E402
import kayit_deposu as kd  # noqa: E402
import makale_bulucu as mb  # noqa: E402
import veri_yeri  # noqa: E402

VARSAYILAN_SINIR_GB = 2.0
EN_COK_KART = 10
KART_GUN = {1: 3, 2: 7, 3: 21, 4: 60}  # kart kutusu → sonraki tekrara kadar gün
ARSIV_SURUM = 1
ARSIVE_GIRMEYEN = ("makale-metin", "audio", "videolar")  # bu bilgisayarda üretilen ya da büyük olanlar
KART_DOSYASI = os.path.join("tekrar", "kartlar.json")  # alt klasörde: ders kaydı (*.json) sanılmasın


def _json_oku(yol, varsayilan=None):
    try:
        with open(yol, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return varsayilan


def _json_yaz(yol, veri):
    kd.atomik_yaz(yol, veri, yedekle=False)


def bugun():
    return time.strftime("%Y-%m-%d")


def gun_ekle(tarih, gun):
    return (datetime.date.fromisoformat(tarih) + datetime.timedelta(days=gun)).isoformat()


def lessons_kok():
    return os.path.join(ders_paketi.KOK, "lessons")


def ders_klasoru(ders):
    mb.ders_gecerli(ders)
    return os.path.join(lessons_kok(), ders)


def depo():
    return kd.Depo(veri_yeri.kayit_kok())


# ---------- Ayar: depolama sınırı ----------
def ayar_yolu():
    return os.path.join(veri_yeri.veri_kok(), "ayarlar.json")


def ayarlar():
    a = _json_oku(ayar_yolu(), {}) or {}
    return a if isinstance(a, dict) else {}


def sinir_gb():
    try:
        g = float(ayarlar().get("depolama_siniri_gb", VARSAYILAN_SINIR_GB))
        return g if g > 0 else VARSAYILAN_SINIR_GB
    except (TypeError, ValueError):
        return VARSAYILAN_SINIR_GB


def sinir_ayarla(gb):
    try:
        gb = round(float(gb), 2)
    except (TypeError, ValueError):
        raise ValueError("Sınır bir sayı olmalı (GB).")
    if not 0.1 <= gb <= 2000:
        raise ValueError("Sınır 0,1 ile 2000 GB arasında olmalı.")
    a = ayarlar()
    a["depolama_siniri_gb"] = gb
    _json_yaz(ayar_yolu(), a)
    return gb


# ---------- Boyutlar ----------
def klasor_boyutu(yol):
    toplam = 0
    for kok, _, dosyalar in os.walk(yol):
        for ad in dosyalar:
            try:
                toplam += os.path.getsize(os.path.join(kok, ad))
            except OSError:
                pass
    return toplam


def dizin_payi(ders):
    """Arama dizininde bu dersin kapladığı yaklaşık yer (metin + anlam vektörleri; sözcük dizini için x2)."""
    yol = bilgi_bankasi.DIZIN
    if not os.path.exists(yol):
        return 0
    try:
        db = sqlite3.connect(yol)
        try:
            r = db.execute("SELECT COALESCE(SUM(LENGTH(metin)),0), COALESCE(SUM(LENGTH(vektor)),0) FROM parca WHERE ders=?",
                           (ders,)).fetchone()
        finally:
            db.close()
        return int(r[0]) * 2 + int(r[1])
    except sqlite3.Error:
        return 0


def dizinden_sil(ders):
    """Dersin parçalarını arama dizininden siler ve dosyayı küçültür."""
    yol = bilgi_bankasi.DIZIN
    if not os.path.exists(yol):
        return
    db = sqlite3.connect(yol)
    try:
        db.execute("DELETE FROM parca WHERE ders=?", (ders,))
        db.execute("DELETE FROM bilgi WHERE anahtar=?", ("imza:" + ders,))
        try:
            db.execute("INSERT INTO parca_fts(parca_fts) VALUES('rebuild')")
        except sqlite3.OperationalError:
            pass
        db.commit()
        db.execute("VACUUM")
    finally:
        db.close()


def yerlesik_mi(ders):
    """Programla gelen ders mi (program güncellemesi geri getirir; arşivlenmez)."""
    if ders == "tanitim":
        return True
    liste = _json_oku(os.path.join(ders_paketi.KOK, "onbellek-listesi.json"), {}) or {}
    on = "lessons/%s/" % ders
    return any(str(f).lstrip("./").startswith(on) for f in liste.get("files") or [])


def kurulu_dersler():
    if not os.path.isdir(lessons_kok()):
        return []
    out = []
    for ad in sorted(os.listdir(lessons_kok())):
        k = os.path.join(lessons_kok(), ad)
        if ad.startswith(".") or ad.endswith(".eski") or not os.path.isdir(k):
            continue
        if os.path.exists(os.path.join(k, "egitmen.json")) or os.path.exists(os.path.join(k, "ders.json")):
            out.append(ad)
    return out


def ders_kayitlari(ders):
    """[(öğrenci kimliği, kayıt yolu)] — bu dersin bütün öğrenci kayıtları."""
    kok = veri_yeri.kayit_kok()
    out = []
    for yol in sorted(glob.glob(os.path.join(glob.escape(kok), "*", ders + ".json"))):
        kimlik = os.path.basename(os.path.dirname(yol))
        if kimlik != kd.YEDEK_KLASORU and not kimlik.startswith("."):
            out.append((kimlik, yol))
    return out


def son_acilma(ders):
    son = ""
    for _, yol in ders_kayitlari(ders):
        k = _json_oku(yol, {}) or {}
        son = max(son, str(k.get("guncelleme") or "")[:10])
    if not son:
        for yol in (mb.durum_yolu(ders), os.path.join(lessons_kok(), ders)):
            if os.path.exists(yol):
                son = max(son, time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(yol))))
    return son or None


def depolama():
    """Derslerin kapladığı yer ve sınır. Toplam = ders klasörleri + arama dizini + derslerin PDF klasörleri."""
    dersler = []
    for ders in kurulu_dersler():
        try:
            mb.ders_gecerli(ders)
        except ValueError:
            continue
        klasor = os.path.join(lessons_kok(), ders)
        pdf_klasoru = mb.makale_klasoru(ders) if mb.kaynaklar(ders) or mb.durum_oku(ders)["ekler"] else None
        satir = {"ders": ders, "baslik": mb.ders_basligi(ders), "ders_bayt": klasor_boyutu(klasor),
                 "dizin_bayt": dizin_payi(ders),
                 "pdf_bayt": klasor_boyutu(pdf_klasoru) if pdf_klasoru and os.path.isdir(pdf_klasoru) else 0,
                 "son_acilma": son_acilma(ders), "yerlesik": yerlesik_mi(ders),
                 "tamamlandi": any((_json_oku(y, {}) or {}).get("tamamlandi") for _, y in ders_kayitlari(ders))}
        satir["toplam"] = satir["ders_bayt"] + satir["dizin_bayt"] + satir["pdf_bayt"]
        dersler.append(satir)
    toplam = sum(d["toplam"] for d in dersler)
    sinir = int(sinir_gb() * 1024 ** 3)
    # Arşiv önerisi: en uzun süredir açılmayan, programla gelmeyen dersler.
    adaylar = sorted((d for d in dersler if not d["yerlesik"]), key=lambda d: (d["son_acilma"] or "", -d["toplam"]))
    return {"sinir_gb": sinir_gb(), "sinir_bayt": sinir, "toplam_bayt": toplam, "asildi": toplam > sinir,
            "dersler": dersler, "arsiv_adaylari": [d["ders"] for d in adaylar],
            "arsiv": arsiv_listesi(), "arsiv_klasoru": arsiv_kok()}


def okunur_boyut(n):
    for birim, b in (("GB", 1024 ** 3), ("MB", 1024 ** 2), ("KB", 1024)):
        if n >= b:
            return ("%.1f %s" % (n / b, birim)).replace(".", ",")
    return "%d bayt" % n


# ---------- Sorular ve tekrar kartları ----------
def _kisalt(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def soru_bilgisi(klasor, c):
    """Kayıttaki bir cevabın sorusunu (kimlik ya da kısa metin) dersin dosyalarında bulur: metin, seçenekler,
    doğru seçenek, örnek cevap. Bulunamazsa kayıttaki metinle yetinilir."""
    soru = _kisalt(c.get("soru"))
    out = {"soru": soru}
    if c.get("vaka"):
        v = _json_oku(os.path.join(klasor, "vakalar", c["vaka"] + ".json"), {}) or {}
        nd = next((n for n in v.get("dugumler") or [] if n.get("id") == c.get("dugum")), None)
        if nd:
            out["soru"] = _kisalt(nd.get("soru") or nd.get("anlat")) or soru
            out["vaka_ozeti"] = _kisalt((v.get("basvuru") or {}).get("sikayet"))
            if nd.get("secenekler"):
                out["secenekler"] = [_kisalt(s.get("metin")) for s in nd["secenekler"]]
                out["dogru"] = [i for i, s in enumerate(nd["secenekler"]) if s.get("sonuc") == "dogru"]
            if nd.get("ornek_cevap"):
                out["ornek_cevap"] = _kisalt(nd["ornek_cevap"])
            out["kaynak"] = "vaka: %s" % (v.get("baslik") or c["vaka"])
            return out
    eg = _json_oku(os.path.join(klasor, "egitmen.json"), {}) or {}
    for s in eg.get("soruBankasi") or []:
        if soru and (s.get("id") == soru or _kisalt(s.get("metin")).startswith(soru[:60])):
            out["soru"] = _kisalt(s.get("metin")) or soru
            if s.get("secenekler"):
                out["secenekler"] = [_kisalt(x if isinstance(x, str) else x.get("metin")) for x in s["secenekler"]]
                if s.get("dogru") is not None:
                    out["dogru"] = s["dogru"] if isinstance(s["dogru"], list) else [s["dogru"]]
            if s.get("ornek_cevap"):
                out["ornek_cevap"] = _kisalt(s["ornek_cevap"])
            return out
    dj = _json_oku(os.path.join(klasor, "ders.json"), {}) or {}
    for sec in dj.get("sections") or []:
        for st in sec.get("steps") or []:
            q = st.get("question") or {}
            p = _kisalt(q.get("prompt"))
            if soru and p and (q.get("id") == soru or p.startswith(soru[:60]) or soru.startswith(p[:60])):
                out["soru"] = p
                if q.get("options"):
                    out["secenekler"] = [_kisalt(o.get("text")) for o in q["options"]]
                    out["dogru"] = [i for i, o in enumerate(q["options"]) if o.get("correct")]
                if q.get("modelAnswer"):
                    out["ornek_cevap"] = _kisalt(q["modelAnswer"])
                return out
    return out


def kart_kimligi(ders, m):
    anahtar = "|".join(str(m.get(a) or "") for a in ("vaka", "dugum", "soru"))
    return hashlib.sha1((ders + "|" + anahtar).encode("utf-8")).hexdigest()[:10]


def zorlanilan_sorular(kayit, klasor, en_cok=EN_COK_KART):
    """Öğrencinin zorlandığı sorular: başarı %80'in altında, ilk denemede tam değil ya da ipucu kullanılmış.
    En düşük başarıdan başlayarak en çok en_cok tane."""
    kr = karne_.hesapla(kayit, karne_.ders_hedefleri(klasor))
    secilen = []
    for m in kr["sorular"]:
        p = m.get("p")
        if m.get("tur") == "vaka_veri" or not (m.get("soru") or m.get("dugum")):
            continue
        if (p is not None and p < 0.8) or m.get("ilk_denemede_tam") is False or m.get("ipucu"):
            secilen.append(m)
        if len(secilen) >= en_cok:
            break
    return secilen


def kart_yolu(kimlik):
    return os.path.join(depo().klasor(kimlik), KART_DOSYASI)


def kartlari_oku(kimlik):
    d, _ = kd.guvenli_oku(kart_yolu(kimlik))
    d = d if isinstance(d, dict) else {}
    d.setdefault("surum", 1)
    d.setdefault("kartlar", {})
    return d


def kartlari_guncelle(kimlik, ders, kayit, klasor):
    """Zorlanılan sorulardan tekrar kartları üretir; var olan kartın tekrar düzeni korunur. Ders başına en çok 10."""
    d = kartlari_oku(kimlik)
    eski = {k["id"]: k for k in d["kartlar"].get(ders, [])}
    yeni = []
    for m in zorlanilan_sorular(kayit, klasor):
        kid = kart_kimligi(ders, m)
        bilgi = soru_bilgisi(klasor, m)
        kart = {"id": kid, "soru": bilgi["soru"], "hedef": m.get("hedef"), "bloom": m.get("bloom"),
                "basari": m.get("p")}
        for a in ("secenekler", "dogru", "ornek_cevap", "vaka_ozeti", "kaynak"):
            if bilgi.get(a) not in (None, "", []):
                kart[a] = bilgi[a]
        if kid in eski:
            for a in ("kutu", "sonraki_tekrar", "eklenme", "sonuclar", "ogrenildi"):
                if a in eski[kid]:
                    kart[a] = eski[kid][a]
        else:
            kart.update({"kutu": 1, "sonraki_tekrar": gun_ekle(bugun(), KART_GUN[1]), "eklenme": bugun()})
        yeni.append(kart)
    # Önceden zorlanılıp artık listede olmayan ama henüz öğrenilmemiş kartlar, yer kaldıkça kalır.
    for kid, k in eski.items():
        if len(yeni) >= EN_COK_KART:
            break
        if kid not in {x["id"] for x in yeni} and not k.get("ogrenildi"):
            yeni.append(k)
    d["kartlar"][ders] = yeni[:EN_COK_KART]
    _json_yaz(kart_yolu(kimlik), d)
    return d["kartlar"][ders]


def zamani_gelen_kartlar(kimlik, gun=None):
    gun = gun or bugun()
    out = []
    kurulu = set(kurulu_dersler())
    for ders, kartlar in kartlari_oku(kimlik)["kartlar"].items():
        for k in kartlar:
            if not k.get("ogrenildi") and (k.get("sonraki_tekrar") or "") <= gun:
                out.append(dict(k, ders=ders, ders_arsivde=ders not in kurulu))
    return sorted(out, key=lambda k: (k.get("sonraki_tekrar") or "", k.get("basari") if k.get("basari") is not None else 1))


def kart_sonucu(kimlik, ders, kart_id, dogru):
    """Tekrar kartı sonucu: doğru → bir üst kutu (3, 7, 21, 60 gün); 4. kutuda yeniden doğru → öğrenildi;
    yanlış → 1. kutu, ertesi gün."""
    d = kartlari_oku(kimlik)
    kart = next((k for k in d["kartlar"].get(ders, []) if k["id"] == kart_id), None)
    if not kart:
        raise ValueError("Böyle bir tekrar kartı yok: %s / %s" % (ders, kart_id))
    b = bugun()
    kutu = int(kart.get("kutu") or 1)
    if dogru:
        if kutu >= 4:
            kart["ogrenildi"] = b
        kutu = min(4, kutu + 1)
        kart["sonraki_tekrar"] = gun_ekle(b, KART_GUN[kutu])
    else:
        kutu = 1
        kart["sonraki_tekrar"] = gun_ekle(b, 1)
        kart.pop("ogrenildi", None)
    kart["kutu"] = kutu
    kart["sonuclar"] = (kart.get("sonuclar") or [])[-9:] + [{"tarih": b, "dogru": bool(dogru)}]
    _json_yaz(kart_yolu(kimlik), d)
    return kart


# ---------- Tamamlama raporu ----------
def _sure_metni(oturumlar):
    dk = sum(float(o.get("sure_dk") or 0) for o in oturumlar)
    if not dk:
        return None
    return "%d saat %d dakika" % divmod(int(round(dk)), 60) if dk >= 60 else "%d dakika" % round(dk)


def tamamlama_raporu(kimlik, ders, ogrenci_notu=None, isaretle=True):
    """Dersin tamamlama raporunu yazar (<kayıtlar>/<kimlik>/raporlar/<ders>_tamamlama.md, her seferinde
    güncellenir), tekrar kartlarını yeniler ve kaydı 'tamamlandı' diye işaretler."""
    klasor = ders_klasoru(ders)
    if not os.path.isdir(klasor):
        raise FileNotFoundError("Ders bu bilgisayarda kurulu değil: %s" % ders)
    dp = depo()
    k, _ = dp.yukle(kimlik, ders)
    if not k:
        raise FileNotFoundError("Bu öğrencinin bu derste kaydı yok: %s / %s" % (kimlik, ders))
    if ogrenci_notu:
        k["ogrenci_notu"] = str(ogrenci_notu).strip()[:4000]
    if isaretle and not k.get("tamamlandi"):
        k["tamamlandi"] = bugun()
    hedefler = karne_.ders_hedefleri(klasor)
    kr = karne_.hesapla(k, hedefler, bugun())
    kartlar = kartlari_guncelle(kimlik, ders, k, klasor)
    baslik = mb.ders_basligi(ders)
    otur = k.get("oturumlar") or []
    tarihler = sorted(o.get("tarih") for o in otur if o.get("tarih"))
    y = ["# Ders tamamlama raporu: %s" % baslik, "",
         "Öğrenci: %s · Rapor tarihi: %s" % (k.get("ogrenci") or kimlik, bugun()),
         "Çalışma: %d oturum%s%s" % (len(otur), (", %s – %s" % (tarihler[0], tarihler[-1])) if tarihler else "",
                                     (" · toplam %s" % _sure_metni(otur)) if _sure_metni(otur) else ""),
         "Genel başarı: %s (%d cevap)" % (karne_.yuzde(kr["genel_oran"]), kr["cevap_sayisi"]), "",
         "> Bu rapor not için değildir. Yalnız bu bilgisayarda durur; hiçbir yere gönderilmez. İstersen "
         "öğretmenine kendin gönderebilirsin.", ""]
    if k.get("deneme"):
        y += ["> **DENEME KAYDI:** öğretmen denemesidir; araştırma verisine katılmaz.", ""]
    y += ["## Hedefler", "", "| Hedef | Hedef düzey | Ulaşılan (yardımsız) | Başarı | Durum |", "| --- | --- | --- | --- | --- |"]
    for h in kr["hedefler"]:
        y.append("| %s %s | %s | %s | %s | %s |" % (
            h["id"], h.get("baslik") or "", karne_.BLOOM_AD.get(h.get("hedef_bloom"), "-"),
            karne_.BLOOM_AD.get(h.get("ulasilan_bloom"), "-"), karne_.yuzde(h["oran"]),
            karne_.DURUM_AD.get(h["durum"], h["durum"])))
    hb = {h["id"]: h for h in kr["hedefler"]}
    y += ["", "## Zorlandığın konular", ""]
    zor = [hb[h] for h in kr["gelistirilecek"] if h in hb]
    if zor:
        y += ["- %s %s (başarı %s)" % (h["id"], h.get("baslik") or "", karne_.yuzde(h["oran"])) for h in zor]
    if kr["yoklanmayan"]:
        y.append("- Henüz yoklanmayan hedefler: " + ", ".join(kr["yoklanmayan"]))
    acik = [yid for yid, v in (k.get("yanilgilar") or {}).items() if v.get("durum") == "acik"]
    if acik:
        y.append("- Açık kalan yanılgılar: " + ", ".join(acik))
    if not (zor or kr["yoklanmayan"] or acik):
        y.append("Belirgin bir zorlanma görünmüyor.")
    if kr["vakalar"] or kr["tehlikeli_secimler"]:
        y += ["", "## Vakalar", ""]
        for v in kr["vakalar"]:
            y.append("- %s · %s · %s%s" % (v.get("tarih", "-"), v.get("vaka", "-"),
                                          karne_.SONUC_AD.get(v.get("sonuc"), v.get("sonuc", "-")),
                                          (" · yeniden anlatılan: " + ", ".join(v["yeniden_anlatilan_bolumler"]))
                                          if v.get("yeniden_anlatilan_bolumler") else ""))
        if kr["tehlikeli_secimler"]:
            y.append("- Hastaya zarar verebilecek seçim: %d kez" % len(kr["tehlikeli_secimler"]))
    if k.get("sorular"):
        y += ["", "## Sorduğun sorular", ""]
        y += ["- %s%s" % (s.get("soru", ""), " (kaynakta yok)" if s.get("kaynakta_yok") else "") for s in k["sorular"][-15:]]
    ekler = mb.durum_oku(ders).get("ekler") or []
    if ekler:
        y += ["", "## Kendi eklediğin makaleler", ""]
        y += ["- %s" % (e.get("kisa") or e.get("baslik") or e.get("id")) for e in ekler]
    if k.get("ogrenci_notu"):
        y += ["", "## Notun", "", k["ogrenci_notu"]]
    y += ["", "## Tekrar kartların", "",
          "Zorlandığın %d soru tekrar kartı oldu. Ders arşive kaldırılsa bile bu kartlar kalır ve zamanı gelince "
          "tekrar oturumunda karşına çıkar." % len(kartlar) if kartlar else "Tekrar kartı çıkmadı."]
    for kart in kartlar:
        y.append("- %s (sonraki tekrar: %s)" % (kart["soru"][:140], kart.get("sonraki_tekrar") or "-"))
    yol = dp.metin_yaz(kimlik, "raporlar", "%s_tamamlama.md" % ders, "\n".join(y) + "\n")
    k["tamamlama_raporu"] = bugun()
    dp.yaz(kimlik, ders, k)
    return {"dosya": yol, "kart_sayisi": len(kartlar), "genel_basari": kr["genel_oran"],
            "gelistirilecek": kr["gelistirilecek"], "yoklanmayan": kr["yoklanmayan"]}


# ---------- Arşiv ----------
def arsiv_kok():
    return os.path.join(veri_yeri.belgeler(), "KlinikKoç Arşiv")


def arsiv_listesi_yolu():
    return os.path.join(veri_yeri.veri_kok(), "arsiv.json")


def arsiv_listesi():
    d = _json_oku(arsiv_listesi_yolu(), {}) or {}
    out = []
    for a in d.get("arsiv") or []:
        a = dict(a)
        a["dosya_var"] = bool(a.get("dosya")) and os.path.exists(a["dosya"])
        out.append(a)
    return out


def _arsiv_listesine(giris=None, cikar=None):
    d = _json_oku(arsiv_listesi_yolu(), {}) or {}
    lst = [a for a in d.get("arsiv") or [] if a.get("ders") not in {cikar, (giris or {}).get("ders")}]
    if giris:
        lst.append(giris)
    _json_yaz(arsiv_listesi_yolu(), {"arsiv": lst})


BENIOKU = """KlinikKoç ders arşivi: {baslik}

Bu zip, dersin kendisini (ses ve videolar hariç), ilerleme kayıtlarını, tamamlama raporlarını ve makale listesini
taşır. Makale PDF'leri bu zip'te YOKTUR; şu klasörde durur ve silinmez:
  {makale_klasoru}

Dersi geri getirmek için: KlinikKoç'ta "Makaleler ve ders paketleri" sayfasının "Depolama ve arşiv" bölümüne bu
zip'i bırakın. KlinikKoç PDF'leri önce o klasörde arar, bulamadıklarını yeniden indirmeyi dener; ilerlemeniz
kaldığı yerden sürer.

Arşivlenme tarihi: {tarih}
"""


def arsivle(ders, cikis=None):
    """Dersi arşive kaldırır. Sıra: raporlar → zip → zip denetimi → silme. Zip sağlam değilse hiçbir şey silinmez."""
    klasor = ders_klasoru(ders)
    if not os.path.isdir(klasor):
        raise FileNotFoundError("Ders bu bilgisayarda kurulu değil: %s" % ders)
    if yerlesik_mi(ders):
        raise ValueError("Bu ders programla birlikte gelir; arşive kaldırılamaz.")
    once = {"ders_bayt": klasor_boyutu(klasor), "dizin_bayt": dizin_payi(ders)}
    baslik = mb.ders_basligi(ders)
    makale_klasoru = mb.makale_klasoru(ders)
    uyarilar = []
    # 1) Her öğrenci için tamamlama raporu (yoksa ya da kayıt rapordan yeniyse) ve tekrar kartları.
    ogrenciler = []
    for kimlik, yol in ders_kayitlari(ders):
        k = _json_oku(yol, {}) or {}
        ogrenciler.append(kimlik)
        if not k.get("tamamlama_raporu") or str(k.get("guncelleme") or "")[:10] > k["tamamlama_raporu"]:
            try:
                tamamlama_raporu(kimlik, ders, isaretle=False)
            except Exception as e:  # rapor yazılamasa da arşiv sürer; kayıt zip'e girer
                uyarilar.append("%s için tamamlama raporu yazılamadı: %s" % (kimlik, e))
    # 2) Zip.
    cikis = cikis or arsiv_kok()
    os.makedirs(cikis, exist_ok=True)
    zip_yolu = os.path.join(cikis, "%s_%s.zip" % (ders, bugun()))
    n = 2
    while os.path.exists(zip_yolu):
        zip_yolu, n = os.path.join(cikis, "%s_%s-%d.zip" % (ders, bugun(), n)), n + 1
    pdfler = sorted(os.listdir(makale_klasoru)) if os.path.isdir(makale_klasoru) else []
    vardi = {ic: os.path.isdir(os.path.join(klasor, ic)) for ic in ("audio", "videolar")}
    manifest = {"surum": ARSIV_SURUM, "tur": "klinikkoc-ders-arsivi", "ders": ders, "baslik": baslik,
                "tarih": time.strftime("%Y-%m-%d %H:%M"), "makale_klasoru": makale_klasoru, "pdfler": pdfler,
                "ogrenciler": ogrenciler, "ses_vardi": vardi["audio"], "video_vardi": vardi["videolar"]}
    gecici = zip_yolu + ".yaziliyor"
    defter = depo().defter()["ogrenciler"]
    try:
        with zipfile.ZipFile(gecici, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("arsiv.json", json.dumps(manifest, ensure_ascii=False, indent=1))
            z.writestr("BENIOKU.txt", BENIOKU.format(baslik=baslik, makale_klasoru=makale_klasoru, tarih=manifest["tarih"]))
            for kok, klasorler, dosyalar in os.walk(klasor):
                rel = os.path.relpath(kok, klasor)
                if rel == ".":
                    klasorler[:] = [x for x in klasorler if x not in ARSIVE_GIRMEYEN]
                for ad in dosyalar:
                    tam = os.path.join(kok, ad)
                    z.write(tam, "ders/%s/%s" % (ders, os.path.relpath(tam, klasor).replace(os.sep, "/")))
            kkok = veri_yeri.kayit_kok()
            for kimlik in ogrenciler:
                z.write(os.path.join(kkok, kimlik, ders + ".json"), "kayitlar/%s/%s.json" % (kimlik, ders))
                for alt in ("raporlar", "karneler"):
                    for y in sorted(glob.glob(os.path.join(glob.escape(os.path.join(kkok, kimlik, alt)), ders + "_*.md"))):
                        z.write(y, "kayitlar/%s/%s/%s" % (kimlik, alt, os.path.basename(y)))
            z.writestr("kayitlar/ogrenciler.json", json.dumps({k: defter[k] for k in ogrenciler if k in defter},
                                                              ensure_ascii=False, indent=1))
            if os.path.exists(mb.durum_yolu(ders)):
                z.write(mb.durum_yolu(ders), "makaleler/durum.json")
        # 3) Denetim: zip açılıyor mu, ders dosyaları eksiksiz mi?
        with zipfile.ZipFile(gecici) as z:
            if z.testzip() is not None:
                raise RuntimeError("Arşiv zip'i bozuk çıktı; ders silinmedi.")
            adlar = set(z.namelist())
            for kok, klasorler, dosyalar in os.walk(klasor):
                if os.path.relpath(kok, klasor) == ".":
                    klasorler[:] = [x for x in klasorler if x not in ARSIVE_GIRMEYEN]
                for ad in dosyalar:
                    rel = os.path.relpath(os.path.join(kok, ad), klasor).replace(os.sep, "/")
                    if "ders/%s/%s" % (ders, rel) not in adlar:
                        raise RuntimeError("Arşivde eksik dosya var (%s); ders silinmedi." % rel)
        os.replace(gecici, zip_yolu)
    except BaseException:
        if os.path.exists(gecici):
            os.remove(gecici)
        raise
    # 4) Silme: ders klasörü, katalog satırı, arama dizinindeki parçalar, makale durumu (zip'te var).
    silinecek = klasor + ".siliniyor"
    os.replace(klasor, silinecek)
    shutil.rmtree(silinecek, ignore_errors=True)
    ders_paketi.katalog_kaldir(ders)
    try:
        dizinden_sil(ders)
    except sqlite3.Error as e:
        uyarilar.append("Arama dizini küçültülemedi: %s" % e)
    if os.path.exists(mb.durum_yolu(ders)):
        os.remove(mb.durum_yolu(ders))
    boyut = os.path.getsize(zip_yolu)
    _arsiv_listesine({"ders": ders, "baslik": baslik, "tarih": manifest["tarih"], "dosya": zip_yolu,
                      "boyut": boyut, "makale_klasoru": makale_klasoru})
    if vardi["audio"] or vardi["videolar"]:
        uyarilar.append("Dersin ses ya da video dosyaları arşive girmedi. Geri yüklenince tarayıcının sesi kullanılır; "
                        "kendi sesleri için öğretmeninizin ders paketini yeniden kurabilirsiniz.")
    return {"ders": ders, "baslik": baslik, "dosya": zip_yolu, "boyut": boyut,
            "acilan_yer": once["ders_bayt"] + once["dizin_bayt"], "makale_klasoru": makale_klasoru,
            "pdf_sayisi": len(pdfler), "ogrenci_sayisi": len(ogrenciler), "uyarilar": uyarilar}


def _guvenli_yol(ad):
    p = ad.replace("\\", "/")
    return not (p.startswith("/") or ".." in p.split("/") or re.match(r"^[A-Za-z]:", p))


def geri_yukle(zip_yolu, makale_ara=True):
    """Arşiv zip'inden dersi, kayıtları ve makale durumunu geri getirir. Yerelde daha yeni kayıt varsa korunur."""
    with zipfile.ZipFile(zip_yolu) as z:
        adlar = z.namelist()
        if "arsiv.json" not in adlar:
            raise ValueError("Bu bir KlinikKoç ders arşivi değil (arsiv.json yok). Ders paketiyse yukarıdaki "
                             "'Ders paketi ekle' kutusunu kullanın.")
        if not all(_guvenli_yol(a) for a in adlar):
            raise ValueError("Arşivde güvensiz dosya yolu var; açılmadı.")
        m = json.loads(z.read("arsiv.json").decode("utf-8"))
        ders = mb.ders_gecerli(str(m.get("ders") or ""))
        if m.get("surum", 1) > ARSIV_SURUM:
            raise ValueError("Bu arşiv KlinikKoç'un daha yeni bir sürümüyle yapılmış; önce programı güncelleyin.")
        sonuc = {"ders": ders, "baslik": m.get("baslik"), "kayit_geri": [], "kayit_korundu": [], "kayit_ayni": [],
                 "uyarilar": []}
        # 1) Ders
        hedef = os.path.join(lessons_kok(), ders)
        if os.path.isdir(hedef):
            sonuc["ders_zaten_kurulu"] = True
        else:
            on = "ders/%s/" % ders
            dosyalar = [a for a in adlar if a.startswith(on) and not a.endswith("/")]
            if not dosyalar:
                raise ValueError("Arşivde dersin dosyaları yok.")
            fd, paket = tempfile.mkstemp(suffix=".zip")
            os.close(fd)
            try:
                with zipfile.ZipFile(paket, "w", zipfile.ZIP_DEFLATED) as p:
                    for a in dosyalar:
                        p.writestr(ders + "/" + a[len(on):], z.read(a))
                ders_paketi.yukle(paket)
            finally:
                os.remove(paket)
        # 2) Öğrenci kayıtları
        dp = depo()
        dp.hazirla()
        defter_arsiv = json.loads(z.read("kayitlar/ogrenciler.json").decode("utf-8")) if "kayitlar/ogrenciler.json" in adlar else {}
        d = dp.defter()
        degisti = False
        for kimlik, v in defter_arsiv.items():
            if kimlik not in d["ogrenciler"] and kd.kisalt(kimlik) == kimlik:
                d["ogrenciler"][kimlik] = v
                degisti = True
        if degisti:
            dp._defteri_yaz(d)
        for a in adlar:
            mt = re.fullmatch(r"kayitlar/([^/]+)/([^/]+\.json|(?:raporlar|karneler)/[^/]+\.md)", a)
            if not mt:
                continue
            kimlik, rel = mt.group(1), mt.group(2)
            if kd.kisalt(kimlik) != kimlik:
                continue
            yerel = os.path.join(dp.klasor(kimlik), *rel.split("/"))
            if rel.endswith(".json"):
                if rel != ders + ".json":
                    continue
                arsivdeki = json.loads(z.read(a).decode("utf-8"))
                mevcut, _ = dp.yukle(kimlik, ders)
                if mevcut and str(mevcut.get("guncelleme") or "") >= str(arsivdeki.get("guncelleme") or ""):
                    # Bu bilgisayardaki kayıt arşivdekiyle aynı ya da ondan yeni: dokunulmaz.
                    ayni = str(mevcut.get("guncelleme") or "") == str(arsivdeki.get("guncelleme") or "")
                    sonuc["kayit_ayni" if ayni else "kayit_korundu"].append(kimlik)
                    continue
                kd.atomik_yaz(yerel, arsivdeki)  # eski yerel kayıt varsa yedeklerde kalır
                sonuc["kayit_geri"].append(kimlik)
            elif not os.path.exists(yerel):
                os.makedirs(os.path.dirname(yerel), exist_ok=True)
                with open(yerel, "wb") as f:
                    f.write(z.read(a))
        # 3) Makale durumu
        if "makaleler/durum.json" in adlar and not os.path.exists(mb.durum_yolu(ders)):
            durum = json.loads(z.read("makaleler/durum.json").decode("utf-8"))
            durum.pop("calisiyor", None)
            _json_yaz(mb.durum_yolu(ders), durum)
    if m.get("ses_vardi") or m.get("video_vardi"):
        sonuc["uyarilar"].append("Dersin ses ya da video dosyaları arşivde yoktu; tarayıcının sesi kullanılacak.")
    # 4) Makaleler: önce makale klasörü, sonra (internet varsa) indirme; ardından dizinleme.
    if mb.kaynaklar(ders) or mb.durum_oku(ders).get("ekler"):
        sonuc["makaleler"] = mb.arka_planda_hazirla(ders, makale_ara) if makale_ara else mb.hazirla(ders, False)
    else:
        try:
            bilgi_bankasi.dizinle([ders], sessiz=True, yol=bilgi_bankasi.DIZIN)
        except Exception as e:
            sonuc["uyarilar"].append("Arama dizini güncellenemedi: %s" % e)
    _arsiv_listesine(cikar=ders)
    sonuc["makale_klasoru"] = mb.makale_klasoru(ders)
    if m.get("makale_klasoru") and os.path.normcase(m["makale_klasoru"]) != os.path.normcase(sonuc["makale_klasoru"]):
        sonuc["uyarilar"].append("Makaleler arşivdeyken şu klasördeydi: %s. PDF'ler bulunamazsa onları yeni klasöre "
                                 "taşıyıp 'Makaleleri bul' deyin: %s" % (m["makale_klasoru"], sonuc["makale_klasoru"]))
    return sonuc


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--depolama", action="store_true")
    ap.add_argument("--sinir", type=float, metavar="GB")
    ap.add_argument("--rapor", nargs=2, metavar=("OGRENCI", "DERS"))
    ap.add_argument("--arsivle", metavar="DERS")
    ap.add_argument("--geri-yukle", dest="geri_yukle", metavar="ZIP")
    a = ap.parse_args()
    if a.sinir is not None:
        print("Sınır: %s GB" % sinir_ayarla(a.sinir))
    if a.rapor:
        print(json.dumps(tamamlama_raporu(*a.rapor), ensure_ascii=False, indent=1))
    if a.arsivle:
        print(json.dumps(arsivle(a.arsivle), ensure_ascii=False, indent=1))
    if a.geri_yukle:
        print(json.dumps(geri_yukle(a.geri_yukle, makale_ara=False), ensure_ascii=False, indent=1))
    if a.depolama or not any((a.sinir is not None, a.rapor, a.arsivle, a.geri_yukle)):
        d = depolama()
        print("Toplam %s / sınır %s GB%s" % (okunur_boyut(d["toplam_bayt"]), d["sinir_gb"], " (AŞILDI)" if d["asildi"] else ""))
        for x in d["dersler"]:
            print("  %-36s %10s  son açılma %s%s" % (x["ders"], okunur_boyut(x["toplam"]), x["son_acilma"] or "-",
                                                     " (programla gelir)" if x["yerlesik"] else ""))
        for x in d["arsiv"]:
            print("  arşivde: %s → %s" % (x["ders"], x["dosya"]))


if __name__ == "__main__":
    main()
