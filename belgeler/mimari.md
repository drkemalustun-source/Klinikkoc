# Mimari ve ders dosyası başvurusu

## Katmanlar

```
ders.json  ──►  core.js (yükleme, ilerleme)  ──►  player.js (adım akışı)
                                                    │        │
                                         speech.js ◄┘        └► board.js (tahta)
                                     (Web Speech | ses dosyası | sessiz)
                                                    │
                                              app.js (arayüz, sorular)
                                                    │
                                         js/qa/ (soru sor: bilgi bulma + sağlayıcılar)
```

- Oynatıcı ders içeriğini bilmez; yalnızca şemayı bilir. Yeni bir ders, yeni bir `ders.json` demektir.
- Ses motoru değiştirilebilir. Oynatıcı yalnızca `speak(metin, {stepId, segment, onSentence})`, `replay()` ve `stop()` çağırır.
  `onSentence` o an okunan cümleyi verir; altyazı bununla eşlenir. Hazır seste cümle zamanları manifestte durur
  (`tools/ses-uret.py` üretir: `{src, dur, sentences: [{t, text}]}`).
  Hazır ses manifesti varsa `AudioFileEngine`, yoksa `WebSpeechEngine`, sessiz modda `SilentEngine` kullanılır.
- Varsayılan ayarlarla hiçbir ağ isteği dış servise gitmez; tüm dosyalar aynı klasörden gelir. Tek istisna,
  kullanıcının kendisi seçtiği soru-cevap modelidir (aşağıda).

## Ses katmanı (`js/ses/`)

1. aşamada eklendi. Oynatıcı ders anlatımını önceden üretilmiş seslerle (`speech.js` içindeki `AudioFileEngine`)
çalar; bu katman canlı seslendirme ve konuşma tanıma (3. aşama) ile ses testi sayfası içindir.

```
                 AT.ses  (ses.js: kayıt defteri, telaffuz sözlüğü, ölçüm ve ses yardımcıları)
                ┌──────────────┴──────────────┐
         TextToSpeech                   SpeechToText
     tts-tarayici.js (Web Speech)   stt-tarayici.js (Web Speech: sunucu | cihaz içi)
     tts-piper.js    (Piper WASM)   stt-whisper.js  (Transformers.js: WebGPU | WASM)
                                    stt-duyu.js     (tools/sunucu.py üzerinden Python)
```

- Her motor bir adaptördür ve kendini `AT.ses.registerTTS(id, fabrika)` ya da `registerSTT` ile kaydeder.
  Yeni motor = yeni dosya; ör. üniversite sunucusundaki bir model için yalnızca HTTP çağıran bir adaptör.
- Ortak arayüz (ayrıntı `ses.js` başındaki açıklamada):
  - TTS: `init()`, `voices()`, `speak(metin, {voice, rate})`, `stop()`, isteğe bağlı `synthesize()`.
  - STT: `status()`, `init()`, `transcribe(ses16k)`. Tüm motorlar aynı 16 kHz kaydı alır.
- Metin TTS'ye gitmeden önce `AT.ses.pronounce()` ile telaffuz sözlüğünden (`ses/telaffuz.json`) geçer.
- Ağır kitaplıklar (`vendor/`) yalnızca ilgili motor seçilince yüklenir. Modeller ilk kullanımda
  Hugging Face'ten indirilir ve tarayıcıda saklanır.
- `ses-testi/` motorları karşılaştıran ayrı sayfadır. Uygulamadan bağımsızdır.

## Ders dosyası

```jsonc
{
  "schemaVersion": 1,
  "id": "peri-implantitis-cerrahi",          // klasör adıyla aynı
  "title": "...", "subtitle": "...", "language": "tr-TR",
  "level": "...", "estimatedMinutes": 40,
  "source": { "citation": "...", "doi": "...", "license": "CC BY 4.0" },
  "assets": { "fig1": { "src": "assets/fig1.png", "alt": "...", "caption": "...", "credit": "..." } },
  "goals": [ { "id": "H1", "title": "...", "subgoals": [ { "id": "H1.1", "text": "...", "sourceRef": "s. 4" } ] } ],
  "sections": [
    { "id": "h1", "title": "...", "goals": ["H1.1", "H1.2"],
      "steps": [
        { "id": "h1-1",
          "say": "Anlatım metni. {1}Bu cümlede vurgu belirir.",
          "board": [
            { "type": "image", "asset": "fig1" },
            { "type": "highlight", "cue": 1, "region": [0.1, 0.2, 0.3, 0.25], "label": "Kemik defekti" }
          ] },
        { "id": "h1-q1",
          "question": { "type": "single", "goal": "H1.1", "prompt": "...",
            "options": [ { "text": "...", "correct": true }, { "text": "...", "why": "Neden yanlış" } ],
            "explanation": "Cevaptan sonra seslendirilir.", "sourceRef": "s. 4" } }
      ] }
  ]
}
```

### Zamanlama

`say` içindeki `{1}`, `{2}` ... işaretleri metni parçalara böler. Anlatıcı bir işarete geldiğinde
aynı numaralı `cue` taşıyan komutlar çalışır. `cue` verilmeyen komutlar adım başında çalışır.
Bir bölüm içindeki komutlar birikir; yeni bölüm tahtayı temizler. Bölüm içinde temizlemek için `clear`.

### Tahta komutları

| Komut | Alanlar | Bölge |
|---|---|---|
| `title` | `text`, `subtitle?` | başlık |
| `bullets` | `items[]`, `title?` | notlar |
| `point` | `text` (son listeye madde ekler) | notlar |
| `text` | `text`, `style?`: `note` · `key` · `warn` | notlar |
| `term` | `term`, `definition` | notlar |
| `image` | `asset`, `caption?` | görsel |
| `highlight` | `region` [x, y, genişlik, yükseklik] (0–1, görsele oranla), `label?`, `shape?`: `rect` · `ellipse`, `color?`: `accent` · `ok` · `warn`, `id?` | görsel üstü |
| `unhighlight` | `id?` (yoksa hepsi) | görsel üstü |
| `zoom` / `unzoom` | `region` | görsel |
| `table` | `headers[]`, `rows[][]`, `title?`, `caption?` | görsel |
| `flow` | `nodes[]`, `direction?`: `row` · `column`, `title?` | görsel |
| `compare` | `columns[]` = `{title, items[], color?}`, `title?` | görsel |
| `draw` | `shapes[]`, `viewBox?` (vars. `0 0 160 90`), `title?` | görsel |
| `clear` | | hepsi |

`draw` şekilleri: `line`/`arrow` (`x1,y1,x2,y2`), `rect` (`x,y,w,h,r?`), `ellipse` (`cx,cy,rx,ry`),
`path` (`d`), `text` (`x,y,text,size?,anchor?`). Ortak: `color` (`chalk` · `accent` · `ok` · `warn` · `info` · `muted`),
`dashed`, `fill`. Çizgiler sırayla "elle çiziliyormuş" gibi belirir.

Metinlerde `**kalın**` ve `_italik_` kullanılabilir. HTML yorumlanmaz.

### Soru türleri

`single` (tek doğru), `multiple` (bir ya da daha çok doğru, "Kontrol et" ile), `truefalse` (`answer: true|false`).
Her soru bir alt hedefe (`goal`) bağlanır. İsteğe bağlı `review`: yanlış cevapta dinletilecek adımın kimliği
(verilmezse `sourceRef`e göre seçilir). Cevaplar aralıklı tekrar takvimine (`progress.srs`) de işlenir. Hedefler tablosu bu bağlantıdan hesaplanır:
alt hedefin tüm soruları doğruysa "Ulaşıldı", yanlış varsa "Tekrar edin" ve o bölümü yeniden dinleme düğmesi.

## Canlı soru-cevap (`js/qa/`)

```
soru ─► bilgi.js: KnowledgeRetriever ─► [K1..K6] parçalar ─► qa.js: istem ─► sağlayıcı.chat() ─► metin + tahta komutları
          ├ LessonRetriever (ders anlatımı ve soruları, BM25)                      │
          └ IndexRetriever  (kaynak-dizini.json; sözlük + sayfa köprüsü)           └► cleanBoard(): doğrulama, lisans notu
```

- **Kipler:** `none` (yalnız arama, varsayılan), `local` (Ollama / OpenAI uyumlu), `api` (Anthropic). Ayarlar `localStorage`
  `at:qa:ayar`; anahtar `at:qa:key:<sağlayıcı>`. `config.js` → `qa.defaults` kurum varsayılanını verebilir (anahtar hariç).
- **Sağlayıcı arayüzü:** `AT.qa.registerProvider(id, { label, kind, needsKey, defaultModel, defaultBaseURL, tools, chat })`.
  `chat({ system, messages, tools, onText, signal, model, baseURL, key })` → `{ text, toolInput, usage: { input, output, cacheRead, cacheWrite }, model, stop }`.
  Araçlar sağlayıcıdan bağımsız JSON Schema olarak verilir; her sağlayıcı kendi biçimine çevirir.
- **İstem:** sistem kısmı ders boyunca sabittir (kurallar, hedefler, görsel listesi ve lisansları) ve Anthropic'te
  `cache_control` ile önbelleğe alınır. Kullanıcı kısmı değişir: o anki bölüm, son anlatım, parçalar, soru. Son 4 soru-cevap düz metin olarak eklenir.
- **Tahta aracı `tahtaya_yaz`:** `{ komutlar: [...] }`, ders şemasındaki komutların alt kümesi (title, bullets, text, term, table,
  flow, compare, image, highlight, draw). `cleanBoard` bilinmeyen alanları atar, uzunlukları sınırlar, yalnız dersin `assets`
  görsellerine izin verir (`open: false` olan görsel doğrudan gösterilmez) ve `draw` altına kaynak/uyarlama notu ekler.
  Araç desteklemeyen modelde yanıt `{"cevap", "tahta"}` JSON'u olarak istenir (`parseJsonAnswer`).
- **Anthropic:** `vendor/anthropic-sdk.js` ilk soruda yüklenir; akışlı istek, `effort: low`, sunucu tarafı yedek model
  (`server-side-fallback-2026-07-01`, Haiku hariç), `refusal` ve hata türleri Türkçe iletilere çevrilir.
- **Maliyet:** `qa.js` → `PRICES` (1M token başına $); önbellek okuma ve yazma ayrı hesaplanır.
- **Kaynak dizini biçimi:** `{ surum, kaynaklar: [{ id, baslik, kisa, atif, lisans, acik }], sozluk: { tr: en }, parcalar: [{ k, s, t }] }`.
  Ders klasöründe `kaynak-dizini.json` (+ `.js` kopyası). Ders dosyasında `knowledge.index` ile başka ad verilebilir.

## Canlı tahta (`canli.html`, `js/canli.js`, `tools/tahta-mcp.py`)

Öğretim üyesi modu. Claude masaüstü uygulaması, stdio üzerinden konuşan küçük bir MCP sunucusunu
(`tools/tahta-mcp.py`, yalnız Python kitaplığı) başlatır. Araçlar ders dosyalarını doğrudan diskten
okur (`dersler`, `ders_oku`, `gorsel_bak`); tahta komutlarını `tools/sunucu.py`'nin `/api/canli/`
kuyruğuna gönderir (`tahta`, `soru_sor`, `durdur`, `tahta_durumu`).

`canli.html` kuyruğu uzun yoklamayla (`/api/canli/al`) alır, komutları sırayla uygular ve her komutun
sonucunu (`/api/canli/bitti`) bildirir; anlatımlı adımlar ses bitince, sorular cevap gelince biter.
`dur` komutu sırayı beklemeden uygulanır. Araç çağrısı en çok ~40 sn bekler; daha uzun anlatımlar
`tahta_durumu(no)` ile beklenir. Tahta komutları ders dosyasındakilerle aynıdır (`js/board.js`).

Duraklat: sayfadaki ⏸ tuşu (P / Boşluk) hiçbir komutu iptal etmez; `ses.audio` duraklatılır, cümle ve
adım döngüleri `durak.bekle()`'de bekler, devamda ses aynı noktadan sürer. Sayfa durumu
`/api/canli/duraklat` ile bildirir; sunucu bu sırada bekleme süresi dolan sonuçları `sürüyor` yerine
`duraklatildi` (not alanıyla) döndürür, `durum` yanıtında da `duraklatildi` alanı vardır. `dur`/Esc ve
söz alma duraklamayı kaldırır; sayfa yeniden yüklenince (`merhaba`) sıfırlanır.

Ses: `/api/canli/ses` cümle cümle WAV üretir (`ses/ses-ayari.json`: varsayılan Pocket TTS Türkçe kadın 3,
`tools/pocket-isci.py` ayrı ortamda; hazır değilse Piper dfki; telaffuz sözlüğü `tools/ses-uret.py` ile aynı);
sayfa bir sonraki cümleyi önceden ister. Sunucu sesi yoksa Web Speech (tr-TR).
Sunucu yalnız 127.0.0.1'i dinler ve başka kökenden (Origin) gelen istekleri reddeder.
