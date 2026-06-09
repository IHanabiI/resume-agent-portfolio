from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from src.schemas import JobPosting, JobWorkspace


def parse_job_workspace_upload(text: str) -> JobWorkspace:
    text = text.strip()
    if not text:
        return JobWorkspace()
    try:
        data = json.loads(text)
        if _looks_like_native_workspace(data):
            return JobWorkspace.model_validate(data)
        workspace = _parse_flexible_jobs_payload(data)
        if workspace.jobs:
            return workspace
        return JobWorkspace.model_validate(data)
    except Exception:
        return JobWorkspace(
            jobs=[
                JobPosting(
                    job_id=_new_id(),
                    title="导入的岗位",
                    jd_text=text,
                    status="待分析",
                    created_at=_now(),
                    updated_at=_now(),
                )
            ]
        )


def job_workspace_to_json_text(workspace: JobWorkspace) -> str:
    return json.dumps(workspace.model_dump(), ensure_ascii=False, indent=2)


def upsert_job(workspace: JobWorkspace, job: JobPosting) -> JobWorkspace:
    now = _now()
    if not job.job_id:
        job.job_id = _new_id()
    if not job.created_at:
        job.created_at = now
    job.updated_at = now
    jobs = [item for item in workspace.jobs if item.job_id != job.job_id]
    jobs.insert(0, job)
    workspace.jobs = jobs
    workspace.active_job_id = job.job_id
    return workspace


def update_job_status(
    workspace: JobWorkspace,
    job_id: str,
    status: str,
    match_score: int | None = None,
    last_resume_file: str = "",
    fit_recommendation: str = "",
    fit_risks: list[str] | None = None,
    fit_matched_points: list[str] | None = None,
    suggested_resume_angle: str = "",
) -> JobWorkspace:
    for job in workspace.jobs:
        if job.job_id != job_id:
            continue
        job.status = status  # type: ignore[assignment]
        if match_score is not None:
            job.match_score = max(0, min(100, match_score))
        if last_resume_file:
            job.last_resume_file = last_resume_file
        if fit_recommendation:
            job.fit_recommendation = fit_recommendation
        if fit_risks is not None:
            job.fit_risks = fit_risks
        if fit_matched_points is not None:
            job.fit_matched_points = fit_matched_points
        if suggested_resume_angle:
            job.suggested_resume_angle = suggested_resume_angle
        job.updated_at = _now()
        workspace.active_job_id = job.job_id
        break
    return workspace


def update_job_package(
    workspace: JobWorkspace,
    job_id: str,
    resume_markdown: str,
    opener_markdown: str,
    changelog_markdown: str,
    needs_confirmation: list[str] | None = None,
    placeholders: list[str] | None = None,
    evidence_map: list[dict] | None = None,
    last_resume_file: str = "tailored_resume.docx",
) -> JobWorkspace:
    for job in workspace.jobs:
        if job.job_id != job_id:
            continue
        job.status = "已生成简历"
        job.package_generated_at = _now()
        job.package_resume_markdown = resume_markdown
        job.package_opener_markdown = opener_markdown
        job.package_changelog_markdown = changelog_markdown
        job.package_needs_confirmation = needs_confirmation or []
        job.package_placeholders = placeholders or []
        job.package_evidence_map = evidence_map or []
        job.last_resume_file = last_resume_file
        job.updated_at = _now()
        workspace.active_job_id = job.job_id
        break
    return workspace


def get_active_job(workspace: JobWorkspace) -> JobPosting | None:
    if workspace.active_job_id:
        for job in workspace.jobs:
            if job.job_id == workspace.active_job_id:
                return job
    return workspace.jobs[0] if workspace.jobs else None


def infer_job_title_from_jd(jd_text: str) -> str:
    lines = [line.strip() for line in jd_text.splitlines() if line.strip()]
    for line in lines[:8]:
        if any(token in line for token in ["岗位", "职位", "招聘", "策划", "工程师", "实习"]):
            cleaned = re.sub(r"^(岗位名称|岗位|职位|招聘)[:：]?", "", line).strip()
            return cleaned[:80]
    return lines[0][:80] if lines else "未命名岗位"


def ranked_jobs(workspace: JobWorkspace) -> list[JobPosting]:
    status_rank = {
        "已生成简历": 5,
        "已分析": 4,
        "待分析": 3,
        "已收藏": 2,
    }
    return sorted(
        workspace.jobs,
        key=lambda job: (
            job.match_score,
            status_rank.get(job.status, 1),
            job.updated_at or job.created_at,
        ),
        reverse=True,
    )


def shortlist_to_json_text(workspace: JobWorkspace) -> str:
    rows = [
        {
            "company": job.company,
            "title": job.title,
            "match_score": job.match_score,
            "status": job.status,
            "platform": job.platform,
            "location": job.location,
            "salary": job.salary,
            "source_url": job.source_url,
            "recommendation": job.fit_recommendation,
            "risks": job.fit_risks,
            "suggested_resume_angle": job.suggested_resume_angle,
            "package_generated_at": job.package_generated_at,
            "notes": job.notes,
            "last_resume_file": job.last_resume_file,
            "updated_at": job.updated_at,
        }
        for job in ranked_jobs(workspace)
    ]
    return json.dumps({"version": workspace.version, "shortlist": rows}, ensure_ascii=False, indent=2)


def _parse_flexible_jobs_payload(data: Any) -> JobWorkspace:
    jobs_raw = _extract_jobs_list(data)
    root_company = _extract_company_name(_pick(data, "company", "company_name", "companyName")) if isinstance(data, dict) else ""
    jobs: list[JobPosting] = []
    now = _now()
    seen: set[str] = set()
    for raw in jobs_raw:
        if not isinstance(raw, dict):
            continue
        job = _job_from_mapping(raw, root_company, now)
        if not job.jd_text.strip() and not job.title.strip():
            continue
        dedupe_key = "|".join(
            [
                job.source_url.strip().lower(),
                job.company.strip().lower(),
                job.title.strip().lower(),
                job.jd_text[:200].strip().lower(),
            ]
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        jobs.append(job)
    active_job_id = jobs[0].job_id if jobs else ""
    return JobWorkspace(active_job_id=active_job_id, jobs=jobs)


def _looks_like_native_workspace(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    jobs = data.get("jobs")
    if not isinstance(jobs, list):
        return False
    if data.get("active_job_id"):
        return True
    return any(isinstance(job, dict) and "jd_text" in job for job in jobs)


def _extract_jobs_list(data: Any) -> list[Any]:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for key in ("jobs", "data", "items", "results", "positions", "job_list", "jobList"):
        value = data.get(key)
        if isinstance(value, list):
            return value
    return []


def _job_from_mapping(raw: dict[str, Any], root_company: str, now: str) -> JobPosting:
    company = _extract_company_name(
        _pick(raw, "company", "company_name", "companyName", "company_full_name", "companyFullName", "employer")
    ) or root_company
    title = _clean_text(
        _pick(raw, "title", "job_title", "jobTitle", "position", "position_name", "positionName", "job_name", "jobName", "name")
    )
    source_url = _clean_text(_pick(raw, "source_url", "sourceUrl", "url", "job_url", "jobUrl", "apply_url", "applyUrl", "link"))
    platform = _clean_text(_pick(raw, "platform", "source", "site", "channel"))
    location = _format_value(_pick(raw, "location", "city", "work_location", "workLocation", "address"))
    salary = _format_value(_pick(raw, "salary", "salary_range", "salaryRange", "compensation", "pay"))
    requirements_summary = _format_value(_pick(raw, "requirements", "job_requirements", "jobRequirements"))
    tags = _extract_tags(raw)
    jd_text = _compose_jd_text(raw, title, company, platform, location, salary, requirements_summary, tags)

    return JobPosting(
        job_id=_clean_text(_pick(raw, "job_id", "jobId", "id")) or _new_id(),
        company=company,
        title=title or infer_job_title_from_jd(jd_text),
        source_url=source_url,
        platform=platform,
        location=location,
        salary=salary,
        requirements_summary=requirements_summary,
        tags=tags,
        jd_text=jd_text,
        status="待分析",
        notes=_clean_text(_pick(raw, "notes", "note", "remark", "memo")),
        created_at=_clean_text(_pick(raw, "created_at", "createdAt", "captured_at", "capturedAt", "exported_at", "exportedAt")) or now,
        updated_at=_clean_text(_pick(raw, "updated_at", "updatedAt")) or now,
    )


def _compose_jd_text(
    raw: dict[str, Any],
    title: str,
    company: str,
    platform: str,
    location: str,
    salary: str,
    requirements_summary: str,
    tags: list[str],
) -> str:
    blocks: list[tuple[str, str]] = [
        ("公司", company),
        ("岗位", title),
        ("平台", platform),
        ("地点", location),
        ("薪资", salary),
        ("标签", "、".join(tags)),
        ("要求摘要", requirements_summary),
        ("岗位描述", _format_value(_pick(raw, "jd_text", "job_description", "jobDescription", "description", "desc", "content"))),
        ("岗位要求", _format_value(_pick(raw, "job_requirements", "jobRequirements", "responsibilities", "qualification", "qualifications"))),
        ("工作职责", _format_value(_pick(raw, "duties", "responsibilities", "job_responsibilities", "jobResponsibilities"))),
        ("加分项", _format_value(_pick(raw, "preferred", "preferred_skills", "preferredSkills", "nice_to_have", "niceToHave"))),
        ("公司介绍", _format_value(_pick(raw, "company_intro", "companyIntro", "company_description", "companyDescription"))),
        ("福利", _format_value(_pick(raw, "benefits", "welfare"))),
    ]
    lines: list[str] = []
    seen: set[str] = set()
    for label, value in blocks:
        cleaned = value.strip()
        if not cleaned:
            continue
        key = f"{label}:{cleaned}".lower()
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"{label}：{cleaned}")
    return "\n\n".join(lines)


def _pick(mapping: Any, *keys: str) -> Any:
    if not isinstance(mapping, dict):
        return ""
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return ""


def _extract_company_name(value: Any) -> str:
    if isinstance(value, dict):
        return _clean_text(_pick(value, "name", "company_name", "companyName", "full_name", "fullName"))
    return _clean_text(value)


def _extract_tags(raw: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("tags", "keywords", "skills", "labels"):
        value = raw.get(key)
        if isinstance(value, list):
            values.extend(_clean_text(item) for item in value)
        elif isinstance(value, str):
            values.extend(part.strip() for part in re.split(r"[,，/、;；\s]+", value) if part.strip())
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        if item and item.lower() not in seen:
            seen.add(item.lower())
            result.append(item)
    return result[:20]


def _format_value(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, str):
        return _clean_text(value)
    if isinstance(value, list):
        return "\n".join(f"- {_format_value(item)}" for item in value if _format_value(item))
    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            formatted = _format_value(item)
            if formatted:
                parts.append(f"{key}: {formatted}")
        return "\n".join(parts)
    return _clean_text(str(value))


def _clean_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
