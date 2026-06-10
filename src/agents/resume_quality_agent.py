from __future__ import annotations

import hashlib
import re

from src.schemas import ResumeQualityIssue, ResumeQualityReport, ResumeStarItem, ResumeStarProfile


SKIP_SECTION_TERMS = [
    "个人信息",
    "基本信息",
    "联系方式",
    "技能",
    "技术栈",
    "证书",
    "奖项",
    "荣誉",
    "自我评价",
    "个人简介",
    "求职意向",
]

EXPERIENCE_SECTION_TERMS = ["经历", "项目", "实习", "工作", "创业", "实践"]
WORKLIKE_SECTION_TERMS = ["工作", "实习", "项目", "创业", "实践", "兼职"]
EDUCATION_SECTION_TERMS = ["教育", "学历", "学校", "专业", "本科", "硕士", "博士"]
ORG_SUFFIXES = ("部", "组", "科", "岗", "中心", "团队", "部门", "事业部", "工作室", "小组")
ACTION_TERMS = [
    "负责",
    "主导",
    "设计",
    "推动",
    "搭建",
    "开发",
    "实现",
    "优化",
    "完成",
    "参与",
    "协作",
    "维护",
    "分析",
    "制定",
    "落地",
    "交付",
    "复盘",
    "提升",
    "降低",
    "增长",
    "减少",
    "负责",
    "built",
    "designed",
    "developed",
    "implemented",
    "optimized",
    "led",
    "created",
]
RESULT_TERMS = [
    "提升",
    "降低",
    "增长",
    "减少",
    "达到",
    "超过",
    "节省",
    "完成",
    "上线",
    "交付",
    "获得",
    "排名",
    "用户",
    "准确率",
    "效率",
    "转化",
    "收益",
    "increased",
    "reduced",
    "improved",
    "launched",
    "delivered",
]
METRIC_PATTERN = re.compile(r"(\d+(\.\d+)?\s*(%|k|K|w|W|万|千|人|次|天|小时|个月|年|元|美元|条|个|倍)?)")
DATE_PATTERN = re.compile(r"(\d{4}[./年-]\d{1,2}|20\d{2}|19\d{2}|至今|present)", re.IGNORECASE)
TECH_TERMS = [
    "python",
    "streamlit",
    "langgraph",
    "llm",
    "agent",
    "openai",
    "react",
    "vue",
    "javascript",
    "typescript",
    "sql",
    "docker",
    "github",
    "api",
    "pandas",
    "fastapi",
]


def assess_resume_quality(resume_text: str) -> tuple[ResumeQualityReport, ResumeStarProfile]:
    lines = _collect_lines(resume_text)
    resume_hash = hashlib.md5(resume_text.encode("utf-8", errors="ignore")).hexdigest()

    current_section = "未命名区块"
    evaluated = 0
    action_items: list[str] = []
    result_items: list[str] = []
    metric_items: list[str] = []
    empty_shell_items: list[str] = []
    missing_action_items: list[str] = []
    missing_result_items: list[str] = []
    missing_metric_items: list[str] = []
    star_items: list[ResumeStarItem] = []

    for line in lines:
        if _is_heading(line):
            current_section = _clean_heading(line)
            continue
        if _should_skip_section(current_section):
            continue
        if not _looks_like_experience_section(current_section) and not _looks_like_bullet(line):
            continue

        cleaned = _clean_line(line)
        if len(cleaned) < 8:
            continue

        has_action = _contains_action(cleaned)
        has_metric = _contains_metric(cleaned)
        has_result = _contains_any(cleaned, RESULT_TERMS) or has_metric
        is_empty_shell = _looks_like_empty_shell(cleaned, has_action, has_result)

        if is_empty_shell:
            empty_shell_items.append(cleaned)
            continue

        if has_action or has_result:
            evaluated += 1
            if has_action:
                action_items.append(cleaned)
            else:
                missing_action_items.append(cleaned)
            if has_result:
                result_items.append(cleaned)
            else:
                missing_result_items.append(cleaned)
            if has_metric:
                metric_items.append(cleaned)
            else:
                missing_metric_items.append(cleaned)
            star_items.append(_build_star_item(current_section, cleaned, has_action, has_result, not has_metric))

    score = _score_quality(evaluated, action_items, result_items, metric_items, empty_shell_items, missing_result_items)
    if score >= 75:
        status = "strong"
    elif score >= 50:
        status = "usable"
    else:
        status = "weak"

    issues = _build_issues(empty_shell_items, missing_action_items, missing_result_items, missing_metric_items)
    strengths = []
    if action_items:
        strengths.append(f"已有 {len(action_items)} 条经历写出了具体行动。")
    if result_items:
        strengths.append(f"已有 {len(result_items)} 条经历写出了结果或影响。")
    if metric_items:
        strengths.append(f"已有 {len(metric_items)} 条经历包含数字或规模信息。")
    if not strengths:
        strengths.append("当前简历缺少可直接用于岗位匹配的行动和结果描述。")

    recommended_fixes = []
    if empty_shell_items:
        recommended_fixes.append("优先补全空壳工作/项目经历：写清做了什么、怎么做、产生了什么结果。")
    if missing_result_items:
        recommended_fixes.append("为只有行动没有结果的条目补充结果，例如上线、交付、排名、效率、用户反馈或业务影响。")
    if missing_metric_items:
        recommended_fixes.append("为重点项目补充可确认数字；没有数字时保留事实，不要编造。")
    if not recommended_fixes:
        recommended_fixes.append("当前简历已有基本可用证据，可继续针对目标 JD 做排序和措辞优化。")

    summary = (
        f"识别到 {evaluated} 条可评估经历，{len(empty_shell_items)} 条空壳经历，"
        f"{len(missing_result_items)} 条缺结果，{len(missing_metric_items)} 条缺量化信息。"
    )
    report = ResumeQualityReport(
        score=score,
        status=status,  # type: ignore[arg-type]
        summary=summary,
        evaluated_items=evaluated,
        empty_shell_items=empty_shell_items[:12],
        missing_action_items=missing_action_items[:12],
        missing_result_items=missing_result_items[:12],
        missing_metric_items=missing_metric_items[:12],
        strengths=strengths,
        issues=issues[:20],
        recommended_fixes=recommended_fixes,
    )
    star = ResumeStarProfile(
        resume_hash=resume_hash,
        summary=f"已生成 {len(star_items)} 条 STAR 候选经历。",
        items=star_items[:50],
    )
    return report, star


def _collect_lines(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return [line.strip() for line in normalized.splitlines() if line.strip()]


def _is_heading(line: str) -> bool:
    if line.startswith("#"):
        return True
    if _looks_like_bullet(line):
        return False
    if len(line) <= 30 and any(term in line for term in SKIP_SECTION_TERMS):
        return True
    return len(line) <= 12 and any(term in line for term in EXPERIENCE_SECTION_TERMS)


def _clean_heading(line: str) -> str:
    return _clean_line(line).strip("# ：:")


def _clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip(" \t-*+•#"))


def _should_skip_section(section: str) -> bool:
    if _looks_like_mixed_work_education_section(section):
        return False
    if any(term in section for term in EDUCATION_SECTION_TERMS):
        return True
    return any(term in section for term in SKIP_SECTION_TERMS)


def _looks_like_experience_section(section: str) -> bool:
    return any(term in section for term in EXPERIENCE_SECTION_TERMS)


def _looks_like_mixed_work_education_section(section: str) -> bool:
    return any(term in section for term in WORKLIKE_SECTION_TERMS) and any(
        term in section for term in EDUCATION_SECTION_TERMS
    )


def _looks_like_bullet(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith(("-", "*", "+", "•")) or bool(re.match(r"^\d+[.、)]", stripped))


def _contains_any(text: str, terms: list[str]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


def _contains_metric(text: str) -> bool:
    date_spans = [match.span() for match in DATE_PATTERN.finditer(text)]
    for match in METRIC_PATTERN.finditer(text):
        unit = match.group(3)
        if not unit:
            continue
        if any(match.start() >= start and match.end() <= end for start, end in date_spans):
            continue
        return True
    return False


def _contains_action(text: str) -> bool:
    lower = text.lower()
    for term in ACTION_TERMS:
        if re.fullmatch(r"[a-zA-Z]+", term):
            if term.lower() in lower:
                return True
            continue
        for match in re.finditer(re.escape(term), text):
            if not _action_term_is_org_label(text, match.start(), match.end()):
                return True
    return False


def _action_term_is_org_label(text: str, start: int, end: int) -> bool:
    after = text[end : end + 4]
    before = text[max(0, start - 4) : start]
    if after.startswith(ORG_SUFFIXES):
        return True
    if before.endswith(ORG_SUFFIXES) and not after.startswith(("了", "并", "和", "与", "、")):
        return True
    return False


def _looks_like_empty_shell(text: str, has_action: bool, has_result: bool) -> bool:
    if has_action or has_result:
        return False
    if DATE_PATTERN.search(text):
        return True
    if _looks_like_org_title_line(text):
        return True
    separators = ["|", "·", "，", ",", " ", "-", "—", "－"]
    return 2 <= sum(1 for sep in separators if sep in text) and len(text) <= 80


def _looks_like_org_title_line(text: str) -> bool:
    if len(text) > 80:
        return False
    has_org_suffix = any(suffix in text for suffix in ORG_SUFFIXES)
    has_header_separator = any(sep in text for sep in ["|", "·", "-", "—", "－", " "])
    has_company_hint = any(term in text for term in ["公司", "大学", "学院", "工作室", "团队"])
    return has_org_suffix and (has_header_separator or has_company_hint)


def _build_star_item(section: str, text: str, has_action: bool, has_result: bool, needs_metrics: bool) -> ResumeStarItem:
    skills = [term for term in TECH_TERMS if term in text.lower()]
    return ResumeStarItem(
        source_section=section,
        title=text[:60],
        situation=f"来自简历「{section}」区块。",
        task="需结合上下文确认具体任务。" if not has_action else "该条目已经包含行动描述，可进一步补充任务背景。",
        action=text if has_action else "",
        result=text if has_result else "",
        skills=skills,
        raw_text=text,
        has_action=has_action,
        has_result=has_result,
        needs_metrics=needs_metrics,
    )


def _score_quality(
    evaluated: int,
    action_items: list[str],
    result_items: list[str],
    metric_items: list[str],
    empty_shell_items: list[str],
    missing_result_items: list[str],
) -> int:
    score = 35
    score += min(25, len(action_items) * 5)
    score += min(25, len(result_items) * 5)
    score += min(15, len(metric_items) * 4)
    score -= min(30, len(empty_shell_items) * 8)
    score -= min(20, len(missing_result_items) * 3)
    if evaluated == 0:
        score = min(score, 30)
    return max(0, min(100, score))


def _build_issues(
    empty_shell_items: list[str],
    missing_action_items: list[str],
    missing_result_items: list[str],
    missing_metric_items: list[str],
) -> list[ResumeQualityIssue]:
    issues: list[ResumeQualityIssue] = []
    for item in empty_shell_items[:6]:
        issues.append(
            ResumeQualityIssue(
                severity="high",
                category="empty_shell",
                location=item[:80],
                problem="该经历只有标题、时间或组织信息，缺少可验证行动和结果。",
                suggestion="补充你具体做了什么、如何做、交付了什么结果。",
            )
        )
    for item in missing_result_items[:6]:
        issues.append(
            ResumeQualityIssue(
                severity="medium",
                category="missing_result",
                location=item[:80],
                problem="该条目写出了行动，但缺少结果或影响。",
                suggestion="补充上线、交付、排名、效率、反馈、规模或业务结果。",
            )
        )
    for item in missing_metric_items[:6]:
        issues.append(
            ResumeQualityIssue(
                severity="low",
                category="missing_metric",
                location=item[:80],
                problem="该条目缺少可确认数字。",
                suggestion="如有真实数据，补充人数、规模、周期、准确率、效率或使用量；没有则不要编造。",
            )
        )
    for item in missing_action_items[:4]:
        issues.append(
            ResumeQualityIssue(
                severity="medium",
                category="missing_action",
                location=item[:80],
                problem="该条目有结果倾向，但行动描述不够清楚。",
                suggestion="补充你采用的方法、工具、流程或协作方式。",
            )
        )
    return issues
