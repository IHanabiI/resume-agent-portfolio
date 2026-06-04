from __future__ import annotations

import re

from src.config import load_prompt
from src.llm_client import LLMClient
from src.schemas import JobAnalysis


COMMON_SKILLS = [
    "Python", "SQL", "Excel", "Tableau", "Power BI", "机器学习", "数据分析", "Streamlit",
    "LangGraph", "OpenAI", "Pydantic", "Java", "JavaScript", "TypeScript", "React",
    "Vue", "Docker", "Kubernetes", "Linux", "沟通", "协作", "项目管理", "A/B测试",
]


def analyze_jd(job_description: str, llm: LLMClient | None = None) -> JobAnalysis:
    llm = llm or LLMClient()
    prompt = load_prompt("jd_analyzer_prompt.md")
    result = llm.generate_structured(
        "你是岗位 JD 分析 Agent，只根据 JD 文本提取岗位要求。",
        f"{prompt}\n\n目标岗位 JD：\n{job_description}",
        JobAnalysis,
    )
    return result or _fallback_analyze_jd(job_description)


def _fallback_analyze_jd(text: str) -> JobAnalysis:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    title = ""
    for line in lines[:8]:
        if any(k in line for k in ["岗位", "职位", "招聘", "工程师", "分析师", "经理"]):
            title = re.sub(r"^(岗位名称|岗位|职位|招聘)[:：]?", "", line).strip()
            break
    skills = [skill for skill in COMMON_SKILLS if skill.lower() in text.lower()]
    responsibilities = [line for line in lines if any(k in line for k in ["负责", "参与", "完成", "建设", "分析", "优化"])]
    preferred = [line for line in lines if any(k in line for k in ["加分", "优先", "最好", "熟悉"])]
    focus = [line for line in lines if any(k in line for k in ["要求", "能力", "经验", "关注"])]
    keywords = sorted(set(skills + _extract_cn_keywords(text)))
    return JobAnalysis(
        job_title=title or "目标岗位",
        core_responsibilities=responsibilities[:8],
        required_skills=skills[:12],
        preferred_skills=preferred[:8],
        keywords=keywords[:20],
        recruiter_focus=focus[:8],
    )


def _extract_cn_keywords(text: str) -> list[str]:
    candidates = ["数据", "用户", "增长", "业务", "产品", "模型", "自动化", "报表", "指标", "需求", "交付"]
    return [word for word in candidates if word in text]
