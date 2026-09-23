"""หารูปสำหรับเดคจาก Openverse — ดึงตัวเลือกมาเยอะแล้วเลือกเอง

    python deck/find_img.py                 # ดึงตัวเลือก + ทำ contact sheet
    python deck/find_img.py apply           # ก๊อปตัวที่เลือกใน picks.json เข้า deck/img/
"""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "poc/eval"))
from PIL import Image, ImageDraw
from pick import search                     # ใช้ตัวค้น Openverse เดิม (กรอง license แล้ว)

HERE = Path(__file__).parent
CAND, IMG = HERE / "cand", HERE / "img"
PICKS = HERE / "picks.json"
N = 8

SLOTS = {
    "scene_talk": "two people sitting talking",
    "pain_face":  "portrait face close up person",
    "pain_body":  "group of people standing talking together",
    "pain_env":   "crowded train station commuters walking",
}


def fetch(only=None):
    CAND.mkdir(parents=True, exist_ok=True)
    f0 = CAND / "cand.json"
    meta = json.loads(f0.read_text()) if (only and f0.exists()) else {}
    for slot, q in SLOTS.items():
        if only and slot not in only:
            continue
        hits = []
        for k, it in enumerate(search(q, N)):
            f = CAND / f"{slot}_{k}.jpg"
            try:
                import urllib.request
                f.write_bytes(urllib.request.urlopen(
                    urllib.request.Request(it["url"], headers={"User-Agent": "cedt-poc/0.1"}),
                    timeout=30).read())
                Image.open(f).verify()
            except Exception:
                f.unlink(missing_ok=True)
                continue
            hits.append({"k": k, "title": it["title"], "license": it["license"],
                         "creator": it.get("creator", "?"),
                         "source": it.get("foreign_landing_url", "")})
        meta[slot] = {"query": q, "hits": hits}
        print(f"  {slot:12s} {len(hits)} ตัวเลือก")
    (CAND / "cand.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))

    W = TH = 200
    sheet = Image.new("RGB", (N * W, len(SLOTS) * (TH + 24)), "white")
    d = ImageDraw.Draw(sheet)
    for r, slot in enumerate(SLOTS):
        if slot not in meta:
            continue
        y = r * (TH + 24)
        d.text((4, y + TH + 6), f"{slot}: {SLOTS[slot]}", fill="black")
        for h in meta[slot]["hits"]:
            f = CAND / f"{slot}_{h['k']}.jpg"
            if not f.exists():
                continue
            th = Image.open(f).convert("RGB")
            th.thumbnail((W - 8, TH - 8))
            sheet.paste(th, (h["k"] * W + 4, y + 4 + (TH - 8 - th.height) // 2))
            d.text((h["k"] * W + 6, y + 6), str(h["k"]), fill="red")
    sheet.save(CAND / "sheet.png")
    if not PICKS.exists():
        PICKS.write_text(json.dumps({s: 0 for s in SLOTS}, indent=2))
    print(f"\nดู {CAND}/sheet.png แล้วแก้เลขใน {PICKS}")


def apply():
    meta = json.loads((CAND / "cand.json").read_text())
    picks = json.loads(PICKS.read_text())
    credits = []
    for slot, k in picks.items():
        src = CAND / f"{slot}_{k}.jpg"
        if not src.exists():
            print(f"  ข้าม {slot}: ไม่มีตัวเลือก {k}")
            continue
        shutil.copy(src, IMG / f"{slot}.jpg")
        hit = next((h for h in meta[slot]["hits"] if h["k"] == k), {})
        credits.append({"file": f"{slot}.jpg", **hit})
        print(f"  {slot}.jpg  {hit.get('license')}  {hit.get('title', '')[:40]}")
    (HERE / "credits.json").write_text(json.dumps(credits, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "apply":
        apply()
    else:
        fetch(set(sys.argv[1:]) or None)
