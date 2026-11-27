@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem KlinikKoc'u acar: yerel sunucuyu baslatir ve ana sayfayi tarayicida gosterir.
rem Ders paketi eklemek, makaleler ve ogretmen sihirbazi bu sunucuyla calisir.
set PY=python
where python >nul 2>nul || set PY=py -3
rem KUR'un sectigi Python (3.10-3.13; gerekirse KlinikKoc'un kendi indirdigi) varsa o kullanilir.
set "PYYOL="
if exist ".python\secilen.txt" set /p PYYOL=<".python\secilen.txt"
if defined PYYOL if exist "%PYYOL%" set PY="%PYYOL%"
%PY% -c "import sys" >nul 2>nul
if errorlevel 1 (
  echo Python bulunamadi. Once KUR-Windows dosyasini calistirin.
  pause
  exit /b 1
)
echo KlinikKoc aciliyor. Bu pencere acik kaldikca KlinikKoc calisir; isiniz bitince pencereyi kapatin.
%PY% tools\sunucu.py --sayfa ana.html
pause
