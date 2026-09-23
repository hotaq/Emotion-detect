"""สร้างรูปประกอบเดค — รันครั้งเดียวก่อน build.py

    python deck/make_assets.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

OUT = Path(__file__).parent / "img"
EMOJI = "/System/Library/Fonts/Apple Color Emoji.ttc"
BASE = Path(__file__).parent.parent / "poc/eval/img/env_4.jpg"   # ถนนในเมือง คนเดิน


def sticker(char: str, name: str, size: int = 160):
    """เรนเดอร์อีโมจิเป็น PNG โปร่งใส — Apple Color Emoji รับเฉพาะบางขนาด 160 คมสุด"""
    f = ImageFont.truetype(EMOJI, 160)
    im = Image.new("RGBA", (180, 180), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((10, 10), char, font=f, embedded_color=True)
    im.crop(im.getbbox()).resize((size, size), Image.LANCZOS).save(OUT / f"{name}.png")


def vision_levels():
    """จำลองสิ่งที่คนแต่ละระดับมองเห็น — ใช้ภาพถนนจริงใบเดียวกันทั้งแถว"""
    src = Image.open(BASE).convert("RGB")
    w = min(src.width, src.height * 4 // 3)
    src = src.crop(((src.width - w) // 2, 0, (src.width + w) // 2, src.height))
    src = src.resize((420, 315), Image.LANCZOS)

    # (blur, ความสว่าง, คอนทราสต์) ไล่จากปกติไปตาบอดสนิท
    steps = [(0, 1.0, 1.0), (3, .95, .85), (14, .72, .5), (55, .62, .14), (0, 0, 0)]
    labels = ["ปกติ", "ระดับ 1-2", "ระดับ 3", "ระดับ 4", "ระดับ 5"]
    gap, pad = 18, 8
    sheet = Image.new("RGB", (5 * 420 + 4 * gap, 315 + pad * 2), "#0d0d0f")
    for i, (b, br, ct) in enumerate(steps):
        im = src.copy()
        if br == 0:
            im = Image.new("RGB", src.size, "#000000")
        else:
            if b:
                im = im.filter(ImageFilter.GaussianBlur(b))
            im = ImageEnhance.Brightness(im).enhance(br)
            im = ImageEnhance.Contrast(im).enhance(ct)
        sheet.paste(im, (i * (420 + gap), pad))
        if i >= 2:                                  # ขอบส้มเน้นกลุ่มเป้าหมาย
            ImageDraw.Draw(sheet).rectangle(
                [i * (420 + gap), pad, i * (420 + gap) + 419, pad + 314],
                outline="#FFB020", width=6)
    sheet.save(OUT / "vision_levels.png")
    return labels


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for char, name in [("📷", "ic_cam"), ("🙂", "ic_emotion"), ("🧍", "ic_body"),
                       ("🏙️", "ic_env"), ("🧠", "ic_fuse"), ("⚠️", "ic_priority"),
                       ("🔊", "ic_speak")]:
        sticker(char, name)
        print("  sticker", name)
    print("  vision_levels", vision_levels())
