#!/usr/bin/env python3
"""Bir dersin anlatım seslerini önceden, bir kez üretir (Piper, açık kaynak, ücretsiz).

Üretilen MP3 dosyaları dersle birlikte yayımlanır; öğrencinin cihazında hiçbir ses
modeli ya da servis çalışmaz. Yalnızca ders hazırlayan bilgisayarda gerekir.

Kurulum (bir kez):
  python tools/ses-uret.py --kur

Kullanım:
  python tools/ses-uret.py peri-implantitis-cerrahi
  python tools/ses-uret.py peri-implantitis-cerrahi --ses tr_TR-fahrettin-medium --hiz 1.0
  python tools/ses-uret.py peri-implantitis-cerrahi --deneme --cikti %TEMP%\\ses-deneme

Ses motoru ve ses ses/ses-ayari.json'dan gelir (varsayılan: Pocket TTS Türkçe, female_3,
wite-tech/pocket-tts-turkish, CC-BY-4.0). Pocket ayrı bir Python ortamında çalışır; bir kez:
  python tools/ses-uret.py --kur-pocket [Python 3.10–3.13 yolu]
Eski Piper sesi için: --motor piper (ya da --ses tr_TR-dfki-medium).

Yaptıkları:
  - Ses modelini (varsayılan tr_TR-dfki-medium, ~63 MB) ilk seferde Hugging Face'ten indirir
    ve tools/.sesler/ klasöründe saklar.
  - Her adımın anlatımını {n} işaretlerine göre parçalara, parçaları cümlelere böler.
    Metin önce ses/telaffuz.json sözlüğünden geçer (js/ses/ses.js ile aynı kural).
  - Her parça bir MP3 olur; manifest her cümlenin başlangıç saniyesini tutar
    (oynatıcı altyazıyı cümle cümle bununla eşler).
  - Soru adımlarına "Doğru. / Tam değil." geri bildirim sesleri de üretilir.
  - Metni değişmeyen parçalar yeniden üretilmez (dosya adı metnin özetini taşır).

Çıktı: lessons/<id>/audio/*.mp3, manifest.json ve dosyadan açma için manifest.js.
Sesler normal hızda üretilir; --hiz yalnızca oynatıcının başlangıç hızını belirler
(ses testinde dinlenen 1,2 hızla aynı yöntem).
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SES_KLASORU = os.path.join(KOK, "tools", ".sesler")
PAKETLER = ["piper-tts", "soundfile", "numpy"]
HF = "https://huggingface.co/rhasspy/piper-voices/resolve/main/tr/tr_TR/{ad}/{kalite}/tr_TR-{ad}-{kalite}{uzanti}?download=true"
SESSIZLIK_CUMLE = 0.25  # cümleler arası boşluk (sn)


# ---- js/core.js AT.splitCues ve AT.feedbackText ile aynı ----
def split_cues(say):
    parts, last, cue = [], 0, 0
    text = say or ""
    for m in re.finditer(r"\{(\d+)\}", text):
        parts.append({"cue": cue, "text": text[last:m.start()].strip()})
        cue = int(m.group(1))
        last = m.end()
    parts.append({"cue": cue, "text": text[last:].strip()})
    return [p for i, p in enumerate(parts) if p["text"] or p["cue"] or i == 0]


def feedback_text(q, correct):
    return ("Doğru. " if correct else "Tam değil. ") + (q.get("explanation") or "")


# ---- js/speech.js sentences() ile aynı bölme ----
def sentences(text):
    out = [m.group(0).strip() for m in re.finditer(r"[^.!?…;:]+[.!?…;:]*\s*", text)]
    out = [s for s in out if s]
    return out or [text]


# ---- Altyazı ile aynı düz metin: **kalın** ve _italik_ işaretleri sese gitmez ----
def plain(text):
    return re.sub(r"\*\*|(?<!\w)_|_(?!\w)", "", text)


# ---- js/ses/ses.js replaceTr: Türkçe büyük/küçük harf duyarsız, sözcük başında eşleşir ----
def tr_lower(s):
    return s.replace("I", "ı").replace("İ", "i").lower()


def is_word(ch):
    return bool(ch) and (ch.isalnum())


def replace_tr(text, find, repl, whole):
    low, key = tr_lower(text), tr_lower(find)
    if not key or len(low) != len(text):
        return text
    out, frm = [], 0
    while True:
        i = low.find(key, frm)
        if i == -1:
            break
        before = low[i - 1] if i > 0 else ""
        after = low[i + len(key)] if i + len(key) < len(low) else ""
        if not is_word(before) and (not whole or not is_word(after)):
            out.append(text[frm:i] + repl)
        else:
            out.append(text[frm:i + len(key)])
        frm = i + len(key)
    out.append(text[frm:])
    return "".join(out)


def load_dictionary():
    path = os.path.join(KOK, "ses", "telaffuz.json")
    if not os.path.exists(path):
        return []
    data = json.load(open(path, encoding="utf-8"))
    entries = data.get("entries", []) if isinstance(data, dict) else data
    entries = [e for e in entries if e.get("yazim") and e.get("okunus") is not None]
    return sorted(entries, key=lambda e: -len(e["yazim"]))


def pronounce(text, dictionary):
    for e in dictionary:
        text = replace_tr(text, e["yazim"], e["okunus"], bool(e.get("tam")))
    return text


# ---- Ses modeli ----
def voice_files(name):
    m = re.match(r"tr_TR-([a-z]+)-(x_low|low|medium|high)$", name)
    if not m:
        sys.exit("Ses adı tr_TR-<ad>-<kalite> biçiminde olmalı, ör. tr_TR-dfki-medium")
    os.makedirs(SES_KLASORU, exist_ok=True)
    paths = []
    for ext in (".onnx", ".onnx.json"):
        dest = os.path.join(SES_KLASORU, name + ext)
        if not os.path.exists(dest):
            url = HF.format(ad=m.group(1), kalite=m.group(2), uzanti=ext)
            print("İndiriliyor:", name + ext)
            tmp = dest + ".part"
            with urllib.request.urlopen(url, timeout=60) as r, open(tmp, "wb") as f:
                while True:
                    block = r.read(1 << 20)
                    if not block:
                        break
                    f.write(block)
            os.replace(tmp, dest)
        paths.append(dest)
    return paths[0]


def main():
    ap = argparse.ArgumentParser(description="Ders seslerini Piper ile önceden üretir.")
    ap.add_argument("ders", nargs="?", help="ders kimliği (lessons/ altındaki klasör adı)")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import pocket_ses
    ayar = pocket_ses.ayar()
    ap.add_argument("--motor", choices=["piper", "pocket"], default=None,
                    help="ses motoru (vars. ses/ses-ayari.json: %s)" % ayar.get("motor"))
    ap.add_argument("--ses", default=None,
                    help="pocket: female_1..3 / male_1..3; piper: tr_TR-<ad>-<kalite> (vars. ayar dosyasından)")
    ap.add_argument("--kur-pocket", nargs="?", const="", metavar="PYTHON",
                    help="Pocket ses ortamını (.ses-ortami) kur ve çık; isteğe bağlı Python 3.10–3.13 yolu")
    ap.add_argument("--hiz", type=float, default=1.2, help="oynatıcının başlangıç hızı (vars. 1.2)")
    ap.add_argument("--kalite", type=float, default=0.6,
                    help="MP3 sıkıştırma 0 (en iyi) – 1 (en küçük); vars. 0.6")
    ap.add_argument("--cikti", help="çıktı klasörü (vars. lessons/<id>/audio); deneme için başka klasör verin")
    ap.add_argument("--deneme", action="store_true", help="yalnız ilk bölümü üret (--cikti ile birlikte kullanın)")
    ap.add_argument("--kur", action="store_true", help="gereken Python paketlerini kur ve çık")
    a = ap.parse_args()

    if a.kur:
        sys.exit(subprocess.call([sys.executable, "-m", "pip", "install", "--upgrade"] + PAKETLER))
    if a.kur_pocket is not None:
        sys.exit(pocket_ses.kur(a.kur_pocket or None))
    if a.deneme and not a.cikti:
        ap.error("--deneme ile --cikti klasörü de verin (dersin kendi ses klasörü bozulmasın)")
    if a.motor is None:
        # --ses tr_TR-... verildiyse Piper demektir.
        a.motor = "piper" if (a.ses or "").startswith("tr_TR-") else (ayar.get("motor") or "piper")
    if a.ses is None:
        a.ses = (ayar.get("ses") or "female_3") if a.motor == "pocket" else (ayar.get("yedek") or "tr_TR-dfki-medium")
    if not a.ders:
        ap.error("ders kimliği gerekli")

    try:
        import numpy as np
        import soundfile as sf
        from piper import PiperVoice
        from piper.config import SynthesisConfig
    except ImportError as e:
        sys.exit("Eksik paket (%s). Önce: python tools/ses-uret.py --kur" % e)
    if "MP3" not in sf.available_formats():
        sys.exit("soundfile MP3 yazamıyor; python tools/ses-uret.py --kur ile güncelleyin.")

    lesson_dir = os.path.join(KOK, "lessons", a.ders)
    lesson = json.load(open(os.path.join(lesson_dir, "ders.json"), encoding="utf-8"))
    out_dir = os.path.abspath(a.cikti) if a.cikti else os.path.join(lesson_dir, "audio")
    os.makedirs(out_dir, exist_ok=True)
    dictionary = load_dictionary()

    if a.motor == "pocket":
        isci = pocket_ses.PocketIsci()
        print("Pocket TTS Türkçe (%s) yükleniyor..." % a.ses)
        isci.baslat()
        isci.hazir.wait(900)
        if isci.durum != "hazır":
            sys.exit(isci.durum)
        rate = 24000
        tohum = ayar.get("tohum")

        def synth(s):
            import io as _io
            data, sr = sf.read(_io.BytesIO(isci.wav(s, a.ses, tohum)), dtype="int16")
            if sr != rate:
                sys.exit("Beklenmeyen örnekleme hızı: %s" % sr)
            return data
        voice_id = "pocket:" + a.ses
    else:
        model = voice_files(a.ses)
        voice = PiperVoice.load(model)
        rate = voice.config.sample_rate
        cfg = SynthesisConfig()

        def synth(s):
            audio = [c.audio_int16_array for c in voice.synthesize(s, syn_config=cfg)]
            return np.concatenate(audio) if audio else np.zeros(0, dtype=np.int16)
        voice_id = a.ses
    gap = np.zeros(int(rate * SESSIZLIK_CUMLE), dtype=np.int16)

    manifest = {"format": "mp3", "voice": voice_id, "rate": a.hiz, "steps": {}}
    keep, made, reused = set(), 0, 0
    old = {}
    old_path = os.path.join(out_dir, "manifest.json")
    if os.path.exists(old_path):
        try:
            for entries in json.load(open(old_path, encoding="utf-8")).get("steps", {}).values():
                for e in entries:
                    if isinstance(e, dict):
                        old[e["src"]] = e
        except Exception:
            pass
    t_start = time.time()

    def render(key, text):
        nonlocal made, reused
        sents = sentences(plain(text))
        spoken = [pronounce(s, dictionary) for s in sents]
        h = hashlib.sha1(("%s|%s" % (voice_id, "\n".join(spoken))).encode("utf-8")).hexdigest()[:10]
        name = "%s-%s.mp3" % (re.sub(r"[^a-zA-Z0-9_-]", "_", key), h)
        src = "audio/" + name
        keep.add(name)
        path = os.path.join(out_dir, name)
        if os.path.exists(path) and src in old:
            reused += 1
            return old[src]
        pieces, starts, t = [], [], 0.0
        for i, s in enumerate(spoken):
            audio = synth(s)
            starts.append(round(t, 2))
            pieces.append(audio)
            t += len(audio) / rate
            if i < len(spoken) - 1:
                pieces.append(gap)
                t += len(gap) / rate
        data = np.concatenate(pieces) if pieces else gap
        sf.write(path, data, rate, format="MP3", compression_level=a.kalite)
        made += 1
        if made % 20 == 0:
            print("  %d parça üretildi..." % made)
        return {"src": src, "dur": round(len(data) / rate, 2),
                "sentences": [{"t": st, "text": s} for st, s in zip(starts, sents)]}

    sections = lesson["sections"][:1] if a.deneme else lesson["sections"]
    for sec in sections:
        for st in sec["steps"]:
            q = st.get("question")
            parts = split_cues(st.get("say") or (q and q.get("prompt")))
            manifest["steps"][st["id"]] = [
                render("%s-%d" % (st["id"], i), p["text"]) if p["text"] else None
                for i, p in enumerate(parts)]
            if q:
                manifest["steps"][st["id"] + ":dogru"] = [render(st["id"] + "-dogru", feedback_text(q, True))]
                manifest["steps"][st["id"] + ":yanlis"] = [render(st["id"] + "-yanlis", feedback_text(q, False))]

    for f in os.listdir(out_dir):
        if f.endswith(".mp3") and f not in keep:
            os.remove(os.path.join(out_dir, f))
    body = json.dumps(manifest, ensure_ascii=False, indent=1)
    open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8").write(body + "\n")
    open(os.path.join(out_dir, "manifest.js"), "w", encoding="utf-8").write(
        "/* tools/ses-uret.py üretti; elle düzenlemeyin. */\nAT.registerAudioManifest(%s, %s);\n"
        % (json.dumps(a.ders), body))

    total = sum(os.path.getsize(os.path.join(out_dir, f)) for f in keep)
    secs = sum(e["dur"] for v in manifest["steps"].values() for e in v if e)
    print("Ses hazır: %d yeni, %d değişmemiş parça; toplam %.1f dk, %.1f MB; %d sn sürdü."
          % (made, reused, secs / 60, total / 1e6, time.time() - t_start))
    if not (lesson.get("audio") or {}).get("manifest"):
        print('Not: ders.json içinde "audio": {"manifest": "audio/manifest.json"} alanı yok; ekleyin.')


if __name__ == "__main__":
    main()
