#!/usr/bin/env python3
"""Pocket TTS Türkçe ses işçisi (tools/pocket_ses.py başlatır; elle çalıştırmak gerekmez).

Ses ortamındaki Python ile (.ses-ortami) çalışır: modeli bir kez yükler, sonra standart girdiden
gelen her satırı ({"no":..,"metin":..,"ses":..,"tohum":..}) WAV'a çevirir ve standart çıktıya
"@@" ile başlayan tek satırlık bir JSON yanıtı yazar (WAV base64). Model: wite-tech/pocket-tts-turkish
(CC-BY-4.0); model önbelleği tools/.sesler/hf altında tutulur.
"""
import base64
import io
import json
import os
import sys
import time
import wave

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("HF_HOME", os.path.join(KOK, "tools", ".sesler", "hf"))
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

# Windows'ta borular yerel kod sayfasıyla açılır; Türkçe harfler bozulmasın diye UTF-8'e çevrilir.
sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")
# Kitaplıkların yazdıkları yanıt kanalına karışmasın: protokol yalnız gerçek stdout'tan gider.
_kanal = sys.stdout
sys.stdout = sys.stderr


def _sentencepiece_yamasi():
    """Windows'ta sentencepiece, Türkçe harf içeren yoldaki (ör. 'koç deneme') tokenizer.model dosyasını
    kendisi açamayabilir: yol bozulur ('koÃ§') ve NOT_FOUND verir. Böyle bir yolda dosyayı Python okur,
    içeriği çözücüye verir. (İşçi -X utf8 ile başlar; bu ikinci savunmadır.)"""
    try:
        import sentencepiece
    except Exception:
        return
    asil = sentencepiece.SentencePieceProcessor.LoadFromFile

    def dosyadan_yukle(self, filename):
        yol = os.fsdecode(os.fspath(filename))
        if yol.isascii():
            return asil(self, filename)
        with open(yol, "rb") as f:
            return self.LoadFromSerializedProto(f.read())

    sentencepiece.SentencePieceProcessor.LoadFromFile = dosyadan_yukle


def yanit(veri):
    _kanal.write("@@" + json.dumps(veri, ensure_ascii=False) + "\n")
    _kanal.flush()


def wav_bayt(ses, oran):
    import numpy as np
    ses = np.clip(np.asarray(ses, dtype=np.float32).reshape(-1), -1.0, 1.0)
    tampon = io.BytesIO()
    with wave.open(tampon, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(oran)
        w.writeframes((ses * 32767.0).astype("<i2").tobytes())
    return tampon.getvalue()


def main():
    t0 = time.time()
    try:
        _sentencepiece_yamasi()
        from pocket_tts_turkish import TurkishTTS
        tts = TurkishTTS.from_pretrained(device="cpu")
        tts.generate("Merhaba.", voice=tts.voices[0], seed=1)  # ısınma: ilk cümle yavaş olmasın
    except Exception as e:
        yanit({"hazir": False, "hata": "%s: %s" % (type(e).__name__, e)})
        return 1
    yanit({"hazir": True, "sure": round(time.time() - t0, 1), "sesler": tts.voices, "oran": tts.sample_rate})
    for satir in sys.stdin:
        satir = satir.strip()
        if not satir:
            continue
        no = None
        try:
            istek = json.loads(satir)
            no = istek.get("no")
            t = time.time()
            ses = tts.generate(istek["metin"], voice=istek.get("ses") or "female_3",
                               seed=istek.get("tohum"))
            yanit({"no": no, "wav": base64.b64encode(wav_bayt(ses, tts.sample_rate)).decode("ascii"),
                   "sure": round(time.time() - t, 2)})
        except Exception as e:
            yanit({"no": no, "hata": "%s: %s" % (type(e).__name__, e)})
    return 0


if __name__ == "__main__":
    sys.exit(main())
