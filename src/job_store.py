from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from src.schemas import JobPosting, JobWorkspace


def parse_job_workspace_upload(text: str) -> JobWorkspace:
    workspace, _report = parse_job_workspace_upload_with_report(text)
    return workspace


def parse_job_workspace_upload_with_report(text: str) -> tuple[JobWorkspace, dict[str, Any]]:
    text = text.strip()
    if not text:
        return JobWorkspace(), _new_import_report(
            source_type="empty",
            errors=["文件内容为空，没有导入岗位。"],
        )
    try:
        data = json.loads(text)
        if _looks_like_native_workspace(data):
            workspace = JobWorkspace.model_validate(data)
            return workspace, _new_import_report(
                source_type="job_workspace",
                imported_count=len(workspace.jobs),
                recognized_fields=_recognized_workspace_fields(data),
                warnings=_workspace_warnings(workspace),
            )
        workspace, report = _parse_flexible_jobs_payload_with_report(data)
        if workspace.jobs:
            return workspace, report
        workspace = JobWorkspace.model_validate(data)
        return workspace, _new_import_report(
            source_type="job_workspace",
            imported_count=len(workspace.jobs),
            recognized_fields=_recognized_workspace_fields(data),
            warnings=_workspace_warnings(workspace),
        )
    except json.JSONDecodeError as exc:
        if text.startswith("{") or text.startswith("["):
            return JobWorkspace(), _new_import_report(
                source_type="invalid_json",
                errors=[f"JSON 解析失败：第 {exc.lineno} 行第 {exc.colno} 列，{exc.msg}。"],
            )
        workspace = _plain_text_workspace(text)
        return workspace, _new_import_report(
            source_type="plain_text",
            imported_count=len(workspace.jobs),
            warnings=["未识别为 JSON，已按单条 JD 文本导入。"],
        )
    except Exception as exc:
        if text.startswith("{") or text.startswith("["):
            return JobWorkspace(), _new_import_report(
                source_type="invalid_json",
                errors=[f"JSON 结构不符合岗位库格式：{exc}"],
            )
        workspace = _plain_text_workspace(text)
        return workspace, _new_import_report(
            source_type="plain_text",
            imported_count=len(workspace.jobs),
            warnings=["未识别为岗位库 JSON，已按单条 JD 文本导入。"],
        )


def job_workspace_template_json() -> str:
    now = _now()
    sample = {
        "version": "1.0",
        "jobs": [
            {
                "company": "示例游戏公司",
                "title": "玩法策划",
                "source_url": "https://example.com/jobs/game-designer",
                "platform": "Boss直聘 / 官网 / 猎聘",
                "location": "上海",
                "salary": "15-25K",
                "tags": ["玩法策划", "系统设计", "数值", "UE/Unity"],
                "jd_text": "岗位职责：\n- 负责核心玩法机制、系统规则和关卡体验设计。\n- 基于数据和玩家反馈迭代版本体验。\n\n任职要求：\n- 有完整项目或 Demo 经验。\n- 能输出清晰的策划案、原型和验收标准。",
                "notes": "重点测试玩法循环、系统拆解和项目落地表达。",
                "created_at": now,
                "updated_at": now,
            }
        ],
    }
    return json.dumps(sample, ensure_ascii=False, indent=2)


def job_import_supported_fields() -> dict[str, list[str]]:
    return {
        "岗位列表容器": ["jobs", "data", "items", "results", "positions", "job_list", "jobList"],
        "公司": ["company", "company_name", "companyName", "company_full_name", "companyFullName", "employer"],
        "岗位名称": ["title", "job_title", "jobTitle", "position", "position_name", "positionName", "job_name", "jobName", "name"],
        "岗位链接": ["source_url", "sourceUrl", "url", "job_url", "jobUrl", "apply_url", "applyUrl", "link"],
        "平台": ["platform", "source", "site", "channel"],
        "地点": ["location", "city", "work_location", "workLocation", "address"],
        "薪资": ["salary", "salary_range", "salaryRange", "compensation", "pay"],
        "标签": ["tags", "keywords", "skills", "labels"],
        "JD 正文": ["jd_text", "job_description", "jobDescription", "description", "desc", "content"],
        "岗位要求": ["job_requirements", "jobRequirements", "requirements", "qualification", "qualifications"],
        "工作职责": ["duties", "responsibilities", "job_responsibilities", "jobResponsibilities"],
        "加分项": ["preferred", "preferred_skills", "preferredSkills", "nice_to_have", "niceToHave"],
        "备注": ["notes", "note", "remark", "memo"],
    }


def _plain_text_workspace(text: str) -> JobWorkspace:
    now = _now()
    return JobWorkspace(
        jobs=[
            JobPosting(
                job_id=_new_id(),
                title="导入的岗位",
                jd_text=text,
                status="待分析",
                created_at=now,
                updated_at=now,
            )
        ]
    )


def _new_import_report(
    source_type: str,
    imported_count: int = 0,
    skipped_count: int = 0,
    recognized_fields: list[str] | None = None,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "source_type": source_type,
        "imported_count": imported_count,
        "skipped_count": skipped_count,
        "recognized_fields": recognized_fields or [],
        "warnings": warnings or [],
        "errors": errors or [],
    }


def _workspace_warnings(workspace: JobWorkspace) -> list[str]:
    warnings: list[str] = []
    if not workspace.jobs:
        warnings.append("岗位列表为空。请确认 JSON 中存在 jobs/data/items 等岗位数组。")
    missing_jd = sum(1 for job in workspace.jobs if not job.jd_text.strip())
    if missing_jd:
        warnings.append(f"{missing_jd} 个岗位缺少 JD 正文，后续无法分析。")
    missing_title = sum(1 for job in workspace.jobs if not job.title.strip())
    if missing_title:
        warnings.append(f"{missing_title} 个岗位缺少岗位名称，系统会尝试从 JD 第一行推断。")
    return warnings


def _recognized_workspace_fields(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return []
    recognized: list[str] = []
    for key in ("version", "active_job_id", "jobs"):
        if key in data:
            recognized.append(key)
    return recognized


def _parse_flexible_jobs_payload_with_report(data: Any) -> tuple[JobWorkspace, dict[str, Any]]:
    jobs_raw = _extract_jobs_list(data)
    root_company = _extract_company_name(_pick(data, "company", "company_name", "companyName")) if isinstance(data, dict) else ""
    jobs: list[JobPosting] = []
    now = _now()
    seen: set[str] = set()
    skipped_count = 0
    warnings: list[str] = []
    recognized_fields: set[str] = set()
    for raw in jobs_raw:
        if not isinstance(raw, dict):
            skipped_count += 1
            continue
        recognized_fields.update(_recognized_job_fields(raw))
        job = _job_from_mapping(raw, root_company, now)
        if not job.jd_text.strip() and not job.title.strip():
            skipped_count += 1
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
            skipped_count += 1
            continue
        seen.add(dedupe_key)
        jobs.append(job)
    if not jobs_raw:
        warnings.append("没有找到岗位数组。支持的容器字段包括 jobs、data、items、results、positions、job_list、jobList。")
    workspace = JobWorkspace(active_job_id=jobs[0].job_id if jobs else "", jobs=jobs)
    warnings.extend(_workspace_warnings(workspace))
    return workspace, _new_import_report(
        source_type="flexible_jobs_json",
        imported_count=len(jobs),
        skipped_count=skipped_count,
        recognized_fields=sorted(recognized_fields),
        warnings=warnings,
    )


def _recognized_job_fields(raw: dict[str, Any]) -> list[str]:
    recognized: list[str] = []
    for group in job_import_supported_fields().values():
        for key in group:
            if key in raw:
                recognized.append(key)
    return recognized


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
    workspace, _report = _parse_flexible_jobs_payload_with_report(data)
    return workspace


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
