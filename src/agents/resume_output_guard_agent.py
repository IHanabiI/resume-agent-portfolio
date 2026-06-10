from __future__ import annotations

import re

from src.schemas import ResumeStructure


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
BULLET_RE = re.compile(r"^(\s*)([-*+•]|\d+[.、)])\s+(.+?)\s*$")
INTERNAL_MARKER_RE = re.compile(
    r"\b(?:L\d{3}|S\d{3}|line_id|section_id|alignment_plan|ResumeAlignmentPlan|ResumeStructure)\b",
    re.IGNORECASE,
)
CODE_FENCE_RE = re.compile(r"^\s*```(?:markdown|md|json)?\s*$", re.IGNORECASE)
DATE_RE = re.compile(r"(\d{4}[./年-]\d{1,2}|20\d{2}|19\d{2}|至今|present)", re.IGNORECASE)

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

        if heading and len(heading.group(1)) == 3:
            text = heading.group(2).strip()
            if _looks_like_detail_heading(text):
                cleaned.append(f"- {text}")
                warnings.append(f"已将疑似职责/成果标题改为普通列表项：{text[:40]}")
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
    original_sections = _original_section_signatures(original_structure)
    final_sections = _markdown_section_signatures(cleaned)
    if not original_sections:
        return warnings

    original_titles = [section["title"] for section in original_sections]
    final_titles = [section["title"] for section in final_sections]
    original_norms = [_normalize_title(title) for title in original_titles]
    final_norms = [_normalize_title(title) for title in final_titles]
    final_norm_set = set(final_norms)
    original_norm_set = set(original_norms)

    missing = [title for title in original_titles if _normalize_title(title) not in final_norm_set]
    added = [title for title in final_titles if _normalize_title(title) not in original_norm_set]
    if missing:
        warnings.append("原简历章节可能缺失或被改名：" + "、".join(missing[:8]))
    if added:
        warnings.append("最终简历出现原文没有的章节：" + "、".join(added[:8]))

    expected_order = [title for title in original_norms if title in final_norm_set]
    actual_order = [title for title in final_norms if title in original_norm_set]
    if expected_order and actual_order and expected_order != actual_order:
        warnings.append("原简历章节顺序可能被改变；参考项目要求顶层章节顺序冻结。")

    original_by_title = {section["norm_title"]: section for section in original_sections}
    final_by_title = {section["norm_title"]: section for section in final_sections}
    for norm_title in original_norm_set & final_norm_set:
        original = original_by_title[norm_title]
        final = final_by_title[norm_title]
        if original["heading_level"] != final["heading_level"]:
            warnings.append(
                f"章节标题层级可能被改变：{original['title']} "
                f"从 H{original['heading_level']} 变为 H{final['heading_level']}"
            )
        original_bullets = original["bullet_count"]
        final_bullets = final["bullet_count"]
        if original_bullets and original_bullets != final_bullets:
            warnings.append(
                f"章节列表数量发生变化：{original['title']} "
                f"原 {original_bullets} 条，现 {final_bullets} 条；参考项目要求列表条目一行一条且数量尽量冻结。"
            )
    return warnings


def _original_section_signatures(original_structure: ResumeStructure) -> list[dict[str, int | str]]:
    sections: list[dict[str, int | str]] = []
    for section in original_structure.sections:
        if not section.title or section.section_id == "S000" or section.heading_level <= 1:
            continue
        sections.append(
            {
                "title": section.title,
                "norm_title": _normalize_title(section.title),
                "heading_level": section.heading_level,
                "bullet_count": sum(1 for line in section.lines if line.line_type == "bullet"),
            }
        )
    return sections


def _markdown_section_signatures(markdown: str) -> list[dict[str, int | str]]:
    sections: list[dict[str, int | str]] = []
    current: dict[str, int | str] | None = None
    for raw in markdown.splitlines():
        line = raw.strip()
        if not line:
            continue
        heading = HEADING_RE.match(line)
        if heading:
            title = heading.group(2).strip()
            current = {
                "title": title,
                "norm_title": _normalize_title(title),
                "heading_level": len(heading.group(1)),
                "bullet_count": 0,
            }
            sections.append(current)
            continue
        if current and BULLET_RE.match(line):
            current["bullet_count"] = int(current["bullet_count"]) + 1
    return [section for section in sections if int(section["heading_level"]) > 1]


def _is_forbidden_title(title: str, original_titles: set[str]) -> bool:
    normalized = title.lower().replace(" ", "")
    if _normalize_title(title) in original_titles:
        return False
    hard_forbidden = any(term.lower().replace(" ", "") in normalized for term in HARD_FORBIDDEN_SECTION_TERMS)
    if hard_forbidden:
        return True
    return any(term.lower().replace(" ", "") in normalized for term in FORBIDDEN_SECTION_TERMS)


def _looks_like_detail_heading(text: str) -> bool:
    if len(text) < 16:
        return False
    if DATE_RE.search(text):
        return False
    action_prefixes = (
        "负责",
        "参与",
        "主导",
        "设计",
        "输出",
        "完成",
        "推动",
        "协作",
        "整理",
        "分析",
        "优化",
        "实现",
        "搭建",
        "基于",
        "通过",
        "使用",
    )
    result_terms = ("提升", "降低", "增长", "上线", "交付", "验证", "反馈", "完成", "产出")
    has_sentence_punctuation = any(mark in text for mark in ("，", "。", "；", "：", ",", ";", ":"))
    starts_with_action = text.startswith(action_prefixes)
    has_result = any(term in text for term in result_terms)
    return starts_with_action or (len(text) >= 24 and (has_sentence_punctuation or has_result))


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
