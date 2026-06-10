from __future__ import annotations

from src.agents.alignment_planner_agent import build_alignment_plan
from src.agents.fact_checker_agent import fact_check_resume
from src.agents.jd_analyzer_agent import analyze_jd
from src.agents.job_fit_agent import assess_job_fit
from src.agents.match_gap_agent import analyze_match_and_gap
from src.agents.question_agent import refine_questions
from src.agents.resume_changelog_agent import build_diff_changelog
from src.agents.resume_output_guard_agent import guard_final_resume
from src.agents.resume_parser_agent import parse_resume
from src.agents.resume_plan_audit_agent import audit_alignment_execution
from src.agents.resume_plan_applier_agent import build_ordered_resume_draft
from src.agents.resume_quality_agent import assess_resume_quality
from src.agents.resume_structure_agent import parse_resume_structure
from src.agents.resume_writer_agent import revise_resume_after_audit, write_resume
from src.agents.sufficiency_agent import assess_information_sufficiency
from src.graph.state import ResumeAgentState
from src.llm_client import get_llm_client


def parse_resume_node(state: ResumeAgentState) -> ResumeAgentState:
    llm = get_llm_client()
    quality, star = assess_resume_quality(state["resume_text"])
    return {
        "candidate_profile": parse_resume(state["resume_text"], llm),
        "resume_quality_report": quality,
        "resume_star_profile": star,
        "resume_structure": parse_resume_structure(state["resume_text"]),
    }


def analyze_jd_node(state: ResumeAgentState) -> ResumeAgentState:
    llm = get_llm_client()
    return {"job_analysis": analyze_jd(state["job_description"], llm)}


def match_gap_node(state: ResumeAgentState) -> ResumeAgentState:
    llm = get_llm_client()
    gap = analyze_match_and_gap(
        state["candidate_profile"],
        state["job_analysis"],
        state["resume_text"],
        state.get("memory_text", ""),
        state.get("github_context", ""),
        state.get("user_answers", []),
        llm,
    )
    return {"gap_analysis": gap, "needs_questions": bool(gap.questions_to_user)}


def question_node(state: ResumeAgentState) -> ResumeAgentState:
    llm = get_llm_client()
    refined = refine_questions(state["gap_analysis"], llm)
    return {"gap_analysis": refined, "needs_questions": bool(refined.questions_to_user)}


def sufficiency_node(state: ResumeAgentState) -> ResumeAgentState:
    report = assess_information_sufficiency(
        state["candidate_profile"],
        state["job_analysis"],
        state["gap_analysis"],
        state["resume_text"],
        state.get("memory_text", ""),
        state.get("github_context", ""),
        state.get("user_answers", []),
    )
    fit = assess_job_fit(
        state["candidate_profile"],
        state["job_analysis"],
        state["gap_analysis"],
        state["resume_text"],
        state.get("memory_text", ""),
        state.get("github_context", ""),
        state.get("resume_quality_report"),
        state.get("resume_star_profile"),
    )
    return {"sufficiency_report": report, "job_fit_report": fit}


def alignment_plan_node(state: ResumeAgentState) -> ResumeAgentState:
    llm = get_llm_client()
    plan = build_alignment_plan(
        state["candidate_profile"],
        state["job_analysis"],
        state["gap_analysis"],
        state["resume_text"],
        state.get("user_answers", []),
        state.get("resume_star_profile"),
        state.get("resume_quality_report"),
        state.get("resume_structure"),
        state.get("memory_text", ""),
        state.get("github_context", ""),
        llm,
    )
    return {"alignment_plan": plan}


def apply_alignment_plan_node(state: ResumeAgentState) -> ResumeAgentState:
    draft = build_ordered_resume_draft(
        state.get("resume_structure"),
        state.get("alignment_plan"),
    )
    return {"ordered_resume_draft": draft}


def write_resume_node(state: ResumeAgentState) -> ResumeAgentState:
    llm = get_llm_client()
    result = write_resume(
        state["candidate_profile"],
        state["job_analysis"],
        state["gap_analysis"],
        state["resume_text"],
        state.get("user_answers", []),
        state.get("resume_star_profile"),
        state.get("alignment_plan"),
        state.get("resume_structure"),
        state.get("ordered_resume_draft", ""),
        state.get("memory_text", ""),
        state.get("github_context", ""),
        llm,
    )
    return {"tailored_resume": result}


def fact_check_node(state: ResumeAgentState) -> ResumeAgentState:
    llm = get_llm_client()
    tailored = state["tailored_resume"]
    checked, guarded_resume, guard_warnings, execution_warnings = _check_guard_and_audit(state, tailored, llm)

    if _should_retry_after_audit(execution_warnings) and llm.available:
        revised = revise_resume_after_audit(
            state["candidate_profile"],
            state["job_analysis"],
            state["gap_analysis"],
            state["resume_text"],
            state.get("user_answers", []),
            tailored,
            guarded_resume,
            execution_warnings,
            state.get("resume_star_profile"),
            state.get("alignment_plan"),
            state.get("resume_structure"),
            state.get("ordered_resume_draft", ""),
            state.get("memory_text", ""),
            state.get("github_context", ""),
            llm,
        )
        if revised.resume_markdown.strip() and revised.resume_markdown.strip() != tailored.resume_markdown.strip():
            tailored = revised
            checked, guarded_resume, guard_warnings, execution_warnings = _check_guard_and_audit(state, tailored, llm)

    all_warnings = [*guard_warnings, *execution_warnings]
    checked.needs_confirmation = list(dict.fromkeys([*checked.needs_confirmation, *all_warnings]))[:30]
    tailored.changelog_markdown = build_diff_changelog(
        state["resume_text"],
        guarded_resume,
        all_warnings,
    )
    return {"fact_check": checked, "tailored_resume": tailored}


def _check_guard_and_audit(
    state: ResumeAgentState,
    tailored,
    llm,
):
    checked = fact_check_resume(
        tailored,
        state["resume_text"],
        state.get("user_answers", []),
        state.get("memory_text", ""),
        state.get("github_context", ""),
        llm,
    )
    final_resume = checked.final_resume_markdown or tailored.resume_markdown
    guarded_resume, guard_warnings = guard_final_resume(
        final_resume,
        state.get("resume_structure"),
    )
    checked.final_resume_markdown = guarded_resume
    execution_warnings = audit_alignment_execution(
        state["resume_text"],
        guarded_resume,
        state.get("alignment_plan"),
    )
    return checked, guarded_resume, guard_warnings, execution_warnings


def _should_retry_after_audit(execution_warnings: list[str]) -> bool:
    retry_markers = [
        "最终简历没有产生可比较正文变化",
        "高优先级计划未在真实 diff 中明显体现",
        "计划未明显执行",
    ]
    return any(any(marker in warning for marker in retry_markers) for warning in execution_warnings)
