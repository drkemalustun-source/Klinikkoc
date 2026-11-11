"""Claude masaüstü uygulamasının MCP ayar dosyası (claude_desktop_config.json): nerede, nasıl yazılır, denetlenir.

tools/tahta-mcp.py --kur / --kaldir / --dene bu modülü kullanır.
"""
import glob
import json
import os
import shutil
import sys

AD = "klinik-koc"
TAHTA_MCP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tahta-mcp.py")


# ---------- Claude masaüstü ayarı ----------
# Claude masaüstü uygulamasının MCP ayarı (claude_desktop_config.json) kuruluma göre farklı yerdedir:
#  - Windows, Microsoft Store (MSIX) kurulumu, yeni sürümler: %LOCALAPPDATA%\Claude-Data\claude_<paket>\
#    (uygulama veriyi buraya taşır, eski paket klasörüne ".user-data-left.*" işareti bırakır)
#  - Windows, MSIX eski sürümler: %LOCALAPPDATA%\Packages\Claude_<paket>\LocalCache\Roaming\Claude\
#  - Windows, .exe kurulumu: %APPDATA%\Claude\
#  - macOS: ~/Library/Application Support/Claude/   - Linux: ~/.config/Claude/
# Kesin yol, uygulamada Ayarlar › Geliştirici › "Yapılandırmayı düzenle" düğmesinin açtığı dosyadır;
# bulunamazsa kullanıcı onu --ayar "<yol>" ile verebilir.
AYAR_ADI = "claude_desktop_config.json"


def _paket_kimligi(klasor_adi):
    """'Claude_pzs8sxrjxfjjc' / 'claude_pzs8sxrjxfjjc' → 'pzs8sxrjxfjjc'."""
    return klasor_adi.split("_", 1)[1].lower() if "_" in klasor_adi else ""


def ayar_adaylari(isletim=None, ortam=None):
    """Olası ayar dosyalarını [(yol, tur, aciklama)] olarak döndürür.

    tur: "asil"  → Claude'un okuduğu dosya (kur buraya yazar)
         "eski"  → eskiden kullanılan, artık okunmayan dosya (yalnız bilgi için listelenir)
    Klasörü olmayan adaylar listelenmez. Hiç aday yoksa boş liste döner.
    """
    isletim = isletim or ("nt" if os.name == "nt" else sys.platform)
    ortam = os.environ if ortam is None else ortam
    sonuc = []
    if isletim == "nt":
        appdata = ortam.get("APPDATA", "")
        yerel = ortam.get("LOCALAPPDATA", "")
        tasinan = set()
        if yerel:
            for d in sorted(glob.glob(os.path.join(yerel, "Claude-Data", "claude_*"))):
                if os.path.isdir(d):
                    tasinan.add(_paket_kimligi(os.path.basename(d)))
                    sonuc.append((os.path.join(d, AYAR_ADI), "asil", "Microsoft Store kurulumu (yeni yer)"))
        msix_var = False
        if yerel:
            for paket in sorted(glob.glob(os.path.join(yerel, "Packages", "Claude_*"))):
                d = os.path.join(paket, "LocalCache", "Roaming", "Claude")
                if not os.path.isdir(d):
                    continue
                msix_var = True
                ayrildi = glob.glob(os.path.join(d, ".user-data-left*"))
                if ayrildi or _paket_kimligi(os.path.basename(paket)) in tasinan:
                    sonuc.append((os.path.join(d, AYAR_ADI), "eski", "Microsoft Store paket klasörü (veri taşınmış)"))
                else:
                    sonuc.append((os.path.join(d, AYAR_ADI), "asil", "Microsoft Store paket klasörü"))
        if appdata and os.path.isdir(os.path.join(appdata, "Claude")):
            if msix_var or tasinan:
                # Store kurulumunda uygulama %APPDATA%\Claude'u okumaz.
                sonuc.append((os.path.join(appdata, "Claude", AYAR_ADI), "eski", "%APPDATA%\\Claude (Store kurulumu bunu okumaz)"))
            else:
                sonuc.append((os.path.join(appdata, "Claude", AYAR_ADI), "asil", "Claude .exe kurulumu"))
    else:
        if isletim == "darwin":
            d = os.path.expanduser("~/Library/Application Support/Claude")
        else:
            d = os.path.join(ortam.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "Claude")
        if os.path.isdir(d):
            sonuc.append((os.path.join(d, AYAR_ADI), "asil", "Claude masaüstü"))
    return sonuc


def ayar_dosyalari():
    """Claude'un okuduğu ayar dosyaları (kur bunlara yazar)."""
    return [y for y, tur, _ in ayar_adaylari() if tur == "asil"]


YOL_GOSTER = ("Claude'un ayar dosyası bulunamadı.\n"
              "Claude masaüstü uygulamasını açın → Ayarlar → Geliştirici → \"Yapılandırmayı düzenle\".\n"
              "Açılan dosyanın yolunu kopyalayıp şunu çalıştırın:\n"
              "  python tools/tahta-mcp.py --kur --ayar \"<dosyanın yolu>\"")


def _ayar_yolu_arg():
    if "--ayar" in sys.argv:
        i = sys.argv.index("--ayar")
        if i + 1 >= len(sys.argv):
            sys.exit("--ayar'dan sonra dosya yolunu yazın.")
        yol = os.path.abspath(os.path.expanduser(sys.argv[i + 1].strip('"')))
        if os.path.isdir(yol):
            yol = os.path.join(yol, AYAR_ADI)
        return yol
    return None


def sunucu_girdisi():
    return {"command": sys.executable, "args": [TAHTA_MCP],
            "env": {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}}


# Aynı araç adlarını (tahta, dinle, tahtayi_ac...) kullanan eski programlar. Claude ikisini birden görürse yanlış
# programın aracını çağırabilir (ör. açık olmayan eski tahtayı dinler): KUR bunları ayardan çıkarır (yedek alınır).
CAKISAN_SUNUCULAR = ("akilli-tahta",)


def cakisanlar(sunucular):
    """Ayar dosyasındaki, bizimle aynı araç adlarını kullanan eski tahta girdileri."""
    out = []
    for ad, g in (sunucular or {}).items():
        if ad == AD or not isinstance(g, dict):
            continue
        hedef = " ".join(str(x) for x in (g.get("args") or []))
        if ad in CAKISAN_SUNUCULAR or ("tahta-mcp.py" in hedef and ad != AD):
            out.append(ad)
    return out


def ayara_yaz(yol, kaldir=False):
    """Yalnız mcpServers[AD]'yi (ve kurulumda aynı araç adlarını kullanan eski tahta girdilerini) değiştirir;
    dosyadaki öteki alanlar (preferences vb.) olduğu gibi kalır. Döner: çıkarılan eski girdilerin adları."""
    os.makedirs(os.path.dirname(yol), exist_ok=True)
    ayar = {}
    if os.path.exists(yol) and os.path.getsize(yol) > 0:
        try:
            with open(yol, encoding="utf-8-sig") as f:
                ayar = json.load(f) or {}
        except Exception:
            sys.exit("Ayar dosyası okunamadı (bozuk JSON?): %s\nDosyayı düzeltip yeniden deneyin." % yol)
        shutil.copy2(yol, yol + ".yedek")
    sunucular = ayar.setdefault("mcpServers", {})
    cikan = []
    if kaldir:
        sunucular.pop(AD, None)
    else:
        sunucular[AD] = sunucu_girdisi()
        for ad in cakisanlar(sunucular):
            sunucular.pop(ad, None)
            cikan.append(ad)
    gecici = yol + ".yaziliyor"
    with open(gecici, "w", encoding="utf-8") as f:
        json.dump(ayar, f, ensure_ascii=False, indent=2)
    os.replace(gecici, yol)
    return cikan


def ayar_raporu():
    """--dene için: bulunan her ayar dosyasında bu sunucu var mı? Sorun varsa uyarı satırları döndürür."""
    satirlar, uyarilar = [], []
    adaylar = ayar_adaylari()
    if not adaylar:
        uyarilar.append(YOL_GOSTER)
    for yol, tur, aciklama in adaylar:
        durum = "dosya yok"
        if os.path.exists(yol):
            try:
                with open(yol, encoding="utf-8-sig") as f:
                    tum = (json.load(f) or {}).get("mcpServers") or {}
                g = tum.get(AD)
                if tur == "asil":
                    for ad in cakisanlar(tum):
                        uyarilar.append("Claude ayarında eski '%s' tahtası da kayıtlı; araç adları aynı olduğu için Claude "
                                        "yanlış tahtayı dinleyebilir. KUR'u yeniden çalıştırın (eskisini çıkarır)." % ad)
                if g:
                    hedef = (g.get("args") or [""])[0]
                    durum = AD + " var" + ("" if os.path.exists(hedef) else " AMA dosyası yok: " + hedef)
                    if tur == "asil" and not os.path.exists(hedef):
                        uyarilar.append("%s girdisi var olmayan bir dosyayı gösteriyor: %s\nKUR'u bu klasörden yeniden çalıştırın." % (AD, hedef))
                else:
                    durum = AD + " YOK"
            except Exception as e:
                durum = "okunamadı (%s)" % e
        satirlar.append("  [%s] %s\n        %s — %s" % ("asıl" if tur == "asil" else "eski", aciklama, yol, durum))
        if tur == "asil" and AD + " var" not in durum:
            uyarilar.append("Claude'un okuduğu dosyada %s yok: %s\nKUR'u yeniden çalıştırın." % (AD, yol))
    return satirlar, uyarilar
