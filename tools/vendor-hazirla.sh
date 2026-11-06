#!/bin/sh
# vendor/ klasöründeki üçüncü taraf kitaplıklarını yeniden üretir (yalnız geliştirici için).
# Sürümler sabittir; değiştirmek isterseniz aşağıdaki numaraları güncelleyip yeniden çalıştırın.
# Gerekenler: Node.js ve npm.
set -e
KOK="$(cd "$(dirname "$0")/.." && pwd)"
GECICI="$(mktemp -d)"
cd "$GECICI"
npm init -y >/dev/null
npm install --no-audit --no-fund --ignore-scripts \
  @mintplex-labs/piper-tts-web@1.0.5 onnxruntime-web@1.18.0 @huggingface/transformers@3.7.6 @anthropic-ai/sdk@0.137.0 esbuild@0.25.0 >/dev/null
# Piper: kitaplık ve onnxruntime-web'in JS kısmı tek dosyada; .wasm dosyaları CDN'den gelir
# (cdnjs onnxruntime-web 1.18.0 ve jsDelivr piper-wasm 1.0.0). fs/path yalnız Node kolunda geçer, tarayıcıda çağrılmaz.
echo "export * from '@mintplex-labs/piper-tts-web';" > piper-giris.js
npx esbuild piper-giris.js --bundle --format=esm --minify --platform=browser --external:fs --external:path --outfile="$KOK/vendor/piper-tts-web.js" --log-level=warning
# Transformers.js: dağıtım paketi zaten tek dosya; .wasm dosyası jsDelivr'den gelir.
cp node_modules/@huggingface/transformers/dist/transformers.min.js "$KOK/vendor/transformers.min.js"
# Anthropic SDK: yalnız Claude API kipi seçilince ve ilk soruda yüklenir.
echo "export * from '@anthropic-ai/sdk'; export { default } from '@anthropic-ai/sdk';" > anthropic-giris.js
npx esbuild anthropic-giris.js --bundle --format=esm --minify --platform=browser --outfile="$KOK/vendor/anthropic-sdk.js" --log-level=warning
cd "$KOK"
rm -rf "$GECICI"
echo "vendor/ güncellendi."
