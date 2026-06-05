from __future__ import annotations

from src.config import load_prompt
from src.llm_client import LLMClient, pretty_json
from src.schemas import EvidenceItem, FactCheckResult, TailoredResumeResult, UserAnswer


def fact_check_resume(
    result: TailoredResumeResult,
    resume_text: str,
    user_answers: list[UserAnswer],
    memory_text: str = "",
    github_context: str = "",
    llm: LLMClient | None = None,
) -> FactCheckResult:
    llm = llm or LLMClient()
    prompt = load_prompt("fact_checker_prompt.md")
    answer_text = "\n".join(a.answer for a in user_answers if a.answer.strip())
    checked = llm.generate_structured(
        "你是事实校验 Agent。没有来源的关键内容必须删除或标记为待确认。可用来源包括原始简历、用户回答、个人记忆库和 GitHub 公开证据。",
        (
            f"{prompt}\n\n待校验简历结果：\n{pretty_json(result)}"
            f"\n\n原始简历来源：\n{resume_text}"
            f"\n\n用户补充来源：\n{answer_text}"
            f"\n\n个人记忆库来源：\n{memory_text}"
            f"\n\nGitHub 公开证据来源：\n{github_context}"
        ),
        FactCheckResult,
    )
    if checked:
        return checked
    return _fallback_fact_check(result, resume_text, user_answers, memory_text, github_context)


def _fallback_fact_check(
    result: TailoredResumeResult,
    resume_text: str,
    user_answers: list[UserAnswer],
    memory_text: str,
    github_context: str,
) -> FactCheckResult:
    source_items = [("original_resume", resume_text)]
    source_items.extend(("user_answer", a.answer) for a in user_answers if a.answer.strip())
    if memory_text.strip():
        source_items.append(("user_memory", memory_text))
    if github_context.strip():
        source_items.append(("github", github_context))

    evidence: list[EvidenceItem] = []
    needs_confirmation: list[str] = []

    for item in result.evidence_map:
        claim = item.resume_claim.strip()
        if not claim:
            continue
        source_type, matched_source = _find_source(claim, source_items)
        if matched_source:
            evidence.append(
                EvidenceItem(
                    resume_claim=claim,
                    source_type=source_type,
                    source_text=matched_source[:500],
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

    final_markdown = _remove_unverified_lines(result.resume_markdown, needs_confirmation)

    return FactCheckResult(
        final_resume_markdown=final_markdown,
        evidence_map=evidence,
        removed_claims=needs_confirmation[:20],
        needs_confirmation=needs_confirmation[:20],
    )


def _find_source(claim: str, sources: list[tuple[str, str]]) -> tuple[str, str]:
    normalized_claim = claim.lower()
    tokens = [
        token
        for token in normalized_claim.replace("，", " ").replace("。", " ").replace("、", " ").split()
        if len(token) >= 2
    ]
    for source_type, source in sources:
        normalized_source = source.lower()
        if claim and claim in source:
            return source_type, claim
        if tokens and sum(1 for token in tokens if token in normalized_source) >= max(1, min(3, len(tokens))):
            return source_type, source
    return "none", ""


def _remove_unverified_lines(markdown: str, claims: list[str]) -> str:
    if not claims:
        return markdown
    claim_tokens = [_important_tokens(claim) for claim in claims]
    kept: list[str] = []
    removed_section_added = False
    for line in markdown.splitlines():
        if line.lstrip().startswith("- ") and _line_matches_claim(line, claim_tokens):
            continue
        kept.append(line)
    if claims:
        kept.extend(["", "## 待确认信息"])
        removed_section_added = True
        for claim in claims[:20]:
            kept.append(f"- {claim}")
    if removed_section_added:
        kept.append("")
        kept.append("> 上述内容缺少可验证来源，未写入正式简历正文。")
    return "\n".join(kept).strip()


def _line_matches_claim(line: str, claim_tokens: list[list[str]]) -> bool:
    normalized = line.lower()
    for tokens in claim_tokens:
        if tokens and sum(1 for token in tokens if token in normalized) >= max(1, min(3, len(tokens))):
            return True
    return False


def _important_tokens(text: str) -> list[str]:
    normalized = (
        text.lower()
        .replace("：", " ")
        .replace("，", " ")
        .replace("、", " ")
        .replace("。", " ")
        .replace("；", " ")
        .replace(":", " ")
        .replace(",", " ")
    )
    return [token for token in normalized.split() if len(token) >= 2][:12]
