# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

KlinikKoç is an open-source clinical-reasoning coach for dental students. It teaches a short lesson on a "blackboard" (`tahta`) with Turkish narration, then runs branching clinical cases and keeps a report card (`karne`) that stays on the student's own device. Everything is written in Turkish: the UI, docs, commit messages and identifiers (`ders` = lesson, `vaka` = case, `karne` = report card, `kayit` = record, `sihirbaz` = wizard, `egitmen` = instructor persona, `ogrenci`/`ogretmen` = student/teacher). Keep new names, messages and docs in Turkish.

There is no build step and no package manager. The frontend is plain HTML and vanilla JS. The backend is Python using only the standard library, except for optional extras (pypdf/pypdfium2, Piper/Pocket TTS, onnxruntime) that degrade gracefully when they're missing. Node 18+ is used only by `tools/paketle.mjs`. `vendor/` holds prebuilt third-party bundles, which are regenerated with `tools/vendor-hazirla.sh`.

## Commands

```sh
python3 tools/sunucu.py --sayfa ana.html      # run the app (local server on 127.0.0.1:8810); BASLAT-* scripts do this
python3 -m unittest discover -s tools/testler -v                       # all tests (~20 s, no network)
python3 -m unittest tools/testler/test_temel.py                        # one file (run from repo root)
python3 -m unittest discover -s tools/testler -k test_surum_ayni       # one test by name
python3 tools/yayin_denetimi.py               # publish check: blocks private content, student records, unlicensed images
node tools/paketle.mjs                        # validate lessons/, regenerate katalog.json/.js + onbellek-listesi.json
node tools/paketle.mjs --ornek                # validate ornek-dersler/ and regenerate their ders.js copies
python3 tools/vaka_denetle.py                 # validate case cards against schema/vaka.schema.json
python3 tools/tahta-mcp.py --kur | --dene     # register the MCP server with the Claude desktop app / smoke-test it
python3 tools/surum.py --paketler <dir>       # build the student and teacher release zips
```

CI (`.github/workflows/denetim.yml`) runs the publish check, both `paketle.mjs` runs, `vaka_denetle.py` and the tests. It fails if `git diff` shows that `paketle.mjs` changed `ornek-dersler/`, `lessons/katalog.*` or `onbellek-listesi.json`. After you edit a lesson JSON, run the matching `paketle.mjs` and commit what it regenerates.

Tests set `KLINIK_KOC_ANLAM_KURMA=1` so that semantic search doesn't try to install itself. Network access is replaced with fake objects (`SahteAg`, `SahteClaude`, `SahteModel`). Tests that need pypdf are skipped when it isn't installed. `tools/testler/ornek_ders.py` temporarily copies the sample lesson into `lessons/` and removes it afterwards.

## Version bumps

The version lives in the `SURUM` file. `config.js` (`version: '…'`) and `sw.js` (`SW_SURUM`) must match it, and `test_surum_ayni` checks `config.js`. `tools/tahta-mcp.py` reads `SURUM` at runtime. Commit messages start with the version and a Turkish summary (e.g. `4.1.1: …`).

## Architecture

Read `belgeler/mimari.md` for the full reference: the lesson JSON format, board commands, the `{n}` cue timing, the QA provider interface and the live-board protocol. The big picture:

**Two ways to use it.**
1. **Player** (`index.html`, `js/core.js` → `js/player.js` → `js/board.js` + `js/speech.js`, with the UI in `js/app.js`). It runs offline from `file://` or through the server, and plays the prepared lesson steps from `ders.json`. This is why `paketle.mjs` writes `.js` copies of the JSON files (`ders.js`, `katalog.js`, `kaynak-dizini.js`): `file://` can't fetch JSON. The player knows only the schema (`schema/ders.schema.json`), never specific lessons.
2. **Live instructor** (`canli.html`, `js/canli.js`). The Claude desktop app starts `tools/tahta-mcp.py`, an stdio MCP server. Tool calls read lessons and records from disk, and board and speech commands go into the `/api/canli/` queue in `tools/sunucu.py`. `canli.html` long-polls that queue, renders each command, speaks it, and reports completion. Tool descriptions and the system instruction text live in `tools/mcp_araclar.py`; the handlers live in `ISLEYICILER` in `tahta-mcp.py`. If you rename a tool, update both files. Teacher-only tools (`OGRETMEN_ARACLARI`) are hidden in the student profile. The teaching persona and its rules come from `egitmenler/ortak.md` and `inci.md`/`mercan.md`, which `egitmen_hazirla` returns.

**The local server** (`tools/sunucu.py`) serves the repo and hosts several APIs: `/api/canli/` (live board), `/api/makale/` (article finder and lesson-package install, `makaleler.html`), `/api/sihirbaz/` (teacher wizard, `sihirbaz.html` + `tools/sihirbaz.py`), Duyu speech-to-text, and sentence-by-sentence TTS. It listens on 127.0.0.1 only and rejects cross-origin requests. Keep it that way.

**Board** (`js/board.js`, `js/board-etkilesim.js`, `js/anatomi*.js`): the same command set is used by lesson files, the QA `tahtaya_yaz` tool and the live board. Anatomy templates for `draw` live in `js/anatomi.js` (and the `-bolge`/`-kontur` variants). `tools/sablonlar.json` and `sablon-galerisi.html` list them.

**Search and knowledge base** (`tools/bilgi_bankasi.py`): an SQLite hybrid of BM25 and an optional local semantic model, with Turkish-to-English term mapping from `ses/terimler-tr-en.json`. If you change the chunking rules, bump `SURUM` in `bilgi_bankasi.py`; that forces a reindex. The browser QA path (`js/qa/`) has its own retriever plus pluggable providers (Anthropic, OpenAI-compatible, Ollama).

**Data locations.** Program files and user data are kept apart so that updates never touch user data. `tools/veri_yeri.py` resolves the persistent data root (`~/Library/Application Support/KlinikKoc`, `%APPDATA%\KlinikKoc`), which can be overridden with `KLINIK_KOC_VERI`/`KLINIK_KOC_KAYIT`, and an optional shared cloud folder (`ortak_klasor.py`). Student records are written atomically with 5 rotating backups (`kayit_deposu.py`). The updater (`surum.py`) replaces program files but never touches `lessons/`, records, articles or private content.

**Lessons ship separately.** The app comes with no lessons. `lessons/*/` is gitignored, and lessons are installed from teacher-made `.zip` packages (`tools/ders_paketi.py`). The repo holds only the empty catalog and the CC BY sample lesson in `ornek-dersler/peri-implantitis-cerrahi/`, which the tests use. Packages contain only article citations and DOIs; `makale_bulucu.py` downloads the PDFs on the student's machine.

**Student vs teacher build.** There is one codebase. The student build drops `OGRETMEN_DOSYALARI` (listed in `tools/surum.py`) and contains a `SURUM-TURU` file. The `*-ogrenci` branches are generated and CI ignores them.

## Content rules

- Never commit patient data or copyrighted material. `ozel/`, `lessons/ozel-*` and `lessons/*/vakalar/ozel-*` are gitignored and checked by `yayin_denetimi.py`. Every image needs a `credit` that gives its source and license (CC BY or CC0 only).
- Code is MIT and content is CC BY 4.0. Clinical content is not marked "onaylandı" (approved) until a teacher has approved it.

## Behavioral guidelines

Source: [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills). These guidelines aim to reduce common LLM coding mistakes. They bias toward caution over speed; for trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
