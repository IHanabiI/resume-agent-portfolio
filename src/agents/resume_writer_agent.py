from __future__ import annotations

from src.config import load_prompt
from src.llm_client import LLMClient, pretty_json
from src.schemas import (
    CandidateProfile,
    EvidenceItem,
    GapAnalysis,
    JobAnalysis,
    ResumeAlignmentPlan,
    ResumeStarProfile,
    TailoredResumeResult,
    UserAnswer,
)


def write_resume(
    candidate: CandidateProfile,
    job: JobAnalysis,
    gap: GapAnalysis,
    resume_text: str,
    user_answers: list[UserAnswer],
    resume_star_profile: ResumeStarProfile | None = None,
    alignment_plan: ResumeAlignmentPlan | None = None,
    memory_text: str = "",
    github_context: str = "",
    llm: LLMClient | None = None,
) -> TailoredResumeResult:
    llm = llm or LLMClient()
    prompt = load_prompt("resume_writer_prompt.md")
    result = llm.generate_structured(
        "你是简历生成 Agent。事实优先于表达，禁止编造，禁止夸大。可使用的事实来源只有原始简历、个人记忆库、GitHub 公开证据和用户补充回答。",
        (
            f"{prompt}\n\n候选人信息：\n{pretty_json(candidate)}\n\n岗位分析：\n{pretty_json(job)}"
            f"\n\n缺口分析：\n{pretty_json(gap)}"
            f"\n\nSTAR 证据：\n{pretty_json(resume_star_profile)}"
            f"\n\n岗位对齐改写计划：\n{pretty_json(alignment_plan)}"
            f"\n\n用户补充回答：\n{pretty_json({'answers': [a.model_dump() for a in user_answers]})}"
            f"\n\n原始简历全文：\n{resume_text}"
            f"\n\n个人记忆库：\n{memory_text}"
            f"\n\nGitHub 公开证据：\n{github_context}"
        ),
        TailoredResumeResult,
    )
    if not result:
        return _fallback_write(candidate, job, gap, user_answers, memory_text, github_context, alignment_plan)
    if not result.opener_markdown:
        result.opener_markdown = _build_opener(candidate, job, gap, github_context)
    if not result.changelog_markdown:
        result.changelog_markdown = _build_changelog(
            job,
            gap,
            result.integrated_keywords,
            result.still_missing_info,
            alignment_plan,
        )
    return result


def _fallback_write(
    candidate: CandidateProfile,
    job: JobAnalysis,
    gap: GapAnalysis,
    user_answers: list[UserAnswer],
    memory_text: str,
    github_context: str,
    alignment_plan: ResumeAlignmentPlan | None = None,
) -> TailoredResumeResult:
    lines = [
        f"# {candidate.name or '候选人'}",
        "",
        f"- 联系方式：{candidate.contact or '待补充'}",
        f"- 目标岗位：{job.job_title or '目标岗位'}",
        "",
        "## 个人优势",
    ]
    strengths = (
        (alignment_plan.strongest_evidence if alignment_plan else [])
        or gap.matched_strengths
        or ["基于现有事实来源进行岗位适配表达，未添加无来源经历。"]
    )
    for item in strengths[:5]:
        lines.append(f"- {item}")

    answered = [
        a for a in user_answers
        if a.answer.strip() and a.answer.strip().lower() not in {"没有", "跳过", "不清楚", "none", "skip", "not sure"}
    ]
    for answer in answered[:3]:
        lines.append(f"- {answer.answer.strip()}")

    if candidate.skills:
        lines.extend(["", "## 技能"])
        lines.append("- " + "、".join(candidate.skills[:20]))

    if candidate.work_experience:
        lines.extend(["", "## 工作经历"])
        for exp in candidate.work_experience:
            lines.append(f"### {exp.company or '工作经历'}")
            if exp.title or exp.period:
                lines.append(f"- {exp.title} {exp.period}".strip())
            for resp in exp.responsibilities[:5]:
                lines.append(f"- {resp}")
            for ach in exp.achievements[:3]:
                lines.append(f"- {ach}")

    if candidate.projects:
        lines.extend(["", "## 项目经历"])
        for project in candidate.projects:
            lines.append(f"### {project.name or '项目经历'}")
            if project.role or project.period:
                lines.append(f"- {project.role} {project.period}".strip())
            if project.description:
                lines.append(f"- {project.description}")
            for ach in project.achievements[:4]:
                lines.append(f"- {ach}")

    if candidate.education:
        lines.extend(["", "## 教育背景"])
        for edu in candidate.education:
            lines.append(f"- {edu}")

    evidence = [
        EvidenceItem(
            resume_claim=line.lstrip("-# ").strip(),
            source_type="original_resume",
            source_text=line.lstrip("-# ").strip(),
            status="needs_confirmation",
        )
        for line in lines
        if line.startswith("- ") and "待补充" not in line
    ]
    for answer in answered:
        evidence.append(
            EvidenceItem(
                resume_claim=answer.answer.strip(),
                source_type="user_answer",
                source_text=answer.answer.strip(),
                status="verified",
            )
        )
    if memory_text.strip():
        evidence.append(
            EvidenceItem(
                resume_claim="使用个人记忆库补充候选人经历和优势",
                source_type="user_memory",
                source_text=memory_text[:500],
                status="verified",
            )
        )
    if github_context.strip():
        evidence.append(
            EvidenceItem(
                resume_claim="参考 GitHub 公开仓库信息补充项目和技术证据",
                source_type="github",
                source_text=github_context[:500],
                status="verified",
            )
        )
    return TailoredResumeResult(
        resume_markdown="\n".join(lines),
        opener_markdown=_build_opener(candidate, job, gap, github_context),
        changelog_markdown=_build_changelog(
            job,
            gap,
            [k for k in job.keywords if k][:12],
            gap.missing_information[:8],
            alignment_plan,
        ),
        optimization_notes=[
            "已按岗位对齐计划重排和强化已有事实。",
            "已纳入个人记忆库和 GitHub 公开证据。",
            "没有为缺失技能或成果编造经历。",
        ],
        integrated_keywords=[k for k in job.keywords if k][:12],
        still_missing_info=gap.missing_information[:8],
        evidence_map=evidence,
    )


def _build_opener(
    candidate: CandidateProfile,
    job: JobAnalysis,
    gap: GapAnalysis,
    github_context: str,
) -> str:
    strengths = gap.matched_strengths[:2] or ["我有与岗位要求相关的项目/实践经历"]
    github_line = "另外，我有可公开查看的 GitHub 项目证据，便于进一步核验项目实现。" if github_context.strip() else ""
    lines = [
        f"您好，我想应聘{job.job_title or '这个岗位'}。",
        "",
        "我关注到岗位要求中比较重视"
        + ("、".join(job.keywords[:5]) if job.keywords else "岗位相关能力")
        + "，我的经历中比较匹配的部分是：",
    ]
    for item in strengths:
        lines.append(f"- {item}")
    if github_line:
        lines.extend(["", github_line])
    lines.extend(
        [
            "",
            "我已根据该岗位要求准备了一版定制简历，如方便的话，希望能进一步沟通岗位匹配情况。谢谢。",
        ]
    )
    return "\n".join(lines)


def _build_changelog(
    job: JobAnalysis,
    gap: GapAnalysis,
    keywords: list[str],
    missing_info: list[str],
    alignment_plan: ResumeAlignmentPlan | None = None,
) -> str:
    lines = [
        "## 已做调整",
        "- 根据 JD 关键词重排并强化与岗位相关的经历表达。",
        "- 优先保留有原始简历、个人记忆、GitHub 或用户回答支撑的内容。",
        "- 对缺少证据的能力或成果保持保守表达，没有编造项目、数字或职责。",
    ]
    if alignment_plan and alignment_plan.required_actions:
        lines.extend(["", "## 岗位对齐计划"])
        for action in alignment_plan.required_actions[:8]:
            lines.append(f"- {action.target}：{action.instruction}")
    if keywords:
        lines.extend(["", "## 关联 JD 关键词"])
        for item in keywords[:12]:
            lines.append(f"- {item}")
    if gap.matched_strengths:
        lines.extend(["", "## 使用的匹配依据"])
        for item in gap.matched_strengths[:6]:
            lines.append(f"- {item}")
    if missing_info:
        lines.extend(["", "## 需要用户补充"])
        for item in missing_info[:8]:
            lines.append(f"- [请填写：{item}]")
    elif gap.missing_information:
        lines.extend(["", "## 需要用户补充"])
        for item in gap.missing_information[:8]:
            lines.append(f"- [请填写：{item}]")
    else:
        lines.extend(["", "## 需要用户补充", "- 暂无明确缺失项。"])
    return "\n".join(lines)


def _short_lines(text: str) -> list[str]:
    lines = []
    for raw in text.splitlines():
        line = raw.strip(" -#\t")
        if 8 <= len(line) <= 180:
            lines.append(line)
    return lines
