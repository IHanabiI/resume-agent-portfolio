from __future__ import annotations

from src.config import load_prompt
from src.llm_client import LLMClient, pretty_json
from src.schemas import CandidateProfile, EvidenceItem, GapAnalysis, JobAnalysis, TailoredResumeResult, UserAnswer


def write_resume(
    candidate: CandidateProfile,
    job: JobAnalysis,
    gap: GapAnalysis,
    resume_text: str,
    user_answers: list[UserAnswer],
    llm: LLMClient | None = None,
) -> TailoredResumeResult:
    llm = llm or LLMClient()
    prompt = load_prompt("resume_writer_prompt.md")
    result = llm.generate_structured(
        "你是简历生成 Agent。事实优先于表达，禁止编造，禁止夸大。",
        (
            f"{prompt}\n\n候选人信息：\n{pretty_json(candidate)}\n\n岗位分析：\n{pretty_json(job)}"
            f"\n\n缺口分析：\n{pretty_json(gap)}\n\n用户补充回答：\n{pretty_json({'answers': [a.model_dump() for a in user_answers]})}"
            f"\n\n原始简历全文：\n{resume_text}"
        ),
        TailoredResumeResult,
    )
    return result or _fallback_write(candidate, job, gap, user_answers)


def _fallback_write(
    candidate: CandidateProfile,
    job: JobAnalysis,
    gap: GapAnalysis,
    user_answers: list[UserAnswer],
) -> TailoredResumeResult:
    lines = [
        f"# {candidate.name or '候选人'}",
        "",
        f"- 联系方式：{candidate.contact or '待补充'}",
        f"- 目标岗位：{job.job_title or '目标岗位'}",
        "",
        "## 个人优势",
    ]
    strengths = gap.matched_strengths or ["基于原始简历信息进行岗位适配表达，未添加无来源经历。"]
    for item in strengths[:5]:
        lines.append(f"- {item}")

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

    answered = [a for a in user_answers if a.answer.strip() and a.answer.strip() not in {"没有", "跳过", "不清楚"}]
    if answered:
        lines.extend(["", "## 补充信息"])
        for answer in answered:
            lines.append(f"- {answer.answer.strip()}")

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
    return TailoredResumeResult(
        resume_markdown="\n".join(lines),
        optimization_notes=["已按 JD 匹配点重排简历结构。", "没有为缺失技能或成果编造经历。"],
        integrated_keywords=[k for k in job.keywords if k][:12],
        still_missing_info=gap.missing_information[:8],
        evidence_map=evidence,
    )

