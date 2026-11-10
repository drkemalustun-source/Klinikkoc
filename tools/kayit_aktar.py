#!/usr/bin/env python3
"""Öğrenci kayıtlarını dışa ve içe aktarma (yalnız bu bilgisayarda; hiçbir yere gönderilmez).

Öğrenci (kendi kaydı):
  python tools/kayit_aktar.py liste
  python tools/kayit_aktar.py disa  --ogrenci <kimlik ya da ad> [--cikti dosya.json]
      Bütün dersleri, raporları ve karneleri TEK dosyada toplar (varsayılan: masaüstü).
  python tools/kayit_aktar.py ice   <dosya.json> [--uzerine]
      Başka bilgisayarda aynı dosyayı içe alır. Buradaki kayıt daha yeniyse ona dokunmaz
      (--uzerine ile yine de yazar; eskisi yedekler/ klasöründe kalır).

Öğretmen (araştırma, anonim):
  python tools/kayit_aktar.py anonim --hepsi | --ogrenci k1 k2 ... | --dosya a.json b.json  [--deneme-dahil] [--cikti x.json]
      Seçilen öğrencilerin kayıtlarını kimlik bilgisi OLMADAN tek dosyada toplar: ad, kimlik, ayırt edici,
      serbest metinler (kanıt özetleri, öğrencinin soruları, yanıt özetleri, oturum özetleri) çıkarılır;
      öğrenciye rastgele bir kod verilir; tarihler öğrencinin ilk kaydından bu yana geçen güne çevrilir
      (belgeler/anonimlestirme.md: tam tarih yok, göreli süre). Deneme kayıtları varsayılan olarak dışarıda kalır.
      Öğrencilerin kendi dışa aktardığı dosyalar --dosya ile içe almadan anonimleştirilebilir.

Kayıt yeri KLINIK_KOC_KAYIT ile değiştirilebilir (bkz. veri_yeri.py).
"""
import argparse
import json
import os
import re
import secrets
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kayit_deposu as kd  # noqa: E402
import veri_yeri  # noqa: E402

TUR = "klinikkoc-ogrenci-kaydi"
ANONIM_TUR = "klinikkoc-anonim-kayitlar"
SURUM = 1
METIN_KLASORLERI = ("raporlar", "karneler")


def varsayilan_depo():
    kok = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return kd.Depo(veri_yeri.kayit_kok(), None if veri_yeri.kayit_ortamdan_mi() else os.path.join(kok, "kayitlar"))


# ---------- Öğrenci: tek dosya ----------
def paket(depo, ogrenci):
    kimlik = depo.coz(ogrenci)
    klasor = depo.klasor(kimlik)
    if not os.path.isdir(klasor):
        raise kd.KayitHatasi("Bu öğrencinin kaydı yok: %s" % ogrenci)
    bilgi = depo.bilgi(kimlik)
    dersler, uyarilar = {}, []
    for ders in bilgi["dersler"]:
        k, u = depo.yukle(kimlik, ders)
        uyarilar += u
        if k:
            dersler[ders] = k
    dosyalar = {}
    for alt in METIN_KLASORLERI:
        ak = os.path.join(klasor, alt)
        if os.path.isdir(ak):
            for ad in sorted(os.listdir(ak)):
                if ad.endswith(".md"):
                    with open(os.path.join(ak, ad), encoding="utf-8") as f:
                        dosyalar[alt + "/" + ad] = f.read()
    return {"tur": TUR, "surum": SURUM, "olusturma": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "aciklama": "KlinikKoç öğrenci kaydı. Yalnız öğrencinin isteğiyle paylaşılır.",
            "ogrenci": {"kimlik": kimlik, "ad": bilgi["ad"], "ayirt": bilgi["ayirt"], "deneme": bilgi["deneme"]},
            "dersler": dersler, "dosyalar": dosyalar}, uyarilar


def disa_aktar(depo, ogrenci, cikti=None):
    p, uyarilar = paket(depo, ogrenci)
    if not cikti:
        cikti = os.path.join(veri_yeri.masaustu(), "KlinikKoc-kayit-%s-%s.json" % (
            p["ogrenci"]["kimlik"], time.strftime("%Y-%m-%d")))
    elif os.path.isdir(cikti):
        cikti = os.path.join(cikti, "KlinikKoc-kayit-%s-%s.json" % (p["ogrenci"]["kimlik"], time.strftime("%Y-%m-%d")))
    kd.atomik_yaz(cikti, p, yedekle=False)
    return {"dosya": os.path.abspath(cikti), "kimlik": p["ogrenci"]["kimlik"], "dersler": sorted(p["dersler"]),
            "rapor_karne": len(p["dosyalar"]), "uyarilar": uyarilar}


def paket_oku(yol):
    with open(yol, encoding="utf-8") as f:
        p = json.load(f)
    if not isinstance(p, dict) or p.get("tur") != TUR:
        raise kd.KayitHatasi("Bu bir KlinikKoç öğrenci kaydı dosyası değil: %s" % yol)
    if int(p.get("surum") or 0) > SURUM:
        raise kd.KayitHatasi("Dosya daha yeni bir sürümle yazılmış; programı güncelleyin.")
    return p


def ice_aktar(depo, yol, uzerine=False):
    p = paket_oku(yol)
    o = p.get("ogrenci") or {}
    kimlik = o.get("kimlik")
    depo.klasor(kimlik)  # kimlik denetimi
    defter = depo.defter()
    var = defter["ogrenciler"].get(kimlik)
    if var and kd.ad_anahtari(var.get("ad")) != kd.ad_anahtari(o.get("ad")):
        raise kd.KayitHatasi("Bu bilgisayarda aynı kimlikle başka bir öğrenci (%s) var; içe aktarılmadı." % var.get("ad"))
    if not var:
        defter["ogrenciler"][kimlik] = {"ad": o.get("ad") or kimlik, "ayirt": o.get("ayirt"),
                                        "olusturma": time.strftime("%Y-%m-%d"), "deneme": bool(o.get("deneme")),
                                        "ice_aktarildi": time.strftime("%Y-%m-%d")}
        if not o.get("ayirt"):
            defter["ogrenciler"][kimlik]["eski_kayit"] = True
        depo._defteri_yaz(defter)
    alinan, atlanan = [], []
    for ders, k in sorted((p.get("dersler") or {}).items()):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,80}", ders or ""):
            atlanan.append({"ders": ders, "neden": "geçersiz ders adı"})
            continue
        mevcut, _ = depo.yukle(kimlik, ders)
        if mevcut and not uzerine and (mevcut.get("guncelleme") or "") >= (k.get("guncelleme") or ""):
            atlanan.append({"ders": ders, "neden": "bu bilgisayardaki kayıt aynı ya da daha yeni"})
            continue
        guncelleme = k.get("guncelleme")
        depo.yaz(kimlik, ders, k)  # eski sürüm yedekler/ içinde kalır
        if guncelleme:  # içe alınan kaydın zamanı korunur
            yol_ = depo.kayit_yolu(kimlik, ders)
            k2, _ = kd.guvenli_oku(yol_)
            k2["guncelleme"] = guncelleme
            kd.atomik_yaz(yol_, k2, yedekle=False)
        alinan.append(ders)
    yazilan = 0
    for goreli, metin in (p.get("dosyalar") or {}).items():
        alt, _, ad = goreli.partition("/")
        if alt not in METIN_KLASORLERI or not ad or "/" in ad or "\\" in ad or ad.startswith("."):
            continue
        hedef = os.path.join(depo.klasor(kimlik), alt, ad)
        if not os.path.exists(hedef):
            depo.metin_yaz(kimlik, alt, ad, metin)
            yazilan += 1
    return {"kimlik": kimlik, "ad": o.get("ad"), "alinan_dersler": alinan, "atlanan": atlanan,
            "rapor_karne": yazilan, "kayit_klasoru": depo.klasor(kimlik)}


# ---------- Öğretmen: anonim toplu aktarma ----------
def _gun(baslangic, tarih):
    if not baslangic or not tarih:
        return None
    try:
        a = time.mktime(time.strptime(baslangic[:10], "%Y-%m-%d"))
        b = time.mktime(time.strptime(tarih[:10], "%Y-%m-%d"))
    except ValueError:
        return None
    return int(round((b - a) / 86400))


def _sec(d, alanlar):
    return {a: d[a] for a in alanlar if a in d and d[a] is not None}


def _tarihler(k):
    t = [k.get("olusturma")]
    for liste in ("guven", "sorular", "testler", "cevaplar", "vakalar", "oturumlar"):
        t += [x.get("tarih") for x in k.get(liste) or [] if isinstance(x, dict)]
    return [x for x in t if isinstance(x, str) and len(x) >= 10]


def anonim_ders(k, baslangic, ham_yanitlar=False):
    g = lambda t: _gun(baslangic, t)  # noqa: E731
    hedefler = {}
    for hid, v in (k.get("hedefler") or {}).items():
        h = _sec(v, ("yardimsiz_duzey", "destekle_duzey", "durum", "kutu"))
        h["kanit_sayisi"] = len(v.get("kanitlar") or [])
        if v.get("son"):
            h["son_gun"] = g(v["son"])
        hedefler[hid] = h
    testler = []
    for t in k.get("testler") or []:
        x = _sec(t, ("tur", "form", "puan", "dogru", "toplam", "emin_ama_yanlis", "secilen_yanilgilar", "yarim_kaldi",
                     "cevapsiz"))
        x["gun"] = g(t.get("tarih"))
        alanlar = ("no", "hedef", "puan", "guven", "yanilgi", "emin_ama_yanlis") + (("ham_yanit",) if ham_yanitlar else ())
        x["yanitlar"] = [_sec(y, alanlar) for y in t.get("yanitlar") or []]
        testler.append(x)
    return {
        "ders": k.get("ders"), "mod": k.get("mod"), "oturum_sayisi": len(k.get("oturumlar") or []),
        "oturum_gunleri": [g(o.get("tarih")) for o in k.get("oturumlar") or []],
        "hedefler": hedefler,
        "yanilgilar": {y: _sec(v, ("durum",)) for y, v in (k.get("yanilgilar") or {}).items()},
        "guven": [dict(_sec(x, ("hedef", "guven", "dogru")), gun=g(x.get("tarih"))) for x in k.get("guven") or []],
        "ogrenci_soru_sayisi": len(k.get("sorular") or []),
        "testler": testler,
        "cevaplar": [dict(_sec(c, ("soru", "hedef", "bloom", "tur", "puan", "en_yuksek", "ilk_deneme", "ipucu", "vaka",
                                   "dugum", "tehlikeli")), gun=g(c.get("tarih"))) for c in k.get("cevaplar") or []],
        "vakalar": [dict(_sec(v, ("vaka", "sonuc", "dugum_sayisi")), gun=g(v.get("tarih"))) for v in k.get("vakalar") or []],
    }


def anonim(depo=None, ogrenciler=None, dosyalar=None, deneme_dahil=False, cikti=None, ham_yanitlar=False):
    """Seçilen öğrencilerin (ya da hepsinin) kayıtlarını kimliksiz tek dosyada toplar.

    ham_yanitlar=True: ölçme testlerinin kısa yazılı cevapları ham metin olarak eklenir (puanlayıcı uyumu, ör.
    Cohen kappa, için). Bu serbest metindir; dosya paylaşılmadan önce öğretmen okumalıdır."""
    kaynaklar = []  # (deneme, {ders: kayıt})
    if dosyalar:
        for y in dosyalar:
            p = paket_oku(y)
            kaynaklar.append((bool((p.get("ogrenci") or {}).get("deneme")) or
                              any(k.get("deneme") for k in (p.get("dersler") or {}).values()), p.get("dersler") or {}))
    if depo is not None and (ogrenciler or not dosyalar):
        kimlikler = [depo.coz(o) for o in ogrenciler] if ogrenciler else [b["kimlik"] for b in depo.ogrenciler()]
        for kimlik in dict.fromkeys(kimlikler):
            b = depo.bilgi(kimlik)
            dersler = {}
            for ders in b["dersler"]:
                k, _ = depo.yukle(kimlik, ders)
                if k:
                    dersler[ders] = k
            kaynaklar.append((b["deneme"] or depo.deneme_mi(kimlik) or any(k.get("deneme") for k in dersler.values()),
                              dersler))
    kayitlar, haric = [], 0
    kodlar = set()
    for deneme, dersler in kaynaklar:
        if deneme and not deneme_dahil:
            haric += 1
            continue
        if not dersler:
            continue
        tarihler = [t for k in dersler.values() for t in _tarihler(k)]
        baslangic = min(tarihler) if tarihler else None
        kod = None
        while not kod or kod in kodlar:
            kod = "K-" + secrets.token_hex(3).upper()
        kodlar.add(kod)
        x = {"kod": kod, "dersler": [anonim_ders(k, baslangic, ham_yanitlar) for _, k in sorted(dersler.items())]}
        if deneme:
            x["deneme"] = True
        kayitlar.append(x)
    secrets.SystemRandom().shuffle(kayitlar)
    out = {"tur": ANONIM_TUR, "surum": SURUM,
           "aciklama": ("Kimliksiz araştırma verisi: ad, kimlik ve ayırt edici yok; ölçme testlerinin kısa yazılı "
                        "cevapları ham metin olarak VAR (paylaşmadan önce okuyun); " if ham_yanitlar else
                        "Kimliksiz araştırma verisi: ad, kimlik, ayırt edici ve serbest metin yok; ") +
                       "kodlar rastgeledir ve geri çevrilemez; günler öğrencinin ilk kaydından bu yana geçen gündür.",
           "ogrenci_sayisi": len(kayitlar), "haric_tutulan_deneme": haric, "deneme_dahil": bool(deneme_dahil),
           "ham_yanitlar": bool(ham_yanitlar),
           "kayitlar": kayitlar}
    if cikti:
        if os.path.isdir(cikti):
            cikti = os.path.join(cikti, "KlinikKoc-anonim-%s.json" % time.strftime("%Y-%m-%d"))
        kd.atomik_yaz(cikti, out, yedekle=False)
        out = dict(out, dosya=os.path.abspath(cikti))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="KlinikKoç kayıtlarını dışa/içe aktar (yalnız bu bilgisayarda).")
    alt = ap.add_subparsers(dest="komut", required=True)
    alt.add_parser("liste", help="bu bilgisayardaki öğrenci kayıtlarını listele")
    a = alt.add_parser("disa", help="bir öğrencinin bütün kaydını tek dosyaya yaz")
    a.add_argument("--ogrenci", required=True)
    a.add_argument("--cikti")
    a = alt.add_parser("ice", help="dışa aktarılmış kayıt dosyasını içe al")
    a.add_argument("dosya")
    a.add_argument("--uzerine", action="store_true")
    a = alt.add_parser("anonim", help="öğretmen: seçilen öğrencilerin kimliksiz toplu aktarımı")
    g = a.add_mutually_exclusive_group(required=True)
    g.add_argument("--hepsi", action="store_true")
    g.add_argument("--ogrenci", nargs="+")
    g.add_argument("--dosya", nargs="+")
    a.add_argument("--deneme-dahil", action="store_true")
    a.add_argument("--ham-yanitlar", action="store_true",
                   help="ölçme testlerinin kısa yazılı cevaplarını ham metin olarak ekle (paylaşmadan önce okuyun)")
    a.add_argument("--cikti")
    ar = ap.parse_args(argv)
    depo = varsayilan_depo()
    try:
        if ar.komut == "liste":
            print("Kayıt klasörü:", depo.kok)
            for b in depo.ogrenciler():
                print("- %s  (%s%s)  dersler: %s  son: %s" % (b["kimlik"], b["ad"], ", DENEME" if b["deneme"] else "",
                                                           ", ".join(b["dersler"]) or "-", b["son_calisma"] or "-"))
        elif ar.komut == "disa":
            r = disa_aktar(depo, ar.ogrenci, ar.cikti)
            print("Yazıldı:", r["dosya"])
            for u in r["uyarilar"]:
                print("Uyarı:", u)
        elif ar.komut == "ice":
            r = ice_aktar(depo, ar.dosya, ar.uzerine)
            print("İçe alınan dersler:", ", ".join(r["alinan_dersler"]) or "-")
            for x in r["atlanan"]:
                print("Atlandı: %s (%s)" % (x["ders"], x["neden"]))
            print("Kayıt klasörü:", r["kayit_klasoru"])
        else:
            cikti = ar.cikti or veri_yeri.masaustu()
            r = anonim(None if ar.dosya else depo, ar.ogrenci, ar.dosya, ar.deneme_dahil, cikti,
                       ham_yanitlar=ar.ham_yanitlar)
            print("Yazıldı: %s (%d öğrenci, %d deneme kaydı dışarıda)" % (r["dosya"], r["ogrenci_sayisi"],
                                                                        r["haric_tutulan_deneme"]))
    except (kd.KayitHatasi, OSError, ValueError) as e:
        print("Hata:", e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
