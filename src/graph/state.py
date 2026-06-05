from __future__ import annotations

from typing import TypedDict

from src.schemas import (
    CandidateProfile,
    FactCheckResult,
    GapAnalysis,
    InformationSufficiencyReport,
    JobAnalysis,
    TailoredResumeResult,
    UserAnswer,
)


class ResumeAgentState(TypedDict, total=False):
    resume_text: str
    job_description: str
    memory_text: str
    github_context: str
    candidate_profile: CandidateProfile
    job_analysis: JobAnalysis
    gap_analysis: GapAnalysis
    sufficiency_report: InformationSufficiencyReport
    user_answers: list[UserAnswer]
    tailored_resume: TailoredResumeResult
    fact_check: FactCheckResult
    needs_questions: bool
