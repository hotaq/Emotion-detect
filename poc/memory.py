"""ความจำของ session — แยกออกมาเพราะ app.py ลาก streamlit มาด้วย เทสต์ไม่ได้."""
import difflib

MEM_CAP = 600        # ตัวอักษร — กันไม่ให้ context โตไม่มีเพดานตอนคุยยาว ๆ
MEM_RECENT = 5       # กี่ประโยคล่าสุดที่ส่งแบบเต็ม ที่เก่ากว่านี้ยุบลง summary


def is_dup(narrative: str, recent: list[str], thresh: float = 0.8) -> bool:
    return any(difflib.SequenceMatcher(None, narrative, r).ratio() > thresh for r in recent)


def push(recent: list[str], narrative: str) -> list[str]:
    return (recent + [narrative])[-MEM_RECENT:]


def memo(recent: list[str], summary: str = "") -> str:
    """context ที่ส่งกลับไปทุกรอบ: สรุปสะสม (เก่า) + ประโยคล่าสุดแบบเต็ม."""
    if not (recent or summary):
        return ""
    out = "\n--- ความจำของ session นี้ ---"
    if summary:
        out += f"\nสรุปที่ผ่านมา: {summary}"
    if recent:
        out += "\nที่เพิ่งพูดไปล่าสุด:\n- " + "\n- ".join(recent)
    return out + ("\nอย่าพูดเรื่องเดิมซ้ำ ให้บอกเฉพาะสิ่งที่เปลี่ยนไปหรือเพิ่งเห็นใหม่ "
                  "ถ้าไม่มีอะไรใหม่เลยให้ narrative_th เป็นค่าว่าง \"\"")
