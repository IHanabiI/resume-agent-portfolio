from __future__ import annotations

import re

from src.schemas import ResumeStructure


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
INTERNAL_MARKER_RE = re.compile(
    r"\b(?:L\d{3}|S\d{3}|line_id|section_id|alignment_plan|ResumeAlignmentPlan|ResumeStructure)\b",
    re.IGNORECASE,
)
CODE_FENCE_RE = re.compile(r"^\s*```(?:markdown|md|json)?\s*$", re.IGNORECASE)

FORBIDDEN_SECTION_TERMS = [
    "待确认信息",
    "待确认事项",
    "补充信息",
    "记忆库可用事实",
    "GitHub 相关证据",
    "GitHub证据",
    "证据来源",
    "事实来源",
    "改动说明",
    "优化说明",
    "岗位对齐计划",
    "程序预排草稿",
    "原简历结构骨架",
    "交付说明",
    "分析说明",
    "输出说明",
    "changelog",
    "evidence",
    "alignment_plan",
]

HARD_FORBIDDEN_SECTION_TERMS = [
    "待确认信息",
    "待确认事项",
    "记忆库可用事实",
    "GitHub 相关证据",
    "GitHub证据",
    "证据来源",
    "事实来源",
    "改动说明",
    "优化说明",
    "岗位对齐计划",
    "程序预排草稿",
    "原简历结构骨架",
    "交付说明",
    "分析说明",
    "输出说明",
    "changelog",
    "evidence",
    "alignment_plan",
]

FORBIDDEN_LINE_TERMS = [
    "上述内容缺少可验证来源",
    "未写入正式简历正文",
    "以下内容需要确认",
    "以下为改动说明",
    "以下为证据来源",
]


def guard_final_resume(
    markdown: str,
    original_structure: ResumeStructure | None = None,
) -> tuple[str, list[str]]:
    """Keep the exported resume as resume-only Markdown.

    The reference project separates resume.md from opener/changelog/evidence. This
    guard enforces the same boundary after model generation and fact checking.
    """
    warnings: list[str] = []
    text = (markdown or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return "", ["最终简历为空，请检查生成结果。"]

    text = _strip_wrapping_code_fence(text, warnings)
    original_titles = _original_titles(original_structure)
    lines = _remove_forbidden_sections(text.split("\n"), warnings, original_titles)
    lines = _clean_lines(lines, warnings)
    cleaned = _normalize_blank_lines(lines).strip()

    if original_structure:
        warnings.extend(_structure_warnings(cleaned, original_structure))

    return cleaned, _dedupe(warnings)[:30]


def _strip_wrapping_code_fence(text: str, warnings: list[str]) -> str:
    lines = text.split("\n")
    if len(lines) >= 2 and CODE_FENCE_RE.match(lines[0]) and lines[-1].strip() == "```":
        warnings.append("已移除最终简历外层 Markdown 代码块。")
        return "\n".join(lines[1:-1]).strip()
    return text


def _remove_forbidden_sections(
    lines: list[str],
    warnings: list[str],
    original_titles: set[str],
) -> list[str]:
    kept: list[str] = []
    skip_level: int | None = None

    for line in lines:
        heading = HEADING_RE.match(line.strip())
        if heading:
            level = len(heading.group(1))
            title = heading.group(2).strip()
            if skip_level is not None and level <= skip_level:
                skip_level = None
            if skip_level is None and _is_forbidden_title(title, original_titles):
                skip_level = level
                warnings.append(f"已从最终简历中移除辅助章节：{title}")
                continue

        if skip_level is not None:
            continue
        kept.append(line)

    return kept


def _clean_lines(lines: list[str], warnings: list[str]) -> list[str]:
    cleaned: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned.append("")
            continue
        if CODE_FENCE_RE.match(stripped) or stripped == "```":
            warnings.append("已移除最终简历中的代码块边界。")
            continue
        if any(term in stripped for term in FORBIDDEN_LINE_TERMS):
            warnings.append("已移除最终简历中的内部说明文字。")
            continue
        if INTERNAL_MARKER_RE.search(stripped):
            stripped = INTERNAL_MARKER_RE.sub("", stripped)
            stripped = re.sub(r"\s{2,}", " ", stripped).strip(" ：:，,")
            warnings.append("已清理最终简历中的内部定位标记。")
            if not stripped:
                continue

        heading = HEADING_RE.match(stripped)
        if heading and len(heading.group(1)) > 3:
            text = heading.group(2).strip()
            cleaned.append(f"- {text}")
            warnings.append(f"已将过深标题改为普通列表项：{text[:40]}")
            continue

        cleaned.append(stripped)
    return cleaned


def _normalize_blank_lines(lines: list[str]) -> str:
    normalized: list[str] = []
    blank = False
    for line in lines:
        if not line.strip():
            if not blank and normalized:
                normalized.append("")
            blank = True
            continue
        normalized.append(line.rstrip())
        blank = False
    return "\n".join(normalized)


def _structure_warnings(cleaned: str, original_structure: ResumeStructure) -> list[str]:
    warnings: list[str] = []
    cleaned_headings = {
        HEADING_RE.match(line.strip()).group(2).strip()
        for line in cleaned.splitlines()
        if HEADING_RE.match(line.strip())
    }
    for section in original_structure.sections:
        if not section.title or section.section_id == "S000":
            continue
        if section.title not in cleaned_headings:
            warnings.append(f"原简历章节可能缺失或被改名：{section.title}")
    return warnings


def _is_forbidden_title(title: str, original_titles: set[str]) -> bool:
    normalized = title.lower().replace(" ", "")
    hard_forbidden = any(term.lower().replace(" ", "") in normalized for term in HARD_FORBIDDEN_SECTION_TERMS)
    if hard_forbidden:
        return True
    if _normalize_title(title) in original_titles:
        return False
    return any(term.lower().replace(" ", "") in normalized for term in FORBIDDEN_SECTION_TERMS)


def _original_titles(original_structure: ResumeStructure | None) -> set[str]:
    if not original_structure:
        return set()
    return {_normalize_title(section.title) for section in original_structure.sections if section.title}


def _normalize_title(title: str) -> str:
    return title.lower().replace(" ", "").strip()


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result
