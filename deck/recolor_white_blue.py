"""Recolor the existing editable deck without rebuilding its layouts."""
from pathlib import Path
from copy import copy
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parent
SOURCE = BASE / "henjai.pptx"
TARGET = BASE / "henjai-white-blue.pptx"
PALETTE = {
    "0D0D0F": "FFFFFF",
    "1C1C22": "EAF2FF",
    "FFFFFF": "142D4E",
    "FFB020": "1565D8",
    "8A8A92": "52657D",
}
pattern = re.compile(rb'(<a:srgbClr\b[^>]*\bval=")([A-Fa-f0-9]{6})(")')

with zipfile.ZipFile(SOURCE) as src, zipfile.ZipFile(TARGET, "w") as dst:
    count = 0
    for item in src.infolist():
        data = src.read(item.filename)
        if re.fullmatch(r"ppt/slides/slide\d+\.xml", item.filename):
            data = pattern.sub(
                lambda m: m[1] + PALETTE.get(m[2].decode().upper(), m[2].decode()).encode() + m[3],
                data,
            )
            count += 1
        dst.writestr(copy(item), data)

with zipfile.ZipFile(SOURCE) as src, zipfile.ZipFile(TARGET) as dst:
    assert dst.testzip() is None
    assert src.namelist() == dst.namelist()
    for name in src.namelist():
        before, after = src.read(name), dst.read(name)
        if re.fullmatch(r"ppt/slides/slide\d+\.xml", name):
            ET.fromstring(after)
            # Removing color values must leave byte-identical text and layout XML.
            strip_colors = lambda b: pattern.sub(lambda m: m[1] + b"COLOR" + m[3], b)
            assert strip_colors(before) == strip_colors(after), name
        else:
            assert before == after, name
    assert count == 30
print(f"Created {TARGET}: 30 slides; text, layouts, images and notes unchanged.")

if "--preview-copies" in sys.argv:
    preview_dir = Path("/private/tmp/henjai-white-blue-preview")
    preview_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(TARGET) as src:
        presentation = src.read("ppt/presentation.xml")
        ids = re.findall(rb"<p:sldId\s[^>]*/>", presentation)
        assert len(ids) == 30
        for i, slide_id in enumerate(ids, 1):
            one = re.sub(rb"<p:sldIdLst>.*?</p:sldIdLst>", b"<p:sldIdLst>" + slide_id + b"</p:sldIdLst>", presentation)
            with zipfile.ZipFile(preview_dir / f"slide-{i:02}.pptx", "w") as dst:
                for item in src.infolist():
                    dst.writestr(copy(item), one if item.filename == "ppt/presentation.xml" else src.read(item.filename))
