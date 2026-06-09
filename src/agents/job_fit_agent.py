from __future__ import annotations

from src.schemas import CandidateProfile, GapAnalysis, JobAnalysis, JobFitReport


def assess_job_fit(
    candidate: CandidateProfile,
    job: JobAnalysis,
    gap: GapAnalysis,
    resume_text: str,
    memory_text: str = "",
    github_context: str = "",
) -> JobFitReport:
    context = "\n".join([resume_text, memory_text, github_context] + candidate.skills).lower()
    requirements = _unique(job.required_skills + job.keywords + job.recruiter_focus)
    covered = [item for item in requirements if item.lower() in context]
    missing = [item for item in requirements if item.lower() not in context]

    coverage_score = round(55 * len(covered) / max(1, len(requirements)))
    evidence_score = 0
    if candidate.projects:
        evidence_score += 12
    if candidate.work_experience:
        evidence_score += 10
    if memory_text.strip():
        evidence_score += 8
    if github_context.strip():
        evidence_score += 10
    if candidate.skills:
        evidence_score += 5
    gap_penalty = min(20, len(gap.missing_information) * 3)
    score = max(0, min(100, coverage_score + evidence_score - gap_penalty))

    if score >= 75:
        status = "high"
        recommendation = "建议优先投递。现有经历和岗位要求匹配度较高，重点打磨项目成果和证据表达。"
    elif score >= 50:
        status = "medium"
        recommendation = "可以投递，但需要针对 JD 补充关键项目、量化结果或岗位相关表达。"
    else:
        status = "low"
        recommendation = "不建议直接投递正式版本。建议先补充更多相关事实，或降低简历表达强度。"

    matched_points = []
    if covered:
        matched_points.append(f"已覆盖 {len(covered)} 个岗位关键词：{', '.join(covered[:8])}")
    matched_points.extend(gap.matched_strengths[:5])
    if github_context.strip():
        matched_points.append("已有 GitHub 公开证据，可辅助证明项目和技术栈。")

    risks = []
    if missing:
        risks.append(f"尚缺少这些岗位关键词的明确证据：{', '.join(missing[:8])}")
    risks.extend(gap.missing_information[:5])
    if not candidate.work_experience:
        risks.append("正式工作或实习经历较少，需要用项目事实和交付证据弥补。")
    if not github_context.strip():
        risks.append("尚未读取 GitHub 证据，项目可信度展示不足。")

    angle = _resume_angle(job, covered, github_context)
    return JobFitReport(
        score=score,
        status=status,
        recommendation=recommendation,
        matched_points=_dedupe(matched_points)[:8],
        risks=_dedupe(risks)[:8],
        suggested_resume_angle=angle,
    )


def _resume_angle(job: JobAnalysis, covered: list[str], github_context: str) -> str:
    text = " ".join([job.job_title] + job.keywords + job.recruiter_focus)
    if any(term in text for term in ["游戏", "策划", "玩法", "数值", "战斗"]):
        return "突出游戏项目、Mod/工具制作、玩法理解、数据反馈和持续迭代能力。"
    if any(term in text.lower() for term in ["agent", "llm", "langgraph", "ai"]):
        return "突出 AI Agent 工作流、工具调用、记忆/证据设计和可部署 Demo。"
    if github_context.strip():
        return "突出可公开验证的项目证据、技术栈和交付结果。"
    return "围绕岗位关键词重排项目经历，优先展示有证据的职责、技术和结果。"


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        value = item.strip()
        key = value.lower()
        if len(value) >= 2 and key not in seen:
            seen.add(key)
            result.append(value)
    return result[:30]


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(item.strip())
    return result
