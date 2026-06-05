from __future__ import annotations

import json
import re

from src.schemas import MemoryCandidate, MemoryFact, UserAnswer, UserMemory


SKIP_ANSWERS = {"", "没有", "不清楚", "跳过", "none", "not sure", "skip"}


def parse_memory_upload(text: str) -> UserMemory:
    text = text.strip()
    if not text:
        return UserMemory()
    try:
        data = json.loads(text)
        return UserMemory.model_validate(data)
    except Exception:
        return UserMemory(raw_notes=text)


def memory_to_text(memory: UserMemory | str) -> str:
    if isinstance(memory, str):
        return memory.strip()
    lines: list[str] = []
    if memory.profile_summary:
        lines.extend(["# 个人概况", memory.profile_summary])
    if memory.target_roles:
        lines.append("# 目标岗位")
        lines.extend(f"- {item}" for item in memory.target_roles)
    _add_facts(lines, "最强卖点", memory.strongest_selling_points)
    _add_facts(lines, "优势", memory.strengths)
    _add_facts(lines, "技能", memory.skills)
    _add_facts(lines, "项目事实", memory.projects)
    _add_facts(lines, "工作事实", memory.work_facts)
    _add_facts(lines, "追问沉淀", memory.qa_memory)
    _add_facts(lines, "GitHub 证据", memory.github_facts)
    _add_facts(lines, "不要写入简历", memory.do_not_claim)
    if memory.preferences:
        lines.append("# 偏好")
        lines.extend(f"- {item}" for item in memory.preferences)
    if memory.raw_notes:
        lines.extend(["# 原始备注", memory.raw_notes])
    return "\n".join(lines).strip()


def memory_to_json_text(memory_text: str) -> str:
    memory = UserMemory(raw_notes=memory_text.strip())
    return json.dumps(memory.model_dump(), ensure_ascii=False, indent=2)


def build_memory_json_text(
    memory_text: str,
    answers: list[UserAnswer] | None = None,
    github_context: str = "",
    memory_candidates: list[MemoryCandidate] | None = None,
) -> str:
    memory = UserMemory(raw_notes=memory_text.strip())
    candidates = memory_candidates if memory_candidates is not None else curate_memory_candidates(answers or [], github_context)
    _apply_candidates(memory, candidates)
    return json.dumps(memory.model_dump(), ensure_ascii=False, indent=2)


def curate_memory_candidates(
    answers: list[UserAnswer] | None = None,
    github_context: str = "",
) -> list[MemoryCandidate]:
    candidates: list[MemoryCandidate] = []
    for answer in answers or []:
        if answer.answer.strip().lower() in SKIP_ANSWERS:
            continue
        candidates.append(_candidate_from_answer(answer))
    candidates.extend(_github_candidates(github_context))
    return _dedupe_candidates(candidates)


def _candidate_from_answer(answer: UserAnswer) -> MemoryCandidate:
    content = answer.answer.strip()
    related = answer.related_jd_requirement.strip()
    lower = content.lower()
    tags = ["qa", "jd-guided"]
    if related:
        tags.append(_safe_tag(related))

    if any(term in content for term in ["不要写", "不能写", "不希望", "不熟", "只是了解", "没做过", "不会"]):
        category = "do_not_claim"
        save_by_default = True
    elif any(term in content for term in ["项目", "系统", "平台", "工具", "仓库", "应用", "agent", "Agent"]):
        category = "project"
        save_by_default = True
    elif any(term in content for term in ["实习", "工作", "负责", "团队", "交付"]):
        category = "work_fact"
        save_by_default = True
    elif any(term in content for term in ["熟悉", "掌握", "使用", "技术栈", "框架", "语言"]) or "skill" in lower:
        category = "skill"
        save_by_default = True
    else:
        category = "qa"
        save_by_default = len(content) >= 12

    return MemoryCandidate(
        category=category,
        content=f"问题：{answer.question}\n回答：{content}",
        evidence=related or "用户追问回答",
        tags=tags,
        source_type="user_answer",
        save_by_default=save_by_default,
    )


def _github_candidates(github_context: str) -> list[MemoryCandidate]:
    text = github_context.strip()
    if not text:
        return []
    candidates: list[MemoryCandidate] = [
        MemoryCandidate(
            category="project",
            content=text[:2000],
            evidence="GitHub public data",
            tags=["github", "public-evidence"],
            source_type="github",
            save_by_default=True,
        )
    ]
    language_line = _find_line(text, "主要语言")
    if language_line:
        candidates.append(
            MemoryCandidate(
                category="skill",
                content=language_line,
                evidence="GitHub public data",
                tags=["github", "language"],
                source_type="github",
                save_by_default=True,
            )
        )
    return candidates


def _apply_candidates(memory: UserMemory, candidates: list[MemoryCandidate]) -> None:
    for candidate in candidates:
        if not candidate.save_by_default or not candidate.content.strip():
            continue
        fact = MemoryFact(
            category=candidate.category,
            content=candidate.content.strip(),
            evidence=candidate.evidence,
            tags=candidate.tags,
        )
        if candidate.category == "strength":
            memory.strengths.append(fact)
        elif candidate.category == "skill":
            memory.skills.append(fact)
        elif candidate.category == "project":
            memory.projects.append(fact)
        elif candidate.category == "work_fact":
            memory.work_facts.append(fact)
        elif candidate.category == "preference":
            memory.preferences.append(candidate.content.strip())
        elif candidate.category == "do_not_claim":
            memory.do_not_claim.append(fact)
        else:
            memory.qa_memory.append(fact)
        if candidate.source_type == "github":
            memory.github_facts.append(fact)


def _add_facts(lines: list[str], title: str, facts: list[MemoryFact]) -> None:
    if not facts:
        return
    lines.append(f"# {title}")
    for fact in facts:
        suffix = f" 证据：{fact.evidence}" if fact.evidence else ""
        tags = f" 标签：{', '.join(fact.tags)}" if fact.tags else ""
        lines.append(f"- {fact.content}{suffix}{tags}")


def _safe_tag(text: str) -> str:
    tag = re.sub(r"\s+", "-", text.strip())
    return tag[:32]


def _find_line(text: str, needle: str) -> str:
    for line in text.splitlines():
        if needle in line:
            return line.strip(" -")
    return ""


def _dedupe_candidates(candidates: list[MemoryCandidate]) -> list[MemoryCandidate]:
    seen: set[str] = set()
    result: list[MemoryCandidate] = []
    for candidate in candidates:
        key = f"{candidate.category}:{candidate.content.strip()[:160]}"
        if key not in seen:
            seen.add(key)
            result.append(candidate)
    return result
