"""ดึงภาพทดสอบจาก Wikimedia Commons (เปิดฟรี มีระบุ license)

    python eval/fetch.py           # ดึงตาม QUERIES ด้านล่าง
"""
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).parent / "img"
UA = {"User-Agent": "cedt-rushhour-poc/0.1 (research)"}

# emotion/body ใช้ "หมวด" ที่คนจัดไว้ — แม่นกว่า full-text ที่คืนภาพวาด/รูปปั้นมา
# env/nolabel ใช้ search ต่อ เพราะรอบก่อนได้ภาพตรงดีอยู่แล้ว
SOURCES = {
    "emotion": ("cat", ["Smiling", "Crying", "Anger", "Surprise", "Sadness", "Laughing"]),
    "body": ("cat", ["Handshakes", "People pointing", "Crossed arms",
                     "Waving", "Queues", "People talking"]),
    "env": ("search", ["coffee shop interior people", "hospital waiting room",
                       "train station platform crowd", "meeting room presentation",
                       "busy street sidewalk", "supermarket aisle"]),
    "nolabel": ("search", ["empty corridor building", "staircase interior",
                           "construction site barrier", "wet floor sign",
                           "empty classroom", "parked bicycles sidewalk"]),
}

# หมวดพวกนี้ปนภาพวาด/รูปปั้น/ไอคอนเยอะ ต้องกรองทิ้ง ไม่งั้นวัดอารมณ์คนไม่ได้
BAD = ("drawing", "painting", "sketch", "engraving", "statue", "sculpture", "icon",
       "logo", "diagram", "map", "coat of arms", "emoji", "smiley", "cartoon",
       "illustration", "clipart", "clip art", "woodcut", "etching", "fresco", "mural")


def is_photo(title: str, ii: dict) -> bool:
    t = title.lower()
    return (ii.get("mime") == "image/jpeg"
            and ii.get("width", 0) >= 400
            and not any(w in t for w in BAD))


def get(url, tries=5):
    """Commons จำกัดอัตรา -> ถอยเป็นทวีคูณ"""
    for i in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read()
        except urllib.error.HTTPError as e:
            if e.code != 429 or i == tries - 1:
                raise
            time.sleep(5 * 3 ** i)   # 5s, 15s, 45s
    raise RuntimeError("unreachable")


COMMON = {"action": "query", "format": "json", "prop": "imageinfo",
          "iiprop": "url|mime|size|extmetadata", "iiurlwidth": 1024}


def candidates(kind: str, term: str, n: int = 30):
    """คืนเฉพาะรูปถ่ายจริง เรียงตามลำดับที่ Commons ให้มา"""
    q = dict(COMMON)
    if kind == "cat":
        q |= {"generator": "categorymembers", "gcmtitle": f"Category:{term}",
              "gcmtype": "file", "gcmlimit": n}
    else:
        q |= {"generator": "search", "gsrnamespace": 6,
              "gsrsearch": f"filetype:bitmap {term}", "gsrlimit": n}
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(q)
    for p in json.loads(get(url)).get("query", {}).get("pages", {}).values():
        ii = p["imageinfo"][0]
        if not is_photo(p["title"], ii):
            continue
        yield {"title": p["title"], "url": ii["thumburl"],
               "license": ii["extmetadata"].get("LicenseShortName", {}).get("value", "?"),
               "credit": ii["extmetadata"].get("Artist", {}).get("value", "?")[:120]}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    mf = OUT.parent / "manifest.json"
    done = {m["file"]: m for m in json.loads(mf.read_text())} if mf.exists() else {}
    manifest = []
    for group, (kind, terms) in SOURCES.items():
        for i, q in enumerate(terms):
            name = f"{group}_{i}.jpg"
            if (OUT / name).exists() and name in done:
                manifest.append(done[name])
                continue
            hit = next(iter(candidates(kind, q)), None)
            if hit is None and kind == "cat":     # บางหมวดมีแต่ subcategory ไม่มีไฟล์
                time.sleep(3)
                hit = next(iter(candidates("search", q + " people")), None)
            if hit is None:
                print(f"  ไม่เจอรูปถ่ายใน: {q}")
                continue
            (OUT / name).write_bytes(get(hit["url"]))
            time.sleep(3)                     # สุภาพกับ Commons
            manifest.append({"file": name, "group": group, "query": q, **hit})
            mf.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))   # เซฟทุกไฟล์ เผื่อ 429
            print(f"  {name:14s} {hit['license']:14s} {q}")
    mf.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"\nได้ {len(manifest)} ภาพ -> {OUT}")


if __name__ == "__main__":
    sys.exit(main())
