from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
}


def main() -> None:
    path = Path(r"C:\Users\25701\Desktop\YOLO6D_FastMoving_详细公式版_扩展完整版讲义.docx")
    root = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml"))
    current_heading = ""
    index = 0
    for para in root.findall(".//w:p", NS):
        normal_text = "".join(t.text or "" for t in para.findall(".//w:t", NS)).strip()
        maths = para.findall(".//m:oMath", NS)
        if normal_text and len(normal_text) < 80 and not maths:
            current_heading = normal_text
        for math in maths:
            math_text = "".join(t.text or "" for t in math.findall(".//m:t", NS)).strip()
            if not math_text:
                continue
            index += 1
            if index <= 260:
                print(f"{index:03d} | {current_heading} | {math_text}")


if __name__ == "__main__":
    main()
