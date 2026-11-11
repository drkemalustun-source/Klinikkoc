"""Otomatik uyandırma: Claude dinlemiyorken öğrenci tahtada konuşursa, sözü Claude masaüstü sohbetine yazıp gönderir.

Neden gerekli: Claude masaüstü sırayla çalışır; Claude'un sırası bitince (cevabını yazıp durunca) tahta onu kendisi
harekete geçiremez. Eskiden öğrenci sohbete "tahtaya bak" yazmak zorundaydı. Bu modül o işi öğrencinin yerine yapar:
Claude penceresini öne getirir, "Tahtadan sesli soru: ..." metnini sohbet kutusuna yapıştırıp Enter'a basar ve
öğrenciyi tahtaya geri döndürür.

- Windows: PowerShell (user32 SetForegroundWindow + pano + SendKeys). Ek kurulum gerekmez.
- macOS: osascript (System Events). İlk kullanımda Sistem Ayarları › Gizlilik › Erişilebilirlik'te izin istenir.
- Başka sistemlerde (Linux) xdotool varsa onunla; yoksa kullanılmaz.

Ayar: veri klasöründeki ayarlar.json → "otomatik_uyandirma": true | false (varsayılan: açık). Tahtadaki
"Otomatik gönder" düğmesi de bunu değiştirir.
"""
import os
import shutil
import subprocess
import sys
import tempfile

ONEK = "Tahtadan sesli soru: "

_WIN_BETIK = r"""
$ErrorActionPreference = 'Stop'
Add-Type @'
using System; using System.Runtime.InteropServices;
public class KKPencere {
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
  [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] public static extern void keybd_event(byte b, byte s, uint f, UIntPtr e);
}
'@
$metin = Get-Content -Raw -Encoding UTF8 -LiteralPath $args[0]
$p = Get-Process -Name 'claude' -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne [IntPtr]::Zero } | Select-Object -First 1
if (-not $p) { Write-Output 'CLAUDE_YOK'; exit 3 }
$h = $p.MainWindowHandle
$once = [KKPencere]::GetForegroundWindow()
$eskiPano = $null
try { $eskiPano = Get-Clipboard -Raw -ErrorAction SilentlyContinue } catch {}
Set-Clipboard -Value $metin
if ([KKPencere]::IsIconic($h)) { [KKPencere]::ShowWindow($h, 9) | Out-Null }
# Alt tuşuna kısa basış: Windows başka bir uygulamanın pencereyi öne almasına ancak böyle izin verir.
[KKPencere]::keybd_event(0x12, 0, 0, [UIntPtr]::Zero); [KKPencere]::keybd_event(0x12, 0, 2, [UIntPtr]::Zero)
[KKPencere]::SetForegroundWindow($h) | Out-Null
Start-Sleep -Milliseconds 600
$ws = New-Object -ComObject WScript.Shell
$ws.SendKeys('^v')
Start-Sleep -Milliseconds 250
$ws.SendKeys('~')
Start-Sleep -Milliseconds 500
if ($once -ne [IntPtr]::Zero -and $once -ne $h) {
  [KKPencere]::keybd_event(0x12, 0, 0, [UIntPtr]::Zero); [KKPencere]::keybd_event(0x12, 0, 2, [UIntPtr]::Zero)
  [KKPencere]::SetForegroundWindow($once) | Out-Null
}
if ($eskiPano) { try { Set-Clipboard -Value $eskiPano } catch {} }
Write-Output 'TAMAM'
"""

_MAC_BETIK = """
on run argv
  set metin to read (POSIX file (item 1 of argv)) as «class utf8»
  tell application "System Events" to set onceki to name of first application process whose frontmost is true
  set eskiPano to ""
  try
    set eskiPano to the clipboard as text
  end try
  set the clipboard to metin
  tell application "Claude" to activate
  delay 0.6
  tell application "System Events"
    keystroke "v" using command down
    delay 0.25
    key code 36
  end tell
  delay 0.5
  if onceki is not "Claude" then
    tell application onceki to activate
  end if
  if eskiPano is not "" then set the clipboard to eskiPano
  return "TAMAM"
end run
"""


def destekleniyor():
    if os.name == "nt":
        return shutil.which("powershell") is not None or shutil.which("powershell.exe") is not None
    if sys.platform == "darwin":
        return shutil.which("osascript") is not None
    return shutil.which("xdotool") is not None


def gonder(metin, zaman=20):
    """Metni Claude sohbetine yazıp gönderir. Döner: (başarılı mı, açıklama)."""
    metin = ONEK + " ".join(str(metin).split())
    fd, yol = tempfile.mkstemp(prefix="klinikkoc-uyandir-", suffix=".txt")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(metin)
        if os.name == "nt":
            fd2, betik = tempfile.mkstemp(prefix="klinikkoc-uyandir-", suffix=".ps1")
            with os.fdopen(fd2, "w", encoding="utf-8-sig") as f:
                f.write(_WIN_BETIK)
            try:
                r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                                    "-WindowStyle", "Hidden", "-File", betik, yol],
                                   capture_output=True, text=True, timeout=zaman,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            finally:
                os.unlink(betik)
        elif sys.platform == "darwin":
            r = subprocess.run(["osascript", "-", yol], input=_MAC_BETIK, capture_output=True, text=True, timeout=zaman)
        elif shutil.which("xdotool"):
            pencere = subprocess.run(["xdotool", "search", "--name", "Claude"], capture_output=True, text=True,
                                     timeout=5).stdout.split()
            if not pencere:
                return False, "Claude penceresi bulunamadı."
            r = subprocess.run(["xdotool", "windowactivate", "--sync", pencere[0], "type", "--delay", "5", metin],
                               capture_output=True, text=True, timeout=zaman)
            if r.returncode == 0:
                subprocess.run(["xdotool", "key", "Return"], timeout=5)
                return True, "gönderildi"
            return False, (r.stderr or "xdotool hata verdi").strip()[:200]
        else:
            return False, "Bu sistemde otomatik gönderme yok."
    except subprocess.TimeoutExpired:
        return False, "Claude penceresine yazma zaman aşımına uğradı."
    except OSError as e:
        return False, str(e)[:200]
    finally:
        try:
            os.unlink(yol)
        except OSError:
            pass
    cikti = (r.stdout or "").strip()
    if r.returncode == 0 and "TAMAM" in cikti:
        return True, "gönderildi"
    if "CLAUDE_YOK" in cikti:
        return False, "Claude masaüstü uygulaması açık değil."
    hata = (r.stderr or cikti or "bilinmeyen hata").strip()
    if sys.platform == "darwin" and ("1002" in hata or "not allowed" in hata.lower() or "erişilebilirlik" in hata.lower()):
        return False, ("Mac izin istiyor: Sistem Ayarları › Gizlilik ve Güvenlik › Erişilebilirlik'te Claude'u "
                       "(ve Terminal'i) açın.")
    return False, hata[:300]
