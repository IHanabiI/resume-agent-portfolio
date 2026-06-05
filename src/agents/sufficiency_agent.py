from __future__ import annotations

from src.schemas import (
    CandidateProfile,
    GapAnalysis,
    InformationSufficiencyReport,
    JobAnalysis,
    UserAnswer,
)


def assess_information_sufficiency(
    candidate: CandidateProfile,
    job: JobAnalysis,
    gap: GapAnalysis,
    resume_text: str,
    memory_text: str = "",
    github_context: str = "",
    user_answers: list[UserAnswer] | None = None,
) -> InformationSufficiencyReport:
    """Score whether the available evidence is enough to generate a useful resume."""
    user_answers = user_answers or []
    evidence_blocks = [
        resume_text.strip(),
        memory_text.strip(),
        github_context.strip(),
        "\n".join(answer.answer for answer in user_answers if answer.answer.strip()),
    ]
    available_sources = sum(1 for block in evidence_blocks if len(block) >= 40)

    required_terms = _unique_terms(job.required_skills + job.keywords + job.recruiter_focus)
    context = "\n".join(block for block in evidence_blocks if block).lower()
    covered_terms = [term for term in required_terms if term.lower() in context]

    coverage_ratio = len(covered_terms) / max(1, len(required_terms))
    source_score = min(25, available_sources * 7)
    coverage_score = round(45 * coverage_ratio)
    profile_score = _profile_score(candidate)
    gap_penalty = min(25, len(gap.missing_information) * 4)
    question_penalty = min(15, len(gap.questions_to_user) * 3)
    score = max(0, min(100, source_score + coverage_score + profile_score - gap_penalty - question_penalty))

    missing = list(gap.missing_information[:6])
    if not memory_text.strip():
        missing.append("个人记忆库为空，原始简历之外的真实能力和经历还没有沉淀。")
    if not github_context.strip():
        missing.append("尚未读取 GitHub 证据，项目和代码能力缺少外部公开佐证。")
    if not user_answers:
        missing.append("还没有本轮追问回答，隐藏经历和量化成果可能没有被挖掘。")

    enough = []
    if resume_text.strip():
        enough.append("已提供原始简历，可作为基础事实来源。")
    if memory_text.strip():
        enough.append("已导入或填写个人记忆库，可复用简历外的真实经历。")
    if github_context.strip():
        enough.append("已读取 GitHub 公开证据，可辅助验证项目和技术栈。")
    if covered_terms:
        enough.append(f"已在事实来源中覆盖 {len(covered_terms)} 个岗位关键词。")

    recommended_questions = [
        item.question
        for item in gap.questions_to_user[:5]
        if item.question.strip()
    ]
    if len(recommended_questions) < 3:
        recommended_questions.extend(
            [
                "这个岗位最看重的技能中，你有哪些真实项目或课程/实习经历可以证明？",
                "是否有可量化结果，例如交付周期、使用人数、性能提升、自动化节省时间？",
                "哪些能力你不希望写进简历，或者只是了解但不熟练？",
            ][: 3 - len(recommended_questions)]
        )

    if score >= 78:
        status = "strong"
        ready = True
        summary = "信息较充分，可以生成一版有竞争力的定制简历；仍建议保留事实校验。"
    elif score >= 55:
        status = "usable"
        ready = True
        summary = "信息基本可用，可以先生成简历；若想提高质量，建议继续补充关键项目和量化成果。"
    else:
        status = "insufficient"
        ready = False
        summary = "当前信息偏少，建议先回答追问或补充记忆库，否则简历优化会比较保守。"

    return InformationSufficiencyReport(
        score=score,
        status=status,
        ready_to_generate=ready,
        summary=summary,
        enough_evidence=enough[:8],
        missing_evidence=_dedupe(missing)[:8],
        recommended_questions=_dedupe(recommended_questions)[:5],
    )


def _profile_score(candidate: CandidateProfile) -> int:
    score = 0
    if candidate.skills:
        score += 8
    if candidate.projects:
        score += 10
    if candidate.work_experience:
        score += 10
    if candidate.education:
        score += 4
    if candidate.achievements:
        score += 5
    return min(25, score)


def _unique_terms(items: list[str]) -> list[str]:
    seen: set[str] = set()
    terms: list[str] = []
    for item in items:
        term = item.strip()
        key = term.lower()
        if len(term) >= 2 and key not in seen:
            seen.add(key)
            terms.append(term)
    return terms[:30]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(item.strip())
    return result
