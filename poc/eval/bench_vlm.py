"""VLM ตัวเล็กที่สั่งด้วย prompt ได้ — ถามอารมณ์ตรง ๆ ต่างจาก captioner ที่สั่งไม่ได้

    python eval/bench_vlm.py
"""
import time
from pathlib import Path

import torch
from PIL import Image

HERE = Path(__file__).parent
IMG = HERE / "img"
DEV = "mps" if torch.backends.mps.is_available() else "cpu"

TRUTH = {"emotion_0": "happy", "emotion_1": "sad", "emotion_2": "angry",
         "emotion_3": "surprise", "emotion_4": "sad", "emotion_5": "happy",
         "emotion_6": "angry"}
ASK = ("Look at the person's face. What emotion are they feeling? "
       "Answer with ONE word from: happy, sad, angry, fear, surprise, disgust, neutral.")


def score(cap, gt):
    c = cap.lower()
    return gt in c or {"surprise": "surprised", "angry": "anger",
                       "sad": "sadness", "happy": "smil"}.get(gt, "~~") in c


def run(name, gen):
    print("=" * 72); print(name); print("=" * 72)
    files = sorted(IMG.glob("emotion_*.jpg"))
    try:
        gen(Image.open(files[0]).convert("RGB"))                  # warmup
    except Exception as e:
        print(f"  รันไม่ได้: {e.__class__.__name__}: {str(e)[:120]}\n")
        return
    ok, tot = 0, 0.0
    for f in files:
        t = time.time()
        cap = gen(Image.open(f).convert("RGB"))
        dt = (time.time() - t) * 1000
        tot += dt
        gt = TRUTH[f.stem]
        good = score(cap, gt)
        ok += good
        print(f"  {f.stem:12s} {dt:6.0f} ms  เฉลย {gt:9s} {'✓' if good else '✗'}"
              f"\n{'':16s}-> {cap.strip()[:110]}")
    print(f"\n  เฉลี่ย {tot/len(files):.0f} ms/ภาพ   อ่านอารมณ์ถูก {ok}/{len(files)}\n")


def florence():
    from transformers import AutoModelForCausalLM, AutoProcessor
    mid = "microsoft/Florence-2-base"
    pr = AutoProcessor.from_pretrained(mid, trust_remote_code=True)
    m = AutoModelForCausalLM.from_pretrained(mid, trust_remote_code=True,
                                             dtype=torch.float32).to(DEV).eval()

    def gen(im):
        task = "<MORE_DETAILED_CAPTION>"
        x = pr(text=task, images=im, return_tensors="pt").to(DEV)
        with torch.no_grad():
            ids = m.generate(input_ids=x["input_ids"], pixel_values=x["pixel_values"],
                             max_new_tokens=80, num_beams=1, do_sample=False)
        return pr.batch_decode(ids, skip_special_tokens=True)[0]
    return gen


def qwen():
    from transformers import AutoModelForImageTextToText, AutoProcessor
    mid = "Qwen/Qwen3-VL-2B-Instruct"
    pr = AutoProcessor.from_pretrained(mid)
    m = AutoModelForImageTextToText.from_pretrained(mid, dtype=torch.float16).to(DEV).eval()

    def gen(im):
        msg = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": ASK}]}]
        txt = pr.apply_chat_template(msg, tokenize=False, add_generation_prompt=True)
        x = pr(text=[txt], images=[im], return_tensors="pt").to(DEV)
        with torch.no_grad():
            out = m.generate(**x, max_new_tokens=24, do_sample=False)
        return pr.batch_decode(out[:, x["input_ids"].shape[1]:], skip_special_tokens=True)[0]
    return gen


if __name__ == "__main__":
    print(f"อุปกรณ์ {DEV}\n")
    for name, loader in (("microsoft/Florence-2-base  <MORE_DETAILED_CAPTION>", florence),
                         ("Qwen/Qwen3-VL-2B-Instruct  ถามอารมณ์ตรง ๆ", qwen)):
        try:
            run(name, loader())
        except Exception as e:
            print("=" * 72); print(name); print("=" * 72)
            print(f"  โหลดไม่ได้: {e.__class__.__name__}: {str(e)[:150]}\n")
