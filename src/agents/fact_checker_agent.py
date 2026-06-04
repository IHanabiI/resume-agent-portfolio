from __future__ import annotations

from src.config import load_prompt
from src.llm_client import LLMClient, pretty_json
from src.schemas import EvidenceItem, FactCheckResult, TailoredResumeResult, UserAnswer


def fact_check_resume(
    result: TailoredResumeResult,
    resume_text: str,
    user_answers: list[UserAnswer],
    llm: LLMClient | None = None,
) -> FactCheckResult:
    llm = llm or LLMClient()
    prompt = load_prompt("fact_checker_prompt.md")
    answer_text = "\n".join(a.answer for a in user_answers if a.answer.strip())
    checked = llm.generate_structured(
        "你是事实校验 Agent。没有来源的关键内容必须删除或标记为待确认。",
        (
            f"{prompt}\n\n待校验简历结果：\n{pretty_json(result)}"
            f"\n\n原始简历来源：\n{resume_text}\n\n用户补充来源：\n{answer_text}"
        ),
        FactCheckResult,
    )
    if checked:
        return checked
    return _fallback_fact_check(result, resume_text, user_answers)


def _fallback_fact_check(
    result: TailoredResumeResult,
    resume_text: str,
    user_answers: list[UserAnswer],
) -> FactCheckResult:
    sources = [resume_text] + [a.answer for a in user_answers if a.answer.strip()]
    evidence: list[EvidenceItem] = []
    removed: list[str] = []
    needs_confirmation: list[str] = []

    for item in result.evidence_map:
        claim = item.resume_claim.strip()
        if not claim:
            continue
        matched_source = _find_source(claim, sources)
        if matched_source:
            source_type = "user_answer" if matched_source not in resume_text else "original_resume"
            evidence.append(
                EvidenceItem(
                    resume_claim=claim,
                    source_type=source_type,
                    source_text=matched_source[:300],
                    status="verified",
                )
            )
        else:
            needs_confirmation.append(claim)
            evidence.append(
                EvidenceItem(
                    resume_claim=claim,
                    source_type=item.source_type if item.source_type != "none" else "none",
                    source_text=item.source_text,
                    status="needs_confirmation",
                )
            )

    return FactCheckResult(
        final_resume_markdown=result.resume_markdown,
        evidence_map=evidence,
        removed_claims=removed,
        needs_confirmation=needs_confirmation[:20],
    )


def _find_source(claim: str, sources: list[str]) -> str:
    normalized_claim = claim.lower()
    tokens = [token for token in normalized_claim.replace("，", " ").replace("。", " ").split() if len(token) >= 2]
    for source in sources:
        normalized_source = source.lower()
        if claim and claim in source:
            return claim
        if tokens and sum(1 for token in tokens if token in normalized_source) >= max(1, min(3, len(tokens))):
            return source
    return ""

