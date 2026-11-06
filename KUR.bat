@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo KlinikKoc kurulumu
echo.
set PY=python
where python >nul 2>nul || set PY=py -3
echo 1/2 Piper ses paketleri denetleniyor (zaten kuruluysa hizli gecer)...
%PY% tools\ses-uret.py --kur
echo.
echo 2/2 Claude masaustu uygulamasina KlinikKoc araclari ekleniyor...
%PY% tools\tahta-mcp.py --kur
echo.
%PY% tools\tahta-mcp.py --dene
echo.
echo Bitti. Claude uygulamasini saatin yanindaki simgeden tamamen kapatip yeniden acin.
pause
