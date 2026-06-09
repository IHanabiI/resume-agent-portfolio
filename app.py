from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

import streamlit as st

from src.schemas import JobWorkspace

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
    from src.job_store import (
        get_active_job,
        infer_job_title_from_jd,
        job_workspace_to_json_text,
        parse_job_workspace_upload,
        update_job_status,
        upsert_job,
    )
    from src.llm_client import pretty_json
    from src import memory_store
    from src.schemas import JobPosting, JobWorkspace, MemoryFact, UserAnswer, UserMemory

    parse_memory_upload = memory_store.parse_memory_upload
    curate_memory_candidates = getattr(memory_store, "curate_memory_candidates", lambda answers=None, github_context="": [])
    memory_to_json_text = memory_store.memory_to_json_text
    memory_to_text = memory_store.memory_to_text
    build_memory_json_text = getattr(memory_store, "build_memory_json_text", None)

    if build_memory_json_text is None:
        def build_memory_json_text(
            memory_text: str,
            answers: list[UserAnswer] | None = None,
            github_context: str = "",
            memory_candidates: list | None = None,
        ) -> str:
            memory = UserMemory(raw_notes=memory_text.strip())
            if answers:
                memory.qa_memory = [
                    MemoryFact(
                        category="guided_qa",
                        content=f"Question: {answer.question}\nAnswer: {answer.answer}",
                        evidence=answer.related_jd_requirement,
                        tags=["qa", "jd-guided"],
                    )
                    for answer in answers
                    if answer.answer.strip()
                ]
            if github_context.strip():
                memory.github_facts = [
                    MemoryFact(
                        category="github_public_evidence",
                        content=github_context[:2000],
                        evidence="GitHub public data",
                        tags=["github", "public-evidence"],
                    )
                ]
            return json.dumps(memory.model_dump(), ensure_ascii=False, indent=2)

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
        "get_active_job": get_active_job,
        "infer_job_title_from_jd": infer_job_title_from_jd,
        "job_workspace_to_json_text": job_workspace_to_json_text,
        "parse_job_workspace_upload": parse_job_workspace_upload,
        "update_job_status": update_job_status,
        "upsert_job": upsert_job,
        "run_analysis": run_analysis,
        "run_generation": run_generation,
        "pretty_json": pretty_json,
        "build_memory_json_text": build_memory_json_text,
        "curate_memory_candidates": curate_memory_candidates,
        "memory_to_json_text": memory_to_json_text,
        "memory_to_text": memory_to_text,
        "parse_memory_upload": parse_memory_upload,
        "JobPosting": JobPosting,
        "JobWorkspace": JobWorkspace,
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
        "memory_candidates": [],
        "session_context_text": "",
        "job_workspace": None,
        "active_job_id": "",
        "job_company": "",
        "job_title": "",
        "job_source_url": "",
        "job_notes": "",
        "job_status": "待分析",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    if st.session_state.job_workspace is None:
        st.session_state.job_workspace = JobWorkspace()


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
    render_job_workspace_section(modules)
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


def render_job_workspace_section(modules) -> None:
    st.header("1. 岗位库")
    st.caption("这里保存目标岗位、JD、投递状态和备注。岗位库会导出为 job_workspace.json，不依赖数据库。")

    workspace = st.session_state.job_workspace
    upload = st.file_uploader("导入岗位库 JSON 或 JD 文本", type=["json", "txt"], key="job_workspace_upload")
    if upload:
        text = upload.getvalue().decode("utf-8", errors="ignore")
        workspace = modules["parse_job_workspace_upload"](text)
        st.session_state.job_workspace = workspace
        active_job = modules["get_active_job"](workspace)
        if active_job:
            _load_job_into_session(active_job)
        st.success("已导入岗位库。")

    if workspace.jobs:
        options = [job.job_id for job in workspace.jobs]
        labels = {
            job.job_id: f"{job.company or '未填写公司'} - {job.title or '未命名岗位'} [{job.status}]"
            for job in workspace.jobs
        }
        current_id = st.session_state.active_job_id or workspace.active_job_id or options[0]
        index = options.index(current_id) if current_id in options else 0
        selected_id = st.selectbox(
            "选择已保存岗位",
            options=options,
            index=index,
            format_func=lambda job_id: labels.get(job_id, job_id),
        )
        col_load, col_delete = st.columns([1, 1])
        with col_load:
            if st.button("加载选中岗位到 JD 输入区"):
                selected = _find_job(workspace, selected_id)
                if selected:
                    _load_job_into_session(selected)
                    st.success("已加载岗位。")
                    st.rerun()
        with col_delete:
            if st.button("删除选中岗位"):
                workspace.jobs = [job for job in workspace.jobs if job.job_id != selected_id]
                if workspace.active_job_id == selected_id:
                    workspace.active_job_id = workspace.jobs[0].job_id if workspace.jobs else ""
                st.session_state.job_workspace = workspace
                st.session_state.active_job_id = workspace.active_job_id
                st.success("已删除岗位。")
                st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        st.session_state.job_company = st.text_input("公司名称", value=st.session_state.job_company)
        st.session_state.job_title = st.text_input(
            "岗位名称",
            value=st.session_state.job_title,
            placeholder="留空时会尝试从 JD 自动推断",
        )
    with col2:
        st.session_state.job_source_url = st.text_input("岗位链接", value=st.session_state.job_source_url)
        st.session_state.job_status = st.selectbox(
            "投递状态",
            ["已收藏", "待分析", "已分析", "已生成简历", "已投递", "面试中", "已拒绝", "已 offer", "放弃"],
            index=["已收藏", "待分析", "已分析", "已生成简历", "已投递", "面试中", "已拒绝", "已 offer", "放弃"].index(
                st.session_state.job_status if st.session_state.job_status in ["已收藏", "待分析", "已分析", "已生成简历", "已投递", "面试中", "已拒绝", "已 offer", "放弃"] else "待分析"
            ),
        )

    st.session_state.job_notes = st.text_area("岗位备注", value=st.session_state.job_notes, height=90)

    col_save, col_export = st.columns([1, 1])
    with col_save:
        if st.button("保存当前 JD 到岗位库", type="secondary"):
            _save_current_job(modules)

    with col_export:
        st.download_button(
            "下载岗位库 JSON",
            data=modules["job_workspace_to_json_text"](st.session_state.job_workspace).encode("utf-8"),
            file_name="job_workspace.json",
            mime="application/json",
        )

    if st.session_state.job_workspace.jobs:
        rows = [
            {
                "公司": job.company,
                "岗位": job.title,
                "状态": job.status,
                "匹配度": f"{job.match_score}%" if job.match_score else "",
                "链接": job.source_url,
                "更新时间": job.updated_at,
            }
            for job in st.session_state.job_workspace.jobs
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)


def render_input_section(modules) -> None:
    st.header("2. 输入材料")
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

    st.caption("点击“开始分析”后，结果会显示在本区域下方的「3. 分析结果」。如果需要最终简历，请在追问页点击「立刻生成定制简历」。")

    action_col1, action_col2 = st.columns([1, 1])
    with action_col1:
        start_clicked = st.button("开始分析", type="primary")
    with action_col2:
        if st.button("保存当前 JD 到岗位库", key="save_jd_from_input"):
            _save_current_job(modules)

    if start_clicked:
        if not st.session_state.resume_text.strip():
            st.error("请上传或粘贴原始简历。")
            return
        if not st.session_state.job_description.strip():
            st.error("请输入目标岗位 JD。")
            return
        try:
            with st.spinner("正在执行 LangGraph 分析工作流，完成后会在下方显示「3. 分析结果」..."):
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
                st.session_state.session_context_text = ""
                if st.session_state.active_job_id:
                    fit = st.session_state.analysis_state.get("job_fit_report")
                    st.session_state.job_workspace = modules["update_job_status"](
                        st.session_state.job_workspace,
                        st.session_state.active_job_id,
                        "已分析",
                        fit.score if fit else None,
                    )
        except Exception:
            st.error("分析失败。请检查模型接口配置，或稍后重试。")
            st.code(traceback.format_exc(), language="python")
            return
        st.success("分析完成。")


def render_analysis_section(modules) -> None:
    state = st.session_state.analysis_state
    candidate = state["candidate_profile"]
    job = state["job_analysis"]
    gap = state["gap_analysis"]
    sufficiency = state.get("sufficiency_report")
    fit = state.get("job_fit_report")

    st.header("3. 分析结果")
    tabs = st.tabs(["岗位匹配度", "信息足够度", "岗位分析", "候选人解析", "匹配与缺口", "追问问题"])
    with tabs[0]:
        if fit:
            st.metric("岗位匹配度", f"{fit.score}%")
            st.write(fit.recommendation)
            if fit.status == "high":
                st.success("建议优先投递。")
            elif fit.status == "medium":
                st.info("可以投递，但建议先补充关键证据。")
            else:
                st.warning("匹配度偏低，建议谨慎投递或补充更多事实。")

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("匹配点")
                for item in fit.matched_points or ["暂无明确匹配点。"]:
                    st.write(f"- {item}")
            with col2:
                st.subheader("风险")
                for item in fit.risks or ["暂无明显风险。"]:
                    st.write(f"- {item}")
            st.subheader("简历切入角度")
            st.write(fit.suggested_resume_angle or "围绕岗位关键词重排项目经历。")
        else:
            st.info("尚未生成岗位匹配度评估。")
    with tabs[1]:
        if sufficiency:
            st.metric("当前信息足够度", f"{sufficiency.score}%")
            st.write(sufficiency.summary)
            if sufficiency.ready_to_generate:
                st.success("当前信息已经可以生成一版定制简历。")
            else:
                st.warning("建议先继续补充信息，再生成正式简历。")

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("已有证据")
                for item in sufficiency.enough_evidence or ["暂无明确证据。"]:
                    st.write(f"- {item}")
            with col2:
                st.subheader("建议补充")
                for item in sufficiency.missing_evidence or ["暂无明显缺口。"]:
                    st.write(f"- {item}")

            st.subheader("下一步建议追问")
            for item in sufficiency.recommended_questions or ["可以直接生成简历。"]:
                st.write(f"- {item}")
        else:
            st.info("尚未生成信息足够度评估。")
    with tabs[2]:
        st.json(job.model_dump())
    with tabs[3]:
        st.json(candidate.model_dump())
    with tabs[4]:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("匹配优势")
            for item in gap.matched_strengths or ["暂未识别到明确匹配优势。"]:
                st.write(f"- {item}")
        with col2:
            st.subheader("缺失信息")
            for item in gap.missing_information or ["暂未识别到明显缺口。"]:
                st.write(f"- {item}")
    with tabs[5]:
        render_questions(modules, gap.questions_to_user)


def render_questions(modules, questions) -> None:
    st.subheader("补充真实信息")
    st.caption("你可以先回答一轮问题，再点击“继续追问”。Agent 会把回答沉淀到本轮记忆中，并根据岗位要求继续挖掘更具体的信息。信息足够时，也可以直接生成简历。")
    questions = _filter_repeated_questions(questions)
    if not questions:
        st.success("当前没有新的必须追问问题，可以直接生成定制简历。")

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

    accepted_preview = _accepted_answers(answers)
    memory_candidates = modules["curate_memory_candidates"](accepted_preview, st.session_state.github_context)
    selected_memory_candidates = []
    if memory_candidates:
        with st.expander("本轮准备保存到个人记忆库的事实", expanded=True):
            st.caption("勾选后，这些内容会进入导出的 user_memory.json；不勾选也不影响本次简历生成。")
            for idx, candidate in enumerate(memory_candidates, start=1):
                checked = st.checkbox(
                    f"{candidate.category}：{candidate.content[:120]}",
                    value=candidate.save_by_default,
                    key=f"memory_candidate_{st.session_state.question_round}_{idx}",
                )
                st.caption(f"来源：{candidate.source_type}；证据：{candidate.evidence or '用户确认'}")
                if checked:
                    selected_memory_candidates.append(candidate)

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("继续追问并更新记忆", type="secondary"):
            accepted_answers = _accepted_answers(answers)
            if not accepted_answers:
                st.warning("请至少填写一个有效回答；如果都没有，可以直接点击“立刻生成定制简历”。")
                return
            st.session_state.cumulative_answers.extend(accepted_answers)
            st.session_state.session_context_text = _merge_answers_into_memory(
                st.session_state.session_context_text,
                accepted_answers,
                st.session_state.question_round,
            )
            st.session_state.memory_candidates.extend(selected_memory_candidates)
            st.session_state.memory_text = _merge_memory_candidates_into_text(
                st.session_state.memory_text,
                selected_memory_candidates,
                st.session_state.question_round,
            )
            with st.spinner("正在根据新回答重新分析，并生成下一轮追问..."):
                st.session_state.analysis_state = modules["run_analysis"](
                    st.session_state.resume_text,
                    st.session_state.job_description,
                    _combined_memory_context(),
                    st.session_state.github_context,
                    st.session_state.cumulative_answers,
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
                st.session_state.session_context_text = _merge_answers_into_memory(
                    st.session_state.session_context_text,
                    current_answers,
                    st.session_state.question_round,
                )
                st.session_state.memory_candidates.extend(selected_memory_candidates)
                st.session_state.memory_text = _merge_memory_candidates_into_text(
                    st.session_state.memory_text,
                    selected_memory_candidates,
                    st.session_state.question_round,
                )
            all_answers = st.session_state.cumulative_answers
            state = dict(st.session_state.analysis_state)
            state["user_answers"] = all_answers
            state["memory_text"] = _combined_memory_context()
            state["github_context"] = st.session_state.github_context
            with st.spinner("正在生成简历并执行事实校验..."):
                st.session_state.generation_state = modules["run_generation"](state)
                tailored = st.session_state.generation_state["tailored_resume"]
                fact_check = st.session_state.generation_state["fact_check"]
                full_md = modules["build_full_markdown"](tailored, fact_check)
                modules["save_markdown"](full_md, modules["OUTPUT_DIR"])
                modules["save_docx"](full_md, modules["OUTPUT_DIR"])
                if st.session_state.active_job_id:
                    fit = st.session_state.analysis_state.get("job_fit_report") if st.session_state.analysis_state else None
                    st.session_state.job_workspace = modules["update_job_status"](
                        st.session_state.job_workspace,
                        st.session_state.active_job_id,
                        "已生成简历",
                        fit.score if fit else None,
                        "tailored_resume.docx",
                    )
            st.success("定制简历已生成。")


def _accepted_answers(answers):
    skipped = {"", "没有", "不清楚", "跳过", "none", "not sure", "skip"}
    return [answer for answer in answers if answer.answer.strip().lower() not in skipped]


def _find_job(workspace, job_id: str):
    for job in workspace.jobs:
        if job.job_id == job_id:
            return job
    return None


def _load_job_into_session(job) -> None:
    st.session_state.active_job_id = job.job_id
    st.session_state.job_workspace.active_job_id = job.job_id
    st.session_state.job_company = job.company
    st.session_state.job_title = job.title
    st.session_state.job_source_url = job.source_url
    st.session_state.job_notes = job.notes
    st.session_state.job_status = job.status
    st.session_state.job_description = job.jd_text
    st.session_state.analysis_state = None
    st.session_state.generation_state = None
    st.session_state.cumulative_answers = []
    st.session_state.session_context_text = ""
    st.session_state.question_round = 1


def _save_current_job(modules) -> None:
    if not st.session_state.job_description.strip():
        st.error("请先填写岗位 JD。")
        return
    JobPosting = modules["JobPosting"]
    title = st.session_state.job_title.strip() or modules["infer_job_title_from_jd"](st.session_state.job_description)
    job = JobPosting(
        job_id=st.session_state.active_job_id,
        company=st.session_state.job_company.strip(),
        title=title,
        source_url=st.session_state.job_source_url.strip(),
        jd_text=st.session_state.job_description.strip(),
        status=st.session_state.job_status,
        notes=st.session_state.job_notes.strip(),
    )
    st.session_state.job_workspace = modules["upsert_job"](st.session_state.job_workspace, job)
    st.session_state.active_job_id = job.job_id
    st.session_state.job_workspace.active_job_id = job.job_id
    st.session_state.job_title = title
    st.success("已保存岗位。")
    st.rerun()


def _filter_repeated_questions(questions):
    asked_keys = {_question_key(answer.question) for answer in st.session_state.cumulative_answers}
    answered_requirements = {
        answer.related_jd_requirement.strip().lower()
        for answer in st.session_state.cumulative_answers
        if answer.answer.strip() and answer.related_jd_requirement.strip()
    }
    filtered = []
    seen_current = set()
    for question in questions:
        key = _question_key(question.question)
        requirement = question.related_jd_requirement.strip().lower()
        if key in asked_keys or key in seen_current:
            continue
        if requirement and requirement in answered_requirements:
            continue
        if _is_generic_project_question(question.question) and _answered_requirement(answered_requirements, "隐藏经历挖掘"):
            continue
        if _is_metric_question(question.question) and _answered_requirement(answered_requirements, "结果量化"):
            continue
        seen_current.add(key)
        filtered.append(question)
    return filtered


def _question_key(text: str) -> str:
    normalized = "".join(ch for ch in text.lower() if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")
    replacements = ["请说明", "请补充", "是否", "你", "的", "和", "或", "与"]
    for item in replacements:
        normalized = normalized.replace(item, "")
    return normalized[:80]


def _answered_requirement(answered_requirements: set[str], requirement: str) -> bool:
    target = requirement.lower()
    return any(target == item or target in item or item in target for item in answered_requirements)


def _is_generic_project_question(text: str) -> bool:
    return "原始简历没有写出" in text and any(term in text for term in ["项目", "开源仓库", "自动化工具"])


def _is_metric_question(text: str) -> bool:
    return any(term in text for term in ["可确认数据", "用户数", "效率提升", "准确率", "处理规模"])


def _combined_memory_context() -> str:
    parts = [
        st.session_state.memory_text.strip(),
        st.session_state.session_context_text.strip(),
    ]
    return "\n\n".join(part for part in parts if part)


def _merge_answers_into_memory(memory_text: str, answers, round_number: int) -> str:
    lines = [memory_text.strip()] if memory_text.strip() else []
    lines.append(f"\n# 第 {round_number} 轮追问补充")
    for answer in answers:
        lines.append(f"- 问题：{answer.question}")
        lines.append(f"  回答：{answer.answer}")
        if answer.related_jd_requirement:
            lines.append(f"  关联岗位要求：{answer.related_jd_requirement}")
    return "\n".join(lines).strip()


def _merge_memory_candidates_into_text(memory_text: str, candidates, round_number: int) -> str:
    if not candidates:
        return memory_text.strip()
    lines = [memory_text.strip()] if memory_text.strip() else []
    lines.append(f"\n# 第 {round_number} 轮已确认记忆事实")
    for candidate in candidates:
        lines.append(f"- 分类：{candidate.category}")
        lines.append(f"  内容：{candidate.content}")
        if candidate.evidence:
            lines.append(f"  证据：{candidate.evidence}")
        if candidate.tags:
            lines.append(f"  标签：{', '.join(candidate.tags)}")
    return "\n".join(lines).strip()


def render_generation_section(modules) -> None:
    state = st.session_state.generation_state
    tailored = state["tailored_resume"]
    fact_check = state["fact_check"]
    full_markdown = modules["build_full_markdown"](tailored, fact_check)

    st.header("4. 生成结果")
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
                st.session_state.memory_candidates
                + modules["curate_memory_candidates"]([], st.session_state.github_context),
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
            github_candidates = modules["curate_memory_candidates"]([], st.session_state.github_context)
            if github_candidates:
                with st.expander("GitHub 将沉淀为这些记忆事实", expanded=False):
                    for candidate in github_candidates:
                        st.write(f"- **{candidate.category}**：{candidate.content[:180]}")
            st.download_button(
                "下载 GitHub 证据 TXT",
                data=st.session_state.github_context.encode("utf-8"),
                file_name="github_context.txt",
                mime="text/plain",
            )


if __name__ == "__main__":
    main()
