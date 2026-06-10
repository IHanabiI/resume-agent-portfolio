from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.config import WORKSPACE_DIR


WORKSPACE_VERSION = "1.0"


class WorkspaceSnapshot(BaseModel):
    version: str = WORKSPACE_VERSION
    workspace_id: str = ""
    updated_at: str = ""
    resume_text: str = ""
    resume_raw_text: str = ""
    resume_template_docx_name: str = ""
    resume_template_docx_bytes_b64: str = ""
    job_description: str = ""
    memory_text: str = ""
    github_input: str = ""
    github_context: str = ""
    session_context_text: str = ""
    question_answer_drafts: dict[str, str] = Field(default_factory=dict)
    active_job_id: str = ""
    job_company: str = ""
    job_title: str = ""
    job_source_url: str = ""
    job_notes: str = ""
    job_status: str = "待分析"
    job_workspace: dict[str, Any] = Field(default_factory=dict)
    cumulative_answers: list[dict[str, Any]] = Field(default_factory=list)
    memory_candidates: list[dict[str, Any]] = Field(default_factory=list)
    last_tailored_resume: dict[str, Any] = Field(default_factory=dict)
    last_fact_check: dict[str, Any] = Field(default_factory=dict)


def workspace_id_for_key(user_key: str, salt: str = "") -> str:
    normalized = user_key.strip()
    if not normalized:
        raise ValueError("工作区 Key 不能为空。")
    material = f"{salt or 'resume-agent-workspace'}::{normalized}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:24]


def workspace_path(workspace_id: str) -> Path:
    _ensure_dir()
    return WORKSPACE_DIR / f"{workspace_id}.json"


def load_workspace(user_key: str, salt: str = "") -> WorkspaceSnapshot | None:
    workspace_id = workspace_id_for_key(user_key, salt)
    path = workspace_path(workspace_id)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    data["workspace_id"] = workspace_id
    return WorkspaceSnapshot.model_validate(data)


def save_workspace(user_key: str, snapshot: WorkspaceSnapshot, salt: str = "") -> WorkspaceSnapshot:
    workspace_id = workspace_id_for_key(user_key, salt)
    snapshot.workspace_id = workspace_id
    snapshot.updated_at = _now()
    path = workspace_path(workspace_id)
    path.write_text(json.dumps(snapshot.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    return snapshot


def delete_workspace(user_key: str, salt: str = "") -> bool:
    workspace_id = workspace_id_for_key(user_key, salt)
    path = workspace_path(workspace_id)
    if not path.exists():
        return False
    path.unlink()
    return True


def workspace_to_json_text(snapshot: WorkspaceSnapshot) -> str:
    return json.dumps(snapshot.model_dump(), ensure_ascii=False, indent=2)


def parse_workspace_json(text: str) -> WorkspaceSnapshot:
    return WorkspaceSnapshot.model_validate(json.loads(text))


def _ensure_dir() -> None:
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
