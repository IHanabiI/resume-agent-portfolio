from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import OUTPUT_DIR, get_settings
from src.exporter.docx_exporter import markdown_to_docx_bytes, save_docx
from src.exporter.markdown_exporter import build_full_markdown, save_markdown
from src.file_parser import extract_text_from_upload
from src.graph.workflow import run_analysis, run_generation
from src.llm_client import pretty_json
from src.schemas import UserAnswer


st.set_page_config(page_title="简历定制 Agent", layout="wide")


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
    init_state()
    settings = get_settings()

    st.title("简历定制 Agent")
    st.caption("基于 LangGraph 的简历解析、JD 分析、缺口追问、事实校验与导出工作流。")

    if not check_access(settings.app_password):
        return

    if not settings.openai_api_key and settings.enable_demo_fallback:
        st.info("当前未检测到 OPENAI_API_KEY，应用会使用基础规则兜底，适合演示流程；配置 API Key 后可获得更高质量结果。")
    elif not settings.openai_api_key:
        st.warning("当前未检测到 OPENAI_API_KEY，且未启用兜底模式。请配置 .env 后运行。")

    render_input_section()
    if st.session_state.analysis_state:
        render_analysis_section()
    if st.session_state.generation_state:
        render_generation_section()


def check_access(app_password: str) -> bool:
    if not app_password:
        return True
    if st.session_state.get("authenticated"):
        with st.sidebar:
            st.success("已通过访问验证")
            if st.button("退出访问"):
                st.session_state.authenticated = False
                st.rerun()
        return True

    st.subheader("访问验证")
    st.write("请输入项目访问密码。")
    entered = st.text_input("访问密码", type="password")
    if st.button("进入项目", type="primary"):
        if entered == app_password:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("访问密码不正确。")
    return False


def render_input_section() -> None:
    st.header("1. 输入材料")
    left, right = st.columns(2)
    with left:
        uploaded = st.file_uploader("上传原始简历", type=["pdf", "docx", "txt"])
        pasted_resume = st.text_area("或粘贴简历文本", height=260, value=st.session_state.resume_text)
    with right:
        job_description = st.text_area("粘贴目标岗位 JD", height=330, value=st.session_state.job_description)

    if uploaded:
        try:
            st.session_state.resume_text = extract_text_from_upload(uploaded.name, uploaded.getvalue())
            st.success(f"已读取文件：{uploaded.name}")
        except Exception as exc:
            st.error(f"文件解析失败：{exc}")
    elif pasted_resume.strip():
        st.session_state.resume_text = pasted_resume.strip()
    if job_description.strip():
        st.session_state.job_description = job_description.strip()

    if st.button("开始分析", type="primary"):
        if not st.session_state.resume_text.strip():
            st.error("请上传或粘贴原始简历。")
            return
        if not st.session_state.job_description.strip():
            st.error("请输入目标岗位 JD。")
            return
        with st.spinner("正在执行 LangGraph 分析工作流..."):
            st.session_state.analysis_state = run_analysis(
                st.session_state.resume_text,
                st.session_state.job_description,
            )
            st.session_state.generation_state = None
            st.session_state.answers = []
        st.success("分析完成。")


def render_analysis_section() -> None:
    state = st.session_state.analysis_state
    candidate = state["candidate_profile"]
    job = state["job_analysis"]
    gap = state["gap_analysis"]

    st.header("2. 分析结果")
    tabs = st.tabs(["岗位分析", "候选人解析", "匹配与缺口", "追问"])
    with tabs[0]:
        st.json(job.model_dump())
    with tabs[1]:
        st.json(candidate.model_dump())
    with tabs[2]:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("匹配优势")
            for item in gap.matched_strengths or ["暂无明确匹配点"]:
                st.write(f"- {item}")
        with col2:
            st.subheader("缺失信息")
            for item in gap.missing_information or ["暂无明显缺口"]:
                st.write(f"- {item}")
    with tabs[3]:
        render_questions(gap.questions_to_user)


def render_questions(questions) -> None:
    st.subheader("请补充真实信息")
    if not questions:
        st.write("当前没有必须追问的问题，可以直接生成定制简历。")

    answers: list[UserAnswer] = []
    for index, question in enumerate(questions[:5], start=1):
        st.markdown(f"**问题 {index}：{question.question}**")
        st.caption(f"用途：{question.why_needed}；关联 JD：{question.related_jd_requirement}")
        answer = st.text_area(
            f"回答 {index}",
            key=f"answer_{index}",
            placeholder="可以填写真实经历；也可以回答：没有 / 不清楚 / 跳过",
            height=100,
        )
        answers.append(
            UserAnswer(
                question=question.question,
                answer=answer.strip(),
                related_jd_requirement=question.related_jd_requirement,
            )
        )

    if st.button("生成定制简历", type="primary"):
        state = dict(st.session_state.analysis_state)
        state["user_answers"] = answers
        with st.spinner("正在生成简历并执行事实校验..."):
            st.session_state.generation_state = run_generation(state)
            tailored = st.session_state.generation_state["tailored_resume"]
            fact_check = st.session_state.generation_state["fact_check"]
            full_md = build_full_markdown(tailored, fact_check)
            save_markdown(full_md, OUTPUT_DIR)
            save_docx(full_md, OUTPUT_DIR)
        st.success("定制简历已生成。")


def render_generation_section() -> None:
    state = st.session_state.generation_state
    tailored = state["tailored_resume"]
    fact_check = state["fact_check"]
    full_markdown = build_full_markdown(tailored, fact_check)

    st.header("3. 生成结果")
    tabs = st.tabs(["定制简历", "优化说明", "事实来源映射", "原始 JSON"])
    with tabs[0]:
        st.markdown(fact_check.final_resume_markdown or tailored.resume_markdown)
    with tabs[1]:
        st.subheader("优化说明")
        for item in tailored.optimization_notes:
            st.write(f"- {item}")
        st.subheader("已融入岗位关键词")
        st.write("、".join(tailored.integrated_keywords) if tailored.integrated_keywords else "无")
        st.subheader("仍建议补充的信息")
        for item in tailored.still_missing_info or ["暂无"]:
            st.write(f"- {item}")
        if fact_check.needs_confirmation:
            st.subheader("待确认内容")
            for item in fact_check.needs_confirmation:
                st.write(f"- {item}")
    with tabs[2]:
        st.dataframe([item.model_dump() for item in fact_check.evidence_map], use_container_width=True)
    with tabs[3]:
        st.code(pretty_json({"tailored_resume": tailored.model_dump(), "fact_check": fact_check.model_dump()}), language="json")

    st.download_button(
        "下载 Markdown",
        data=full_markdown.encode("utf-8"),
        file_name="tailored_resume.md",
        mime="text/markdown",
    )
    st.download_button(
        "下载 DOCX",
        data=markdown_to_docx_bytes(full_markdown),
        file_name="tailored_resume.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


if __name__ == "__main__":
    main()
