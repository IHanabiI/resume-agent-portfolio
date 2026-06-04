from __future__ import annotations

from src.config import load_prompt
from src.llm_client import LLMClient, pretty_json
from src.schemas import CandidateProfile, GapAnalysis, JobAnalysis, QuestionItem


def analyze_match_and_gap(
    candidate: CandidateProfile,
    job: JobAnalysis,
    resume_text: str,
    memory_text: str = "",
    github_context: str = "",
    llm: LLMClient | None = None,
) -> GapAnalysis:
    llm = llm or LLMClient()
    prompt = load_prompt("match_gap_prompt.md")
    context = _build_context(resume_text, memory_text, github_context)
    result = llm.generate_structured(
        "你是匹配与缺口分析 Agent。不得把 JD 要求当成候选人已经具备的事实；只把原始简历、个人记忆库、GitHub 公开证据、用户回答中有来源的信息视为事实。",
        (
            f"{prompt}\n\n候选人结构化信息：\n{pretty_json(candidate)}\n\n岗位分析：\n{pretty_json(job)}"
            f"\n\n可用事实来源：\n{context}"
        ),
        GapAnalysis,
    )
    return result or _fallback_gap(candidate, job, context)


def _build_context(resume_text: str, memory_text: str, github_context: str) -> str:
    sections = [f"## 原始简历\n{resume_text}"]
    if memory_text.strip():
        sections.append(f"## 个人记忆库\n{memory_text}")
    if github_context.strip():
        sections.append(f"## GitHub 公开证据\n{github_context}")
    return "\n\n".join(sections)


def _fallback_gap(candidate: CandidateProfile, job: JobAnalysis, context: str) -> GapAnalysis:
    context_blob = " ".join([context] + candidate.skills).lower()
    matched: list[str] = []
    missing: list[str] = []
    questions: list[QuestionItem] = []

    requirements = [item for item in job.required_skills + job.keywords[:10] if item]
    for skill in requirements:
        if skill.lower() in context_blob:
            matched.append(f"在现有事实来源中找到了与「{skill}」相关的信息，可作为岗位匹配点。")
        else:
            missing.append(f"未找到「{skill}」的明确经历或证据。")
            if len(questions) < 5:
                questions.append(
                    QuestionItem(
                        question=(
                            f"JD 提到「{skill}」。你是否有真实使用或相关项目经历？"
                            "请说明具体场景、你的职责、使用工具和可确认成果；如果没有，请回答“没有”或“跳过”。"
                        ),
                        why_needed="用于判断是否可以把该能力写入定制简历，避免无来源补写。",
                        related_jd_requirement=skill,
                    )
                )

    if len(questions) < 5:
        questions.append(
            QuestionItem(
                question="你是否有与目标岗位相关、但原始简历没有写出的项目、实习、课程设计、开源仓库或自动化工具经历？请补充事实和证据。",
                why_needed="用于扩展个人记忆库，让 Agent 不只依赖原始简历。",
                related_jd_requirement="隐藏经历挖掘",
            )
        )
    if len(questions) < 5:
        questions.append(
            QuestionItem(
                question="这些经历是否有可确认数据，例如处理规模、交付周期、用户数、节省时间、准确率或效率提升？没有数据可以回答“没有”。",
                why_needed="用于增强结果导向表达；没有数据时不会自动编造。",
                related_jd_requirement="结果量化",
            )
        )

    return GapAnalysis(
        matched_strengths=matched[:8],
        missing_information=missing[:8],
        questions_to_user=questions[:5],
    )
