"""วัดว่าย้าย FER + YOLO11-Pose ลงเครื่องแล้ว เร็วพอและแม่นพอไหม

    python eval/bench_local.py

เทียบกับ baseline Gemini ใน results.json (2.2 วิ/ภาพ, อ่านอารมณ์ถูก 4/6)
"""
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image

HERE = Path(__file__).parent
IMG = HERE / "img"
DEV = "mps" if torch.backends.mps.is_available() else "cpu"

# เฉลยจากคำค้นที่ใช้ดึงภาพ — 8 คลาสเดียวกับที่ prompt บังคับไว้
TRUTH = {"emotion_0": "happy", "emotion_1": "sad", "emotion_2": "angry",
         "emotion_3": "surprise", "emotion_4": "sad", "emotion_5": "happy",
         "emotion_6": "angry"}
ALIAS = {"happiness": "happy", "sadness": "sad", "anger": "angry",
         "surprised": "surprise", "fearful": "fear", "disgusted": "disgust"}


def bench_pose():
    from ultralytics import YOLO
    m = YOLO("yolo11n-pose.pt")
    files = sorted(IMG.glob("*.jpg"))
    m.predict(str(files[0]), verbose=False, device=DEV)          # warmup
    rows, t_all = [], 0.0
    for f in files:
        t = time.time()
        r = m.predict(str(f), verbose=False, device=DEV, conf=.35)[0]
        dt = (time.time() - t) * 1000
        t_all += dt
        kp = r.keypoints
        n = 0 if kp is None else len(kp)
        vis = 0 if not n else int((kp.conf > .5).sum())           # จุดข้อต่อที่มั่นใจ
        rows.append((f.stem, dt, n, vis))
    return rows, t_all / len(files)


def crop_haar(img):
    """ตัวหาหน้าแบบเก่า (2001) — เร็วแต่พลาดบ่อยเวลาหน้าเอียงหรือแสงไม่ดี"""
    haar = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = haar.detectMultiScale(g, 1.1, 5, minSize=(60, 60))
    if not len(faces):
        return None
    x, y, w, h = max(faces, key=lambda b: b[2] * b[3])
    p = int(.2 * w)
    return img[max(0, y - p):y + h + p, max(0, x - p):x + w + p]


_person = None


def crop_person_head(img):
    """ใช้ YOLO หาคนก่อน แล้วตัดส่วนหัว (40% บนของกล่อง) — ทนกว่า haar"""
    global _person
    if _person is None:
        from ultralytics import YOLO
        _person = YOLO("yolo11n.pt")
    r = _person.predict(img, verbose=False, device=DEV, classes=[0], conf=.3)[0]
    if not len(r.boxes):
        return None
    b = max(r.boxes, key=lambda b: float(b.conf))
    x1, y1, x2, y2 = (int(v) for v in b.xyxy[0])
    h = int((y2 - y1) * .42)
    return img[y1:y1 + h, x1:x2]


def bench_fer(cropper, name):
    from transformers import pipeline
    clf = pipeline("image-classification", model="trpakov/vit-face-expression", device=DEV)
    rows, t_all = [], 0.0
    files = sorted(IMG.glob("emotion_*.jpg"))
    clf(Image.open(files[0]).convert("RGB"))                      # warmup
    for f in files:
        img = cv2.imread(str(f))
        t = time.time()
        crop = cropper(img)
        found = crop is not None and crop.size > 0
        if not found:
            crop = img                                            # ไม่เจอ -> ใส่ทั้งภาพ
        out = clf(Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)))[0]
        dt = (time.time() - t) * 1000
        t_all += dt
        lab = ALIAS.get(out["label"].lower(), out["label"].lower())
        rows.append((f.stem, dt, int(found), lab, out["score"], TRUTH.get(f.stem, "?")))
    return rows, t_all / len(files)


def main():
    print(f"อุปกรณ์: {DEV}\n")

    print("=" * 68)
    print("YOLO11n-Pose — อ่านท่าทาง")
    print("=" * 68)
    rows, avg = bench_pose()
    body = [r for r in rows if r[0].startswith("body_")]
    for n, dt, cnt, vis in body:
        print(f"  {n:12s} {dt:6.0f} ms   คน {cnt}   จุดข้อต่อชัด {vis}")
    hit = sum(1 for _, _, c, _ in body if c)
    print(f"\n  เฉลี่ยทั้ง 24 ภาพ : {avg:.0f} ms/ภาพ")
    print(f"  เจอคนในภาพ body  : {hit}/{len(body)}")

    best = (0, 1e9, "")
    for cropper, name in ((crop_haar, "haar cascade"), (crop_person_head, "YOLO person -> หัว")):
        print("\n" + "=" * 68)
        print(f"FER (ViT) + {name}")
        print("=" * 68)
        rows, avg_f = bench_fer(cropper, name)
        ok = 0
        for n, dt, nf, lab, sc, gt in rows:
            good = lab == gt
            ok += good
            print(f"  {n:12s} {dt:6.0f} ms   ตัดหน้าได้ {'✓' if nf else '✗'}"
                  f"   ทำนาย {lab:9s} ({sc:.2f})   เฉลย {gt:9s} {'✓' if good else '✗'}")
        print(f"\n  เฉลี่ย {avg_f:.0f} ms/ภาพ   ถูก {ok}/{len(rows)}")
        if ok > best[0]:
            best = (ok, avg_f, name)
    ok, avg_f, name = best

    print("\n" + "=" * 68)
    print("สรุปเทียบ Gemini")
    print("=" * 68)
    try:
        g = json.load(open(HERE / "results.json"))
        gt_ok = sum(1 for r in g if r["file"].startswith("emotion_")
                    and r["emotion"] == TRUTH.get(Path(r["file"]).stem))
        gsec = [r["sec"] for r in g if not r["err"]]
        gavg = sum(gsec) / len(gsec) * 1000
    except Exception:
        gt_ok, gavg = "?", float("nan")
    print(f"  {'':22s}{'เวลา/ภาพ':>12s}   อ่านอารมณ์ถูก")
    print(f"  {'Gemini (cloud)':22s}{gavg:>9.0f} ms   {gt_ok}/6")
    print(f"  {'FER ในเครื่อง':22s}{avg_f:>9.0f} ms   {ok}/6  ({name})")
    print(f"  {'YOLO11-Pose ในเครื่อง':22s}{avg:>9.0f} ms   (ท่าทาง ไม่ใช่อารมณ์)")
    print(f"\n  เร็วขึ้น {gavg / max(avg_f + avg, 1):.0f} เท่า ถ้าใช้สองตัวนี้แทน")


if __name__ == "__main__":
    sys.exit(main())
