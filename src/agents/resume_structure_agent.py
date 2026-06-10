from __future__ import annotations

import hashlib
import re

from src.schemas import ResumeLine, ResumeSection, ResumeStructure


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
BULLET_RE = re.compile(r"^(\s*)([-*+•]|\d+[.、)])\s+(.+?)\s*$")


def parse_resume_structure(resume_text: str) -> ResumeStructure:
    resume_hash = hashlib.md5(resume_text.encode("utf-8", errors="ignore")).hexdigest()
    sections: list[ResumeSection] = []
    lines: list[ResumeLine] = []
    current = ResumeSection(section_id="S000", title="未命名区块", heading_level=0)
    sections.append(current)

    logical_index = 0
    for raw in resume_text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        text = raw.rstrip()
        if not text.strip():
            continue
        logical_index += 1
        heading = HEADING_RE.match(text.strip())
        bullet = BULLET_RE.match(text)
        line_id = f"L{logical_index:03d}"

        if heading:
            level = len(heading.group(1))
            title = heading.group(2).strip()
            section_id = f"S{len(sections):03d}"
            current = ResumeSection(section_id=section_id, title=title, heading_level=level)
            sections.append(current)
            line = ResumeLine(
                line_id=line_id,
                text=text.strip(),
                line_type="heading",
                heading_level=level,
                section_id=section_id,
                section_title=title,
            )
        elif bullet:
            line = ResumeLine(
                line_id=line_id,
                text=text.strip(),
                line_type="bullet",
                heading_level=0,
                section_id=current.section_id,
                section_title=current.title,
            )
        else:
            line = ResumeLine(
                line_id=line_id,
                text=text.strip(),
                line_type="paragraph",
                heading_level=0,
                section_id=current.section_id,
                section_title=current.title,
            )
        current.lines.append(line)
        lines.append(line)

    sections = [section for section in sections if section.lines or section.section_id == "S000"]
    non_empty_sections = [section for section in sections if section.lines]
    return ResumeStructure(
        resume_hash=resume_hash,
        summary=f"识别到 {len(non_empty_sections)} 个章节、{len(lines)} 行有效内容。",
        sections=non_empty_sections,
        lines=lines,
    )
