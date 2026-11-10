#!/usr/bin/env python3
"""Dayanak eşiklerini ölçer: ders içi ve ders dışı sorularda en iyi benzerlik nasıl dağılıyor?

Bilgi bankası her aramada iki sinyal ölçer (bkz. tools/bilgi_bankasi.py, "Dayanak etiketi"):
  anlam benzerliği (anlam araması açıksa) ve sözcük kapsamı (her zaman).
Bu betik iki grup soru sorar:
  ders içi:  her dersin ders.json sorularının metinleri ve egitmen.json hedef başlıklarından türetilmiş sorular
  ders dışı: diş hekimliğinin başka alanlarından ve tamamen alan dışından sorular (aşağıdaki liste)
ve her iki sinyal için iki grubun dağılımını (en az, çeyrekler, en çok) yazar, iki grubu en iyi ayıran eşikleri önerir.

Ders içeriği ekrana yazılmaz; yalnız sayılar ve ders dışı soruların kendisi yazılır (onlar bu dosyada).

Kullanım:
  python tools/dayanak_olc.py                 bütün dersler
  python tools/dayanak_olc.py --ders X        yalnız bir ders
  python tools/dayanak_olc.py --ayrinti       ders dışı her sorunun değerlerini de yaz
  python tools/dayanak_olc.py --json rapor.json   sonuçları dosyaya da yaz

Önerilen eşikler kendiliğinden yazılmaz. Öğretmen onaylarsa bilgi_bankasi.py'deki DAYANAK_* sabitlerine
işlenir ya da KLINIK_KOC_DAYANAK_GUCLU / _ZAYIF / _SOZCUK_GUCLU / _SOZCUK_ZAYIF ortam değişkenleriyle verilir.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bilgi_bankasi as bb  # noqa: E402

# Ders dışı sorular. İlk soru qa-testi/karsilastir.js'teki kaynak dışı denetim sorusudur.
DERS_DISI = [
    "Diş beyazlatmada hangi jel daha etkilidir?",
    "Ofis tipi beyazlatmada hidrojen peroksit yoğunluğu ne olmalı?",
    "Ev tipi beyazlatma plağı kaç saat takılır?",
    "Ortodontik braket hangi yaşta takılır?",
    "Şeffaf plak ile tel tedavisinin farkı nedir?",
    "Sınıf II maloklüzyonda fonksiyonel aparey ne zaman kullanılır?",
    "Kanal tedavisinde hangi irrigasyon solüsyonu kullanılır?",
    "Kök kanal dolgusunda güta perka nasıl yoğunlaştırılır?",
    "Süt dişlerinde pulpotomi hangi durumda yapılır?",
    "Kompozit dolguda hangi bonding sistemi tercih edilmeli?",
    "Zirkonyum kron için preparasyon ne kadar derin olmalı?",
    "Gömülü yirmi yaş dişi çekiminden sonra kuru soket nasıl önlenir?",
    "Çocuklarda flor vernik kaç ayda bir uygulanır?",
    "Temporomandibular eklem ağrısında gece plağı işe yarar mı?",
    "Karnıyarık nasıl yapılır?",
    "Kek kabarmazsa ne yapmalı?",
    "Dün akşamki futbol maçını kim kazandı?",
    "Ofsayt kuralı nasıl işler?",
    "İstanbul'dan Ankara'ya trenle kaç saat sürer?",
    "Kışın domates fidesi nasıl yetiştirilir?",
]


def ders_ici_sorgular(ders):
    klasor = os.path.join(bb.KOK, "lessons", ders)
    d = bb._oku(os.path.join(klasor, "ders.json")) or {}
    eg = bb._oku(os.path.join(klasor, "egitmen.json")) or {}
    out = []
    for s in d.get("sections", []):
        for st in s.get("steps", []):
            q = st.get("question") or {}
            if q.get("prompt"):
                out.append(("soru", q["prompt"]))
    for h in eg.get("hedefler") or []:
        if h.get("baslik"):
            out.append(("hedef", h["baslik"].rstrip(".?") + " nedir?"))
    for s in (eg.get("olcme") or {}).get("sorular") or []:
        if s.get("soru"):
            out.append(("olcme", s["soru"]))
    return out


# Ders içi soruların cevabı aranırken soru parçalarının kendisi aranmaz; yoksa soru kendini bulur ve ölçüm şişer.
CEVAP_TURLERI = ["kaynak", "anlatim", "ogretmen_notu", "vaka"]


def olc(sorgu, ders, model):
    _, oz = bb.ara_ve_dayanak(sorgu, ders=ders, tur=CEVAP_TURLERI, k=6, model=model)
    return oz


def dagilim(x):
    x = sorted(v for v in x if v is not None)
    if not x:
        return None

    def c(p):
        i = (len(x) - 1) * p
        a, b = int(i), min(int(i) + 1, len(x) - 1)
        return round(x[a] + (x[b] - x[a]) * (i - a), 3)
    return {"n": len(x), "en_az": x[0], "q1": c(0.25), "ortanca": c(0.5), "q3": c(0.75), "en_cok": x[-1]}


def esik_oner(ic, dis, pay=0.02):
    """İki eşik önerir (anlamları belgeler/bilgi-bankasi.md'de).
    guclu: hiçbir ders dışı sorunun ulaşamadığı değer: en yüksek ders dışı değer + küçük bir güvenlik payı.
    zayif: ders dışı soruların en az %90'ının altında kaldığı değer. Bu ikisinin arası "zayıf" bölgedir:
           eğitmen yalnız parçanın açıkça söylediğini aktarır."""
    ic = [v for v in ic if v is not None]
    dis = sorted(v if v is not None else 0.0 for v in dis)
    if not ic or not dis:
        return None
    guclu = round(dis[-1] + pay, 3)
    i = (len(dis) - 1) * 0.9
    a, b = int(i), min(int(i) + 1, len(dis) - 1)
    zayif = round(min(dis[a] + (dis[b] - dis[a]) * (i - a), guclu), 3)
    return {"zayif": zayif, "guclu": guclu,
            "ders_ici_dayanakli_orani": round(sum(v >= zayif for v in ic) / len(ic), 3),
            "ders_disi_dayanaksiz_orani": round(sum(v < zayif for v in dis) / len(dis), 3),
            "guclu_ustundeki_ders_ici_orani": round(sum(v >= guclu for v in ic) / len(ic), 3)}


def main():
    ap = argparse.ArgumentParser(description="Dayanak eşiklerini ölç ve öner")
    ap.add_argument("--ders")
    ap.add_argument("--ayrinti", action="store_true")
    ap.add_argument("--json", metavar="DOSYA")
    a = ap.parse_args()

    model = bb.AnlamModeli()
    print("Anlam araması: %s" % ("açık (" + model.ad + ")" if model.hazir else "kapalı: " + str(model.neden)))
    bb.dizinle(model=model, sessiz=True)
    dersler = [a.ders] if a.ders else bb.ders_kimlikleri()

    ic = []
    for ders in dersler:
        sorgular = ders_ici_sorgular(ders)
        for tur, s in sorgular:
            ic.append(dict(olc(s, ders, model), ders=ders, kaynak=tur))
        print("  %-34s %d ders içi soru" % (ders, len(sorgular)))
    dis = []
    for s in DERS_DISI:
        # Ders dışı soru her derste ayrı aranır; en kötü durum (en yüksek değer) sayılır.
        en = None
        for ders in dersler:
            oz = olc(s, ders, model)
            if en is None or (oz["en_iyi_benzerlik"] or 0, oz["en_iyi_kapsam"] or 0) > \
                    (en["en_iyi_benzerlik"] or 0, en["en_iyi_kapsam"] or 0):
                en = dict(oz, ders=ders)
        dis.append(dict(en, sorgu=s))

    rapor = {"anlam_aramasi": model.hazir, "dersler": dersler, "sinyaller": {}}
    sinyaller = [("en_iyi_kapsam", "Sözcük kapsamı", "sozcuk")]
    if model.hazir:
        sinyaller.insert(0, ("en_iyi_benzerlik", "Anlam benzerliği", "anlam"))
    for alan, ad, kisa in sinyaller:
        di, dd = dagilim([x[alan] for x in ic]), dagilim([x[alan] for x in dis])
        oneri = esik_oner([x[alan] for x in ic], [x[alan] for x in dis])
        rapor["sinyaller"][kisa] = {"ders_ici": di, "ders_disi": dd, "oneri": oneri}
        print("\n%s" % ad)
        for grup, v in (("ders içi ", di), ("ders dışı", dd)):
            if v:
                print("  %s n=%-3d en az %.3f · Ç1 %.3f · ortanca %.3f · Ç3 %.3f · en çok %.3f" % (
                    grup, v["n"], v["en_az"], v["q1"], v["ortanca"], v["q3"], v["en_cok"]))
            else:
                print("  %s değer yok" % grup)
        if oneri:
            print("  Önerilen eşikler: zayıf ≥ %.3f, güçlü ≥ %.3f" % (oneri["zayif"], oneri["guclu"]))
            print("  Bu eşiklerle: dayanaklı sayılan ders içi oranı %%%d · dayanaksız sayılan ders dışı oranı %%%d · "
                  "güçlü sayılan ders içi oranı %%%d" % (oneri["ders_ici_dayanakli_orani"] * 100,
                                                     oneri["ders_disi_dayanaksiz_orani"] * 100,
                                                     oneri["guclu_ustundeki_ders_ici_orani"] * 100))
    print("\nŞu anki eşiklerle etiketler:")
    for grup, liste in (("ders içi", ic), ("ders dışı", dis)):
        say = {e: sum(1 for x in liste if x["dayanak"] == e) for e in ("guclu", "zayif", "yok")}
        print("  %-9s güçlü %d · zayıf %d · yok %d" % (grup, say["guclu"], say["zayif"], say["yok"]))
    if a.ayrinti:
        print("\nDers dışı sorular:")
        for x in dis:
            print("  %-6s benzerlik %-6s kapsam %-6s  %s" % (x["dayanak"], x["en_iyi_benzerlik"], x["en_iyi_kapsam"],
                                                           x["sorgu"]))
    if a.json:
        rapor["ders_disi"] = [{k: x.get(k) for k in ("sorgu", "dayanak", "en_iyi_benzerlik", "en_iyi_kapsam")}
                              for x in dis]
        rapor["ders_ici_etiketler"] = {e: sum(1 for x in ic if x["dayanak"] == e) for e in ("guclu", "zayif", "yok")}
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(rapor, f, ensure_ascii=False, indent=1)
        print("\nYazıldı:", a.json)


if __name__ == "__main__":
    main()
