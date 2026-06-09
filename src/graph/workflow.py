from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.graph.nodes import (
    analyze_jd_node,
    fact_check_node,
    match_gap_node,
    parse_resume_node,
    question_node,
    sufficiency_node,
    write_resume_node,
)
from src.graph.state import ResumeAgentState


def build_analysis_graph():
    graph = StateGraph(ResumeAgentState)
    graph.add_node("parse_resume", parse_resume_node)
    graph.add_node("analyze_jd", analyze_jd_node)
    graph.add_node("match_gap", match_gap_node)
    graph.add_node("generate_questions", question_node)
    graph.add_node("assess_sufficiency", sufficiency_node)

    graph.set_entry_point("parse_resume")
    graph.add_edge("parse_resume", "analyze_jd")
    graph.add_edge("analyze_jd", "match_gap")
    graph.add_conditional_edges(
        "match_gap",
        lambda state: "ask" if state.get("needs_questions") else "ready",
        {"ask": "generate_questions", "ready": "assess_sufficiency"},
    )
    graph.add_edge("generate_questions", "assess_sufficiency")
    graph.add_edge("assess_sufficiency", END)
    return graph.compile()


def build_generation_graph():
    graph = StateGraph(ResumeAgentState)
    graph.add_node("write_resume", write_resume_node)
    graph.add_node("fact_check", fact_check_node)
    graph.set_entry_point("write_resume")
    graph.add_edge("write_resume", "fact_check")
    graph.add_edge("fact_check", END)
    return graph.compile()


def run_analysis(
    resume_text: str,
    job_description: str,
    memory_text: str = "",
    github_context: str = "",
    user_answers: list | None = None,
) -> ResumeAgentState:
    app = build_analysis_graph()
    return app.invoke(
        {
            "resume_text": resume_text,
            "job_description": job_description,
            "memory_text": memory_text,
            "github_context": github_context,
            "user_answers": user_answers or [],
        }
    )


def run_generation(state: ResumeAgentState) -> ResumeAgentState:
    app = build_generation_graph()
    return app.invoke(state)
