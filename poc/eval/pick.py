"""ดึงภาพตัวเลือกมาเยอะ ๆ แล้วให้คนเลือกเอง — คำค้นอย่างเดียวเลือกให้ไม่ได้

    python eval/pick.py fetch     # โหลด 8 ตัวเลือก/ช่อง + ทำ contact sheet
    <เปิด eval/cand/*.png ดู แล้วแก้เลขใน eval/picks.json>
    python eval/pick.py apply     # ก๊อปตัวที่เลือกเข้า eval/img/ + manifest
"""
import json
import shutil
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).parent
CAND, IMG = HERE / "cand", HERE / "img"
PICKS = HERE / "picks.json"
UA = {"User-Agent": "cedt-rushhour-poc/0.1 (research)"}
N = 8

# ใช้ license ที่เอาไปใส่รายงานได้ (ตัด NC/ND ออก)
SLOTS = {
    "emotion": ["smiling face portrait", "crying person face", "angry face person",
                "surprised face person", "sad face portrait", "laughing people"],
    "body": ["people shaking hands", "two people hugging", "person with folded arms portrait",
             "woman waving hello", "people queue line waiting", "people talking together"],
    "env": ["coffee shop interior customers", "hospital waiting room", "train station platform crowd",
            "office meeting room people", "busy city sidewalk pedestrians", "supermarket aisle shopper"],
    "nolabel": ["empty corridor building", "staircase indoor", "construction barrier sidewalk",
                "wet floor caution sign", "empty classroom desks", "bicycles parked sidewalk"],
}


def search(q, n=N):
    url = "https://api.openverse.org/v1/images/?" + urllib.parse.urlencode(
        {"q": q, "license_type": "commercial,modification", "page_size": n, "mature": "false"})
    r = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30))
    return r.get("results", [])


def fetch(only: set[str] | None = None):
    CAND.mkdir(parents=True, exist_ok=True)
    f = CAND / "cand.json"
    meta = json.loads(f.read_text()) if (only and f.exists()) else {}
    for group, terms in SLOTS.items():
        for i, q in enumerate(terms):
            slot = f"{group}_{i}"
            if only and slot not in only:
                continue
            hits = []
            for k, it in enumerate(search(q)):
                try:
                    data = urllib.request.urlopen(
                        urllib.request.Request(it["url"], headers=UA), timeout=30).read()
                    (CAND / f"{slot}_{k}.jpg").write_bytes(data)
                    Image.open(CAND / f"{slot}_{k}.jpg").verify()
                except Exception:
                    (CAND / f"{slot}_{k}.jpg").unlink(missing_ok=True)
                    continue
                hits.append({"k": k, "title": it["title"], "license": it["license"],
                             "creator": it.get("creator", "?"), "source": it.get("foreign_landing_url", "")})
            meta[slot] = {"query": q, "group": group, "hits": hits}
            print(f"  {slot:12s} {len(hits)} ตัวเลือก  {q}")
            time.sleep(0.5)
    (CAND / "cand.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    sheets(meta)
    if not PICKS.exists():
        PICKS.write_text(json.dumps({s: 0 for s in meta}, indent=2))
    print(f"\nดู {CAND}/*.png แล้วแก้เลข 0-{N-1} ใน {PICKS}\nเสร็จแล้วรัน  python eval/pick.py apply")


def sheets(meta):
    """contact sheet ต่อกลุ่ม — แถวละช่อง คอลัมน์คือตัวเลือก 0..N-1"""
    for group in SLOTS:
        slots = [s for s in meta if meta[s]["group"] == group]
        W = TH = 190
        img = Image.new("RGB", (N * W, len(slots) * (TH + 24)), "white")
        d = ImageDraw.Draw(img)
        for r, slot in enumerate(slots):
            y = r * (TH + 24)
            d.text((4, y + TH + 6), f"{slot}: {meta[slot]['query']}", fill="black")
            for h in meta[slot]["hits"]:
                f = CAND / f"{slot}_{h['k']}.jpg"
                if not f.exists():
                    continue
                th = Image.open(f).convert("RGB")
                th.thumbnail((W - 8, TH - 8))
                img.paste(th, (h["k"] * W + 4, y + 4 + (TH - 8 - th.height) // 2))
                d.text((h["k"] * W + 6, y + 6), str(h["k"]), fill="red")
        img.save(CAND / f"{group}.png")


def apply():
    meta = json.loads((CAND / "cand.json").read_text())
    picks = json.loads(PICKS.read_text())
    IMG.mkdir(parents=True, exist_ok=True)
    manifest = []
    for slot, k in picks.items():
        src = CAND / f"{slot}_{k}.jpg"
        if not src.exists():
            print(f"  ข้าม {slot}: ไม่มีตัวเลือก {k}")
            continue
        shutil.copy(src, IMG / f"{slot}.jpg")
        hit = next((h for h in meta[slot]["hits"] if h["k"] == k), {})
        manifest.append({"file": f"{slot}.jpg", "group": meta[slot]["group"],
                         "query": meta[slot]["query"], **hit})
    (HERE / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"เข้า {IMG} แล้ว {len(manifest)} ภาพ — รัน  python eval/run.py")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "fetch"
    if cmd == "apply":
        apply()
    else:
        fetch(set(sys.argv[2:]) or None)
