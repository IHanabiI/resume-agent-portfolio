from __future__ import annotations

from src.agents.resume_plan_binding_agent import bind_alignment_plan_targets
from src.config import load_prompt
from src.llm_client import LLMClient, pretty_json
from src.schemas import (
    CandidateProfile,
    GapAnalysis,
    JobAnalysis,
    ResumeAlignmentAction,
    ResumeAlignmentPlan,
    ResumeQualityReport,
    ResumeStarProfile,
    ResumeStructure,
    UserAnswer,
)


def build_alignment_plan(
    candidate: CandidateProfile,
    job: JobAnalysis,
    gap: GapAnalysis,
    resume_text: str,
    user_answers: list[UserAnswer],
    resume_star_profile: ResumeStarProfile | None = None,
    resume_quality_report: ResumeQualityReport | None = None,
    resume_structure: ResumeStructure | None = None,
    memory_text: str = "",
    github_context: str = "",
    llm: LLMClient | None = None,
) -> ResumeAlignmentPlan:
    llm = llm or LLMClient()
    if llm.settings.fast_alignment_plan:
        fallback = _fallback_plan(
            job,
            gap,
            resume_star_profile,
            resume_quality_report,
            user_answers,
            memory_text,
            github_context,
        )
        return bind_alignment_plan_targets(fallback, resume_structure)

    prompt = load_prompt("alignment_planner_prompt.md")
    result = llm.generate_structured(
        "你是简历岗位对齐规划器。你只输出改写计划，不写最终简历。事实优先，禁止编造，必须保留原简历骨架。",
        (
            f"{prompt}\n\n候选人结构化信息：\n{pretty_json(candidate)}"
            f"\n\n岗位分析：\n{pretty_json(job)}"
            f"\n\n匹配缺口：\n{pretty_json(gap)}"
            f"\n\n简历质量评估：\n{pretty_json(resume_quality_report)}"
            f"\n\n原简历结构骨架：\n{pretty_json(resume_structure)}"
            f"\n\nSTAR 证据：\n{pretty_json(resume_star_profile)}"
            f"\n\n用户补充回答：\n{pretty_json({'answers': [a.model_dump() for a in user_answers]})}"
            f"\n\n原始简历全文：\n{resume_text}"
            f"\n\n个人记忆库：\n{memory_text}"
            f"\n\nGitHub 公开证据：\n{github_context}"
        ),
        ResumeAlignmentPlan,
    )
    if result:
        result.format_constraints = _merge_constraints(result.format_constraints)
        return bind_alignment_plan_targets(result, resume_structure)
    fallback = _fallback_plan(
        job,
        gap,
        resume_star_profile,
        resume_quality_report,
        user_answers,
        memory_text,
        github_context,
    )
    return bind_alignment_plan_targets(fallback, resume_structure)


def _fallback_plan(
    job: JobAnalysis,
    gap: GapAnalysis,
    star: ResumeStarProfile | None,
    quality: ResumeQualityReport | None,
    answers: list[UserAnswer],
    memory_text: str,
    github_context: str,
) -> ResumeAlignmentPlan:
    star_evidence = []
    evidence = []
    if star:
        star_evidence.extend(item.raw_text for item in star.items[:6] if item.raw_text.strip())
    evidence.extend(star_evidence)
    evidence.extend(gap.matched_strengths[:4])
    evidence.extend(
        answer.answer.strip()
        for answer in answers
        if answer.answer.strip() and answer.answer.strip().lower() not in {"没有", "跳过", "不清楚", "none", "skip"}
    )
    if memory_text.strip():
        evidence.append(memory_text.strip()[:240])
    if github_context.strip():
        evidence.append(github_context.strip()[:240])

    required_actions = [
        ResumeAlignmentAction(
            action_type="rewrite",
            target=item[:80],
            source_evidence=item,
            jd_reason="该证据与目标岗位关键词或职责存在匹配关系。",
            instruction="在原简历对应位置内强化与目标岗位相关的行动、产物和结果表达；不得改变事实。",
            allowed_change="rewrite_existing",
            priority=4,
        )
        for item in star_evidence[:5]
    ]

    placeholders = []
    missing = list(gap.missing_information)
    if quality:
        missing.extend(quality.missing_result_items[:3])
        missing.extend(quality.missing_metric_items[:3])
        missing.extend(quality.empty_shell_items[:3])
    for item in missing[:8]:
        placeholders.append(
            ResumeAlignmentAction(
                action_type="placeholder",
                target=item[:80],
                source_evidence="当前事实来源不足。",
                jd_reason="该信息可能影响岗位匹配，但缺少可验证事实。",
                instruction=f"如必须出现，只能写为 [请填写：{item[:60]}]，不能替用户编造。",
                allowed_change="insert_placeholder",
                priority=5,
            )
        )

    skill_adjustments = [
        ResumeAlignmentAction(
            action_type="skill_reorder",
            target="专业技能",
            source_evidence="、".join(job.required_skills[:8] + job.preferred_skills[:4]),
            jd_reason="技能板块应优先展示 JD 中权重最高的技能、工具、方法和产物。",
            instruction="在不虚构熟练程度的前提下，将已有且匹配 JD 的技能前移；缺失技能不得写成已掌握。",
            allowed_change="reorder_only",
            priority=4,
        )
    ]

    do_not_use = list(gap.hard_skill_gaps[:6])
    do_not_use.extend(item.requirement for item in gap.soft_evidence_gaps if item.current_status == "missing")

    return ResumeAlignmentPlan(
        target_role=job.job_title,
        strategy_summary=(
            f"围绕 {job.job_title or '目标岗位'} 强化已有证据，优先重排与 JD 直接相关的项目、成果和技能。"
        ),
        strongest_evidence=list(dict.fromkeys(evidence))[:6],
        required_actions=required_actions,
        skill_adjustments=skill_adjustments,
        placeholders=placeholders,
        do_not_use_claims=list(dict.fromkeys(do_not_use))[:10],
        format_constraints=_merge_constraints([]),
    )


def _merge_constraints(existing: list[str]) -> list[str]:
    defaults = [
        "只改内容不改架子：保留原简历主要章节，不新增交付说明类章节。",
        "列表格式保持一条一行，不把多个要点压成一个长段落。",
        "`#` 只用于姓名或简历主标题，`##` 只用于顶层章节，`###` 只用于具体公司、项目、学校或经历条目。",
        "没有事实来源的 JD 要求不能写入简历，只能放入缺口或占位符。",
        "没有量化数据时不能编造数字，只能使用 `[请填写：xxx]`。",
        "轻度推断必须保留 `[需用户确认：xxx]`。",
    ]
    return list(dict.fromkeys([item for item in existing if item.strip()] + defaults))
