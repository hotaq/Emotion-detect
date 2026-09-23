"""ลองโมเดล image-to-caption จริง ๆ กับชุดทดสอบ 24 ภาพ

    python eval/bench_caption.py
"""
import sys
import time
from pathlib import Path

import torch
from PIL import Image

HERE = Path(__file__).parent
IMG = HERE / "img"
DEV = "mps" if torch.backends.mps.is_available() else "cpu"

PICK = ["emotion_0", "emotion_2", "emotion_4", "body_0", "body_2",
        "env_0", "env_2", "nolabel_3"]
WHAT = {"emotion_0": "หญิงยิ้ม", "emotion_2": "ชายหน้าโกรธจัด", "emotion_4": "เด็กหญิงหน้าเศร้า",
        "body_0": "คนสองคนจับมือกัน", "body_2": "หญิงยืนกอดอก",
        "env_0": "ร้านกาแฟมีลูกค้า", "env_2": "ชานชาลารถไฟคนแน่น", "nolabel_3": "ป้ายเตือนพื้นเปียก"}


def run(name, loader):
    try:
        gen = loader()
    except Exception as e:
        print(f"  โหลดไม่ได้: {e.__class__.__name__}: {str(e)[:80]}")
        return
    gen(Image.open(IMG / f"{PICK[0]}.jpg").convert("RGB"))        # warmup
    tot = 0.0
    for k in PICK:
        im = Image.open(IMG / f"{k}.jpg").convert("RGB")
        t = time.time()
        cap = gen(im)
        dt = (time.time() - t) * 1000
        tot += dt
        print(f"  {k:12s} {dt:6.0f} ms  ภาพคือ[{WHAT[k]}]\n{'':16s}-> {cap}")
    print(f"  เฉลี่ย {tot/len(PICK):.0f} ms/ภาพ\n")


def git_base():
    from transformers import AutoModelForCausalLM, AutoProcessor
    pr = AutoProcessor.from_pretrained("microsoft/git-base")
    m = AutoModelForCausalLM.from_pretrained("microsoft/git-base").to(DEV).eval()

    def gen(im):
        px = pr(images=im, return_tensors="pt").pixel_values.to(DEV)
        with torch.no_grad():
            ids = m.generate(pixel_values=px, max_length=40)
        return pr.batch_decode(ids, skip_special_tokens=True)[0]
    return gen


def blip():
    from transformers import BlipForConditionalGeneration, BlipProcessor
    pr = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
    m = BlipForConditionalGeneration.from_pretrained(
        "Salesforce/blip-image-captioning-base").to(DEV).eval()

    def gen(im):
        with torch.no_grad():
            ids = m.generate(**pr(im, return_tensors="pt").to(DEV), max_new_tokens=40)
        return pr.decode(ids[0], skip_special_tokens=True)
    return gen


if __name__ == "__main__":
    print(f"อุปกรณ์ {DEV}\n")
    for name, loader in (("microsoft/git-base (ตามหน้า HF)", git_base),
                         ("Salesforce/blip-image-captioning-base", blip)):
        print("=" * 72)
        print(name)
        print("=" * 72)
        run(name, loader)
