from __future__ import annotations

import re

from src.config import load_prompt
from src.llm_client import LLMClient
from src.schemas import CandidateProfile, EvidenceSnippet, ProjectExperience, WorkExperience


def parse_resume(resume_text: str, llm: LLMClient | None = None) -> CandidateProfile:
    llm = llm or LLMClient()
    if llm.settings.fast_analysis_mode:
        return _fallback_parse_resume(resume_text)
    prompt = load_prompt("resume_parser_prompt.md")
    result = llm.generate_structured(
        "你是严格的简历解析 Agent，只提取原文中存在的信息，不做推测。",
        f"{prompt}\n\n原始简历：\n{resume_text}",
        CandidateProfile,
    )
    if result:
        if not result.raw_evidence:
            result.raw_evidence = _evidence_lines(resume_text)
        return result
    return _fallback_parse_resume(resume_text)


def _fallback_parse_resume(text: str) -> CandidateProfile:
    lines = _evidence_lines(text)
    first_line = lines[0] if lines else ""
    name = first_line if len(first_line) <= 12 and not any(ch.isdigit() for ch in first_line) else ""
    email = re.search(r"[\w.+-]+@[\w.-]+\.\w+", text)
    phone = re.search(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)", text)
    contact = " / ".join(x for x in [phone.group(0) if phone else "", email.group(0) if email else ""] if x)

    skills = _collect_after_headers(lines, ["技能", "专业技能", "技术栈", "技能清单"], stop_headers=["项目", "工作", "教育", "证书"])
    education = [line for line in lines if any(k in line for k in ["大学", "学院", "本科", "硕士", "博士", "专科"])]
    certifications = [line for line in lines if any(k in line for k in ["证书", "认证", "资格"])]
    achievements = [line for line in lines if any(k in line for k in ["提升", "增长", "优化", "获奖", "负责", "完成"])]

    projects: list[ProjectExperience] = []
    for line in lines:
        if "项目" in line and len(line) <= 80:
            projects.append(ProjectExperience(name=line, evidence=[EvidenceSnippet(source_text=line)]))

    work_items = [line for line in lines if any(k in line for k in ["公司", "实习", "工作", "工程师", "运营", "产品"])]
    work_experience = [
        WorkExperience(company=item, responsibilities=[item], evidence=[EvidenceSnippet(source_text=item)])
        for item in work_items[:5]
    ]

    return CandidateProfile(
        name=name,
        contact=contact,
        education=education[:5],
        work_experience=work_experience,
        projects=projects[:5],
        skills=_split_keywords(skills),
        certifications=certifications[:5],
        achievements=achievements[:8],
        raw_evidence=lines[:80],
    )


def _evidence_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _collect_after_headers(lines: list[str], headers: list[str], stop_headers: list[str]) -> str:
    collecting = False
    values: list[str] = []
    for line in lines:
        if any(header in line for header in headers):
            collecting = True
            values.append(line)
            continue
        if collecting and any(header in line for header in stop_headers):
            break
        if collecting:
            values.append(line)
    return " ".join(values)


def _split_keywords(text: str) -> list[str]:
    parts = re.split(r"[,，、/|；;\s]+", text)
    return sorted({p.strip("：:()（）") for p in parts if 1 < len(p.strip()) <= 30})
