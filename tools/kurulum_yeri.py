#!/usr/bin/env python3
"""Windows'ta yeni kurulumun yeri: indirilen klasör (ör. Masaüstü, İndirilenler) yerine sabit C:\\KlinikKoc.

Kemal'in kararları (27 Kasım 2026):
  - Yalnız YENİ kurulumlar taşınır; var olan (daha önce kurulmuş ya da Claude'un kullandığı) kurulum yerinde kalır.
  - Bilgisayarlar kişisel; C:\\KlinikKoc'un bütün Windows hesaplarına ortak olması sorun değil.
Kurallar: emin olunamayan her durumda yerinde kalınır. C:\\KlinikKoc'ta zaten KlinikKoç varsa üstüne yazılmaz,
oradaki kurulum kullanılır. Klasör oluşturulamazsa yerinde kurulur. Mac ve Linux'ta hiçbir şey değişmez.
Kopyalama taşıma değildir: indirilen klasör yerinde kalır (kurulumun sonundaki eski sürüm taraması silmeyi sorar).

KUR-Windows.bat çağırır:
  python tools/kurulum_yeri.py --karar      → tek satır: BURADA | TASI <hedef> | ORADA <hedef>
  python tools/kurulum_yeri.py --kopyala    → bu klasörü hedefe kopyalar (yalnız karar TASI iken)
Deneme için hedef KLINIK_KOC_KURULUM_YERI ortam değişkeniyle değiştirilebilir.
Yalnız Python'un kendi kitaplığını kullanır.
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VARSAYILAN_HEDEF = r"C:\KlinikKoc"
IMZA = os.path.join("tools", "tahta-mcp.py")

# Bir klasörün daha önce kurulup kullanıldığını gösteren izler (yeni indirilen klasörde hiçbiri olmaz).
KURULUM_IZLERI = (".ses-ortami", ".dizin", ".modeller", os.path.join("tools", ".sesler"),
                  os.path.join(".python", "secilen.txt"), "kayitlar", "ozel")
# Kopyalanmayanlar: bu bilgisayarda yeniden üretilir ya da gerekmez (ses ortamı mutlak yollar içerir).
KOPYALANMAZ = {".ses-ortami", ".dizin", ".modeller", ".git", "__pycache__"}


def hedef():
    return os.environ.get("KLINIK_KOC_KURULUM_YERI") or VARSAYILAN_HEDEF


def _gercek(yol):
    return os.path.normcase(os.path.realpath(yol))


def _ayni(a, b):
    try:
        return _gercek(a) == _gercek(b)
    except (TypeError, ValueError, OSError):
        return False


def _surum(klasor):
    try:
        with open(os.path.join(klasor, "SURUM"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def kurulu_ders_var(kok):
    d = os.path.join(kok, "lessons")
    try:
        return any(os.path.isdir(os.path.join(d, x)) and not x.startswith(".") for x in os.listdir(d))
    except OSError:
        return False


def claude_kullaniyor(kok):
    """Claude'un ayar dosyasında bu klasörün tahta-mcp.py'si kayıtlı mı?"""
    try:
        import eski_surumler
        return _gercek(kok) in eski_surumler._claude_kullaniyor()
    except Exception:
        return False


def var_olan_kurulum_mu(kok, claude=None):
    """Bu klasör daha önce kurulmuş mu? Emin olunamazsa True (yerinde kalınır)."""
    if any(os.path.exists(os.path.join(kok, iz)) for iz in KURULUM_IZLERI):
        return True
    if kurulu_ders_var(kok):
        return True
    return claude_kullaniyor(kok) if claude is None else bool(claude)


def karar(kok=KOK, hedef_yol=None, isletim=None, claude=None):
    """("BURADA", None) | ("TASI", hedef) | ("ORADA", hedef)."""
    isletim = isletim or os.name
    hedef_yol = hedef_yol or hedef()
    if isletim != "nt":
        return "BURADA", None
    if _ayni(kok, hedef_yol):
        return "BURADA", None
    try:
        if var_olan_kurulum_mu(kok, claude):
            return "BURADA", None
    except Exception:
        return "BURADA", None
    if os.path.isfile(os.path.join(hedef_yol, IMZA)):
        return "ORADA", hedef_yol
    if os.path.exists(hedef_yol):
        try:
            if os.listdir(hedef_yol):  # başka bir şey var: dokunulmaz
                return "BURADA", None
        except OSError:
            return "BURADA", None
    return "TASI", hedef_yol


def _yok_say(kaynak_kok):
    def yok(dizin, adlar):
        out = set(adlar) & KOPYALANMAZ
        if _ayni(dizin, os.path.join(kaynak_kok, "tools")) and ".sesler" in adlar:
            out.add(".sesler")
        return out
    return yok


def kopyala(kok=KOK, hedef_yol=None):
    """Bu klasörü hedefe kopyalar. Döner: hedef. Yarıda kalırsa yarım hedef silinir ve hata yükselir."""
    hedef_yol = hedef_yol or hedef()
    bos_vardi = os.path.isdir(hedef_yol)
    if bos_vardi and os.listdir(hedef_yol):
        raise RuntimeError("Hedef klasör boş değil: %s" % hedef_yol)
    try:
        shutil.copytree(kok, hedef_yol, ignore=_yok_say(kok), dirs_exist_ok=bos_vardi)
    except BaseException:
        shutil.rmtree(hedef_yol, ignore_errors=True)
        if bos_vardi:
            os.makedirs(hedef_yol, exist_ok=True)
        raise
    if not os.path.isfile(os.path.join(hedef_yol, IMZA)):
        raise RuntimeError("Kopya eksik: %s" % hedef_yol)
    return hedef_yol


def main(argv):
    if "--karar" in argv:
        k, h = karar()
        print(k if not h else "%s %s" % (k, h))
        if k == "ORADA" and _surum(KOK) and _surum(h) and _surum(KOK) != _surum(h):
            sys.stderr.write("Not: %s klasöründe KlinikKoç %s var; indirdiğiniz %s. Yeni sürümü programın kendi "
                             "güncellemesiyle alın.\n" % (h, _surum(h), _surum(KOK)))
        return 0
    if "--kopyala" in argv:
        k, h = karar()
        if k != "TASI":
            print("Kopyalama gerekmiyor (%s)." % k)
            return 1
        try:
            kopyala(KOK, h)
        except Exception as e:
            print("Kopyalanamadı (%s); KlinikKoç bulunduğu yere kurulacak." % e)
            return 1
        print("KlinikKoç %s klasörüne kopyalandı." % h)
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
