# POC v0 — Emotion & Context-Aware Vision

## run
```bash
cd poc
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # then put GEMINI_API_KEY
streamlit run app.py
```

## flow
`upload/cam -> YOLO11n overlay (โชว์) + Gemini Flash (emotion/body/env -> narrative_th) -> edge-tts Thai`

- YOLO fail-soft: ไม่มีโมเดลก็รันต่อได้
- prompt อยู่ใน `SYSTEM_PROMPT` บนสุดของ `app.py`
- ถ้าจะทำตาม doc เต็ม: แยก MediaPipe + Emotion classifier + YOLO-Pose ทีหลัง ตอนนี้ Gemini เหมาไปก่อน
