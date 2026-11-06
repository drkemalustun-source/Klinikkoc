# Üçüncü taraf kitaplıkları

Bu klasördeki dosyalar `tools/vendor-hazirla.sh` ile üretilir; elle değiştirmeyin.

| Dosya | Kitaplık | Sürüm | Lisans |
|---|---|---|---|
| `piper-tts-web.js` | @mintplex-labs/piper-tts-web (Piper TTS'nin tarayıcı sürümü) + onnxruntime-web'in JS kısmı | 1.0.5 / 1.18.0 | MIT / MIT |
| `transformers.min.js` | @huggingface/transformers (Transformers.js) | 3.7.6 | Apache 2.0 |
| `anthropic-sdk.js` | @anthropic-ai/sdk (Claude API'nin resmî JavaScript kitaplığı; yalnız API kipinde yüklenir) | 0.137.0 | MIT |

Çalışırken indirilenler (kitaplıkların kendi varsayılanları):

- WebAssembly dosyaları: cdnjs.cloudflare.com (onnxruntime-web 1.18.0), cdn.jsdelivr.net (piper-wasm 1.0.0, Transformers.js 3.7.6).
- Modeller: huggingface.co. Piper Türkçe sesleri MIT (rhasspy/piper-voices; varsayılan İlkiz: ilkeraktuna/piper-tts-tr-ilkiz-medium, MIT), Whisper modelleri MIT (onnx-community), Duyu-small Apache 2.0 (KaanAydinli/Duyu-small).

İkinci aşamada çevrimdışı kurulum için WebAssembly dosyaları ve seçilen modeller de bu klasöre alınabilir.
