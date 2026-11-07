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


def masaustu():
    """Dışa aktarılan dosyalar için kullanıcının masaüstü (yoksa ev klasörü)."""
    ev = os.path.expanduser("~")
    for aday in (os.path.join(os.environ.get("OneDrive", ""), "Desktop") if os.environ.get("OneDrive") else "",
                 os.path.join(ev, "Desktop"), os.path.join(ev, "Masaüstü")):
        if aday and os.path.isdir(aday):
            return aday
    return ev
