"""Ders görsellerini öğrencinin kendi makale PDF'inden, kendi bilgisayarında çıkarır.

Abonelikli bir makalenin şekilleri ders paketine konamaz. Paket bunun yerine görselin nerede olduğunu söyler:

    ders.json  "assets":   {"sekil1": {"src": "assets/sekil1.png", "caption": "...",
                                       "makaleden": {"kaynak": "su2010", "sayfa": 3, "bolge": [0.08, 0.12, 0.92, 0.55]}}}
    egitmen.json "gorseller": {"sekil1": {"src": "gorseller/sekil1.png", "baslik": "...", "makaleden": {...}}}

kaynak: kaynaklar.json'daki makale kimliği · sayfa: 1'den başlar · bolge: sayfanın kesilecek kısmı, sol-üst ve
sağ-alt köşe, sayfa genişliği/yüksekliğine oranla (0–1); yoksa bütün sayfa.

Öğrenci makaleyi indirince ya da Makaleler sayfasına bırakınca (makale_bulucu) bu modül o makaleye bağlı görselleri
sayfadan çizip ders klasörüne PNG olarak yazar. Şekiller kimseye gönderilmez; herkes kendi kopyasından alır.
Çizim için pypdfium2 gerekir (makale_bulucu.py --kur kurar); yoksa görseller "çizici yok" diye eksik kalır ve tahta
"şekil makalede" notu gösterir.

    python tools/makale_sekil.py <ders>                      eksik görselleri çıkar
    python tools/makale_sekil.py <ders> --onizle <kaynak> 3  3. sayfayı bütün olarak onizleme.png'ye çiz (bölge seçmek için)
"""
import argparse
import importlib.util
import json
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import makale_bulucu as mb  # noqa: E402

OLCEK = 2.5  # 72 dpi × 2.5 ≈ 180 dpi: tahtada net, dosya küçük
EN_BUYUK_KENAR = 2400


def cizici_var():
    return importlib.util.find_spec("pypdfium2") is not None


def _json_oku(yol, varsayilan=None):
    try:
        with open(yol, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return varsayilan


def png_yaz(yol, genislik, yukseklik, satirlar):
    """RGB satırlarından (her biri genislik*3 bayt) PNG yazar; yalnız Python'un kendi kitaplığıyla."""
    def parca(tur, veri):
        return struct.pack(">I", len(veri)) + tur + veri + struct.pack(">I", zlib.crc32(tur + veri) & 0xFFFFFFFF)
    ham = b"".join(b"\x00" + s for s in satirlar)
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    gecici = yol + ".tmp"
    with open(gecici, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n")
        f.write(parca(b"IHDR", struct.pack(">IIBBBBB", genislik, yukseklik, 8, 2, 0, 0, 0)))
        f.write(parca(b"IDAT", zlib.compress(ham, 9)))
        f.write(parca(b"IEND", b""))
    os.replace(gecici, yol)


def tanimlar(ders):
    """Dersin makaleden çıkarılacak görselleri: [(ad, hedef yol, makaleden)] (ders.json ve egitmen.json)."""
    klasor = os.path.join(mb.KOK, "lessons", mb.ders_gecerli(ders))
    out = []
    for dosya, alan in (("ders.json", "assets"), ("egitmen.json", "gorseller")):
        for ad, g in ((_json_oku(os.path.join(klasor, dosya), {}) or {}).get(alan) or {}).items():
            m = g.get("makaleden") if isinstance(g, dict) else None
            src = g.get("src") if isinstance(g, dict) else None
            if not (m and src) or src.startswith(("http:", "https:", "data:")):
                continue
            hedef = os.path.normpath(os.path.join(klasor, src))
            if not hedef.startswith(os.path.normpath(klasor) + os.sep):
                continue  # paket dışına yazma
            out.append((ad, hedef, m))
    return out


def _pdf_yolu(ders, kaynak):
    s = (mb.durum_oku(ders).get("kaynaklar") or {}).get(kaynak) or {}
    yol = s.get("pdf") or s.get("dosya")
    if s.get("durum") == "hazir" and yol and os.path.exists(yol):
        return yol
    return None


def sayfa_ciz(pdf, sayfa, bolge=None, olcek=OLCEK):
    """(genislik, yukseklik, RGB satırları). sayfa 1'den başlar; bolge [x0, y0, x1, y1] oran (sol-üst köken)."""
    import pypdfium2 as pdfium
    belge = pdfium.PdfDocument(pdf)
    try:
        if not 1 <= sayfa <= len(belge):
            raise ValueError("Makalede %d. sayfa yok (%d sayfa)." % (sayfa, len(belge)))
        s = belge[sayfa - 1]
        w, h = s.get_size()
        kirp = (0, 0, 0, 0)
        if bolge:
            x0, y0, x1, y1 = [min(1.0, max(0.0, float(v))) for v in bolge]
            if x1 - x0 < 0.02 or y1 - y0 < 0.02:
                raise ValueError("Bölge çok küçük: %s" % bolge)
            kirp = (x0 * w, (1 - y1) * h, (1 - x1) * w, y0 * h)  # pdfium: sol, alt, sağ, üst kesilecek pay
        olcek = min(olcek, EN_BUYUK_KENAR / max(1.0, max(w - kirp[0] - kirp[2], h - kirp[1] - kirp[3])))
        bmp = s.render(scale=olcek, crop=kirp, rev_byteorder=True)  # RGB(A) sırası
        gen, yuk, adim, kanal = bmp.width, bmp.height, bmp.stride, bmp.n_channels
        tampon = bytes(bmp.buffer)
        satirlar = []
        for y in range(yuk):
            satir = tampon[y * adim: y * adim + gen * kanal]
            if kanal == 4:
                satir = b"".join(satir[i:i + 3] for i in range(0, len(satir), 4))
            elif kanal == 1:
                satir = b"".join(bytes((c, c, c)) for c in satir)
            satirlar.append(satir)
        return gen, yuk, satirlar
    finally:
        belge.close()


def cikar(ders, yeniden=False):
    """Eksik görselleri çıkarır. {ad: durum}: hazir | var | makale-yok | cizici-yok | hata: ..."""
    sonuc = {}
    tanim = tanimlar(ders)
    if not tanim:
        return sonuc
    cizici = cizici_var()
    for ad, hedef, m in tanim:
        if os.path.exists(hedef) and not yeniden:
            sonuc[ad] = "var"
            continue
        pdf = _pdf_yolu(ders, m.get("kaynak"))
        if not pdf:
            sonuc[ad] = "makale-yok"
            continue
        if not cizici:
            sonuc[ad] = "cizici-yok"
            continue
        try:
            png_yaz(hedef, *sayfa_ciz(pdf, int(m.get("sayfa") or 1), m.get("bolge")))
            sonuc[ad] = "hazir"
        except Exception as e:  # bozuk PDF, yanlış sayfa: o görsel eksik kalır, ders çalışır
            sonuc[ad] = "hata: %s" % e
    d = mb.durum_oku(ders)
    d["sekiller"] = sonuc
    mb.durum_yaz(ders, d)
    return sonuc


def ozet(ders):
    """Makaleler sayfası için: kaç görsel makaleden bekleniyor, kaçı hazır."""
    tanim = tanimlar(ders)
    hazir = sum(1 for _, hedef, _ in tanim if os.path.exists(hedef))
    return {"toplam": len(tanim), "hazir": hazir, "cizici": cizici_var(),
            "eksik_makaleler": sorted({m.get("kaynak") for _, hedef, m in tanim if not os.path.exists(hedef)})}


def _json_yaz(yol, veri):
    gecici = yol + ".tmp"
    with open(gecici, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=1)
    os.replace(gecici, yol)


def gorsel_tanimi(ad, kaynak, sayfa, bolge=None, baslik=None, aciklama=None):
    if not ad or not all(c.isalnum() or c in "-_" for c in ad):
        raise ValueError("Görsel adı harf, rakam, - ve _ olmalı: %r" % ad)
    m = {"kaynak": str(kaynak), "sayfa": int(sayfa)}
    if bolge:
        b = [round(min(1.0, max(0.0, float(v))), 4) for v in bolge]
        if len(b) != 4 or b[2] - b[0] < 0.02 or b[3] - b[1] < 0.02:
            raise ValueError("Bölge [sol, üst, sağ, alt] (0–1) olmalı: %s" % bolge)
        m["bolge"] = b
    return m


def tanimla(ders, ad, kaynak, sayfa, bolge=None, baslik=None, aciklama=None):
    """Kurulu bir derse makaleden alınacak bir görsel ekler (ya da tanımını günceller) ve hemen çizer.
    egitmen.json'a (canlı tahta) ve ders.json varsa ona (oynatıcı) yazılır."""
    klasor = os.path.join(mb.KOK, "lessons", mb.ders_gecerli(ders))
    if not os.path.isdir(klasor):
        raise ValueError("Ders kurulu değil: %s" % ders)
    m = gorsel_tanimi(ad, kaynak, sayfa, bolge)
    eg_yol = os.path.join(klasor, "egitmen.json")
    if os.path.exists(eg_yol):
        eg = _json_oku(eg_yol, {}) or {}
        g = (eg.setdefault("gorseller", {})).get(ad) or {}
        g.update({"src": g.get("src") if (g.get("src") or "").endswith(".png") else "gorseller/%s.png" % ad,
                  "makaleden": m})
        if baslik:
            g["baslik"] = baslik
        if aciklama:
            g["aciklama"] = aciklama
        eg["gorseller"][ad] = g
        _json_yaz(eg_yol, eg)
    d_yol = os.path.join(klasor, "ders.json")
    if os.path.exists(d_yol):
        d = _json_oku(d_yol, {}) or {}
        a = (d.setdefault("assets", {})).get(ad) or {}
        a.update({"src": a.get("src") if (a.get("src") or "").endswith(".png") else "assets/%s.png" % ad, "makaleden": m})
        if baslik or aciklama:
            a["caption"] = ". ".join(x for x in (baslik, aciklama) if x)
        a.setdefault("alt", aciklama or baslik or ad)
        d["assets"][ad] = a
        _json_yaz(d_yol, d)
    if not os.path.exists(eg_yol) and not os.path.exists(d_yol):
        raise ValueError("Derste ne egitmen.json ne ders.json var.")
    pdf = _pdf_yolu(ders, m["kaynak"])
    if not pdf:
        return {"ad": ad, "durum": "makale-yok", "makaleden": m}
    hedefler = [h for a2, h, _ in tanimlar(ders) if a2 == ad]
    for h in hedefler:
        png_yaz(h, *sayfa_ciz(pdf, m["sayfa"], m.get("bolge")))
    return {"ad": ad, "durum": "hazir", "makaleden": m, "dosya": hedefler[0] if hedefler else None}


def onizleme(pdf, sayfa, bolge=None, olcek=1.3):
    """Bir sayfayı (ya da bölgesini) geçici PNG baytı olarak verir: Claude bölge seçerken bakar."""
    import tempfile
    fd, yol = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        png_yaz(yol, *sayfa_ciz(pdf, int(sayfa), bolge, olcek))
        with open(yol, "rb") as f:
            return f.read()
    finally:
        os.remove(yol)


def main():
    ap = argparse.ArgumentParser(description="Ders görsellerini öğrencinin makale PDF'inden çıkarır")
    ap.add_argument("ders")
    ap.add_argument("--yeniden", action="store_true", help="var olanları da yeniden çiz")
    ap.add_argument("--onizle", nargs=2, metavar=("KAYNAK", "SAYFA"), help="bir sayfayı bütün olarak çiz")
    a = ap.parse_args()
    if a.onizle:
        pdf = _pdf_yolu(a.ders, a.onizle[0])
        if not pdf:
            print("Bu makalenin PDF'i hazır değil.")
            return 1
        png_yaz(os.path.abspath("onizleme.png"), *sayfa_ciz(pdf, int(a.onizle[1]), None, 1.5))
        print("onizleme.png yazıldı.")
        return 0
    for ad, durum in sorted(cikar(a.ders, a.yeniden).items()):
        print("%-16s %s" % (ad, durum))
    return 0


if __name__ == "__main__":
    sys.exit(main())
