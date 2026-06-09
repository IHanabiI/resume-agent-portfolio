from __future__ import annotations

from src.schemas import CandidateProfile, GapAnalysis, JobAnalysis, JobFitReport, ResumeQualityReport, ResumeStarProfile


def assess_job_fit(
    candidate: CandidateProfile,
    job: JobAnalysis,
    gap: GapAnalysis,
    resume_text: str,
    memory_text: str = "",
    github_context: str = "",
    resume_quality: ResumeQualityReport | None = None,
    star_profile: ResumeStarProfile | None = None,
) -> JobFitReport:
    context = "\n".join([resume_text, memory_text, github_context] + candidate.skills).lower()
    requirements = _unique(job.required_skills + job.keywords + job.recruiter_focus)
    covered = [item for item in requirements if item.lower() in context]
    missing = [item for item in requirements if item.lower() not in context]

    hard_skills_score = _score_hard_skills(covered, missing, job.preferred_skills, context)
    experience_depth_score = _score_experience_depth(candidate, resume_quality, star_profile, memory_text, github_context)
    domain_fit_score = _score_domain_fit(job, context, covered, requirements)
    soft_fit_score = _score_soft_fit(job, gap, context, resume_quality)
    gap_penalty = min(10, len(gap.missing_information) * 2)
    score = max(
        0,
        min(
            100,
            round((hard_skills_score + experience_depth_score + domain_fit_score + soft_fit_score) / 4) - gap_penalty,
        ),
    )

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
    if star_profile and star_profile.items:
        matched_points.append(f"简历中已有 {len(star_profile.items)} 条 STAR 候选经历可用于岗位适配。")
    matched_points.extend(gap.matched_strengths[:5])
    if github_context.strip():
        matched_points.append("已有 GitHub 公开证据，可辅助证明项目和技术栈。")

    risks = []
    if missing:
        risks.append(f"尚缺少这些岗位关键词的明确证据：{', '.join(missing[:8])}")
    risks.extend(gap.missing_information[:5])
    if resume_quality:
        if resume_quality.empty_shell_items:
            risks.append(f"简历存在 {len(resume_quality.empty_shell_items)} 条空壳经历，生成前建议补全行动和结果。")
        if resume_quality.missing_metric_items:
            risks.append(f"有 {len(resume_quality.missing_metric_items)} 条经历缺少可确认数字，量化说服力不足。")
    if not candidate.work_experience:
        risks.append("正式工作或实习经历较少，需要用项目事实和交付证据弥补。")
    if not github_context.strip():
        risks.append("尚未读取 GitHub 证据，项目可信度展示不足。")

    angle = _resume_angle(job, covered, github_context)
    one_liner = _one_liner(score, hard_skills_score, experience_depth_score, domain_fit_score, soft_fit_score)
    return JobFitReport(
        score=score,
        hard_skills_score=hard_skills_score,
        experience_depth_score=experience_depth_score,
        domain_fit_score=domain_fit_score,
        soft_fit_score=soft_fit_score,
        status=status,
        one_liner=one_liner,
        recommendation=recommendation,
        matched_points=_dedupe(matched_points)[:8],
        risks=_dedupe(risks)[:8],
        suggested_resume_angle=angle,
    )


def _score_hard_skills(covered: list[str], missing: list[str], preferred: list[str], context: str) -> int:
    total = len(covered) + len(missing)
    base = round(100 * len(covered) / max(1, total))
    bonus = sum(5 for item in preferred if item and item.lower() in context)
    return max(0, min(100, base + bonus))


def _score_experience_depth(
    candidate: CandidateProfile,
    resume_quality: ResumeQualityReport | None,
    star_profile: ResumeStarProfile | None,
    memory_text: str,
    github_context: str,
) -> int:
    score = 35
    if candidate.work_experience:
        score += 20
    if candidate.projects:
        score += 15
    if star_profile and star_profile.items:
        score += min(20, len(star_profile.items) * 4)
    if resume_quality:
        score += round(resume_quality.score * 0.15)
        score -= min(15, len(resume_quality.empty_shell_items) * 5)
    if memory_text.strip():
        score += 5
    if github_context.strip():
        score += 5
    return max(0, min(100, score))


def _score_domain_fit(job: JobAnalysis, context: str, covered: list[str], requirements: list[str]) -> int:
    domain_terms = _unique(job.keywords + job.recruiter_focus + [job.job_title])
    hits = [item for item in domain_terms if item and item.lower() in context]
    base = round(100 * len(hits) / max(1, len(domain_terms)))
    if covered:
        base = max(base, round(80 * len(covered) / max(1, len(requirements))))
    return max(20 if domain_terms else 45, min(100, base))


def _score_soft_fit(
    job: JobAnalysis,
    gap: GapAnalysis,
    context: str,
    resume_quality: ResumeQualityReport | None,
) -> int:
    focus = [item for item in job.recruiter_focus if item.strip()]
    hits = [item for item in focus if item.lower() in context]
    score = round(85 * len(hits) / max(1, len(focus))) if focus else 55
    if gap.matched_strengths:
        score += min(15, len(gap.matched_strengths) * 3)
    if resume_quality and resume_quality.score >= 70:
        score += 5
    return max(0, min(100, score))


def _one_liner(total: int, hard: int, depth: int, domain: int, soft: int) -> str:
    weakest = min(
        [("硬技能", hard), ("经验深度", depth), ("领域契合", domain), ("软性匹配", soft)],
        key=lambda item: item[1],
    )
    if total >= 75:
        return f"整体匹配较强，主要短板在{weakest[0]}，适合优先投递。"
    if total >= 50:
        return f"可以投递，但需要先补强{weakest[0]}相关证据。"
    return f"当前匹配偏弱，建议重点补充{weakest[0]}证据后再投递。"


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
