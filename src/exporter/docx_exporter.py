from __future__ import annotations

from io import BytesIO
from pathlib import Path

from docx import Document
from docx.shared import Pt


def markdown_to_docx_bytes(markdown_text: str) -> bytes:
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Microsoft YaHei"
    style.font.size = Pt(10.5)

    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if not line:
            doc.add_paragraph("")
            continue
        if line.startswith("# "):
            doc.add_heading(line[2:].strip(), level=1)
        elif line.startswith("## "):
            doc.add_heading(line[3:].strip(), level=2)
        elif line.startswith("### "):
            doc.add_heading(line[4:].strip(), level=3)
        elif line.startswith("- "):
            doc.add_paragraph(line[2:].strip(), style="List Bullet")
        elif line.startswith("|"):
            doc.add_paragraph(line)
        else:
            doc.add_paragraph(line)

    stream = BytesIO()
    doc.save(stream)
    return stream.getvalue()


def save_docx(markdown_text: str, output_dir: Path, filename: str = "tailored_resume.docx") -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    path.write_bytes(markdown_to_docx_bytes(markdown_text))
    return path

