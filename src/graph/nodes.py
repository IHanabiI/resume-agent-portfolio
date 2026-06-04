from __future__ import annotations

from src.agents.fact_checker_agent import fact_check_resume
from src.agents.jd_analyzer_agent import analyze_jd
from src.agents.match_gap_agent import analyze_match_and_gap
from src.agents.question_agent import refine_questions
from src.agents.resume_parser_agent import parse_resume
from src.agents.resume_writer_agent import write_resume
from src.graph.state import ResumeAgentState
from src.llm_client import LLMClient


def parse_resume_node(state: ResumeAgentState) -> ResumeAgentState:
    llm = LLMClient()
    return {"candidate_profile": parse_resume(state["resume_text"], llm)}


def analyze_jd_node(state: ResumeAgentState) -> ResumeAgentState:
    llm = LLMClient()
    return {"job_analysis": analyze_jd(state["job_description"], llm)}


def match_gap_node(state: ResumeAgentState) -> ResumeAgentState:
    llm = LLMClient()
    gap = analyze_match_and_gap(
        state["candidate_profile"],
        state["job_analysis"],
        state["resume_text"],
        llm,
    )
    return {"gap_analysis": gap, "needs_questions": bool(gap.questions_to_user)}


def question_node(state: ResumeAgentState) -> ResumeAgentState:
    llm = LLMClient()
    refined = refine_questions(state["gap_analysis"], llm)
    return {"gap_analysis": refined, "needs_questions": bool(refined.questions_to_user)}


def write_resume_node(state: ResumeAgentState) -> ResumeAgentState:
    llm = LLMClient()
    result = write_resume(
        state["candidate_profile"],
        state["job_analysis"],
        state["gap_analysis"],
        state["resume_text"],
        state.get("user_answers", []),
        llm,
    )
    return {"tailored_resume": result}


def fact_check_node(state: ResumeAgentState) -> ResumeAgentState:
    llm = LLMClient()
    checked = fact_check_resume(
        state["tailored_resume"],
        state["resume_text"],
        state.get("user_answers", []),
        llm,
    )
    return {"fact_check": checked}

