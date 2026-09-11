# Handoff — Emotion & Context-Aware AI Vision Assistant (POC v0)

Team Rushhour, CEDT Chula. Concept doc: `/Users/chinnaphat/Downloads/CONCEPT IDEA.docx.pdf` (11 pages).

## 1. What this is
AI narrator for severely blind users (level 3–5). Not just "what is in the image" but "what does it feel like": face emotion + body language + place context → one warm Thai sentence → spoken audio.

Full arch (per doc):
```
[camera] → Emotion (MediaPipe Face + Gemini + classifier) ─┐
          → Body (YOLO11-Pose) ────────────────────────────┼→ Gemini Flash summarizer → Thai TTS
          → Environment (YOLO11 + Gemini) ─────────────────┘
```
POC shortcut: YOLO11n overlay for show + Gemini Flash does all 3 reasonings in one prompt.

## 2. Repo map
```
pigan/
  handoff.md          ← this file
  poc/
    app.py              ← Streamlit app (all logic)
    requirements.txt    ← streamlit, pillow, dotenv, google-generativeai, google-genai, edge-tts, gtts, ultralytics, opencv, numpy
    README.md           ← quick run guide
    .env.example        ← GEMINI_API_KEY=...
```
Key symbols in `app.py`: `SYSTEM_PROMPT`, `analyze_with_gemini()`, `yolo_overlay()`, `tts_thai()`, live-loop block at bottom.

## 3. Run
```bash
cd /Users/chinnaphat/Desktop/cedt/pigan/poc
/opt/anaconda3/bin/python -m pip install -r requirements.txt
cp .env.example .env  # put GEMINI_API_KEY, or paste in sidebar
/opt/anaconda3/bin/python -m streamlit run app.py
```
Must install with the SAME python that runs streamlit (`/opt/anaconda3/bin/python`). After install, restart streamlit.

## 4. How to demo
1. Sidebar: paste GEMINI_API_KEY, pick model (see §5).
2. Top radio: Upload / Webcam (browser) / USB cam (switchable).
   - USB: selectbox camera index + `🔄 สลับกล้อง` + `📸 ถ่ายภาพ` + `กระจก` checkbox.
   - Upload: file uploader OR paste local path (e.g. `/var/.../*.png`).
3. `↔️ สลับซ้าย-ขวา` flips current image (persists until pressed again).
4. `🔍 Analyze` → detection view + Result JSON (`emotion/body_language/environment/narrative_th`) + Thai narrative + audio player + mp3 download.
5. `🔴 Live mode` (bottom, USB mode only): checkbox + interval 3/5/10s + "speak only on change". One capture+analyze per rerun, `sleep → rerun`. Uncheck to stop.

## 5. Models & quota (as of 2026-09-11)
- `gemini-2.0-flash` / `1.5-flash` are DEAD (404). Do not use.
- Working: `gemini-2.5-flash` (20 RPD), `gemini-3.6-flash` (20 RPD), `gemini-3-flash` (20 RPD), `gemini-3.5-flash-lite` (500 RPD), `gemini-3.1-flash-lite` (500 RPD).
- One-shot: any. Live demo: use a *-lite (500/day) or quota dies in minutes (5s interval ≈ 12 calls/min).

## 6. TTS — important
- `tts_thai()` tries `edge-tts` (voice `th-TH-PremwadeeNeural`) then falls back to `gTTS(lang=th)`.
- Generation works (verified `/tmp/poc_th.mp3`, `/tmp/poc_live_*.mp3` 30–45KB).
- Browsers BLOCK autoplay: user MUST press ▶️ on the player or use `⬇️ โหลด mp3`. This is not a bug.
- If "No module named edge_tts": wrong env — reinstall with `/opt/anaconda3/bin/python -m pip install edge-tts gtts`.

## 7. Issues hit & fixed
| Symptom | Cause | Fix |
|---|---|---|
| `No module named google.generativeai` | deps not installed | install requirements; app now supports both `google-genai` (new) and `google-generativeai` (old) |
| `404 gemini-2.0-flash no longer available` | model retired | model list updated to 2.5/3.x |
| `use_container_width` deprecation warnings | Streamlit API change | replaced with `width='stretch'` |
| Camera switch confusion | `st.camera_input` can't switch devices | added USB/OpenCV mode with index select + cycle button; plus post-capture `↔️` flip |
| Clipboard PNG "cannot use" | no path input | added local-path textbox; file itself was valid PNG |
| "No sound" | autoplay blocked / wrong env | proven mp3 generates; added size caption + download button + gTTS fallback |

## 8. What's NOT done (next)
1. True realtime (<500ms): current live is 3–10s polling. Needs local-only fast loop (YOLO + on-device FER) + Gemini only every N sec.
2. Real modules per doc: MediaPipe Face Landmarker + trained emotion classifier (AffectNet/RAF-DB/FER-2013), YOLO11-Pose for body, hazard recall eval.
3. Eval harness: Context Accuracy, Hallucination Rate, Time-to-Alert on 20–30 collected images.
4. Mobile packaging / Thai TTS streaming (currently file-based).

## 9. Prompt contract
`SYSTEM_PROMPT` forces JSON-only: `{emotion{label,confidence,detail_th}, body_language{detail_th}, environment{scene_th,objects_th,safety_th}, narrative_th}`. `analyze_with_gemini` strips code fences, falls back to `{narrative_th: raw_text}` on JSON parse fail.
