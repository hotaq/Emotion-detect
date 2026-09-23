"""กล้อง + Gemini + เสียง — ไม่ผูกกับ UI ตัวไหน."""
import io
import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path

import cv2
from dotenv import load_dotenv
from PIL import Image

from memory import MEM_CAP, is_dup, memo, push

load_dotenv()

GEMINI_TIMEOUT = 25
# วัดจริง 2026-09-11 (ภาพ 768px): 3.1-flash-lite ~2s, 3.5-flash-lite ~27s (มันเปิด thinking เอง)
MODELS = ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-3-flash-preview"]
CAM_CHOICE = Path(__file__).parent / ".cam_choice.json"

SYSTEM_PROMPT = """\
คุณคือผู้ช่วยบรรยายภาพให้คนตาบอดสนิท (ระดับ 3-5)
ดูภาพแล้วตอบ JSON เท่านั้น ห้ามมีข้อความอื่น:
{
  "narrative_th": "ประโยคเดียว ไม่เกิน 20 คำ — ต้องเป็นคีย์แรกเสมอ ห้ามสลับลำดับ",
  "reading": {"is_document": false, "text": ""},
  "emotion": {"label": "...", "confidence": "high|medium|low", "detail_th": "..."},
  "body_language": {"detail_th": "..."},
  "environment": {"scene_th": "...", "objects_th": ["..."], "safety_th": "..."},
  "memory_th": "สรุปสะสมของ session นี้ ไม่เกิน 3 บรรทัด — เอาของเดิมที่ให้ไปมาอัปเดต ไม่ใช่เขียนใหม่ทั้งหมด"
}

emotion.label ต้องเลือกจากรายการนี้เท่านั้น (ภาษาอังกฤษ ห้ามคิดคำเอง):
happy, sad, angry, fear, surprised, disgust, neutral, no_person

กฎสำคัญที่สุด — ความถูกต้องมาก่อนความสุภาพ:
- ถ้าเห็นอารมณ์ลบ ให้บอกตรง ๆ ว่าโกรธ เศร้า ร้องไห้ ไม่พอใจ อึดอัด กลัว
  ห้ามแปลงเป็นเรื่องบวก ห้ามใช้คำว่า "ยิ้มทะเล้น" "สนุกสนาน" กับหน้าที่กำลังโกรธหรือร้องไห้
- ปากเปิดกว้าง + คิ้วขมวด + หน้าย่น มักเป็นโกรธหรือร้องไห้ ไม่ใช่หัวเราะ ดูที่ตาและคิ้วประกอบเสมอ
- ผู้ใช้ตาบอดต้องใช้ข้อมูลนี้ตัดสินใจว่าจะพูดต่อ จะหยุด หรือจะปลอบ
  บอกผิดว่าเขาอารมณ์ดีทั้งที่กำลังโกรธ อันตรายกว่าการบอกว่าไม่แน่ใจ
- ไม่ชัดให้ตอบ neutral แล้วตั้ง confidence = "low" อย่าเดาไปทางบวก
- ไม่มีคนในภาพ ให้ label = "no_person" แล้วเน้นสถานที่กับสิ่งกีดขวาง/อันตราย

เมื่อผู้ใช้ยกเอกสารมาจ่อกล้อง — ต้องเปลี่ยนพฤติกรรมทันที:
ถ้ามีเอกสาร หนังสือ ป้าย เมนู ฉลาก หรือหน้าจอ ที่กินพื้นที่เกินครึ่งภาพและอ่านตัวหนังสือออก
แปลว่าเขาตั้งใจยกมันมาให้คุณอ่าน ไม่ได้อยากรู้ว่ามีอะไรวางอยู่ตรงไหน
- reading.is_document = true
- reading.text = ถอดข้อความทั้งหมดตามลำดับบนลงล่าง ตรงตัวทุกคำ
  ห้ามสรุป ห้ามข้าม ห้ามแปล ถ้าต้นฉบับเป็นอังกฤษให้คงอังกฤษไว้
  ข้ามพวกโลโก้ที่ไม่มีข้อความ และข้ามสิ่งที่อยู่นอกเอกสาร เช่น โต๊ะหรือคีย์บอร์ดที่เป็นฉากหลัง
- narrative_th = บอกสั้น ๆ ว่ากำลังจะอ่านอะไร เช่น "ปกโบรชัวร์มิตซูบิชิ เดี๋ยวอ่านให้ฟังนะ"
  ห้ามเอาเนื้อหาในเอกสารมาใส่ narrative_th เพราะมันอยู่ใน reading.text อยู่แล้ว
ถ้าไม่เข้าเงื่อนไขนี้ ให้ reading.is_document = false และ reading.text = "" เสมอ

มุมมองของภาพ — เข้าใจผิดข้อนี้แล้วพังทั้งหมด:
ภาพนี้คือสิ่งที่ "ดวงตาของผู้ใช้" มองเห็น กล้องอยู่ตรงตำแหน่งตาเขา
ทุกคนทุกสิ่งในภาพจึงอยู่รอบตัวเขา ไม่ใช่ฉากที่เขานั่งดูอยู่ห่าง ๆ
- พูดกับเขาโดยตรง ใช้คำว่า "คุณ" เสมอ
- บอกความสัมพันธ์กับตัวเขา ไม่ใช่แค่รายงานว่าเกิดอะไรขึ้น
  ถูก: เขานั่งยิ้มให้คุณ            ผิด: มีคนนั่งยิ้มอยู่
  ถูก: เธอหันมาทางคุณแล้วโบกมือ     ผิด: ผู้หญิงกำลังโบกมือ
  ถูก: มีเก้าอี้ขวางทางซ้ายของคุณ   ผิด: มีเก้าอี้อยู่ด้านซ้ายของภาพ
- บอกทิศและระยะเทียบกับตัวเขาเสมอ: ตรงหน้าคุณ ทางซ้ายของคุณ ห่างไปสองสามก้าว
- ห้ามพูดเหมือนคนยืนดูรูปอยู่ข้างนอก ห้ามใช้ "ในภาพ" "ด้านซ้ายของภาพ" "ฉากนี้"
- แต่ห้ามแต่งความสัมพันธ์ที่ไม่มีจริง ถ้าเขาไม่ได้หันมาหาคุณก็บอกตามจริง
  เช่น เขาหันข้างให้คุณ · เขากำลังคุยกับคนอื่นอยู่ ไม่ได้สนใจคุณ

narrative_th — กฎเข้มงวด ผู้ใช้ต้องฟังจบเร็วเพื่อเดินต่อได้:
- ประโยคเดียว ไม่เกิน 20 คำ พูดจบใน 5 วินาที ยาวกว่านี้คือผิด
- มีอันตรายหรือสิ่งกีดขวาง -> ขึ้นต้นด้วยคำว่า "ระวัง" ทันที แล้วบอกว่าอะไร อยู่ทางไหน
- ไม่มีอันตราย -> บอกคนกับอารมณ์ก่อน แล้วค่อยสถานที่สั้น ๆ
- ห้ามเกริ่น ห้ามใช้คำว่า "ภาพนี้" "บรรยากาศ" "ท่ามกลาง" "อย่างเห็นได้ชัด" "ดูเหมือนว่า"
- ห้ามบรรยายสีเสื้อ ทรงผม พื้นหลัง เว้นแต่ช่วยให้ระบุตัวคนได้
- ยาวเกินไป (ห้ามเขียนแบบนี้): ภาพนี้แสดงบรรยากาศภายในห้องประชุมที่ดูเป็นทางการ โดยมีชายคนหนึ่ง...
- สั้นกำลังดี: ระวัง มีเก้าอี้ขวางทางซ้าย
- สั้นกำลังดี: ชายตรงหน้ากำลังโกรธ คิ้วขมวดแน่น"""

# ภาพนิ่ง = ไม่ต้องพูด, ขยับนิด = บอกเฉพาะที่เปลี่ยน, เปลี่ยนฉาก = บรรยายใหม่หมด
MODE_PROMPT = {
    "first": "\nนี่คือครั้งแรก บรรยายภาพรวมให้ครบ: คนตรงหน้า อารมณ์ ท่าทาง สถานที่ และสิ่งกีดขวาง",
    "delta": "\nฉากเดิม เปลี่ยนแค่เล็กน้อย พูดเฉพาะสิ่งที่ต่างไปจากที่คุณเพิ่งบอก เช่น คนขยับ "
             "สีหน้าเปลี่ยน มีของใหม่โผล่มา ห้ามทวนฉากเดิม ถ้าไม่มีอะไรใหม่จริง ๆ "
             'ให้ narrative_th = "" (ค่าว่าง) ไปเลย อย่าฝืนหาเรื่องพูด',
    "scene": "\nฉากเปลี่ยนไปแล้ว บรรยายที่ใหม่ทั้งหมด เน้นสถานที่ คนที่อยู่ตรงหน้า และสิ่งที่ต้องระวัง",
    "alert": "\nภาพเปลี่ยนกะทันหัน อาจมีคนหรือสิ่งของเคลื่อนเข้ามาใกล้ "
             "บอกสั้นที่สุดและขึ้นต้นด้วยสิ่งที่ต้องระวังก่อน",
}


# ==================== กล้อง ====================
def list_cams(max_n: int = 6) -> list[int]:
    """ไล่ index ต่อเนื่อง เจอตัวแรกที่เปิดไม่ได้ = จบ (กัน 'out device of bound').

    ลำดับของ OpenCV ไม่ตรงกับ system_profiler/ffmpeg (เครื่องนี้ 0=iPhone, 1=MacBook)
    """
    found, devnull, saved = [], os.open(os.devnull, os.O_WRONLY), os.dup(2)
    os.dup2(devnull, 2)                       # กลบ warning ของ OpenCV ตอน probe
    try:
        for i in range(max_n):
            ok = False
            cap = cv2.VideoCapture(i, cv2.CAP_AVFOUNDATION)
            if cap.isOpened():
                ok, _ = cap.read()
            cap.release()
            if not ok:
                break
            found.append(i)
    finally:
        os.dup2(saved, 2); os.close(saved); os.close(devnull)
    return found or [0]


def open_cam(idx: int):
    cap = cv2.VideoCapture(idx, cv2.CAP_AVFOUNDATION)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


def save_cam(idx: int):
    CAM_CHOICE.write_text(json.dumps({"cam_idx": idx}))


def load_cam() -> int:
    try:
        return int(json.loads(CAM_CHOICE.read_text())["cam_idx"])
    except Exception:
        return 0


_yolo = None


def yolo_plot(frame):
    """ตีกรอบวัตถุ — ใช้แค่หน้า /dev ผู้ใช้จริงไม่เห็นภาพอยู่แล้ว."""
    global _yolo
    try:
        if _yolo is None:
            from ultralytics import YOLO
            _yolo = YOLO("yolo11n.pt")
        return _yolo.predict(frame, verbose=False, imgsz=320, conf=0.4)[0].plot()
    except Exception:
        return frame


# ==================== Gemini ====================
# ตัวคูณจากที่วัดจริง: กล้องนิ่ง noise 0.02 -> still .05 / scene .18 / alert .44
NOISE_MULT = (2.5, 9.0, 22.0)


def thresholds(noise: float) -> tuple[float, float, float]:
    return tuple(round(noise * m, 3) for m in NOISE_MULT)


def gray_small(frame):
    return cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (64, 36))


def change_score(a, b) -> float:
    """0 = ภาพเดิมเป๊ะ, 1 = คนละภาพ. ทำในเครื่อง ไม่กิน quota."""
    import numpy as np
    return float(np.abs(a.astype("int16") - b.astype("int16")).mean() / 255.0)


def analyze(img: Image.Image, api_key: str, model: str,
            recent: list[str] | None = None, summary: str = "",
            mode: str = "first") -> dict:
    img = img.convert("RGB")
    if img.width > 768:                       # ย่อก่อนส่ง -> อัปโหลดไวขึ้นมาก
        img = img.resize((768, int(img.height * 768 / img.width)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    from google import genai
    client = genai.Client(api_key=api_key, http_options={"timeout": GEMINI_TIMEOUT * 1000})
    resp = client.models.generate_content(
        model=model,
        contents=[{"role": "user", "parts": [
            {"inline_data": {"mime_type": "image/jpeg", "data": buf.getvalue()}},
            {"text": SYSTEM_PROMPT + MODE_PROMPT.get(mode, "") + memo(recent or [], summary) +
                     "\nAnalyze this image for a blind user. Return JSON only."}]}],
        config={"temperature": 0.4, "max_output_tokens": 512},
    )
    text = re.sub(r"^```(json)?|```$", "", (resp.text or "").strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except Exception:
        return {"narrative_th": text[:500], "_raw": text}


# ==================== เสียง ====================
# วัดจริง 12 ก.ย. 2569: gTTS 0.31s · edge-tts 0.75s · macOS say 0.46s · Gemini TTS 6.0s
# ใช้ gTTS (ของ Google) เป็นหลัก — เร็วสุดและไม่ต้องพึ่งบริการของ Microsoft
def tts_thai(text: str, out_path: str) -> str | None:
    try:
        from gtts import gTTS
        gTTS(text=text, lang="th").save(out_path)
        return out_path
    except Exception:
        pass
    try:                                       # เน็ตล่ม -> ใช้เสียงที่ติดมากับ macOS
        import subprocess
        subprocess.run(["say", "-v", "Kanya", "-o", out_path.replace(".mp3", ".aiff"), text],
                       check=True, timeout=20)
        return out_path.replace(".mp3", ".aiff")
    except Exception:
        return None


def speech_for(r: dict, recent: list[str]) -> tuple[str | None, str | None]:
    """คืน (ข้อความที่จะพูด, narrative ที่จะจำ) — เอกสารอ่านทั้งหมดและไม่เช็คซ้ำ"""
    narrative = (r.get("narrative_th") or "").strip()
    rd = r.get("reading") or {}
    doc = (rd.get("text") or "").strip() if rd.get("is_document") else ""
    if doc:                                    # ผู้ใช้ยกฉลาก/เอกสารมาจ่อ -> อ่านให้จบ ห้ามเงียบ
        return (f"{narrative} {doc}" if narrative else doc), narrative or doc
    if narrative and not is_dup(narrative, recent):
        return narrative, narrative
    return None, narrative


# ==================== session ====================
class Session:
    """2 thread: อ่านกล้องตลอด + ยิง Gemini เป็นช่วง ๆ. Flask แค่มาอ่าน state."""

    def __init__(self):
        self.lock = threading.Lock()
        self._ctl = threading.Lock()          # กันกดปุ่มรัว ๆ จนเปิดกล้องซ้อนกัน
        self._threads = []
        self.frame = None
        self.running = False
        self.cam = load_cam()
        self.mirror = True
        self.every = 0.5           # เท่ากับ web/ — นับจากพูดจบ ไม่ใช่จากถามครั้งก่อน
        # เกณฑ์คิดจาก noise ของกล้องเอง (วัดตอนเริ่ม) — ตั้งค่าตายตัวใช้ไม่ได้
        # iPhone วางนิ่ง noise ~0.02 แต่ถือเดินจะสูงกว่ามาก
        self.auto = True
        self.noise = 0.02
        self.still, self.scene, self.alert = thresholds(self.noise)
        self.model = MODELS[0]
        self.key = os.getenv("GEMINI_API_KEY", "").strip()
        self.proc = None                      # afplay ที่กำลังเล่น
        self.fast_on = True                   # สายเร็ว: ในเครื่องล้วน ไม่ต้องใช้เน็ต
        self.fast_proc = None
        self.reset()

    def reset(self):
        self.narrative = ""
        self.recent, self.summary = [], ""
        self.result = None
        self.fps = self.lat = self.t_last = 0.0
        self.n = self.dup = self.timeouts = 0
        self.busy = False
        self.fast = {}
        self.fast_text = ""
        self.fast_ms = 0.0
        self.fast_n = 0
        self.prev_gray = None
        self.change = 0.0
        self.mode = "first"
        self.skipped_still = 0
        self.stage = "รอเริ่ม"
        self.err = ""

    # ---- lifecycle ----
    def start(self):
        with self._ctl:
            if self.running:
                return
            for t in self._threads:           # รอรอบก่อนปล่อยกล้องจริง ๆ ก่อนเปิดใหม่
                t.join(timeout=GEMINI_TIMEOUT + 2)
            self._threads = [threading.Thread(target=fn, daemon=True)
                             for fn in (self._capture, self._brain, self._fastloop)]
            self.running = True
            self.t_last = 0.0
            for t in self._threads:
                t.start()

    def stop(self):
        with self._ctl:
            self.running = False
            self.stage = "หยุดแล้ว"

    @property
    def speaking(self) -> bool:
        return any(p is not None and p.poll() is None
                   for p in (self.proc, self.fast_proc))

    # ---- threads ----
    def _capture(self):
        cap = open_cam(self.cam)
        if not cap.isOpened():
            self.err = f"เปิดกล้อง {self.cam} ไม่ได้"
            self.running = False
            return
        self.err = ""                         # เปิดได้แล้ว ล้างข้อความ "กำลังต่อใหม่" ที่ค้างจากรอบก่อน
        n, t0 = 0, time.time()
        cal, prev = [], None                  # วัด noise ของกล้องตัวนี้ ~2 วิแรก
        fails = 0
        while self.running:
            ok, fr = cap.read()
            if not ok:
                # iPhone Continuity Camera หลับหรือสัญญาณขาดชั่วคราวเป็นเรื่องปกติ — ต่อใหม่ก่อนยอมแพ้
                fails += 1
                self.err = f"กล้องหลุด กำลังต่อใหม่ ({fails}/20)"
                cap.release()
                time.sleep(.5)
                cap = open_cam(self.cam)
                if cap.isOpened() and cap.read()[0]:
                    self.err = ""
                    fails = 0
                    continue
                if fails >= 20:                   # ~10 วิ แล้วยังไม่กลับมา
                    self.err = "กล้องหลุดนานเกิน — ปลุก iPhone แล้วกดเริ่มใหม่"
                    break
                continue
            if fails or self.err.startswith("กล้องหลุด"):
                self.err = ""                 # กลับมาแล้ว ไม่ว่าจะทางไหน
            fails = 0
            # iPhone Continuity Camera ล็อกจอ = ยังต่ออยู่แต่ส่งเฟรมดำสนิท (ทุกพิกเซล 0) มาเรื่อย ๆ
            # ถ้าไม่ดัก ระบบจะอ่านได้ 30 fps แล้วทำเหมือนปกติทั้งที่ไม่เห็นอะไรเลย
            if n % 15 == 0 and int(fr.max()) == 0:
                self.err = "กล้องส่งภาพดำสนิท — ปลดล็อก iPhone แล้วรอสักครู่ หรือเลือกกล้องอื่นที่ /dev"
            elif self.err.startswith("กล้องส่งภาพดำ"):
                self.err = ""
            if self.mirror:
                fr = cv2.flip(fr, 1)
            with self.lock:
                self.frame = fr
            n += 1
            if len(cal) < 40:
                g = gray_small(fr)
                if prev is not None:
                    cal.append(change_score(prev, g))
                prev = g
                if len(cal) == 40 and self.auto:
                    import statistics
                    self.noise = round(statistics.median(cal), 4)
                    self.still, self.scene, self.alert = thresholds(self.noise)
            if n % 15 == 0:                   # วัด fps ทุก 15 เฟรม พอ
                self.fps, t0 = 15 / (time.time() - t0), time.time()
        cap.release()
        self.running = False

    def _brain(self):
        while self.running:
            time.sleep(0.2)
            if self.speaking:                 # ยังพูดไม่จบ ถามไปก็ได้ผลที่พูดไม่ทันอยู่ดี
                self.t_last = time.time()
                continue
            if time.time() - self.t_last < self.every:
                continue
            with self.lock:
                fr = None if self.frame is None else self.frame.copy()
            if fr is None:
                continue

            g = gray_small(fr)
            self.change = 1.0 if self.prev_gray is None else change_score(self.prev_gray, g)
            if self.n and self.change < self.still:    # ภาพนิ่ง -> ไม่ต้องถาม ไม่เปลืองโควตา
                self.t_last = time.time()
                self.skipped_still += 1
                self.stage = "😴 ภาพนิ่ง ไม่ต้องพูด"
                continue
            self.prev_gray = g
            self.mode = ("first" if not self.n else
                         "alert" if self.change >= self.alert else
                         "scene" if self.change >= self.scene else "delta")

            self.t_last, self.busy, self.stage = time.time(), True, "📤 ส่งภาพขึ้น Gemini"
            t0 = time.time()
            try:
                pil = Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB))
                r = analyze(pil, self.key, self.model, self.recent, self.summary, self.mode)
                self.lat = time.time() - t0
                self.result = r
                self.summary = (r.get("memory_th") or self.summary).strip()[:MEM_CAP]
                self.n += 1
                self.err = ""
                to_say, narrative = speech_for(r, self.recent)
                if to_say:
                    self.narrative = to_say
                    self.recent = push(self.recent, narrative)
                    self.stage = "🔊 สร้างเสียงไทย"
                    mp3 = tts_thai(to_say, f"/tmp/poc_rt_{self.n}.mp3")
                    if mp3 and not self.speaking:
                        self.proc = subprocess.Popen(
                            ["afplay", mp3], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                elif narrative:
                    self.dup += 1             # เรื่องเดิม -> เงียบ
                self.stage = "✅ เสร็จ"
            except Exception as e:
                self.lat = time.time() - t0
                self.timeouts += 1
                self.stage = "❌ พลาด"
                self.err = f"{e.__class__.__name__}: {e}"[:200]
            finally:
                self.busy = False

    def _fastloop(self):
        """ในเครื่องล้วน ~110 ms/รอบ — เตือนได้ก่อน Gemini 20 เท่า และใช้ได้ตอนเน็ตหลุด"""
        import fast
        last = ""
        while self.running:
            if not self.fast_on:
                time.sleep(.3)
                continue
            with self.lock:
                fr = None if self.frame is None else self.frame.copy()
            if fr is None:
                time.sleep(.1)
                continue
            t0 = time.time()
            try:
                r = fast.read(fr)
                txt = fast.phrase(r) or ""
            except Exception as e:
                self.err = f"fast: {e.__class__.__name__}: {e}"[:140]
                time.sleep(1)
                continue
            self.fast_ms = round((time.time() - t0) * 1000)
            self.fast, self.fast_text = r, txt
            # พูดเฉพาะตอนเรื่องเปลี่ยน และต้องไม่ทับเสียงที่กำลังเล่นอยู่
            if txt and txt != last and not self.speaking:
                last = txt
                self.fast_n += 1
                try:
                    self.fast_proc = subprocess.Popen(
                        ["say", "-v", "Kanya", txt],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass
            elif not txt:
                last = ""

    # ---- สำหรับ UI ----
    def jpeg(self, dev: bool = False) -> bytes | None:
        with self.lock:
            fr = None if self.frame is None else self.frame.copy()
        if fr is None:
            return None
        fr = cv2.resize(fr, (640, 360))
        if dev:
            fr = yolo_plot(fr)
        return cv2.imencode(".jpg", fr, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()

    def state(self) -> dict:
        return {"running": self.running, "speaking": self.speaking, "busy": self.busy,
                "stage": self.stage, "narrative": self.narrative, "err": self.err,
                "fps": round(self.fps, 1), "lat": round(self.lat, 1), "n": self.n,
                "dup": self.dup, "timeouts": self.timeouts, "cam": self.cam,
                "change": round(self.change, 3), "mode": self.mode,
                "still": self.still, "scene": self.scene, "alert": self.alert,
                "noise": self.noise, "auto": self.auto, "voice": "gTTS th",
                "skipped_still": self.skipped_still,
                "fast_on": self.fast_on, "fast_text": self.fast_text,
                "fast_ms": self.fast_ms, "fast_n": self.fast_n,
                "fast": self.fast,
                "every": self.every, "model": self.model, "has_key": bool(self.key),
                "summary": self.summary, "recent": self.recent, "result": self.result}
