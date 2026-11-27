"""Kullanıcıya gösterilen "şu komutu çalıştırın" yazıları: programın kendi Python'u ve tam yollarla.

Kısa "python tools/..." yazısı başka bir klasörde ya da bilgisayardaki başka bir Python'la (ör. 3.15) çalışabilir;
Ali'nin 27 Kasım 2026 raporundaki sorun buydu (Öneri 1). Bu yazı, KlinikKoç'u çalıştıran Python'la ve
programın klasöründeki dosyayla çalışır; her yerde kopyalanıp yapıştırılabilir.
Yalnız Python'un kendi kitaplığını kullanır.
"""
import os
import sys

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _tirnak(yol):
    return '"%s"' % yol if (" " in yol or os.name == "nt") else yol


def yazi(betik, *argumanlar):
    """ör. yazi("ses-uret.py", "--kur-pocket") → '"C:\\...\\python.exe" "C:\\KlinikKoc\\tools\\ses-uret.py" --kur-pocket'"""
    parcalar = [_tirnak(sys.executable or ("py" if os.name == "nt" else "python3")),
                _tirnak(os.path.join(KOK, "tools", betik))]
    return " ".join(parcalar + list(argumanlar))
