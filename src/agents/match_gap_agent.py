from __future__ import annotations

import re

from src.config import load_prompt
from src.llm_client import LLMClient, pretty_json
from src.requirement_classifier import (
    active_soft_groups,
    cluster_hard_requirements,
    filter_actionable_hard_requirements,
    has_soft_evidence,
    is_soft_requirement,
    soft_group_for_requirement,
    split_hard_and_soft_requirements,
)
from src.schemas import (
    CandidateProfile,
    GapAnalysis,
    JobAnalysis,
    QuestionItem,
    ResumeQualityReport,
    ResumeStarProfile,
    SoftEvidenceGap,
    UserAnswer,
)


def analyze_match_and_gap(
    candidate: CandidateProfile,
    job: JobAnalysis,
    resume_text: str,
    memory_text: str = "",
    github_context: str = "",
    user_answers: list[UserAnswer] | None = None,
    resume_quality: ResumeQualityReport | None = None,
    star_profile: ResumeStarProfile | None = None,
    llm: LLMClient | None = None,
) -> GapAnalysis:
    llm = llm or LLMClient()
    context = _build_context(resume_text, memory_text, github_context, user_answers or [], resume_quality, star_profile)
    if llm.settings.fast_analysis_mode:
        return _prune_answered_gap(_fallback_gap(candidate, job, context), user_answers or [])
    prompt = load_prompt("match_gap_prompt.md")
    result = llm.generate_structured(
        "你是匹配与缺口分析 Agent。不得把 JD 要求当成候选人已经具备的事实；只把原始简历、个人记忆库、GitHub 公开证据、用户回答中有来源的信息视为事实。",
        (
            f"{prompt}\n\n候选人结构化信息：\n{pretty_json(candidate)}\n\n岗位分析：\n{pretty_json(job)}"
            f"\n\n可用事实来源：\n{context}"
        ),
        GapAnalysis,
    )
    return _prune_answered_gap(_normalize_gap(result or _fallback_gap(candidate, job, context), candidate, job, context), user_answers or [])


def _build_context(
    resume_text: str,
    memory_text: str,
    github_context: str,
    user_answers: list[UserAnswer],
    resume_quality: ResumeQualityReport | None = None,
    star_profile: ResumeStarProfile | None = None,
) -> str:
    sections = []
    if star_profile and star_profile.items:
        star_lines = "\n".join(f"- {item.raw_text}" for item in star_profile.items if item.raw_text.strip())
        if star_lines.strip():
            sections.append(f"## 有效 STAR 证据\n{star_lines}")
    elif not resume_quality or resume_quality.evaluated_items > 0:
        sections.append(f"## 原始简历\n{resume_text}")
    elif resume_quality.empty_shell_items:
        sections.append(
            f"## 空壳经历提示\n原简历存在 {len(resume_quality.empty_shell_items)} 条只有标题、时间或组织信息的经历，不能作为能力证明。"
        )
    if memory_text.strip():
        sections.append(f"## 个人记忆库\n{memory_text}")
    if github_context.strip():
        sections.append(f"## GitHub 公开证据\n{github_context}")
    if user_answers:
        answer_text = "\n".join(
            f"- 问题：{answer.question}\n  回答：{answer.answer}\n  关联岗位要求：{answer.related_jd_requirement}"
            for answer in user_answers
            if answer.answer.strip()
        )
        if answer_text.strip():
            sections.append(f"## 已回答追问\n{answer_text}")
    return "\n\n".join(sections)


def _fallback_gap(candidate: CandidateProfile, job: JobAnalysis, context: str) -> GapAnalysis:
    context_blob = " ".join([context] + candidate.skills).lower()
    matched: list[str] = []
    missing: list[str] = []
    hard_gaps: list[str] = []
    soft_gaps: list[SoftEvidenceGap] = []
    questions: list[QuestionItem] = []

    requirements, _ = split_hard_and_soft_requirements(job.required_skills + job.keywords[:12])
    requirements = filter_actionable_hard_requirements(requirements)
    job_text = _job_text(job)

    for group in active_soft_groups(job_text):
        name = str(group["name"])
        if has_soft_evidence(group, context_blob):
            matched.append(f"已有与「{name}」相关的事实线索，可用于证明 JD 中的软性能力要求。")
            continue
        soft_gap = SoftEvidenceGap(
            requirement=name,
            evidence_needed=str(group["evidence_needed"]),
            current_status="missing",
            suggested_question=str(group["question"]),
        )
        soft_gaps.append(soft_gap)
        missing.append(f"软性证据缺口：JD 强调「{name}」，但当前材料缺少可验证场景。建议补充：{soft_gap.evidence_needed}")
        if len(questions) < 3:
            questions.append(
                QuestionItem(
                    question=soft_gap.suggested_question,
                    why_needed="软性能力不能只写标签，必须用具体经历证明，避免空泛表述。",
                    related_jd_requirement=name,
                )
            )

    for skill in requirements:
        if skill.lower() in context_blob:
            matched.append(f"在现有事实来源中找到了与「{skill}」相关的信息，可作为岗位匹配点。")
        else:
            hard_gaps.append(skill)
            missing.append(f"硬技能缺口：未找到「{skill}」的明确经历或证据。")
    for group in cluster_hard_requirements(hard_gaps):
        if len(questions) >= 5:
            break
        related = "、".join(str(item) for item in group.get("requirements", []) if str(item).strip())
        questions.append(
            QuestionItem(
                question=str(group["question"]),
                why_needed=f"用于判断是否可以把「{group['name']}」写入定制简历，避免逐个关键词机械追问或无来源补写。",
                related_jd_requirement=related or str(group["name"]),
            )
        )

    if len(questions) < 5 and not _has_project_context(context):
        questions.append(
            QuestionItem(
                question="你是否有与目标岗位相关、但原始简历没有写出的项目、实习、课程设计、开源仓库或自动化工具经历？请补充事实和证据。",
                why_needed="用于扩展个人记忆库，让 Agent 不只依赖原始简历。",
                related_jd_requirement="隐藏经历挖掘",
            )
        )
    if len(questions) < 5 and not _has_metric_context(context):
        questions.append(
            QuestionItem(
                question="这些经历是否有可确认数据，例如处理规模、交付周期、用户数、节省时间、准确率或效率提升？没有数据可以回答“没有”。",
                why_needed="用于增强结果导向表达；没有数据时不会自动编造。",
                related_jd_requirement="结果量化",
            )
        )

    return GapAnalysis(
        matched_strengths=_dedupe(matched)[:8],
        missing_information=_dedupe(missing)[:8],
        hard_skill_gaps=_dedupe(hard_gaps)[:8],
        soft_evidence_gaps=soft_gaps[:6],
        questions_to_user=_dedupe_questions(questions)[:5],
    )


def _normalize_gap(gap: GapAnalysis, candidate: CandidateProfile, job: JobAnalysis, context: str) -> GapAnalysis:
    fallback = _fallback_gap(candidate, job, context)
    hard_gaps = filter_actionable_hard_requirements(_dedupe(gap.hard_skill_gaps + fallback.hard_skill_gaps))
    soft_gaps = _merge_soft_gaps(gap.soft_evidence_gaps, fallback.soft_evidence_gaps)

    legacy_missing = [
        item
        for item in gap.missing_information
        if not _looks_like_soft_keyword_missing(item)
    ]
    missing = _dedupe(legacy_missing + fallback.missing_information)
    questions = _dedupe_questions(fallback.questions_to_user + _filter_legacy_soft_questions(gap.questions_to_user))
    matched = _dedupe(gap.matched_strengths + fallback.matched_strengths)

    return GapAnalysis(
        matched_strengths=matched[:8],
        missing_information=missing[:8],
        hard_skill_gaps=hard_gaps[:8],
        soft_evidence_gaps=soft_gaps[:6],
        questions_to_user=questions[:5],
    )


def _prune_answered_gap(gap: GapAnalysis, user_answers: list[UserAnswer]) -> GapAnalysis:
    answered_requirements = {
        answer.related_jd_requirement.strip().lower()
        for answer in user_answers
        if answer.answer.strip() and answer.related_jd_requirement.strip()
    }
    if not answered_requirements:
        return gap
    answered_tokens = _requirement_tokens(answered_requirements)
    hard_gaps = [
        item
        for item in gap.hard_skill_gaps
        if not _requirement_already_answered(item, answered_requirements, answered_tokens)
    ]
    soft_gaps = [
        item
        for item in gap.soft_evidence_gaps
        if not _requirement_already_answered(item.requirement, answered_requirements, answered_tokens)
    ]
    questions = [
        item
        for item in gap.questions_to_user
        if not _requirement_already_answered(item.related_jd_requirement, answered_requirements, answered_tokens)
    ]
    missing = [
        item
        for item in gap.missing_information
        if not _missing_item_answered(item, answered_requirements, answered_tokens)
    ]
    return GapAnalysis(
        matched_strengths=gap.matched_strengths,
        missing_information=missing,
        hard_skill_gaps=hard_gaps,
        soft_evidence_gaps=soft_gaps,
        questions_to_user=questions,
    )


def _job_text(job: JobAnalysis) -> str:
    return "\n".join(
        [
            job.job_title,
            *job.core_responsibilities,
            *job.required_skills,
            *job.preferred_skills,
            *job.keywords,
            *job.recruiter_focus,
        ]
    )


def _has_project_context(context: str) -> bool:
    lowered = context.lower()
    if any(term in lowered for term in ["github", "gitlab", "gitee", "repo", "repository"]):
        return True
    project_terms = ["项目", "github", "开源", "仓库", "mod", "agent", "工具", "系统", "模块"]
    return sum(1 for term in project_terms if term in lowered) >= 2


def _has_metric_context(context: str) -> bool:
    lowered = context.lower()
    metric_terms = ["浏览量", "点赞", "下载", "用户", "群", "效率", "准确率", "提升", "节省", "交付周期"]
    digit_count = sum(1 for ch in context if ch.isdigit())
    has_number = digit_count >= 2 or any(term in lowered for term in ["w", "万", "百", "千"])
    has_metric_word = any(term in lowered for term in metric_terms)
    return has_number and (has_metric_word or digit_count >= 3)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        value = item.strip()
        key = value.lower()
        if value and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _dedupe_questions(questions: list[QuestionItem]) -> list[QuestionItem]:
    seen: set[str] = set()
    result: list[QuestionItem] = []
    for question in questions:
        key = f"{question.related_jd_requirement.strip().lower()}::{question.question.strip().lower()}"
        if question.question.strip() and key not in seen:
            seen.add(key)
            result.append(question)
    return result


def _filter_legacy_soft_questions(questions: list[QuestionItem]) -> list[QuestionItem]:
    result: list[QuestionItem] = []
    seen_soft_groups: set[str] = set()
    for question in questions:
        requirement = question.related_jd_requirement.strip()
        text = question.question.strip()
        if not requirement and not text:
            continue
        group = soft_group_for_requirement(requirement) or soft_group_for_requirement(text)
        if group:
            name = str(group["name"])
            if name in seen_soft_groups:
                continue
            seen_soft_groups.add(name)
            result.append(
                QuestionItem(
                    question=str(group["question"]),
                    why_needed="软性能力不能只写标签，必须用具体经历证明，避免空泛表述。",
                    related_jd_requirement=name,
                )
            )
            continue
        if is_soft_requirement(requirement) or _looks_like_legacy_generic_soft_question(text) or _looks_like_legacy_keyword_question(text):
            continue
        result.append(question)
    return result


def _merge_soft_gaps(primary: list[SoftEvidenceGap], fallback: list[SoftEvidenceGap]) -> list[SoftEvidenceGap]:
    by_key: dict[str, SoftEvidenceGap] = {}
    for gap in primary + fallback:
        key = gap.requirement.strip().lower()
        if key and key not in by_key:
            by_key[key] = gap
    return list(by_key.values())


def _looks_like_soft_keyword_missing(text: str) -> bool:
    soft_terms = ["沟通", "协作", "团队", "逻辑", "表达", "主动", "推动", "用户体验", "反馈", "细节"]
    return text.startswith("未找到") and any(term in text for term in soft_terms)


def _looks_like_legacy_generic_soft_question(text: str) -> bool:
    return text.startswith("JD 提到") and any(term in text for term in ["沟通", "协作", "团队", "逻辑", "表达", "用户体验", "反馈", "细节"])


def _looks_like_legacy_keyword_question(text: str) -> bool:
    return text.startswith("JD 提到") and "你是否有真实使用或相关项目经历" in text


def _requirement_tokens(requirements: set[str]) -> set[str]:
    tokens: set[str] = set()
    for requirement in requirements:
        for token in re.split(r"[、,，/｜|;；\s]+", requirement):
            cleaned = token.strip().lower()
            if len(cleaned) >= 2:
                tokens.add(cleaned)
    return tokens


def _requirement_already_answered(requirement: str, answered_requirements: set[str], answered_tokens: set[str]) -> bool:
    target = requirement.strip().lower()
    if not target:
        return False
    if any(target == item or target in item or item in target for item in answered_requirements):
        return True
    tokens = _requirement_tokens({target})
    if not tokens:
        return False
    if tokens & answered_tokens:
        return True
    joined_answered = "\n".join(answered_requirements)
    return any(token in joined_answered for token in tokens)


def _missing_item_answered(text: str, answered_requirements: set[str], answered_tokens: set[str]) -> bool:
    lowered = text.lower()
    return any(item and item in lowered for item in answered_requirements) or any(token in lowered for token in answered_tokens)
