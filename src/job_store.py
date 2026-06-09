from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone

from src.schemas import JobPosting, JobWorkspace


def parse_job_workspace_upload(text: str) -> JobWorkspace:
    text = text.strip()
    if not text:
        return JobWorkspace()
    try:
        data = json.loads(text)
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
) -> JobWorkspace:
    for job in workspace.jobs:
        if job.job_id != job_id:
            continue
        job.status = status  # type: ignore[assignment]
        if match_score is not None:
            job.match_score = max(0, min(100, match_score))
        if last_resume_file:
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


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
