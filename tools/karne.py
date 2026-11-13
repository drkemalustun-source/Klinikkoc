"""Öğrenci karnesi: öğrencinin kendi kaydından (kalıcı kayıt klasörü/<öğrenci kimliği>/<ders>.json) hesaplanır.

Karne not için değildir; öğrencinin nerede güçlü, nerede tekrar gerektiğini görmesi içindir ve
yalnız öğrencinin bilgisayarında durur. Hesaplanan ölçüler:
  - hedef başına başarı oranı (alınan puan / en yüksek puan) ve ilk denemede doğru oranı
  - Bloom düzeyine göre başarı (hatırla → oluştur)
  - soru (madde) başına güçlük: bu öğrencinin o sorudaki ortalama başarısı (p değeri).
    Tek öğrencinin verisidir; sınıf düzeyindeki madde analizi (isteğe bağlı, anonim) sonraki aşamadadır.
  - rubrikte en sık eksik kalan ölçütler, vaka sonuçları, tehlikeli seçimler
"""
import json
import os


def _json_oku(yol):
    with open(yol, encoding="utf-8") as f:
        return json.load(f)


BLOOM = ["hatirla", "anla", "uygula", "cozumle", "degerlendir", "olustur"]
BLOOM_AD = dict(zip(BLOOM, ["Hatırla", "Anla", "Uygula", "Çözümle", "Değerlendir", "Oluştur"]))
TUR_AD = {"secmeli": "seçmeli", "acik": "açık uçlu", "vaka_karar": "vaka kararı", "vaka_acik": "vaka, açık uçlu",
          "vaka_veri": "vaka, veri toplama"}
DURUM_AD = {"ele_alinmadi": "ele alınmadı", "destekle_yapti": "destekle yaptı", "bagimsiz_yapti": "bağımsız yaptı",
            "tekrar_gerekli": "tekrar gerekli", "devam_ediyor": "devam ediyor"}
SONUC_AD = {"iyi": "iyi sonuç", "kabul": "kabul edilebilir", "kotu": "kötü sonuç", "yarim": "yarım kaldı"}


def secenekli_mi(c):
    """Seçeneklerden seçilerek verilen cevap mı (seçmeli soru ya da takılınca gösterilen seçenekler)?"""
    return bool(c.get("secenekli")) or c.get("tur") == "secmeli"


def bloom_tablosu(bloom):
    """Bloom tablosu (markdown satırları): her düzeyde kendi cevabıyla ve seçenekle verilen cevaplar ayrı."""
    hucre = lambda g: "-" if not g or not g["cevap"] else "%s (%d soru)" % (yuzde(g["oran"]), g["cevap"])
    y = ["| Düzey | Kendi cevabıyla | Seçenekten seçerek |", "| --- | --- | --- |"]
    for b in bloom:
        serbest = b.get("serbest") or {"cevap": b["cevap"], "oran": b["oran"]}
        y.append("| %s | %s | %s |" % (BLOOM_AD[b["duzey"]], hucre(serbest), hucre(b.get("secenekli"))))
    y += ["", "Seçenekten seçerek verilen cevaplar, kendi kurduğun cevaplardan ayrı gösterilir."]
    return y


def oran(puan, en):
    return round(puan / en, 3) if en else None


def yuzde(x):
    return "-" if x is None else "%%%d" % round(x * 100)


def gucluk(p):
    if p is None:
        return "-"
    return "kolay" if p >= 0.8 else "orta" if p >= 0.5 else "zor"


def ders_hedefleri(ders_klasoru):
    """[{id, baslik, bloom}] — önce egitmen.json, yoksa ders.json alt hedefleri."""
    eg = os.path.join(ders_klasoru, "egitmen.json")
    if os.path.exists(eg):
        h = _json_oku(eg).get("hedefler") or []
        if h:
            return [{"id": x["id"], "baslik": x.get("baslik"), "bloom": x.get("bloom")} for x in h]
    d = os.path.join(ders_klasoru, "ders.json")
    if os.path.exists(d):
        dj = _json_oku(d)
        return [{"id": s["id"], "baslik": s.get("text"), "bloom": s.get("bloom")}
                for g in dj.get("goals") or [] for s in g.get("subgoals") or []]
    return []


def hesapla(kayit, hedefler, bugun=None):
    cevaplar = kayit.get("cevaplar") or []
    out = {"ogrenci": kayit.get("ogrenci"), "ders": kayit.get("ders"), "cevap_sayisi": len(cevaplar)}
    if kayit.get("deneme"):
        out["deneme"] = True  # öğretmen denemesi: karnede ayrı işaretlenir, araştırma aktarımına katılmaz
    toplam_p = sum(c.get("puan", 0) for c in cevaplar)
    toplam_e = sum(c.get("en_yuksek", 1) for c in cevaplar)
    out["genel_oran"] = oran(toplam_p, toplam_e)

    # Hedefler
    hed = []
    for h in hedefler:
        cs = [c for c in cevaplar if c.get("hedef") == h["id"]]
        ilk = [c for c in cs if c.get("ilk_deneme") is not None]
        v = (kayit.get("hedefler") or {}).get(h["id"], {})
        hed.append({
            "id": h["id"], "baslik": h.get("baslik"), "hedef_bloom": h.get("bloom"), "cevap": len(cs),
            "oran": oran(sum(c.get("puan", 0) for c in cs), sum(c.get("en_yuksek", 1) for c in cs)),
            "ilk_deneme_dogru": oran(sum(1 for c in ilk if c.get("ilk_deneme") and c.get("puan", 0) >= c.get("en_yuksek", 1)),
                                     len(ilk)) if ilk else None,
            "ulasilan_bloom": v.get("yardimsiz_duzey"), "durum": v.get("durum", "ele_alinmadi"),
            "sonraki_tekrar": v.get("sonraki_tekrar")})
    out["hedefler"] = hed

    # Bloom düzeyleri: öğrencinin kendi kurduğu cevaplar ile seçenekten seçtikleri ayrı sayılır; seçenekle verilen
    # doğru cevap o düzeyde bağımsız başarı gibi görünmesin (v5).
    bl = []
    for b in BLOOM:
        cs = [c for c in cevaplar if c.get("bloom") == b]
        if cs:
            g = {"duzey": b, "cevap": len(cs),
                 "oran": oran(sum(c.get("puan", 0) for c in cs), sum(c.get("en_yuksek", 1) for c in cs))}
            for ad, grup in (("serbest", [c for c in cs if not secenekli_mi(c)]), ("secenekli", [c for c in cs if secenekli_mi(c)])):
                g[ad] = {"cevap": len(grup), "oran": oran(sum(c.get("puan", 0) for c in grup),
                                                           sum(c.get("en_yuksek", 1) for c in grup))}
            bl.append(g)
    out["bloom"] = bl

    # Sorular (madde analizi, tek öğrenci)
    maddeler = {}
    for c in cevaplar:
        anahtar = (c.get("vaka") or "") + "|" + (c.get("dugum") or "") + "|" + str(c.get("soru") or "")
        m = maddeler.setdefault(anahtar, {"soru": c.get("soru"), "vaka": c.get("vaka"), "dugum": c.get("dugum"),
                                          "hedef": c.get("hedef"), "bloom": c.get("bloom"), "tur": c.get("tur"),
                                          "deneme": 0, "puan": 0.0, "en": 0.0, "ipucu": 0, "ilk": None})
        m["deneme"] += 1
        m["puan"] += c.get("puan", 0)
        m["en"] += c.get("en_yuksek", 1)
        m["ipucu"] += int(c.get("ipucu") or 0)
        if m["ilk"] is None:
            m["ilk"] = c.get("puan", 0) >= c.get("en_yuksek", 1)
    madde_listesi = []
    for m in maddeler.values():
        p = oran(m["puan"], m["en"])
        madde_listesi.append({k: m[k] for k in ("soru", "vaka", "dugum", "hedef", "bloom", "tur", "deneme", "ipucu")
                              if m[k] not in (None, "")} | {"p": p, "gucluk": gucluk(p), "ilk_denemede_tam": m["ilk"]})
    out["sorular"] = sorted(madde_listesi, key=lambda x: (x["p"] if x["p"] is not None else 2))

    # Rubrikte eksik kalan ölçütler
    eksik = {}
    for c in cevaplar:
        for o in c.get("eksik_olcutler") or []:
            anahtar = "%s · %s" % (c.get("dugum") or c.get("soru") or "?", o)
            eksik[anahtar] = eksik.get(anahtar, 0) + 1
    out["eksik_olcutler"] = sorted(eksik.items(), key=lambda x: -x[1])[:8]

    out["tehlikeli_secimler"] = [{"vaka": c.get("vaka"), "dugum": c.get("dugum"), "soru": c.get("soru"),
                                  "tarih": c.get("tarih")} for c in cevaplar if c.get("tehlikeli")]
    out["vakalar"] = kayit.get("vakalar") or []

    # Güçlü ve geliştirilecek hedefler (en az iki cevaba dayanarak)
    out["guclu"] = [h["id"] for h in hed if h["cevap"] >= 2 and (h["oran"] or 0) >= 0.8]
    out["gelistirilecek"] = [h["id"] for h in hed if h["cevap"] >= 1 and h["oran"] is not None and h["oran"] < 0.6]
    out["tekrar_zamani_gelen"] = sorted(h["id"] for h in hed if h["sonraki_tekrar"] and bugun and h["sonraki_tekrar"] <= bugun)
    out["yoklanmayan"] = [h["id"] for h in hed if not h["cevap"]]
    return out


def markdown(k, ders_basligi=None, tarih=None):
    y = ["# Karne — %s" % (ders_basligi or k.get("ders")), "",
         "Öğrenci: %s · Tarih: %s · Cevaplanan soru/vaka adımı: %d · Genel başarı: %s" % (
             k.get("ogrenci"), tarih or "-", k["cevap_sayisi"], yuzde(k["genel_oran"])), "",
         "> Bu karne not için değildir. Yalnız senin bilgisayarında durur ve hiçbir yere gönderilmez. "
         "Amacı, hangi hedefte güçlü olduğunu ve neyi tekrar etmen gerektiğini göstermektir.", ""]
    if k.get("deneme"):
        y += ["> **DENEME KAYDI:** bu bir öğretmen denemesidir; araştırma verisine katılmaz.", ""]
    if k["gelistirilecek"] or k["tekrar_zamani_gelen"]:
        y += ["## Sıradaki adımın", ""]
        if k["tekrar_zamani_gelen"]:
            y.append("- Tekrar zamanı gelen hedefler: " + ", ".join(k["tekrar_zamani_gelen"]))
        if k["gelistirilecek"]:
            y.append("- Geliştirilecek hedefler (başarı %60'ın altında): " + ", ".join(k["gelistirilecek"]))
        if k["yoklanmayan"]:
            y.append("- Henüz yoklanmayan hedefler: " + ", ".join(k["yoklanmayan"]))
        y.append("")
    y += ["## Hedefler", "", "| Hedef | Hedef düzey | Cevap | Başarı | İlk denemede tam | Durum | Sonraki tekrar |",
          "| --- | --- | --- | --- | --- | --- | --- |"]
    for h in k["hedefler"]:
        y.append("| %s %s | %s | %d | %s | %s | %s | %s |" % (
            h["id"], h.get("baslik") or "", BLOOM_AD.get(h.get("hedef_bloom"), "-"), h["cevap"], yuzde(h["oran"]),
            yuzde(h["ilk_deneme_dogru"]), DURUM_AD.get(h["durum"], h["durum"]), h.get("sonraki_tekrar") or "-"))
    if k["bloom"]:
        y += ["", "## Düşünme düzeyine göre (Bloom)", ""] + bloom_tablosu(k["bloom"])
        y += ["", "Üst düzeylerde (çözümle, değerlendir, oluştur) başarı alt düzeylerden belirgin düşükse, bilgiyi "
              "biliyor ama vakaya uygulamakta zorlanıyorsun demektir: vaka çalışmasına ağırlık ver."]
    if k["sorular"]:
        y += ["", "## Soru güçlüğü (senin cevaplarına göre)", "",
              "| Soru | Tür | Hedef | Bloom | Deneme | Başarı (p) | Güçlük | İpucu |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
        for m in k["sorular"][:20]:
            ad = ("%s / %s" % (m["vaka"], m.get("dugum", ""))) if m.get("vaka") else str(m.get("soru", ""))[:70]
            y.append("| %s | %s | %s | %s | %d | %s | %s | %d |" % (
                ad, TUR_AD.get(m.get("tur"), m.get("tur") or "-"), m.get("hedef", "-"), BLOOM_AD.get(m.get("bloom"), "-"),
                m["deneme"], "-" if m["p"] is None else "%.2f" % m["p"], m["gucluk"], m.get("ipucu", 0)))
        y += ["", "p: o sorudaki ortalama başarın (1 = hep tam). Tek kişinin verisi olduğu için sorunun kendisinin "
              "zorluğunu değil, senin için zorluğunu gösterir."]
    if k["eksik_olcutler"]:
        y += ["", "## Açık uçlu cevaplarda en sık eksik kalanlar", ""]
        for o, n in k["eksik_olcutler"]:
            y.append("- %s (%d kez)" % (o, n))
    if k["vakalar"]:
        y += ["", "## Vakalar", "", "| Tarih | Vaka | Sonuç | Yeniden anlatılan bölümler |", "| --- | --- | --- | --- |"]
        for v in k["vakalar"]:
            y.append("| %s | %s | %s | %s |" % (v.get("tarih", "-"), v.get("vaka", "-"), SONUC_AD.get(v.get("sonuc"), v.get("sonuc", "-")),
                                               ", ".join(v.get("yeniden_anlatilan_bolumler") or []) or "-"))
    if k["tehlikeli_secimler"]:
        y += ["", "## Dikkat: hastaya zarar verebilecek seçimler", ""]
        for t in k["tehlikeli_secimler"]:
            y.append("- %s / %s (%s)" % (t.get("vaka") or "-", t.get("dugum") or t.get("soru") or "-", t.get("tarih") or "-"))
    return "\n".join(y) + "\n"
