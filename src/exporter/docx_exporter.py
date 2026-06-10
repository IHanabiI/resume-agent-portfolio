from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Iterable

from docx import Document
from docx.document import Document as DocumentObject
from docx.shared import Pt
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P


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


def markdown_to_template_docx_bytes(markdown_text: str, template_bytes: bytes) -> bytes:
    """Fill an existing DOCX with resume text while keeping its shell.

    This keeps sections, styles, headers/footers, tables, and embedded media in
    place as much as python-docx allows. It is intentionally conservative: image
    only paragraphs are preserved and not used as text targets, while existing
    text paragraphs are replaced in document order.
    """

    doc = Document(BytesIO(template_bytes))
    lines = _markdown_to_resume_lines(markdown_text)
    if not lines:
        return _docx_to_bytes(doc)

    targets = [paragraph for paragraph in _iter_paragraphs(doc) if paragraph.text.strip()]

    if not targets:
        for item in lines:
            _append_line(doc, item)
        return _docx_to_bytes(doc)

    line_index = 0
    for paragraph in targets:
        if line_index >= len(lines):
            _replace_paragraph_text(paragraph, "")
            continue
        _replace_paragraph_text(paragraph, lines[line_index]["text"])
        _apply_basic_markdown_style(paragraph, lines[line_index]["kind"])
        line_index += 1

    for item in lines[line_index:]:
        _append_line(doc, item)

    return _docx_to_bytes(doc)


def save_docx(markdown_text: str, output_dir: Path, filename: str = "tailored_resume.docx") -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    path.write_bytes(markdown_to_docx_bytes(markdown_text))
    return path


def _markdown_to_resume_lines(markdown_text: str) -> list[dict[str, str]]:
    lines: list[dict[str, str]] = []
    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        kind = "paragraph"
        text = line
        if line.startswith("### "):
            kind = "heading"
            text = line[4:].strip()
        elif line.startswith("## "):
            kind = "heading"
            text = line[3:].strip()
        elif line.startswith("# "):
            kind = "heading"
            text = line[2:].strip()
        elif line.startswith("- "):
            kind = "bullet"
            text = f"- {line[2:].strip()}"
        lines.append({"kind": kind, "text": text})
    return lines


def _iter_paragraphs(parent: DocumentObject | _Cell) -> Iterable[Paragraph]:
    if isinstance(parent, DocumentObject):
        parent_elm = parent.element.body
    else:
        parent_elm = parent._tc

    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            table = Table(child, parent)
            for row in table.rows:
                for cell in row.cells:
                    yield from _iter_paragraphs(cell)


def _paragraph_has_media(paragraph: Paragraph) -> bool:
    return bool(
        paragraph._p.xpath(".//w:drawing")
        or paragraph._p.xpath(".//w:pict")
        or paragraph._p.xpath(".//a:blip")
    )


def _replace_paragraph_text(paragraph: Paragraph, text: str) -> None:
    has_media = _paragraph_has_media(paragraph)
    for run in paragraph.runs:
        run.text = ""
    if text:
        if paragraph.runs and not has_media:
            paragraph.runs[0].text = text
        else:
            paragraph.add_run(text)


def _apply_basic_markdown_style(paragraph: Paragraph, kind: str) -> None:
    if not paragraph.runs:
        return
    if kind == "heading":
        paragraph.runs[-1].bold = True
    elif kind == "bullet":
        paragraph.runs[-1].bold = False


def _append_line(doc: DocumentObject, item: dict[str, str]) -> None:
    if item["kind"] == "heading":
        paragraph = doc.add_paragraph()
        run = paragraph.add_run(item["text"])
        run.bold = True
    elif item["kind"] == "bullet":
        doc.add_paragraph(item["text"], style="List Bullet")
    else:
        doc.add_paragraph(item["text"])


def _docx_to_bytes(doc: DocumentObject) -> bytes:
    stream = BytesIO()
    doc.save(stream)
    return stream.getvalue()
