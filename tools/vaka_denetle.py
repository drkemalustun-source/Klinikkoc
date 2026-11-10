#!/usr/bin/env python3
"""Vaka kartlarını denetler (yalnız Python'un kendi kitaplığı gerekir).

  python tools/vaka_denetle.py                 bütün derslerin vakalarını denetler
  python tools/vaka_denetle.py dosya.json ...  yalnız verilen kartları denetler

Denetlenenler: zorunlu alanlar, kimliklerin tekliği, düğümler arası bağlantılar, her yolun bir
sonla bitmesi, hedef ve ders bölümlerinin derste var olması, görsel dosyaların varlığı,
gerçek hastadan uyarlanan vakalarda anonimlik ve onam kaydı, metinde kimlik ele verebilecek
izler (tarih, telefon, kimlik/protokol numarası). Hata varsa çıkış kodu 1 olur.
Şema ve alanların anlamı: schema/vaka.schema.json, belgeler/vaka-karti.md
"""
import glob
import json
import os
import re
import sys


def _json_oku(yol):
    with open(yol, encoding="utf-8") as f:
        return json.load(f)


KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLOOM = ("hatirla", "anla", "uygula", "cozumle", "degerlendir", "olustur")
DUGUM_TURLERI = ("karar", "acik", "veri", "bilgi", "son")
BULGU_TURLERI = ("anamnez", "klinik", "radyografik", "laboratuvar", "fotograf", "diger")
SECENEK_SONUC = ("dogru", "kabul", "yanlis", "tehlikeli")
KIMLIK = "^[a-z0-9][a-z0-9-]*$"

# Kimlik ele verebilecek izler. Yanlış alarm olabilir; uyarı olarak gösterilir.
IZLER = [
    (re.compile(r"\b\d{1,2}[./]\d{1,2}[./](19|20)\d{2}\b"), "tam tarih (gün.ay.yıl) — yerine '3 gün önce' gibi göreli süre yazın"),
    (re.compile(r"\b[1-9]\d{10}\b"), "11 haneli sayı (T.C. kimlik no olabilir)"),
    (re.compile(r"\b0?5\d{2}[ -]?\d{3}[ -]?\d{2}[ -]?\d{2}\b"), "telefon numarası"),
    (re.compile(r"protokol\s*(no|numaras)", re.I), "protokol numarası"),
    (re.compile(r"\b(hasta adı|adı soyadı|ad soyad)\b", re.I), "hasta adı alanı"),
    (re.compile(r"@[a-z0-9-]+\.[a-z]{2,}", re.I), "e-posta adresi"),
]


def ders_klasoru(ders):
    """Kurulu ders (lessons/) ya da depodaki örnek ders (ornek-dersler/)."""
    for ust in ("lessons", "ornek-dersler"):
        k = os.path.join(KOK, ust, ders)
        if os.path.isdir(k):
            return k
    return os.path.join(KOK, "lessons", ders)


def ders_bilgisi(ders):
    klasor = ders_klasoru(ders)
    hedefler, bolumler, yanilgilar = set(), set(), set()
    for ad in ("ders.json", "egitmen.json"):
        yol = os.path.join(klasor, ad)
        if not os.path.exists(yol):
            continue
        d = _json_oku(yol)
        for g in d.get("goals") or []:
            hedefler.add(g.get("id"))
            hedefler.update(s.get("id") for s in g.get("subgoals") or [])
        for s in d.get("sections") or []:
            bolumler.add(s.get("id"))
        for h in d.get("hedefler") or []:
            hedefler.add(h.get("id"))
        for y in (d.get("yanilgilar") or []) + (d.get("misconceptions") or []):
            yanilgilar.add(y.get("id"))
    return os.path.isdir(klasor), hedefler, bolumler, yanilgilar


def metinleri_gez(x, yol=""):
    if isinstance(x, str):
        yield yol, x
    elif isinstance(x, dict):
        for k, v in x.items():
            yield from metinleri_gez(v, yol + "." + k if yol else k)
    elif isinstance(x, list):
        for i, v in enumerate(x):
            yield from metinleri_gez(v, "%s[%d]" % (yol, i))


def denetle(yol):
    """(hatalar, uyarilar, vaka) döndürür."""
    H, U = [], []
    try:
        with open(yol, encoding="utf-8") as f:
            v = json.load(f)
    except ValueError as e:
        return ["JSON okunamadı: %s" % e], [], None
    if not isinstance(v, dict):
        return ["Kart bir JSON nesnesi olmalı"], [], None

    for alan in ("surum", "id", "baslik", "ders", "kurgusal", "dagitim", "hedefler", "hasta", "basvuru",
                 "bulgular", "baslangic", "dugumler"):
        if alan not in v:
            H.append("Zorunlu alan yok: %s" % alan)
    if H:
        return H, U, v
    if v["surum"] != 1:
        H.append("surum 1 olmalı")
    dosya_kimligi = os.path.splitext(os.path.basename(yol))[0]
    if v["id"] != dosya_kimligi:
        H.append("id (%s) dosya adıyla (%s) aynı olmalı" % (v["id"], dosya_kimligi))
    if not re.match(KIMLIK, v["id"]):
        H.append("id yalnız küçük harf, rakam ve tire içermeli")
    if v["dagitim"] not in ("acik", "fakulte"):
        H.append("dagitim 'acik' ya da 'fakulte' olmalı")

    # Ders ve hedefler
    ders_var, hedefler, bolumler, yanilgilar = ders_bilgisi(v["ders"])
    yanilgilar |= {y.get("id") for y in v.get("yanilgilar") or []}
    beklenen = os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(yol))))
    if os.path.basename(os.path.dirname(os.path.abspath(yol))) == "vakalar" and beklenen != v["ders"]:
        H.append("Kart lessons/%s/vakalar içinde ama ders alanı '%s'" % (beklenen, v["ders"]))
    if not ders_var:
        H.append("Ders bulunamadı: lessons/%s" % v["ders"])
    for h in v["hedefler"]:
        if hedefler and h not in hedefler:
            H.append("Hedef derste yok: %s" % h)

    # Anonimlik
    if v["kurgusal"] is not True:
        a = v.get("anonimlik")
        if not isinstance(a, dict):
            H.append("Gerçek hastadan uyarlanan vakada 'anonimlik' bölümü zorunlu (kurgusal değilse)")
        else:
            if a.get("kimliksizlestirildi") is not True:
                H.append("anonimlik.kimliksizlestirildi true olmadan vaka kullanılamaz")
            if a.get("egitim_onayi") is not True:
                H.append("anonimlik.egitim_onayi true olmadan vaka kullanılamaz")
            if not (a.get("denetleyen") or "").strip():
                H.append("anonimlik.denetleyen boş")
            if not a.get("gorseller_denetlendi") and any(b.get("gorsel") for b in v["bulgular"]):
                H.append("Vakada görsel var: anonimlik.gorseller_denetlendi true olmalı")
    hasta = v.get("hasta") or {}
    ya = hasta.get("yas_araligi")
    if ya and not re.match(r"^\d{1,2}0-\d{1,2}9$|^\d{1,3}\+$", ya):
        H.append("hasta.yas_araligi on yıllık aralık olmalı (ör. 40-49), tam yaş değil: %s" % ya)
    if not (v.get("ogretmen_onayi") or {}).get("onaylandi"):
        U.append("Öğretmen onayı yok: öğrenciye 'taslak vaka' diye gösterilir")

    # Bulgular
    bulgular = {}
    for b in v["bulgular"]:
        bid = b.get("id")
        if not bid or not re.match(KIMLIK, bid):
            H.append("Bulgu kimliği geçersiz: %r" % bid)
            continue
        if bid in bulgular:
            H.append("Aynı bulgu kimliği iki kez: %s" % bid)
        bulgular[bid] = b
        if b.get("tur") not in BULGU_TURLERI:
            H.append("Bulgu %s: tur %s olmalı" % (bid, "|".join(BULGU_TURLERI)))
        if not (b.get("metin") or "").strip():
            H.append("Bulgu %s: metin boş" % bid)
        if b.get("gorsel"):
            g = os.path.join(ders_klasoru(v["ders"]), b["gorsel"])
            if not os.path.exists(g):
                H.append("Bulgu %s: görsel dosyası yok: %s" % (bid, b["gorsel"]))
            if not b.get("gorsel_aciklama"):
                U.append("Bulgu %s: gorsel_aciklama yok (eğitmen görselde ne olduğunu bilmeli)" % bid)
        if b.get("acilis", "istenince") == "istenince" and not b.get("baslik"):
            U.append("Bulgu %s: istenince açılıyor ama baslik yok (öğrenci neyi isteyeceğini bilmeli)" % bid)

    # Düğümler
    dugumler = {}
    for d in v["dugumler"]:
        did = d.get("id")
        if not did or not re.match(KIMLIK, did):
            H.append("Düğüm kimliği geçersiz: %r" % did)
            continue
        if did in dugumler:
            H.append("Aynı düğüm kimliği iki kez: %s" % did)
        dugumler[did] = d
    if v["baslangic"] not in dugumler:
        H.append("baslangic düğümü yok: %s" % v["baslangic"])

    kenarlar = {}
    for did, d in dugumler.items():
        tur = d.get("tur")
        on = "Düğüm %s" % did
        cik = []
        if tur not in DUGUM_TURLERI:
            H.append("%s: tur %s olmalı" % (on, "|".join(DUGUM_TURLERI)))
            continue
        if d.get("bloom") and d["bloom"] not in BLOOM:
            H.append("%s: geçersiz Bloom düzeyi %s" % (on, d["bloom"]))
        if tur in ("karar", "acik", "veri") and not d.get("bloom"):
            U.append("%s: bloom düzeyi yok" % on)
        if d.get("hedef") and hedefler and d["hedef"] not in hedefler:
            H.append("%s: hedef derste yok: %s" % (on, d["hedef"]))
        for alan in ("acilan_bulgular", "gerekli_bulgular"):
            for b in d.get(alan) or []:
                if b not in bulgular:
                    H.append("%s: %s içinde olmayan bulgu: %s" % (on, alan, b))
        t = d.get("takilirsa") or {}
        if t.get("bolum") and bolumler and t["bolum"] not in bolumler:
            H.append("%s: takilirsa.bolum derste yok: %s" % (on, t["bolum"]))
        if tur == "karar":
            s = d.get("secenekler") or []
            if len(s) < 2:
                H.append("%s: karar düğümünde en az 2 seçenek olmalı" % on)
            if not d.get("soru"):
                H.append("%s: soru yok" % on)
            if not any(x.get("sonuc") == "dogru" for x in s):
                H.append("%s: en az bir seçeneğin sonucu 'dogru' olmalı" % on)
            for i, x in enumerate(s):
                if x.get("sonuc") not in SECENEK_SONUC:
                    H.append("%s, seçenek %d: sonuc %s olmalı" % (on, i + 1, "|".join(SECENEK_SONUC)))
                if x.get("yanilgi") and x["yanilgi"] not in yanilgilar:
                    H.append("%s, seçenek %d: yanılgı tanımlı değil: %s (vakanın yanilgilar listesine ekleyin)" % (on, i + 1, x["yanilgi"]))
                if not x.get("geribildirim"):
                    U.append("%s, seçenek %d: geribildirim yok" % (on, i + 1))
                if x.get("sonraki"):
                    cik.append(x["sonraki"])
                elif x.get("sonuc") in ("dogru", "kabul"):
                    H.append("%s, seçenek %d: doğru/kabul seçenekte sonraki düğüm yazılmalı" % (on, i + 1))
            if not d.get("takilirsa"):
                U.append("%s: takilirsa yok (öğrenci takılırsa hangi ders bölümüne dönülecek?)" % on)
        elif tur == "acik":
            if not d.get("soru"):
                H.append("%s: soru yok" % on)
            if not d.get("rubrik"):
                H.append("%s: açık uçlu soruda rubrik zorunlu" % on)
            for i, r in enumerate(d.get("rubrik") or []):
                if not r.get("olcut") or not isinstance(r.get("puan"), int) or not 1 <= r["puan"] <= 5:
                    H.append("%s, rubrik %d: olcut ve 1–5 arası puan gerekli" % (on, i + 1))
            if not d.get("ornek_cevap"):
                H.append("%s: açık uçlu soruda ornek_cevap zorunlu" % on)
        elif tur == "veri":
            if not d.get("gerekli_bulgular"):
                H.append("%s: veri düğümünde gerekli_bulgular zorunlu" % on)
        elif tur == "son":
            if d.get("sonraki") or d.get("secenekler"):
                H.append("%s: son düğümünden çıkış olamaz" % on)
            if d.get("sonuc") not in ("iyi", "kabul", "kotu"):
                H.append("%s: son düğümünde sonuc iyi|kabul|kotu olmalı" % on)
        if tur in ("acik", "veri", "bilgi"):
            if d.get("sonraki"):
                cik.append(d["sonraki"])
            else:
                H.append("%s: sonraki düğüm yazılmalı" % on)
        for c in cik:
            if c not in dugumler:
                H.append("%s: olmayan düğüme gidiyor: %s" % (on, c))
        kenarlar[did] = [c for c in cik if c in dugumler]

    # Erişilebilirlik ve sonlar
    if v["baslangic"] in dugumler:
        gorulen, yigin = set(), [v["baslangic"]]
        while yigin:
            n = yigin.pop()
            if n in gorulen:
                continue
            gorulen.add(n)
            yigin.extend(kenarlar.get(n, []))
        for n in dugumler:
            if n not in gorulen:
                U.append("Düğüm %s başlangıçtan erişilemiyor" % n)
        sonlar = {n for n, d in dugumler.items() if d.get("tur") == "son"}
        if not sonlar & gorulen:
            H.append("Başlangıçtan hiçbir son düğümüne varılamıyor")
        # Sona varamayan düğüm (döngüye hapsolan yol)
        varan = set(sonlar)
        degisti = True
        while degisti:
            degisti = False
            for n, c in kenarlar.items():
                if n not in varan and any(x in varan for x in c):
                    varan.add(n)
                    degisti = True
        for n in gorulen - varan:
            H.append("Düğüm %s'den hiçbir sona varılamıyor" % n)

    # Kimlik izleri
    for alan, metin in metinleri_gez(v):
        if alan.startswith("anonimlik"):
            continue
        for desen, ad in IZLER:
            if desen.search(metin):
                (U if v["kurgusal"] else H).append("%s: %s olabilir: '%s'" % (alan, ad, desen.search(metin).group(0)))
    return H, U, v


def tum_kartlar():
    return sorted(glob.glob(os.path.join(KOK, "lessons", "*", "vakalar", "*.json")) +
                  glob.glob(os.path.join(KOK, "ornek-dersler", "*", "vakalar", "*.json")))


def main(argv):
    yollar = argv or tum_kartlar()
    if not yollar:
        print("Vaka kartı bulunamadı (lessons/<ders>/vakalar/*.json).")
        return 0
    toplam_hata = 0
    for y in yollar:
        H, U, _ = denetle(y)
        ad = os.path.relpath(y, KOK)
        print(("✗ " if H else "✓ ") + ad)
        for h in H:
            print("   hata:  " + h)
        for u in U:
            print("   uyarı: " + u)
        toplam_hata += len(H)
    print("%d kart, %d hata." % (len(yollar), toplam_hata))
    return 1 if toplam_hata else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
