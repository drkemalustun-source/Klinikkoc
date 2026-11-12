#!/bin/bash
# KlinikKoç'u açar: yerel sunucuyu başlatır ve ana sayfayı tarayıcıda gösterir. Finder'da çift tıklayın.
# Ders paketi eklemek, makaleler ve öğretmen sihirbazı bu sunucuyla çalışır.
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 bulunamadı. Önce KUR-Mac dosyasını çalıştırın."
  read -r -p "Kapatmak için Enter'a basın..." _
  exit 1
fi
echo "KlinikKoç açılıyor. Bu pencere açık kaldıkça KlinikKoç çalışır; işiniz bitince pencereyi kapatın."
python3 tools/sunucu.py --sayfa ana.html
