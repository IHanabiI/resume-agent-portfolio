from __future__ import annotations

from src.config import load_prompt
from src.llm_client import LLMClient, pretty_json
from src.schemas import GapAnalysis


def refine_questions(gap: GapAnalysis, llm: LLMClient | None = None) -> GapAnalysis:
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
        result.questions_to_user = result.questions_to_user[:5]
        return result
    return gap
