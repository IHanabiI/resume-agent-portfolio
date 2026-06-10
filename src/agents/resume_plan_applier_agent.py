from __future__ import annotations

import re

from src.schemas import ResumeAlignmentAction, ResumeAlignmentPlan, ResumeLine, ResumeStructure


def build_ordered_resume_draft(
    resume_structure: ResumeStructure | None,
    alignment_plan: ResumeAlignmentPlan | None,
) -> str:
    if not resume_structure or not resume_structure.lines:
        return ""
    if not alignment_plan:
        return "\n".join(line.text for line in resume_structure.lines)

    actions = _effective_actions(alignment_plan)
    if not actions:
        return "\n".join(line.text for line in resume_structure.lines)

    rendered: list[str] = []
    for section in resume_structure.sections:
        if not section.lines:
            continue
        headings = [line for line in section.lines if line.line_type == "heading"]
        body = [line for line in section.lines if line.line_type != "heading"]
        for line in headings:
            rendered.append(line.text)
        if body:
            sorted_body = sorted(
                body,
                key=lambda line: (
                    -_line_priority(line, actions),
                    line.line_id,
                ),
            )
            rendered.extend(line.text for line in sorted_body)
        rendered.append("")
    return "\n".join(rendered).strip()


def _effective_actions(plan: ResumeAlignmentPlan) -> list[ResumeAlignmentAction]:
    actions = []
    actions.extend(plan.required_actions)
    actions.extend(plan.skill_adjustments)
    actions.extend(plan.placeholders)
    return [
        action
        for action in actions
        if action.action_type in {"section_reorder", "item_reorder", "rewrite", "skill_reorder"}
        and action.allowed_change in {"reorder_only", "rewrite_existing"}
    ]


def _line_priority(line: ResumeLine, actions: list[ResumeAlignmentAction]) -> int:
    best = 0
    for action in actions:
        if _action_matches_line(action, line):
            best = max(best, action.priority)
    return best


def _action_matches_line(action: ResumeAlignmentAction, line: ResumeLine) -> bool:
    haystacks = [
        action.target,
        action.source_evidence,
        action.instruction,
        action.jd_reason,
    ]
    target_text = " ".join(haystacks).lower()
    line_text = line.text.lower()
    if line.line_id and line.line_id.lower() in target_text:
        return True
    if line.section_id and line.section_id.lower() in target_text:
        return True
    if line.section_title and line.section_title.lower() in target_text:
        return True
    if _compact(line_text) and _compact(line_text) in _compact(target_text):
        return True
    return _token_overlap(line_text, target_text) >= 2


def _compact(text: str) -> str:
    return re.sub(r"\s+", "", text.strip().lower())


def _token_overlap(left: str, right: str) -> int:
    tokens = {
        token
        for token in re.split(r"[\s,，、/|:：;；()（）\[\]【】\-]+", left.lower())
        if len(token) >= 3
    }
    if not tokens:
        return 0
    return sum(1 for token in tokens if token in right)
