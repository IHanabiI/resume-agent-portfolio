from __future__ import annotations

import re

from src.schemas import ResumeAlignmentAction, ResumeAlignmentPlan, ResumeLine, ResumeStructure


LOCATOR_RE = re.compile(r"\bS\d{3}/.*?/L\d{3}\b", re.IGNORECASE)
CONCRETE_ACTION_TYPES = {"rewrite", "item_reorder", "skill_reorder", "placeholder"}


def bind_alignment_plan_targets(
    plan: ResumeAlignmentPlan,
    resume_structure: ResumeStructure | None,
) -> ResumeAlignmentPlan:
    if not resume_structure or not resume_structure.lines:
        return plan

    for action in _all_actions(plan):
        if LOCATOR_RE.search(action.target or ""):
            continue
        line = _best_line_for_action(action, resume_structure.lines)
        if not line:
            continue
        locator = _line_locator(line)
        original_target = (action.target or "").strip()
        action.target = f"{locator} - {original_target or line.text}"
        if not action.source_evidence.strip() and line.line_type != "heading":
            action.source_evidence = line.text
    return plan


def _all_actions(plan: ResumeAlignmentPlan) -> list[ResumeAlignmentAction]:
    actions: list[ResumeAlignmentAction] = []
    actions.extend(plan.required_actions)
    actions.extend(plan.skill_adjustments)
    actions.extend(plan.placeholders)
    return actions


def _best_line_for_action(action: ResumeAlignmentAction, lines: list[ResumeLine]) -> ResumeLine | None:
    best_line: ResumeLine | None = None
    best_score = 0
    best_specific_score = 0
    for line in lines:
        score = _line_score(action, line)
        if score > best_score:
            best_score = score
            best_specific_score = _specific_line_score(action, line)
            best_line = line
    if not best_line:
        return None
    if action.action_type in CONCRETE_ACTION_TYPES:
        if best_line.line_type == "heading":
            return None
        if best_specific_score < 20:
            return None
        return best_line if best_score >= 20 else None
    return best_line if best_score >= 5 else None


def _line_score(action: ResumeAlignmentAction, line: ResumeLine) -> int:
    haystack = _action_haystack(action)
    compact_haystack = _compact(haystack)
    score = _specific_line_score(action, line)

    if line.section_id and line.section_id.lower() in haystack.lower():
        score += 30
    if line.section_title and _compact(line.section_title) in compact_haystack:
        score += 10

    if action.action_type == "skill_reorder" and _looks_like_skill_line(line):
        score += 15
    if action.action_type in {"rewrite", "item_reorder"} and line.line_type == "heading":
        score -= 8
    return score


def _specific_line_score(action: ResumeAlignmentAction, line: ResumeLine) -> int:
    haystack = _action_haystack(action)
    compact_haystack = _compact(haystack)
    compact_line = _compact(line.text)
    score = 0

    if line.line_id and line.line_id.lower() in haystack.lower():
        score += 100
    if compact_line and compact_line in compact_haystack:
        score += 40
    if _compact(action.target) and _compact(action.target) in compact_line:
        score += 20
    if _compact(action.source_evidence) and _compact(action.source_evidence) in compact_line:
        score += 30
    score += min(12, _token_overlap(line.text, haystack) * 3)
    return score


def _line_locator(line: ResumeLine) -> str:
    section = line.section_title or "未命名区块"
    return f"{line.section_id}/{section}/{line.line_id}"


def _action_haystack(action: ResumeAlignmentAction) -> str:
    return "\n".join(
        [
            action.target,
            action.source_evidence,
            action.jd_reason,
            action.instruction,
        ]
    )


def _looks_like_skill_line(line: ResumeLine) -> bool:
    text = f"{line.section_title} {line.text}"
    return any(term in text for term in ["技能", "能力", "工具", "技术栈", "专业"])


def _token_overlap(left: str, right: str) -> int:
    right_compact = _compact(right)
    tokens = {
        token
        for token in re.split(r"[\s,，、/|:：;；()（）\[\]【】\-]+", (left or "").lower())
        if len(token) >= 2
    }
    return sum(1 for token in tokens if _compact(token) in right_compact)


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").strip().lower())
