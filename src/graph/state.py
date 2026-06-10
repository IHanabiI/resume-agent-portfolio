from __future__ import annotations

from typing import TypedDict

from src.schemas import (
    CandidateProfile,
    FactCheckResult,
    GapAnalysis,
    InformationSufficiencyReport,
    JobFitReport,
    JobAnalysis,
    ResumeAlignmentPlan,
    ResumeQualityReport,
    ResumeStarProfile,
    ResumeStructure,
    TailoredResumeResult,
    UserAnswer,
)


class ResumeAgentState(TypedDict, total=False):
    resume_text: str
    job_description: str
    memory_text: str
    github_context: str
    candidate_profile: CandidateProfile
    resume_quality_report: ResumeQualityReport
    resume_star_profile: ResumeStarProfile
    resume_structure: ResumeStructure
    job_analysis: JobAnalysis
    gap_analysis: GapAnalysis
    sufficiency_report: InformationSufficiencyReport
    job_fit_report: JobFitReport
    alignment_plan: ResumeAlignmentPlan
    ordered_resume_draft: str
    user_answers: list[UserAnswer]
    tailored_resume: TailoredResumeResult
    fact_check: FactCheckResult
    needs_questions: bool
