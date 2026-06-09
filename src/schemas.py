from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EvidenceSnippet(BaseModel):
    source_type: Literal["original_resume", "user_answer", "user_confirmed", "user_memory", "github"] = "original_resume"
    source_text: str = ""


class WorkExperience(BaseModel):
    company: str = ""
    title: str = ""
    period: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    evidence: list[EvidenceSnippet] = Field(default_factory=list)


class ProjectExperience(BaseModel):
    name: str = ""
    role: str = ""
    period: str = ""
    description: str = ""
    technologies: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    evidence: list[EvidenceSnippet] = Field(default_factory=list)


class CandidateProfile(BaseModel):
    name: str = ""
    contact: str = ""
    education: list[str] = Field(default_factory=list)
    work_experience: list[WorkExperience] = Field(default_factory=list)
    projects: list[ProjectExperience] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    raw_evidence: list[str] = Field(default_factory=list)


class JobAnalysis(BaseModel):
    job_title: str = ""
    core_responsibilities: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    recruiter_focus: list[str] = Field(default_factory=list)


class JobPosting(BaseModel):
    job_id: str = ""
    company: str = ""
    title: str = ""
    source_url: str = ""
    jd_text: str = ""
    status: Literal["已收藏", "待分析", "已分析", "已生成简历", "已投递", "面试中", "已拒绝", "已 offer", "放弃"] = "待分析"
    notes: str = ""
    match_score: int = Field(default=0, ge=0, le=100)
    last_resume_file: str = ""
    created_at: str = ""
    updated_at: str = ""


class JobWorkspace(BaseModel):
    version: str = "1.0"
    active_job_id: str = ""
    jobs: list[JobPosting] = Field(default_factory=list)


class JobFitReport(BaseModel):
    score: int = Field(default=0, ge=0, le=100)
    status: Literal["low", "medium", "high"] = "low"
    recommendation: str = ""
    matched_points: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    suggested_resume_angle: str = ""


class QuestionItem(BaseModel):
    question: str = ""
    why_needed: str = ""
    related_jd_requirement: str = ""


class GapAnalysis(BaseModel):
    matched_strengths: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    questions_to_user: list[QuestionItem] = Field(default_factory=list)


class UserAnswer(BaseModel):
    question: str
    answer: str = ""
    related_jd_requirement: str = ""


class InformationSufficiencyReport(BaseModel):
    score: int = Field(default=0, ge=0, le=100)
    status: Literal["insufficient", "usable", "strong"] = "insufficient"
    ready_to_generate: bool = False
    summary: str = ""
    enough_evidence: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    recommended_questions: list[str] = Field(default_factory=list)


class MemoryFact(BaseModel):
    category: str = ""
    content: str = ""
    evidence: str = ""
    tags: list[str] = Field(default_factory=list)


class MemoryCandidate(BaseModel):
    category: Literal["strength", "skill", "project", "work_fact", "preference", "do_not_claim", "qa"] = "qa"
    content: str = ""
    evidence: str = ""
    tags: list[str] = Field(default_factory=list)
    source_type: Literal["user_answer", "github", "manual"] = "user_answer"
    save_by_default: bool = True


class UserMemory(BaseModel):
    profile_summary: str = ""
    target_roles: list[str] = Field(default_factory=list)
    strongest_selling_points: list[MemoryFact] = Field(default_factory=list)
    strengths: list[MemoryFact] = Field(default_factory=list)
    skills: list[MemoryFact] = Field(default_factory=list)
    projects: list[MemoryFact] = Field(default_factory=list)
    work_facts: list[MemoryFact] = Field(default_factory=list)
    qa_memory: list[MemoryFact] = Field(default_factory=list)
    github_facts: list[MemoryFact] = Field(default_factory=list)
    do_not_claim: list[MemoryFact] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)
    raw_notes: str = ""


class GitHubRepositoryEvidence(BaseModel):
    name: str = ""
    url: str = ""
    description: str = ""
    languages: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    readme_excerpt: str = ""
    updated_at: str = ""


class GitHubContext(BaseModel):
    source: str = ""
    profile_url: str = ""
    summary: str = ""
    repositories: list[GitHubRepositoryEvidence] = Field(default_factory=list)
    raw_evidence: list[str] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    resume_claim: str = ""
    source_type: Literal["original_resume", "user_answer", "user_confirmed", "user_memory", "github", "none"] = "none"
    source_text: str = ""
    status: Literal["verified", "needs_confirmation", "removed"] = "needs_confirmation"


class TailoredResumeResult(BaseModel):
    resume_markdown: str = ""
    optimization_notes: list[str] = Field(default_factory=list)
    integrated_keywords: list[str] = Field(default_factory=list)
    still_missing_info: list[str] = Field(default_factory=list)
    evidence_map: list[EvidenceItem] = Field(default_factory=list)


class FactCheckResult(BaseModel):
    final_resume_markdown: str = ""
    evidence_map: list[EvidenceItem] = Field(default_factory=list)
    removed_claims: list[str] = Field(default_factory=list)
    needs_confirmation: list[str] = Field(default_factory=list)
