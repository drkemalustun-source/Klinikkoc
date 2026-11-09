@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo KlinikKoc kurulumu (Windows)
echo.
set PY=python
where python >nul 2>nul || set PY=py -3
%PY% -c "import sys" >nul 2>nul
if errorlevel 1 (
  echo Python bulunamadi. python.org/downloads adresinden Python 3.12'yi kurun
  echo ^(kurulumda "Add python.exe to PATH" kutusunu isaretleyin^), sonra bu dosyayi yeniden calistirin.
  pause
  exit /b 1
)
echo 1/3 Piper ses paketleri denetleniyor (zaten kuruluysa hizli gecer)...
%PY% tools\ses-uret.py --kur
echo.
echo 2/3 Claude masaustu uygulamasina KlinikKoc araclari ekleniyor...
%PY% tools\tahta-mcp.py --kur
echo.
echo 3/3 Dogal Turkce kadin sesi (Pocket, istege bagli)
%PY% tools\ses-uret.py --pocket-durum
if not errorlevel 1 goto ses_dene
echo Dogal Turkce kadin sesi icin yaklasik 1 GB indirilecek (bir kez).
choice /C EH /M "Kurulsun mu? E = Evet, H = Hayir"
if errorlevel 2 goto ses_yok
%PY% tools\ses-uret.py --kur-pocket
if errorlevel 1 goto ses_yok
:ses_dene
%PY% tools\ses-uret.py --dene-pocket
goto denetim
:ses_yok
echo Dogal ses kurulmadi; tahta daha basit bir yedek sesle konusacak. Sonra kurmak icin KUR-Windows'u yeniden calistirin.
:denetim
echo.
%PY% tools\tahta-mcp.py --dene
echo.
echo Bitti. Claude'u tamamen kapatin: saatin yanindaki ^^ isareti, Claude simgesi, sag tik, Cik.
echo Sonra Claude'u acin. Ayarlar, Gelistirici ekraninda klinik-koc "Calisiyor" gorunmeli.
pause
