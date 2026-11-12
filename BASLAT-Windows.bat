@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem KlinikKoc'u acar: yerel sunucuyu baslatir ve ana sayfayi tarayicida gosterir.
rem Ders paketi eklemek, makaleler ve ogretmen sihirbazi bu sunucuyla calisir.
set PY=python
where python >nul 2>nul || set PY=py -3
%PY% -c "import sys" >nul 2>nul
if errorlevel 1 (
  echo Python bulunamadi. Once KUR-Windows dosyasini calistirin.
  pause
  exit /b 1
)
echo KlinikKoc aciliyor. Bu pencere acik kaldikca KlinikKoc calisir; isiniz bitince pencereyi kapatin.
%PY% tools\sunucu.py --sayfa ana.html
pause
