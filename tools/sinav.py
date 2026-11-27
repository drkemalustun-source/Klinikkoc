"""Nilgün'ün sınavı: plan denetimi, uyarlamalı soru sırası, ölçütle puanlama ve sonuç.

Kurallar (Kemal Üstün, 27 Kasım 2026):
- Sınav planı dersin hedeflerinden kurulur; her hedef en az bir kez sorulur (kapsam sabit).
- Güçlük değişir: hedef düzeyindeki cevap tamsa üst düzey soruya çıkılır (yalnız tam sınavda) ya da sıradaki hedefe
  geçilir; eksikse alt düzey soruya inilir. Alt düzey soru ipucu değil, yeni bir sorudur.
- Cevap anahtarı ve ölçütler sınav başlamadan kaydedilir; sınav sırasında değişmez.
- Puanı program hesaplar: eğitmen her ölçüt için yalnız "karşılandı / karşılanmadı" der.
  Hedef başına: hedef düzeyinde tam cevap 2; kısmen ya da yalnız alt düzeyde tam 1; hiçbiri 0.
  Üst düzey soru puanı değiştirmez; raporda "hedefin üstünde" diye görünür.
- Dayanağı zayıf olan soru sınava girmez; pilot ölçme sorularına benzeyen soru da girmez.

Yalnız Python'un kendi kitaplığını kullanır; dosya okumaz, yazmaz (o iş tahta-mcp.py'de).
"""
import difflib
import math
import re

TUR = "klinikkoc-sinav"
SURUM = 1
DUZEYLER = ("hedef", "alt", "ust")
DUZEY_AD = {"hedef": "hedef düzeyi", "alt": "alt düzey", "ust": "üst düzey"}
SURELER = ("kisa", "tam")
GUVEN = ("tahmin", "biraz", "emin")
KISA_HEDEF = 6          # kısa sınavda sorulan hedef sayısı (yaklaşık 15 dakika)
EN_COK_OLCUT = 8
OLCME_BENZERLIK = 0.80  # pilot ölçme sorusuna bu kadar benzeyen soru reddedilir
ONAYLI_BENZERLIK = 0.90  # öğretmenin onayladığı soruyla bu kadar örtüşen soru "öğretmen sorusu" sayılır
# Anahtar maddesinin kaynaktaki dayanağı: "yok" olan soru hiçbir zaman sınava girmez. "zayif" olan soru da girmez
# (Kemal Üstün'ün kararı, 27 Kasım 2026). ZAYIF_KABUL True yapılırsa "zayif" soru sınava girer ama raporda
# "program doğrulayamadı" diye işaretlenir (dayanak eşikleri ölçülene kadar düşünülen seçenek).
ZAYIF_KABUL = False


def anahtar(ders, hedef):
    return "%s/%s" % (ders, hedef)


def duz(s):
    """Karşılaştırma için sadeleştirir: küçük harf (Türkçe i/ı), noktalama yok, tek boşluk."""
    s = (s or "").replace("İ", "i").replace("I", "ı").lower()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)).strip()


def benzerlik(a, b):
    a, b = duz(a), duz(b)
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def tam_icin_varsayilan(olcutler):
    """Tam cevap için karşılanması gereken en az ölçüt sayısı: ölçütlerin üçte ikisi, zorunlulardan az olamaz."""
    n = len(olcutler)
    z = sum(1 for o in olcutler if o.get("zorunlu"))
    return max(1, z, int(math.ceil(2 * n / 3.0)))


def kisa_secim(hedefler, oncelik=None, ikincil=None, adet=KISA_HEDEF):
    """Kısa sınav için hedef seçer. Önce öncelikli hedefler (zayıf kalan, tekrar zamanı gelen) sırasıyla alınır;
    kalan yer önce ikincil hedeflerden (hiç yoklanmamış), sonra ötekilerden, dersin sırasına eşit aralıklarla
    yayılarak doldurulur. Seçilenler dersin sırasıyla döner."""
    if len(hedefler) <= adet:
        return list(hedefler)
    hepsi = [anahtar(h["ders"], h["id"]) for h in hedefler]
    secili = []
    for a in oncelik or []:
        if a in hepsi and a not in secili and len(secili) < adet:
            secili.append(a)

    def yay(havuz):
        havuz = [a for a in havuz if a not in secili]
        eksik = adet - len(secili)
        if eksik <= 0 or not havuz:
            return
        if len(havuz) <= eksik:
            secili.extend(havuz)
            return
        adim = len(havuz) / float(eksik)
        for i in range(eksik):
            a = havuz[int(i * adim)]
            if a not in secili:
                secili.append(a)

    yay([a for a in hepsi if a in set(ikincil or [])])
    yay(hepsi)
    return [h for h in hedefler if anahtar(h["ders"], h["id"]) in secili]


# ---------- Plan denetimi ----------
def plan_denetle(sorular, hedefler, sayfa_sayisi=None, onayli=None, olcme=None, dayanak_fn=None, cikarilan=None):
    """Nilgün'ün hazırladığı soruları denetler.

    sorular: [{ders, hedef, duzey, soru, anahtar: [{madde, sayfa}], olcutler: [{metin, zorunlu}], tam_icin?, bloom?}]
    hedefler: sınavda sorulacak hedefler [{ders, id, baslik, bloom}] (sıralı)
    sayfa_sayisi: {ders: kaynağın sayfa sayısı ya da None}
    onayli / olcme: {ders: [soru metni, ...]}  (öğretmenin onayladığı sorular / pilot ölçme soruları)
    dayanak_fn(ders, metin) -> (etiket, [sayfalar]); None ise dayanak denetlenmez
    cikarilan: [{ders, hedef, neden}]  (kaynakta dayanak bulunamadığı için sorulamayan hedefler)

    Döner: {sorular, reddedilen, eksik_hedefler, uyarilar, cikarilan}. eksik_hedefler boşsa plan kaydedilebilir.
    """
    sayfa_sayisi, onayli, olcme = sayfa_sayisi or {}, onayli or {}, olcme or {}
    gecerli = {anahtar(h["ders"], h["id"]): h for h in hedefler}
    cik = {}
    for c in cikarilan or []:
        a = anahtar(c.get("ders"), c.get("hedef"))
        if a in gecerli and (c.get("neden") or "").strip():
            cik[a] = {"ders": c["ders"], "hedef": c["hedef"], "neden": c["neden"].strip()}
    kabul, ret, uyari, gorulen = [], [], [], set()
    for sira, s in enumerate(sorular or [], 1):
        neden = []
        ders, hedef, duzey = s.get("ders"), s.get("hedef"), s.get("duzey")
        a = anahtar(ders, hedef)
        h = gecerli.get(a)
        if not h:
            neden.append("Bu hedef sınav planında yok: %s" % a)
        if duzey not in DUZEYLER:
            neden.append("duzey 'hedef', 'alt' ya da 'ust' olmalı")
        metin = (s.get("soru") or "").strip()
        if len(metin) < 10:
            neden.append("Soru metni yok ya da çok kısa")
        if (a, duzey) in gorulen:
            neden.append("Bu hedef ve düzey için zaten bir soru var")
        # ölçütler
        olcutler = []
        for i, o in enumerate(s.get("olcutler") or [], 1):
            om = (o.get("metin") if isinstance(o, dict) else str(o or "")).strip()
            if om:
                olcutler.append({"id": "o%d" % i, "metin": om, "zorunlu": bool(isinstance(o, dict) and o.get("zorunlu"))})
        if not olcutler:
            neden.append("En az bir ölçüt gerekli")
        if len(olcutler) > EN_COK_OLCUT:
            neden.append("En çok %d ölçüt olabilir" % EN_COK_OLCUT)
        z = sum(1 for o in olcutler if o["zorunlu"])
        tam = s.get("tam_icin")
        if tam is None:
            tam = tam_icin_varsayilan(olcutler) if olcutler else 1
        elif not isinstance(tam, int) or isinstance(tam, bool) or not max(1, z) <= tam <= max(1, len(olcutler)):
            neden.append("tam_icin, zorunlu ölçüt sayısı (%d) ile ölçüt sayısı (%d) arasında olmalı" % (max(1, z), len(olcutler)))
        # cevap anahtarı
        maddeler = []
        n_sayfa = sayfa_sayisi.get(ders)
        for m in s.get("anahtar") or []:
            mm = (m.get("madde") if isinstance(m, dict) else str(m or "")).strip()
            if not mm:
                continue
            sayfa = m.get("sayfa") if isinstance(m, dict) else None
            if n_sayfa:
                if not isinstance(sayfa, int) or isinstance(sayfa, bool) or not 1 <= sayfa <= n_sayfa:
                    neden.append("Anahtar maddesinin sayfası yok ya da kaynağın dışında (1–%d): %s" % (n_sayfa, mm[:60]))
            elif sayfa is not None and not isinstance(sayfa, int):
                sayfa = None
            maddeler.append({"madde": mm, "sayfa": sayfa})
        if not maddeler:
            neden.append("Cevap anahtarı yok")
        # pilot ölçme soruları Nilgün'e kapalıdır
        if metin and any(benzerlik(metin, x) >= OLCME_BENZERLIK for x in olcme.get(ders) or []):
            neden.append("Soru bir pilot ölçme sorusuna çok benziyor; ölçme soruları sınavda kullanılmaz")
        kaynak = "ogretmen" if metin and any(benzerlik(metin, x) >= ONAYLI_BENZERLIK for x in onayli.get(ders) or []) \
            else "nilgun"
        dayanak = None
        if not neden and kaynak == "nilgun" and dayanak_fn:
            yok, zayif = [], []
            for m in maddeler:
                etiket, sayfalar = dayanak_fn(ders, m["madde"])
                yakin = ("; en yakın sayfalar: %s" % ", ".join(str(x) for x in sayfalar[:3])) if sayfalar else ""
                if etiket == "yok":
                    yok.append(m["madde"][:70] + yakin)
                elif etiket != "guclu":
                    zayif.append(m["madde"][:70] + yakin)
                elif m["sayfa"] and sayfalar and m["sayfa"] not in sayfalar:
                    uyari.append("%s %s: '%s' maddesi için yazılan sayfa (%s) aramanın bulduğu sayfalarla (%s) uyuşmuyor; "
                                 "denetle." % (a, duzey, m["madde"][:50], m["sayfa"], ", ".join(str(x) for x in sayfalar[:3])))
            if yok:
                neden.append("Anahtarın şu maddeleri kaynakta bulunamadı; kaynakta yazmayan şey sorulmaz: " + " | ".join(yok))
            elif zayif and not ZAYIF_KABUL:
                neden.append("Anahtarın kaynakta dayanağı zayıf; maddeyi kaynağın sözleriyle yeniden yaz ya da soruyu "
                             "değiştir: " + " | ".join(zayif))
            else:
                dayanak = "zayif" if zayif else "guclu"
        if neden:
            ret.append({"sira": sira, "ders": ders, "hedef": hedef, "duzey": duzey, "nedenler": neden})
            continue
        gorulen.add((a, duzey))
        kabul.append({"ders": ders, "hedef": hedef, "duzey": duzey, "bloom": s.get("bloom") or (h or {}).get("bloom"),
                      "soru": metin, "anahtar": maddeler, "olcutler": olcutler, "tam_icin": tam, "kaynak": kaynak,
                      "dayanak": dayanak})
    eksik = []
    for a, h in gecerli.items():
        if a in cik:
            continue
        if (a, "hedef") not in gorulen:
            eksik.append({"ders": h["ders"], "hedef": h["id"], "baslik": h.get("baslik"), "bloom": h.get("bloom"),
                          "eksik": "hedef düzeyinde kabul edilmiş soru yok"})
        elif (a, "alt") not in gorulen:
            uyari.append("%s: alt düzey sorusu yok; cevap eksik kalırsa inilecek soru olmayacak." % a)
    # çıkarılan hedefin soruları sınava girmez
    kabul = [q for q in kabul if anahtar(q["ders"], q["hedef"]) not in cik]
    for no, q in enumerate(kabul, 1):
        q["no"] = no
    return {"sorular": kabul, "reddedilen": ret, "eksik_hedefler": eksik, "uyarilar": uyari, "cikarilan": list(cik.values())}


# ---------- Sınavın akışı ----------
def _dizin(s):
    return {(q["ders"], q["hedef"], q["duzey"]): q for q in s.get("sorular") or []}


def _cevaplar(s):
    return {c["no"]: c for c in s.get("cevaplar") or []}


def sorulan_hedefler(s):
    cik = {anahtar(c["ders"], c["hedef"]) for c in s.get("cikarilan") or []}
    return [h for h in s.get("hedefler") or [] if anahtar(h["ders"], h["id"]) not in cik]


def sonraki(s):
    """Sorulacak sıradaki soru ya da None (sınav bitti)."""
    d, c = _dizin(s), _cevaplar(s)
    for h in sorulan_hedefler(s):
        qh = d.get((h["ders"], h["id"], "hedef"))
        if not qh:
            continue
        if qh["no"] not in c:
            return qh
        if c[qh["no"]]["sonuc"] == "tam":
            qu = d.get((h["ders"], h["id"], "ust"))
            if qu and s.get("sure") == "tam" and qu["no"] not in c:
                return qu
        else:
            qa = d.get((h["ders"], h["id"], "alt"))
            if qa and qa["no"] not in c:
                return qa
    return None


def hedef_sirasi(s, q):
    """(kaçıncı hedef, toplam hedef) — tahtadaki 'Hedef 3 / 12' sayacı için."""
    hs = sorulan_hedefler(s)
    for i, h in enumerate(hs, 1):
        if h["ders"] == q["ders"] and h["id"] == q["hedef"]:
            return i, len(hs)
    return len(hs), len(hs)


def degerlendir(q, karsilanan):
    """Ölçütlerden sonuç: 'tam' (bütün zorunlular ve en az tam_icin ölçüt), 'kismi' (en az bir ölçüt) ya da 'yok'."""
    idler = {o["id"] for o in q["olcutler"]}
    k = set(karsilanan or []) & idler
    zorunlu = {o["id"] for o in q["olcutler"] if o.get("zorunlu")}
    if zorunlu <= k and len(k) >= q.get("tam_icin", len(idler)):
        return "tam"
    return "kismi" if k else "yok"


def cevap_isle(s, no, karsilanan, guven=None, ham=None, saat=None):
    """Sıradaki sorunun cevabını işler. Sıra dışı soru ya da bilinmeyen ölçüt ValueError verir."""
    bekleyen = sonraki(s)
    if bekleyen is None:
        raise ValueError("Sınavda sorulacak soru kalmadı; sinav_bitir çağır.")
    if no != bekleyen["no"]:
        raise ValueError("Sıradaki soru %d numaralı soru; önce onu sor." % bekleyen["no"])
    idler = {o["id"] for o in bekleyen["olcutler"]}
    bilinmeyen = [x for x in karsilanan or [] if x not in idler]
    if bilinmeyen:
        raise ValueError("Bu soruda böyle ölçüt yok: %s (ölçütler: %s)" % (", ".join(map(str, bilinmeyen)),
                                                                          ", ".join(sorted(idler))))
    if guven is not None and guven not in GUVEN:
        raise ValueError("guven tahmin, biraz ya da emin olmalı")
    k = [o["id"] for o in bekleyen["olcutler"] if o["id"] in set(karsilanan or [])]
    c = {"no": no, "karsilanan": k, "sonuc": degerlendir(bekleyen, k), "guven": guven, "ham": (ham or "").strip()}
    if saat:
        c["saat"] = saat
    s.setdefault("cevaplar", []).append(c)
    return c


# ---------- Sonuç ----------
def hedef_puani(s, h):
    """Hedefin puanı (0, 1, 2) ya da None (hedef düzeyindeki soru henüz cevaplanmadı)."""
    d, c = _dizin(s), _cevaplar(s)
    qh = d.get((h["ders"], h["id"], "hedef"))
    if not qh or qh["no"] not in c:
        return None
    son = c[qh["no"]]["sonuc"]
    if son == "tam":
        return 2
    if son == "kismi":
        return 1
    qa = d.get((h["ders"], h["id"], "alt"))
    return 1 if qa and qa["no"] in c and c[qa["no"]]["sonuc"] == "tam" else 0


def sonuc(s):
    """Sınavın sonucu: puan, hedef başına durum, soru başına beklenen cevap ve ölçütler, emin ama yanlışlar."""
    d, c = _dizin(s), _cevaplar(s)
    hedefler, toplam, en_yuksek = [], 0, 0
    for h in sorulan_hedefler(s):
        p = hedef_puani(s, h)
        qu = d.get((h["ders"], h["id"], "ust"))
        x = {"ders": h["ders"], "hedef": h["id"], "baslik": h.get("baslik"), "bloom": h.get("bloom"), "puan": p,
             "hedefin_ustunde": bool(qu and qu["no"] in c and c[qu["no"]]["sonuc"] == "tam")}
        if p is not None:
            toplam += p
            en_yuksek += 2
        hedefler.append(x)
    sorular = []
    for q in s.get("sorular") or []:
        if q["no"] not in c:
            continue
        cv = c[q["no"]]
        k = set(cv["karsilanan"])
        sorular.append({
            "no": q["no"], "ders": q["ders"], "hedef": q["hedef"], "duzey": q["duzey"], "soru": q["soru"],
            "cevap": cv.get("ham"), "sonuc": cv["sonuc"], "guven": cv.get("guven"),
            "beklenen": q["anahtar"],
            "dayanak": q.get("dayanak"),
            "karsilanan_olcutler": [o["metin"] for o in q["olcutler"] if o["id"] in k],
            "eksik_olcutler": [o["metin"] + (" (zorunlu)" if o.get("zorunlu") else "") for o in q["olcutler"] if o["id"] not in k],
            "emin_ama_yanlis": cv.get("guven") == "emin" and cv["sonuc"] != "tam"})
    yuzde = int(round(100.0 * toplam / en_yuksek)) if en_yuksek else None
    cevaplanan = [h for h in hedefler if h["puan"] is not None]
    out = {"puan": toplam, "en_yuksek": en_yuksek, "yuzde": yuzde, "hedefler": hedefler, "sorular": sorular,
           "guclu_hedefler": [h for h in cevaplanan if h["puan"] == 2],
           "zayif_hedefler": [h for h in cevaplanan if h["puan"] < 2],
           "sorulmayan_hedefler": [h for h in hedefler if h["puan"] is None],
           "cikarilan_hedefler": s.get("cikarilan") or [],
           "emin_ama_yanlis": [x for x in sorular if x["emin_ama_yanlis"]],
           "tamamlandi": sonraki(s) is None}
    tahmin = s.get("tahmin")
    if isinstance(tahmin, (int, float)) and not isinstance(tahmin, bool) and yuzde is not None:
        out["tahmin"] = {"beklenen": int(tahmin), "gercek": yuzde, "fark": yuzde - int(tahmin)}
    return out


def karsilastir(simdi, onceki):
    """Öğrencinin kendi önceki sınavıyla karşılaştırma (yalnız iki sınavda da sorulan hedefler)."""
    if not onceki:
        return None
    eski = {anahtar(h["ders"], h["hedef"]): h["puan"] for h in onceki.get("hedefler") or [] if h.get("puan") is not None}
    ilerleyen, gerileyen = [], []
    for h in simdi.get("hedefler") or []:
        a = anahtar(h["ders"], h["hedef"])
        if h.get("puan") is None or a not in eski:
            continue
        if h["puan"] > eski[a]:
            ilerleyen.append(a)
        elif h["puan"] < eski[a]:
            gerileyen.append(a)
    return {"onceki_yuzde": onceki.get("yuzde"), "onceki_tarih": onceki.get("tarih"), "simdiki_yuzde": simdi.get("yuzde"),
            "ilerleyen_hedefler": ilerleyen, "gerileyen_hedefler": gerileyen}


def rapor_md(s, r, adlar=None, karsilastirma=None, tavsiye=None):
    """Öğrencinin kendi bilgisayarında kalan sınav raporu (Markdown)."""
    adlar = adlar or {}
    y = ["# Sözlü sınav raporu — Nilgün", "",
         "Tarih: %s · Süre: %s · Dersler: %s" % (s.get("tarih") or "", "kısa" if s.get("sure") == "kisa" else "tam",
                                                 ", ".join(adlar.get(x, x) for x in s.get("dersler") or [])),
         "", "Bu sınav not için değildir. Sonuç yalnız bu bilgisayarda durur; kimseye gönderilmedi.", ""]
    if not r["tamamlandi"]:
        y += ["> Sınav yarıda bırakıldı; puan yalnız cevaplanan hedeflerden hesaplandı.", ""]
    if r["yuzde"] is not None:
        y += ["## Puan", "", "**%d / 100** (%d hedefte %d / %d puan)" % (r["yuzde"], r["en_yuksek"] // 2, r["puan"], r["en_yuksek"])]
        if r.get("tahmin"):
            t = r["tahmin"]
            y.append("Beklediğin: %d · Aldığın: %d · Fark: %+d" % (t["beklenen"], t["gercek"], t["fark"]))
        y.append("")
    if karsilastirma:
        y += ["Önceki sınavın (%s): %s / 100. İlerleyen hedef: %d, gerileyen hedef: %d." % (
            karsilastirma.get("onceki_tarih") or "-", karsilastirma.get("onceki_yuzde"),
            len(karsilastirma["ilerleyen_hedefler"]), len(karsilastirma["gerileyen_hedefler"])), ""]
    if r["emin_ama_yanlis"]:
        y += ["## Emin olduğun ama eksik kalan cevaplar", ""]
        for x in r["emin_ama_yanlis"]:
            y.append("- %s: %s" % (x["hedef"], x["soru"]))
        y.append("")
    y += ["## Hedefler", "", "| Hedef | Düzey | Puan | Not |", "| --- | --- | --- | --- |"]
    for h in r["hedefler"]:
        y.append("| %s %s | %s | %s | %s |" % (h["hedef"], h.get("baslik") or "", h.get("bloom") or "-",
                                             "-" if h["puan"] is None else "%d / 2" % h["puan"],
                                             "hedefin üstünde" if h["hedefin_ustunde"] else
                                             ("sorulmadı" if h["puan"] is None else "")))
    for c in r["cikarilan_hedefler"]:
        y.append("| %s | - | - | sorulamadı: %s |" % (c["hedef"], c["neden"]))
    y += ["", "## Sorular", ""]
    for x in r["sorular"]:
        y += ["### %d. %s (%s, %s)" % (x["no"], x["soru"], x["hedef"], DUZEY_AD[x["duzey"]]), "",
              "Cevabın: %s" % (x["cevap"] or "(boş)"), "",
              "Sonuç: %s%s" % ({"tam": "tam", "kismi": "kısmen", "yok": "karşılanmadı"}[x["sonuc"]],
                              (" · güven: %s" % x["guven"]) if x.get("guven") else ""), "", "Beklenen cevap:"]
        y += ["- %s%s" % (m["madde"], (" (s. %s)" % m["sayfa"]) if m.get("sayfa") else "") for m in x["beklenen"]]
        if x.get("dayanak") == "zayif":
            y += ["", "_Program bu sorunun cevap anahtarını kaynakta doğrulayamadı; yazılan sayfaya kendin de bak._"]
        if x["karsilanan_olcutler"]:
            y += ["", "Karşılanan ölçütler: " + "; ".join(x["karsilanan_olcutler"])]
        if x["eksik_olcutler"]:
            y += ["", "Eksik ölçütler: " + "; ".join(x["eksik_olcutler"])]
        y.append("")
    if tavsiye:
        y += ["## Çalışma tavsiyesi", "", tavsiye.strip(), ""]
    return "\n".join(y)
