from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EvidenceSnippet(BaseModel):
    source_type: Literal["original_resume", "user_answer", "user_confirmed"] = "original_resume"
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


class EvidenceItem(BaseModel):
    resume_claim: str = ""
    source_type: Literal["original_resume", "user_answer", "user_confirmed", "none"] = "none"
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

