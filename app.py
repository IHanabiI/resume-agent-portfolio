from __future__ import annotations

import sys
import traceback
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


st.set_page_config(page_title="Resume Agent", layout="wide")


def load_app_modules():
    from src.config import OUTPUT_DIR, get_settings
    from src.exporter.docx_exporter import markdown_to_docx_bytes, save_docx
    from src.exporter.markdown_exporter import build_full_markdown, save_markdown
    from src.file_parser import extract_text_from_upload
    from src.graph.workflow import run_analysis, run_generation
    from src.llm_client import pretty_json
    from src.schemas import UserAnswer

    return {
        "OUTPUT_DIR": OUTPUT_DIR,
        "get_settings": get_settings,
        "markdown_to_docx_bytes": markdown_to_docx_bytes,
        "save_docx": save_docx,
        "build_full_markdown": build_full_markdown,
        "save_markdown": save_markdown,
        "extract_text_from_upload": extract_text_from_upload,
        "run_analysis": run_analysis,
        "run_generation": run_generation,
        "pretty_json": pretty_json,
        "UserAnswer": UserAnswer,
    }


def init_state() -> None:
    defaults = {
        "resume_text": "",
        "job_description": "",
        "analysis_state": None,
        "generation_state": None,
        "answers": [],
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def main() -> None:
    st.title("Resume Customization Agent")
    st.caption("LangGraph workflow for resume parsing, JD analysis, follow-up questions, fact checking, and export.")

    try:
        modules = load_app_modules()
        settings = modules["get_settings"]()
    except Exception:
        st.error("The app failed during startup.")
        st.code(traceback.format_exc(), language="python")
        return

    init_state()

    if not check_access(settings.app_password):
        return

    with st.sidebar:
        st.header("Runtime")
        st.write(f"Model: `{settings.openai_model}`")
        st.write(f"Base URL: `{settings.openai_base_url or 'OpenAI default'}`")
        st.write(f"API key configured: `{bool(settings.openai_api_key)}`")

    if not settings.openai_api_key and settings.enable_demo_fallback:
        st.info("OPENAI_API_KEY is not configured. The app will use demo fallback rules.")
    elif not settings.openai_api_key:
        st.warning("OPENAI_API_KEY is not configured and demo fallback is disabled.")

    render_input_section(modules)
    if st.session_state.analysis_state:
        render_analysis_section(modules)
    if st.session_state.generation_state:
        render_generation_section(modules)


def check_access(app_password: str) -> bool:
    if not app_password:
        return True
    if st.session_state.get("authenticated"):
        with st.sidebar:
            st.success("Access verified")
            if st.button("Log out"):
                st.session_state.authenticated = False
                st.rerun()
        return True

    st.subheader("Access verification")
    st.write("Enter the project access password.")
    entered = st.text_input("Access password", type="password")
    if st.button("Enter project", type="primary"):
        if entered == app_password:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False


def render_input_section(modules) -> None:
    st.header("1. Input Materials")
    left, right = st.columns(2)
    with left:
        uploaded = st.file_uploader("Upload original resume", type=["pdf", "docx", "txt"])
        pasted_resume = st.text_area("Or paste resume text", height=260, value=st.session_state.resume_text)
    with right:
        job_description = st.text_area("Paste target job description", height=330, value=st.session_state.job_description)

    if uploaded:
        try:
            st.session_state.resume_text = modules["extract_text_from_upload"](uploaded.name, uploaded.getvalue())
            st.success(f"Loaded file: {uploaded.name}")
        except Exception as exc:
            st.error(f"File parsing failed: {exc}")
    elif pasted_resume.strip():
        st.session_state.resume_text = pasted_resume.strip()

    if job_description.strip():
        st.session_state.job_description = job_description.strip()

    if st.button("Start analysis", type="primary"):
        if not st.session_state.resume_text.strip():
            st.error("Please upload or paste an original resume.")
            return
        if not st.session_state.job_description.strip():
            st.error("Please enter a target job description.")
            return
        with st.spinner("Running LangGraph analysis workflow..."):
            st.session_state.analysis_state = modules["run_analysis"](
                st.session_state.resume_text,
                st.session_state.job_description,
            )
            st.session_state.generation_state = None
            st.session_state.answers = []
        st.success("Analysis completed.")


def render_analysis_section(modules) -> None:
    state = st.session_state.analysis_state
    candidate = state["candidate_profile"]
    job = state["job_analysis"]
    gap = state["gap_analysis"]

    st.header("2. Analysis Results")
    tabs = st.tabs(["Job analysis", "Candidate profile", "Match and gaps", "Follow-up questions"])
    with tabs[0]:
        st.json(job.model_dump())
    with tabs[1]:
        st.json(candidate.model_dump())
    with tabs[2]:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Matched strengths")
            for item in gap.matched_strengths or ["No clear strengths found yet."]:
                st.write(f"- {item}")
        with col2:
            st.subheader("Missing information")
            for item in gap.missing_information or ["No obvious gaps found."]:
                st.write(f"- {item}")
    with tabs[3]:
        render_questions(modules, gap.questions_to_user)


def render_questions(modules, questions) -> None:
    st.subheader("Supplement real information")
    if not questions:
        st.write("No required follow-up questions. You can generate the tailored resume directly.")

    answers = []
    UserAnswer = modules["UserAnswer"]
    for index, question in enumerate(questions[:5], start=1):
        st.markdown(f"**Question {index}: {question.question}**")
        st.caption(f"Why needed: {question.why_needed}; Related JD requirement: {question.related_jd_requirement}")
        answer = st.text_area(
            f"Answer {index}",
            key=f"answer_{index}",
            placeholder="Enter real experience, or answer: none / not sure / skip",
            height=100,
        )
        answers.append(
            UserAnswer(
                question=question.question,
                answer=answer.strip(),
                related_jd_requirement=question.related_jd_requirement,
            )
        )

    if st.button("Generate tailored resume", type="primary"):
        state = dict(st.session_state.analysis_state)
        state["user_answers"] = answers
        with st.spinner("Generating resume and running fact check..."):
            st.session_state.generation_state = modules["run_generation"](state)
            tailored = st.session_state.generation_state["tailored_resume"]
            fact_check = st.session_state.generation_state["fact_check"]
            full_md = modules["build_full_markdown"](tailored, fact_check)
            modules["save_markdown"](full_md, modules["OUTPUT_DIR"])
            modules["save_docx"](full_md, modules["OUTPUT_DIR"])
        st.success("Tailored resume generated.")


def render_generation_section(modules) -> None:
    state = st.session_state.generation_state
    tailored = state["tailored_resume"]
    fact_check = state["fact_check"]
    full_markdown = modules["build_full_markdown"](tailored, fact_check)

    st.header("3. Generated Result")
    tabs = st.tabs(["Tailored resume", "Optimization notes", "Evidence map", "Raw JSON"])
    with tabs[0]:
        st.markdown(fact_check.final_resume_markdown or tailored.resume_markdown)
    with tabs[1]:
        st.subheader("Optimization notes")
        for item in tailored.optimization_notes:
            st.write(f"- {item}")
        st.subheader("Integrated JD keywords")
        st.write(", ".join(tailored.integrated_keywords) if tailored.integrated_keywords else "None")
        st.subheader("Still missing information")
        for item in tailored.still_missing_info or ["None"]:
            st.write(f"- {item}")
        if fact_check.needs_confirmation:
            st.subheader("Needs confirmation")
            for item in fact_check.needs_confirmation:
                st.write(f"- {item}")
    with tabs[2]:
        st.dataframe([item.model_dump() for item in fact_check.evidence_map], use_container_width=True)
    with tabs[3]:
        st.code(
            modules["pretty_json"](
                {"tailored_resume": tailored.model_dump(), "fact_check": fact_check.model_dump()}
            ),
            language="json",
        )

    st.download_button(
        "Download Markdown",
        data=full_markdown.encode("utf-8"),
        file_name="tailored_resume.md",
        mime="text/markdown",
    )
    st.download_button(
        "Download DOCX",
        data=modules["markdown_to_docx_bytes"](full_markdown),
        file_name="tailored_resume.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


if __name__ == "__main__":
    main()
