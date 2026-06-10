from __future__ import annotations

import base64
import hashlib
import json
import re
import sys
import traceback
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from src.requirement_classifier import cluster_hard_requirements, filter_actionable_hard_requirements, soft_group_for_requirement
from src.schemas import JobWorkspace, QuestionItem

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


st.set_page_config(page_title="简历定制 Agent", layout="wide")


def load_app_modules():
    from src.config import OUTPUT_DIR, get_settings
    from src.exporter.docx_exporter import markdown_to_docx_bytes, markdown_to_template_docx_bytes, save_docx
    from src.exporter.html_resume_exporter import (
        build_editable_resume_html,
        build_job_delivery_html,
        extract_first_docx_image_data_uri,
    )
    from src.exporter.markdown_exporter import build_full_markdown, save_markdown
    from src.file_parser import extract_text_from_upload
    from src.github_reader import collect_github_context, github_context_to_text
    from src.graph.workflow import run_analysis, run_generation
    from src.job_store import (
        get_active_job,
        infer_job_title_from_jd,
        job_import_supported_fields,
        job_workspace_to_json_text,
        job_workspace_template_json,
        parse_job_workspace_upload,
        parse_job_workspace_upload_with_report,
        ranked_jobs,
        shortlist_to_json_text,
        update_job_package,
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
        "markdown_to_template_docx_bytes": markdown_to_template_docx_bytes,
        "build_editable_resume_html": build_editable_resume_html,
        "build_job_delivery_html": build_job_delivery_html,
        "extract_first_docx_image_data_uri": extract_first_docx_image_data_uri,
        "save_docx": save_docx,
        "build_full_markdown": build_full_markdown,
        "save_markdown": save_markdown,
        "extract_text_from_upload": extract_text_from_upload,
        "collect_github_context": collect_github_context,
        "github_context_to_text": github_context_to_text,
        "get_active_job": get_active_job,
        "infer_job_title_from_jd": infer_job_title_from_jd,
        "job_import_supported_fields": job_import_supported_fields,
        "job_workspace_to_json_text": job_workspace_to_json_text,
        "job_workspace_template_json": job_workspace_template_json,
        "parse_job_workspace_upload": parse_job_workspace_upload,
        "parse_job_workspace_upload_with_report": parse_job_workspace_upload_with_report,
        "ranked_jobs": ranked_jobs,
        "shortlist_to_json_text": shortlist_to_json_text,
        "update_job_package": update_job_package,
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
        "resume_raw_text": "",
        "job_description": "",
        "analysis_state": None,
        "generation_state": None,
        "answers": [],
        "cumulative_answers": [],
        "question_round": 1,
        "question_answer_drafts": {},
        "memory_text": "",
        "github_input": "",
        "github_context": "",
        "memory_candidates": [],
        "session_context_text": "",
        "job_workspace": None,
        "job_import_report": None,
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
        "resume_template_docx_name": "",
        "resume_template_docx_bytes_b64": "",
        "editable_resume_markdown": "",
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

    prepare_tab, shortlist_tab, delivery_tab, source_tab, debug_tab = st.tabs(
        ["准备材料", "Shortlist 工作台", "当前岗位交付", "信息源", "导出与调试"]
    )

    with prepare_tab:
        render_input_section(modules)
        if st.session_state.analysis_state and st.session_state.analysis_state.get("resume_quality_report"):
            render_resume_quality_summary(st.session_state.analysis_state["resume_quality_report"])

    with shortlist_tab:
        render_job_workspace_section(modules)
        render_shortlist_section(modules)

    with delivery_tab:
        if st.session_state.analysis_state:
            render_analysis_section(modules)
        else:
            st.info("请先在「准备材料」填写简历和 JD，并点击「开始分析」。")
        if st.session_state.generation_state:
            render_generation_section(modules)

    with source_tab:
        render_context_section(modules)

    with debug_tab:
        render_debug_export_section(modules)


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


def render_resume_quality_summary(quality) -> None:
    st.subheader("简历质量体检")
    col1, col2, col3 = st.columns(3)
    col1.metric("简历质量", f"{quality.score}%")
    col2.metric("可评估经历", quality.evaluated_items)
    col3.metric("空壳经历", len(quality.empty_shell_items))
    st.write(quality.summary)
    if quality.empty_shell_items:
        st.warning(
            "重要提醒：存在空壳工作/项目经历。它们会被 STAR 评估跳过，"
            "AI 也不会替你编造内容；补全这些经历通常比直接改写更重要。"
        )
        with st.expander("空壳经历补全模板", expanded=False):
            st.markdown(
                "\n".join(
                    [
                        "请优先补全这些经历：",
                        *[f"- {item}" for item in quality.empty_shell_items[:6]],
                        "",
                        "建议按这个结构补：",
                        "1. 当时的场景/目标是什么？",
                        "2. 你具体做了什么？用了什么方法、工具或流程？",
                        "3. 交付了什么产物？",
                        "4. 有什么结果、反馈、规模或可确认数字？没有数字可以明确说没有。",
                    ]
                )
            )
    with st.expander("查看修复建议", expanded=False):
        for item in quality.recommended_fixes:
            st.write(f"- {item}")


def render_debug_export_section(modules) -> None:
    st.header("导出与调试")
    st.caption("这里集中放置备份、迁移和开发调试信息。普通使用时不需要频繁打开。")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.download_button(
            "导出工作区 JSON",
            data=modules["workspace_to_json_text"](_build_workspace_snapshot(modules)).encode("utf-8"),
            file_name="resume_agent_workspace.json",
            mime="application/json",
            key="debug_export_workspace",
        )
    with col2:
        st.download_button(
            "导出岗位库 JSON",
            data=modules["job_workspace_to_json_text"](st.session_state.job_workspace).encode("utf-8"),
            file_name="job_workspace.json",
            mime="application/json",
            key="debug_export_jobs",
        )
    with col3:
        st.download_button(
            "导出 shortlist.json",
            data=modules["shortlist_to_json_text"](st.session_state.job_workspace).encode("utf-8"),
            file_name="shortlist.json",
            mime="application/json",
            key="debug_export_shortlist",
        )

    st.subheader("调试信息")
    if st.session_state.analysis_state:
        with st.expander("完整分析状态", expanded=False):
            st.json(_json_safe_state(st.session_state.analysis_state))
    else:
        st.info("当前还没有分析状态。")

    if st.session_state.generation_state:
        with st.expander("完整生成状态", expanded=False):
            st.json(_json_safe_state(st.session_state.generation_state))
    else:
        st.info("当前还没有生成状态。")


def render_job_workspace_section(modules) -> None:
    st.header("岗位池")
    st.caption("这里保存目标岗位、JD、投递状态和备注。岗位库会导出为 job_workspace.json，不依赖数据库。")

    workspace = st.session_state.job_workspace
    import_col, template_col = st.columns([2, 1])
    with import_col:
        upload = st.file_uploader("导入岗位库 JSON / .jobs.json / JD 文本", type=["json", "txt"], key="job_workspace_upload")
    with template_col:
        st.download_button(
            "下载岗位库模板",
            data=modules["job_workspace_template_json"]().encode("utf-8"),
            file_name="job_workspace_template.json",
            mime="application/json",
            use_container_width=True,
        )
        with st.expander("支持字段", expanded=False):
            for label, fields in modules["job_import_supported_fields"]().items():
                st.write(f"**{label}**：`{', '.join(fields)}`")

    if upload:
        text = upload.getvalue().decode("utf-8", errors="ignore")
        workspace, report = modules["parse_job_workspace_upload_with_report"](text)
        st.session_state.job_import_report = report
        if report.get("errors"):
            st.error("岗位库导入失败。")
        elif workspace.jobs:
            st.session_state.job_workspace = workspace
            active_job = modules["get_active_job"](workspace)
            if active_job:
                _load_job_into_session(active_job, modules)
            _auto_save_workspace(modules, modules["get_settings"]())
            st.success(f"已导入 {len(workspace.jobs)} 个岗位。")
        else:
            st.warning("没有导入任何岗位，请检查 JSON 结构或直接粘贴单条 JD 文本。")

    if st.session_state.get("job_import_report"):
        _render_job_import_report(st.session_state.job_import_report)

    workspace = st.session_state.job_workspace
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
                    _load_job_into_session(selected, modules)
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
                "交付包": "已生成" if job.package_resume_markdown else "",
                "平台": job.platform,
                "地点": job.location,
                "薪资": job.salary,
                "链接": job.source_url,
                "更新时间": job.updated_at,
            }
            for job in st.session_state.job_workspace.jobs
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)


def _render_job_import_report(report: dict) -> None:
    source_labels = {
        "empty": "空文件",
        "job_workspace": "原生岗位库 JSON",
        "flexible_jobs_json": "通用岗位 JSON",
        "plain_text": "单条 JD 文本",
        "invalid_json": "无效 JSON",
    }
    with st.expander("最近一次岗位导入报告", expanded=bool(report.get("errors") or report.get("warnings"))):
        cols = st.columns(3)
        cols[0].metric("导入岗位", int(report.get("imported_count") or 0))
        cols[1].metric("跳过项目", int(report.get("skipped_count") or 0))
        cols[2].metric("识别类型", source_labels.get(report.get("source_type"), report.get("source_type", "未知")))

        for error in report.get("errors", []):
            st.error(error)
        for warning in report.get("warnings", []):
            st.warning(warning)

        recognized_fields = report.get("recognized_fields") or []
        if recognized_fields:
            st.write("已识别字段：")
            st.code(", ".join(recognized_fields), language="text")
        if not report.get("errors") and not recognized_fields and report.get("source_type") != "plain_text":
            st.caption("没有识别到标准字段。建议下载模板，对照字段名整理后重新导入。")


def render_input_section(modules) -> None:
    st.header("准备材料")
    left, right = st.columns(2)
    with left:
        uploaded = st.file_uploader("上传原始简历", type=["pdf", "docx", "txt"])
        pasted_resume = st.text_area("或粘贴简历文本", height=260, value=st.session_state.resume_text)
    with right:
        job_description = st.text_area("粘贴目标岗位 JD", height=330, value=st.session_state.job_description)

    if uploaded:
        try:
            uploaded_data = uploaded.getvalue()
            extracted_text = modules["extract_text_from_upload"](uploaded.name, uploaded_data)
            _set_resume_text(extracted_text, keep_existing_raw=False)
            if Path(uploaded.name).suffix.lower() == ".docx":
                _store_resume_template_docx(uploaded.name, uploaded_data)
            else:
                st.session_state.resume_template_docx_name = ""
                st.session_state.resume_template_docx_bytes_b64 = ""
            st.success(f"已读取文件：{uploaded.name}")
            if st.session_state.resume_template_docx_name:
                st.caption(f"已保存原始 DOCX 模板：{st.session_state.resume_template_docx_name}。最终可下载保留照片/页眉页脚、正文重新排版的 DOCX。")
        except Exception as exc:
            st.error(f"文件解析失败：{exc}")
    elif pasted_resume.strip():
        if pasted_resume.strip() != st.session_state.resume_text.strip():
            _set_resume_text(pasted_resume.strip(), keep_existing_raw=False)

    if job_description.strip():
        st.session_state.job_description = job_description.strip()

    if st.session_state.resume_text.strip():
        _render_resume_input_tools(modules)

    st.caption("点击“开始分析”后，可在「当前岗位交付」查看岗位评估、补充信息和生成结果。")

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
                    _combined_memory_context(),
                    st.session_state.github_context,
                    st.session_state.cumulative_answers,
                )
                st.session_state.generation_state = None
                st.session_state.answers = []
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

    st.header("当前岗位评估")
    tabs = st.tabs(["岗位评估", "补充信息"])
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
                general_risks = [
                    item
                    for item in fit.risks
                    if not item.startswith("尚缺少这些硬技能")
                    and not item.startswith("硬技能缺口")
                    and not item.startswith("软性证据缺口")
                    and not item.startswith("软性能力缺少")
                ]
                for item in general_risks or ["暂无明显风险。"]:
                    st.write(f"- {item}")
                if gap.hard_skill_gaps:
                    st.markdown("**硬技能 / 方法缺口**")
                    for item in gap.hard_skill_gaps[:6]:
                        st.write(f"- 未找到「{item}」的明确经历或证据。")
                if gap.soft_evidence_gaps:
                    st.markdown("**软性能力证据缺口**")
                    for item in gap.soft_evidence_gaps[:4]:
                        st.write(f"- {item.requirement}：{item.evidence_needed}")
                if not gap.hard_skill_gaps and not gap.soft_evidence_gaps:
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
        render_questions(modules, gap, quality)


def render_questions(modules, gap, quality=None) -> None:
    st.subheader("补充真实信息")
    st.caption("这里用于补全会影响简历质量的事实。可以填写后直接生成交付材料；不确定的内容可以跳过，系统会用占位符提示。")
    quality = quality or (st.session_state.analysis_state or {}).get("resume_quality_report")
    resume_quality_questions = _resume_quality_questions(quality)
    if quality and getattr(quality, "empty_shell_items", []):
        st.error(
            "重要提醒：你有空壳经历只有标题、时间或组织信息，没有行动和结果。"
            "这些内容无法被系统优化成有效简历经历；建议优先回答下面的空壳经历问题。"
        )
    if resume_quality_questions:
        st.markdown("**优先补全简历质量问题**")
        for question in resume_quality_questions[:3]:
            st.write(f"- {question.related_jd_requirement}")
    soft_gaps_for_display = _unanswered_soft_gaps(gap)
    hard_gaps_for_display = _unanswered_hard_gaps(gap)
    if soft_gaps_for_display:
        st.markdown("**优先补充软性能力的可验证场景**")
        for item in soft_gaps_for_display[:4]:
            st.write(f"- {item.requirement}：{item.evidence_needed}")
    if hard_gaps_for_display:
        st.markdown("**硬技能 / 方法待确认**")
        st.write("、".join(hard_gaps_for_display[:8]))
    questions = resume_quality_questions + _questions_for_display(gap)
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
        draft_key = _question_identity(question)
        widget_key = f"answer_{draft_key}"
        if widget_key not in st.session_state:
            st.session_state[widget_key] = st.session_state.question_answer_drafts.get(draft_key, "")
        st.markdown(f"**问题 {index}：{question.question}**")
        st.caption(f"用途：{question.why_needed}；关联 JD 要求：{question.related_jd_requirement}")
        answer = st.text_area(
            f"回答 {index}",
            key=widget_key,
            placeholder="请填写真实经历；也可以回答：没有 / 不清楚 / 跳过",
            height=100,
        )
        _remember_question_draft(modules, draft_key, answer)
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
            processed_answers = _processed_answers(answers)
            factual_answers = _accepted_answers(answers)
            if processed_answers:
                st.session_state.cumulative_answers = _merge_user_answers(
                    st.session_state.cumulative_answers,
                    processed_answers,
                )
            if factual_answers:
                st.session_state.session_context_text = _merge_answers_into_memory(
                    st.session_state.session_context_text,
                    factual_answers,
                    st.session_state.question_round,
                )
                st.session_state.memory_candidates.extend(selected_memory_candidates)
                st.session_state.memory_text = _merge_memory_candidates_into_text(
                    st.session_state.memory_text,
                    selected_memory_candidates,
                    st.session_state.question_round,
                )
            _persist_question_progress_to_active_job(modules, autosave=False)
            all_answers = st.session_state.cumulative_answers
            state = dict(st.session_state.analysis_state)
            state["user_answers"] = all_answers
            state["memory_text"] = _combined_memory_context()
            state["github_context"] = st.session_state.github_context
            with st.spinner("正在生成简历、开场白、改动说明并执行事实校验..."):
                st.session_state.generation_state = modules["run_generation"](state)
                tailored = st.session_state.generation_state["tailored_resume"]
                fact_check = st.session_state.generation_state["fact_check"]
                resume_md = fact_check.final_resume_markdown or tailored.resume_markdown
                st.session_state.editable_resume_markdown = resume_md
                modules["save_markdown"](resume_md, modules["OUTPUT_DIR"], "tailored_resume.md")
                modules["save_docx"](resume_md, modules["OUTPUT_DIR"], "tailored_resume.docx")
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
                    package_resume = fact_check.final_resume_markdown or tailored.resume_markdown
                    placeholders = _extract_placeholders(
                        "\n\n".join(
                            [
                                package_resume,
                                tailored.opener_markdown,
                                tailored.changelog_markdown,
                            ]
                        )
                    )
                    st.session_state.job_workspace = modules["update_job_package"](
                        st.session_state.job_workspace,
                        st.session_state.active_job_id,
                        package_resume,
                        tailored.opener_markdown,
                        tailored.changelog_markdown,
                        fact_check.needs_confirmation,
                        list(dict.fromkeys(placeholders + tailored.still_missing_info)),
                        [item.model_dump() for item in fact_check.evidence_map],
                        "tailored_resume.docx",
                    )
                _auto_save_workspace(modules, modules["get_settings"]())
            st.success("岗位交付材料已生成。")

    with col2:
        if st.button("保存补充并重新评估", type="secondary"):
            processed_answers = _processed_answers(answers)
            factual_answers = _accepted_answers(answers)
            if not processed_answers:
                st.warning("请至少填写一个回答；可以填写真实经历，也可以回答“没有 / 不清楚 / 跳过”。")
                return
            st.session_state.cumulative_answers = _merge_user_answers(
                st.session_state.cumulative_answers,
                processed_answers,
            )
            if factual_answers:
                st.session_state.session_context_text = _merge_answers_into_memory(
                    st.session_state.session_context_text,
                    factual_answers,
                    st.session_state.question_round,
                )
            st.session_state.memory_candidates.extend(selected_memory_candidates)
            st.session_state.memory_text = _merge_memory_candidates_into_text(
                st.session_state.memory_text,
                selected_memory_candidates,
                st.session_state.question_round,
            )
            _persist_question_progress_to_active_job(modules, autosave=False)
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
                _persist_question_progress_to_active_job(modules, autosave=False)
                _auto_save_workspace(modules, modules["get_settings"]())
            st.success("已更新记忆并刷新岗位评估。")
            st.rerun()


def _question_identity(question) -> str:
    raw = f"{question.related_jd_requirement.strip()}::{question.question.strip()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _remember_question_draft(modules, draft_key: str, answer: str) -> None:
    drafts = dict(st.session_state.get("question_answer_drafts", {}))
    previous = drafts.get(draft_key, "")
    if previous == answer:
        return
    if answer:
        drafts[draft_key] = answer
    else:
        drafts.pop(draft_key, None)
    st.session_state.question_answer_drafts = drafts
    _persist_question_progress_to_active_job(modules)


def _merge_user_answers(existing, new_answers):
    UserAnswer = type(new_answers[0]) if new_answers else None
    merged = []
    by_key = {}
    for answer in list(existing) + list(new_answers):
        answer_text = _answer_field(answer, "answer")
        if not answer_text.strip():
            continue
        key = _answer_identity(answer)
        by_key[key] = answer
    for answer in by_key.values():
        if UserAnswer and not isinstance(answer, UserAnswer):
            merged.append(UserAnswer.model_validate(answer))
        else:
            merged.append(answer)
    return merged


def _answer_identity(answer) -> str:
    raw = f"{_answer_field(answer, 'related_jd_requirement').strip().lower()}::{_question_key(_answer_field(answer, 'question'))}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _answer_field(answer, field: str) -> str:
    if isinstance(answer, dict):
        return str(answer.get(field, ""))
    return str(getattr(answer, field, ""))


def _persist_question_progress_to_active_job(modules, autosave: bool = True) -> None:
    active_job_id = st.session_state.get("active_job_id", "")
    if active_job_id and st.session_state.get("job_workspace"):
        job = _find_job(st.session_state.job_workspace, active_job_id)
        if job:
            job.question_answers = [
                item.model_dump() if hasattr(item, "model_dump") else item
                for item in st.session_state.get("cumulative_answers", [])
            ]
            job.question_answer_drafts = dict(st.session_state.get("question_answer_drafts", {}))
            job.question_round = max(1, int(st.session_state.get("question_round", 1) or 1))
            job.session_context_text = st.session_state.get("session_context_text", "")
    if autosave:
        _auto_save_workspace(modules, modules["get_settings"]())


def _accepted_answers(answers):
    skipped = {"", "没有", "不清楚", "跳过", "none", "not sure", "skip"}
    return [answer for answer in answers if answer.answer.strip().lower() not in skipped]


def _processed_answers(answers):
    return [answer for answer in answers if answer.answer.strip()]


def _set_resume_text(text: str, keep_existing_raw: bool = True) -> None:
    cleaned = (text or "").strip()
    st.session_state.resume_text = cleaned
    if not keep_existing_raw or not st.session_state.get("resume_raw_text"):
        st.session_state.resume_raw_text = cleaned


def _render_resume_input_tools(modules) -> None:
    report = _resume_format_report(st.session_state.resume_text)
    with st.expander("简历输入检查", expanded=report["needs_cleanup"]):
        st.write(report["summary"])
        if report["issues"]:
            for item in report["issues"]:
                st.write(f"- {item}")
        else:
            st.success("当前简历文本结构看起来可用。")
        st.caption("参考 job-hunt 的做法：先保存原文，再按用户选择整理格式。整理只处理断行、项目符号和常见章节标题，不改写任何事实。")

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("只整理格式", key="normalize_resume_text"):
                st.session_state.resume_text = _normalize_resume_format(st.session_state.resume_text)
                _auto_save_workspace(modules, modules["get_settings"]())
                st.success("已整理格式，原文已保留，可随时还原。")
                st.rerun()
        with col2:
            raw_text = st.session_state.get("resume_raw_text", "")
            if st.button("还原原文", key="restore_raw_resume", disabled=not bool(raw_text.strip())):
                st.session_state.resume_text = raw_text.strip()
                _auto_save_workspace(modules, modules["get_settings"]())
                st.success("已还原为原始简历文本。")
                st.rerun()
        with col3:
            st.download_button(
                "下载原文备份",
                data=(st.session_state.get("resume_raw_text") or st.session_state.resume_text).encode("utf-8"),
                file_name="resume.raw.txt",
                mime="text/plain",
            )


def _resume_format_report(text: str) -> dict:
    lines = [line.strip() for line in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n") if line.strip()]
    if not lines:
        return {"needs_cleanup": False, "summary": "尚未提供简历文本。", "issues": []}

    heading_count = sum(1 for line in lines if _looks_like_resume_heading(line))
    bullet_count = sum(1 for line in lines if _looks_like_resume_bullet(line))
    avg_len = sum(len(line) for line in lines) / max(1, len(lines))
    isolated_streak = _max_isolated_line_streak(lines)
    issues = []
    if heading_count < 2:
        issues.append("章节标题较少，可能是从 PDF/Word 复制后丢失了结构。")
    if bullet_count < 2:
        issues.append("列表项目较少，经历可能被压成了大段文本。")
    if avg_len < 12:
        issues.append("平均行长度偏短，可能存在一行一词或断行问题。")
    if isolated_streak >= 5:
        issues.append(f"检测到连续 {isolated_streak} 行短行，可能存在复制断行。")
    return {
        "needs_cleanup": bool(issues),
        "summary": f"识别到 {len(lines)} 行文本，约 {heading_count} 个章节标题、{bullet_count} 个列表项，平均每行 {avg_len:.1f} 字。",
        "issues": issues,
    }


def _normalize_resume_format(text: str) -> str:
    normalized = (
        (text or "")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\u200b", "")
        .replace("\u00ad", "")
    )
    raw_lines = normalized.split("\n")
    lines: list[str] = []
    for raw in raw_lines:
        line = raw.strip()
        if not line:
            lines.append("")
            continue
        line = _normalize_resume_bullet(line)
        if _is_common_resume_section(line):
            line = f"## {line.lstrip('#').strip()}"
        if lines and _should_merge_resume_lines(lines[-1], line):
            lines[-1] = f"{lines[-1].rstrip()} {line.strip()}"
        else:
            lines.append(line)
    return _collapse_blank_lines(lines).strip()


def _normalize_resume_bullet(line: str) -> str:
    for marker in ["·", "●", "▪", "◦", "▶", "•"]:
        if line.startswith(marker):
            return "- " + line[1:].strip()
    return line


def _should_merge_resume_lines(previous: str, current: str) -> bool:
    if not previous.strip() or not current.strip():
        return False
    if _looks_like_resume_heading(previous) or _looks_like_resume_heading(current):
        return False
    if _looks_like_resume_bullet(previous) and not _looks_like_resume_bullet(current):
        return len(current.strip()) <= 30
    if _looks_like_resume_bullet(current):
        return False
    if previous.rstrip().endswith(("。", "！", "？", ".", "!", "?", "：", ":")):
        return False
    return len(previous.strip()) <= 36 or len(current.strip()) <= 24


def _collapse_blank_lines(lines: list[str]) -> str:
    result: list[str] = []
    blank = False
    for line in lines:
        if not line.strip():
            if result and not blank:
                result.append("")
            blank = True
            continue
        result.append(line.rstrip())
        blank = False
    return "\n".join(result)


def _looks_like_resume_heading(line: str) -> bool:
    stripped = line.strip()
    if stripped.startswith("#"):
        return True
    return _is_common_resume_section(stripped)


def _looks_like_resume_bullet(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith(("-", "*", "+", "•", "·", "●", "▪", "◦", "▶")) or bool(re.match(r"^\d+[.、)]", stripped))


def _is_common_resume_section(line: str) -> bool:
    stripped = line.strip(" #：:")
    section_terms = [
        "个人信息",
        "基本信息",
        "联系方式",
        "个人优势",
        "专业技能",
        "核心能力",
        "技能特长",
        "工作经历",
        "实习经历",
        "项目经历",
        "项目经验",
        "教育背景",
        "教育经历",
        "自我评价",
        "求职意向",
        "证书",
        "奖项",
        "荣誉",
    ]
    return len(stripped) <= 12 and stripped in section_terms


def _max_isolated_line_streak(lines: list[str]) -> int:
    best = 0
    current = 0
    for line in lines:
        if 1 <= len(line.strip()) <= 3:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def _store_resume_template_docx(file_name: str, data: bytes) -> None:
    st.session_state.resume_template_docx_name = file_name
    st.session_state.resume_template_docx_bytes_b64 = base64.b64encode(data).decode("ascii")


def _get_resume_template_docx_bytes() -> bytes:
    encoded = st.session_state.get("resume_template_docx_bytes_b64", "")
    if not encoded:
        return b""
    try:
        return base64.b64decode(encoded)
    except Exception:
        return b""


def _resume_export_title() -> str:
    parts = [
        st.session_state.get("job_company", "").strip(),
        st.session_state.get("job_title", "").strip(),
        "定制简历",
    ]
    return " - ".join(part for part in parts if part)


def _html_resume_storage_key(content_seed: str = "") -> str:
    active = st.session_state.get("active_job_id", "") or "current"
    workspace = st.session_state.get("workspace_id", "") or "local"
    content_hash = hashlib.sha1((content_seed or "").encode("utf-8")).hexdigest()[:10]
    raw = f"{workspace}:{active}:{_resume_export_title()}:{content_hash}"
    return "resume-agent:" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _extract_placeholders(text: str) -> list[str]:
    matches = re.findall(r"\[(请填写|需用户确认)[:：]([^\]]+)\]", text or "")
    return [f"{kind}：{content.strip()}" for kind, content in matches if content.strip()]


def _build_workspace_snapshot(modules):
    WorkspaceSnapshot = modules["WorkspaceSnapshot"]
    generation = st.session_state.get("generation_state") or {}
    tailored = generation.get("tailored_resume") if isinstance(generation, dict) else None
    fact_check = generation.get("fact_check") if isinstance(generation, dict) else None
    return WorkspaceSnapshot(
        workspace_id=st.session_state.get("workspace_id", ""),
        updated_at=st.session_state.get("workspace_updated_at", ""),
        resume_text=st.session_state.resume_text,
        resume_raw_text=st.session_state.get("resume_raw_text", ""),
        resume_template_docx_name=st.session_state.resume_template_docx_name,
        resume_template_docx_bytes_b64=st.session_state.resume_template_docx_bytes_b64,
        job_description=st.session_state.job_description,
        memory_text=st.session_state.memory_text,
        github_input=st.session_state.github_input,
        github_context=st.session_state.github_context,
        session_context_text=st.session_state.session_context_text,
        question_answer_drafts=dict(st.session_state.question_answer_drafts),
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
    st.session_state.resume_raw_text = getattr(snapshot, "resume_raw_text", "") or snapshot.resume_text
    st.session_state.resume_template_docx_name = snapshot.resume_template_docx_name
    st.session_state.resume_template_docx_bytes_b64 = snapshot.resume_template_docx_bytes_b64
    st.session_state.job_description = snapshot.job_description
    st.session_state.memory_text = snapshot.memory_text
    st.session_state.github_input = snapshot.github_input
    st.session_state.github_context = snapshot.github_context
    st.session_state.session_context_text = snapshot.session_context_text
    st.session_state.question_answer_drafts = dict(snapshot.question_answer_drafts or {})
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

    active_job = _find_job(st.session_state.job_workspace, st.session_state.active_job_id)
    if active_job and (
        getattr(active_job, "question_answers", None)
        or getattr(active_job, "question_answer_drafts", None)
        or getattr(active_job, "session_context_text", None)
    ):
        st.session_state.cumulative_answers = [
            UserAnswer.model_validate(item) for item in active_job.question_answers
        ]
        st.session_state.question_answer_drafts = dict(active_job.question_answer_drafts or {})
        st.session_state.session_context_text = active_job.session_context_text or st.session_state.session_context_text
        st.session_state.question_round = max(1, int(active_job.question_round or 1))


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


def _load_job_into_session(job, modules=None) -> None:
    st.session_state.active_job_id = job.job_id
    st.session_state.job_workspace.active_job_id = job.job_id
    st.session_state.job_company = job.company
    st.session_state.job_title = job.title
    st.session_state.job_source_url = job.source_url
    st.session_state.job_notes = job.notes
    st.session_state.job_status = job.status
    st.session_state.job_description = job.jd_text
    st.session_state.analysis_state = None
    st.session_state.generation_state = _job_package_to_generation_state(job, modules) if modules else None
    st.session_state.editable_resume_markdown = job.package_resume_markdown or ""
    UserAnswer = modules["UserAnswer"] if modules else None
    st.session_state.cumulative_answers = [
        UserAnswer.model_validate(item) if UserAnswer else item
        for item in getattr(job, "question_answers", [])
    ]
    st.session_state.question_answer_drafts = dict(getattr(job, "question_answer_drafts", {}) or {})
    st.session_state.session_context_text = getattr(job, "session_context_text", "") or ""
    st.session_state.question_round = max(1, int(getattr(job, "question_round", 1) or 1))


def _job_package_to_generation_state(job, modules):
    if not modules or not job.package_resume_markdown:
        return None
    TailoredResumeResult = modules["TailoredResumeResult"]
    FactCheckResult = modules["FactCheckResult"]
    return {
        "tailored_resume": TailoredResumeResult(
            resume_markdown=job.package_resume_markdown,
            opener_markdown=job.package_opener_markdown,
            changelog_markdown=job.package_changelog_markdown,
            still_missing_info=job.package_placeholders,
            evidence_map=job.package_evidence_map,
        ),
        "fact_check": FactCheckResult(
            final_resume_markdown=job.package_resume_markdown,
            evidence_map=job.package_evidence_map,
            needs_confirmation=job.package_needs_confirmation,
        ),
    }


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
    existing = _find_job(st.session_state.job_workspace, st.session_state.active_job_id)
    job = JobPosting(
        job_id=st.session_state.active_job_id,
        company=st.session_state.job_company.strip(),
        title=title,
        source_url=st.session_state.job_source_url.strip(),
        jd_text=st.session_state.job_description.strip(),
        status=st.session_state.job_status,
        notes=st.session_state.job_notes.strip(),
        match_score=getattr(existing, "match_score", 0) if existing else 0,
        fit_recommendation=getattr(existing, "fit_recommendation", "") if existing else "",
        fit_risks=getattr(existing, "fit_risks", []) if existing else [],
        fit_matched_points=getattr(existing, "fit_matched_points", []) if existing else [],
        suggested_resume_angle=getattr(existing, "suggested_resume_angle", "") if existing else "",
        last_resume_file=getattr(existing, "last_resume_file", "") if existing else "",
        package_generated_at=getattr(existing, "package_generated_at", "") if existing else "",
        package_resume_markdown=getattr(existing, "package_resume_markdown", "") if existing else "",
        package_opener_markdown=getattr(existing, "package_opener_markdown", "") if existing else "",
        package_changelog_markdown=getattr(existing, "package_changelog_markdown", "") if existing else "",
        package_needs_confirmation=getattr(existing, "package_needs_confirmation", []) if existing else [],
        package_placeholders=getattr(existing, "package_placeholders", []) if existing else [],
        package_evidence_map=getattr(existing, "package_evidence_map", []) if existing else [],
        question_answers=[
            item.model_dump() if hasattr(item, "model_dump") else item
            for item in st.session_state.cumulative_answers
        ] or (getattr(existing, "question_answers", []) if existing else []),
        question_answer_drafts=dict(st.session_state.question_answer_drafts)
        or (getattr(existing, "question_answer_drafts", {}) if existing else {}),
        question_round=max(1, int(st.session_state.question_round or 1)),
        session_context_text=st.session_state.session_context_text
        or (getattr(existing, "session_context_text", "") if existing else ""),
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
    st.header("Shortlist 总览")
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
            "交付包": "已生成" if job.package_resume_markdown else "",
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
                _load_job_into_session(selected, modules)
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
            st.write(f"**交付包**：{'已生成' if selected.package_resume_markdown else '尚未生成'}")
            if selected.package_generated_at:
                st.write(f"**生成时间**：{selected.package_generated_at}")
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
            package = " | 已生成" if job.package_resume_markdown else ""
            return f"{score}{package} | {job.company or '未填写公司'} - {job.title or '未命名岗位'}"
    return job_id


def _filter_repeated_questions(questions):
    asked_keys = {_question_key(answer.question) for answer in st.session_state.cumulative_answers}
    answered_requirements = {
        answer.related_jd_requirement.strip().lower()
        for answer in st.session_state.cumulative_answers
        if answer.answer.strip() and answer.related_jd_requirement.strip()
    }
    answered_requirement_tokens = _requirement_tokens(answered_requirements)
    filtered = []
    seen_current = set()
    for question in questions:
        key = _question_key(question.question)
        requirement = question.related_jd_requirement.strip().lower()
        if key in asked_keys or key in seen_current:
            continue
        if requirement and requirement in answered_requirements:
            continue
        if requirement and _requirement_already_answered(requirement, answered_requirements, answered_requirement_tokens):
            continue
        if _is_generic_project_question(question.question) and _answered_requirement(answered_requirements, "隐藏经历挖掘"):
            continue
        if _is_metric_question(question.question) and _answered_requirement(answered_requirements, "结果量化"):
            continue
        if _is_resume_quality_question(question.related_jd_requirement) and _resume_quality_requirement_answered(
            question.related_jd_requirement,
            answered_requirements,
        ):
            continue
        seen_current.add(key)
        filtered.append(question)
    return filtered


def _resume_quality_questions(quality):
    if not quality:
        return []
    questions = []
    for item in getattr(quality, "empty_shell_items", [])[:3]:
        label = f"空壳经历：{item}"
        questions.append(
            QuestionItem(
                question=(
                    f"简历中这段经历目前只有标题或背景，缺少具体内容：「{item}」。"
                    "请按 4 点补充：1）当时的场景/目标；2）你具体做了什么，使用了什么方法、工具或流程；"
                    "3）交付了什么产物；4）产生了什么结果、反馈、规模或可确认数字。"
                    "没有数字可以说明“没有可确认数字”；如果这段经历不想写入简历，请回答“跳过”。"
                ),
                why_needed="空壳经历会被参考项目式 STAR/PAR 评估跳过，补全后才能用于岗位匹配和定制简历；AI 不会替你编造经历。",
                related_jd_requirement=label,
            )
        )
    for item in getattr(quality, "missing_result_items", [])[:2]:
        label = f"缺结果：{item[:60]}"
        questions.append(
            QuestionItem(
                question=(
                    f"这条经历写了行动，但缺少结果：「{item}」。"
                    "请补充最终交付、上线、排名、用户反馈、影响范围、效率变化或你能确认的结果；没有结果可以回答“没有”。"
                ),
                why_needed="结果是 STAR/PAR 评估中的 R，没有结果会降低简历说服力。",
                related_jd_requirement=label,
            )
        )
    for item in getattr(quality, "missing_metric_items", [])[:2]:
        label = f"缺量化：{item[:60]}"
        questions.append(
            QuestionItem(
                question=(
                    f"这条经历缺少可确认数字或规模：「{item}」。"
                    "是否有可确认的数据，例如数量、周期、版本次数、参与人数、用户反馈数量、效率提升或影响范围？没有数字请回答“没有”，不要编造。"
                ),
                why_needed="可确认数字能提升可信度；没有数字时系统会保留事实，不会编造。",
                related_jd_requirement=label,
            )
        )
    return questions


def _questions_for_display(gap):
    questions = []
    seen_soft_groups = set()
    seen_questions = set()
    hard_requirements = filter_actionable_hard_requirements(_unanswered_hard_gaps(gap))
    deferred_questions = []

    for item in _unanswered_soft_gaps(gap):
        group_name = item.requirement.strip()
        question_text = item.suggested_question.strip()
        if not group_name or not question_text:
            continue
        key = group_name.lower()
        if key in seen_soft_groups:
            continue
        seen_soft_groups.add(key)
        questions.append(
            QuestionItem(
                question=question_text,
                why_needed="软性能力不能只写标签，必须用具体经历证明，避免空泛表述。",
                related_jd_requirement=group_name,
            )
        )

    for question in getattr(gap, "questions_to_user", []) or []:
        group = soft_group_for_requirement(question.related_jd_requirement) or soft_group_for_requirement(question.question)
        if group:
            group_name = str(group["name"])
            key = group_name.lower()
            if key in seen_soft_groups:
                continue
            seen_soft_groups.add(key)
            questions.append(
                QuestionItem(
                    question=str(group["question"]),
                    why_needed="软性能力不能只写标签，必须用具体经历证明，避免空泛表述。",
                    related_jd_requirement=group_name,
                )
            )
            continue
        if _is_legacy_keyword_question(question.question):
            if question.related_jd_requirement.strip():
                hard_requirements.append(question.related_jd_requirement.strip())
            continue
        deferred_questions.append(question)

    for group in cluster_hard_requirements(filter_actionable_hard_requirements(hard_requirements)):
        key = str(group["name"]).strip().lower()
        if key in seen_questions:
            continue
        seen_questions.add(key)
        related = "、".join(str(item) for item in group.get("requirements", []) if str(item).strip())
        questions.append(
            QuestionItem(
                question=str(group["question"]),
                why_needed=f"用于判断是否可以把「{group['name']}」写入定制简历，避免逐个关键词机械追问或无来源补写。",
                related_jd_requirement=related or str(group["name"]),
            )
        )

    for question in deferred_questions:
        key = f"{question.related_jd_requirement.strip().lower()}::{question.question.strip().lower()}"
        if question.question.strip() and key not in seen_questions:
            seen_questions.add(key)
            questions.append(question)
    return questions


def _answered_requirement_state():
    answered_requirements = {
        answer.related_jd_requirement.strip().lower()
        for answer in st.session_state.cumulative_answers
        if answer.answer.strip() and answer.related_jd_requirement.strip()
    }
    return answered_requirements, _requirement_tokens(answered_requirements)


def _unanswered_hard_gaps(gap):
    answered_requirements, answered_tokens = _answered_requirement_state()
    result = []
    for item in getattr(gap, "hard_skill_gaps", []) or []:
        if not _requirement_already_answered(item, answered_requirements, answered_tokens):
            result.append(item)
    return result


def _unanswered_soft_gaps(gap):
    answered_requirements, answered_tokens = _answered_requirement_state()
    result = []
    for item in getattr(gap, "soft_evidence_gaps", []) or []:
        if not _requirement_already_answered(item.requirement, answered_requirements, answered_tokens):
            result.append(item)
    return result


def _is_legacy_keyword_question(text: str) -> bool:
    return text.strip().startswith("JD 提到") and "你是否有真实使用或相关项目经历" in text


def _question_key(text: str) -> str:
    normalized = "".join(ch for ch in text.lower() if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")
    replacements = ["请说明", "请补充", "是否", "你", "的", "和", "或", "与"]
    for item in replacements:
        normalized = normalized.replace(item, "")
    return normalized[:80]


def _answered_requirement(answered_requirements: set[str], requirement: str) -> bool:
    target = requirement.lower()
    return any(target == item or target in item or item in target for item in answered_requirements)


def _requirement_tokens(requirements: set[str]) -> set[str]:
    tokens: set[str] = set()
    for requirement in requirements:
        for token in re.split(r"[、,，/｜|;；\s]+", requirement):
            cleaned = token.strip().lower()
            if len(cleaned) >= 2:
                tokens.add(cleaned)
    return tokens


def _requirement_already_answered(requirement: str, answered_requirements: set[str], answered_tokens: set[str]) -> bool:
    if _answered_requirement(answered_requirements, requirement):
        return True
    tokens = _requirement_tokens({requirement})
    if not tokens:
        return False
    if tokens & answered_tokens:
        return True
    joined_answered = "\n".join(answered_requirements)
    return any(token in joined_answered for token in tokens)


def _is_generic_project_question(text: str) -> bool:
    return "原始简历没有写出" in text and any(term in text for term in ["项目", "开源仓库", "自动化工具"])


def _is_metric_question(text: str) -> bool:
    return any(term in text for term in ["可确认数据", "用户数", "效率提升", "准确率", "处理规模"])


def _is_resume_quality_question(requirement: str) -> bool:
    return requirement.startswith(("空壳经历：", "缺结果：", "缺量化："))


def _resume_quality_requirement_answered(requirement: str, answered_requirements: set[str]) -> bool:
    target = requirement.strip().lower()
    target_kind = target.split("：", 1)[0] if "：" in target else target
    return any(
        item == target
        or (item.startswith(target_kind) and (target in item or item in target))
        for item in answered_requirements
    )


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


def _save_edited_resume_package(modules, tailored, fact_check) -> None:
    edited_resume = st.session_state.editable_resume_markdown.strip()
    if not edited_resume:
        st.warning("简历正文为空，未保存。")
        return
    if hasattr(fact_check, "final_resume_markdown"):
        fact_check.final_resume_markdown = edited_resume
    if hasattr(tailored, "resume_markdown"):
        tailored.resume_markdown = edited_resume
    if st.session_state.active_job_id:
        placeholders = _extract_placeholders(
            "\n\n".join(
                [
                    edited_resume,
                    getattr(tailored, "opener_markdown", ""),
                    getattr(tailored, "changelog_markdown", ""),
                ]
            )
        )
        st.session_state.job_workspace = modules["update_job_package"](
            st.session_state.job_workspace,
            st.session_state.active_job_id,
            edited_resume,
            getattr(tailored, "opener_markdown", ""),
            getattr(tailored, "changelog_markdown", ""),
            getattr(fact_check, "needs_confirmation", []),
            list(dict.fromkeys(placeholders + getattr(tailored, "still_missing_info", []))),
            [item.model_dump() if hasattr(item, "model_dump") else item for item in getattr(fact_check, "evidence_map", [])],
            "tailored_resume.docx",
        )
    _auto_save_workspace(modules, modules["get_settings"]())


def render_generation_section(modules) -> None:
    state = st.session_state.generation_state
    tailored = state["tailored_resume"]
    fact_check = state["fact_check"]
    base_resume_markdown = fact_check.final_resume_markdown or tailored.resume_markdown
    if not st.session_state.get("editable_resume_markdown"):
        st.session_state.editable_resume_markdown = base_resume_markdown

    st.header("岗位交付材料")
    tabs = st.tabs(["定制简历", "开场白", "改动说明", "待确认", "核验信息"])
    with tabs[0]:
        st.caption("主交付改为参考 job-hunt 的 HTML/PDF 简历视图：简历正文可编辑，开场白、改动说明和证据表只在 Agent 中展示，不写进简历文件。")
        st.session_state.editable_resume_markdown = st.text_area(
            "可投递简历正文源 Markdown",
            value=st.session_state.editable_resume_markdown,
            height=360,
            key="editable_resume_textarea",
        )

        photo_upload = st.file_uploader(
            "上传原始 DOCX 用于读取简历头像",
            type=["docx"],
            key="resume_template_docx_uploader",
            help="如果上传 DOCX，系统会尝试读取其中第一张图片作为简历照片。最终主交付是 HTML/PDF，不再承诺复刻任意 Word 模板。",
        )
        if photo_upload:
            _store_resume_template_docx(photo_upload.name, photo_upload.getvalue())
            _auto_save_workspace(modules, modules["get_settings"]())
            st.success(f"已保存头像来源 DOCX：{photo_upload.name}")

        template_bytes = _get_resume_template_docx_bytes()
        photo_data_uri = modules["extract_first_docx_image_data_uri"](template_bytes) if template_bytes else ""
        storage_key = _html_resume_storage_key(st.session_state.editable_resume_markdown or "")
        active_job = _find_job(st.session_state.job_workspace, st.session_state.active_job_id)
        final_resume_html = modules["build_editable_resume_html"](
            st.session_state.editable_resume_markdown or "",
            title=_resume_export_title(),
            photo_data_uri=photo_data_uri,
            storage_key=storage_key,
        )
        delivery_html = modules["build_job_delivery_html"](
            resume_markdown=st.session_state.editable_resume_markdown or "",
            opener_markdown=getattr(tailored, "opener_markdown", ""),
            changelog_markdown=getattr(tailored, "changelog_markdown", ""),
            title=_resume_export_title(),
            company=st.session_state.get("job_company", "") or getattr(active_job, "company", ""),
            job_title=st.session_state.get("job_title", "") or getattr(active_job, "title", ""),
            match_score=getattr(active_job, "match_score", 0) if active_job else 0,
            source_url=getattr(active_job, "source_url", "") if active_job else "",
            photo_data_uri=photo_data_uri,
            storage_key=f"{storage_key}:delivery",
        )

        st.markdown("**最终可投递简历**")
        st.caption("下方预览和下载的 HTML 只包含简历正文，可直接编辑并导出 PDF；改动说明、开场白和核验信息仅在 Agent 页面展示，不写进最终简历。若要写回 Agent 岗位库，请修改上方 Markdown 后点击“保存微调到当前岗位”。")
        components.html(final_resume_html, height=820, scrolling=True)

        primary_col1, primary_col2, primary_col3 = st.columns(3)
        with primary_col1:
            st.download_button(
                "下载最终简历 HTML",
                data=final_resume_html.encode("utf-8"),
                file_name="final_resume.html",
                mime="text/html",
            )
        with primary_col2:
            st.download_button(
                "下载源 Markdown",
                data=(st.session_state.editable_resume_markdown or "").encode("utf-8"),
                file_name="tailored_resume.md",
                mime="text/markdown",
            )
        with primary_col3:
            if st.button("保存微调到当前岗位", key="save_edited_resume"):
                _save_edited_resume_package(modules, tailored, fact_check)
                st.success("已保存微调后的简历正文。")

        with st.expander("辅助审查材料：完整交付 HTML", expanded=False):
            st.caption("这个文件包含简历、开场白和改动说明三个标签，适合自己复盘，不建议直接作为投递简历发送。")
            st.download_button(
                "下载完整交付 HTML",
                data=delivery_html.encode("utf-8"),
                file_name="tailored_delivery_review.html",
                mime="text/html",
            )

        with st.expander("辅助格式：DOCX", expanded=False):
            st.caption("DOCX 是辅助编辑格式。任意 Word 模板无法稳定保真；正式投递建议优先使用上方 HTML 打印得到的 PDF。")
            docx_col1, docx_col2 = st.columns(2)
            with docx_col1:
                st.download_button(
                    "下载普通 DOCX",
                    data=modules["markdown_to_docx_bytes"](st.session_state.editable_resume_markdown or ""),
                    file_name="tailored_resume.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            with docx_col2:
                st.download_button(
                    "下载照片版 DOCX",
                    data=(
                        modules["markdown_to_template_docx_bytes"](
                            st.session_state.editable_resume_markdown or "",
                            template_bytes,
                        )
                        if template_bytes
                        else b""
                    ),
                    file_name="tailored_resume_photo.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    disabled=not bool(template_bytes),
                    help="仅尝试保留 DOCX 中的图片/页眉页脚外壳，不保证复刻原 Word 模板。",
                )
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


def render_context_section(modules) -> None:
    st.header("信息源")
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
