#!/usr/bin/env python3
"""KlinikKoç için MCP sunucusu: Claude masaüstü uygulaması tahtayı canlı yönetir.

API anahtarı gerekmez. Claude, sizin aboneliğinizle masaüstü uygulamasında çalışır;
bu dosya ona tahtayı yönetecek araçlar verir (tahtayı aç, ders oku, şekle bak,
tahtaya yaz ve anlat, soru sor, durdur). Komutlar bu bilgisayardaki
tools/sunucu.py'ye, oradan tarayıcıdaki canli.html sayfasına gider.

Kurulum (bir kez):
  python tools/tahta-mcp.py --kur
  Sonra Claude masaüstü uygulamasını tamamen kapatıp (sistem tepsisinden "Quit") yeniden açın.

Kaldırma:
  python tools/tahta-mcp.py --kaldir

Claude ayar dosyasını bulamazsa (Ayarlar › Geliştirici › "Yapılandırmayı düzenle" ile açılan dosya):
  python tools/tahta-mcp.py --kur --ayar "<dosyanın yolu>"

Yalnızca Python'un kendi kitaplığı gerekir. Doğal ses için ayrıca Piper:
  python tools/ses-uret.py --kur   (zaten kuruluysa gerekmez)
"""
import base64
import glob
import hashlib
import json
import os
import random
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KOK, "tools"))
import bilgi_bankasi  # noqa: E402
import ders_paketi  # noqa: E402
import ders_sonu  # noqa: E402
import degerlendirme  # noqa: E402
import karne as karne_  # noqa: E402
import kayit_aktar  # noqa: E402
import kayit_deposu as kd  # noqa: E402
import makale_bulucu  # noqa: E402
import makale_sekil  # noqa: E402
try:
    import sihirbaz  # noqa: E402  (yalnız öğretmen sürümünde vardır)
except ImportError:
    sihirbaz = None
import ana_ekran  # noqa: E402
import surum as surum_  # noqa: E402
import veri_yeri  # noqa: E402


def _metin_oku(yol):
    """Dosyayı okuyup hemen kapatır (açık kalan dosya Windows'ta kilitlenmeye yol açar)."""
    with open(yol, encoding="utf-8") as f:
        return f.read()


def _json_oku(yol):
    with open(yol, encoding="utf-8") as f:
        return json.load(f)


def _ikili_oku(yol):
    with open(yol, "rb") as f:
        return f.read()
PORT = int(os.environ.get("KLINIK_KOC_PORT", "8810"))
ADRES = "http://127.0.0.1:%d" % PORT
def _surum_oku():
    try:
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "SURUM"), encoding="utf-8") as f:
            return f.read().strip() or "0"
    except OSError:
        return "0"


SURUM = _surum_oku()  # programın sürümü: kök klasördeki SURUM dosyası (config.js'teki ile aynı olmalı)
AD = "klinik-koc"
from mcp_araclar import ARACLAR, KOMUT_SEMASI, TALIMAT  # noqa: E402,F401  (araç tanımları ve talimat)

# ---------- Araç profili: öğrenci / öğretmen ----------
# Claude her sohbette bütün araç tanımlarını okur; öğrencinin kullanmadığı öğretmen araçları hem yer kaplar (abonelik
# sınırını daha çabuk doldurur) hem Claude'u yanlış araca yöneltebilir. Öğrenci kurulumunda gizlenirler.
# Öğretmen profili: KLINIK_KOC_PROFIL=ogretmen, ayarlar.json'da "profil": "ogretmen" ya da bu bilgisayarda ders
# sihirbazı kullanılmışsa (veri klasöründe sihirbaz/ taslakları) kendiliğinden.
OGRETMEN_ARACLARI = {"sihirbaz_oku", "sihirbaz_oner", "makale_sayfasi_bak", "makale_sekli_ekle", "degerlendirme_ozeti"}
GIZLI_ARACLAR = {"dinle"}  # eski ad: bekle'ye yönlenir; eski sohbetler çağırırsa çalışır ama listede görünmez


def profil():
    if sihirbaz is None or not surum_.ogretmen_mi():
        return "ogrenci"  # öğrenci sürümü: ders hazırlama dosyaları yok, öğretmen araçları da gösterilmez
    p = (os.environ.get("KLINIK_KOC_PROFIL") or _ayar("profil") or "").strip().lower()
    if p in ("ogretmen", "öğretmen", "ogrenci", "öğrenci"):
        return "ogretmen" if p.startswith(("ogr", "öğr")) and "etmen" in p else "ogrenci"
    return "ogretmen"  # öğretmen sürümü kuruluysa öğretmen araçları açıktır


def araclar():
    gizli = set(GIZLI_ARACLAR)
    if profil() != "ogretmen":
        gizli |= OGRETMEN_ARACLARI
    return [a for a in ARACLAR if a["name"] not in gizli]


# ---------- Yerel sunucuyla konuşma ----------
# Her araç çağrısının bir bağlamı vardır (iş parçacığına özel): bekleme kimliği (Claude çağrıyı iptal ederse sunucudaki
# bekleme hemen biter), teslim edilecek söz numaraları (söz ancak Claude'a yazıldıktan sonra sunucudan silinir),
# bitiş zamanı (bekleme bütçesi) ve iptal işareti.
_BAGLAM = threading.local()


def _baglam():
    return getattr(_BAGLAM, "c", None)


def _ham_istek(yol, govde=None, zaman=60):
    veri = None if govde is None else json.dumps(govde, ensure_ascii=False).encode("utf-8")
    r = urllib.request.Request(ADRES + "/api/canli/" + yol, data=veri,
                               headers={"Content-Type": "application/json", "X-KlinikKoc-Arac": "1"})
    with urllib.request.urlopen(r, timeout=zaman) as y:
        return json.loads(y.read().decode("utf-8"))


def istek(yol, govde=None, zaman=60):
    c = _baglam()
    if c is not None:
        yol += ("&" if "?" in yol else "?") + "bekleme=%s&teslim=1" % c["bekleme"]
    y = _ham_istek(yol, govde, zaman)
    if c is not None and isinstance(y, dict) and y.get("teslim"):
        c["teslimler"].append(y.pop("teslim"))
    return y


def _arka_planda(yol, zaman=3):
    """Sonucu beklenmeyen kısa bildirim (teslim onayı, iptal, etkinlik)."""
    def git():
        try:
            _ham_istek(yol, zaman=zaman)
        except Exception:
            pass
    threading.Thread(target=git, daemon=True).start()


# ---- Bekleme bütçesi: bir araç çağrısı en çok ne kadar açık kalabilir? ----
# Claude masaüstü bir araç çağrısını belli bir süre sonra (çoğu sürümde ~60 sn) zaman aşımıyla keser. Çağrı açıkken
# "ilerleme" bildirimi gönderilirse bazı sürümler süreyi uzatır. Bu yüzden: ilerleme jetonu varsa ilk denemede
# DENEME_SN beklenir; Claude zaman aşımıyla keserse kesildiği süre öğrenilir ve ayarlar.json'a yazılır
# (arac_bekleme_sn); sonraki çağrılar o sınırın biraz altında kalır. Söz bu arada kaybolmaz (teslim onayı).
VARSAYILAN_BEKLEME_SN = 50
DENEME_BEKLEME_SN = 170
NABIZ_SN = float(os.environ.get("KLINIK_KOC_NABIZ_SN") or 10)  # ilerleme bildirimi aralığı
PARCA_SN = 25  # sunucuya tek istekte en çok bu kadar beklenir; aralarda iptal ve bütçe denetlenir


def _ayar(anahtar, varsayilan=None):
    try:
        return ders_sonu.ayarlar().get(anahtar, varsayilan)
    except Exception:
        return varsayilan


def _ayar_yaz(anahtar, deger):
    try:
        a = ders_sonu.ayarlar()
        a[anahtar] = deger
        ders_sonu._json_yaz(ders_sonu.ayar_yolu(), a)
    except Exception:
        pass


def bekleme_butcesi(ilerleme_var):
    try:
        ogrenilen = int(_ayar("arac_bekleme_sn") or 0)
    except (TypeError, ValueError):
        ogrenilen = 0
    if ogrenilen >= 20:
        return min(ogrenilen, 600)
    return DENEME_BEKLEME_SN if ilerleme_var else VARSAYILAN_BEKLEME_SN


def _kalan():
    c = _baglam()
    return (c["bitis"] - time.time()) if c else float(VARSAYILAN_BEKLEME_SN)


def _iptal_edildi():
    c = _baglam()
    return bool(c and c["iptal"])


def uzun_bekle(no=None, ilk=None):
    """no verilirse o komutun (anlatım, soru) bitmesini, verilmezse kullanıcının sözünü bekler. Sunucuya kısa
    parçalarla sorar; bütçe dolana, Claude iptal edene ya da bir şey olana dek sürer. ilk: elde zaten bir ara sonuç
    varsa (ör. gonder 'sürüyor' döndüyse) o."""
    y = ilk
    bitis = time.time() + _kalan()
    while True:
        if y is not None:
            durum = y.get("durum") if isinstance(y, dict) else None
            if durum not in ("sürüyor", "sessiz", "duraklatildi") or _iptal_edildi():
                return y
        kalan = bitis - time.time()
        if kalan < 4 and y is not None:
            return y
        parca = int(max(3, min(PARCA_SN, kalan - 2)))
        yol = ("sonuc?no=%d&bekle=%d" % (int(no), parca)) if no is not None else ("dinle?bekle=%d" % parca)
        once = time.time()
        y = istek(yol, zaman=parca + 20)
        if time.time() - once < 1 and isinstance(y, dict) and y.get("durum") in ("sürüyor", "sessiz", "duraklatildi"):
            time.sleep(1)  # sunucu beklemeden döndüyse (eski sürüm vb.) boşuna dönüp durmayalım


def sunucu_acik():
    try:
        return istek("durum", zaman=3)
    except Exception:
        return None


def sunucuyu_baslat():
    betik = os.path.join(KOK, "tools", "sunucu.py")
    arg = [sys.executable, betik, "--acma", "--port", str(PORT)]
    if os.name == "nt":
        # Ayrı bir konsol penceresinde açılır; kapatmak için o pencereyi kapatmak yeter.
        subprocess.Popen(arg, cwd=KOK, creationflags=subprocess.CREATE_NEW_CONSOLE,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(arg, cwd=KOK, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)


def gonder(komut, bekle=True):
    try:
        if not bekle:
            return istek("gonder", {"komut": komut, "bekle": 0.5}, zaman=30)
        ilk = istek("gonder", {"komut": komut, "bekle": int(max(1, min(PARCA_SN, _kalan() - 2)))}, zaman=PARCA_SN + 20)
        no = ilk.get("no") if isinstance(ilk, dict) else None
        if no is None:
            return ilk
        y = uzun_bekle(no, ilk)
        return _suruyor_notu(y)
    except urllib.error.URLError:
        return {"durum": "bağlı değil", "hata": "Yerel tahta sunucusu kapalı. Önce tahtayi_ac aracını çağır."}


def _suruyor_notu(y):
    if isinstance(y, dict) and y.get("durum") == "sürüyor" and y.get("no"):
        y["not"] = ("Anlatım hâlâ sürüyor (hata değil). Sohbete yazma; bekle(no=%d) çağırarak bitişini bekle. "
                    "Kullanıcı konuşursa hemen döner." % y["no"])
    return y


# ---------- Ders dosyaları ----------
def katalog():
    yol = os.path.join(KOK, "lessons", "katalog.json")
    girisler = []
    if os.path.exists(yol):
        girisler = _json_oku(yol).get("lessons", [])
    bilinen = {g["id"] for g in girisler}
    for d in sorted(glob.glob(os.path.join(KOK, "lessons", "*", "ders.json")) +
                    glob.glob(os.path.join(KOK, "lessons", "*", "egitmen.json"))):
        i = os.path.basename(os.path.dirname(d))
        if i not in bilinen:
            bilinen.add(i)
            girisler.append({"id": i, "path": "lessons/%s/" % i})
    return girisler


def ders_yolu(ders, *parca):
    if not ders or any(c in ders for c in "/\\.") or ders.startswith("_"):
        raise ValueError("Geçersiz ders kimliği")
    return os.path.join(KOK, "lessons", ders, *parca)


def egitmen_json(ders):
    if ders == makale_bulucu.KENDI and os.path.abspath(makale_bulucu.KOK) == os.path.abspath(KOK):
        makale_bulucu.kendi_kitaplik_hazirla()  # kişisel kitaplık ilk istendiğinde kurulur
    yol = ders_yolu(ders, "egitmen.json")
    return _json_oku(yol) if os.path.exists(yol) else None


def ders_json(ders):
    """ders.json'u döndürür. Yalnız egitmen.json olan (canlı) derste ondan özet bir ders kurar."""
    yol = ders_yolu(ders, "ders.json")
    if os.path.exists(yol):
        return _json_oku(yol)
    eg = egitmen_json(ders)
    if not eg:
        raise ValueError("Ders bulunamadı: %s. dersler aracıyla listeye bak." % ders)
    assets = {k: {"src": g["src"], "caption": "%s. %s" % (g.get("baslik", k), g.get("aciklama", "")),
                  "alt": g.get("aciklama")} for k, g in (eg.get("gorseller") or {}).items()}
    kay = eg.get("kaynak") or {}
    if kay.get("sayfaGorseli"):
        for i in range(1, int(kay.get("sayfaSayisi") or 0) + 1):
            nn = "%02d" % i
            assets["sayfa-" + nn] = {"src": kay["sayfaGorseli"].replace("{nn}", nn), "caption": "Kaynak, sayfa %d" % i}
    return {"id": ders, "title": eg.get("baslik"), "level": eg.get("duzey"), "source": kay,
            "goals": eg.get("hedefler"), "sections": [], "assets": assets, "_canli": True}


def ar_dersler(_):
    out = []
    for g in katalog():
        try:
            d = ders_json(g["id"])
        except Exception:
            continue
        eg = egitmen_json(g["id"]) or {}
        out.append({
            "ders": g["id"], "baslik": d.get("title"), "duzey": d.get("level"),
            "egitmen": eg.get("egitmen"), "yalniz_canli": bool(d.get("_canli")),
            "bolumler": [{"bolum": s["id"], "baslik": s.get("title")} for s in d.get("sections", [])],
            "gorseller": {k: v.get("caption") or v.get("alt") for k, v in (d.get("assets") or {}).items()
                          if not k.startswith("sayfa-")},
        })
    if not out:
        return metin({"dersler": [], "not": "Bu bilgisayarda hiç ders yok: program derssiz gelir. Öğrenciye öğretmeninin verdiği "
                                            "ders paketini (.zip) sor; yolunu verirse ders_paketi_ekle ile kur, vermezse "
                                            "ders_paketi_ekle'yi yolsuz çağırıp paket sayfasını aç. Öğrenci derssiz, kendi "
                                            "makalesiyle çalışmak isterse makale_ekle(ders='kendi-makalelerim') kullan."})
    for x in out:
        if x["ders"] == makale_bulucu.KENDI:
            mo = makale_bulucu.ozet(x["ders"])
            x["kendi_kitaplik"] = True
            x["makaleler"] = [m["kisa"] for m in mo["makaleler"] if m["durum"] == "hazir"]
            x["not"] = ("Öğrencinin derse bağlı olmayan kendi makaleleri. Öğrenci 'kendi makalem', 'kendi PDF'im', "
                        "'eklediğim makale' derse bu dersi seç (egitmen_hazirla(ders='kendi-makalelerim')).")
    return metin(out)


def ar_ders_oku(a):
    ders = a.get("ders")
    d = ders_json(ders)
    if a.get("sayfa"):
        eg = egitmen_json(ders) or {}
        kay = eg.get("kaynak") or {}
        try:
            n = int(a["sayfa"])
        except (TypeError, ValueError):
            raise ValueError("sayfa bir sayı olmalı")
        sablon = kay.get("sayfaMetni") or "kaynak/sayfa-{nn}.txt"
        yol = ders_yolu(ders, *sablon.replace("{nn}", "%02d" % n).split("/"))
        if not os.path.exists(yol):
            return metin({"sayfa": n, "durum": "okunamadı", "not": "Bu sayfanın metni pakette yok. "
                          "'Notta yok' deme; 'bu sayfayı okuyamadım' de."})
        out = {"sayfa": n, "kaynak": kay.get("baslik"), "metin": _metin_oku(yol),
               "okuma_notu": kay.get("okumaNotu")}
        if kay.get("sayfaGorseli"):
            out["sayfa_gorseli"] = "sayfa-%02d (gorsel_bak ile bakabilirsin)" % n
        notlar = [x for x in eg.get("ogretmenNotlari", []) if n in (x.get("sayfalar") or [])]
        if notlar:
            out["ogretmen_notlari"] = notlar
        return metin(out)
    bolum = a.get("bolum")
    if not bolum:
        return metin({
            "ders": d.get("id"), "baslik": d.get("title"), "duzey": d.get("level"), "kaynak": d.get("source"),
            "hedefler": d.get("goals"),
            "bolumler": [{"bolum": s["id"], "baslik": s.get("title"), "hedefler": s.get("goals"),
                          "adim": len(s.get("steps", []))} for s in d.get("sections", [])],
            "gorseller": {k: {"aciklama": v.get("alt"), "altyazi": v.get("caption")}
                          for k, v in (d.get("assets") or {}).items() if not k.startswith("sayfa-")},
            "not": "Kaynağın bir sayfasını okumak için ders_oku'yu sayfa ile çağır." if egitmen_json(ders) else None,
        })
    s = next((x for x in d.get("sections", []) if x["id"] == bolum), None)
    if not s:
        raise ValueError("Bölüm yok: %s" % bolum)
    adimlar = []
    for st in s.get("steps", []):
        x = {"adim": st["id"]}
        if st.get("say"):
            x["anlatim"] = st["say"]
        if st.get("board"):
            x["tahta"] = st["board"]
        if st.get("question"):
            q = st["question"]
            x["soru"] = {k: q.get(k) for k in ("type", "prompt", "options", "answer", "explanation", "goal") if q.get(k) is not None}
        if st.get("sourceRef"):
            x["kaynak"] = st["sourceRef"]
        adimlar.append(x)
    return metin({"bolum": s["id"], "baslik": s.get("title"), "hedefler": s.get("goals"), "adimlar": adimlar})


def ar_gorsel_bak(a):
    d = ders_json(a.get("ders"))
    g = (d.get("assets") or {}).get(a.get("gorsel"))
    if not g:
        raise ValueError("Görsel yok. Bu dersin görselleri: " + ", ".join(
            k for k in (d.get("assets") or {}) if not k.startswith("sayfa-")) + " (ve sayfa-01, sayfa-02 ... varsa)")
    yol = os.path.normpath(os.path.join(KOK, "lessons", a["ders"], g["src"]))
    uz = os.path.splitext(yol)[1].lower()
    tur = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
           ".gif": "image/gif"}.get(uz)
    alt = g.get("alt") or ""
    bilgi = "%s\n%s\nİşaretlerken bölge [sol, üst, genişlik, yükseklik] görselin 0–1 arası oranlarıdır." % (
        g.get("caption") or "", "" if alt and alt in (g.get("caption") or "") else alt)
    eg = egitmen_json(a["ders"]) or {}
    eg_g = (eg.get("gorseller") or {}).get(a.get("gorsel")) or {}
    for k in ("ogretmenNotu", "kaynakNotu"):
        if eg_g.get(k):
            bilgi += "\n%s: %s" % ("Öğretmen notu" if k == "ogretmenNotu" else "Kaynak notu", eg_g[k])
    if not tur:
        return {"content": [{"type": "text", "text": bilgi + "\n(Bu görsel türü gösterilemiyor: %s)" % uz}]}
    m = g.get("makaleden") or eg_g.get("makaleden")
    if m and not os.path.exists(yol):
        return {"content": [{"type": "text", "text": bilgi + (
            "\nBu şekil pakette yok; öğrencinin makale PDF'inden (%s, s. %s) çıkarılır ve makale henüz eklenmemiş. "
            "Tahtada yerine 'şekil makalede' notu çıkar. Öğrenciye makaleyi Makaleler sayfasından bu derse eklemesini "
            "söyle; ekleyince şekil kendiliğinden gelir. Şekli görmeden üzerinde işaretleme yapma." % (
                m.get("kaynak"), m.get("sayfa") or "?"))}]}
    veri = base64.b64encode(_ikili_oku(yol)).decode("ascii")
    return {"content": [{"type": "image", "data": veri, "mimeType": tur}, {"type": "text", "text": bilgi}]}


# ---------- Eğitmen, öğrenci kaydı, rapor ----------
EGITMENLER = {"inci": "İnci (lisans)", "mercan": "Mercan (uzmanlık)"}
BLOOM = ["hatirla", "anla", "uygula", "cozumle", "degerlendir", "olustur"]
BLOOM_AD = dict(zip(BLOOM, ["hatırla", "anla", "uygula", "çözümle", "değerlendir", "oluştur"]))
DURUM_AD = {"ele_alinmadi": "ele alınmadı", "destekle_yapti": "destekle yaptı", "bagimsiz_yapti": "bağımsız yaptı",
            "tekrar_gerekli": "tekrar gerekli", "devam_ediyor": "devam ediyor"}
TEKRAR_GUN = {1: 1, 2: 3, 3: 7, 4: 21}  # Leitner kutusu → sonraki geri çağırmaya kadar gün
# İpucu merdiveni: öğrencinin cevaba hangi basamakta ulaştığı. S0 yardımsız; S1 genel yönlendirme ("neye bakmalısın?");
# S2 odaklı ipucu; S3 kısmi çözüm ya da seçenek daraltma; S4 cevabı gösterip açıklama.
ISKELE = ("S0", "S1", "S2", "S3", "S4")


def yeni_kutu(kutu, dogru, yardimsiz, iskele=None):
    """Leitner kutusu. iskele verilmezse eski kural: yardımsız doğru bir üst kutu, gerisi 1. kutu.
    iskele verilirse: S0 doğru bir üst kutu; S1 doğru kutuyu korur (sıfırlamaz); S2–S4 ya da yanlış 1. kutu."""
    kutu = kutu or 0
    if not dogru:
        return 1
    if iskele in ISKELE:
        if iskele == "S0":
            return min(4, kutu + 1)
        if iskele == "S1":
            return max(1, kutu)
        return 1
    return min(4, kutu + 1) if yardimsiz else 1
KAYIT_KOK = veri_yeri.kayit_kok()          # kalıcı yer; KLINIK_KOC_KAYIT önce gelir
ESKI_KAYIT_KOK = os.path.join(KOK, "kayitlar")  # eski sürümlerin yeri: ilk açılışta bir kez kopyalanır
_DEPO = None


def depo():
    global _DEPO
    if _DEPO is None or _DEPO.kok != os.path.abspath(KAYIT_KOK):
        _DEPO = kd.Depo(KAYIT_KOK, None if veri_yeri.kayit_ortamdan_mi() else ESKI_KAYIT_KOK)
    return _DEPO


def bugun():
    return time.strftime("%Y-%m-%d")


def gun_ekle(tarih, gun):
    t = time.mktime(time.strptime(tarih, "%Y-%m-%d")) + gun * 86400 + 3600
    return time.strftime("%Y-%m-%d", time.localtime(t))


def ogrenci_kimligi(ogrenci):
    """Araçların ogrenci alanı (kimlik ya da ad) → kalıcı kimlik. Eski ada göre kayıtlar aynen bulunur."""
    return depo().coz(ogrenci)


def ogrenci_klasoru(ogrenci):
    return depo().klasor(ogrenci_kimligi(ogrenci))


def kayit_yolu(ogrenci, ders):
    ders_yolu(ders)  # kimlik denetimi
    return depo().kayit_yolu(ogrenci_kimligi(ogrenci), ders)


def kayit_yukle(ogrenci, ders):
    ders_yolu(ders)  # kimlik denetimi
    d = depo()
    kimlik = d.coz(ogrenci)
    k, uyarilar = d.yukle(kimlik, ders)
    if k is None:
        bilgi = d.defter()["ogrenciler"].get(kimlik) or {}
        k = {"ogrenci": bilgi.get("ad") or (ogrenci or "").strip(), "ders": ders, "olusturma": bugun(),
             "mod": "once_anlat", "hedefler": {}, "yanilgilar": {}, "guven": [], "sorular": [], "testler": [],
             "oturumlar": [], "mola": None, "cevaplar": [], "vakalar": []}
        if bilgi.get("ayirt"):
            k["tohum"] = kimlik  # ölçme testinde seçenek sırası bu kimliğe bağlı kalır
    k["ogrenci_kimligi"] = kimlik
    if d.deneme_mi(kimlik) or kd.deneme_adi_mi(k.get("ogrenci")):
        k["deneme"] = True
    k["_kimlik"] = kimlik
    if uyarilar:
        k["_uyarilar"] = uyarilar
    return k


def kayit_kaydet(k):
    kimlik = k.get("_kimlik") or k.get("ogrenci_kimligi") or depo().coz(k["ogrenci"])
    return depo().yaz(kimlik, k["ders"], k)


def kayit_temiz(k):
    return {a: v for a, v in k.items() if not a.startswith("_")}


def uyari_ekle(out, k):
    if k.get("_uyarilar"):
        out.setdefault("uyarilar", [])
        out["uyarilar"] = k["_uyarilar"] + out["uyarilar"]
    return out


def tohum(k):
    return k.get("tohum") or (k.get("ogrenci") or "")


def tekrar_zamani_gelenler(k):
    b = bugun()
    return sorted([h for h, v in k["hedefler"].items()
                   if v.get("sonraki_tekrar") and v["sonraki_tekrar"] <= b],
                  key=lambda h: k["hedefler"][h]["sonraki_tekrar"])


def kayit_ozeti(k, eg):
    hedefler = {x["id"]: x for x in (eg or {}).get("hedefler", [])}
    ozet = {}
    for hid, h in hedefler.items():
        v = k["hedefler"].get(hid, {})
        ozet[hid] = {"baslik": h.get("baslik"), "hedef_duzey": h.get("bloom"),
                     "ulasilan_yardimsiz": v.get("yardimsiz_duzey"), "ulasilan_destekle": v.get("destekle_duzey"),
                     "durum": v.get("durum", "ele_alinmadi"), "sonraki_tekrar": v.get("sonraki_tekrar")}
    return {"hedefler": ozet,
            "acik_yanilgilar": [y for y, v in k["yanilgilar"].items() if v.get("durum") == "acik"],
            "tekrar_zamani_gelen": tekrar_zamani_gelenler(k),
            "mola": k.get("mola"), "mod": k.get("mod"),
            "oturum_sayisi": len(k.get("oturumlar", [])),
            "testler": [{"tur": t.get("tur"), "tarih": t.get("tarih"), "puan": t.get("puan"), "toplam": t.get("toplam"),
                         "secilen_yanilgilar": t.get("secilen_yanilgilar")} for t in k.get("testler", [])]}


OGRENCI_TALIMAT = ("Sonraki bütün araçlarda (kayit_yaz, kayit_oku, karne, rapor_yaz, olcme_..., tekrar_listesi, "
                   "sozlu_prova) ogrenci alanına bu kimliği yaz: %s")


def ogrenci_sec(a):
    """egitmen_hazirla için öğrenciyi bulur ya da açar. (kimlik, None) ya da (None, sorulacak durum)."""
    d = depo()
    d.hazirla()
    ad = (a.get("ogrenci") or "").strip()
    ayirt = (a.get("ayirt") or "").strip()
    deneme = bool(a.get("deneme")) or kd.deneme_adi_mi(ad)
    defter = d.defter()["ogrenciler"]
    kim = (a.get("ogrenci_kimligi") or "").strip()
    if not kim and ad in defter and defter[ad].get("ayirt"):
        kim = ad  # ogrenci alanına zaten kimlik yazılmış
    if kim:
        if not d.var_mi(kim):
            raise kd.KayitHatasi("Bu kimlikle kayıt yok: %s" % kim)
        if not (defter.get(kim) or {}).get("ayirt") or deneme:
            d.eskiyi_bagla(kim, ayirt or None, deneme)
        return kim, None
    if not ad:
        return None, {"durum": "ad_gerekli",
                      "talimat": "Öğrenciye bir kez adını ve kısa bir ayırt ediciyi (öğrenci numarasının son 3 hanesi "
                                 "ya da kendi seçtiği bir takma ad) sor; sonra egitmen_hazirla'yı ogrenci ve ayirt ile "
                                 "yeniden çağır. Öğretmen deniyorsa ogrenci='deneme' ya da deneme=true ver."}
    if deneme:
        return d.kimlik_olustur(ad, ayirt or "ogretmen", deneme=True), None
    adaylar = d.adaylar(ad)
    if ayirt:
        for x in adaylar:
            if x.get("ayirt") and kd.kisalt(x["ayirt"]) == kd.kisalt(ayirt):
                return x["kimlik"], None
        if not adaylar or a.get("yeni_ogrenci"):
            return d.kimlik_olustur(ad, ayirt), None
    elif not adaylar:
        return None, {"durum": "ayirt_gerekli",
                      "talimat": "Bu adla kayıt yok; ilk giriş. Öğrenciye kısa bir ayırt edici sor: öğrenci numarasının "
                                 "son 3 hanesi ya da kendi seçeceği bir takma ad (aynı adlı başka öğrenciyle karışmasın "
                                 "diye). Sonra egitmen_hazirla'yı ogrenci ve ayirt ile yeniden çağır."}
    return None, {"durum": "ayni_ad_var", "soru": "Bu adla kayıt var, sen misin?",
                  "kayitlar": [{"kimlik": x["kimlik"], "dersler": x["dersler"], "son_calisma": x["son_calisma"],
                                "eski_kayit": x["eski"]} for x in adaylar],
                  "talimat": "Öğrenciye 'Bu adla kayıt var, sen misin?' diye sor (kaydın derslerini ve son çalışma "
                             "tarihini söyleyebilirsin). Evet derse egitmen_hazirla'yı ogrenci_kimligi=<kimlik> ile "
                             "çağır (eski kayıtsa ayirt'ı da ver, kayıt ona bağlanır). Hayır derse ayirt ve "
                             "yeni_ogrenci=true ile çağır; yeni ve ayrı bir kayıt açılır."}


def ar_egitmen_hazirla(a):
    ders = a.get("ders")
    eg = egitmen_json(ders)
    d = ders_json(ders)
    if not eg:
        eg = {"egitmen": "inci", "izinliEgitmenler": ["inci", "mercan"], "hedefler": [
            {"id": s["id"], "baslik": s.get("text")} for g in d.get("goals", []) for s in g.get("subgoals", [])]}
    secilen = (a.get("egitmen") or eg.get("egitmen") or "inci").lower()
    izinli = eg.get("izinliEgitmenler") or [eg.get("egitmen")]
    not_ = None
    if secilen not in izinli:
        not_ = "%s bu ders için açık değil; dersin eğitmeni %s kullanılıyor." % (secilen, eg.get("egitmen"))
        secilen = eg.get("egitmen")
    if secilen not in EGITMENLER:
        raise ValueError("Bilinmeyen eğitmen: %s" % secilen)
    kurallar = _metin_oku(os.path.join(KOK, "egitmenler", "ortak.md")) + "\n\n" + \
        _metin_oku(os.path.join(KOK, "egitmenler", secilen + ".md"))
    out = {"egitmen": EGITMENLER[secilen], "izinli_egitmenler": [EGITMENLER.get(x, x) for x in izinli],
           "kurallar": kurallar,
           "ders": {"kimlik": ders, "baslik": eg.get("baslik") or d.get("title"), "duzey": eg.get("duzey"),
                    "kaynak": eg.get("kaynak") or d.get("source"), "hedefler": eg.get("hedefler"),
                    "ogretmen_notlari": eg.get("ogretmenNotlari"), "bilinen_yanilgilar": eg.get("yanilgilar"),
                    "oturumlar": eg.get("oturumlar"), "arac_seti": eg.get("aracSeti"), "olcme": olcme_ozeti(eg),
                    "ogretmenin_sorulari": eg.get("soruBankasi") or None,
                    "onemli_noktalar": eg.get("onemliNoktalar") or None,
                    "hazir_cizimler": eg.get("cizimler") or None,
                    "gorseller": {k: v.get("aciklama") for k, v in (eg.get("gorseller") or {}).items()}
                    or {k: v.get("caption") for k, v in (d.get("assets") or {}).items()},
                    "hazir_anlatim_bolumleri": [s["id"] for s in d.get("sections", [])],
                    "vakalar": [os.path.splitext(os.path.basename(y))[0]
                                for y in sorted(glob.glob(ders_yolu(ders, "vakalar", "*.json")))]},
           "bloom_sirasi": BLOOM}
    if not_:
        out["not"] = not_
    kimlik, soru = ogrenci_sec(a)
    if kimlik:
        k = kayit_yukle(kimlik, ders)
        out["ogrenci"] = {"ad": k["ogrenci"], "kimlik": kimlik, "kayit": kayit_ozeti(k, eg),
                          "ilk_oturum": not k.get("oturumlar"), "olcme_sirasi": olcme_sirasi(k, eg),
                          "kayit_klasoru": depo().klasor(kimlik), "not": OGRENCI_TALIMAT % kimlik}
        if k.get("deneme"):
            out["ogrenci"]["deneme"] = True
            out["ogrenci"]["deneme_notu"] = ("Öğretmen deneme kaydı: karnede ve araştırma dışa aktarımında ayrı "
                                             "işaretlenir, anonim aktarıma katılmaz.")
        uyari_ekle(out["ogrenci"], k)
    else:
        out["ogrenci"] = soru
    if depo().tasima_raporu and not getattr(depo(), "_tasima_soylendi", False):
        r = depo().tasima_raporu
        depo()._tasima_soylendi = True
        out["kayit_tasima"] = {"not": "Eski kayıtlar kalıcı kayıt klasörüne kopyalandı; eski dosyalar silinmedi.",
                               "kaynak": r["kaynak"], "yeni_yer": depo().kok, "kopyalanan": r["kopyalanan"]}
    if ders == makale_bulucu.KENDI:
        mo = makale_bulucu.ozet(ders)
        out["makaleler"] = {"hazir": [m["kisa"] for m in mo["makaleler"] if m["durum"] == "hazir"],
                            "not": "Öğrencinin kendi eklediği makaleler. Hangisiyle çalışmak istediğini sor; bilgiyi "
                                   "bilgi_ara(ders='kendi-makalelerim') ile bu makalelerden al."}
        if not out["makaleler"]["hazir"]:
            out["makaleler"]["not"] = ("Kitaplıkta henüz okunmuş makale yok. Öğrenciden PDF'in yolunu iste ve "
                                       "makale_ekle(ders='kendi-makalelerim') ile ekle, ya da makaleler(ac: true) ile "
                                       "sayfayı açıp PDF'i 'Kendi makalelerim' seçiliyken bırakmasını söyle.")
    elif makale_bulucu.kaynaklar(ders):
        mo = makale_bulucu.ozet(ders)
        out["makaleler"] = {"sayilar": mo["sayilar"],
                            "eksik": [m["kisa"] for m in mo["makaleler"] if m["durum"] != "hazir"]}
        if out["makaleler"]["eksik"]:
            out["makaleler"]["not"] = ("Bu dersin bazı makaleleri bu bilgisayarda yok ya da hiç denenmedi. Derse başlamadan "
                                       "öğrenciye söyle ve makale_bul ile indirmeyi öner; inmeyenler için makaleler (ac: true).")
    try:
        if ders_sonu.depolama()["asildi"]:
            out["depolama"] = {**depolama_ozeti(), "not": DEPOLAMA_NOTU}
    except Exception:  # depolama ölçülemese de ders açılır
        pass
    return metin(out)


def ar_kayit_oku(a):
    k = kayit_yukle(a.get("ogrenci"), a.get("ders"))
    eg = egitmen_json(a.get("ders"))
    out = kayit_ozeti(k, eg)
    out["ogrenci_kimligi"] = k["_kimlik"]
    if k.get("deneme"):
        out["deneme"] = True
    if a.get("ayrinti"):
        out["kayit"] = kayit_temiz(k)
    return metin(uyari_ekle(out, k))


def ar_kayit_yaz(a):
    k = kayit_yukle(a.get("ogrenci"), a.get("ders"))
    eg = egitmen_json(a.get("ders")) or {}
    gecerli = {x["id"] for x in eg.get("hedefler", [])}
    uyarilar = []
    b = bugun()
    for g in a.get("hedefler") or []:
        hid = g.get("id")
        if gecerli and hid not in gecerli:
            uyarilar.append("Bilinmeyen hedef: %s" % hid)
            continue
        v = k["hedefler"].setdefault(hid, {"kutu": 0, "kanitlar": []})
        duzey = g.get("duzey")
        if duzey and duzey not in BLOOM:
            uyarilar.append("Geçersiz Bloom düzeyi: %s" % duzey)
            duzey = None
        iskele = g.get("iskele")
        if iskele is not None and iskele not in ISKELE:
            uyarilar.append("Geçersiz iskele basamağı: %s (S0–S4 olmalı)" % iskele)
            iskele = None
        if iskele and not g.get("yardim"):
            g["yardim"] = "yardimsiz" if iskele == "S0" else "destekle"
        elif iskele and (iskele == "S0") != (g.get("yardim") == "yardimsiz"):
            uyarilar.append("%s: yardim (%s) ile iskele (%s) uyuşmuyor; iskele esas alındı" % (hid, g.get("yardim"), iskele))
            g["yardim"] = "yardimsiz" if iskele == "S0" else "destekle"
        yardimsiz = g.get("yardim") == "yardimsiz"
        if duzey:
            alan = "yardimsiz_duzey" if yardimsiz else "destekle_duzey"
            if BLOOM.index(duzey) >= BLOOM.index(v.get(alan) or "hatirla") or not v.get(alan):
                v[alan] = duzey
        if g.get("durum"):
            v["durum"] = g["durum"]
        elif duzey:
            hedef = next((x.get("bloom") for x in eg.get("hedefler", []) if x["id"] == hid), None)
            if yardimsiz and g.get("dogru", True) and hedef in BLOOM and BLOOM.index(duzey) >= BLOOM.index(hedef):
                v["durum"] = "bagimsiz_yapti"
            elif v.get("durum") != "bagimsiz_yapti":
                v["durum"] = "destekle_yapti" if not yardimsiz else "devam_ediyor"
        if duzey or g.get("tur") == "geri_cagirma":
            # Aralıklı tekrar: yardımsız başarı bir üst kutu; yalnız genel yönlendirmeyle (S1) başarı kutuyu korur;
            # başarısızlık ya da daha fazla yardım 1. kutu.
            v["kutu"] = yeni_kutu(v.get("kutu", 0), g.get("dogru", True), yardimsiz, iskele)
            v["sonraki_tekrar"] = gun_ekle(b, TEKRAR_GUN[v["kutu"]])
        v["son"] = b
        if g.get("kanit"):
            v["kanitlar"] = (v.get("kanitlar") or [])[-9:] + [
                {"tarih": b, "tur": g.get("tur", "yanit"), "duzey": duzey, "yardim": g.get("yardim"),
                 **({"iskele": iskele} if iskele else {}), "solo": g.get("solo"), "dogru": g.get("dogru"), "ozet": g["kanit"]}]
    for y in a.get("yanilgilar") or []:
        v = k["yanilgilar"].setdefault(y.get("id"), {"durum": "acik", "ilk": b})
        v["durum"] = y.get("durum", v["durum"])
        if y.get("not"):
            v["not"] = y["not"]
        v["son"] = b
    for g in a.get("guven") or []:
        k["guven"].append(dict(g, tarih=b))
    for s in a.get("sorular") or []:
        k["sorular"].append(dict(s, tarih=b))
    for t in a.get("testler") or []:
        k["testler"].append(dict(t, tarih=b))
    for c in a.get("cevaplar") or []:
        c = dict(c, tarih=b, saat=time.strftime("%H:%M"))
        if c.get("bloom") and c["bloom"] not in BLOOM:
            uyarilar.append("Geçersiz Bloom düzeyi: %s" % c["bloom"])
            c.pop("bloom")
        try:
            c["puan"] = float(c.get("puan", 1 if c.get("dogru") else 0))
            c["en_yuksek"] = float(c.get("en_yuksek") or 1)
        except (TypeError, ValueError):
            uyarilar.append("Cevap puanı sayı olmalı: %s" % c.get("soru"))
            continue
        k.setdefault("cevaplar", []).append(c)
    if a.get("vaka_sonucu"):
        k.setdefault("vakalar", []).append(dict(a["vaka_sonucu"], tarih=b))
    if a.get("mod") in ("once_anlat", "once_yanitla"):
        k["mod"] = a["mod"]
    if "mola" in a:
        k["mola"] = a.get("mola")
    if a.get("oturum"):
        o = dict(a["oturum"], tarih=b)
        if k["oturumlar"] and k["oturumlar"][-1].get("tarih") == b and not a["oturum"].get("yeni"):
            k["oturumlar"][-1].update(o)
        else:
            k["oturumlar"].append(o)
    yol = kayit_kaydet(k)
    out = {"durum": "kaydedildi", "dosya": yol, "ozet": kayit_ozeti(k, eg)}
    if uyarilar:
        out["uyarilar"] = uyarilar
    return metin(uyari_ekle(out, k))


def ar_rapor_yaz(a):
    ders = a.get("ders")
    k = kayit_yukle(a.get("ogrenci"), ders)
    eg = egitmen_json(ders) or {}
    hed = {x["id"]: x for x in eg.get("hedefler", [])}
    y = ["# Çalışma raporu — %s" % (eg.get("baslik") or ders), "",
         "Öğrenci: %s · Tarih: %s · Eğitmen: %s · Oturum sayısı: %d" % (
             k["ogrenci"], bugun(), EGITMENLER.get(eg.get("egitmen"), "-"), len(k.get("oturumlar", []))),
         "", "Bu rapor not için değildir. Öğrencinin bilgisayarında üretildi; otomatik gönderilmedi.", ""]
    if k.get("deneme"):
        y += ["> **DENEME KAYDI:** öğretmen denemesidir; araştırma verisine katılmaz.", ""]
    y += [
         "## Öğretmen özeti", "", (a.get("ogretmen_ozeti") or "(özet yazılmadı)").strip(), ""]
    y += ["## Hedefler", "", "| Hedef | Hedef düzey | Yardımsız ulaşılan | Destekle ulaşılan | Durum | Sonraki tekrar |",
          "| --- | --- | --- | --- | --- | --- |"]
    for hid, h in hed.items():
        v = k["hedefler"].get(hid, {})
        y.append("| %s %s | %s | %s | %s | %s | %s |" % (hid, h.get("baslik", ""), BLOOM_AD.get(h.get("bloom"), "-"),
                 BLOOM_AD.get(v.get("yardimsiz_duzey"), "-"), BLOOM_AD.get(v.get("destekle_duzey"), "-"),
                 DURUM_AD.get(v.get("durum", "ele_alinmadi"), v.get("durum")), v.get("sonraki_tekrar") or "-"))
    yan = {x["id"]: x for x in eg.get("yanilgilar", [])}
    if k["yanilgilar"]:
        y += ["", "## Yanılgılar", ""]
        for yid, v in k["yanilgilar"].items():
            y.append("- **%s** (%s): %s%s" % (yid, v.get("durum"), yan.get(yid, {}).get("metin", ""),
                                              (" — " + v["not"]) if v.get("not") else ""))
    yanlis_emin = [g for g in k.get("guven", []) if g.get("guven") == "emin" and g.get("dogru") is False]
    if k.get("guven"):
        y += ["", "## Güven ve doğruluk (olgu soruları)", "",
              "Toplam %d olgu sorusu; emin ama yanlış: %d." % (len(k["guven"]), len(yanlis_emin))]
        for g in yanlis_emin:
            y.append("- %s: %s" % (g.get("hedef", ""), g.get("soru", "")))
    if k.get("sorular"):
        y += ["", "## Öğrencinin soruları (notta olmayanlar ve ilginç olanlar)", ""]
        for s in k["sorular"]:
            y.append("- %s%s" % (s.get("soru", ""), " — kaynakta yok" if s.get("kaynakta_yok") else ""))
    if k.get("testler"):
        y += ["", "## Ölçme testleri (pilot)", "",
              "| Tarih | Test | Form | Puan | Emin ama yanlış | Seçilen yanılgılar |", "| --- | --- | --- | --- | --- | --- |"]
        for t in k["testler"]:
            y.append("| %s | %s%s | %s | %s / %s | %s | %s |" % (
                t.get("tarih"), TEST_AD.get(t.get("tur"), t.get("tur")), " (yarım)" if t.get("yarim_kaldi") else "",
                t.get("form", "-"), t.get("puan", t.get("dogru")), t.get("toplam"),
                t.get("emin_ama_yanlis", "-"), ", ".join(t.get("secilen_yanilgilar") or []) or "-"))
    if k.get("cevaplar"):
        kr = karne_.hesapla(k, karne_.ders_hedefleri(ders_yolu(ders)), bugun())
        y += ["", "## Bloom düzeyine göre başarı", "", "| Düzey | Cevap | Başarı |", "| --- | --- | --- |"]
        y += ["| %s | %d | %s |" % (karne_.BLOOM_AD[b["duzey"]], b["cevap"], karne_.yuzde(b["oran"])) for b in kr["bloom"]]
        if kr["tehlikeli_secimler"]:
            y += ["", "Vakalarda hastaya zarar verebilecek seçim sayısı: %d" % len(kr["tehlikeli_secimler"])]
    for baslik, alan in (("Öğrenme güçlükleri", "guclukler"), ("Eğitmen için iyileştirme önerileri", "oneriler"),
                         ("Öğrencinin geri bildirimi", "geri_bildirim")):
        if a.get(alan):
            y += ["", "## " + baslik, "", a[alan].strip()]
    y += ["", "---", "Eğitmenin kendi değerlendirmesi bağımsız bir ölçüm değildir. Kalıcılık ancak sonraki oturumlardaki "
          "yardımsız geri çağırmayla gösterilir."]
    yol = depo().metin_yaz(k["_kimlik"], "raporlar", "%s_%s.md" % (ders, time.strftime("%Y-%m-%d_%H%M")),
                           "\n".join(y) + "\n")
    return metin(uyari_ekle({"durum": "yazıldı", "dosya": yol,
                             "not": "Öğrenciye dosyanın yerini söyle; isterse öğretmenine kendisi gönderir."}, k))


# ---------- Bilgi bankası ----------
_MODEL = None


def anlam_modeli():
    global _MODEL
    if _MODEL is None:
        try:
            _MODEL = bilgi_bankasi.AnlamModeli()
        except Exception as e:  # model bozuksa sözcük aramasıyla sürdür
            _MODEL = type("Yok", (), {"hazir": False, "neden": str(e)})()
    return _MODEL


def ar_bilgi_ara(a):
    sorgu = (a.get("sorgu") or "").strip()
    if not sorgu:
        raise ValueError("sorgu gerekli")
    if a.get("ders"):
        ders_yolu(a["ders"])
    model = anlam_modeli()
    # Değişen dersler her aramadan önce yeniden dizinlenir (değişmeyenler saniyenin altında atlanır).
    bilgi_bankasi.dizinle(model=model, sessiz=True)
    k = max(1, min(int(a.get("k") or 6), 15))
    sonuclar, oz = bilgi_bankasi.ara_ve_dayanak(sorgu, a.get("ders"), a.get("tur"), k, model=model)
    out = {"sorgu": sorgu, "anlam_aramasi": "açık" if model.hazir else "kapalı (yalnız sözcük araması)",
           "dayanak": oz["dayanak"]}
    if DAYANAK_TALIMAT.get(oz["dayanak"]):
        out["talimat"] = DAYANAK_TALIMAT[oz["dayanak"]]
    out["dayanak_olcumu"] = {x: oz[x] for x in ("en_iyi_benzerlik", "en_iyi_kapsam", "sozcuk_eslesen_sayi")}
    out["sonuclar"] = sonuclar
    if not sonuclar:
        out["not"] = "Sonuç yok. Başka sözcüklerle ya da daha kısa bir sorguyla dene; yine yoksa 'kaynaklarda bulamadım' de."
    return metin(out)


DAYANAK_TALIMAT = {
    "yok": "Kaynakta bu soruya dayanak bulunamadı. Ders dışı bilgi verme; ortak kurallar §1'i uygula "
           "(\"Bu sorunun cevabı ders kaynağında yer almıyor.\"). Sorgu çok kısa ya da farklı sözcüklerle yazıldıysa "
           "bir kez başka sözcüklerle yeniden arayabilirsin.",
    "zayif": "Dayanak zayıf. Yalnız parçanın açıkça söylediğini aktar; kalanını 'kaynakta yok' diye ayır.",
}


# ---------- Vakalar ----------
VAKA_TALIMAT = """Vakayı şöyle yürüt (vaka bir sınav değil, klinik akıl yürütme alıştırmasıdır):
- Önce hastayı tanıt: yaş aralığı, şikâyet (hastanın sözleriyle), öykü ve 'acilis: baslangic' bulguları. Başlığı,
  tanıyı ve doğru seçenekleri söyleme. Vaka kurgusalsa bir kez "kurgusal vaka" de; öğretmen onayı yoksa "taslak".
- Düğümleri baslangic'tan başlayarak sırayla aç. Her düğümde önce 'anlat', sonra 'soru'.
- veri düğümü: Öğrenci hangi muayeneyi isterse yalnız o bulguyu ver. gerekli_bulgular'ın hepsi istenmeden geçme;
  eksik kalan için önce ipucu ver. İstenmeyen bulguyu kendiliğinden söyleme.
- karar düğümü: Seçenekleri soru_sor ile tahtada göster, 'dogru' alanını VERME (geri bildirimi sen vereceksin).
  Seçimden sonra o seçeneğin geribildirim'ini söyle. sonuc dogru ise (gerekce_iste false değilse) "Neden?" diye
  gerekçesini iste. yanlis ise sıradaki ipucunu ver ve aynı düğümde yeniden sor. tehlikeli ise nedenini sakin ve
  açık söyle; hastaya ne olacağını anlat. kabul ise neden en iyi seçenek olmadığını söyle ve sonraki'ye geç.
- acik düğümü: Öğrencinin cevabını rubrik ölçütlerine göre sessizce puanla. Sonra hangi ölçütleri karşıladığını
  (adıyla) ve eksik kalanları söyle, ardından ornek_cevap'ı "Öğretmenin örnek cevabı" diye göster (tahtada text).
  Zorunlu ölçüt eksikse bir kez daha denemesini iste.
- Takılma: Aynı düğümde iki denemede ilerleyemezse ya da "bilmiyorum" derse vakayı beklet: "Bunu birlikte
  hatırlayalım" de, takilirsa.bolum'u ders_oku ile oku ve o bölümü 2–4 adımda tahtada kısaca yeniden anlat
  (takilirsa.not'a odaklan). Sonra aynı düğüme dön ve soruyu küçültüp yeniden sor.
- Her cevaptan sonra kayit_yaz ile cevaplar listesine işle: soru (düğüm başlığı), vaka, dugum, hedef, bloom, tur
  (vaka_karar|vaka_acik|vaka_veri), puan, en_yuksek (karar: 1, acik: rubrik toplamı, veri: gerekli bulgu sayısı),
  ilk_deneme, ipucu, tehlikeli, karsilanan_olcutler, eksik_olcutler.
- son düğümünde 'anlat'ı söyle, kapanis.ozet ve ogrenme_noktalari ile toparla, kayit_yaz'a vaka_sonucu yaz
  (yeniden_anlatilan_bolumler dahil).
- Kapanışta bir "Ya şöyle olsaydı?" sorusu sor: vakanın tek bir bulgusunu değiştir (ör. "ateş de olsaydı",
  "lezyon dişetiyle sınırlı kalsaydı") ve tanının ya da tedavinin nasıl değişeceğini sor. Değiştirdiğin bulgu, ders
  kaynağında ya da vaka kartında tabloları birbirinden ayıran bir bulgu olarak geçmeli; kaynakta olmayan senaryo
  kurma. Bir soru yeter; cevabı kayit_yaz içinde uygulama türüyle işle.
- Sonra karnesini görmek isteyip istemediğini sor.
- Görseli göstermeden önce gorsel_bak ile bak; gorsel_aciklama'nın ötesinde yorum yapma."""


def vaka_yolu(ders, vaka):
    if not vaka or any(c in vaka for c in "/\\.") or vaka.startswith("_"):
        raise ValueError("Geçersiz vaka kimliği")
    return ders_yolu(ders, "vakalar", vaka + ".json")


def ar_vakalar(a):
    ders = a.get("ders")
    out = []
    for yol in sorted(glob.glob(ders_yolu(ders, "vakalar", "*.json"))):
        try:
            v = _json_oku(yol)
        except ValueError:
            out.append({"vaka": os.path.basename(yol), "hata": "okunamadı"})
            continue
        out.append({"vaka": v.get("id"), "baslik": v.get("baslik"), "duzey": v.get("duzey"), "sure_dk": v.get("sure_dk"),
                    "hedefler": v.get("hedefler"), "kurgusal": v.get("kurgusal"),
                    "ogretmen_onayi": bool((v.get("ogretmen_onayi") or {}).get("onaylandi"))})
    return metin({"ders": ders, "vakalar": out} if out else {"ders": ders, "vakalar": [], "not": "Bu derste vaka kartı yok."})


def ar_vaka_oku(a):
    import vaka_denetle
    yol = vaka_yolu(a.get("ders"), a.get("vaka"))
    if not os.path.exists(yol):
        raise ValueError("Vaka yok. vakalar aracıyla listeye bak.")
    hatalar, uyarilar, v = vaka_denetle.denetle(yol)
    if hatalar:
        return metin({"durum": "kullanılamaz", "hatalar": hatalar,
                      "not": "Bu vaka kartında hata var; öğrenciye açma. Öğretmen tools/vaka_denetle.py ile düzeltmeli."}, hata=True)
    return metin({"talimat": VAKA_TALIMAT, "vaka": v, "uyarilar": uyarilar or None})


def ar_karne(a):
    ders = a.get("ders")
    k = kayit_yukle(a.get("ogrenci"), ders)
    hedefler = karne_.ders_hedefleri(ders_yolu(ders))
    sonuc = karne_.hesapla(k, hedefler, bugun())
    out = {"karne": sonuc}
    if a.get("yaz"):
        d = egitmen_json(ders) or {}
        baslik = d.get("baslik") or ders_json(ders).get("title")
        out["dosya"] = depo().metin_yaz(k["_kimlik"], "karneler", "%s_%s.md" % (ders, time.strftime("%Y-%m-%d_%H%M")),
                                        karne_.markdown(sonuc, baslik, bugun()))
    out["not"] = ("Öğrenciye karnenin özetini 3–5 cümleyle, cesaretlendirici ve somut söyle: en güçlü hedef, "
                  "geliştirilecek hedef ve bir sonraki adım. Puanı not gibi sunma. İstersen tahtada table ile göster.")
    return metin(uyari_ekle(out, k))


# ---------- Sözlü sınav provası ----------
SOZLU_TALIMAT = """Bu bir sözlü sınav provası. Sen sınav hocasısın; sakin, saygılı ve kısa konuş. Not vermezsin.
- Başta söyle: kaç soru soracağını, her soruda önce sesli düşünmesinin serbest olduğunu, sonunda ayrıntılı
  geri bildirim vereceğini. Sınav sırasında ders anlatma, ipucu verme, cevabı onaylama ya da düzeltme.
- Soruyu tahtaya yaz (tahta: title + text) ve sesli sor; cevabı bekle aracıyla al. Sessiz kalırsa bir kez
  "Acele etme, aklına gelenden başla." de; ikinci sessizlikte bir sonraki soruya geç ve bunu not al.
- Cevap kısa kalırsa gerçek sınavdaki gibi en çok bir izleme sorusu sor ("Neden?", "Ayırıcı tanıda ne düşünürsün?",
  "Bu hastada bunu hangi bulguya dayanarak söylüyorsun?"). İzleme sorusu yeni bilgi vermemeli.
- Her cevabı sessizce rubrikle puanla (rubrik yoksa hedefin Bloom düzeyine göre 0–2). Hazır soru azsa hedefler
  listesinden, hedefin Bloom düzeyinde yeni soru kur; bilgisini ders_oku ya da bilgi_ara ile dersten al ve
  bu soruların senin kurduğun soru olduğunu kayda geçir (soru metninin başına "[eğitmen]" yaz).
- Bütün sorular bitince sınav tarzı geri bildirim ver, her soru için üç kısa satır: ne iyiydi, neyi eksik bıraktı
  (rubrik ölçütüyle), sınavda nasıl daha iyi söylenirdi (yapı: tanım → bulgu → karar → gerekçe; terimi doğru kullan).
  Sonra genel izlenim: akıl yürütmenin düzeni, terim kullanımı, kendinden eminlik. En önemli tek öneriyi söyle.
- Her cevabı kayit_yaz'ın cevaplar alanına tur "sozlu" ile işle (soru, hedef, bloom, puan, en_yuksek,
  karsilanan_olcutler, eksik_olcutler, ilk_deneme: true). Hedef düzeyini (gozlemler) yalnız yardımsız ve
  yeterli cevaplarda yükselt. Bitince öğrenci isterse karne aracını çağır."""


def ar_sozlu_prova(a):
    ders = a.get("ders")
    n = max(1, min(int(a.get("soru_sayisi") or 5), 12))
    d = ders_json(ders)
    eg = egitmen_json(ders) or {}
    hedefler = karne_.ders_hedefleri(ders_yolu(ders))
    oncelik = []
    if a.get("ogrenci"):
        k = kayit_yukle(a.get("ogrenci"), ders)
        kr = karne_.hesapla(k, hedefler, bugun())
        oncelik = list(dict.fromkeys(kr["gelistirilecek"] + kr["tekrar_zamani_gelen"] + kr["yoklanmayan"]))
    maddeler = []
    for sec in d.get("sections", []):
        for st in sec.get("steps", []):
            q = st.get("question") or {}
            if q.get("type") == "open":
                maddeler.append({"kaynak": "ders", "bolum": sec.get("id"), "soru": q.get("prompt"), "hedef": q.get("goal"),
                                 "bloom": q.get("bloom"), "rubrik": q.get("rubric"), "ornek_cevap": q.get("modelAnswer")})
    for yol in sorted(glob.glob(ders_yolu(ders, "vakalar", "*.json"))):
        try:
            v = _json_oku(yol)
        except ValueError:
            continue
        for nd in v.get("dugumler", []):
            if nd.get("tur") == "acik":
                maddeler.append({"kaynak": "vaka", "vaka": v.get("id"), "vaka_ozeti": (v.get("basvuru") or {}).get("sikayet"),
                                 "soru": nd.get("soru"), "hedef": nd.get("hedef"), "bloom": nd.get("bloom"),
                                 "rubrik": nd.get("rubrik"), "ornek_cevap": nd.get("ornek_cevap")})
    sira = {h: i for i, h in enumerate(oncelik)}
    maddeler.sort(key=lambda m: (sira.get(m.get("hedef"), len(sira)),
                                 -BLOOM.index(m["bloom"]) if m.get("bloom") in BLOOM else 0))
    secilen = maddeler[:n]
    return metin({"talimat": SOZLU_TALIMAT, "ders": ders, "soru_sayisi": n, "hazir_sorular": secilen,
                  "eksik_soru": max(0, n - len(secilen)),
                  "oncelikli_hedefler": oncelik[:8],
                  "hedefler": [{"id": h["id"], "baslik": h.get("baslik"), "bloom": h.get("bloom")} for h in hedefler],
                  "ogretmen_notlari": eg.get("ogretmenNotlari")})


# ---------- Dersler arası tekrar ----------
TEKRAR_TALIMAT = """Bu bir tekrar oturumu: öğrencinin bütün derslerinden, zamanı gelen ve zayıf kalan hedefler.
- Listenin başından başla; bir oturumda en çok 5 hedef (~10–15 dk). Hangi derslerden geleceğini kısaca söyle.
- Her hedefte önce anlatma, önce sor (geri çağırma): hedefin Bloom düzeyinde tek bir soru ya da kısa bir vaka
  sahnesi. Cevaptan sonra kısa düzelt; gerekiyorsa ders_oku ile o bölümden 2–3 cümlelik yeniden anlatım yap.
- Açık yanılgısı olan hedefte, o yanılgıyı yoklayan bir soru sor; doğru cevaplarsa yanılgıyı kapat.
- Her cevabı o dersin kaydına kayit_yaz ile işle (ders alanı o dersin kimliği). Böylece sonraki tekrar zamanı güncellenir.
- Bitince hangi hedeflerin bir sonraki tekrara kaldığını söyle."""


def gun_farki(once, sonra):
    return int((time.mktime(time.strptime(sonra, "%Y-%m-%d")) - time.mktime(time.strptime(once, "%Y-%m-%d")) + 3600) // 86400)


def ar_tekrar_listesi(a):
    klasor = ogrenci_klasoru(a.get("ogrenci"))
    b = bugun()
    liste = []
    for yol in sorted(glob.glob(os.path.join(klasor, "*.json"))):
        ders = os.path.splitext(os.path.basename(yol))[0]
        if not os.path.isdir(os.path.join(KOK, "lessons", ders)):
            continue
        try:
            k, _ = kd.guvenli_oku(yol)
            if not k:
                continue
            kr = karne_.hesapla(k, karne_.ders_hedefleri(ders_yolu(ders)), b)
        except (ValueError, KeyError, OSError):
            continue
        hb = {h["id"]: h for h in kr["hedefler"]}
        for hid in dict.fromkeys(kr["tekrar_zamani_gelen"] + kr["gelistirilecek"]):
            h = hb.get(hid, {})
            st = h.get("sonraki_tekrar")
            neden = [x for x, v in (("tekrar zamanı geldi", hid in kr["tekrar_zamani_gelen"]),
                                    ("başarı düşük", hid in kr["gelistirilecek"])) if v]
            liste.append({"ders": ders, "hedef": hid, "baslik": h.get("baslik"), "bloom": h.get("hedef_bloom"),
                          "neden": " · ".join(neden), "basari": h.get("oran"),
                          "gecikme_gun": gun_farki(st, b) if st and st <= b else 0})
        for y, v in (k.get("yanilgilar") or {}).items():
            if v.get("durum") == "acik":
                liste.append({"ders": ders, "yanilgi": y, "neden": "açık yanılgı", "basari": None, "gecikme_gun": 0})
    liste.sort(key=lambda x: (-x["gecikme_gun"], x["basari"] if x["basari"] is not None else 1))
    kartlar = [{k: v for k, v in x.items() if k not in ("sonuclar", "eklenme")}
               for x in ders_sonu.zamani_gelen_kartlar(ogrenci_kimligi(a.get("ogrenci")))]
    if not liste and not kartlar:
        return metin({"ogrenci": a.get("ogrenci"), "liste": [], "not": "Bugün tekrar zamanı gelen ya da zayıf kalan hedef yok."})
    out = {"talimat": TEKRAR_TALIMAT, "ogrenci": a.get("ogrenci"), "liste": liste[:20], "toplam": len(liste)}
    if kartlar:
        out["kartlar"] = kartlar[:10]
        out["kart_talimati"] = KART_TALIMAT
    return metin(out)


KART_TALIMAT = """Tekrar kartları: öğrencinin bitirdiği derslerde zorlandığı sorular (ders arşivde olabilir).
- Kartın sorusunu olduğu gibi sor (seçenek varsa soru_sor ile; vaka sorusunda önce vaka_ozeti'ni bir cümleyle söyle).
- Cevaptan sonra kısa düzelt: ornek_cevap ya da doğru seçenek. Ders arşivdeyse ders_oku/bilgi_ara kullanılamaz;
  karttaki bilgiyle yetin, fazlasını uydurma.
- Her kartın sonucunu tekrar_karti_yaz ile işle (dogru: yardımsız doğru mu). Hedefli tekrardan önce kartları sor."""


# ---------- Ölçme (pilot) ----------
TEST_AD = {"on": "Ön test", "son": "Son test", "gecikmeli": "Gecikmeli test"}

OLCME_TALIMAT = """Bu bir ölçme testi, ders değil. Eğitmen kurallarını test bitene kadar askıya al:
- İpucu, açıklama, doğru/yanlış bilgisi verme; öğrencinin cevabını yorumlama. "Bilmiyorum" geçerli bir cevaptır.
- Önce öğrenciye kısaca söyle: soru sayısı, yaklaşık 15 dakika, not için değil, sonuçlar ve doğru cevaplar sonda.
- Soruları sırayla, tek tek sor. Çoktan seçmeli soruda soru_sor'u 'dogru' ve 'aciklama' OLMADAN, verilen secenekler
  sırasıyla ve etiket ile çağır (ör. "Ön test · 3/12"). Dönen 'secim' değerini not al.
- Kısa yazılı soruda soruyu tahtaya yaz (tahta: title + text) ve öğrencinin cevabını sohbetten ya da bekle ile al.
  Puanı 'olcut'e göre sessizce ver (0, 1, 2); öğrenciye söyleme. olcme_kaydet'te öğrencinin cevabını kelimesi
  kelimesine ham_yanit olarak ver (düzeltme, özetleme yok; konuştuysa bekle'nin ham_metin'i).
- Her sorudan sonra güveni sor: soru_sor ile secenekler ["Tahmin", "Biraz", "Emin"], etiket "Ne kadar eminsin?".
- Bütün sorular bitince olcme_kaydet'i çağır. Sonra puanı ve her yanlış sorunun doğru cevabını kısa, sakin bir dille
  göster; 'emin ama yanlış' olanları özellikle düzelt. Öğrenci testi yarıda bırakırsa yarim_kaldi=true ile kaydet.
- Test sonucu kayit_yaz'daki hedef düzeylerini değiştirmez; ölçme ile öğretim ayrı tutulur."""


def olcme(eg):
    o = (eg or {}).get("olcme") or {}
    return o if o.get("durum") == "onaylandi" and o.get("formlar") else None


def olcme_ozeti(eg):
    o = olcme(eg)
    if not o:
        return {"durum": ((eg or {}).get("olcme") or {}).get("durum", "yok"),
                "not": "Onaylı ölçme sorusu yok; test yapma."}
    return {"durum": "onaylandi", "plan": o.get("plan"), "puanlama": o.get("puanlama"),
            "soru_sayisi": {f: len(v) for f, v in o["formlar"].items()},
            "not": "Soruları burada görmüyorsun; testi olcme_testi aracıyla başlat."}


def olcme_sirasi(k, eg):
    o = olcme(eg)
    if not o:
        return None
    yapilan = {t.get("tur"): t for t in k.get("testler", []) if not t.get("yarim_kaldi")}
    if "on" not in yapilan:
        if k.get("oturumlar"):
            return {"oneri": None, "not": "Ön test yapılmadan derse başlanmış; ön test artık önerilmez."}
        return {"oneri": "on", "not": "İlk oturum: derse başlamadan önce isteğe bağlı ön testi öner (yaklaşık 15 dk). "
                                       "Öğrenci istemezse doğrudan derse geç."}
    if "son" not in yapilan:
        return {"oneri": None, "not": "Son test, öğrenci bütün hedefleri çalışıp dersi bitirdiğinde ya da kendisi "
                                       "isterse önerilir (olcme_testi tur=son)."}
    if "gecikmeli" not in yapilan:
        gun = int((o.get("plan") or {}).get("gecikmeli_en_erken_gun", 21))
        hazir = gun_ekle(yapilan["son"].get("tarih", bugun()), gun)
        if bugun() >= hazir:
            return {"oneri": "gecikmeli", "not": "Gecikmeli test zamanı geldi; oturumun başında, tekrar sorularından "
                                                  "ÖNCE öner."}
        return {"oneri": None, "not": "Gecikmeli test %s tarihinden itibaren yapılabilir." % hazir}
    return {"oneri": None, "not": "Üç test de tamamlandı."}


def karisik_sira(ogrenci, ders, tur, no, n):
    tohum = hashlib.sha256(("%s|%s|%s|%s" % (ogrenci.strip().lower(), ders, tur, no)).encode("utf-8")).hexdigest()
    sira = list(range(n))
    random.Random(int(tohum[:16], 16)).shuffle(sira)
    return sira


def olcme_grubu(k, o):
    """Çapraz form tasarımında öğrencinin grubu: 1 → plan olduğu gibi (ör. A→B→A), 2 → formlar yer değiştirir
    (B→A→B). Grup bir kez belirlenir ve kayda yazılır. Öğrenci numarasının son hanesi varsa tek/çift (sınıfta
    yaklaşık yarı yarıya ve öğretmen tarafından denetlenebilir), yoksa kimlikten türetilen sabit bir sayı."""
    if not (o.get("plan") or {}).get("capraz") or len(o.get("formlar") or {}) != 2:
        return None
    if k.get("olcme_grubu") in (1, 2):
        return k["olcme_grubu"]
    bilgi = depo().defter()["ogrenciler"].get(k.get("_kimlik") or k.get("ogrenci_kimligi")) or {}
    ayirt = "".join(c for c in str(bilgi.get("ayirt") or "") if c.isdigit())
    if ayirt:
        g = 1 if int(ayirt[-1]) % 2 == 0 else 2
    else:
        g = 1 + int(hashlib.sha256(tohum(k).strip().lower().encode("utf-8")).hexdigest()[:8], 16) % 2
    k["olcme_grubu"] = g
    return g


def test_formu(a, k=None):
    ders, ogr, tur = a.get("ders"), (a.get("ogrenci") or "").strip(), a.get("tur")
    if not ogr:
        raise ValueError("ogrenci gerekli")
    if tur not in TEST_AD:
        raise ValueError("tur: on, son ya da gecikmeli olmalı")
    eg = egitmen_json(ders)
    o = olcme(eg)
    if not o:
        raise ValueError("Bu derste öğretmenin onayladığı ölçme sorusu yok; test yapılamaz.")
    form = (o.get("plan") or {}).get(tur)
    if form not in o["formlar"]:
        raise ValueError("Bu test türü için form tanımlı değil: %s" % tur)
    if k is not None and olcme_grubu(k, o) == 2:
        a_, b_ = sorted(o["formlar"])
        form = b_ if form == a_ else a_
    return eg, o, form, ogr


def ar_olcme_testi(a):
    test_formu(a)  # önce girdileri denetle
    tur, ders = a["tur"], a["ders"]
    k = kayit_yukle(a["ogrenci"].strip(), ders)
    yeni_grup = "olcme_grubu" not in k
    eg, o, form, ogr = test_formu(a, k)
    if yeni_grup and k.get("olcme_grubu"):
        kayit_kaydet(k)
    ogr = tohum(k)
    uyari = list(k.get("_uyarilar") or [])
    if any(t.get("tur") == tur and not t.get("yarim_kaldi") for t in k.get("testler", [])):
        uyari.append("Bu öğrenci %s testini daha önce tamamladı; tekrarı araştırmada ayrı sayılır." % TEST_AD[tur].lower())
    sira_onerisi = olcme_sirasi(k, eg) or {}
    if sira_onerisi.get("oneri") not in (None, tur):
        uyari.append("Sıradaki önerilen test: %s." % TEST_AD.get(sira_onerisi["oneri"]))
    sorular = []
    for i, s in enumerate(o["formlar"][form], 1):
        x = {"sira": "%d/%d" % (i, len(o["formlar"][form])), "no": s["no"], "hedef": s.get("hedef"),
             "tur": s["tur"], "soru": s["soru"]}
        if s["tur"] == "secmeli":
            sira = karisik_sira(ogr, ders, tur, s["no"], len(s["secenekler"]))
            x["secenekler"] = [s["secenekler"][j] for j in sira]
        else:
            x["olcut"] = s.get("olcut")
        sorular.append(x)
    out = {"test": TEST_AD[a["tur"]], "form": form, "soru_sayisi": len(sorular), "puanlama": o.get("puanlama"),
           "talimat": OLCME_TALIMAT, "sorular": sorular}
    if uyari:
        out["uyarilar"] = uyari
    return metin(out)


def ar_olcme_kaydet(a):
    test_formu(a)
    tur, ders = a["tur"], a["ders"]
    k = kayit_yukle(a["ogrenci"].strip(), ders)
    eg, o, form, ogr = test_formu(a, k)
    ogr = tohum(k)
    sorular = {s["no"]: s for s in o["formlar"][form]}
    toplam = sum(1 if s["tur"] == "secmeli" else 2 for s in sorular.values())
    ayrinti, uyarilar, yanilgilar = [], [], []
    puan = emin_yanlis = 0
    for y in a.get("yanitlar") or []:
        s = sorular.get(y.get("no"))
        if not s:
            uyarilar.append("Bilinmeyen soru: %s" % y.get("no"))
            continue
        r = {"no": s["no"], "hedef": s.get("hedef"), "guven": y.get("guven")}
        if s["tur"] == "secmeli":
            sec = y.get("secim")
            if not isinstance(sec, int) or not 0 <= sec < len(s["secenekler"]):
                r.update(puan=0, cevap=None)
            else:
                asil = karisik_sira(ogr, ders, tur, s["no"], len(s["secenekler"]))[sec]
                r.update(puan=1 if asil == s["dogru"] else 0, cevap=s["secenekler"][asil])
                yid = (s.get("yanilgi_secenekleri") or {}).get(str(asil))
                if yid:
                    r["yanilgi"] = yid
                    yanilgilar.append(yid)
            r["dogru_cevap"] = s["secenekler"][s["dogru"]]
            tam = r["puan"] == 1
        else:
            p = y.get("puan")
            r.update(puan=p if p in (0, 1, 2) else 0, cevap=y.get("yanit_ozet"))
            # Ham cevap: Claude'un puanını sonradan körlemeli insan puanıyla karşılaştırabilmek için (araştırma).
            if (y.get("ham_yanit") or "").strip():
                r["ham_yanit"] = y["ham_yanit"].strip()
            else:
                uyarilar.append("%s: ham_yanit eksik; öğrencinin cevabını kelimesi kelimesine ver" % s["no"])
            tam = r["puan"] == 2
            if r["puan"] == 0 and s.get("yanilgi") and y.get("yanilgi_secildi"):
                yanilgilar.append(s["yanilgi"])
        if y.get("guven") == "emin" and not tam:
            r["emin_ama_yanlis"] = True
            emin_yanlis += 1
        puan += r["puan"]
        ayrinti.append(r)
    eksik = [n for n in sorular if n not in {r["no"] for r in ayrinti}]
    kayit = {"tur": tur, "form": form, "grup": k.get("olcme_grubu"), "tarih": bugun(), "saat": time.strftime("%H:%M"), "puan": puan,
             "toplam": toplam, "emin_ama_yanlis": emin_yanlis, "secilen_yanilgilar": sorted(set(yanilgilar)),
             "yarim_kaldi": bool(a.get("yarim_kaldi") or eksik), "yanitlar": ayrinti}
    if eksik:
        kayit["cevapsiz"] = eksik
    k.setdefault("testler", []).append(kayit)
    yol = kayit_kaydet(k)
    out = {"durum": "kaydedildi", "dosya": yol, "test": TEST_AD[tur], "puan": puan,
           "toplam": toplam, "emin_ama_yanlis": emin_yanlis, "secilen_yanilgilar": kayit["secilen_yanilgilar"],
           "yanlislar": [{"no": r["no"], "cevap": r.get("cevap"), "dogru_cevap": r.get("dogru_cevap"),
                          "olcut": sorular[r["no"]].get("olcut"), "emin_ama_yanlis": r.get("emin_ama_yanlis", False)}
                         for r in ayrinti if r["puan"] < (1 if sorular[r["no"]]["tur"] == "secmeli" else 2)],
           "not": "Şimdi öğrenciye puanı ve yanlışların doğru cevabını kısa ve sakin göster; emin ama yanlış olanları "
                  "özellikle düzelt. Sonra derse ya da molaya geç."}
    if eksik:
        out["cevapsiz"] = eksik
    if uyarilar:
        out["uyarilar"] = uyarilar
    return metin(uyari_ekle(out, k))


# ---------- Kayıtları aktarma (yalnız bu bilgisayarda; hiçbir yere gönderilmez) ----------
def ar_kayit_disa_aktar(a):
    r = kayit_aktar.disa_aktar(depo(), a.get("ogrenci"), a.get("cikti") or None)
    r["not"] = ("Öğrenciye dosyanın yerini söyle. Bu dosyayı başka bilgisayara (USB bellek, e-posta) kendisi taşır; "
                "orada kayit_ice_aktar ile ya da tools/kayit_aktar.py ice ile içe alır. Dosyada adı vardır; "
                "yalnız güvendiği yere koysun.")
    return metin(r)


def ar_kayit_ice_aktar(a):
    yol = os.path.abspath(os.path.expanduser((a.get("dosya") or "").strip().strip('"')))
    if not os.path.isfile(yol):
        raise ValueError("Dosya bulunamadı: %s" % yol)
    r = kayit_aktar.ice_aktar(depo(), yol, bool(a.get("uzerine")))
    r["not"] = "Sonraki araçlarda ogrenci alanına bu kimliği yaz: %s" % r["kimlik"]
    return metin(r)


def ar_kayit_anonim_aktar(a):
    r = kayit_aktar.anonim(depo(), a.get("ogrenciler") or None, a.get("dosyalar") or None,
                           bool(a.get("deneme_dahil")), a.get("cikti") or veri_yeri.masaustu(),
                           ham_yanitlar=bool(a.get("ham_yanitlar")))
    return metin({"dosya": r["dosya"], "ogrenci_sayisi": r["ogrenci_sayisi"],
                  "haric_tutulan_deneme": r["haric_tutulan_deneme"],
                  "not": ("Dosyada ad, kimlik ve ayırt edici yoktur; kodlar rastgeledir. Ölçme testlerinin kısa yazılı "
                          "cevapları ham metin olarak VAR: paylaşmadan önce içinde ad ya da kimlik geçmediğini kontrol et.")
                  if a.get("ham_yanitlar") else
                  "Dosyada ad, kimlik, ayırt edici ve serbest metin yoktur; kodlar rastgeledir."})


# ---------- Tahta ----------
def _ayni_klasor(a, b):
    try:
        return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))
    except (TypeError, ValueError):
        return False


def baska_kurulum_mu(d):
    """Açık sunucu başka bir KlinikKoç kurulumundan mı? Eski sürüm sunucu yolunu söylemez: o zaman None."""
    kok = (d or {}).get("kok")
    if not kok:
        return None
    return None if _ayni_klasor(kok, KOK) else kok


def ar_ses_yeniden_baslat(_):
    if not sunucu_acik():
        return metin({"durum": "sunucu kapalı", "not": "Önce tahtayi_ac."})
    try:
        return metin(istek("ses_yeniden", {}, zaman=10))
    except urllib.error.HTTPError as e:
        return metin({"durum": "desteklenmiyor", "hata": "Açık sunucu bu komutu bilmiyor (%s); sunucu penceresini "
                                                         "kapatıp tahtayi_ac'ı yeniden çağır." % e.code}, hata=True)


def ar_tahtayi_ac(_):
    d = sunucu_acik()
    yabanci = baska_kurulum_mu(d)
    if d and (yabanci or "kok" not in d):
        # Aynı bilgisayarda iki kurulum: açık sunucu başka klasörden. Dersler, görseller ve ses karışmasın diye
        # onu kapatıp bu kurulumun sunucusunu açarız. Eski sürüm sunucu kapatılamazsa kullanıcıya söyleriz.
        try:
            istek("kapat", {}, zaman=5)
            for _ in range(20):
                time.sleep(0.5)
                if not sunucu_acik():
                    break
        except Exception:
            pass
        d = sunucu_acik()
        if d:
            return metin({"durum": "başka kurulum", "hata": (
                "Bu bilgisayarda açık olan KlinikKoç sunucusu başka bir kurulumdan çalışıyor%s; bu kurulum: %s. "
                "Kullanıcıdan o kurulumun siyah sunucu penceresini (ya da BASLAT penceresini) kapatmasını iste, "
                "sonra tahtayi_ac'ı yeniden çağır." % (" (%s)" % yabanci if yabanci else " (eski bir sürüm)", KOK))},
                hata=True)
    if not d:
        sunucuyu_baslat()
        for _ in range(30):
            time.sleep(0.5)
            d = sunucu_acik()
            if d:
                break
        if not d:
            return metin({"durum": "hata", "hata": "Yerel sunucu açılamadı. Bilgisayarda şunu çalıştırın: "
                                                    "python tools/sunucu.py --sayfa canli.html"}, hata=True)
    if not d.get("bagli"):
        webbrowser.open("http://localhost:%d/canli.html" % PORT)
        for _ in range(40):
            time.sleep(0.5)
            d = sunucu_acik() or {}
            if d.get("bagli"):
                break
    if not d.get("bagli"):
        return metin({"durum": "bekleniyor", "not": "Tarayıcıda canli.html açılıyor; birkaç saniye sonra tekrar dene."})
    return metin({"durum": "hazır", "tahta": d.get("sayfa"), "ses": d.get("ses"), "dikte": dikte_durumu(d),
                  "not": "Tahta açık. 'ses' alanı gerçekten kullanılacak sesi söyler (yedek sese düşüldüyse kullanıcıya bir "
                         "cümleyle söyle). Kullanıcı ilk açılışta sayfada 'başlat' düğmesine bir kez dokunmalı. Tarayıcı sesi "
                         "engellerse anlatım o cümlede bekler ve tahta_durumu'nda sayfa.ses_engelli true olur: kullanıcıdan "
                         "ekrandaki 'Sesi açmak için dokunun' düğmesine basmasını iste."})


def dikte_durumu(d):
    """Mikrofonun hangi tanıyıcıyla çalıştığı ve Duyu'nun kurulum durumu."""
    out = {}
    sayfa = d.get("sayfa") if isinstance(d.get("sayfa"), dict) else {}
    if sayfa.get("dikte"):
        out["motor"] = sayfa["dikte"]
    try:
        r = urllib.request.Request(ADRES + "/api/duyu/durum")
        with urllib.request.urlopen(r, timeout=10) as y:
            du = json.loads(y.read().decode("utf-8"))
    except Exception:
        du = None
    if du is None:
        out["duyu"] = "bilinmiyor (sunucu eski sürüm olabilir)"
    elif not du.get("kurulu"):
        out["duyu"] = "kurulu değil"
        out["not"] = ("Mikrofon tarayıcının tanıyıcısıyla çalışıyor; alan terimlerini bozabilir. Daha doğru tanıma için "
                      "kullanıcıya bir kez şu komutu çalıştırmasını önerebilirsin: " + du.get("komut", ""))
    else:
        out["duyu"] = "hazır" if du.get("hazir") else ("kurulu" if du.get("model_indirildi")
                                                       else "kurulu, model ilk kullanımda indirilecek")
    out["terim_duzeltme"] = ("Dikteyle gelen sözlerde 'metin' terim sözlüğüyle düzeltilmiştir; 'ham_metin' tanıyıcının "
                             "ilk çıktısıdır. İkisi farklıysa ve anlam belirsizse öğrenciye kısaca sor.")
    return out


def ar_tahta(a):
    adimlar = a.get("adimlar") or []
    if not isinstance(adimlar, list) or not adimlar:
        raise ValueError("adimlar boş")
    videolari_coz(adimlar, a.get("ders"))
    komut = {"tur": "adimlar", "adimlar": adimlar}
    if a.get("ders"):
        komut["ders"] = a["ders"]
    return metin(gonder(komut, a.get("bekle", True) is not False))


def ar_soru_sor(a):
    komut = {"tur": "soru", "soru": a.get("soru"), "secenekler": a.get("secenekler")}
    for k in ("dogru", "aciklama", "anlat", "etiket"):
        if a.get(k) is not None:
            komut[k] = a[k]
    return metin(gonder(komut))


def ar_tahta_durumu(a):
    if a.get("no"):
        try:
            return metin(_suruyor_notu(uzun_bekle(int(a["no"]))))
        except urllib.error.URLError:
            return metin({"durum": "bağlı değil"})
    try:
        return metin(istek("durum?al=1", zaman=5))
    except Exception:
        return metin({"durum": "sunucu kapalı", "not": "tahtayi_ac ile aç."})


VIDEO_UZANTI = (".mp4", ".m4v", ".webm", ".ogv", ".mov")


def ders_videolari(ders):
    """Kimlik → {src | youtube, baslik, ...}. Klasördeki dosyalar (lessons/<ders>/videolar/) ve tanımlı bağlantılar.
    İsteğe bağlı lessons/<ders>/videolar/videolar.json: {"dosya.mp4": {"baslik", "aciklama", "credit"}}."""
    out = {}
    klasor = ders_yolu(ders, "videolar")
    bilgi = {}
    yol = os.path.join(klasor, "videolar.json")
    if os.path.exists(yol):
        try:
            with open(yol, encoding="utf-8") as f:
                bilgi = json.load(f) or {}
        except ValueError:
            bilgi = {}
    if os.path.isdir(klasor):
        for ad in sorted(os.listdir(klasor)):
            if not ad.lower().endswith(VIDEO_UZANTI):
                continue
            kimlik = os.path.splitext(ad)[0]
            b = bilgi.get(ad) or bilgi.get(kimlik) or {}
            out[kimlik] = dict(b, dosya=ad, src="/lessons/%s/videolar/%s" % (ders, urllib.request.quote(ad)),
                               boyut_mb=round(os.path.getsize(os.path.join(klasor, ad)) / 1e6, 1), internet=False)
    tanimli = dict((ders_json_ham(ders) or {}).get("videos") or {})
    tanimli.update((egitmen_json(ders) or {}).get("videolar") or {})
    for kimlik, v in tanimli.items():
        v = dict(v)
        if v.get("src") and not v["src"].startswith(("/", "http")):
            v["src"] = "/lessons/%s/%s" % (ders, v["src"])
        v["internet"] = bool(v.get("youtube") or str(v.get("src", "")).startswith("http"))
        out[kimlik] = v
    return out


def ders_json_ham(ders):
    yol = ders_yolu(ders, "ders.json")
    if not os.path.exists(yol):
        return None
    with open(yol, encoding="utf-8") as f:
        return json.load(f)


def ar_videolar(a):
    v = ders_videolari(a.get("ders"))
    if not v:
        return metin({"ders": a.get("ders"), "videolar": {},
                      "not": "Bu dersin videosu yok. Öğretmen videoları lessons/%s/videolar/ klasörüne koyabilir; "
                             "kullanıcı bir YouTube bağlantısı verirse {type:'video', youtube:'<bağlantı>'} ile oynatılır." % a.get("ders")})
    return metin({"ders": a.get("ders"), "videolar": v})


def videolari_coz(adimlar, ders):
    """tahta aracındaki video komutlarında 'video' kimliğini dosya yoluna ya da YouTube bağlantısına çevirir."""
    liste = None
    for adim in adimlar:
        for c in (adim or {}).get("komutlar") or []:
            if not isinstance(c, dict) or c.get("type") != "video" or c.get("src") or c.get("youtube"):
                continue
            if not c.get("video"):
                raise ValueError("video komutunda video, youtube ya da src gerekli")
            if not ders:
                raise ValueError("Ders videosu için tahta aracına ders alanını da ver")
            if liste is None:
                liste = ders_videolari(ders)
            v = liste.get(c["video"])
            if not v:
                raise ValueError("Video yok: %s. Bu dersin videoları: %s" % (c["video"], ", ".join(liste) or "yok"))
            for k in ("src", "youtube", "baslangic", "bitis"):
                if v.get(k) is not None and c.get(k) is None:
                    c[k] = v[k]
            if not c.get("caption") and (v.get("baslik") or v.get("caption")):
                c["caption"] = v.get("baslik") or v.get("caption")
            if v.get("credit"):
                c["credit"] = v["credit"]
            c.pop("video", None)


def ar_anlatima_devam(a):
    birak = a.get("birak") is True
    r = gonder({"tur": "devam", "birak": birak}, bekle=True)
    no = r.get("anlatim_no")
    if birak or r.get("durum") not in ("devam_ediyor", "zaten_suruyor") or not no:
        return metin(r)
    # Anlatım sürüyor: bitişini tahta aracındaki gibi bekle (kullanıcı yine konuşursa hemen döner).
    try:
        s = _suruyor_notu(uzun_bekle(int(no)))
    except urllib.error.URLError:
        return metin(r)
    s["devam"] = r.get("durum")
    return metin(s)


SESSIZ_SINIR_SN = 600  # kullanıcı bu kadar süre hiç konuşmazsa dinleme döngüsü bırakılır
UYANDIRMALI_SINIR_SN = 180  # otomatik uyandırma açıksa Claude dinlemeyi daha erken bırakabilir: söz sohbete düşer
_sessizlik = {"bas": None}


def ar_bekle(a):
    """Tek bekleme aracı: no verilirse anlatımın/sorunun bitmesini, verilmezse öğrencinin sözünü bekler."""
    if a.get("no"):
        return ar_tahta_durumu({"no": a["no"]})
    return ar_dinle(a)


def ar_dinle(a):
    bas = time.time()
    try:
        y = uzun_bekle(None)
        if isinstance(y, dict) and y.get("durum") == "sessiz":
            simdi = time.time()
            if _sessizlik["bas"] is None:
                _sessizlik["bas"] = bas
            gecen = int(simdi - _sessizlik["bas"])
            uyandirmali = bool(y.pop("uyandirma", False))
            sinir = UYANDIRMALI_SINIR_SN if uyandirmali else SESSIZ_SINIR_SN
            y["sessiz_sn"] = gecen
            y["devam"] = gecen < sinir
            if y["devam"]:
                y["not"] = "Kullanıcı ara vermiş olabilir; hemen yeniden bekle çağır."
            else:
                _sessizlik["bas"] = None
                if uyandirmali:
                    y["not"] = ("Uzun sessizlik: beklemeyi bırak, sohbete tek cümlelik kısa bir not yaz. Otomatik uyandırma "
                                "açık: öğrenci tahtada konuşunca sözü bu sohbete 'Tahtadan sesli soru: ...' diye kendiliğinden "
                                "düşer; ona tahtada cevap ver.")
                else:
                    y["not"] = ("Uzun sessizlik: beklemeyi bırak. Sohbete kısa not yaz: tahtaya dönünce mikrofona basıp "
                                "konuşsun ya da buraya 'tahtaya bak' yazsın.")
        else:
            _sessizlik["bas"] = None
            if isinstance(y, dict):
                y.pop("uyandirma", None)
        return metin(y)
    except urllib.error.URLError:
        return metin({"durum": "bağlı değil", "hata": "Yerel tahta sunucusu kapalı. Önce tahtayi_ac aracını çağır."})


def ar_durdur(_):
    return metin(gonder({"tur": "dur"}, bekle=True))


# ---------- Makaleler (ders paketindeki makale listesi) ----------
def ar_makaleler(a):
    ders = a.get("ders")
    if not ders:
        return metin({"dersler": makale_bulucu.makaleli_dersler()})
    ders_yolu(ders)
    out = makale_bulucu.ozet(ders)
    if a.get("ac"):
        if not sunucu_acik():
            sunucuyu_baslat()
            for _ in range(30):
                time.sleep(0.5)
                if sunucu_acik():
                    break
        webbrowser.open("http://localhost:%d/makaleler.html?ders=%s" % (PORT, ders))
        out["sayfa"] = "Makaleler sayfası tarayıcıda açıldı."
    if not out["pdf_okuyucu"]:
        out["uyari"] = "PDF okuyucu kurulu değil; inen makaleler metne çevrilemez. KUR dosyasını yeniden çalıştırın."
    eksik = [m["kisa"] for m in out["makaleler"] if m["durum"] in ("eksik", "hata")]
    if eksik:
        out["not"] = ("Eksik makaleler aramada yok. Öğrenciye söyle; makaleler sayfasında yayıncı bağlantısı var, "
                      "PDF'i indirip sayfaya sürükleyebilir.")
    return metin(out)


def ar_ders_paketi_ekle(a):
    yol = (a.get("zip") or "").strip().strip('"')
    if not yol:
        sayfayi_ac("makaleler.html#paketKutu")
        return metin({"durum": "sayfa açıldı", "not": "Ders paketleri sayfası tarayıcıda açıldı. Öğrenciden zip dosyasını "
                                                      "'Ders paketi ekle' alanına sürüklemesini iste."})
    yol = os.path.expanduser(yol)
    if not os.path.isfile(yol):
        raise ValueError("Dosya bulunamadı: %s. Dosyanın tam yolunu sor ya da zip vermeden çağırıp sayfayı aç." % yol)
    try:
        r = ders_paketi.yukle(yol, bool(a.get("uzerine")))
    except FileExistsError as e:
        return metin({"durum": "zaten kurulu", "not": "%s Öğrenci isterse uzerine: true ile yeniden çağır." % e})
    out = {"durum": "kuruldu", "ders": r["ders"], "baslik": r["baslik"], "makale": r["makale"]}
    if r["makale"]:
        out["makaleler"] = makale_bulucu.arka_planda_hazirla(r["ders"])
        out["not"] = ("Makaleler arka planda aranıyor; birkaç dakika sonra makaleler aracıyla durumu kontrol et. "
                      "Eksik kalanları öğrenci yayıncı sayfasından indirip ekleyebilir.")
    return metin(out)


def ar_makale_bul(a):
    ders = a.get("ders")
    ders_yolu(ders)
    if not makale_bulucu.kaynaklar(ders):
        return metin({"durum": "makale yok", "not": "Bu dersin paketinde makale listesi yok."})
    out = makale_bulucu.arka_planda_hazirla(ders)
    out["not"] = "Makaleler arka planda indiriliyor. Birkaç dakika sonra makaleler aracıyla durumu kontrol et."
    return metin(out)


def ar_makale_ekle(a):
    ders = a.get("ders") or makale_bulucu.KENDI
    ders_yolu(ders)
    yol = os.path.expanduser(a.get("dosya") or "")
    if not os.path.isfile(yol):
        raise ValueError("Dosya bulunamadı: %s" % yol)
    with open(yol, "rb") as f:
        veri = f.read()
    return metin(makale_bulucu.elle_ekle(ders, veri, os.path.basename(yol), a.get("kaynak") or None))


def ar_sihirbaz_oku(a):
    if not a.get("ders"):
        return metin({"taslaklar": sihirbaz.liste(),
                      "not": "Öğretmen yeni dersi sihirbaz sayfasında açar: http://localhost:%d/sihirbaz.html" % PORT})
    return metin(sihirbaz.claude_icin_malzeme(a["ders"]))


def ar_sihirbaz_oner(a):
    ders = a.get("ders")
    o = sihirbaz.oneri_yaz(ders, {k: a.get(k) for k in sihirbaz.ONERI_TURLERI}, kim="claude")
    out = {"durum": "yazıldı", "sayilar": {k: len(v) for k, v in o.items() if isinstance(v, list)},
           "not": "Öneriler sihirbaz sayfasında öğretmenin onayını bekliyor. Öğretmene bunu söyle."}
    if a.get("ac"):
        if not sunucu_acik():
            sunucuyu_baslat()
            for _ in range(30):
                time.sleep(0.5)
                if sunucu_acik():
                    break
        webbrowser.open("http://localhost:%d/sihirbaz.html?ders=%s" % (PORT, ders))
    return metin(out)


# ---------- Ders sonu: tamamlama raporu, tekrar kartları, depolama, arşiv ----------
def sayfayi_ac(adres):
    if not sunucu_acik():
        sunucuyu_baslat()
        for _ in range(30):
            time.sleep(0.5)
            if sunucu_acik():
                break
    webbrowser.open("http://localhost:%d/%s" % (PORT, adres))


def depolama_ozeti():
    d = ders_sonu.depolama()
    return {"kullanilan": ders_sonu.okunur_boyut(d["toplam_bayt"]), "sinir_gb": d["sinir_gb"], "asildi": d["asildi"],
            "dersler": [{"ders": x["ders"], "baslik": x["baslik"], "boyut": ders_sonu.okunur_boyut(x["toplam"]),
                         "son_acilma": x["son_acilma"], "tamamlandi": x["tamamlandi"],
                         **({"programla_gelir": True} if x["yerlesik"] else {})} for x in d["dersler"]],
            "arsiv_onerisi": d["arsiv_adaylari"][:5],
            "arsivdekiler": [{"ders": a["ders"], "baslik": a.get("baslik"), "tarih": a.get("tarih"), "dosya": a.get("dosya")}
                             for a in d["arsiv"]]}


DEPOLAMA_NOTU = ("Ders verisi sınırı aşıldı. Öğrenciye kısaca söyle ve 'Hangi dersleri arşive kaldıralım?' diye sor; "
                 "dersleri boyutları ve son açılma tarihleriyle say (öneri: en uzun süredir açılmayanlar). Arşivleme "
                 "otomatik değildir: yalnız öğrencinin seçtiği dersi ders_arsivle ile kaldır. PDF'ler ve tekrar kartları "
                 "kalır; ders istenince geri yüklenir. İsterse sınırı depolama sayfasından büyütebilir (depolama, ac: true).")


def ar_ders_bitir(a):
    ders = a.get("ders")
    ders_yolu(ders)
    kimlik = ogrenci_kimligi(a.get("ogrenci"))
    r = ders_sonu.tamamlama_raporu(kimlik, ders, a.get("ogrenci_notu"))
    tespit = degerlendirme.claude_notu(kimlik, ders, a.get("claude_tespitleri") or [])
    oneri = ana_ekran.oneri_ekle(ders, a.get("program_onerileri") or []) if a.get("program_onerileri") else None
    out = {"durum": "tamamlandı", "rapor": r["dosya"], "tekrar_karti": r["kart_sayisi"],
           "genel_basari": karne_.yuzde(r["genel_basari"]), "gelistirilecek": r["gelistirilecek"],
           "yoklanmayan": r["yoklanmayan"], "claude_tespiti": len(tespit),
           "not": "Öğrenciye raporun yerini ve 3–4 cümlelik özetini söyle (en güçlü hedef, zorlandığı konu, tekrar kartı "
                  "sayısı). Ders yerinde kalır. Tekrar kartları zamanı gelince tekrar_listesi'nde çıkar."}
    if a.get("form", True):
        sayfayi_ac("degerlendirme.html?ders=%s&ogrenci=%s" % (urllib.parse.quote(ders), urllib.parse.quote(kimlik)))
        out["form"] = "Değerlendirme formu tarayıcıda açıldı."
        out["not"] += (" Sonra kısaca söyle: tarayıcıda 2–3 dakikalık bir değerlendirme formu açıldı; isteğe bağlı ve "
                       "adsız. Kendi tespitlerin formun ikinci bölümünde; göndermeden önce görüp çıkarabilir. Göndermek "
                       "öğrenciye kalmış.")
    if oneri:
        out["program_onerisi"] = oneri
    else:
        out["program_onerisi_iste"] = PROGRAM_ONERISI_NOTU
    d = ders_sonu.depolama()
    if d["asildi"]:
        out["depolama"] = depolama_ozeti()
        out["depolama"]["not"] = DEPOLAMA_NOTU
    return metin(out)


PROGRAM_ONERISI_NOTU = (
    "Şimdi program_onerisi aracını çağır: bu derste PROGRAMIN KENDİSİNDE eksik ya da zor bulduğun 1–3 somut şeyi yaz "
    "(ör. gereken çizim şablonu yoktu, öğrencinin sorusu kaynakta bulunamadı, bir araç hata verdi ya da yavaştı, "
    "öğrenci bir düğmeyi bulamadı). Öğrencinin adını, başarısını ya da kişisel bilgisini yazma. Gerçekten bir şey "
    "yoksa çağırma. Öneriler yalnız bu bilgisayarda durur; kullanıcı isterse kendisi gönderir.")


def ar_program_onerisi(a):
    ders = a.get("ders")
    if ders:
        ders_yolu(ders)
    r = ana_ekran.oneri_ekle(ders, a.get("oneriler") or [])
    r["not"] = ("Kaydedildi (yalnız bu bilgisayarda; ana ekranda 'Geri bildirim' bölümünde görünür). Kullanıcıya tek "
                "cümleyle söyle: programı geliştirmek için birkaç not yazdın, isterse ana ekrandan görüp gönderebilir.")
    return metin(r)


def ar_calisma_secimi(_):
    s = ana_ekran.secim_metni()
    if not s["dersler"] and not s["pdfler"]:
        return metin({"secim": None, "not": "Ana ekranda işaretlenmiş bir ders ya da PDF yok. Öğrenciye hangi dersi "
                                            "çalışmak istediğini sor; dersler aracıyla listeyi görebilirsin."})
    ana = s["dersler"][0] if s["dersler"] else makale_bulucu.KENDI
    diger = s["dersler"][1:]
    out = {"dersler": [{"ders": d, "baslik": b} for d, b in zip(s["dersler"], s["ders_adlari"])],
           "kendi_pdfleri": s["pdf_adlari"], "secim_tarihi": s["tarih"], "ilk_ders": ana}
    out["not"] = (
        "Öğrenci ana ekranda bunları işaretledi. egitmen_hazirla(ders='%s') ile başla ve tahtayi_ac çağır. " % ana
        + ("Sonra sırayla öteki dersler: %s (her biri için yeniden egitmen_hazirla). " % ", ".join(diger) if diger else "")
        + ("Öğrencinin kendi PDF'leri 'kendi-makalelerim' dersindedir: bilgi_ara(ders='kendi-makalelerim') ile "
           "onlardan da yararlan ve hangi makaleden aldığını söyle. Yalnız işaretlenen makaleleri kullan: %s. "
           % ", ".join(s["pdf_adlari"]) if s["pdfler"] else "")
        + "Birden çok konu seçildiyse önce kısa bir çalışma planı söyle (hangi sırayla, kaç dakika).")
    return metin(out)


def _makale_pdf(ders, kaynak):
    ders_yolu(ders)
    pdf = makale_sekil._pdf_yolu(ders, kaynak)
    if not pdf:
        raise ValueError("Bu makalenin PDF'i bu bilgisayarda hazır değil (%s). Önce makaleler sayfasından ekleyin." % kaynak)
    if not makale_sekil.cizici_var():
        raise ValueError("Şekil çizici (pypdfium2) kurulu değil: KUR dosyasını yeniden çalıştırın.")
    return pdf


def ar_makale_sayfasi_bak(a):
    pdf = _makale_pdf(a.get("ders"), a.get("kaynak"))
    veri = makale_sekil.onizleme(pdf, int(a.get("sayfa") or 1), a.get("bolge"))
    return {"content": [{"type": "image", "data": base64.b64encode(veri).decode("ascii"), "mimeType": "image/png"},
                        {"type": "text", "text": "Sayfa %s%s. Bölge [sol, üst, sağ, alt], 0–1 oran." % (
                            a.get("sayfa"), " (yalnız bölge)" if a.get("bolge") else "")}]}


def ar_makale_sekli_ekle(a):
    ders = a.get("ders")
    _makale_pdf(ders, a.get("kaynak"))
    r = makale_sekil.tanimla(ders, a.get("ad"), a.get("kaynak"), a.get("sayfa"), a.get("bolge"),
                             a.get("baslik"), a.get("aciklama"))
    icerik = []
    if r.get("dosya") and os.path.exists(r["dosya"]):
        icerik.append({"type": "image", "data": base64.b64encode(_ikili_oku(r["dosya"])).decode("ascii"),
                       "mimeType": "image/png"})
    # Ders sihirbazla hazırlandıysa taslağa da yaz: yeniden paketlenince şekil tanımı kaybolmasın.
    taslak_ders = next((t for t in (ders, ders[5:] if ders.startswith("ozel-") else None)
                        if t and os.path.exists(sihirbaz.taslak_yolu(t))), None)
    if taslak_ders:
        sihirbaz.oge_kaydet(taslak_ders, "gorseller", {"id": a.get("ad"), "baslik": a.get("baslik"),
                                                       "aciklama": a.get("aciklama"), "makaleden": r["makaleden"]})
        r["sihirbaz_taslagi"] = taslak_ders
    r["not"] = ("Kesilen şekle bak: eksik ya da fazla kenar varsa bolge'yi düzeltip yeniden çağır. Şekil dosyası pakete "
                "girmez; öğrenci makaleyi ekleyince kendi bilgisayarında çizilir.")
    icerik.append({"type": "text", "text": json.dumps(r, ensure_ascii=False)})
    return {"content": icerik}


def ar_degerlendirme_notu(a):
    ders = a.get("ders")
    ders_yolu(ders)
    kimlik = ogrenci_kimligi(a.get("ogrenci"))
    t = degerlendirme.claude_notu(kimlik, ders, [{"tur": a.get("tur"), "ayrinti": a.get("ayrinti"), "yer": a.get("yer")}])
    return metin({"durum": "not alındı", "tespit_sayisi": len(t),
                  "not": "Öğrenciye bundan söz etmen gerekmez; ders sonunda formda görecek."})


def ar_degerlendirme_ozeti(a):
    k = a.get("klasor") or degerlendirme.klasor()
    if not os.path.isdir(k):
        return metin({"durum": "klasör yok", "klasor": k,
                      "not": "Öğrencilerden gelen form dosyalarını (.json ya da .txt) bir klasöre koyup yolunu ver."})
    cikis = os.path.join(k, "ozet-%s.md" % time.strftime("%Y-%m-%d")) if a.get("kaydet") else None
    r = degerlendirme.topla([k], cikis, bool(a.get("deneme_dahil")))
    return metin({"form_sayisi": r["form_sayisi"], "ozet": r["metin"], "dosya": r["dosya"],
                  "not": "Öğretmene en çok öne çıkan 3–5 bulguyu söyle: düşük puanlı sorular, sık geçen tespitler, "
                         "açık uçlu cevaplardaki ortak istekler."})


def ar_tekrar_karti_yaz(a):
    kimlik = ogrenci_kimligi(a.get("ogrenci"))
    k = ders_sonu.kart_sonucu(kimlik, a.get("ders"), a.get("kart"), bool(a.get("dogru")))
    return metin({"durum": "kaydedildi", "kutu": k["kutu"], "sonraki_tekrar": k["sonraki_tekrar"],
                  "ogrenildi": bool(k.get("ogrenildi"))})


def ar_depolama(a):
    out = depolama_ozeti()
    if out["asildi"]:
        out["not"] = DEPOLAMA_NOTU
    if a.get("ac"):
        sayfayi_ac("makaleler.html#depolama")
        out["sayfa"] = "Depolama sayfası tarayıcıda açıldı."
    return metin(out)


def ar_ders_arsivle(a):
    r = ders_sonu.arsivle(a.get("ders") or "")
    r["acilan_yer"] = ders_sonu.okunur_boyut(r["acilan_yer"])
    r["boyut"] = ders_sonu.okunur_boyut(r["boyut"])
    r["not"] = ("Öğrenciye söyle: ders arşive kaldırıldı, arşiv zip'i ve PDF'lerin yeri burada; ilerlemesi ve tekrar "
                "kartları duruyor; isterse dersi depolama sayfasından ya da arsivden_geri_yukle ile geri getirebilir.")
    return metin(r)


def ar_arsivden_geri_yukle(a):
    dosya = os.path.expanduser(a.get("dosya") or "")
    if not dosya and a.get("ders"):
        g = next((x for x in ders_sonu.arsiv_listesi() if x["ders"] == a["ders"]), None)
        if not g:
            raise ValueError("Arşiv listesinde böyle bir ders yok: %s" % a["ders"])
        dosya = g["dosya"]
    if not os.path.isfile(dosya):
        raise ValueError("Arşiv dosyası bulunamadı: %s. Öğrenciden zip'in yerini iste." % (dosya or "-"))
    r = ders_sonu.geri_yukle(dosya)
    r["not"] = "Ders geri geldi; makaleler arka planda hazırlanıyor (makaleler aracıyla izle). İlerleme kaldığı yerden sürer."
    return metin(r)


ISLEYICILER = {"egitmen_hazirla": ar_egitmen_hazirla, "kayit_oku": ar_kayit_oku, "kayit_yaz": ar_kayit_yaz,
               "rapor_yaz": ar_rapor_yaz, "olcme_testi": ar_olcme_testi, "olcme_kaydet": ar_olcme_kaydet,
               "tahtayi_ac": ar_tahtayi_ac, "dersler": ar_dersler, "ders_oku": ar_ders_oku,
               "gorsel_bak": ar_gorsel_bak, "tahta": ar_tahta, "soru_sor": ar_soru_sor,
               "tahta_durumu": ar_tahta_durumu, "dinle": ar_dinle, "bekle": ar_bekle, "durdur": ar_durdur,
               "anlatima_devam": ar_anlatima_devam, "videolar": ar_videolar,
               "bilgi_ara": ar_bilgi_ara, "vakalar": ar_vakalar, "vaka_oku": ar_vaka_oku, "karne": ar_karne,
               "sozlu_prova": ar_sozlu_prova, "tekrar_listesi": ar_tekrar_listesi,
               "kayit_disa_aktar": ar_kayit_disa_aktar, "kayit_ice_aktar": ar_kayit_ice_aktar,
               "kayit_anonim_aktar": ar_kayit_anonim_aktar, "makaleler": ar_makaleler,
               "makale_bul": ar_makale_bul, "makale_ekle": ar_makale_ekle,
               "sihirbaz_oku": ar_sihirbaz_oku, "sihirbaz_oner": ar_sihirbaz_oner,
               "ders_bitir": ar_ders_bitir, "program_onerisi": ar_program_onerisi,
               "calisma_secimi": ar_calisma_secimi, "degerlendirme_notu": ar_degerlendirme_notu,
               "degerlendirme_ozeti": ar_degerlendirme_ozeti,
               "makale_sayfasi_bak": ar_makale_sayfasi_bak, "makale_sekli_ekle": ar_makale_sekli_ekle, "tekrar_karti_yaz": ar_tekrar_karti_yaz, "depolama": ar_depolama,
               "ders_arsivle": ar_ders_arsivle, "ders_paketi_ekle": ar_ders_paketi_ekle,
               "ses_yeniden_baslat": ar_ses_yeniden_baslat, "arsivden_geri_yukle": ar_arsivden_geri_yukle}


def metin(veri, hata=False):
    t = veri if isinstance(veri, str) else json.dumps(veri, ensure_ascii=False, indent=1)
    out = {"content": [{"type": "text", "text": t}]}
    if hata:
        out["isError"] = True
    return out


# ---------- MCP (JSON-RPC, satır satır stdin/stdout) ----------
YAZ_KILIT = threading.Lock()  # kanal iş parçacığı ile ana döngü aynı anda yazmasın


def yaz(mesaj):
    with YAZ_KILIT:
        sys.stdout.buffer.write(json.dumps(mesaj, ensure_ascii=False).encode("utf-8") + b"\n")
        sys.stdout.buffer.flush()


# ---------- Claude Code kanalı (isteğe bağlı: --kanal) ----------
# Claude Code'un "channels" özelliği (araştırma önizlemesi) bir MCP sunucusunun oturuma kendiliğinden ileti
# göndermesine izin verir: notifications/claude/channel. Claude masaüstü sohbeti bunu desteklemez; bu yüzden
# yalnız --kanal ile açılır (yoksa söz, iletilmediği hâlde sunucudan alınıp kaybolurdu).
# Claude Code'u şöyle başlatın:  claude --dangerously-load-development-channels server:klinik-koc
KANAL = "--kanal" in sys.argv or os.environ.get("KLINIK_KOC_KANAL") == "1"
_kanal_basladi = False


def kanal_dongusu():
    while True:
        try:
            r = istek("kanal?bekle=25", zaman=45)
        except Exception:
            time.sleep(3)  # sunucu kapalı: tahtayi_ac açınca bağlanılır
            continue
        if r.get("durum") == "konustu" and r.get("metin"):
            sayfa = r.get("sayfa") or {}
            meta = {"kaynak": "tahta_mikrofonu"}
            if sayfa.get("ders"):
                meta["ders"] = str(sayfa["ders"])
            yaz({"jsonrpc": "2.0", "method": "notifications/claude/channel",
                 "params": {"content": r["metin"], "meta": meta}})


def kanali_baslat():
    global _kanal_basladi
    if KANAL and not _kanal_basladi:
        _kanal_basladi = True
        threading.Thread(target=kanal_dongusu, daemon=True).start()


# Beklemeli araçlar ayrı iş parçacığında, ötekiler eskisi gibi sırayla çalışır (kayıt dosyaları aynı anda yazılmasın).
BEKLEMELI = {"tahta", "soru_sor", "tahta_durumu", "dinle", "bekle", "anlatima_devam", "durdur", "tahtayi_ac"}
_SIRALI = threading.Lock()
_ISTEKLER = {}  # JSON-RPC id → çağrı bağlamı (iptal için)
_ISTEK_KILIT = threading.Lock()


def iptal_et(istek_no, neden=""):
    """Claude bir çağrıyı iptal etti (kullanıcı durdurdu ya da zaman aşımı): sunucudaki beklemesi hemen biter,
    o çağrıya verilmiş söz kuyruğa geri döner."""
    with _ISTEK_KILIT:
        c = _ISTEKLER.get(istek_no)
    if not c:
        return
    c["iptal"] = True
    c["neden"] = str(neden or "")
    _arka_planda("iptal?bekleme=%s" % c["bekleme"])


def _ogren(c, gecen):
    """Zaman aşımıyla kesilen bekleme: Claude'un bu bilgisayardaki araç süresi sınırını öğren."""
    neden = c.get("neden", "").lower()
    if c.get("araci") in BEKLEMELI and ("timed out" in neden or "timeout" in neden or "zaman" in neden) and gecen >= 25:
        _ayar_yaz("arac_bekleme_sn", max(20, int(gecen) - 12))


def arac_cagir(no, p):
    """tools/call: bağlam kurar, aracı çalıştırır, yanıtı yazar; teslim onayını ya da geri koymayı yapar."""
    ad = p.get("name")
    ilerleme = ((p.get("_meta") or {}).get("progressToken"))
    bas = time.time()
    c = {"bekleme": "%x-%s" % (os.getpid(), no), "teslimler": [], "iptal": False, "araci": ad,
         "bitis": bas + bekleme_butcesi(ilerleme is not None)}
    with _ISTEK_KILIT:
        _ISTEKLER[no] = c
    dur = threading.Event()
    if ilerleme is not None and ad in BEKLEMELI:
        def nabiz():
            # Çağrı uzun sürerken Claude'a "hâlâ çalışıyorum" bildirimi (zaman aşımını uzatabilir).
            while not dur.wait(NABIZ_SN):
                yaz({"jsonrpc": "2.0", "method": "notifications/progress",
                     "params": {"progressToken": ilerleme, "progress": int(time.time() - bas),
                                "message": "Tahta bekleniyor"}})
        threading.Thread(target=nabiz, daemon=True).start()
    _arka_planda("etkin", zaman=2)
    _BAGLAM.c = c
    try:
        if ad in BEKLEMELI:
            sonuc = isle({"jsonrpc": "2.0", "id": no, "method": "tools/call", "params": p})
        else:
            with _SIRALI:
                sonuc = isle({"jsonrpc": "2.0", "id": no, "method": "tools/call", "params": p})
        hata = None
    except Exception as e:
        sonuc, hata = None, e
    finally:
        _BAGLAM.c = None
        dur.set()
        with _ISTEK_KILIT:
            _ISTEKLER.pop(no, None)
    _arka_planda("etkin", zaman=2)
    if c["iptal"]:
        # İptal edilen çağrıya yanıt yazılmaz; ona verilmiş söz kaybolmasın, kuyruğa geri dönsün.
        for t in c["teslimler"]:
            _arka_planda("teslim?no=%d&onay=0" % int(t))
        _ogren(c, time.time() - bas)
        return
    basarisiz = hata is not None or (isinstance(sonuc, dict) and sonuc.get("isError"))
    try:
        if hata is not None:
            yaz({"jsonrpc": "2.0", "id": no, "error": {"code": -32603, "message": str(hata)}})
        else:
            yaz({"jsonrpc": "2.0", "id": no, "result": sonuc})
        yazildi = True
    except Exception:
        yazildi = False
    for t in c["teslimler"]:
        _arka_planda("teslim?no=%d&onay=%d" % (int(t), 1 if yazildi and not basarisiz else 0))


def isle(m):
    yontem, no, p = m.get("method"), m.get("id"), m.get("params") or {}
    if no is None:
        if yontem == "notifications/initialized":
            kanali_baslat()
        elif yontem == "notifications/cancelled":
            iptal_et(p.get("requestId"), p.get("reason"))
        return None  # bildirim: yanıt verilmez
    if yontem == "initialize":
        yetenek = {"tools": {}}
        if KANAL:
            yetenek["experimental"] = {"claude/channel": {}}
        return {"protocolVersion": p.get("protocolVersion") or "2025-06-18",
                "capabilities": yetenek,
                "serverInfo": {"name": AD, "title": "KlinikKoç", "version": SURUM},
                "instructions": TALIMAT}
    if yontem == "ping":
        return {}
    if yontem == "tools/list":
        return {"tools": araclar()}
    if yontem == "tools/call":
        f = ISLEYICILER.get(p.get("name"))
        if not f:
            raise LookupError("Bilinmeyen araç: %s" % p.get("name"))
        arg = p.get("arguments") or {}
        if arg.get("ogrenci") and arg.get("ders"):
            _AKTIF.update(ogrenci=arg["ogrenci"], ders=arg["ders"])
        try:
            return f(arg)
        except Exception as e:
            _hatayi_forma_yaz(p.get("name"), e)
            return metin("Hata: %s" % e, hata=True)
    if yontem in ("resources/list", "prompts/list"):
        return {yontem.split("/")[0]: []}
    raise NotImplementedError(yontem)


_AKTIF = {}  # son çalışılan öğrenci + ders: araç hataları o dersin değerlendirme formuna kendiliğinden yazılır


def _hatayi_forma_yaz(arac, hata):
    if not _AKTIF.get("ders") or arac in ("degerlendirme_notu", "degerlendirme_ozeti"):
        return
    try:
        degerlendirme.otomatik_not(ogrenci_kimligi(_AKTIF["ogrenci"]), _AKTIF["ders"],
                                   {"tur": "teknik", "ayrinti": "%s aracı hata verdi: %s" % (arac, str(hata)[:300])})
    except Exception:
        pass


def calis():
    while True:
        satir = sys.stdin.buffer.readline()
        if not satir:
            break
        satir = satir.strip()
        if not satir:
            continue
        try:
            m = json.loads(satir.decode("utf-8"))
        except Exception:
            yaz({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Geçersiz JSON"}})
            continue
        if m.get("method") == "tools/call" and m.get("id") is not None:
            # Araç ayrı iş parçacığında çalışır: o beklerken ping, iptal ve başka çağrılar hemen işlenir.
            threading.Thread(target=arac_cagir, args=(m["id"], m.get("params") or {}), daemon=True).start()
            continue
        try:
            sonuc = isle(m)
            if m.get("id") is not None:
                yaz({"jsonrpc": "2.0", "id": m["id"], "result": sonuc})
        except NotImplementedError as e:
            yaz({"jsonrpc": "2.0", "id": m.get("id"), "error": {"code": -32601, "message": "Yöntem yok: %s" % e}})
        except Exception as e:
            yaz({"jsonrpc": "2.0", "id": m.get("id"), "error": {"code": -32603, "message": str(e)}})


# ---------- Claude masaüstü ayarı (tools/claude_ayari.py) ----------
from claude_ayari import (AYAR_ADI, CAKISAN_SUNUCULAR, YOL_GOSTER, _ayar_yolu_arg, _paket_kimligi,  # noqa: E402,F401
                          ayar_adaylari, ayar_dosyalari, ayar_raporu, ayara_yaz, cakisanlar, sunucu_girdisi)


def kur(kaldir=False):
    elle = _ayar_yolu_arg()
    hedefler = [elle] if elle else ayar_dosyalari()
    if not hedefler:
        print(YOL_GOSTER)
        sys.exit(1)
    for yol in hedefler:
        cikan = ayara_yaz(yol, kaldir)
        print(("Kaldırıldı: " if kaldir else "Eklendi (Claude'un okuduğu dosya): ") + yol)
        for ad in cikan:
            print("Eski tahta bağlantısı çıkarıldı: '%s' (aynı araç adlarını kullanıyordu; Claude yanlış tahtayı "
                  "dinleyebilirdi). Eski ayar yedekte: %s.yedek" % (ad, yol))
    if not elle:
        for yol, tur, aciklama in ayar_adaylari():
            if tur == "eski":
                print("Atlandı (eski yer, Claude artık okumuyor): %s" % yol)
    if not kaldir:
        print("\nŞimdi Claude masaüstü uygulamasını TAMAMEN kapatın: saatin yanındaki ^ → Claude simgesi →")
        print("sağ tık → Çık (Mac'te Cmd+Q). Sonra yeniden açın.")
        print("Denetim: Claude'da Ayarlar › Geliştirici ekranında '%s' \"Çalışıyor\" görünmeli." % AD)
        print("Görünmüyorsa: aynı ekranda \"Yapılandırmayı düzenle\"ye basın, açılan dosyanın yolunu")
        print("  python tools/tahta-mcp.py --kur --ayar \"<yol>\"  ile verin.")
        print("Sonra Claude'a şunu yazın:  Tahtayı aç ve bana Şekil 2'yi anlat.")
        kayit_yeri_hazirla()


def kayit_yeri_hazirla():
    d = depo()
    d.hazirla()
    print("\nÖğrenci kayıtları bu klasörde durur (güncellemede silinmez):\n  " + d.kok)
    if d.tasima_raporu:
        print("Eski kayıtlar buraya kopyalandı (%d dosya); eski dosyalar silinmedi: %s" % (
            d.tasima_raporu["kopyalanan"], d.tasima_raporu["kaynak"]))


def kendini_dene():
    """Kurulumdan sonra hızlı denetim: araç listesi ve ders dosyaları okunuyor mu?"""
    print("KlinikKoç sürümü:", SURUM)
    print("Python:", sys.executable)
    print("Klasör:", KOK)
    print("Dersler:", ", ".join(g["id"] for g in katalog()) or "yok")
    print("Araçlar:", ", ".join(a["name"] for a in ARACLAR))
    print("Kayıt klasörü:", KAYIT_KOK)
    d = sunucu_acik()
    print("Yerel sunucu:", "açık, tahta " + ("bağlı" if d and d.get("bagli") else "bağlı değil") if d else "kapalı (Claude açacak)")
    satirlar, uyarilar = ayar_raporu()
    print("Claude ayar dosyaları:")
    for x in satirlar:
        print(x)
    for u in uyarilar:
        print("UYARI: " + u)
    if not uyarilar:
        print("Tamam: Claude'un okuduğu ayar dosyasında %s var." % AD)


if __name__ == "__main__":
    if "--kur" in sys.argv:
        kur()
    elif "--kaldir" in sys.argv:
        kur(kaldir=True)
    elif "--kayit-yeri" in sys.argv:
        kayit_yeri_hazirla()
    elif "--dene" in sys.argv:
        kendini_dene()
    else:
        calis()
