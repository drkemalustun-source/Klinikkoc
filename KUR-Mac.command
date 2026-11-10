#!/bin/bash
# KlinikKoç kurulumu (macOS). Finder'da çift tıklayın.
# İlk açılışta macOS "geliştiricisi doğrulanamadı" derse: dosyaya sağ tıklayın → Aç → Aç.
cd "$(dirname "$0")" || exit 1
echo "KlinikKoç kurulumu (Mac)"
echo

if ! command -v python3 >/dev/null 2>&1 || ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
  echo "Python 3 bulunamadı (ya da çok eski)."
  echo "python.org/downloads adresinden macOS için Python 3'ü kurun, sonra bu dosyayı yeniden çalıştırın."
  echo "(Terminal 'geliştirici araçlarını kurmak ister misiniz?' diye sorarsa 'Yükle' de olur.)"
  read -r -p "Kapatmak için Enter'a basın..." _
  exit 1
fi

echo "1/3 Piper ses paketleri denetleniyor (zaten kuruluysa hızlı geçer)..."
if ! python3 tools/ses-uret.py --kur; then
  echo "Ses paketleri kurulamadı. Ders yine çalışır; ses için tarayıcı sesi kullanılır."
  echo "Hata 'SSL: CERTIFICATE_VERIFY_FAILED' ise: Uygulamalar → Python 3.x klasöründeki"
  echo "'Install Certificates.command' dosyasına çift tıklayıp bu kurulumu yeniden çalıştırın."
fi
python3 tools/makale_bulucu.py --kur || echo "PDF okuyucu kurulamadı; makaleler indirilir ama okunamaz."
echo
echo "2/3 Claude masaüstü uygulamasına KlinikKoç araçları ekleniyor..."
python3 tools/tahta-mcp.py --kur
echo
echo "3/3 Doğal Türkçe kadın sesi (Pocket, isteğe bağlı)"
if python3 tools/ses-uret.py --pocket-durum; then
  python3 tools/ses-uret.py --dene-pocket
else
  echo "Doğal Türkçe kadın sesi için yaklaşık 1 GB indirilecek (bir kez)."
  read -r -p "Kurulsun mu? (E/H) " cevap
  case "$cevap" in
    [EeYy]*)
      if python3 tools/ses-uret.py --kur-pocket; then
        python3 tools/ses-uret.py --dene-pocket
      else
        echo "Doğal ses kurulamadı; tahta daha basit bir yedek sesle konuşacak."
      fi ;;
    *) echo "Doğal ses kurulmadı; tahta daha basit bir yedek sesle konuşacak. Sonra kurmak için KUR-Mac'i yeniden çalıştırın." ;;
  esac
fi
echo
python3 tools/tahta-mcp.py --dene
echo
echo "Bitti. Claude uygulamasını tamamen kapatın (üst menüde Claude → Quit Claude ya da Cmd+Q) ve yeniden açın."
echo "Ayarlar › Geliştirici ekranında klinik-koc \"Çalışıyor\" görünmeli."
read -r -p "Kapatmak için Enter'a basın..." _
