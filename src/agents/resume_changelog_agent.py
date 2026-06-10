from __future__ import annotations

import difflib
import re


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
FILL_RE = re.compile(r"\[请填写[:：]([^\]]+)\]")
CONFIRM_RE = re.compile(r"\[需用户确认[:：]?([^\]]*)\]")


def build_diff_changelog(
    original_markdown: str,
    final_markdown: str,
    guard_warnings: list[str] | None = None,
) -> str:
    original_lines = _meaningful_lines(original_markdown)
    final_lines = _meaningful_lines(final_markdown)
    changes = _line_diff(original_lines, final_lines)
    structure_notes = _structure_notes(original_lines, final_lines, guard_warnings or [])
    fill_items = _extract_unique(FILL_RE, final_markdown)
    confirm_items = _extract_unique(CONFIRM_RE, final_markdown)

    lines = ["# 改动说明 · 对比原始简历", ""]
    lines.append("> 本说明由程序基于原始简历与最终简历的真实文本差异生成，只记录最终文件中实际发生的变化。")

    if changes:
        lines.extend(["", "## 已发生的正文变化"])
        lines.extend(f"{idx}. {item}" for idx, item in enumerate(changes[:24], start=1))
        if len(changes) > 24:
            lines.append(f"25. 另有 {len(changes) - 24} 处细节变化未展开，建议在上方简历编辑区核对。")
    else:
        lines.extend(
            [
                "",
                "## 本岗位未改动正文",
                "- 最终简历与原始简历在可比较文本层面没有差异；系统未编造改动记录。",
            ]
        )

    if structure_notes:
        lines.extend(["", "## 结构、格式与计划执行校验"])
        lines.extend(f"- {item}" for item in structure_notes[:12])

    if fill_items:
        lines.extend(["", "## 需要用户回填"])
        lines.extend(f"- [请填写：{item}]" for item in fill_items[:12])

    if confirm_items:
        lines.extend(["", "## 需要用户确认"])
        lines.extend(f"- [需用户确认：{item or '请核对该处推断是否真实'}]" for item in confirm_items[:12])

    return "\n".join(lines).strip()


def _line_diff(original_lines: list[str], final_lines: list[str]) -> list[str]:
    changes: list[str] = []
    matcher = difflib.SequenceMatcher(a=original_lines, b=final_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        old = original_lines[i1:i2]
        new = final_lines[j1:j2]
        if tag == "insert":
            changes.extend(f"新增/前移：`{_short(line)}`" for line in new)
        elif tag == "delete":
            changes.extend(f"删除/后移：`{_short(line)}`" for line in old)
        elif tag == "replace":
            pair_count = min(len(old), len(new))
            for index in range(pair_count):
                changes.append(f"改写：`{_short(old[index])}` 改为 `{_short(new[index])}`")
            changes.extend(f"删除/后移：`{_short(line)}`" for line in old[pair_count:])
            changes.extend(f"新增/前移：`{_short(line)}`" for line in new[pair_count:])
    return _dedupe(changes)


def _structure_notes(
    original_lines: list[str],
    final_lines: list[str],
    guard_warnings: list[str],
) -> list[str]:
    original_headings = _headings(original_lines)
    final_headings = _headings(final_lines)
    notes: list[str] = []

    missing = [title for title in original_headings if title not in final_headings]
    added = [title for title in final_headings if title not in original_headings]
    if missing:
        notes.append("原简历章节可能缺失或被改名：" + "、".join(missing[:8]))
    else:
        notes.append("原简历章节标题均已保留。")
    if added:
        notes.append("最终简历出现原文没有的章节：" + "、".join(added[:8]))

    for warning in guard_warnings:
        if warning.startswith("原简历章节可能缺失") and missing:
            continue
        notes.append(warning)
    return _dedupe(notes)


def _meaningful_lines(markdown: str) -> list[str]:
    lines: list[str] = []
    for raw in (markdown or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("> 本说明由程序基于"):
            continue
        lines.append(line)
    return lines


def _headings(lines: list[str]) -> list[str]:
    headings: list[str] = []
    for line in lines:
        match = HEADING_RE.match(line)
        if not match:
            continue
        if len(match.group(1)) == 1:
            continue
        headings.append(match.group(2).strip())
    return headings


def _extract_unique(pattern: re.Pattern[str], text: str) -> list[str]:
    values = []
    for match in pattern.finditer(text or ""):
        value = match.group(1).strip()
        if value:
            values.append(value)
    return _dedupe(values)


def _short(text: str, limit: int = 96) -> str:
    compact = re.sub(r"\s+", " ", text).strip("`")
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1] + "…"


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result
