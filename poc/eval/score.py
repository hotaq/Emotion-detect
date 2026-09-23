"""สรุปคะแนนที่กรอกใน score.csv -> ตัวเลขตาม Plan Eval น.9"""
import csv
import sys
from pathlib import Path

rows = list(csv.DictReader((Path(__file__).parent / "score.csv").open(encoding="utf-8-sig")))
done = [r for r in rows if r["correct_0_1"].strip()]
if not done:
    sys.exit("ยังไม่ได้กรอกคะแนนใน score.csv")


def avg(rs, k):
    v = [float(r[k]) for r in rs if r[k].strip()]
    return sum(v) / len(v) if v else float("nan")


print(f"กรอกแล้ว {len(done)}/{len(rows)}\n")
print(f"{'กลุ่ม':<10} {'n':>3} {'Correctness':>12} {'Helpful':>8} {'Concise':>8} {'Halluc.':>9}")
for g in dict.fromkeys(r["group"] for r in done):
    rs = [r for r in done if r["group"] == g]
    print(f"{g:<10} {len(rs):>3} {avg(rs,'correct_0_1')*100:>11.0f}% "
          f"{avg(rs,'helpful_1_5'):>8.1f} {avg(rs,'concise_1_5'):>8.1f} "
          f"{avg(rs,'hallucination_0_1')*100:>8.0f}%")
print(f"{'รวม':<10} {len(done):>3} {avg(done,'correct_0_1')*100:>11.0f}% "
      f"{avg(done,'helpful_1_5'):>8.1f} {avg(done,'concise_1_5'):>8.1f} "
      f"{avg(done,'hallucination_0_1')*100:>8.0f}%")
