"""Qwen3-VL-2B ในเครื่อง + SYSTEM_PROMPT ไทยตัวจริง — เทียบ Gemini ตรง ๆ

    python eval/bench_qwen_th.py
"""
import json
import re
import sys
import time
from pathlib import Path

import torch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core import SYSTEM_PROMPT

HERE = Path(__file__).parent
IMG = HERE / "img"
DEV = "mps" if torch.backends.mps.is_available() else "cpu"
MID = "Qwen/Qwen3-VL-2B-Instruct"

TRUTH = {"emotion_0": "happy", "emotion_1": "sad", "emotion_2": "angry",
         "emotion_3": "surprise", "emotion_4": "sad", "emotion_5": "happy",
         "emotion_6": "angry"}
THAI = re.compile(r"[฀-๿]")


def load():
    from transformers import AutoModelForImageTextToText, AutoProcessor
    pr = AutoProcessor.from_pretrained(MID)
    m = AutoModelForImageTextToText.from_pretrained(MID, dtype=torch.float16).to(DEV).eval()

    def gen(im, max_new=320):
        msg = [{"role": "user", "content": [
            {"type": "image"},
            {"type": "text", "text": SYSTEM_PROMPT +
             "\nAnalyze this image for a blind user. Return JSON only."}]}]
        txt = pr.apply_chat_template(msg, tokenize=False, add_generation_prompt=True)
        x = pr(text=[txt], images=[im], return_tensors="pt").to(DEV)
        with torch.no_grad():
            out = m.generate(**x, max_new_tokens=max_new, do_sample=False)
        return pr.batch_decode(out[:, x["input_ids"].shape[1]:], skip_special_tokens=True)[0]
    return gen


def parse(t):
    t = re.sub(r"^```(json)?|```$", "", t.strip(), flags=re.M).strip()
    try:
        return json.loads(t), True
    except Exception:
        return {"narrative_th": t[:200]}, False


def main():
    gen = load()
    files = sorted(IMG.glob("*.jpg"))
    gen(Image.open(files[0]).convert("RGB"), 32)                  # warmup
    rows, okjson, thai, emo_ok, emo_n = [], 0, 0, 0, 0
    for f in files:
        t = time.time()
        raw = gen(Image.open(f).convert("RGB"))
        dt = time.time() - t
        d, isjson = parse(raw)
        okjson += isjson
        n = (d.get("narrative_th") or "").strip()
        is_th = bool(THAI.search(n))
        thai += is_th
        lab = (d.get("emotion") or {}).get("label", "") if isinstance(d.get("emotion"), dict) else ""
        gt = TRUTH.get(f.stem)
        if gt:
            emo_n += 1
            emo_ok += lab == gt
        rows.append((f.stem, dt, isjson, is_th, lab, gt, n))
        print(f"  {f.stem:12s} {dt:5.1f}s  JSON {'✓' if isjson else '✗'}  ไทย {'✓' if is_th else '✗'}"
              f"  {lab:10s}{('เฉลย ' + gt) if gt else '':14s}\n{'':16s}{n[:96]}")
    N = len(rows)
    avg = sum(r[1] for r in rows) / N
    print(f"\n{'=' * 72}")
    print(f"  ภาพทั้งหมด        {N}")
    print(f"  เฉลี่ย            {avg:.2f} s/ภาพ   (Gemini 2.24 s)")
    print(f"  ตอบ JSON ถูกแบบ   {okjson}/{N}")
    print(f"  เขียนไทยจริง      {thai}/{N}")
    print(f"  อ่านอารมณ์ถูก     {emo_ok}/{emo_n}   (Gemini 4/6 · Qwen ถามคำเดียว 5/6)")
    json.dump([{"file": r[0], "sec": round(r[1], 2), "json": r[2], "thai": r[3],
                "emotion": r[4], "truth": r[5], "narrative_th": r[6]} for r in rows],
              open(HERE / "results_qwen_th.json", "w"), ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
