/* Konuşma tanıma adaptörü: OpenAI Whisper, tarayıcıda Transformers.js ile.
 * Ekran kartı (WebGPU) varsa onu, yoksa işlemciyi (WASM) kullanır. Ses cihazdan çıkmaz.
 * Model ilk kullanımda Hugging Face'ten indirilir ve tarayıcı önbelleğinde kalır.
 *
 * Whisper sessiz bölümlerde ve kaydın sonunda bazen hiç söylenmemiş cümleler uydurur
 * ("İzlediğiniz için teşekkürler" gibi). Önlemler:
 *   1. Ses etkinliği algılama: konuşma yoksa modele hiç gönderilmez; sessiz baş ve son kırpılır.
 *   2. Tekrar süzgeci: aynı öbek art arda 3+ kez geliyorsa bir kez bırakılır.
 *   3. Bilinen uydurma kalıplar silinir (AT.ses.cleanTranscript). */
(function (AT) {
  'use strict';
  const ses = AT.ses;

  const MODELS = {
    'whisper-base': { repo: 'onnx-community/whisper-base', label: 'Whisper base (74M)', gpuOnly: false },
    'whisper-small': { repo: 'onnx-community/whisper-small', label: 'Whisper small (244M)', gpuOnly: false },
    'whisper-turbo': { repo: 'onnx-community/whisper-large-v3-turbo', label: 'Whisper large-v3-turbo (809M, yalnız WebGPU)', gpuOnly: true }
  };

  let libPromise = null;
  const lib = () => (libPromise = libPromise || import(ses.ROOT + 'vendor/transformers.min.js'));

  async function hasWebGPU() {
    if (!navigator.gpu) return false;
    try { return !!(await navigator.gpu.requestAdapter()); } catch (e) { return false; }
  }

  for (const [id, m] of Object.entries(MODELS)) {
    ses.registerSTT(id, () => {
      let pipe = null;
      let device = null;
      return {
        id,
        label: m.label,
        info: {
          offline: 'Evet (ilk indirmeden sonra)',
          dataLeavesDevice: 'Hayır',
          note: 'Model bir kez indirilir; WebGPU yoksa yavaş çalışır.'
        },
        get device() { return device; },
        async status() {
          const gpu = await hasWebGPU();
          if (m.gpuOnly && !gpu) return { ok: false, message: 'Bu model WebGPU ister; bu cihazda yok.' };
          return { ok: true, message: gpu ? 'WebGPU (ekran kartı) kullanılacak.' : 'WebGPU yok; işlemcide (WASM) çalışacak, yavaş olabilir.' };
        },
        async init(onProgress) {
          const t0 = performance.now();
          const tf = await lib();
          tf.env.allowLocalModels = false;
          device = (await hasWebGPU()) ? 'webgpu' : 'wasm';
          const dtype = device === 'webgpu'
            ? { encoder_model: 'fp32', decoder_model_merged: 'q4' }
            : { encoder_model: 'q8', decoder_model_merged: 'q8' };
          const meter = ses.progressMeter(onProgress);
          pipe = await tf.pipeline('automatic-speech-recognition', m.repo, {
            device,
            dtype,
            progress_callback: (p) => { if (p.status === 'progress' || p.status === 'done') meter.update(p.file, p.loaded, p.total); }
          });
          // İlk çalıştırma (WebGPU gölgelendirici derlemesi) ölçümü bozmasın diye bir kez ısıt.
          await pipe(new Float32Array(ses.SAMPLE_RATE), { language: 'turkish', task: 'transcribe' });
          return { loadMs: performance.now() - t0, bytes: meter.bytes, device };
        },
        async transcribe(audio16k) {
          if (!pipe) throw new Error('Model hazır değil.');
          const speech = ses.detectSpeech(audio16k, ses.SAMPLE_RATE);
          if (!speech) return { text: '', ms: 0, note: 'Konuşma algılanmadı; modele gönderilmedi.' };
          const t0 = performance.now();
          const long = speech.audio.length > ses.SAMPLE_RATE * 30;
          const out = await pipe(speech.audio, {
            language: 'turkish',
            task: 'transcribe',
            ...(long ? { chunk_length_s: 30, stride_length_s: 5 } : {})
          });
          const raw = (Array.isArray(out) ? out.map((o) => o.text).join(' ') : out.text) || '';
          return { text: ses.cleanTranscript(raw), raw, ms: performance.now() - t0, device };
        }
      };
    });
  }
})(window.AT = window.AT || {});
