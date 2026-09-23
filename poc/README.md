# Emotion & Context-Aware AI Vision — POC

จอผู้ใช้จริงตามเอกสารแนวคิด (น.11): ดำล้วน ปุ่มเดียวเต็มจอ waveform ตอนพูด

## รัน
```bash
/opt/anaconda3/bin/python -m pip install -r requirements.txt
cp .env.example .env      # ใส่ GEMINI_API_KEY
/opt/anaconda3/bin/python server.py
```
- `http://127.0.0.1:8000/` — จอผู้ใช้จริง
- `http://127.0.0.1:8000/dev` — แดชบอร์ดเดโม (วิดีโอ + YOLO + JSON + ความจำ)

## สองความเร็ว
```
สายเร็ว  (ในเครื่อง ~110 ms, ไม่ต้องใช้เน็ต)   YOLO11-Pose + FER -> ประโยคสั้น -> say -v Kanya
สายช้า   (Gemini ทุก 5 วิ)                      คำบรรยายยาว + ความจำ session -> gTTS
```
วัดจริง 12 ก.ย. 2569 บน MPS · ชุดทดสอบ 24 ภาพ

| | เวลา/ภาพ | อ่านอารมณ์ถูก |
|---|---|---|
| Gemini (cloud) | 2,243 ms | 4/6 |
| FER + ตัดหัวด้วย YOLO | **72 ms** | 4/6 |
| FER + haar cascade | 65 ms | 2/6 |
| YOLO11-Pose | **42 ms** | — |

ตัวหาหน้าสำคัญกว่าตัวโมเดล — เปลี่ยนจาก haar เป็น YOLO ทำให้ 2/6 → 4/6
⚠️ n=6 และเฉลยมาจากคำค้น ไม่ใช่คน label — ยังสรุปว่า "เสมอ Gemini" ไม่ได้

## ไฟล์
| ไฟล์ | ทำอะไร |
|---|---|
| `server.py` | Flask routes |
| `core.py` | กล้อง + Gemini + TTS + `Session` (2 thread: อ่านกล้อง / ยิง Gemini) |
| `fast.py` | สายเร็ว — YOLO11-Pose + FER + ทำประโยคไทย |
| `memory.py` | ความจำ session — 5 ประโยคล่าสุด + สรุปสะสม cap 600 ตัว |
| `templates/` | `index.html` จอผู้ใช้, `dev.html` แดชบอร์ด |

`python test_memory.py` — เช็คว่ากันพูดซ้ำได้จริง

## prompt ปรับตามภาพ (adaptive)
วัดความต่างของเฟรมในเครื่องก่อน (grayscale 64x36, absdiff) แล้วค่อยเลือกว่าจะถามอะไร

| ภาพเปลี่ยน | โหมด | ทำอะไร |
|---|---|---|
| < 0.02 | — | **ไม่ยิง Gemini เลย** ภาพนิ่งก็ไม่ต้องพูด ประหยัดโควตา |
| < 0.18 | `delta` | บอกเฉพาะสิ่งที่ต่างจากที่เพิ่งพูด ไม่มีอะไรใหม่ = เงียบ |
| < 0.45 | `scene` | เปลี่ยนฉาก บรรยายที่ใหม่ทั้งหมด |
| ≥ 0.45 | `alert` | เปลี่ยนกะทันหัน ขึ้นต้นด้วยสิ่งที่ต้องระวัง |

เกณฑ์ปรับได้ที่ `/dev` (กล้อง/แสงต่างกันค่าไม่เท่ากัน)

## กับดักที่เจอมาแล้ว
- **กล้อง**: OpenCV เรียง index คนละลำดับกับ macOS (เครื่องนี้ 0 = iPhone, 1 = MacBook) ดูภาพที่ `/dev` แล้วเลือกเอา
- **model**: `gemini-3.1-flash-lite` ~2s ใช้ตัวนี้ · `3.5-flash-lite` ~27s เพราะเปิด thinking เอง realtime ไม่ทัน · `gemini-2.0/1.5` ตายแล้ว
- **เสียง**: สายช้าใช้ **gTTS ของ Google** 0.31 วิ + `afplay` · เน็ตล่มถอยไปใช้ `say -v Kanya` ของ macOS
  วัดเทียบแล้ว: gTTS 0.31s · edge-tts 0.75s · macOS say 0.46s · Gemini TTS 6.0s — **ไม่ใช้ edge-tts ของ Microsoft แล้ว** · สายเร็วใช้ `say -v Kanya` ของ macOS (เรียก 3 ms ออฟไลน์)
- **MPS tensor**: ผลจาก ultralytics อยู่บน GPU ต้อง `.cpu()` ก่อนส่งให้ numpy
