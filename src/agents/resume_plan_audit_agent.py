from __future__ import annotations

import difflib
import re

from src.schemas import ResumeAlignmentAction, ResumeAlignmentPlan


PLACEHOLDER_FILL_RE = re.compile(r"\[请填写[:：][^\]]+\]")
PLACEHOLDER_CONFIRM_RE = re.compile(r"\[需用户确认[:：]?[^\]]*\]")


def audit_alignment_execution(
    original_markdown: str,
    final_markdown: str,
    alignment_plan: ResumeAlignmentPlan | None,
) -> list[str]:
    if not alignment_plan:
        return []

    actions = _actionable_actions(alignment_plan)
    if not actions:
        return []

    changed_text = "\n".join(_changed_lines(original_markdown, final_markdown))
    final_text = final_markdown or ""
    warnings: list[str] = []

    if actions and not changed_text.strip():
        warnings.append(f"岗位对齐计划包含 {len(actions)} 项动作，但最终简历没有产生可比较正文变化。")

    for action in actions[:16]:
        status = _audit_action(action, final_text, changed_text)
        if status:
            warnings.append(status)

    return _dedupe(warnings)[:20]


def _audit_action(
    action: ResumeAlignmentAction,
    final_text: str,
    changed_text: str,
) -> str:
    label = _action_label(action)
    target_hit_final = _overlap(action.target, final_text) or _overlap(action.source_evidence, final_text)
    target_hit_changed = _overlap(_action_haystack(action), changed_text)

    if action.allowed_change == "insert_placeholder":
        if PLACEHOLDER_FILL_RE.search(final_text) and target_hit_final:
            return ""
        return f"计划未明显执行：{label} 要求插入回填占位符，但最终简历未定位到对应占位或目标。"

    if action.allowed_change == "confirm_inference":
        if PLACEHOLDER_CONFIRM_RE.search(final_text) and target_hit_final:
            return ""
        return f"计划未明显执行：{label} 要求保留需确认标记，但最终简历未定位到对应确认标记或目标。"

    if not target_hit_final:
        return f"计划目标未在最终简历中定位：{label}"

    if action.priority >= 4 and not target_hit_changed:
        return f"高优先级计划未在真实 diff 中明显体现：{label}"

    return ""


def _changed_lines(original_markdown: str, final_markdown: str) -> list[str]:
    original_lines = _meaningful_lines(original_markdown)
    final_lines = _meaningful_lines(final_markdown)
    changed: list[str] = []
    matcher = difflib.SequenceMatcher(a=original_lines, b=final_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        changed.extend(original_lines[i1:i2])
        changed.extend(final_lines[j1:j2])
    return changed


def _actionable_actions(plan: ResumeAlignmentPlan) -> list[ResumeAlignmentAction]:
    actions: list[ResumeAlignmentAction] = []
    actions.extend(plan.required_actions)
    actions.extend(plan.skill_adjustments)
    actions.extend(plan.placeholders)
    return [
        action
        for action in actions
        if action.action_type != "keep" and action.allowed_change != "keep"
    ]


def _action_label(action: ResumeAlignmentAction) -> str:
    target = _short(action.target or action.instruction or action.jd_reason)
    action_type = action.action_type or "action"
    return f"{action_type} / {action.allowed_change} / {target}"


def _action_haystack(action: ResumeAlignmentAction) -> str:
    return "\n".join(
        [
            action.target,
            action.source_evidence,
            action.jd_reason,
            action.instruction,
        ]
    )


def _overlap(needle: str, haystack: str) -> bool:
    compact_needle = _compact(needle)
    compact_haystack = _compact(haystack)
    if len(compact_needle) >= 8 and compact_needle in compact_haystack:
        return True

    tokens = _tokens(needle)
    if not tokens:
        return False
    hit_count = sum(1 for token in tokens if token in compact_haystack)
    return hit_count >= max(1, min(3, len(tokens)))


def _tokens(text: str) -> list[str]:
    raw_tokens = re.split(r"[\s,，、/|:：;；()（）\[\]【】\-]+", (text or "").lower())
    return [token for token in raw_tokens if len(token) >= 2][:12]


def _meaningful_lines(markdown: str) -> list[str]:
    return [line.strip() for line in (markdown or "").splitlines() if line.strip()]


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").lower())


def _short(text: str, limit: int = 80) -> str:
    compact = re.sub(r"\s+", " ", text or "").strip()
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
