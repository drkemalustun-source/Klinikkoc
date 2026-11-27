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
if errorlevel 1 goto pyyok
rem Bu indirilen kopya ise ve KlinikKoc sabit yerinde (C:\KlinikKoc) kuruluysa oradaki acilir.
set "YER="
set "YERHEDEF="
for /f "tokens=1,*" %%a in ('%PY% tools\kurulum_yeri.py --karar 2^>nul') do (set "YER=%%a" & set "YERHEDEF=%%b")
if "%YER%"=="ORADA" if exist "%YERHEDEF%\BASLAT-Windows.bat" (
  echo KlinikKoc %YERHEDEF% klasorunde kurulu; oradan aciliyor.
  "%YERHEDEF%\BASLAT-Windows.bat"
)
:pyyok
%PY% -c "import sys" >nul 2>nul
if errorlevel 1 (
  echo Python bulunamadi. Once KUR-Windows dosyasini calistirin.
  pause
  exit /b 1
)
echo KlinikKoc aciliyor. Bu pencere acik kaldikca KlinikKoc calisir; isiniz bitince pencereyi kapatin.
%PY% tools\sunucu.py --sayfa ana.html
pause
