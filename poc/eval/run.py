"""รัน pipeline กับภาพทดสอบ แล้วออกไฟล์ให้คนให้คะแนน (Plan Eval น.9)

    python eval/run.py                 # รันทุกภาพใน manifest
    python eval/run.py emotion         # เฉพาะกลุ่ม
"""
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image

import core

HERE = Path(__file__).parent
IMG = HERE / "img"


def main(group: str | None = None):
    manifest = json.loads((HERE / "manifest.json").read_text())
    if group:
        manifest = [m for m in manifest if m["group"] == group]
    key = core.os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        sys.exit("ใส่ GEMINI_API_KEY ใน .env ก่อน")

    rows = []
    for m in manifest:
        f = IMG / m["file"]
        if not f.exists():
            continue
        t0 = time.time()
        try:
            # mode=first: วัดคุณภาพคำบรรยายเดี่ยว ๆ ไม่เอา memory มาช่วย
            r = core.analyze(Image.open(f), key, core.MODELS[0], mode="first")
            err = ""
        except Exception as e:
            r, err = {}, f"{e.__class__.__name__}: {e}"[:120]
        rows.append({
            "file": m["file"], "group": m["group"], "query": m["query"],
            "sec": round(time.time() - t0, 1),
            "emotion": (r.get("emotion") or {}).get("label", ""),
            "conf": (r.get("emotion") or {}).get("confidence", ""),
            "narrative_th": (r.get("narrative_th") or "").strip(),
            "safety_th": (r.get("environment") or {}).get("safety_th", ""),
            "err": err,
        })
        print(f"{m['file']:14s} {rows[-1]['sec']:>4}s  {rows[-1]['emotion']:<10} "
              f"{rows[-1]['narrative_th'][:60] or rows[-1]['err']}")

    (HERE / "results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2))

    # ไฟล์ให้คนกรอกคะแนนเอง — ว่างไว้ 4 ช่องท้าย
    out = HERE / "score.csv"
    with out.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, ["file", "group", "query", "emotion", "narrative_th",
                                "correct_0_1", "helpful_1_5", "concise_1_5", "hallucination_0_1"])
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in w.fieldnames})

    ok = [r for r in rows if not r["err"]]
    print(f"\n{len(ok)}/{len(rows)} สำเร็จ · เฉลี่ย {sum(r['sec'] for r in ok)/max(len(ok),1):.1f}s")
    print(f"กรอกคะแนนที่ {out}  แล้วรัน  python eval/score.py")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
