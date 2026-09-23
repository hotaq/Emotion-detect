# เห็นใจ · HENJAI — เวอร์ชัน Vercel

Gemini อย่างเดียว ไม่มีโมเดลในเครื่อง — เพราะ Vercel เป็น serverless

## deploy
```bash
npm i -g vercel        # ครั้งแรกเท่านั้น
cd web
vercel                 # deploy preview
vercel --prod          # ขึ้นจริง
```
แล้วตั้ง env ที่ Vercel dashboard → Settings → Environment Variables:

| key | ค่า |
|---|---|
| `GEMINI_API_KEY` | คีย์ของคุณ |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` (ไม่ตั้งก็ใช้ตัวนี้) |

หรือสั่งจาก CLI: `vercel env add GEMINI_API_KEY`

`?dev=1` ต่อท้าย URL = โชว์เวลา/โหมด/ค่าความเปลี่ยนแปลง + ภาพกล้องมุมล่างขวา

## ทำไมต้องกลับด้านสถาปัตยกรรม

| | เครื่องตัวเอง (`poc/`) | Vercel (`web/`) |
|---|---|---|
| กล้อง | OpenCV ฝั่งเซิร์ฟเวอร์ | **getUserMedia ในเบราว์เซอร์** |
| วิดีโอ | MJPEG stream | ไม่ต้องส่ง อยู่ในเครื่องผู้ใช้อยู่แล้ว |
| วัดภาพเปลี่ยน | numpy | **canvas 64x36 ใน JS** |
| ความจำ | ตัวแปรใน Session | **ส่ง recent[] + summary มากับทุก request** |
| กันพูดซ้ำ | difflib | เทียบคำซ้ำใน JS |
| เสียงไทย | edge-tts + afplay | **speechSynthesis ของเบราว์เซอร์** |
| สายเร็ว FER+Pose | 110 ms | **ไม่มี** — torch+ultralytics ใหญ่เกินลิมิต Vercel |

serverless ไม่มี process ค้าง จึงเก็บ state ฝั่งเซิร์ฟเวอร์ไม่ได้ — ความจำทั้งหมดย้ายไปอยู่ฝั่งเบราว์เซอร์แล้วส่งกลับมาทุกครั้ง

## ที่หายไปเทียบกับ poc/
- **สายเร็ว 110 ms** (FER + YOLO11-Pose) — เหลือแค่ Gemini ~2.9 วิ
- ทำงานตอนเน็ตหลุดไม่ได้
- YOLO overlay หน้า /dev

## ที่ได้เพิ่ม
- เปิดจากมือถือได้ทันที ใช้กล้องหลัง (`facingMode: environment`)
- API key อยู่ฝั่งเซิร์ฟเวอร์ ไม่หลุดไปเบราว์เซอร์
- ไม่ต้องลง python/torch/opencv อะไรเลย

## ข้อควรระวัง
- **ต้องเป็น https** ไม่งั้น `getUserMedia` ไม่ทำงาน (Vercel ให้ https อยู่แล้ว · localhost ก็ได้)
- เสียงไทยขึ้นกับเครื่องผู้ใช้ — iOS/macOS มี Kanya, Android ส่วนใหญ่มี, Windows อาจไม่มี
- ต้องแตะหน้าจอก่อนเสียงถึงจะออก (นโยบาย autoplay ของเบราว์เซอร์)
- โควตา free tier 500 ครั้ง/วัน · ตั้งไว้ถามทุก 5 วิ = ใช้ได้ ~40 นาที/วัน
