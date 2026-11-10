"""KlinikKoç'un kalıcı veri klasörü: program klasörünün dışında, güncellemede silinmez.

  macOS:   ~/Library/Application Support/KlinikKoc
  Windows: %APPDATA%\\KlinikKoc
  Linux:   $XDG_DATA_HOME/KlinikKoc (yoksa ~/.local/share/KlinikKoc)

KLINIK_KOC_VERI ortam değişkeni bu kökü değiştirir. Öğrenci kayıtları için KLINIK_KOC_KAYIT
her şeyden önce gelir. Yalnız Python'un kendi kitaplığını kullanır.
"""
import os
import sys

UYGULAMA = "KlinikKoc"


def veri_kok():
    ozel = os.environ.get("KLINIK_KOC_VERI")
    if ozel:
        return os.path.abspath(os.path.expanduser(ozel))
    ev = os.path.expanduser("~")
    if sys.platform == "darwin":
        taban = os.path.join(ev, "Library", "Application Support")
    elif os.name == "nt":
        taban = os.environ.get("APPDATA") or os.path.join(ev, "AppData", "Roaming")
    else:
        taban = os.environ.get("XDG_DATA_HOME") or os.path.join(ev, ".local", "share")
    return os.path.join(taban, UYGULAMA)


def kayit_kok():
    ozel = os.environ.get("KLINIK_KOC_KAYIT")
    if ozel:
        return os.path.abspath(os.path.expanduser(ozel))
    return os.path.join(veri_kok(), "kayitlar")


def kayit_ortamdan_mi():
    return bool(os.environ.get("KLINIK_KOC_KAYIT"))


def belgeler():
    """Kullanıcının Belgeler klasörü. Windows'ta OneDrive'a taşınmış olabilir; önce sistemden sorulur."""
    ev = os.path.expanduser("~")
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes
            yol = ctypes.c_wchar_p()
            # FOLDERID_Documents {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
            guid = (ctypes.c_byte * 16)(*bytes.fromhex("d09ad3fd8f23af46adb46c85480369c7"))
            if ctypes.windll.shell32.SHGetKnownFolderPath(guid, 0, None, ctypes.byref(yol)) == 0 and yol.value:
                sonuc = yol.value
                ctypes.windll.ole32.CoTaskMemFree(yol)
                if os.path.isdir(sonuc):
                    return sonuc
        except Exception:
            pass
    adaylar = [os.path.join(ev, "Documents"), os.path.join(ev, "Belgeler")]
    if os.environ.get("OneDrive"):
        adaylar.insert(0, os.path.join(os.environ["OneDrive"], "Documents"))
    for aday in adaylar:
        if os.path.isdir(aday):
            return aday
    return ev


def makale_kok():
    """İndirilen makalelerin durduğu, öğrencinin gördüğü klasör: Belgeler/KlinikKoç Makaleler.
    Ders arşivlenince de PDF'ler burada kalır; geri yüklemede önce buraya bakılır.
    KLINIK_KOC_MAKALE ortam değişkeni bu yeri değiştirir."""
    ozel = os.environ.get("KLINIK_KOC_MAKALE")
    if ozel:
        return os.path.abspath(os.path.expanduser(ozel))
    return os.path.join(belgeler(), "KlinikKoç Makaleler")


def masaustu():
    """Dışa aktarılan dosyalar için kullanıcının masaüstü (yoksa ev klasörü)."""
    ev = os.path.expanduser("~")
    for aday in (os.path.join(os.environ.get("OneDrive", ""), "Desktop") if os.environ.get("OneDrive") else "",
                 os.path.join(ev, "Desktop"), os.path.join(ev, "Masaüstü")):
        if aday and os.path.isdir(aday):
            return aday
    return ev
