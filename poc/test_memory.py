"""รัน: python test_memory.py"""
from memory import MEM_CAP, MEM_RECENT, is_dup, memo, push

A = "คุณอยู่ในห้องเรียน มีโต๊ะและกระดานดำข้างหน้า บรรยากาศเงียบสงบ"

# กันพูดซ้ำ
assert not is_dup(A, [])
assert is_dup(A, [A])
assert is_dup("คุณอยู่ในห้องเรียน มีโต๊ะและกระดานดำข้างหน้า บรรยากาศสงบ", [A])   # เกือบเหมือน
assert not is_dup("มีคนเดินเข้ามาทางซ้าย ระวังมีเก้าอี้ขวางอยู่", [A])            # เรื่องใหม่
assert is_dup(A, ["เรื่องอื่นไปเลย", A])                                        # เทียบทุกตัว

# recent ไม่โตเกินเพดาน และเก็บตัวใหม่สุดไว้
r = []
for i in range(50):
    r = push(r, f"ประโยคที่ {i}")
assert len(r) == MEM_RECENT and r[-1] == "ประโยคที่ 49"

# คุยยาวแค่ไหน prompt ก็ไม่บวม
assert memo([], "") == ""
big = memo(r, "x" * MEM_CAP)
assert len(big) < MEM_CAP + 600, len(big)
assert "x" * MEM_CAP in big and "ประโยคที่ 49" in big
print("ok")

# --- prompt ปรับตามการเปลี่ยนของภาพ ---
import numpy as np

from core import MODE_PROMPT, change_score


def mode_for(change, n=1, still=0.02, scene=0.18, alert=0.45):
    if n and change < still:
        return "skip"
    return ("first" if not n else "alert" if change >= alert
            else "scene" if change >= scene else "delta")


flat = np.zeros((36, 64), "uint8")
assert change_score(flat, flat) == 0.0
assert change_score(flat, np.full((36, 64), 255, "uint8")) == 1.0

assert mode_for(0.0) == "skip"                      # ภาพนิ่ง -> ไม่ยิง Gemini
assert mode_for(0.05) == "delta"                    # ขยับนิด -> บอกเฉพาะที่เปลี่ยน
assert mode_for(0.30) == "scene"                    # เปลี่ยนฉาก -> บรรยายใหม่
assert mode_for(0.60) == "alert"                    # กะทันหัน -> เตือนก่อน
assert mode_for(0.0, n=0) == "first"                # รอบแรกพูดเสมอ
assert set(MODE_PROMPT) == {"first", "delta", "scene", "alert"}
print("ok")

# เกณฑ์ต้องมาจาก noise ของกล้อง ไม่ใช่ตัวเลขตายตัว
from core import thresholds

assert thresholds(0.02) == (0.05, 0.18, 0.44)      # กล้องนิ่ง = ค่าที่จูนมือไว้เดิม
shaky = thresholds(0.08)                           # ถือเดิน noise สูง -> เกณฑ์ขยับตาม
assert shaky[0] > 0.18 and shaky < (1, 1, 1)
assert thresholds(0.02) < thresholds(0.03)         # noise มากขึ้น เกณฑ์ต้องสูงขึ้น
print("ok")
