import asyncio
import io
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image
import streamlit as st

load_dotenv()

SYSTEM_PROMPT = """\
You are an Emotion & Context-Aware AI Vision Assistant for blind users.
Analyze the image and return ONLY valid JSON (no markdown) with this schema:
{
  "emotion": {"label": "happy/sad/angry/neutral/surprise/fear/unknown", "confidence": "high/medium/low", "detail_th": "อธิบายสีหน้าคนตรงหน้าเป็นภาษาไทยสั้นๆ"},
  "body_language": {"detail_th": "ท่าทาง ระยะห่าง หันมาหาเราหรือไม่ เป็นภาษาไทย"},
  "environment": {"scene_th": "สถานที่คืออะไร", "objects_th": ["วัตถุสำคัญ"], "safety_th": "เตือนภัยถ้ามี ไม่งั้นบอกว่าปลอดภัย"},
  "narrative_th": "เล่ารวม 1-2 ประโยค ภาษาไทย อบอุ่น เข้าใจง่าย เอาความปลอดภัยก่อน"
}
Rules:
- narrative_th is what the user HEARS. Concise, no jargon.
- If no person visible, emotion.label = "unknown" and say so in Thai.
- Never hallucinate names. Never invent objects.
- Prioritize hazards (stairs, vehicles, obstacles).
"""

def get_api_key():
    sidebar_key = st.sidebar.text_input("GEMINI_API_KEY", type="password", placeholder="paste key...")
    return sidebar_key.strip() or os.getenv("GEMINI_API_KEY", "").strip()

def analyze_with_gemini(img: Image.Image, api_key: str, model_name: str) -> dict:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=90)
    img_bytes = buf.getvalue()
    text = ""
    # Try new SDK (google-genai) first, fall back to old (google-generativeai)
    try:
        from google import genai as new_genai
        client = new_genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=model_name,
            contents=[{"role": "user", "parts": [{"inline_data": {"mime_type": "image/jpeg", "data": img_bytes}}, {"text": SYSTEM_PROMPT + "\nAnalyze this image for a blind user. Return JSON only."}]}],
            config={"temperature": 0.4, "max_output_tokens": 1024},
        )
        text = (resp.text or "").strip()
    except ImportError:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name, system_instruction=SYSTEM_PROMPT)
        resp = model.generate_content(
            [{"mime_type": "image/jpeg", "data": img_bytes},
             "Analyze this image for a blind user. Return JSON only."],
            generation_config={"temperature": 0.4, "max_output_tokens": 1024},
        )
        text = (resp.text or "").strip()
    # strip code fences if model adds them
    text = re.sub(r"^```(json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except Exception:
        # fallback: wrap raw text as narrative
        return {
            "emotion": {"label": "unknown", "confidence": "low", "detail_th": "-"},
            "body_language": {"detail_th": "-"},
            "environment": {"scene_th": "-", "objects_th": [], "safety_th": "-"},
            "narrative_th": text[:500],
            "_raw": text,
        }

def yolo_overlay(img: Image.Image) -> Image.Image:
    """Try YOLO11n boxes. Fail-soft -> return original."""
    try:
        res = get_yolo().predict(img, verbose=False)[0]
        return Image.fromarray(res.plot()[:, :, ::-1])
    except Exception as e:
        st.caption(f"YOLO skipped ({e.__class__.__name__}): showing original")
        return img

async def _edge_tts_async(text: str, out_path: str):
    import edge_tts
    comm = edge_tts.Communicate(text, voice="th-TH-PremwadeeNeural")
    await comm.save(out_path)

def tts_thai(text: str, out_path: str = "/tmp/poc_th.mp3") -> str | None:
    # 1) edge-tts (เสียงดีสุด)
    try:
        import edge_tts
        asyncio.run(_edge_tts_async(text, out_path))
        return out_path
    except ImportError:
        pass
    except Exception as e:
        st.warning(f"edge-tts error ({e}), fallback gTTS")
    # 2) gTTS fallback (ลงง่าย ไม่มีปัญหา env)
    try:
        from gtts import gTTS
        gTTS(text=text, lang="th").save(out_path)
        return out_path
    except ImportError:
        st.error("ยังไม่มี TTS: รัน `python3 -m pip install edge-tts gtts` ใน env เดียวกับ streamlit แล้ว restart")
        return None
    except Exception as e:
        st.warning(f"gTTS failed ({e})")
        return None


# ==================== camera / model helpers (realtime) ====================
CAM_CHOICE_FILE = Path(__file__).parent / ".cam_choice.json"

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

@st.cache_resource(show_spinner=False)
def list_cams(max_n: int = 6) -> list[int]:
    """ไล่ index ต่อเนื่อง เจอตัวแรกที่เปิดไม่ได้ = จบ (กัน 'out device of bound').

    หมายเหตุสำคัญ: ลำดับของ OpenCV ไม่ตรงกับ system_profiler / ffmpeg
    เช่นเครื่องนี้ OpenCV 0 = iPhone, 1 = MacBook (กลับกับที่ macOS บอก)
    เลยไม่ map ชื่อให้ ต้องดูภาพตัวอย่างเอา
    """
    import cv2, os
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
    """เปิดกล้องค้างไว้ (เปิด/ปิดทุกเฟรม = ช้ามาก บน macOS ~1s/ครั้ง)."""
    import cv2
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
    """ปล่อยกล้องทุกตัวจริง ๆ (cache.clear() เฉย ๆ ไม่ปล่อย handle)."""
    reg = _cap_reg()
    for c in reg.values():
        try:
            c.release()
        except Exception:
            pass
    reg.clear()

def grab_one(idx: int, w: int = 320):
    """แคป 1 เฟรมไว้ทำภาพตัวอย่างตอนเลือกกล้อง."""
    import cv2
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

@st.cache_resource(show_spinner=False)
def get_yolo():
    """โหลดโมเดลครั้งเดียว (เดิมโหลดใหม่ทุกเฟรม)."""
    from ultralytics import YOLO
    return YOLO("yolo11n.pt")

@st.cache_resource(show_spinner=False)
def rt_state() -> dict:
    """state ของ background Gemini thread (อยู่รอด rerun)."""
    return {"busy": False, "result": None, "narrative": "", "last_spoken": "",
            "t_last": 0.0, "err": "", "n": 0, "proc": None}

def _gemini_worker(pil, key, model, state):
    try:
        r = analyze_with_gemini(pil, key, model)
        state["result"] = r
        state["narrative"] = (r.get("narrative_th") or "").strip()
        state["err"] = ""
        state["n"] += 1
    except Exception as e:
        state["err"] = f"{e.__class__.__name__}: {e}"
    finally:
        state["busy"] = False

def speak_local(mp3: str, state: dict):
    """เล่นเสียงผ่านลำโพงเครื่องด้วย afplay — ไม่โดน browser บล็อก autoplay."""
    import subprocess
    pr = state.get("proc")
    if pr is not None and pr.poll() is None:
        return False                          # ยังพูดอยู่ ไม่ทับ
    try:
        state["proc"] = subprocess.Popen(["afplay", mp3],
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False

st.set_page_config(page_title="Emotion Vision POC", layout="wide")
st.title("👁️ Emotion & Context-Aware Vision — POC")
st.caption("POC v0: upload/snap → YOLO overlay (โชว์) + Gemini Flash (คิด) → เสียงไทย")

api_key = get_api_key()
model_name = st.sidebar.selectbox("Gemini model", ["gemini-2.5-flash", "gemini-3.6-flash", "gemini-3-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"], index=0)
use_yolo = st.sidebar.checkbox("YOLO overlay", value=True)

mode = st.radio("📷 แหล่งภาพ", ["อัปโหลด", "Webcam (browser)", "กล้อง USB (สลับได้)"], horizontal=True)
img = None
src = None

if mode == "อัปโหลด":
    up = st.file_uploader("อัพรูป", type=["jpg", "jpeg", "png", "webp"])
    if up:
        src = up
        img = Image.open(src).convert("RGB")
    path_in = st.text_input("หรือวาง local path (เช่น /var/.../xxx.png)", placeholder="/var/folders/.../image.png")
    if path_in and img is None:
        try:
            img = Image.open(path_in.strip()).convert("RGB")
            st.caption(f"โหลดจาก path: {path_in.strip()}")
        except Exception as e:
            st.error(f"เปิดไฟล์ไม่ได้: {e}")

elif mode == "Webcam (browser)":
    st.caption("บนมือถือ browser จะถามเองว่าจะใช้กล้องหน้าหรือหลัง")
    cam = st.camera_input("ถ่ายจาก webcam")
    if cam:
        src = cam
        img = Image.open(src).convert("RGB")

else:
    # USB / built-in multi-cam via OpenCV — สลับกล้องได้จริง
    import cv2
    import numpy as np
    if "cam_idx" not in st.session_state:
        st.session_state.cam_idx = load_cam_choice()
    if "cv_frame" not in st.session_state:
        st.session_state.cv_frame = None
    cams = list_cams()
    def cam_label(i):
        return f"กล้อง {i}"
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        sel = st.selectbox("เลือกกล้อง", cams, format_func=cam_label,
                           index=cams.index(st.session_state.cam_idx) if st.session_state.cam_idx in cams else 0)
        if sel != st.session_state.cam_idx:
            st.session_state.cam_idx = sel
            save_cam_choice(sel)
            release_caps()           # เปลี่ยนกล้อง -> ปล่อยตัวเดิมก่อน
            st.rerun()
    with c2:
        if st.button("🔄 สลับกล้อง"):
            # วนไปกล้องตัวถัดไป
            ni = (cams.index(st.session_state.cam_idx) + 1) % len(cams) if st.session_state.cam_idx in cams else 0
            st.session_state.cam_idx = cams[ni]
            save_cam_choice(cams[ni])
            release_caps()
            st.rerun()
    with c3:
        mirror = st.checkbox("กระจก", value=True)
    st.session_state.mirror = mirror

    # ⚠️ ลำดับ index ของ OpenCV ไม่ตรงกับชื่อกล้องใน macOS -> ต้องดูภาพเอา
    with st.expander("🔍 ไม่แน่ใจว่ากล้องไหนคืออันไหน? กดดูภาพตัวอย่าง"):
        st.caption("OpenCV เรียงกล้องคนละลำดับกับ macOS (เครื่องนี้ 0 = iPhone, 1 = MacBook) — ดูภาพแล้วเลือกชัวร์กว่า")
        if st.button("📷 ดูตัวอย่างทุกกล้อง"):
            release_caps()
            st.session_state.cam_previews = {i: grab_one(i) for i in cams}
            release_caps()
        previews = st.session_state.get("cam_previews")
        if previews:
            pcols = st.columns(len(previews))
            for col, (i, im) in zip(pcols, previews.items()):
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

    if st.button("📸 ถ่ายภาพ", type="primary"):
        cap = get_cap(st.session_state.cam_idx)
        for _ in range(3):          # ไล่เฟรมค้างใน buffer ออกก่อน
            ok, frame = cap.read()
        if ok:
            if mirror:
                frame = cv2.flip(frame, 1)
            st.session_state.cv_frame = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        else:
            st.error(f"เปิดกล้อง {st.session_state.cam_idx} ไม่ได้")
    if st.session_state.cv_frame is not None:
        img = st.session_state.cv_frame

if img is None:
    st.info("👆 เลือกภาพ / ถ่ายภาพก่อน แล้วกด Analyze")
    st.stop()

# ↔️ สลับซ้าย-ขวา (flip horizontal) ใช้ได้ทุกโหมด กดแล้วคงอยู่จนกดอีกที
if "flip_h" not in st.session_state:
    st.session_state.flip_h = False
if st.button("↔️ สลับซ้าย-ขวา", help="กลับภาพซ้ายขวา เช่น กล้องหน้ากระจก"):
    st.session_state.flip_h = not st.session_state.flip_h
    st.rerun()
if st.session_state.flip_h:
    img = img.transpose(Image.FLIP_LEFT_RIGHT)
if st.session_state.flip_h:
    st.caption("↔️ flipped (กดปุ่มอีกทีเพื่อกลับ)")

col1, col2 = st.columns(2)
with col1:
    st.image(img, caption="input", width='stretch')

if st.button("🔍 Analyze", type="primary"):
    if not api_key:
        st.error("ใส่ GEMINI_API_KEY ก่อน (sidebar หรือ .env)")
        st.stop()
    with st.spinner("Gemini กำลังดูรูป..."):
        result = analyze_with_gemini(img, api_key, model_name)
    with col2:
        disp = yolo_overlay(img) if use_yolo else img
        st.image(disp, caption="detection view", width='stretch')
    st.subheader("📋 Result JSON")
    st.json(result)
    narrative = result.get("narrative_th", "")
    st.subheader("🗣️ Narrative (สิ่งที่จะพูด)")
    st.success(narrative)
    if narrative:
        with st.spinner("กำลังสร้างเสียงไทย..."):
            mp3 = tts_thai(narrative)
        if mp3 and Path(mp3).exists():
            sz = Path(mp3).stat().st_size // 1024
            st.caption(f"🔊 ไฟล์เสียงพร้อม ({sz}KB) — กด ▶️ เพื่อฟัง (browser บล็อก autoplay)")
            st.audio(mp3, format="audio/mp3")
            st.download_button("⬇️ โหลด mp3", data=open(mp3, "rb").read(), file_name="narrative_th.mp3", mime="audio/mp3")

st.divider()
st.subheader("⚡ Realtime mode (วิดีโอสด + บรรยายอัตโนมัติ)")
st.caption("วิดีโอลื่นแบบ real-time (YOLO ในเครื่อง) ส่วน Gemini ยิงเป็นช่วง ๆ แบบ background ไม่หน่วงภาพ")

rc1, rc2, rc3, rc4 = st.columns([1.4, 1, 1, 1])
with rc1:
    rt_on = st.checkbox("⚡ เปิด Realtime", value=False)
with rc2:
    rt_every = st.select_slider("Gemini ทุกกี่วิ", options=[3, 5, 8, 10, 15, 30], value=8)
with rc3:
    rt_yolo = st.checkbox("YOLO overlay", value=True)
with rc4:
    rt_speak = st.checkbox("🔊 เสียงออกลำโพง", value=True, help="ใช้ afplay ของ macOS — ไม่โดน browser บล็อก autoplay")

if rt_on:
    if mode != "กล้อง USB (สลับได้)":
        st.warning("Realtime ใช้ได้กับโหมด ‘กล้อง USB’ เท่านั้น — สลับไปโหมดนั้นก่อน")
        st.stop()
    if not api_key:
        st.error("ใส่ GEMINI_API_KEY ก่อน")
        st.stop()

    import time as _t, threading as _th, cv2 as _cv2
    stt = rt_state()
    cap = get_cap(st.session_state.cam_idx)
    if not cap.isOpened():
        release_caps()
        st.error(f"เปิดกล้อง index {st.session_state.cam_idx} ไม่ได้ — เลือก index อื่นด้านบน")
        st.stop()

    vcol, tcol = st.columns([3, 2])
    ph_video = vcol.empty()
    ph_fps = vcol.empty()
    ph_narr = tcol.empty()
    ph_json = tcol.empty()
    ph_stat = tcol.empty()

    mirror_rt = st.session_state.get("mirror", True)
    t_chunk = _t.time()
    frames = 0
    last_draw = 0.0

    # วนอ่านเฟรมสด ~2 วิ แล้ว rerun ครั้งนึง (เพื่อให้ checkbox/ปุ่มตอบสนอง)
    while _t.time() - t_chunk < 2.0:
        ok, frame = cap.read()
        if not ok:
            ph_fps.error("อ่านเฟรมไม่ได้ — กล้องอาจถูกแอปอื่นยึด หรือ iPhone หลุด")
            break
        if mirror_rt:
            frame = _cv2.flip(frame, 1)

        small = _cv2.resize(frame, (640, 360))
        if rt_yolo:
            try:
                disp = get_yolo().predict(small, verbose=False, imgsz=320, conf=0.4)[0].plot()[:, :, ::-1]
            except Exception:
                disp = small[:, :, ::-1]
        else:
            disp = small[:, :, ::-1]
        ph_video.image(disp, channels="RGB", width='stretch')
        frames += 1

        now = _t.time()
        # ยิง Gemini แบบ background — ไม่บล็อกวิดีโอ
        if (not stt["busy"]) and (now - stt["t_last"] >= rt_every):
            stt["busy"] = True
            stt["t_last"] = now
            pil = Image.fromarray(_cv2.cvtColor(frame, _cv2.COLOR_BGR2RGB))
            _th.Thread(target=_gemini_worker,
                       args=(pil, api_key, model_name, stt), daemon=True).start()

    fps = frames / max(_t.time() - t_chunk, 1e-6)
    ph_fps.caption(f"🎥 {fps:.1f} FPS — กล้อง index {st.session_state.cam_idx} — "
                   f"Gemini ทุก {rt_every}s ({'กำลังคิด…' if stt['busy'] else 'ว่าง'}) — รอบที่ {stt['n']}")

    narrative = stt["narrative"]
    if stt["err"]:
        ph_stat.error(f"Gemini: {stt['err']}")
    if narrative:
        ph_narr.success(narrative)
        if stt["result"]:
            with ph_json.expander("Result JSON"):
                st.json(stt["result"])
        if narrative != stt["last_spoken"]:
            stt["last_spoken"] = narrative
            mp3 = tts_thai(narrative, out_path=f"/tmp/poc_rt_{stt['n']}.mp3")
            if mp3 and Path(mp3).exists():
                if rt_speak and speak_local(mp3, stt):
                    ph_stat.caption("🔊 กำลังพูดผ่านลำโพงเครื่อง")
                else:
                    ph_stat.audio(mp3, format="audio/mp3", autoplay=True)
    else:
        ph_narr.info("กำลังรอผลรอบแรกจาก Gemini…")

    st.rerun()
else:
    st.caption("ปิดอยู่ — ติ๊ก ‘⚡ เปิด Realtime’ เพื่อเริ่มวิดีโอสด")
    if st.button("🔌 ปล่อยกล้อง (ถ้าค้าง)"):
        release_caps()
        st.success("ปล่อยแล้ว")
