from __future__ import annotations

import re


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
BULLET_RE = re.compile(r"^(\s*)([-*+•‣▪]|\d+[.、])\s+(.+?)\s*$")


def normalize_resume_project_blocks(markdown_text: str) -> str:
    """Normalize resume bullets for skill sections and project blocks."""
    lines = []
    in_project_section = False
    project_section_level = 0
    in_project_item = False
    skip_project_item = False
    in_skill_section = False
    skill_section_level = 0

    for raw in (markdown_text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = _normalize_bullet_marker(raw.rstrip())
        stripped = line.strip()
        if not stripped:
            if not skip_project_item:
                lines.append("")
            continue

        heading = HEADING_RE.match(stripped)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2).strip()
            if in_project_section and level <= project_section_level:
                in_project_section = False
                project_section_level = 0
                in_project_item = False
                skip_project_item = False
            if in_skill_section and level <= skill_section_level:
                in_skill_section = False
                skill_section_level = 0

            if _is_project_section_title(title):
                in_project_section = True
                project_section_level = level
                in_project_item = False
                skip_project_item = False
            elif in_project_section and level == project_section_level + 1:
                in_project_item = True
                skip_project_item = _is_forbidden_project_title(title)

            if _is_skill_section_title(title):
                in_skill_section = True
                skill_section_level = level

            if skip_project_item:
                continue
            lines.append(stripped)
            continue

        if in_project_section and skip_project_item:
            if _looks_like_project_header_bullet(stripped):
                bullet = BULLET_RE.match(stripped)
                text = _clean_project_heading_text(bullet.group(3) if bullet else stripped)
                if _is_forbidden_project_title(text):
                    continue
                lines.append(f"### {text}")
                in_project_item = True
                skip_project_item = False
            continue

        if in_project_section and _looks_like_project_header_bullet(stripped):
            bullet = BULLET_RE.match(stripped)
            text = _clean_project_heading_text(bullet.group(3) if bullet else stripped)
            skip_project_item = _is_forbidden_project_title(text)
            if skip_project_item:
                in_project_item = False
                continue
            lines.append(f"### {text}")
            in_project_item = True
            continue

        if skip_project_item:
            continue

        if in_project_section and in_project_item and _looks_like_project_detail_bullet(stripped):
            bullet = BULLET_RE.match(stripped)
            text = _clean_project_detail_text(bullet.group(3) if bullet else stripped)
            if text:
                lines.append(f"- {text}")
            continue

        if in_project_section and in_project_item and _looks_like_project_detail_paragraph(stripped):
            text = _clean_project_detail_text(stripped)
            if text:
                lines.append(f"- {text}")
            continue

        if in_skill_section and _looks_like_skill_detail_line(stripped):
            bullet = BULLET_RE.match(stripped)
            text = _clean_skill_text(bullet.group(3) if bullet else stripped)
            if text:
                lines.append(f"- {text}")
            continue

        lines.append(line.rstrip())

    return _normalize_blank_lines(lines).strip()


def _normalize_bullet_marker(line: str) -> str:
    stripped = line.lstrip()
    if stripped.startswith(("• ", "‣ ", "▪ ")):
        indent = line[: len(line) - len(stripped)]
        return f"{indent}- {stripped[2:].strip()}"
    return line


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


def _is_project_section_title(title: str) -> bool:
    normalized = title.lower().replace(" ", "")
    return any(term in normalized for term in ("项目经历", "项目经验", "项目实践", "项目作品", "project"))


def _is_skill_section_title(title: str) -> bool:
    normalized = title.lower().replace(" ", "")
    return any(term in normalized for term in ("专业技能", "技能", "技能特长", "技术栈", "核心能力", "skills"))


def _is_forbidden_project_title(title: str) -> bool:
    normalized = title.lower().replace(" ", "")
    forbidden_terms = (
        "gameplayanalyzeragent",
        "游戏源文件玩法拆解工作流",
        "玩法拆解工作流",
    )
    return any(term in normalized for term in forbidden_terms)


def _looks_like_project_header_bullet(line: str) -> bool:
    bullet = BULLET_RE.match(line)
    if not bullet:
        return False
    text = _clean_project_heading_text(bullet.group(3))
    if not text or len(text) < 6 or len(text) > 180:
        return False
    if HEADING_RE.match(text) or _starts_with_detail_or_action(text):
        return False

    separator_index = _first_project_separator_index(text)
    if separator_index == -1 or separator_index > 36:
        return False

    lead = text[:separator_index].strip(" -/|｜:：·")
    if not lead or len(lead) > 28 or _is_detail_label(lead):
        return False

    return _has_project_header_signal(text, lead)


def _looks_like_project_detail_bullet(line: str) -> bool:
    bullet = BULLET_RE.match(line)
    if not bullet:
        return False
    text = _clean_project_detail_text(bullet.group(3))
    if not text or len(text) < 4:
        return False
    return not _looks_like_project_header_bullet(line)


def _looks_like_skill_detail_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if HEADING_RE.match(stripped):
        return False
    return len(stripped) >= 3


def _looks_like_project_detail_paragraph(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if HEADING_RE.match(stripped) or BULLET_RE.match(stripped):
        return False
    if _is_project_section_title(stripped):
        return False
    return len(stripped) >= 4


def _clean_project_heading_text(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^[-*+•‣▪]\s+", "", cleaned).strip()
    cleaned = re.sub(r"^\*\*(.+?)\*\*$", r"\1", cleaned).strip()
    cleaned = cleaned.replace("**", "").strip()
    return cleaned.rstrip("。；;")


def _clean_project_detail_text(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^[-*+•‣▪]\s+", "", cleaned).strip()
    cleaned = cleaned.replace("**", "").strip()
    return cleaned


def _clean_skill_text(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^[-*+•‣▪]\s+", "", cleaned).strip()
    cleaned = cleaned.replace("**", "").strip()
    return cleaned


def _first_project_separator_index(text: str) -> int:
    indexes = [text.find(sep) for sep in ("：", ":", " - ", " / ", " | ", "｜", " · ", " — ") if sep in text]
    return min(indexes) if indexes else -1


def _has_project_header_signal(text: str, lead: str) -> bool:
    lowered = text.lower()
    if re.search(r"[A-Za-z][A-Za-z0-9_-]{1,}", lead):
        return True
    if any(mark in text for mark in ("《", "》")):
        return True
    if any(term in lowered for term in ("github", "demo", "unity", "godot", "mod", "agent", "streamlit", "langgraph")):
        return True
    if any(term in text for term in ("项目", "系统", "平台", "工具", "小程序", "已发布", "已打包", "上线")):
        return True
    return len(lead) <= 12 and not _is_detail_label(lead)


def _starts_with_detail_or_action(text: str) -> bool:
    prefixes = (
        "独立设计",
        "设计",
        "使用",
        "面向",
        "围绕",
        "完成",
        "实现",
        "搭建",
        "负责",
        "参与",
        "主导",
        "推动",
        "输出",
        "抽取",
        "识别",
        "整理",
        "分析",
        "优化",
        "通过",
        "基于",
        "默认",
        "预留",
        "后续",
        "自动扫描",
        "在",
        "接入",
        "编写",
        "维护",
        "验证",
        "测试",
        "支持",
        "协作",
        "开发",
        "项目定位",
        "核心玩法",
        "项目成果",
        "主要成果",
        "技术实现",
        "规则实现",
        "文档输出",
        "玩法设计",
        "系统设计",
        "工作内容",
        "职责",
        "成果",
        "结果",
    )
    return text.startswith(prefixes)


def _is_detail_label(text: str) -> bool:
    label = text.strip().lower()
    detail_labels = {
        "玩法设计",
        "系统设计",
        "技术实现",
        "规则实现",
        "文档输出",
        "项目定位",
        "项目成果",
        "主要成果",
        "核心职责",
        "工作内容",
        "职责",
        "成果",
        "结果",
        "背景",
        "目标",
        "亮点",
    }
    return label in detail_labels or label.endswith(("设计", "实现", "输出", "职责", "成果"))
