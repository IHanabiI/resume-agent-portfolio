from __future__ import annotations

import sys
import traceback
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


st.set_page_config(page_title="简历定制 Agent", layout="wide")


def load_app_modules():
    from src.config import OUTPUT_DIR, get_settings
    from src.exporter.docx_exporter import markdown_to_docx_bytes, save_docx
    from src.exporter.markdown_exporter import build_full_markdown, save_markdown
    from src.file_parser import extract_text_from_upload
    from src.github_reader import collect_github_context, github_context_to_text
    from src.graph.workflow import run_analysis, run_generation
    from src.llm_client import pretty_json
    from src.memory_store import build_memory_json_text, memory_to_json_text, memory_to_text, parse_memory_upload
    from src.schemas import UserAnswer

    return {
        "OUTPUT_DIR": OUTPUT_DIR,
        "get_settings": get_settings,
        "markdown_to_docx_bytes": markdown_to_docx_bytes,
        "save_docx": save_docx,
        "build_full_markdown": build_full_markdown,
        "save_markdown": save_markdown,
        "extract_text_from_upload": extract_text_from_upload,
        "collect_github_context": collect_github_context,
        "github_context_to_text": github_context_to_text,
        "run_analysis": run_analysis,
        "run_generation": run_generation,
        "pretty_json": pretty_json,
        "build_memory_json_text": build_memory_json_text,
        "memory_to_json_text": memory_to_json_text,
        "memory_to_text": memory_to_text,
        "parse_memory_upload": parse_memory_upload,
        "UserAnswer": UserAnswer,
    }


def init_state() -> None:
    defaults = {
        "resume_text": "",
        "job_description": "",
        "analysis_state": None,
        "generation_state": None,
        "answers": [],
        "cumulative_answers": [],
        "question_round": 1,
        "memory_text": "",
        "github_input": "",
        "github_context": "",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def main() -> None:
    st.title("简历定制 Agent")
    st.caption("基于 LangGraph 的简历解析、JD 分析、信息追问、事实校验与文件导出工作流。")

    try:
        modules = load_app_modules()
        settings = modules["get_settings"]()
    except Exception:
        st.error("应用启动失败。")
        st.code(traceback.format_exc(), language="python")
        return

    init_state()

    if not check_access(settings.app_password):
        return

    with st.sidebar:
        st.header("运行配置")
        st.write(f"模型：`{settings.openai_model}`")
        st.write(f"接口地址：`{settings.openai_base_url or 'OpenAI 默认地址'}`")
        st.write(f"API Key 已配置：`{bool(settings.openai_api_key)}`")

    if not settings.openai_api_key and settings.enable_demo_fallback:
        st.info("当前未配置 OPENAI_API_KEY，应用会使用基础规则兜底，适合演示流程。")
    elif not settings.openai_api_key:
        st.warning("当前未配置 OPENAI_API_KEY，且未启用演示兜底。")

    render_context_section(modules)
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
            st.success("访问验证已通过")
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


def render_input_section(modules) -> None:
    st.header("1. 输入材料")
    left, right = st.columns(2)
    with left:
        uploaded = st.file_uploader("上传原始简历", type=["pdf", "docx", "txt"])
        pasted_resume = st.text_area("或粘贴简历文本", height=260, value=st.session_state.resume_text)
    with right:
        job_description = st.text_area("粘贴目标岗位 JD", height=330, value=st.session_state.job_description)

    if uploaded:
        try:
            st.session_state.resume_text = modules["extract_text_from_upload"](uploaded.name, uploaded.getvalue())
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
            st.session_state.analysis_state = modules["run_analysis"](
                st.session_state.resume_text,
                st.session_state.job_description,
                st.session_state.memory_text,
                st.session_state.github_context,
            )
            st.session_state.generation_state = None
            st.session_state.answers = []
            st.session_state.cumulative_answers = []
            st.session_state.question_round = 1
        st.success("分析完成。")


def render_analysis_section(modules) -> None:
    state = st.session_state.analysis_state
    candidate = state["candidate_profile"]
    job = state["job_analysis"]
    gap = state["gap_analysis"]

    st.header("2. 分析结果")
    tabs = st.tabs(["岗位分析", "候选人解析", "匹配与缺口", "追问问题"])
    with tabs[0]:
        st.json(job.model_dump())
    with tabs[1]:
        st.json(candidate.model_dump())
    with tabs[2]:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("匹配优势")
            for item in gap.matched_strengths or ["暂未识别到明确匹配优势。"]:
                st.write(f"- {item}")
        with col2:
            st.subheader("缺失信息")
            for item in gap.missing_information or ["暂未识别到明显缺口。"]:
                st.write(f"- {item}")
    with tabs[3]:
        render_questions(modules, gap.questions_to_user)


def render_questions(modules, questions) -> None:
    st.subheader("补充真实信息")
    st.caption("你可以先回答一轮问题，再点击“继续追问”。Agent 会把回答沉淀到本轮记忆中，并根据岗位要求继续挖掘更具体的信息。信息足够时，也可以直接生成简历。")
    if not questions:
        st.write("当前没有必须追问的问题，可以直接生成定制简历。")

    answers = []
    UserAnswer = modules["UserAnswer"]
    if st.session_state.cumulative_answers:
        with st.expander("已累计的追问回答", expanded=False):
            for idx, item in enumerate(st.session_state.cumulative_answers, start=1):
                st.markdown(f"**{idx}. {item.question}**")
                st.write(item.answer)

    for index, question in enumerate(questions[:5], start=1):
        st.markdown(f"**问题 {index}：{question.question}**")
        st.caption(f"用途：{question.why_needed}；关联 JD 要求：{question.related_jd_requirement}")
        answer = st.text_area(
            f"回答 {index}",
            key=f"answer_{st.session_state.question_round}_{index}",
            placeholder="请填写真实经历；也可以回答：没有 / 不清楚 / 跳过",
            height=100,
        )
        answers.append(
            UserAnswer(
                question=question.question,
                answer=answer.strip(),
                related_jd_requirement=question.related_jd_requirement,
            )
        )

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("继续追问并更新记忆", type="secondary"):
            accepted_answers = _accepted_answers(answers)
            if not accepted_answers:
                st.warning("请至少填写一个有效回答；如果都没有，可以直接点击“立刻生成定制简历”。")
                return
            st.session_state.cumulative_answers.extend(accepted_answers)
            st.session_state.memory_text = _merge_answers_into_memory(
                st.session_state.memory_text,
                accepted_answers,
                st.session_state.question_round,
            )
            with st.spinner("正在根据新回答重新分析，并生成下一轮追问..."):
                st.session_state.analysis_state = modules["run_analysis"](
                    st.session_state.resume_text,
                    st.session_state.job_description,
                    st.session_state.memory_text,
                    st.session_state.github_context,
                )
                st.session_state.question_round += 1
                st.session_state.generation_state = None
            st.success("已更新记忆并生成下一轮追问。")
            st.rerun()

    with col2:
        if st.button("立刻生成定制简历", type="primary"):
            current_answers = _accepted_answers(answers)
            if current_answers:
                st.session_state.cumulative_answers.extend(current_answers)
                st.session_state.memory_text = _merge_answers_into_memory(
                    st.session_state.memory_text,
                    current_answers,
                    st.session_state.question_round,
                )
            all_answers = st.session_state.cumulative_answers
            state = dict(st.session_state.analysis_state)
            state["user_answers"] = all_answers
            state["memory_text"] = st.session_state.memory_text
            state["github_context"] = st.session_state.github_context
            with st.spinner("正在生成简历并执行事实校验..."):
                st.session_state.generation_state = modules["run_generation"](state)
                tailored = st.session_state.generation_state["tailored_resume"]
                fact_check = st.session_state.generation_state["fact_check"]
                full_md = modules["build_full_markdown"](tailored, fact_check)
                modules["save_markdown"](full_md, modules["OUTPUT_DIR"])
                modules["save_docx"](full_md, modules["OUTPUT_DIR"])
            st.success("定制简历已生成。")


def _accepted_answers(answers):
    skipped = {"", "没有", "不清楚", "跳过", "none", "not sure", "skip"}
    return [answer for answer in answers if answer.answer.strip().lower() not in skipped]


def _merge_answers_into_memory(memory_text: str, answers, round_number: int) -> str:
    lines = [memory_text.strip()] if memory_text.strip() else []
    lines.append(f"\n# 第 {round_number} 轮追问补充")
    for answer in answers:
        lines.append(f"- 问题：{answer.question}")
        lines.append(f"  回答：{answer.answer}")
        if answer.related_jd_requirement:
            lines.append(f"  关联岗位要求：{answer.related_jd_requirement}")
    return "\n".join(lines).strip()


def render_generation_section(modules) -> None:
    state = st.session_state.generation_state
    tailored = state["tailored_resume"]
    fact_check = state["fact_check"]
    full_markdown = modules["build_full_markdown"](tailored, fact_check)

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
        for item in tailored.still_missing_info or ["无"]:
            st.write(f"- {item}")
        if fact_check.needs_confirmation:
            st.subheader("待确认内容")
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
        "下载 Markdown",
        data=full_markdown.encode("utf-8"),
        file_name="tailored_resume.md",
        mime="text/markdown",
    )
    st.download_button(
        "下载 DOCX",
        data=modules["markdown_to_docx_bytes"](full_markdown),
        file_name="tailored_resume.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


def render_context_section(modules) -> None:
    st.header("0. 个人记忆与外部证据")
    st.caption("这里用于补足原始简历没有写出的真实经历。Agent 只会把这些内容作为事实来源，不会凭空编造。")

    memory_tab, github_tab = st.tabs(["个人记忆库", "GitHub 证据"])

    with memory_tab:
        memory_file = st.file_uploader("导入记忆库 JSON 或 TXT", type=["json", "txt"], key="memory_upload")
        if memory_file:
            text = memory_file.getvalue().decode("utf-8", errors="ignore")
            memory = modules["parse_memory_upload"](text)
            st.session_state.memory_text = modules["memory_to_text"](memory)
            st.success("已导入个人记忆库。")

        st.session_state.memory_text = st.text_area(
            "个人记忆库",
            value=st.session_state.memory_text,
            height=180,
            placeholder=(
                "请记录原始简历没有写全、但真实存在的信息，例如：\n"
                "- 我做过的项目、负责内容、技术栈\n"
                "- 我熟悉但简历没写的工具/框架\n"
                "- 可确认的数据、成果、奖项、证书\n"
                "- 不希望写入简历的内容或表达偏好"
            ),
        )
        st.download_button(
            "下载记忆库 JSON",
            data=modules["build_memory_json_text"](
                st.session_state.memory_text,
                st.session_state.cumulative_answers,
                st.session_state.github_context,
            ).encode("utf-8"),
            file_name="user_memory.json",
            mime="application/json",
        )

    with github_tab:
        st.session_state.github_input = st.text_area(
            "GitHub 用户名或仓库链接",
            value=st.session_state.github_input,
            height=100,
            placeholder="例如：IHanabiI 或 https://github.com/IHanabiI/resume-agent-portfolio",
        )
        if st.button("读取 GitHub 公开信息"):
            if not st.session_state.github_input.strip():
                st.error("请先输入 GitHub 用户名或仓库链接。")
            else:
                with st.spinner("正在读取 GitHub 公开仓库信息..."):
                    context = modules["collect_github_context"](st.session_state.github_input)
                    st.session_state.github_context = modules["github_context_to_text"](context)
                st.success("GitHub 信息读取完成。")

        if st.session_state.github_context:
            st.text_area("已收集到的 GitHub 证据", value=st.session_state.github_context, height=220)
            st.download_button(
                "下载 GitHub 证据 TXT",
                data=st.session_state.github_context.encode("utf-8"),
                file_name="github_context.txt",
                mime="text/plain",
            )


if __name__ == "__main__":
    main()
