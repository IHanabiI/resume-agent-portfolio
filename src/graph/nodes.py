from __future__ import annotations

from src.agents.alignment_planner_agent import build_alignment_plan
from src.agents.fact_checker_agent import fact_check_resume
from src.agents.jd_analyzer_agent import analyze_jd
from src.agents.job_fit_agent import assess_job_fit
from src.agents.match_gap_agent import analyze_match_and_gap
from src.agents.question_agent import refine_questions
from src.agents.resume_parser_agent import parse_resume
from src.agents.resume_quality_agent import assess_resume_quality
from src.agents.resume_writer_agent import write_resume
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
        state.get("memory_text", ""),
        state.get("github_context", ""),
        llm,
    )
    return {"alignment_plan": plan}


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
        state.get("memory_text", ""),
        state.get("github_context", ""),
        llm,
    )
    return {"tailored_resume": result}


def fact_check_node(state: ResumeAgentState) -> ResumeAgentState:
    llm = get_llm_client()
    checked = fact_check_resume(
        state["tailored_resume"],
        state["resume_text"],
        state.get("user_answers", []),
        state.get("memory_text", ""),
        state.get("github_context", ""),
        llm,
    )
    return {"fact_check": checked}
