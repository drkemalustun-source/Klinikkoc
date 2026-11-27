@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "KOK=%~dp0"
echo KlinikKoc kurulumu (Windows)
echo.
call :python_bul
if not defined PY (
  echo Uygun Python bulunamadi ve indirilemedi. python.org/downloads adresinden Python 3.12'yi kurun
  echo ^(kurulumda "Add python.exe to PATH" kutusunu isaretleyin^), sonra bu dosyayi yeniden calistirin.
  pause
  exit /b 1
)
rem Yeni kurulum sabit bir yere (C:\KlinikKoc) kopyalanir; daha once kurulmus klasor yerinde kalir.
set "YER=BURADA"
set "YERHEDEF="
for /f "tokens=1,*" %%a in ('%PY% tools\kurulum_yeri.py --karar') do (set "YER=%%a" & set "YERHEDEF=%%b")
if "%YER%"=="ORADA" (
  echo KlinikKoc zaten %YERHEDEF% klasorunde kurulu; kurulum oradan suruyor.
  "%YERHEDEF%\KUR-Windows.bat"
)
if "%YER%"=="TASI" (
  echo KlinikKoc sabit yerine kopyalaniyor: %YERHEDEF% ...
  %PY% tools\kurulum_yeri.py --kopyala
  if not errorlevel 1 (
    echo Kurulum %YERHEDEF% klasorunden suruyor. Indirdiginiz klasoru sonra silebilirsiniz.
    echo.
    "%YERHEDEF%\KUR-Windows.bat"
  )
)
if not exist "%KOK%.python" mkdir "%KOK%.python"
%PY% -X utf8 -c "import sys; print(sys.executable)" > "%KOK%.python\secilen.txt"
echo Kullanilan Python:
type "%KOK%.python\secilen.txt"
echo.
echo 1/3 Piper ses paketleri denetleniyor (zaten kuruluysa hizli gecer)...
%PY% tools\ses-uret.py --kur
%PY% tools\makale_bulucu.py --kur
echo.
echo Anlam aramasi kuruluyor (yaklasik 120 MB, bir kez; Turkce soruyla Ingilizce makalede arama icin)...
%PY% tools\bilgi_bankasi.py --kur-anlam
if errorlevel 1 echo Anlam aramasi kurulamadi. Arama yine calisir: sozcuk aramasi ve Turkce-Ingilizce terim eslemesi.
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
echo Eski surum klasorleri araniyor (onayiniz olmadan hicbir sey silinmez)...
%PY% tools\eski_surumler.py --sor
echo.
echo KlinikKoc klasoru: %KOK%
echo Bitti. Claude'u tamamen kapatin: saatin yanindaki ^^ isareti, Claude simgesi, sag tik, Cik.
echo Sonra Claude'u acin. Ayarlar, Gelistirici ekraninda klinik-koc "Calisiyor" gorunmeli.
pause
exit /b 0

:python_bul
rem KlinikKoc ve ses paketleri Python 3.10-3.13 ister (daha yenisi icin ses paketleri henuz yok).
rem Sira: py -3.13 ... -3.10, python, daha once indirilen (.python klasoru), en son indirme.
rem Bilgisayarda uygun Python varsa hicbir sey indirilmez.
set "PY="
for %%v in (3.13 3.12 3.11 3.10) do if not defined PY (py -%%v -c "import sys" >nul 2>nul && set "PY=py -%%v")
if not defined PY (python -c "import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 13) else 1)" >nul 2>nul && set "PY=python")
if not defined PY for /d %%d in ("%KOK%.python\cpython-3.12*") do if exist "%%d\python.exe" set PY="%%d\python.exe"
if defined PY exit /b 0
echo Bu bilgisayarda uygun Python (3.10-3.13) yok. KlinikKoc'un kendi Python'u indiriliyor
echo (yaklasik 70 MB, bir kez; yalniz KlinikKoc klasorune kurulur, bilgisayarin ayarlarina dokunmaz)...
set "UVZIP=%TEMP%\klinikkoc-uv.zip"
set "UVDIR=%TEMP%\klinikkoc-uv"
set "UVARCH=x86_64"
if /i "%PROCESSOR_ARCHITECTURE%"=="ARM64" set "UVARCH=aarch64"
set "UVURL=https://github.com/astral-sh/uv/releases/download/0.9.0/uv-%UVARCH%-pc-windows-msvc.zip"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; try { Invoke-WebRequest -UseBasicParsing -Uri $env:UVURL -OutFile $env:UVZIP; Expand-Archive -Force -Path $env:UVZIP -DestinationPath $env:UVDIR; exit 0 } catch { Write-Host $_; exit 1 }"
if errorlevel 1 exit /b 0
"%UVDIR%\uv.exe" python install 3.12 --install-dir "%KOK%.python" --no-bin --no-registry
if errorlevel 1 exit /b 0
for /d %%d in ("%KOK%.python\cpython-3.12*") do if exist "%%d\python.exe" set PY="%%d\python.exe"
exit /b 0
