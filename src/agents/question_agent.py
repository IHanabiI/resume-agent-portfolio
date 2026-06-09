from __future__ import annotations

from src.config import load_prompt
from src.llm_client import LLMClient, pretty_json
from src.requirement_classifier import soft_group_for_requirement
from src.schemas import GapAnalysis, QuestionItem


def refine_questions(gap: GapAnalysis, llm: LLMClient | None = None) -> GapAnalysis:
    gap.questions_to_user = _clean_soft_questions(gap)
    if len(gap.questions_to_user) > 5:
        gap.questions_to_user = gap.questions_to_user[:5]

    llm = llm or LLMClient()
    if llm.settings.fast_analysis_mode:
        return gap
    prompt = load_prompt("question_prompt.md")
    result = llm.generate_structured(
        "你是追问 Agent。你只能优化问题表述，不能新增无依据的候选人事实。",
        f"{prompt}\n\n缺口分析：\n{pretty_json(gap)}",
        GapAnalysis,
    )
    if result:
        result.soft_evidence_gaps = result.soft_evidence_gaps or gap.soft_evidence_gaps
        result.hard_skill_gaps = result.hard_skill_gaps or gap.hard_skill_gaps
        result.questions_to_user = _clean_soft_questions(result)[:5]
        return result
    return gap


def _clean_soft_questions(gap: GapAnalysis) -> list[QuestionItem]:
    questions: list[QuestionItem] = []
    seen: set[str] = set()
    for item in gap.soft_evidence_gaps:
        key = item.requirement.strip().lower()
        if item.suggested_question.strip() and key not in seen:
            seen.add(key)
            questions.append(
                QuestionItem(
                    question=item.suggested_question,
                    why_needed="软性能力不能只写标签，必须用具体经历证明，避免空泛表述。",
                    related_jd_requirement=item.requirement,
                )
            )
    for question in gap.questions_to_user:
        group = soft_group_for_requirement(question.related_jd_requirement) or soft_group_for_requirement(question.question)
        if group:
            key = str(group["name"]).lower()
            if key in seen:
                continue
            seen.add(key)
            questions.append(
                QuestionItem(
                    question=str(group["question"]),
                    why_needed="软性能力不能只写标签，必须用具体经历证明，避免空泛表述。",
                    related_jd_requirement=str(group["name"]),
                )
            )
            continue
        key = f"{question.related_jd_requirement.strip().lower()}::{question.question.strip().lower()}"
        if question.question.strip() and key not in seen:
            seen.add(key)
            questions.append(question)
    return questions
