"""Realtime Emotion & Context-Aware Vision — POC v1 (realtime only)."""
import asyncio
import io
import json
import os
import re
import threading
import time
from pathlib import Path

import cv2
import numpy as np
import streamlit as st
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

SYSTEM_PROMPT = """\
คุณคือผู้ช่วยบรรยายภาพให้คนตาบอดสนิท (ระดับ 3-5)
ดูภาพแล้วตอบ JSON เท่านั้น ห้ามมีข้อความอื่น:
{
  "emotion": {"label": "...", "confidence": "high|medium|low", "detail_th": "..."},
  "body_language": {"detail_th": "..."},
  "environment": {"scene_th": "...", "objects_th": ["..."], "safety_th": "..."},
  "narrative_th": "ประโยคเดียว อบอุ่น เป็นธรรมชาติ บอกทั้งอารมณ์ ท่าทาง และบรรยากาศรอบตัว"
}
ถ้าไม่มีคนในภาพ ให้ emotion.label = "no_person" แล้วเน้นบรรยายสถานที่กับสิ่งกีดขวาง/อันตราย
narrative_th ต้องสั้น ฟังแล้วเห็นภาพ ไม่เกิน 2 ประโยค"""

# ==================== config ====================
CAM_CHOICE_FILE = Path(__file__).parent / ".cam_choice.json"


def get_api_key() -> str:
    k = st.sidebar.text_input("GEMINI_API_KEY", type="password", placeholder="paste key...")
    return k.strip() or os.getenv("GEMINI_API_KEY", "").strip()


def save_cam_choice(idx: int):
    try:
        CAM_CHOICE_FILE.write_text(json.dumps({"cam_idx": idx}))
    except Exception:
        pass


def load_cam_choice() -> int:
    try:
        return int(json.loads(CAM_CHOICE_FILE.read_text())["cam_idx"])
    except Exception:
        return 0


# ==================== camera ====================
@st.cache_resource(show_spinner=False)
def list_cams(max_n: int = 6) -> list[int]:
    """ไล่ index ต่อเนื่อง เจอตัวแรกที่เปิดไม่ได้ = จบ (กัน 'out device of bound').

    ลำดับของ OpenCV ไม่ตรงกับ system_profiler/ffmpeg (เครื่องนี้ 0=iPhone, 1=MacBook)
    เลยไม่ map ชื่อให้ ต้องดูภาพตัวอย่างเอา
    """
    found: list[int] = []
    devnull, saved = os.open(os.devnull, os.O_WRONLY), os.dup(2)
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


@st.cache_resource(show_spinner=False)
def _cap_reg() -> dict:
    return {}


def get_cap(idx: int):
    """เปิดกล้องค้างไว้ — เปิด/ปิดทุกเฟรมช้ามากบน macOS (~1s/ครั้ง)."""
    reg = _cap_reg()
    cap = reg.get(idx)
    if cap is None or not cap.isOpened():
        cap = cv2.VideoCapture(idx, cv2.CAP_AVFOUNDATION)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        reg[idx] = cap
    return cap


def release_caps():
    for c in _cap_reg().values():
        try:
            c.release()
        except Exception:
            pass
    _cap_reg().clear()


def grab_one(idx: int, w: int = 320):
    cap = get_cap(idx)
    frame = None
    for _ in range(5):                        # ไล่ buffer ให้ได้ภาพสด
        ok, fr = cap.read()
        if ok:
            frame = fr
    if frame is None:
        return None
    h = int(frame.shape[0] * w / frame.shape[1])
    return Image.fromarray(cv2.cvtColor(cv2.resize(frame, (w, h)), cv2.COLOR_BGR2RGB))


# ==================== models ====================
@st.cache_resource(show_spinner=False)
def get_yolo():
    from ultralytics import YOLO
    return YOLO("yolo11n.pt")


GEMINI_TIMEOUT = 25          # วินาที — เกินนี้ถือว่าเจ๊ง ไม่รอต่อ

def analyze_with_gemini(img: Image.Image, api_key: str, model_name: str) -> dict:
    img = img.convert("RGB")
    if img.width > 768:                       # ย่อก่อนส่ง -> อัปโหลดไวขึ้นมาก
        img = img.resize((768, int(img.height * 768 / img.width)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    img_bytes = buf.getvalue()
    try:
        from google import genai as new_genai
        try:
            client = new_genai.Client(api_key=api_key,
                                      http_options={"timeout": GEMINI_TIMEOUT * 1000})
        except Exception:
            client = new_genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=model_name,
            contents=[{"role": "user", "parts": [
                {"inline_data": {"mime_type": "image/jpeg", "data": img_bytes}},
                {"text": SYSTEM_PROMPT + "\nAnalyze this image for a blind user. Return JSON only."}]}],
            config={"temperature": 0.4, "max_output_tokens": 512},
        )
        text = (resp.text or "").strip()
    except ImportError:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name, system_instruction=SYSTEM_PROMPT)
        resp = model.generate_content(
            [{"mime_type": "image/jpeg", "data": img_bytes},
             "Analyze this image for a blind user. Return JSON only."],
            generation_config={"temperature": 0.4, "max_output_tokens": 512},
            request_options={"timeout": GEMINI_TIMEOUT},
        )
        text = (resp.text or "").strip()
    text = re.sub(r"^```(json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except Exception:
        return {"emotion": {"label": "unknown", "confidence": "low", "detail_th": "-"},
                "body_language": {"detail_th": "-"},
                "environment": {"scene_th": "-", "objects_th": [], "safety_th": "-"},
                "narrative_th": text[:500], "_raw": text}


# ==================== tts ====================
async def _edge_tts_async(text: str, out_path: str):
    import edge_tts
    await edge_tts.Communicate(text, voice="th-TH-PremwadeeNeural").save(out_path)


def tts_thai(text: str, out_path: str = "/tmp/poc_th.mp3") -> str | None:
    try:
        import edge_tts  # noqa: F401
        asyncio.run(_edge_tts_async(text, out_path))
        return out_path
    except ImportError:
        pass
    except Exception:
        pass
    try:
        from gtts import gTTS
        gTTS(text=text, lang="th").save(out_path)
        return out_path
    except Exception:
        return None


# ==================== background gemini ====================
@st.cache_resource(show_spinner=False)
def rt_state() -> dict:
    """state ของ background thread — ต้องอยู่รอด rerun."""
    return {"busy": False, "result": None, "narrative": "", "last_spoken": "",
            "t_last": 0.0, "lat": 0.0, "err": "", "n": 0, "proc": None,
            "sent_at": 0.0, "sent_thumb": None, "stage": "รอเริ่ม",
            "gen": 0, "mp3": None, "skipped": 0}


def _gemini_worker(pil, key, model, state, gen, speak):
    """ทำทั้ง Gemini + TTS + เล่นเสียง ใน thread เดียว — main thread จะได้ไม่ค้าง."""
    t0 = time.time()
    try:
        state["stage"] = "📤 ส่งภาพขึ้น Gemini"
        r = analyze_with_gemini(pil, key, model)
        if gen != state["gen"]:               # รอบนี้ถูก timeout ไปแล้ว ทิ้งผลทิ้ง
            return
        state["result"] = r
        narrative = (r.get("narrative_th") or "").strip()
        state["narrative"] = narrative
        state["err"] = ""
        state["n"] += 1
        state["lat"] = time.time() - t0       # latency ของ Gemini ล้วน ๆ

        if narrative and narrative != state["last_spoken"]:
            state["last_spoken"] = narrative
            state["stage"] = "🔊 สร้างเสียงไทย"
            mp3 = tts_thai(narrative, out_path=f"/tmp/poc_rt_{state['n']}.mp3")
            state["mp3"] = mp3
            if mp3 and speak:
                speak_local(mp3, state)
        state["stage"] = "✅ เสร็จ"
    except Exception as e:
        if gen == state["gen"]:
            state["stage"] = "❌ พลาด"
            state["err"] = f"{e.__class__.__name__}: {e}"
    finally:
        if gen == state["gen"]:
            state["busy"] = False


def speak_local(mp3: str, state: dict) -> bool:
    """เล่นผ่านลำโพงเครื่องด้วย afplay — ไม่โดน browser บล็อก autoplay."""
    import subprocess
    pr = state.get("proc")
    if pr is not None and pr.poll() is None:
        return False                          # ยังพูดอยู่ ไม่พูดทับ
    try:
        state["proc"] = subprocess.Popen(["afplay", mp3],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


# ==================== UI ====================
st.set_page_config(page_title="Realtime Vision POC", layout="wide")
st.title("⚡ Realtime Emotion & Context Vision")
st.caption("วิดีโอสด + YOLO ในเครื่อง (realtime) • Gemini บรรยาย background เป็นช่วง ๆ • เสียงไทยออกลำโพง")

api_key = get_api_key()
# วัดจริง 2026-09-11 (ภาพ 768px): 3.1-flash-lite ~2s, 3.5-flash-lite ~27s, flash-lite-latest ~31s
# ตัวที่ช้าเพราะมันเปิด thinking เอง -> realtime ไม่ทัน อย่าใช้
MODELS = ["gemini-3.1-flash-lite", "gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-3-flash-preview"]
model_name = st.sidebar.selectbox("Gemini model", MODELS, index=0)
st.sidebar.caption("✅ **3.1-flash-lite เร็วสุด ~2s** (500 ครั้ง/วัน) — แนะนำตัวนี้\n\n"
                   "⚠️ 3.5-flash-lite ช้า ~27s เพราะเปิด thinking เอง realtime ไม่ทัน")

if "cam_idx" not in st.session_state:
    st.session_state.cam_idx = load_cam_choice()
cams = list_cams()

c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
with c1:
    sel = st.selectbox("กล้อง", cams, format_func=lambda i: f"กล้อง {i}",
                       index=cams.index(st.session_state.cam_idx) if st.session_state.cam_idx in cams else 0)
    if sel != st.session_state.cam_idx:
        st.session_state.cam_idx = sel
        save_cam_choice(sel)
        release_caps()
        st.rerun()
with c2:
    mirror = st.checkbox("🪞 กระจก", value=True)
with c3:
    rt_yolo = st.checkbox("YOLO overlay", value=True)
with c4:
    rt_speak = st.checkbox("🔊 เสียงออกลำโพง", value=True, help="afplay ของ macOS — ไม่โดน browser บล็อก")

# ลำดับ index ของ OpenCV ไม่ตรงกับชื่อกล้องใน macOS -> ต้องดูภาพเอา
with st.expander("🔍 ไม่แน่ใจว่ากล้องไหนคืออันไหน? กดดูภาพตัวอย่าง"):
    st.caption("OpenCV เรียงกล้องคนละลำดับกับ macOS (เครื่องนี้ 0 = iPhone, 1 = MacBook)")
    if st.button("📷 ดูตัวอย่างทุกกล้อง"):
        release_caps()
        st.session_state.cam_previews = {i: grab_one(i) for i in cams}
        release_caps()
    previews = st.session_state.get("cam_previews")
    if previews:
        for col, (i, im) in zip(st.columns(len(previews)), previews.items()):
            with col:
                if im is None:
                    st.warning(f"กล้อง {i}: ไม่มีภาพ")
                    continue
                st.image(im, caption=f"กล้อง {i}", width='stretch')
                if st.button(f"✅ ใช้กล้อง {i}", key=f"pick{i}"):
                    st.session_state.cam_idx = i
                    save_cam_choice(i)
                    release_caps()
                    st.rerun()

r1, r2 = st.columns([1, 3])
with r1:
    rt_on = st.checkbox("⚡ เปิด Realtime", value=False)
with r2:
    rt_every = st.select_slider("Gemini บรรยายทุกกี่วิ", options=[3, 5, 8, 10, 15, 30], value=5)

st.divider()

if not rt_on:
    st.info("ติ๊ก **⚡ เปิด Realtime** เพื่อเริ่มวิดีโอสด")
    if st.button("🔌 ปล่อยกล้อง (ถ้าค้าง)"):
        release_caps()
        st.success("ปล่อยแล้ว")
    st.stop()

if not api_key:
    st.error("ใส่ GEMINI_API_KEY ก่อน (sidebar หรือ .env)")
    st.stop()

stt = rt_state()
cap = get_cap(st.session_state.cam_idx)
if not cap.isOpened():
    release_caps()
    st.error(f"เปิดกล้อง {st.session_state.cam_idx} ไม่ได้ — ลองเลือกกล้องอื่น หรือปลุก iPhone")
    st.stop()

vcol, tcol = st.columns([3, 2])
ph_video, ph_prog, ph_fps = vcol.empty(), vcol.empty(), vcol.empty()
ph_sent, ph_narr, ph_json, ph_stat = tcol.empty(), tcol.empty(), tcol.empty(), tcol.empty()

# ถ้า Gemini ใช้เวลานานกว่าที่ตั้งไว้ ให้ยืดรอบเองอัตโนมัติ จะได้ไม่ยิงทับกันจนคิวค้าง
eff_every = rt_every
if stt["lat"] > rt_every:
    eff_every = round(stt["lat"] * 1.2, 1)
    st.warning(f"⚠️ Gemini ใช้เวลา {stt['lat']:.1f}s ซึ่งนานกว่าที่ตั้งไว้ {rt_every}s "
               f"— ยืดรอบเป็น {eff_every}s ให้อัตโนมัติ (เลือก model *-lite จะเร็วกว่า)")

t_chunk, frames = time.time(), 0
# วนอ่านเฟรมสด ~2 วิ แล้ว rerun หนึ่งครั้ง เพื่อให้ checkbox/ปุ่มยังกดได้
while time.time() - t_chunk < 2.0:
    ok, frame = cap.read()
    if not ok:
        ph_fps.error("อ่านเฟรมไม่ได้ — กล้องอาจถูกแอปอื่นยึด หรือ iPhone หลุด")
        break
    if mirror:
        frame = cv2.flip(frame, 1)

    now = time.time()
    # กันงานค้าง: ถ้ารอบก่อนเกิน timeout ให้ตัดทิ้ง แล้วเดินต่อ
    if stt["busy"] and now - stt["t_last"] > GEMINI_TIMEOUT:
        stt["gen"] += 1                       # เลื่อน gen -> ผลที่ค้างอยู่จะถูกทิ้ง
        stt["busy"] = False
        stt["skipped"] += 1
        stt["stage"] = "⏱️ timeout"
        stt["err"] = f"รอบก่อนเกิน {GEMINI_TIMEOUT}s — ตัดทิ้งแล้วไปรอบใหม่ (ข้ามไป {stt['skipped']} รอบ)"

    if (not stt["busy"]) and (now - stt["t_last"] >= eff_every):  # ยิง Gemini แบบไม่บล็อกวิดีโอ
        stt["gen"] += 1
        stt["busy"], stt["t_last"], stt["sent_at"] = True, now, now
        stt["stage"] = "📤 ส่งภาพขึ้น Gemini"
        stt["sent_thumb"] = cv2.imencode(".jpg", cv2.resize(frame, (240, 135)),
                                         [cv2.IMWRITE_JPEG_QUALITY, 70])[1].tobytes()
        pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        threading.Thread(target=_gemini_worker,
                         args=(pil, api_key, model_name, stt, stt["gen"], rt_speak),
                         daemon=True).start()

    small = cv2.resize(frame, (640, 360))
    if rt_yolo:
        try:
            small = get_yolo().predict(small, verbose=False, imgsz=320, conf=0.4)[0].plot()
        except Exception:
            pass
    if now - stt["sent_at"] < 0.6:            # แฟลชกรอบแดงให้เห็นว่าเฟรมนี้ถูกส่งไป
        cv2.rectangle(small, (2, 2), (637, 357), (0, 0, 255), 6)
        cv2.putText(small, "SENT -> GEMINI", (16, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2, cv2.LINE_AA)
    elif stt["busy"]:                         # กระพริบจุดแดงระหว่างรอผล
        if int(now * 2) % 2 == 0:
            cv2.circle(small, (620, 24), 9, (0, 0, 255), -1)
        cv2.putText(small, "GEMINI...", (505, 32),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2, cv2.LINE_AA)
    # ส่งเป็น JPEG bytes เร็วกว่าให้ streamlit encode PNG เอง
    ph_video.image(cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes())
    frames += 1

    if frames % 4 == 0:                       # แถบ process ~7 ครั้ง/วิ พอ ไม่ต้องทุกเฟรม
        if stt["busy"]:
            el = now - stt["t_last"]
            exp = max(stt["lat"] or 3.0, 0.5)
            ph_prog.progress(min(el / exp, 0.99),
                             text=f"🧠 {stt['stage']} — {el:.1f}s")
        else:
            left = max(eff_every - (now - stt["t_last"]), 0.0)
            ph_prog.progress(min(1 - left / eff_every, 1.0),
                             text=f"⏳ ส่งเฟรมถัดไปให้ Gemini ใน {left:.0f}s")

fps = frames / max(time.time() - t_chunk, 1e-6)
ph_fps.caption(f"🎥 **{fps:.1f} FPS** • กล้อง {st.session_state.cam_idx} • "
               f"Gemini {stt['stage']} • สำเร็จ {stt['n']} รอบ "
               f"(ล่าสุด {stt['lat']:.1f}s, รอบละ {eff_every}s"
               + (f", timeout {stt['skipped']}" if stt["skipped"] else "") + ")")

if stt["sent_thumb"]:
    ph_sent.image(stt["sent_thumb"],
                  caption=f"📤 เฟรมที่ส่งให้ Gemini ล่าสุด (รอบ {stt['n']})")
if stt["err"]:
    ph_stat.error(f"Gemini: {stt['err']}")

narrative = stt["narrative"]
if narrative:
    ph_narr.success(narrative)
    if stt["result"]:
        with ph_json.expander("Result JSON"):
            st.json(stt["result"])
    mp3 = stt["mp3"]
    if mp3 and Path(mp3).exists() and not rt_speak:
        ph_stat.audio(mp3, format="audio/mp3", autoplay=True)   # ไม่เปิดลำโพง -> เล่นผ่าน browser
else:
    ph_narr.info("กำลังรอผลรอบแรกจาก Gemini…")

st.rerun()
