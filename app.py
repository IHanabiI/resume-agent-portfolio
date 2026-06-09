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
        ranked_jobs,
        shortlist_to_json_text,
        update_job_status,
        upsert_job,
    )
    from src.llm_client import pretty_json
    from src import memory_store
    from src.workspace_store import (
        WorkspaceSnapshot,
        delete_workspace,
        load_workspace,
        parse_workspace_json,
        save_workspace,
        workspace_to_json_text,
    )
    from src.schemas import (
        FactCheckResult,
        JobPosting,
        JobWorkspace,
        MemoryCandidate,
        MemoryFact,
        TailoredResumeResult,
        UserAnswer,
        UserMemory,
    )

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
        "ranked_jobs": ranked_jobs,
        "shortlist_to_json_text": shortlist_to_json_text,
        "update_job_status": update_job_status,
        "upsert_job": upsert_job,
        "run_analysis": run_analysis,
        "run_generation": run_generation,
        "pretty_json": pretty_json,
        "WorkspaceSnapshot": WorkspaceSnapshot,
        "delete_workspace": delete_workspace,
        "load_workspace": load_workspace,
        "parse_workspace_json": parse_workspace_json,
        "save_workspace": save_workspace,
        "workspace_to_json_text": workspace_to_json_text,
        "build_memory_json_text": build_memory_json_text,
        "curate_memory_candidates": curate_memory_candidates,
        "memory_to_json_text": memory_to_json_text,
        "memory_to_text": memory_to_text,
        "parse_memory_upload": parse_memory_upload,
        "JobPosting": JobPosting,
        "JobWorkspace": JobWorkspace,
        "MemoryCandidate": MemoryCandidate,
        "TailoredResumeResult": TailoredResumeResult,
        "FactCheckResult": FactCheckResult,
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
        "workspace_key": "",
        "workspace_id": "",
        "workspace_loaded": False,
        "workspace_updated_at": "",
        "workspace_upload_done": False,
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

    if not check_workspace_access(modules, settings):
        return

    with st.sidebar:
        render_workspace_sidebar(modules, settings)
        st.divider()
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
    render_shortlist_section(modules)


def check_workspace_access(modules, settings) -> bool:
    if st.session_state.get("workspace_loaded"):
        return True

    st.subheader("工作区 Key")
    st.write("请输入你的工作区 Key。相同 Key 会自动恢复上次保存的简历、岗位库、记忆库和生成结果。")
    entered = st.text_input("工作区 Key", type="password", placeholder="例如 Hanabi-2026")
    st.caption("Key 不会明文保存；系统只保存它的哈希。请不要使用过于简单的 Key。")
    if st.button("进入工作区", type="primary"):
        key = entered.strip()
        if len(key) < 3:
            st.error("工作区 Key 至少需要 3 个字符。")
            return False
        if not _workspace_key_allowed(key, settings.allowed_workspace_keys):
            st.error("工作区 Key 不正确。")
            return False
        try:
            snapshot = modules["load_workspace"](key, settings.workspace_salt or settings.app_password)
            st.session_state.workspace_key = key
            if snapshot:
                _apply_workspace_snapshot(modules, snapshot)
                st.success("已恢复上次工作区。")
            else:
                st.session_state.workspace_id = ""
                st.session_state.workspace_updated_at = ""
                st.success("已创建新工作区。")
            st.session_state.workspace_loaded = True
            _auto_save_workspace(modules, settings)
            st.rerun()
        except Exception as exc:
            st.error(f"工作区加载失败：{exc}")
    return False


def _workspace_key_allowed(key: str, allowed_keys: str) -> bool:
    allowed = [item.strip() for item in (allowed_keys or "").split(",") if item.strip()]
    if not allowed:
        return True
    return key in allowed


def render_workspace_sidebar(modules, settings) -> None:
    st.header("工作区")
    st.write(f"状态：`已加载`")
    if st.session_state.workspace_id:
        st.caption(f"ID：{st.session_state.workspace_id}")
    if st.session_state.workspace_updated_at:
        st.caption(f"最后保存：{st.session_state.workspace_updated_at}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("保存", key="save_workspace_now"):
            snapshot = _auto_save_workspace(modules, settings)
            if snapshot:
                st.success("已保存工作区。")
    with col2:
        if st.button("退出", key="logout_workspace"):
            _auto_save_workspace(modules, settings)
            st.session_state.clear()
            st.rerun()

    snapshot = _build_workspace_snapshot(modules)
    st.download_button(
        "导出工作区 JSON",
        data=modules["workspace_to_json_text"](snapshot).encode("utf-8"),
        file_name="resume_agent_workspace.json",
        mime="application/json",
    )

    uploaded = st.file_uploader("导入工作区 JSON", type=["json"], key="workspace_upload")
    if uploaded and not st.session_state.get("workspace_upload_done"):
        try:
            imported = modules["parse_workspace_json"](uploaded.getvalue().decode("utf-8", errors="ignore"))
            _apply_workspace_snapshot(modules, imported)
            _auto_save_workspace(modules, settings)
            st.session_state.workspace_upload_done = True
            st.success("已导入并保存工作区。")
            st.rerun()
        except Exception as exc:
            st.error(f"工作区导入失败：{exc}")
    elif not uploaded:
        st.session_state.workspace_upload_done = False

    if st.button("清空当前工作区", key="delete_workspace"):
        if modules["delete_workspace"](st.session_state.workspace_key, settings.workspace_salt or settings.app_password):
            st.success("已删除当前工作区文件。")
        st.session_state.clear()
        st.rerun()


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
        _auto_save_workspace(modules, modules["get_settings"]())
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

    col_save, col_batch, col_export = st.columns([1, 1, 1])
    with col_save:
        if st.button("保存当前 JD 到岗位库", type="secondary"):
            _save_current_job(modules)

    with col_batch:
        if st.button("批量分析岗位库", type="secondary"):
            _batch_analyze_jobs(modules)

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
                "平台": job.platform,
                "地点": job.location,
                "薪资": job.salary,
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
        current_job = _upsert_current_job(modules)
        if not current_job:
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
                fit = st.session_state.analysis_state.get("job_fit_report")
                st.session_state.job_workspace = modules["update_job_status"](
                    st.session_state.job_workspace,
                    st.session_state.active_job_id,
                    "已分析",
                    fit.score if fit else None,
                    fit_recommendation=fit.recommendation if fit else "",
                    fit_risks=fit.risks if fit else None,
                    fit_matched_points=fit.matched_points if fit else None,
                    suggested_resume_angle=fit.suggested_resume_angle if fit else "",
                )
                st.session_state.job_status = "已分析"
                _auto_save_workspace(modules, modules["get_settings"]())
        except Exception:
            st.error("分析失败。请检查模型接口配置，或稍后重试。")
            st.code(traceback.format_exc(), language="python")
            return
        st.success("分析完成，并已写入岗位库。")


def render_analysis_section(modules) -> None:
    state = st.session_state.analysis_state
    candidate = state["candidate_profile"]
    job = state["job_analysis"]
    gap = state["gap_analysis"]
    sufficiency = state.get("sufficiency_report")
    fit = state.get("job_fit_report")
    quality = state.get("resume_quality_report")
    star = state.get("resume_star_profile")

    st.header("3. 分析结果")
    tabs = st.tabs(["岗位评估", "补充信息", "调试信息"])
    with tabs[0]:
        if fit:
            metric_col1, metric_col2, metric_col3 = st.columns([1, 1, 1])
            with metric_col1:
                st.metric("岗位匹配度", f"{fit.score}%")
            with metric_col2:
                if sufficiency:
                    st.metric("信息完整度", f"{sufficiency.score}%")
            with metric_col3:
                if quality:
                    st.metric("简历质量", f"{quality.score}%")

            st.subheader("一句话评估")
            st.write(fit.one_liner or fit.recommendation)
            if fit.status == "high":
                st.success("建议优先投递。")
            elif fit.status == "medium":
                st.info("可以投递，但建议先补充关键证据。")
            else:
                st.warning("匹配度偏低，建议谨慎投递或补充更多事实。")

            st.subheader("四维评分")
            score_col1, score_col2, score_col3, score_col4 = st.columns(4)
            score_col1.metric("硬技能", f"{fit.hard_skills_score}%")
            score_col2.metric("经验深度", f"{fit.experience_depth_score}%")
            score_col3.metric("领域契合", f"{fit.domain_fit_score}%")
            score_col4.metric("软性匹配", f"{fit.soft_fit_score}%")

            col1, col2 = st.columns(2)
            with col1:
                st.subheader("命中点")
                for item in fit.matched_points or ["暂无明确匹配点。"]:
                    st.write(f"- {item}")
                if gap.matched_strengths:
                    st.subheader("匹配优势")
                    for item in gap.matched_strengths[:6]:
                        st.write(f"- {item}")
            with col2:
                st.subheader("风险与缺口")
                for item in fit.risks or ["暂无明显风险。"]:
                    st.write(f"- {item}")
                for item in gap.missing_information[:6]:
                    st.write(f"- {item}")

            if sufficiency:
                with st.expander("证据完整度", expanded=False):
                    st.write(sufficiency.summary)
                    col3, col4 = st.columns(2)
                    with col3:
                        st.subheader("已有证据")
                        for item in sufficiency.enough_evidence or ["暂无明确证据。"]:
                            st.write(f"- {item}")

            if quality:
                with st.expander("简历质量体检", expanded=True):
                    st.write(quality.summary)
                    if quality.empty_shell_items:
                        st.warning("存在空壳经历，建议优先补全。")
                        for item in quality.empty_shell_items[:6]:
                            st.write(f"- {item}")
                    col5, col6 = st.columns(2)
                    with col5:
                        st.subheader("优势")
                        for item in quality.strengths or ["暂无明确优势。"]:
                            st.write(f"- {item}")
                    with col6:
                        st.subheader("建议修复")
                        for item in quality.recommended_fixes or ["暂无建议。"]:
                            st.write(f"- {item}")
                    if quality.issues:
                        st.subheader("问题清单")
                        st.dataframe([item.model_dump() for item in quality.issues], use_container_width=True, hide_index=True)

            if star:
                with st.expander("STAR 候选经历", expanded=False):
                    st.write(star.summary)
                    rows = [
                        {
                            "区块": item.source_section,
                            "经历": item.title,
                            "有行动": item.has_action,
                            "有结果": item.has_result,
                            "缺量化": item.needs_metrics,
                            "技能": "、".join(item.skills),
                        }
                        for item in star.items[:20]
                    ]
                    st.dataframe(rows, use_container_width=True, hide_index=True)
                    with col4:
                        st.subheader("建议补充")
                        for item in sufficiency.missing_evidence or ["暂无明显缺口。"]:
                            st.write(f"- {item}")

            st.subheader("简历切入角度")
            st.write(fit.suggested_resume_angle or "围绕岗位关键词重排项目经历。")
        else:
            st.info("尚未生成岗位匹配度评估。")

        st.subheader("下一步")
        st.write("先补充关键事实，或直接生成岗位交付材料。")

    with tabs[1]:
        render_questions(modules, gap.questions_to_user)
    with tabs[2]:
        st.caption("这些是开发和核验用的结构化结果，默认不作为主流程展示。")
        with st.expander("岗位结构化结果", expanded=False):
            st.json(job.model_dump())
        with st.expander("候选人结构化结果", expanded=False):
            st.json(candidate.model_dump())
        if quality:
            with st.expander("简历质量报告", expanded=False):
                st.json(quality.model_dump())
        if star:
            with st.expander("STAR Profile", expanded=False):
                st.json(star.model_dump())
        with st.expander("完整分析状态", expanded=False):
            st.json(_json_safe_state(state))


def render_questions(modules, questions) -> None:
    st.subheader("补充真实信息")
    st.caption("这里用于补全会影响简历质量的事实。可以填写后直接生成交付材料；不确定的内容可以跳过，系统会用占位符提示。")
    questions = _filter_repeated_questions(questions)
    if not questions:
        st.success("当前没有新的必须补充问题，可以直接生成岗位交付材料。")

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
        with st.expander("准备保存到个人记忆库的事实", expanded=False):
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
        if st.button("直接生成岗位交付材料", type="primary"):
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
            with st.spinner("正在生成简历、开场白、改动说明并执行事实校验..."):
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
                        fit_recommendation=fit.recommendation if fit else "",
                        fit_risks=fit.risks if fit else None,
                        fit_matched_points=fit.matched_points if fit else None,
                        suggested_resume_angle=fit.suggested_resume_angle if fit else "",
                    )
                _auto_save_workspace(modules, modules["get_settings"]())
            st.success("岗位交付材料已生成。")

    with col2:
        if st.button("保存补充并重新评估", type="secondary"):
            accepted_answers = _accepted_answers(answers)
            if not accepted_answers:
                st.warning("请至少填写一个有效回答；如果都没有，可以直接生成岗位交付材料。")
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
            with st.spinner("正在根据补充信息重新评估岗位匹配..."):
                st.session_state.analysis_state = modules["run_analysis"](
                    st.session_state.resume_text,
                    st.session_state.job_description,
                    _combined_memory_context(),
                    st.session_state.github_context,
                    st.session_state.cumulative_answers,
                )
                st.session_state.question_round += 1
                st.session_state.generation_state = None
                _auto_save_workspace(modules, modules["get_settings"]())
            st.success("已更新记忆并刷新岗位评估。")
            st.rerun()


def _accepted_answers(answers):
    skipped = {"", "没有", "不清楚", "跳过", "none", "not sure", "skip"}
    return [answer for answer in answers if answer.answer.strip().lower() not in skipped]


def _build_workspace_snapshot(modules):
    WorkspaceSnapshot = modules["WorkspaceSnapshot"]
    generation = st.session_state.get("generation_state") or {}
    tailored = generation.get("tailored_resume") if isinstance(generation, dict) else None
    fact_check = generation.get("fact_check") if isinstance(generation, dict) else None
    return WorkspaceSnapshot(
        workspace_id=st.session_state.get("workspace_id", ""),
        updated_at=st.session_state.get("workspace_updated_at", ""),
        resume_text=st.session_state.resume_text,
        job_description=st.session_state.job_description,
        memory_text=st.session_state.memory_text,
        github_input=st.session_state.github_input,
        github_context=st.session_state.github_context,
        session_context_text=st.session_state.session_context_text,
        active_job_id=st.session_state.active_job_id,
        job_company=st.session_state.job_company,
        job_title=st.session_state.job_title,
        job_source_url=st.session_state.job_source_url,
        job_notes=st.session_state.job_notes,
        job_status=st.session_state.job_status,
        job_workspace=st.session_state.job_workspace.model_dump() if st.session_state.job_workspace else {},
        cumulative_answers=[
            item.model_dump() if hasattr(item, "model_dump") else item
            for item in st.session_state.cumulative_answers
        ],
        memory_candidates=[
            item.model_dump() if hasattr(item, "model_dump") else item
            for item in st.session_state.memory_candidates
        ],
        last_tailored_resume=tailored.model_dump() if hasattr(tailored, "model_dump") else {},
        last_fact_check=fact_check.model_dump() if hasattr(fact_check, "model_dump") else {},
    )


def _apply_workspace_snapshot(modules, snapshot) -> None:
    JobWorkspace = modules["JobWorkspace"]
    UserAnswer = modules["UserAnswer"]
    MemoryCandidate = modules["MemoryCandidate"]
    TailoredResumeResult = modules["TailoredResumeResult"]
    FactCheckResult = modules["FactCheckResult"]

    st.session_state.workspace_id = snapshot.workspace_id
    st.session_state.workspace_updated_at = snapshot.updated_at
    st.session_state.resume_text = snapshot.resume_text
    st.session_state.job_description = snapshot.job_description
    st.session_state.memory_text = snapshot.memory_text
    st.session_state.github_input = snapshot.github_input
    st.session_state.github_context = snapshot.github_context
    st.session_state.session_context_text = snapshot.session_context_text
    st.session_state.active_job_id = snapshot.active_job_id
    st.session_state.job_company = snapshot.job_company
    st.session_state.job_title = snapshot.job_title
    st.session_state.job_source_url = snapshot.job_source_url
    st.session_state.job_notes = snapshot.job_notes
    st.session_state.job_status = snapshot.job_status or "待分析"
    st.session_state.job_workspace = JobWorkspace.model_validate(snapshot.job_workspace or {})
    st.session_state.cumulative_answers = [
        UserAnswer.model_validate(item) for item in snapshot.cumulative_answers
    ]
    st.session_state.memory_candidates = [
        MemoryCandidate.model_validate(item) for item in snapshot.memory_candidates
    ]
    st.session_state.analysis_state = None
    if snapshot.last_tailored_resume and snapshot.last_fact_check:
        st.session_state.generation_state = {
            "tailored_resume": TailoredResumeResult.model_validate(snapshot.last_tailored_resume),
            "fact_check": FactCheckResult.model_validate(snapshot.last_fact_check),
        }
    else:
        st.session_state.generation_state = None


def _auto_save_workspace(modules, settings):
    if not st.session_state.get("workspace_key"):
        return None
    snapshot = _build_workspace_snapshot(modules)
    saved = modules["save_workspace"](
        st.session_state.workspace_key,
        snapshot,
        settings.workspace_salt or settings.app_password,
    )
    st.session_state.workspace_id = saved.workspace_id
    st.session_state.workspace_updated_at = saved.updated_at
    return saved


def _json_safe_state(state):
    result = {}
    for key, value in dict(state).items():
        if hasattr(value, "model_dump"):
            result[key] = value.model_dump()
        elif isinstance(value, list):
            result[key] = [item.model_dump() if hasattr(item, "model_dump") else item for item in value]
        else:
            result[key] = value
    return result


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
    job = _upsert_current_job(modules)
    if not job:
        return
    st.success("已保存岗位。")
    st.rerun()


def _upsert_current_job(modules):
    if not st.session_state.job_description.strip():
        st.error("请先填写岗位 JD。")
        return None
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
    _auto_save_workspace(modules, modules["get_settings"]())
    return job


def _batch_analyze_jobs(modules) -> None:
    if not st.session_state.resume_text.strip():
        st.error("请先在「2. 输入材料」上传或粘贴原始简历，再批量分析岗位库。")
        return
    jobs = [job for job in st.session_state.job_workspace.jobs if job.jd_text.strip()]
    if not jobs:
        st.error("岗位库里没有可分析的 JD。")
        return

    original_active_job_id = st.session_state.active_job_id or st.session_state.job_workspace.active_job_id
    progress = st.progress(0, text="准备批量分析岗位库...")
    success_count = 0
    failures = []

    with st.spinner("正在批量分析岗位库，完成后可以在 Shortlist 总览查看排序..."):
        for index, job in enumerate(jobs, start=1):
            progress.progress(
                int((index - 1) * 100 / len(jobs)),
                text=f"正在分析：{job.company or '未填写公司'} - {job.title or '未命名岗位'}",
            )
            try:
                state = modules["run_analysis"](
                    st.session_state.resume_text,
                    job.jd_text,
                    _combined_memory_context(),
                    st.session_state.github_context,
                )
                fit = state.get("job_fit_report")
                st.session_state.job_workspace = modules["update_job_status"](
                    st.session_state.job_workspace,
                    job.job_id,
                    "已分析",
                    fit.score if fit else None,
                    fit_recommendation=fit.recommendation if fit else "",
                    fit_risks=fit.risks if fit else None,
                    fit_matched_points=fit.matched_points if fit else None,
                    suggested_resume_angle=fit.suggested_resume_angle if fit else "",
                )
                if job.job_id == original_active_job_id:
                    st.session_state.analysis_state = state
                    st.session_state.job_description = job.jd_text
                success_count += 1
            except Exception as exc:
                failures.append(f"{job.company or '未填写公司'} - {job.title or '未命名岗位'}：{exc}")
        progress.progress(100, text="批量分析完成。")

    st.session_state.job_workspace.active_job_id = original_active_job_id
    st.session_state.active_job_id = original_active_job_id
    if success_count:
        st.success(f"已完成 {success_count} 个岗位的批量分析。")
    if failures:
        with st.expander("分析失败的岗位", expanded=True):
            for item in failures:
                st.write(f"- {item}")
    _auto_save_workspace(modules, modules["get_settings"]())


def render_shortlist_section(modules) -> None:
    st.header("5. Shortlist 总览")
    st.caption("参考 job-hunt 的求职工作区思路：把岗位按匹配度排序，用于决定优先分析和投递顺序。")

    workspace = st.session_state.job_workspace
    if not workspace.jobs:
        st.info("岗位库为空。先导入 `.jobs.json` 或保存一个 JD 后，这里会显示排序榜单。")
        return

    ranked = modules["ranked_jobs"](workspace)
    rows = [
        {
            "排名": index,
            "匹配度": f"{job.match_score}%" if job.match_score else "未分析",
            "公司": job.company or "未填写公司",
            "岗位": job.title or "未命名岗位",
            "状态": job.status,
            "平台": job.platform,
            "地点": job.location,
            "薪资": job.salary,
            "投递链接": job.source_url,
            "建议": job.fit_recommendation,
            "最后简历": job.last_resume_file,
        }
        for index, job in enumerate(ranked, start=1)
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    col_load, col_export = st.columns([1, 1])
    with col_load:
        selected_id = st.selectbox(
            "从 Shortlist 加载岗位",
            options=[job.job_id for job in ranked],
            format_func=lambda job_id: _short_job_label(ranked, job_id),
            key="shortlist_selected_job",
        )
        if st.button("加载该岗位继续处理", key="load_shortlist_job"):
            selected = _find_job(workspace, selected_id)
            if selected:
                _load_job_into_session(selected)
                st.success("已加载岗位。")
                st.rerun()

    with col_export:
        st.download_button(
            "下载 shortlist.json",
            data=modules["shortlist_to_json_text"](workspace).encode("utf-8"),
            file_name="shortlist.json",
            mime="application/json",
        )

    selected = _find_job(workspace, st.session_state.get("shortlist_selected_job", ""))
    if selected:
        with st.expander("当前选中岗位详情", expanded=False):
            st.write(f"**公司**：{selected.company or '未填写'}")
            st.write(f"**岗位**：{selected.title or '未命名岗位'}")
            st.write(f"**匹配度**：{selected.match_score}%")
            st.write(f"**建议**：{selected.fit_recommendation or '尚未分析'}")
            st.write(f"**简历切入角度**：{selected.suggested_resume_angle or '尚未分析'}")
            if selected.fit_matched_points:
                st.subheader("匹配点")
                for item in selected.fit_matched_points:
                    st.write(f"- {item}")
            if selected.fit_risks:
                st.subheader("风险")
                for item in selected.fit_risks:
                    st.write(f"- {item}")
            if selected.notes:
                st.subheader("备注")
                st.write(selected.notes)


def _short_job_label(jobs, job_id: str) -> str:
    for job in jobs:
        if job.job_id == job_id:
            score = f"{job.match_score}%" if job.match_score else "未分析"
            return f"{score} | {job.company or '未填写公司'} - {job.title or '未命名岗位'}"
    return job_id


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
    tabs = st.tabs(["定制简历", "开场白", "改动说明", "待确认", "核验信息"])
    with tabs[0]:
        st.markdown(fact_check.final_resume_markdown or tailored.resume_markdown)
    with tabs[1]:
        st.markdown(tailored.opener_markdown or "暂无开场白。")
        st.download_button(
            "下载 opener.md",
            data=(tailored.opener_markdown or "").encode("utf-8"),
            file_name="opener.md",
            mime="text/markdown",
        )
    with tabs[2]:
        st.markdown(tailored.changelog_markdown or "暂无改动说明。")
        st.download_button(
            "下载 changelog.md",
            data=(tailored.changelog_markdown or "").encode("utf-8"),
            file_name="changelog.md",
            mime="text/markdown",
        )
    with tabs[3]:
        st.subheader("待用户处理")
        missing = list(tailored.still_missing_info)
        if fact_check.needs_confirmation:
            st.subheader("待确认内容")
            for item in fact_check.needs_confirmation:
                st.write(f"- {item}")
        if missing:
            st.subheader("建议补充")
            for item in missing:
                st.write(f"- [请填写：{item}]")
        if not fact_check.needs_confirmation and not missing:
            st.success("当前没有明显待确认或待补充内容。")
    with tabs[4]:
        st.subheader("已融入岗位关键词")
        st.write("、".join(tailored.integrated_keywords) if tailored.integrated_keywords else "无")
        with st.expander("事实来源映射", expanded=False):
            st.dataframe([item.model_dump() for item in fact_check.evidence_map], use_container_width=True)
        with st.expander("原始 JSON", expanded=False):
            st.code(
                modules["pretty_json"](
                    {"tailored_resume": tailored.model_dump(), "fact_check": fact_check.model_dump()}
                ),
                language="json",
            )

    st.download_button(
        "下载完整 Markdown",
        data=full_markdown.encode("utf-8"),
        file_name="job_package.md",
        mime="text/markdown",
    )
    st.download_button(
        "下载完整 DOCX",
        data=modules["markdown_to_docx_bytes"](full_markdown),
        file_name="job_package.docx",
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
            _auto_save_workspace(modules, modules["get_settings"]())
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
                    _auto_save_workspace(modules, modules["get_settings"]())
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
