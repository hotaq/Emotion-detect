"""สายเร็ว — หน้าที่เดียวคือกันเดินชน ทำในเครื่องล้วน ไม่ต้องใช้เน็ต

แบ่งงานกับ Gemini ชัดเจน
  สายนี้      ความปลอดภัย  — มีอะไรขวาง อยู่ทางไหน ใกล้แค่ไหน  ต้องทันที
  Gemini      ความหมาย     — อารมณ์ บริบท เล่าเป็นประโยค        รอได้ 2 วิ

โมเดลที่ใช้ (วัดบน MPS 12 ก.ย. 2569)
  Depth-Anything-V2-Metric  ~85 ms   ระยะเป็นเมตรจริง — กันชนกำแพง เสา ประตูกระจก
                                     (COCO ไม่มีคลาสพวกนี้ YOLO จึงมองไม่เห็นเลย)
  YOLO11n                   ~40 ms   บอกชื่อของที่มันรู้จัก ใช้เสริมตอน depth เตือน
  YOLO11n-pose              ~42 ms   คน · ระยะ · ท่าทาง
  MediaPipe FaceLandmarker  ~4 ms    ม่านตา — เขาเห็นเราหรือเปล่า
เสียง: say -v Kanya ของ macOS — ออฟไลน์ เรียก 3 ms

อารมณ์ไม่ได้อ่านที่นี่ เป็นงานของ Gemini — FER เคยอยู่ตรงนี้แต่เอาออกแล้ว
เพราะ eval บอกว่า Gemini แม่นกว่าหรือเท่ากัน และการอ่านอารมณ์ไม่ใช่เรื่องเร่งด่วน
"""
import time
from collections import deque

import cv2
import numpy as np
import torch
from PIL import Image

DEV = "mps" if torch.backends.mps.is_available() else "cpu"
FACE_MODEL = "models/face_landmarker.task"

# COCO keypoints
NOSE, L_EYE, R_EYE, L_EAR, R_EAR = 0, 1, 2, 3, 4
L_SH, R_SH, L_EL, R_EL, L_WR, R_WR, L_HIP, R_HIP = 5, 6, 7, 8, 9, 10, 11, 12
CONF = .5

# ม่านตา: ratio 0=หางตาด้านหนึ่ง 1=อีกด้าน 0.5=มองตรง
IRIS = {"left": (33, 133, 468), "right": (362, 263, 473)}

# สิ่งที่คนตาบอดควรรู้ว่าอยู่ตรงไหน — COCO id -> ชื่อไทย
OBSTACLE = {
    1: "จักรยาน", 2: "รถยนต์", 3: "มอเตอร์ไซค์", 5: "รถบัส", 7: "รถบรรทุก",
    13: "ม้านั่ง", 24: "เป้", 26: "กระเป๋าถือ", 28: "กระเป๋าเดินทาง",
    39: "ขวดน้ำ", 41: "แก้ว", 56: "เก้าอี้", 57: "โซฟา", 58: "กระถางต้นไม้",
    59: "เตียง", 60: "โต๊ะ", 62: "จอทีวี", 63: "แล็ปท็อป", 72: "ตู้เย็น",
}
ROAD = {2, 3, 5, 7}                            # ยานพาหนะ = อันตรายกว่าเฟอร์นิเจอร์

_pose = _det = _face = _depth = None


def _models():
    global _pose, _det, _face, _depth
    if _pose is None:
        from ultralytics import YOLO
        _pose = YOLO("yolo11n-pose.pt")
        _det = YOLO("yolo11n.pt")
    if _depth is None:
        from transformers import pipeline as hf
        _depth = hf("depth-estimation",
                    model="depth-anything/Depth-Anything-V2-Metric-Indoor-Small-hf", device=DEV)
    if _face is None:
        import mediapipe as mp
        from mediapipe.tasks import python as mpp
        from mediapipe.tasks.python import vision
        _face = vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
            base_options=mpp.BaseOptions(model_asset_path=FACE_MODEL,
                                         delegate=mpp.BaseOptions.Delegate.CPU),
            output_face_blendshapes=True, num_faces=1))
        _face.__dict__["_mp"] = mp
    return _pose, _det, _face, _depth


def face_signals(frame) -> dict:
    """ม่านตา + blendshape — บอกได้ว่าเขามองมาทางเราจริงไหม ไม่ใช่แค่เห็นตาเขา"""
    _, _, face, _ = _models()
    mp = face.__dict__["_mp"]
    res = face.detect(mp.Image(image_format=mp.ImageFormat.SRGB,
                               data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
    if not res.face_landmarks:
        return {}
    lm = res.face_landmarks[0]
    ratios = []
    for a, b, iris in IRIS.values():
        span = lm[b].x - lm[a].x
        if abs(span) > 1e-6:
            ratios.append((lm[iris].x - lm[a].x) / span)
    bs = {b.category_name: b.score for b in (res.face_blendshapes[0] if res.face_blendshapes else [])}
    off = sum(abs(r - .5) for r in ratios) / len(ratios) if ratios else None
    return {
        "gaze": None if off is None else ("มองมาที่คุณ" if off < .12 else "มองไปทางอื่น"),
        "gaze_off": None if off is None else round(off, 2),
        "brow_down": round(max(bs.get("browDownLeft", 0), bs.get("browDownRight", 0)), 2),
        "squint": round(max(bs.get("eyeSquintLeft", 0), bs.get("eyeSquintRight", 0)), 2),
        "smile": round(max(bs.get("mouthSmileLeft", 0), bs.get("mouthSmileRight", 0)), 2),
        "jaw_open": round(bs.get("jawOpen", 0), 2),
    }


def obstacles(frame, det, max_n=2) -> list[dict]:
    """สิ่งกีดขวางที่ใกล้พอจะต้องบอก — เรียงตามความใกล้"""
    H, W = frame.shape[:2]
    r = det.predict(frame, verbose=False, device=DEV, conf=.4)[0]
    b = r.boxes
    if not len(b):
        return []
    xyxy, cls = b.xyxy.cpu().numpy(), b.cls.cpu().numpy().astype(int)
    out = []
    for (x1, y1, x2, y2), c in zip(xyxy, cls):
        if c not in OBSTACLE:
            continue
        big = (y2 - y1) / H
        if big < .18:                          # เล็กเกินไป = อยู่ไกล ไม่ต้องเตือน
            continue
        cx = (x1 + x2) / 2 / W
        out.append({"name": OBSTACLE[c], "big": round(float(big), 2), "road": c in ROAD,
                    "side": "ทางซ้าย" if cx < .38 else "ทางขวา" if cx > .62 else "ตรงหน้า"})
    seen, uniq = set(), []                     # ของชนิดเดียวกันฝั่งเดียวกัน พูดครั้งเดียวพอ
    for o in sorted(out, key=lambda o: -o["big"]):
        k = (o["name"], o["side"])
        if k not in seen:
            seen.add(k); uniq.append(o)
    return uniq[:max_n]


# ระยะเป็นเมตรจริงจากรุ่น Metric — เกณฑ์จึงตั้งเป็นเมตรได้ตรง ๆ ไม่ต้องจูนตามฉาก
# รุ่นเดิม (relative) ให้ค่า 0-1 ที่แปลว่า "ใกล้สุดในเฟรมนี้" ซึ่งทุกเฟรมมีเสมอ -> เตือนตลอด
WARN_M = 1.5       # ใช้แค่ติดป้าย near_side ให้หน้า /dev ดู — ไม่ได้เอาไว้เตือน
STOP_M = 0.5       # ชิดจริง ๆ เท่านั้นถึงเตือน (ประมาณช่วงแขน)
RELEASE_M = 0.9    # ต้องถอยห่างเกินนี้ก่อน ถึงจะเตือนรอบใหม่ได้ — กันพูดซ้ำ
DROP_M = .30       # เข้ามาใกล้ขึ้นเท่านี้ในหนึ่งหน้าต่าง = กำลังเดินเข้าไปหา
GROW = .05          # โตขึ้นเท่านี้ใน 1 วิ = กำลังเข้ามาหา ไม่ใช่แค่อยู่ใกล้
# วัดจริง: คนตาบอดเดินระวัง ~0.2 m/s หน้าต่าง 1.2 วิ จับไม่ทัน (ลดแค่ 0.24 m) — ต้องยืด
WINDOW = 2.4        # วินาที ที่ย้อนไปเทียบ  -> จับได้ตั้งแต่ ~0.125 m/s

# ponytail: กล้องตัวเดียว ใช้ประวัติตัวเดียวพอ — ถ้าทำหลายกล้องต้องแยกตาม cam id
_hist = deque(maxlen=64)         # ~8 Hz × 8 วิ พอสำหรับหน้าต่าง 2.4 วิ


_armed = True       # เตือนไปแล้วรอบนี้หรือยัง


def reset_history():
    global _armed
    _hist.clear()
    _armed = True


def _growing(key: str, now_val: float) -> bool:
    """กล่องคนโตขึ้นในภาพไหม — โตขึ้น = เดินเข้ามาหาเรา"""
    if now_val is None:
        return False
    t = time.time()
    old = [v for ts, k, v in _hist if k == key and t - ts >= WINDOW]
    return bool(old) and (now_val - old[-1]) > GROW


def _closing(now_m: float) -> bool:
    """ระยะเป็นเมตรลดลงไหม — ลดลง = กำลังเดินเข้าไปหา

    เทียบกับมัธยฐานของช่วง [WINDOW, WINDOW+0.8s] ก่อนหน้า ไม่ใช่เฟรมเดียว — depth สั่นได้ ±0.1 m
    """
    if now_m is None:
        return False
    t = time.time()
    old = [v for ts, k, v in _hist
           if k == "dist" and v is not None and WINDOW <= t - ts <= WINDOW + .8]
    if not old:
        return False
    old.sort()
    return (old[len(old) // 2] - now_m) > DROP_M


def say_dist(m: float) -> str:
    if m < .6:
        return "ชิดตัวแล้ว"
    if m < 1.2:
        return "ห่างประมาณหนึ่งก้าว"
    if m < 2.0:
        return "ห่างประมาณสองก้าว"
    return f"ห่างประมาณ {round(m)} เมตร"
SIDE_TH = {"ซ้าย": 0, "ตรงหน้า": 1, "ขวา": 2}


def depth_bands(frame, depth) -> dict:
    """แบ่งแถบที่เท้าจะเดินไปเป็นสามส่วน คืนระยะเป็นเมตรของแต่ละฝั่ง"""
    out = depth(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
    # ต้องใช้ predicted_depth เท่านั้น — out["depth"] เป็นภาพ 0-255 ไว้ดูเฉย ๆ ไม่ใช่เมตร
    pd = out["predicted_depth"]
    d = np.asarray(pd.squeeze().cpu() if hasattr(pd, "cpu") else pd, dtype=np.float32)
    H, W = d.shape
    walk = d[int(H * .50):int(H * .95), :]                  # ครึ่งล่าง = ที่ที่จะเดินเข้าไป
    m = [float(np.median(walk[:, int(W * a):int(W * b)])) for a, b in ((0, .33), (.33, .67), (.67, 1))]
    i = int(np.argmin(m))                                   # เมตรน้อย = ใกล้
    # ทั้งสามฝั่งใกล้พอ ๆ กัน = กำแพงหรือของใหญ่เต็มหน้า อย่าสุ่มเลือกฝั่ง ไม่งั้นพูดสลับซ้าย-ขวา
    side = "ตรงหน้า" if (max(m) - min(m)) < .25 else ["ทางซ้าย", "ตรงหน้า", "ทางขวา"][i]
    return {"dist_m": [round(v, 1) for v in m],
            "near_side": side if m[i] < WARN_M else None,
            "near_m": round(m[i], 1),
            "very_near": m[i] < STOP_M}


def read(frame) -> dict:
    pose, det, _, depth = _models()
    H, W = frame.shape[:2]
    r = pose.predict(frame, verbose=False, device=DEV, conf=.35)[0]
    out = {"persons": len(r.boxes), "near": None, "facing": None, "gesture": None,
           "obstacles": obstacles(frame, det), **depth_bands(frame, depth)}
    now = time.time()
    _hist.append((now, "dist", out.get("near_m")))
    out["closing_in"] = _closing(out.get("near_m"))
    if not len(r.boxes):
        _hist.append((now, "person", 0.0))
        out["approaching"] = False
        return out
    xyxy = r.boxes.xyxy.cpu().numpy()          # tensor อยู่บน MPS ต้องย้ายมา cpu ก่อน
    i = int(np.argmax(xyxy[:, 3] - xyxy[:, 1]))
    x1, y1, x2, y2 = (int(v) for v in xyxy[i])
    ratio = (y2 - y1) / H
    out["near"] = ("ใกล้มาก" if ratio > .75 else
                   "ห่างประมาณสองสามก้าว" if ratio > .4 else "อยู่ไกลออกไป")

    k = r.keypoints
    if k is not None and k.conf is not None and len(k.conf) > i:
        xy, c = k.xy[i].cpu().numpy(), k.conf[i].cpu().numpy()
        see = lambda j: c[j] > CONF
        if see(L_EAR) != see(R_EAR):
            out["facing"] = "หันข้างให้"
        # ponytail: ตีความท่าทางแบบง่าย ๆ พอสำหรับ POC
        if all(see(j) for j in (L_WR, R_WR, L_SH, R_SH, L_HIP)):
            lo, hi = min(xy[L_SH][0], xy[R_SH][0]), max(xy[L_SH][0], xy[R_SH][0])
            mid_y = xy[L_SH][1] + (xy[L_HIP][1] - xy[L_SH][1]) * .5
            if all(lo < xy[j][0] < hi and xy[j][1] < mid_y for j in (L_WR, R_WR)):
                out["gesture"] = "ยืนกอดอก"
        for wr, sh in ((L_WR, L_SH), (R_WR, R_SH)):
            if see(wr) and see(sh) and xy[wr][1] < xy[sh][1]:
                out["gesture"] = "ยกมือขึ้น"

    _hist.append((time.time(), "person", ratio))
    out["approaching"] = _growing("person", ratio)
    if ratio > .25:                            # ใกล้พอจะเห็นหน้า -> เขามองเราหรือเปล่า
        out.update(face_signals(frame))
        if out.get("gaze"):
            out["facing"] = out["gaze"]
    return out


def phrase(r: dict) -> str | None:
    """เตือนอย่างเดียว: ชิดของจริง ๆ แล้ว — อย่างอื่นเงียบหมด

    พูดครั้งเดียวต่อการเข้าใกล้หนึ่งครั้ง แล้วต้องถอยห่างเกิน RELEASE_M ก่อนถึงจะเตือนใหม่
    ไม่งั้นยืนอยู่ข้างกำแพงมันจะพูดทุกครั้งที่คำเปลี่ยน (ซ้าย/ขวา/หนึ่งก้าว/ชิด)
    """
    global _armed
    m = r.get("near_m")
    if m is None:
        return None
    if m > RELEASE_M:
        _armed = True                           # ห่างออกไปแล้ว พร้อมเตือนรอบหน้า
        return None
    if m < STOP_M and _armed:
        _armed = False
        side = r.get("near_side") or "ตรงหน้า"
        named = next((o["name"] for o in r.get("obstacles", []) if o["side"] == side), None)
        return f"ระวัง มี{named or 'อะไรบางอย่าง'}{side} ชิดตัวแล้ว"
    return None
