from __future__ import annotations

import re

from src.schemas import ResumeAlignmentAction, ResumeAlignmentPlan, ResumeLine, ResumeStructure


EXPERIENCE_SECTION_TERMS = ("工作", "项目", "实习", "经历", "实践", "创业")
SKILL_SECTION_TERMS = ("技能", "技术", "能力", "工具", "栈")


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
            rendered.extend(_render_ordered_body(section.title, body, actions))
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


def _render_ordered_body(
    section_title: str,
    body: list[ResumeLine],
    actions: list[ResumeAlignmentAction],
) -> list[str]:
    if _looks_like_experience_section(section_title):
        blocks = _group_experience_blocks(body)
        sorted_blocks = sorted(
            blocks,
            key=lambda block: (
                -_block_priority(block, actions),
                _line_order(block[0]),
            ),
        )
        rendered: list[str] = []
        for block in sorted_blocks:
            rendered.extend(line.text for line in _order_block_children(block, actions))
        return rendered

    if _looks_like_skill_section(section_title):
        sorted_body = sorted(
            body,
            key=lambda line: (
                -_line_priority(line, actions),
                _line_order(line),
            ),
        )
        return [line.text for line in sorted_body]

    return [line.text for line in body]


def _group_experience_blocks(lines: list[ResumeLine]) -> list[list[ResumeLine]]:
    blocks: list[list[ResumeLine]] = []
    current: list[ResumeLine] = []

    for line in lines:
        starts_new_block = bool(current) and line.line_type == "paragraph"
        if starts_new_block:
            blocks.append(current)
            current = [line]
            continue
        current.append(line)

    if current:
        blocks.append(current)
    return blocks


def _order_block_children(block: list[ResumeLine], actions: list[ResumeAlignmentAction]) -> list[ResumeLine]:
    if len(block) <= 1:
        return block

    if block[0].line_type == "paragraph":
        return [block[0], *_order_bullet_runs(block[1:], actions)]
    return _order_bullet_runs(block, actions)


def _order_bullet_runs(lines: list[ResumeLine], actions: list[ResumeAlignmentAction]) -> list[ResumeLine]:
    ordered: list[ResumeLine] = []
    run: list[ResumeLine] = []

    def flush_run() -> None:
        if not run:
            return
        ordered.extend(
            sorted(
                run,
                key=lambda line: (
                    -_line_priority(line, actions),
                    _line_order(line),
                ),
            )
        )
        run.clear()

    for line in lines:
        if line.line_type == "bullet":
            run.append(line)
            continue
        flush_run()
        ordered.append(line)
    flush_run()
    return ordered


def _block_priority(block: list[ResumeLine], actions: list[ResumeAlignmentAction]) -> int:
    return max((_line_priority(line, actions) for line in block), default=0)


def _line_order(line: ResumeLine) -> int:
    match = re.search(r"\d+", line.line_id or "")
    return int(match.group(0)) if match else 0


def _looks_like_experience_section(section_title: str) -> bool:
    return any(term in section_title for term in EXPERIENCE_SECTION_TERMS)


def _looks_like_skill_section(section_title: str) -> bool:
    return any(term in section_title for term in SKILL_SECTION_TERMS)


def _action_matches_line(action: ResumeAlignmentAction, line: ResumeLine) -> bool:
    haystacks = [
        action.target,
        action.source_evidence,
        action.instruction,
        action.jd_reason,
    ]
    target_text = " ".join(haystacks).lower()
    line_text = _plain_line_text(line.text).lower()
    if line.line_id and line.line_id.lower() in target_text:
        return True
    if line.section_id and line.section_id.lower() in target_text:
        return True
    if line.section_title and line.section_title.lower() in target_text:
        return True
    compact_line = _compact(line_text)
    compact_target = _compact(target_text)
    if compact_line and (compact_line in compact_target or compact_target in compact_line):
        return True
    return _token_overlap(line_text, target_text) >= 2


def _plain_line_text(text: str) -> str:
    return re.sub(r"^\s*(?:[-*+•]|\d+[.、)])\s+", "", text).strip()


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
