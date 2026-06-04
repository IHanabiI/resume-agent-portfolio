from __future__ import annotations

from src.config import load_prompt
from src.llm_client import LLMClient, pretty_json
from src.schemas import CandidateProfile, GapAnalysis, JobAnalysis, QuestionItem


def analyze_match_and_gap(
    candidate: CandidateProfile,
    job: JobAnalysis,
    resume_text: str,
    llm: LLMClient | None = None,
) -> GapAnalysis:
    llm = llm or LLMClient()
    prompt = load_prompt("match_gap_prompt.md")
    result = llm.generate_structured(
        "你是匹配与缺口分析 Agent。不得把 JD 要求当成候选人已经具备的事实。",
        f"{prompt}\n\n候选人信息：\n{pretty_json(candidate)}\n\n岗位分析：\n{pretty_json(job)}\n\n原始简历：\n{resume_text}",
        GapAnalysis,
    )
    return result or _fallback_gap(candidate, job, resume_text)


def _fallback_gap(candidate: CandidateProfile, job: JobAnalysis, resume_text: str) -> GapAnalysis:
    resume_blob = " ".join([resume_text] + candidate.skills).lower()
    matched: list[str] = []
    missing: list[str] = []
    questions: list[QuestionItem] = []

    for skill in job.required_skills + job.keywords[:8]:
        if not skill:
            continue
        if skill.lower() in resume_blob:
            matched.append(f"简历中出现了与「{skill}」相关的信息，可作为岗位匹配点。")
        else:
            missing.append(f"未找到「{skill}」的明确经历或证据。")
            if len(questions) < 5:
                questions.append(
                    QuestionItem(
                        question=f"JD 提到「{skill}」。你是否有真实使用或相关项目经历？请说明具体场景、你的职责和可确认成果；如果没有可回答“没有”或“跳过”。",
                        why_needed="用于判断是否可以把该能力写入定制简历，避免无来源补写。",
                        related_jd_requirement=skill,
                    )
                )

    if not questions:
        questions.append(
            QuestionItem(
                question="目标岗位强调的项目成果是否有可确认数据，例如处理规模、交付周期、用户数、节省时间或提升效果？没有数据可以回答“没有”。",
                why_needed="用于增强结果导向表达；没有数据时不会自动编造。",
                related_jd_requirement="结果量化",
            )
        )
    return GapAnalysis(
        matched_strengths=matched[:8],
        missing_information=missing[:8],
        questions_to_user=questions[:5],
    )

