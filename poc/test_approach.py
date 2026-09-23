"""เตือนเฉพาะชิดจริง ๆ และพูดครั้งเดียว: python test_approach.py"""
import fast


def run(dists, side="ตรงหน้า"):
    fast.reset_history()
    out = []
    for m in dists:
        r = {"near_m": m, "near_side": side if m < fast.WARN_M else None,
             "obstacles": [], "persons": 0, "near": None}
        out.append(fast.phrase(r))
    return out

# เดินเข้าหากำแพง: เงียบตลอดจนชิด แล้วพูดครั้งเดียว แล้วเงียบแม้จะยังชิดอยู่
o = run([2.0, 1.5, 1.2, 0.9, 0.7, 0.45, 0.4, 0.3, 0.3])
assert o[:5] == [None] * 5, "ก่อนชิดต้องเงียบ"
assert o[5] and "ชิดตัวแล้ว" in o[5], "ชิดแล้วต้องเตือน"
assert o[6:] == [None] * 3, "ชิดค้างอยู่ ห้ามพูดซ้ำ"

# ยืนข้างกำแพงระยะ 0.6-0.8 (ใกล้แต่ไม่ชิด) -> เงียบทั้งหมด
assert run([0.7, 0.8, 0.6, 0.7, 0.8]) == [None] * 5, "ใกล้แต่ไม่ชิด ไม่เตือน"

# ชิด -> ถอยออกนิดเดียว (ยังไม่ถึง RELEASE) -> ชิดอีก = ห้ามพูดซ้ำ
o = run([0.4, 0.7, 0.4])
assert o == [o[0], None, None] and o[0], "ถอยไม่พ้น 0.9 ห้ามเตือนซ้ำ"

# ชิด -> ถอยห่างเกิน 0.9 -> ชิดอีก = เตือนใหม่ได้
o = run([0.4, 1.2, 0.4])
assert o[0] and o[1] is None and o[2], "ถอยพ้นแล้วกลับมาชิด ต้องเตือนใหม่"

# คนเดินเข้ามา / รถ -> เงียบ (สายนี้เตือนแค่ชนเท่านั้น)
fast.reset_history()
assert fast.phrase({"near_m": 2.0, "near_side": None, "persons": 1, "near": "ใกล้มาก",
                    "approaching": True, "obstacles": [{"name": "รถยนต์", "side": "ทางขวา",
                    "road": True, "big": .4}]}) is None, "อย่างอื่นไม่ต้องเตือน"

# บอกชื่อถ้า YOLO รู้จักของที่ชิด
fast.reset_history()
r = {"near_m": 0.4, "near_side": "ทางซ้าย", "persons": 0, "near": None,
     "obstacles": [{"name": "เก้าอี้", "side": "ทางซ้าย", "road": False, "big": .6}]}
assert fast.phrase(r) == "ระวัง มีเก้าอี้ทางซ้าย ชิดตัวแล้ว"
print("ok")
