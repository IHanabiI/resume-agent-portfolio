from __future__ import annotations

import json

from src.schemas import MemoryFact, UserMemory


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
    _add_facts(lines, "优势", memory.strengths)
    _add_facts(lines, "技能", memory.skills)
    _add_facts(lines, "项目事实", memory.projects)
    _add_facts(lines, "工作事实", memory.work_facts)
    if memory.preferences:
        lines.append("# 偏好")
        lines.extend(f"- {item}" for item in memory.preferences)
    if memory.raw_notes:
        lines.extend(["# 原始备注", memory.raw_notes])
    return "\n".join(lines).strip()


def memory_to_json_text(memory_text: str) -> str:
    memory = UserMemory(raw_notes=memory_text.strip())
    return json.dumps(memory.model_dump(), ensure_ascii=False, indent=2)


def _add_facts(lines: list[str], title: str, facts: list[MemoryFact]) -> None:
    if not facts:
        return
    lines.append(f"# {title}")
    for fact in facts:
        suffix = f" 证据：{fact.evidence}" if fact.evidence else ""
        tags = f" 标签：{', '.join(fact.tags)}" if fact.tags else ""
        lines.append(f"- {fact.content}{suffix}{tags}")
