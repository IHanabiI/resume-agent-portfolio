from __future__ import annotations

import base64
import html
import json
import mimetypes
import re
import zipfile
from io import BytesIO

import markdown

from src.resume_markdown_normalizer import normalize_resume_project_blocks


def build_editable_resume_html(
    resume_markdown: str,
    *,
    title: str = "定制简历",
    photo_data_uri: str = "",
    storage_key: str = "resume-agent-editable-resume",
) -> str:
    resume_html = _markdown_to_html(resume_markdown)
    safe_title = html.escape(title or "定制简历")
    safe_storage_key = json.dumps(storage_key or "resume-agent-editable-resume", ensure_ascii=False)
    filename_json = json.dumps(_pdf_filename("", title or "定制简历"), ensure_ascii=False)
    photo_html = (
        f'<img class="resume-photo" src="{html.escape(photo_data_uri, quote=True)}" alt="简历照片">'
        if photo_data_uri
        else ""
    )
    template = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>__TITLE__</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
  <style>
    :root {
      --ink: #111827;
      --muted: #64748b;
      --line: #dbe3ef;
      --accent: #205781;
      --accent-strong: #174264;
      --paper: #ffffff;
      --bg: #eef3f8;
      --warn: #b45309;
      --danger: #b91c1c;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: "Microsoft YaHei", "Source Han Sans CN", "Noto Sans CJK SC", Arial, sans-serif;
      font-size: 13px;
      line-height: 1.48;
    }
    button {
      height: 34px;
      border: 1px solid #cbd5e1;
      background: #fff;
      color: #111827;
      padding: 0 12px;
      border-radius: 6px;
      font: inherit;
      cursor: pointer;
      white-space: nowrap;
    }
    button:hover { background: #f8fafc; border-color: #94a3b8; }
    button.primary {
      background: var(--accent);
      border-color: var(--accent);
      color: #fff;
      font-weight: 700;
    }
    button.primary:hover { background: var(--accent-strong); border-color: var(--accent-strong); }
    .topbar {
      position: sticky;
      top: 0;
      z-index: 20;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 12px 18px;
      background: rgba(255, 255, 255, .96);
      border-bottom: 1px solid var(--line);
      backdrop-filter: blur(10px);
    }
    .title {
      margin: 0;
      font-size: 16px;
      line-height: 1.25;
      letter-spacing: 0;
      overflow-wrap: anywhere;
    }
    .actions {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 8px;
      flex-wrap: wrap;
    }
    .save-status {
      min-width: 92px;
      color: #047857;
      font-size: 12px;
      text-align: right;
    }
    .save-status.editing { color: var(--muted); }
    .shell {
      width: min(980px, calc(100vw - 28px));
      margin: 18px auto 42px;
      overflow-x: auto;
      padding-bottom: 24px;
    }
    .page {
      position: relative;
      width: 210mm;
      min-height: 297mm;
      margin: 0 auto;
      padding: 16mm 17mm 15mm;
      background: var(--paper);
      box-shadow: 0 14px 34px rgba(15, 23, 42, .16);
    }
    .resume-photo {
      position: absolute;
      top: 16mm;
      right: 17mm;
      width: 25mm;
      height: 33mm;
      object-fit: cover;
      border: 1px solid #dbe3ef;
      background: #fff;
    }
    #resume {
      min-height: 262mm;
      outline: none;
      padding-right: __PHOTO_PAD__;
    }
    #resume:focus { outline: 2px solid #93c5fd; outline-offset: 6px; }
    #resume h1 {
      margin: 0 0 5px;
      font-size: 21px;
      line-height: 1.15;
      color: #111827;
      letter-spacing: 0;
    }
    #resume h2 {
      margin: 12px 0 6px;
      padding-bottom: 3px;
      border-bottom: 1px solid var(--line);
      font-size: 14.5px;
      line-height: 1.25;
      color: var(--accent);
      letter-spacing: 0;
    }
    #resume h3 {
      margin: 8px 0 4px;
      font-size: 13px;
      line-height: 1.28;
      color: #111827;
      letter-spacing: 0;
    }
    #resume p { margin: 3px 0; }
    #resume ul, #resume ol {
      margin: 4px 0 7px 18px;
      padding: 0;
    }
    #resume li {
      margin: 2px 0;
      padding-left: 2px;
    }
    #resume strong { font-weight: 700; }
    #resume a { color: #0f4c81; text-decoration: none; }
    .ph-fill, .ph-confirm {
      display: inline;
      padding: 1px 5px;
      border-radius: 4px;
      font-weight: 700;
    }
    .ph-fill {
      background: #fee2e2;
      color: var(--danger);
      border: 1px dashed #dc2626;
    }
    .ph-confirm {
      background: #fef3c7;
      color: var(--warn);
      border: 1px dashed #d97706;
    }
    @page {
      size: A4;
      margin: 0;
    }
    @media (max-width: 760px) {
      .topbar { align-items: flex-start; flex-direction: column; }
      .actions { justify-content: flex-start; width: 100%; }
      .save-status { text-align: left; }
      .shell { width: calc(100vw - 18px); margin-top: 12px; }
      .page { margin-left: 0; margin-right: 0; }
    }
    @media print {
      body { background: #fff; }
      .topbar { display: none !important; }
      .shell { width: auto; margin: 0; padding: 0; overflow: visible; }
      .page {
        width: 210mm;
        min-height: 297mm;
        margin: 0;
        padding: 16mm 17mm 15mm;
        box-shadow: none;
      }
      #resume { padding-right: __PHOTO_PAD__; }
    }
  </style>
</head>
<body>
  <header class="topbar">
    <h1 class="title">__TITLE__</h1>
    <div class="actions">
      <span class="save-status" id="save-status">已自动保存</span>
      <button id="restore-btn" type="button">还原初始版本</button>
      <button class="primary" id="pdf-btn" type="button">导出 PDF</button>
    </div>
  </header>
  <main class="shell">
    <article class="page" id="resume-paper">
      __PHOTO_HTML__
      <section id="resume" contenteditable="true">__RESUME_HTML__</section>
    </article>
  </main>
  <script>
    const storageKey = __STORAGE_KEY__;
    const pdfFilename = __FILENAME_JSON__;
    const resumeEl = document.getElementById("resume");
    const resumePaper = document.getElementById("resume-paper");
    const statusEl = document.getElementById("save-status");
    const initialHtml = resumeEl.innerHTML;
    const saved = localStorage.getItem(storageKey);
    if (saved !== null) {
      resumeEl.innerHTML = saved;
    }

    function setStatus(text, editing) {
      statusEl.textContent = text;
      statusEl.classList.toggle("editing", Boolean(editing));
    }

    let timer = null;
    resumeEl.addEventListener("paste", event => {
      event.preventDefault();
      const text = (event.clipboardData || window.clipboardData).getData("text/plain");
      document.execCommand("insertText", false, text);
    });
    resumeEl.addEventListener("input", () => {
      setStatus("编辑中...", true);
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        localStorage.setItem(storageKey, resumeEl.innerHTML);
        setStatus("已自动保存", false);
      }, 450);
    });

    document.getElementById("restore-btn").addEventListener("click", () => {
      localStorage.removeItem(storageKey);
      resumeEl.innerHTML = initialHtml;
      setStatus("已还原", false);
    });

    document.getElementById("pdf-btn").addEventListener("click", () => {
      const cloned = resumePaper.cloneNode(true);
      cloned.style.boxShadow = "none";
      cloned.style.margin = "0";
      cloned.querySelector("#resume")?.removeAttribute("contenteditable");

      if (window.html2pdf) {
        html2pdf().set({
          margin: 0,
          filename: pdfFilename,
          image: { type: "jpeg", quality: 0.98 },
          html2canvas: { scale: 2, useCORS: true, backgroundColor: "#fff" },
          jsPDF: { unit: "mm", format: "a4", orientation: "portrait" },
          pagebreak: { mode: ["css", "legacy"] }
        }).from(cloned).save();
      } else {
        window.print();
      }
    });
  </script>
</body>
</html>"""

    return (
        template.replace("__TITLE__", safe_title)
        .replace("__PHOTO_HTML__", photo_html)
        .replace("__PHOTO_PAD__", "33mm" if photo_data_uri else "0")
        .replace("__RESUME_HTML__", resume_html)
        .replace("__STORAGE_KEY__", safe_storage_key)
        .replace("__FILENAME_JSON__", filename_json)
    )


def build_job_delivery_html(
    *,
    resume_markdown: str,
    opener_markdown: str = "",
    changelog_markdown: str = "",
    title: str = "岗位交付材料",
    company: str = "",
    job_title: str = "",
    match_score: int | None = None,
    source_url: str = "",
    photo_data_uri: str = "",
    storage_key: str = "resume-agent-delivery",
) -> str:
    resume_html = _markdown_to_html(resume_markdown)
    opener_html = _markdown_to_html(opener_markdown) if opener_markdown.strip() else _empty_state("暂无开场白。")
    changelog_html = (
        _highlight_changelog_fill(_markdown_to_html(changelog_markdown))
        if changelog_markdown.strip()
        else _empty_state("暂无改动说明。")
    )
    safe_title = html.escape(title or "岗位交付材料")
    safe_company = html.escape(company or "未填写公司")
    safe_job_title = html.escape(job_title or "未命名岗位")
    safe_source_url = html.escape(source_url or "", quote=True)
    safe_storage_key = json.dumps(storage_key or "resume-agent-delivery", ensure_ascii=False)
    opener_json = json.dumps(opener_markdown or "", ensure_ascii=False)
    filename_json = json.dumps(_pdf_filename(company, job_title), ensure_ascii=False)
    match_text = _format_match_score(match_score)
    photo_html = (
        f'<img class="resume-photo" src="{html.escape(photo_data_uri, quote=True)}" alt="简历照片">'
        if photo_data_uri
        else ""
    )
    source_link = (
        f'<a class="source-link" href="{safe_source_url}" target="_blank" rel="noopener">查看原岗位</a>'
        if source_url
        else ""
    )

    template = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>__TITLE__</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
  <style>
    :root {
      --ink: #111827;
      --muted: #64748b;
      --soft: #f8fafc;
      --line: #dbe3ef;
      --accent: #205781;
      --accent-strong: #174264;
      --paper: #ffffff;
      --bg: #eef3f8;
      --warn: #b45309;
      --danger: #b91c1c;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: "Microsoft YaHei", "Source Han Sans CN", "Noto Sans CJK SC", Arial, sans-serif;
      font-size: 13px;
      line-height: 1.48;
    }
    button {
      height: 34px;
      border: 1px solid #cbd5e1;
      background: #fff;
      color: #111827;
      padding: 0 12px;
      border-radius: 6px;
      font: inherit;
      cursor: pointer;
      white-space: nowrap;
    }
    button:hover { background: #f8fafc; border-color: #94a3b8; }
    button.primary {
      background: var(--accent);
      border-color: var(--accent);
      color: #fff;
      font-weight: 700;
    }
    button.primary:hover { background: var(--accent-strong); border-color: var(--accent-strong); }
    .topbar {
      position: sticky;
      top: 0;
      z-index: 20;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 12px 18px;
      background: rgba(255, 255, 255, .96);
      border-bottom: 1px solid var(--line);
      backdrop-filter: blur(10px);
    }
    .title-block { min-width: 0; }
    .title-block h1 {
      margin: 0;
      font-size: 16px;
      line-height: 1.25;
      letter-spacing: 0;
      overflow-wrap: anywhere;
    }
    .meta {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 5px;
      color: var(--muted);
      font-size: 12px;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      min-height: 22px;
      padding: 2px 8px;
      border: 1px solid #e2e8f0;
      border-radius: 999px;
      background: #fff;
    }
    .source-link { color: var(--accent); text-decoration: none; font-weight: 700; }
    .source-link:hover { text-decoration: underline; }
    .actions {
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 8px;
      flex-wrap: wrap;
    }
    .save-status {
      min-width: 92px;
      color: #047857;
      font-size: 12px;
      text-align: right;
    }
    .save-status.editing { color: var(--muted); }
    .shell {
      width: min(1180px, calc(100vw - 28px));
      margin: 18px auto 42px;
    }
    .tabs {
      display: flex;
      gap: 4px;
      border-bottom: 1px solid var(--line);
      margin-bottom: 16px;
      overflow-x: auto;
    }
    .tab {
      border: 0;
      border-bottom: 2px solid transparent;
      border-radius: 0;
      background: transparent;
      color: var(--muted);
      height: 38px;
      padding: 0 16px;
      font-weight: 700;
    }
    .tab.active {
      color: var(--accent);
      border-bottom-color: var(--accent);
      background: transparent;
    }
    .view { display: none; }
    .view.active { display: block; }
    .resume-wrap {
      overflow-x: auto;
      padding: 2px 0 24px;
    }
    .page {
      position: relative;
      width: 210mm;
      min-height: 297mm;
      margin: 0 auto;
      padding: 16mm 17mm 15mm;
      background: var(--paper);
      box-shadow: 0 14px 34px rgba(15, 23, 42, .16);
    }
    .resume-photo {
      position: absolute;
      top: 16mm;
      right: 17mm;
      width: 25mm;
      height: 33mm;
      object-fit: cover;
      border: 1px solid #dbe3ef;
      background: #fff;
    }
    #resume {
      min-height: 262mm;
      outline: none;
      padding-right: __PHOTO_PAD__;
    }
    #resume:focus { outline: 2px solid #93c5fd; outline-offset: 6px; }
    #resume h1 {
      margin: 0 0 5px;
      font-size: 21px;
      line-height: 1.15;
      color: #111827;
      letter-spacing: 0;
    }
    #resume h2 {
      margin: 12px 0 6px;
      padding-bottom: 3px;
      border-bottom: 1px solid var(--line);
      font-size: 14.5px;
      line-height: 1.25;
      color: var(--accent);
      letter-spacing: 0;
    }
    #resume h3 {
      margin: 8px 0 4px;
      font-size: 13px;
      line-height: 1.28;
      color: #111827;
      letter-spacing: 0;
    }
    #resume p { margin: 3px 0; }
    #resume ul, #resume ol {
      margin: 4px 0 7px 18px;
      padding: 0;
    }
    #resume li {
      margin: 2px 0;
      padding-left: 2px;
    }
    #resume strong { font-weight: 700; }
    #resume a { color: #0f4c81; text-decoration: none; }
    .panel {
      background: #fff;
      border: 1px solid var(--line);
      padding: 24px 28px;
      min-height: 240px;
      box-shadow: 0 2px 10px rgba(15, 23, 42, .04);
    }
    .panel h1, .panel h2, .panel h3 {
      margin: 14px 0 8px;
      letter-spacing: 0;
    }
    .panel h1 { font-size: 20px; }
    .panel h2 { font-size: 16px; color: var(--accent); }
    .panel h3 { font-size: 14px; }
    .panel p { margin: 6px 0; }
    .panel ul, .panel ol { margin: 6px 0 8px 22px; padding: 0; }
    .panel li { margin: 3px 0; }
    .empty {
      color: var(--muted);
      padding: 36px 0;
      text-align: center;
    }
    .changelog-fill {
      margin: 8px 0 12px;
      padding: 10px 12px;
      background: #fffbeb;
      border-left: 3px solid #f59e0b;
      color: #78350f;
    }
    .ph-fill, .ph-confirm {
      display: inline;
      padding: 1px 5px;
      border-radius: 4px;
      font-weight: 700;
    }
    .ph-fill {
      background: #fee2e2;
      color: var(--danger);
      border: 1px dashed #dc2626;
    }
    .ph-confirm {
      background: #fef3c7;
      color: var(--warn);
      border: 1px dashed #d97706;
    }
    @page {
      size: A4;
      margin: 0;
    }
    @media (max-width: 760px) {
      .topbar { align-items: flex-start; flex-direction: column; }
      .actions { justify-content: flex-start; width: 100%; }
      .save-status { text-align: left; }
      .shell { width: calc(100vw - 18px); margin-top: 12px; }
      .panel { padding: 18px; }
      .page {
        margin-left: 0;
        margin-right: 0;
      }
    }
    @media print {
      body { background: #fff; }
      .topbar, .tabs, .panel, .view:not(#resume-view) { display: none !important; }
      .shell, .resume-wrap { width: auto; margin: 0; padding: 0; overflow: visible; }
      #resume-view { display: block !important; }
      .page {
        width: 210mm;
        min-height: 297mm;
        margin: 0;
        padding: 16mm 17mm 15mm;
        box-shadow: none;
      }
      #resume { padding-right: __PHOTO_PAD__; }
    }
  </style>
</head>
<body>
  <header class="topbar">
    <div class="title-block">
      <h1>__TITLE__</h1>
      <div class="meta">
        <span class="pill">公司：__COMPANY__</span>
        <span class="pill">岗位：__JOB_TITLE__</span>
        <span class="pill">匹配度：__MATCH_TEXT__</span>
        __SOURCE_LINK__
      </div>
    </div>
    <div class="actions">
      <span class="save-status" id="save-status">已自动保存</span>
      <button id="restore-btn" type="button">还原初始版本</button>
      <button id="copy-opener-btn" type="button">复制开场白</button>
      <button class="primary" id="pdf-btn" type="button">导出 PDF</button>
    </div>
  </header>

  <main class="shell">
    <nav class="tabs" aria-label="交付材料">
      <button class="tab active" type="button" data-tab="resume-view">定制简历</button>
      <button class="tab" type="button" data-tab="opener-view">开场白</button>
      <button class="tab" type="button" data-tab="changelog-view">改动说明</button>
    </nav>

    <section id="resume-view" class="view active">
      <div class="resume-wrap">
        <article class="page" id="resume-paper">
          __PHOTO_HTML__
          <section id="resume" contenteditable="true">__RESUME_HTML__</section>
        </article>
      </div>
    </section>
    <section id="opener-view" class="view">
      <article class="panel">__OPENER_HTML__</article>
    </section>
    <section id="changelog-view" class="view">
      <article class="panel">__CHANGELOG_HTML__</article>
    </section>
  </main>

  <script>
    const storageKey = __STORAGE_KEY__;
    const openerMarkdown = __OPENER_JSON__;
    const pdfFilename = __FILENAME_JSON__;
    const resumeEl = document.getElementById("resume");
    const resumePaper = document.getElementById("resume-paper");
    const statusEl = document.getElementById("save-status");
    const initialHtml = resumeEl.innerHTML;
    const saved = localStorage.getItem(storageKey);
    if (saved !== null) {
      resumeEl.innerHTML = saved;
    }

    function setStatus(text, editing) {
      statusEl.textContent = text;
      statusEl.classList.toggle("editing", Boolean(editing));
    }

    document.querySelectorAll(".tab").forEach(button => {
      button.addEventListener("click", () => {
        document.querySelectorAll(".tab").forEach(item => item.classList.toggle("active", item === button));
        document.querySelectorAll(".view").forEach(view => view.classList.toggle("active", view.id === button.dataset.tab));
      });
    });

    let timer = null;
    resumeEl.addEventListener("paste", event => {
      event.preventDefault();
      const text = (event.clipboardData || window.clipboardData).getData("text/plain");
      document.execCommand("insertText", false, text);
    });
    resumeEl.addEventListener("input", () => {
      setStatus("编辑中...", true);
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        localStorage.setItem(storageKey, resumeEl.innerHTML);
        setStatus("已自动保存", false);
      }, 450);
    });

    document.getElementById("restore-btn").addEventListener("click", () => {
      localStorage.removeItem(storageKey);
      resumeEl.innerHTML = initialHtml;
      setStatus("已还原", false);
    });

    document.getElementById("copy-opener-btn").addEventListener("click", async () => {
      if (!openerMarkdown.trim()) return;
      await navigator.clipboard.writeText(openerMarkdown);
      const btn = document.getElementById("copy-opener-btn");
      btn.textContent = "已复制";
      setTimeout(() => { btn.textContent = "复制开场白"; }, 1600);
    });

    document.getElementById("pdf-btn").addEventListener("click", () => {
      const cloned = resumePaper.cloneNode(true);
      cloned.style.boxShadow = "none";
      cloned.style.margin = "0";
      cloned.querySelector("#resume")?.removeAttribute("contenteditable");

      if (window.html2pdf) {
        html2pdf().set({
          margin: 0,
          filename: pdfFilename,
          image: { type: "jpeg", quality: 0.98 },
          html2canvas: { scale: 2, useCORS: true, backgroundColor: "#fff" },
          jsPDF: { unit: "mm", format: "a4", orientation: "portrait" },
          pagebreak: { mode: ["css", "legacy"] }
        }).from(cloned).save();
      } else {
        window.print();
      }
    });
  </script>
</body>
</html>"""

    return (
        template.replace("__TITLE__", safe_title)
        .replace("__COMPANY__", safe_company)
        .replace("__JOB_TITLE__", safe_job_title)
        .replace("__MATCH_TEXT__", html.escape(match_text))
        .replace("__SOURCE_LINK__", source_link)
        .replace("__PHOTO_HTML__", photo_html)
        .replace("__PHOTO_PAD__", "33mm" if photo_data_uri else "0")
        .replace("__RESUME_HTML__", resume_html)
        .replace("__OPENER_HTML__", opener_html)
        .replace("__CHANGELOG_HTML__", changelog_html)
        .replace("__STORAGE_KEY__", safe_storage_key)
        .replace("__OPENER_JSON__", opener_json)
        .replace("__FILENAME_JSON__", filename_json)
    )


def build_shortlist_delivery_html(
    *,
    jobs,
    title: str = "求职 Shortlist",
    photo_data_uri: str = "",
    storage_key: str = "resume-agent-shortlist",
) -> str:
    job_sections: list[str] = []
    nav_items: list[str] = []
    for index, job in enumerate(jobs, start=1):
        company = getattr(job, "company", "") or "未填写公司"
        job_title = getattr(job, "title", "") or "未命名岗位"
        score = _format_match_score(getattr(job, "match_score", 0))
        status = getattr(job, "status", "") or "待分析"
        source_url = getattr(job, "source_url", "") or ""
        location = getattr(job, "location", "") or ""
        salary = getattr(job, "salary", "") or ""
        recommendation = getattr(job, "fit_recommendation", "") or "尚未分析"
        angle = getattr(job, "suggested_resume_angle", "") or ""
        resume_markdown = getattr(job, "package_resume_markdown", "") or ""
        opener_markdown = getattr(job, "package_opener_markdown", "") or ""
        changelog_markdown = getattr(job, "package_changelog_markdown", "") or ""
        jd_text = getattr(job, "jd_text", "") or ""
        risks = getattr(job, "fit_risks", []) or []
        matched_points = getattr(job, "fit_matched_points", []) or []

        active = " active" if index == 1 else ""
        resume_html = _markdown_to_html(resume_markdown) if resume_markdown.strip() else _empty_state("该岗位尚未生成定制简历。")
        opener_html = _markdown_to_html(opener_markdown) if opener_markdown.strip() else _empty_state("该岗位暂无开场白。")
        changelog_html = _highlight_changelog_fill(_markdown_to_html(changelog_markdown)) if changelog_markdown.strip() else _empty_state("该岗位暂无改动说明。")
        jd_html = _markdown_to_html(jd_text) if jd_text.strip() else _empty_state("该岗位暂无 JD 正文。")
        source_link = (
            f'<a href="{html.escape(source_url, quote=True)}" target="_blank" rel="noopener">原岗位链接</a>'
            if source_url
            else '<span class="muted">无岗位链接</span>'
        )
        photo_html = (
            f'<img class="resume-photo" src="{html.escape(photo_data_uri, quote=True)}" alt="简历照片">'
            if photo_data_uri
            else ""
        )
        filename = _pdf_filename(company, job_title)
        item_storage_key = f"{storage_key}:{getattr(job, 'job_id', '') or index}"

        nav_items.append(
            f"""
            <button class="job-item{active}" type="button" onclick="selectJob({index})">
              <span class="rank">#{index}</span>
              <span class="job-title">{html.escape(job_title)}</span>
              <span class="company">{html.escape(company)}</span>
              <span class="score">{html.escape(score)}</span>
            </button>
            """
        )

        matched_html = _list_block("匹配点", matched_points)
        risks_html = _list_block("风险", risks)
        meta_bits = [
            f"状态：{status}",
            f"匹配度：{score}",
            f"地点：{location}" if location else "",
            f"薪资：{salary}" if salary else "",
        ]
        meta_html = "".join(f"<span>{html.escape(bit)}</span>" for bit in meta_bits if bit)

        job_sections.append(
            f"""
            <section id="job-{index}" class="job-view{active}" data-filename="{html.escape(filename, quote=True)}" data-storage="{html.escape(item_storage_key, quote=True)}">
              <header class="job-header">
                <div>
                  <h2>{html.escape(company)} · {html.escape(job_title)}</h2>
                  <div class="job-meta">{meta_html}{source_link}</div>
                </div>
                <div class="job-actions">
                  <button type="button" onclick="copyOpener()">复制开场白</button>
                  <button type="button" onclick="resetResume()">还原简历</button>
                  <button class="primary" type="button" onclick="exportPdf()">导出当前简历 PDF</button>
                </div>
              </header>
              <div class="recommendation">
                <strong>投递建议</strong>
                <p>{html.escape(recommendation)}</p>
                {f'<p><strong>简历切入角度</strong>：{html.escape(angle)}</p>' if angle else ''}
                {matched_html}
                {risks_html}
              </div>
              <div class="tabs">
                <button class="tab active" type="button" onclick="selectTab(this, 'resume')">简历</button>
                <button class="tab" type="button" onclick="selectTab(this, 'opener')">开场白</button>
                <button class="tab" type="button" onclick="selectTab(this, 'changelog')">改动说明</button>
                <button class="tab" type="button" onclick="selectTab(this, 'jd')">JD</button>
              </div>
              <div class="tab-panel active" data-panel="resume">
                <div class="resume-wrap">
                  <article class="resume-page">
                    {photo_html}
                    <div class="resume-content" contenteditable="true" spellcheck="false" data-original="{html.escape(resume_html, quote=True)}">{resume_html}</div>
                  </article>
                </div>
              </div>
              <div class="tab-panel" data-panel="opener">
                <div class="panel">{opener_html}</div>
                <textarea class="opener-source" aria-hidden="true">{html.escape(opener_markdown)}</textarea>
              </div>
              <div class="tab-panel" data-panel="changelog">
                <div class="panel">{changelog_html}</div>
              </div>
              <div class="tab-panel" data-panel="jd">
                <div class="panel">{jd_html}</div>
              </div>
            </section>
            """
        )

    if not job_sections:
        job_sections.append('<section class="job-view active"><div class="empty">岗位库为空。</div></section>')

    safe_title = html.escape(title or "求职 Shortlist")
    template = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>__TITLE__</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
  <style>
    :root {
      --ink: #111827;
      --muted: #64748b;
      --line: #dbe3ef;
      --accent: #205781;
      --accent-strong: #174264;
      --paper: #ffffff;
      --bg: #eef3f8;
      --soft: #f8fafc;
      --warn: #b45309;
      --danger: #b91c1c;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: "Microsoft YaHei", "Source Han Sans CN", "Noto Sans CJK SC", Arial, sans-serif;
      font-size: 13px;
      line-height: 1.48;
    }
    button {
      min-height: 34px;
      border: 1px solid #cbd5e1;
      background: #fff;
      color: #111827;
      padding: 6px 12px;
      border-radius: 6px;
      font: inherit;
      cursor: pointer;
    }
    button:hover { background: #f8fafc; border-color: #94a3b8; }
    button.primary {
      background: var(--accent);
      border-color: var(--accent);
      color: #fff;
      font-weight: 700;
    }
    button.primary:hover { background: var(--accent-strong); border-color: var(--accent-strong); }
    .topbar {
      position: sticky;
      top: 0;
      z-index: 20;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      padding: 12px 18px;
      background: rgba(255, 255, 255, .96);
      border-bottom: 1px solid var(--line);
      backdrop-filter: blur(10px);
    }
    .topbar h1 { margin: 0; font-size: 16px; letter-spacing: 0; }
    .layout {
      display: grid;
      grid-template-columns: 300px minmax(0, 1fr);
      gap: 18px;
      width: min(1440px, calc(100vw - 28px));
      margin: 18px auto 42px;
    }
    .sidebar {
      position: sticky;
      top: 64px;
      align-self: start;
      max-height: calc(100vh - 86px);
      overflow: auto;
      border: 1px solid var(--line);
      background: #fff;
    }
    .sidebar-title {
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      font-weight: 700;
    }
    .job-list { display: grid; gap: 0; }
    .job-item {
      display: grid;
      grid-template-columns: auto 1fr auto;
      gap: 4px 8px;
      width: 100%;
      min-height: 72px;
      padding: 10px 12px;
      border: 0;
      border-bottom: 1px solid #edf2f7;
      border-radius: 0;
      text-align: left;
      background: #fff;
    }
    .job-item.active {
      background: #edf7ff;
      border-left: 3px solid var(--accent);
    }
    .rank { color: var(--muted); font-weight: 700; }
    .job-title { min-width: 0; font-weight: 700; overflow-wrap: anywhere; }
    .company {
      grid-column: 2 / 4;
      color: var(--muted);
      overflow-wrap: anywhere;
    }
    .score { color: var(--accent); font-weight: 700; }
    .job-view { display: none; }
    .job-view.active { display: block; }
    .job-header {
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-start;
      padding: 18px 20px;
      border: 1px solid var(--line);
      background: #fff;
    }
    .job-header h2 {
      margin: 0 0 7px;
      font-size: 18px;
      letter-spacing: 0;
      overflow-wrap: anywhere;
    }
    .job-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      color: var(--muted);
      font-size: 12px;
    }
    .job-meta span, .job-meta a {
      display: inline-flex;
      align-items: center;
      min-height: 22px;
      padding: 2px 8px;
      border: 1px solid #e2e8f0;
      border-radius: 999px;
      background: #fff;
      color: inherit;
      text-decoration: none;
    }
    .job-meta a { color: var(--accent); font-weight: 700; }
    .job-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 8px; }
    .recommendation {
      margin-top: 12px;
      padding: 14px 18px;
      border: 1px solid var(--line);
      background: #fff;
    }
    .recommendation p { margin: 5px 0; }
    .recommendation ul { margin: 6px 0 8px 18px; padding: 0; }
    .tabs {
      display: flex;
      gap: 4px;
      margin-top: 16px;
      border-bottom: 1px solid var(--line);
      overflow-x: auto;
    }
    .tab {
      border: 0;
      border-bottom: 2px solid transparent;
      border-radius: 0;
      background: transparent;
      color: var(--muted);
      min-height: 38px;
      padding: 0 16px;
      font-weight: 700;
    }
    .tab.active {
      color: var(--accent);
      border-bottom-color: var(--accent);
      background: transparent;
    }
    .tab-panel { display: none; }
    .tab-panel.active { display: block; }
    .resume-wrap {
      overflow-x: auto;
      padding: 18px 0 24px;
    }
    .resume-page {
      position: relative;
      width: 210mm;
      min-height: 297mm;
      margin: 0 auto;
      padding: 16mm 17mm 15mm;
      background: var(--paper);
      box-shadow: 0 14px 34px rgba(15, 23, 42, .16);
    }
    .resume-photo {
      position: absolute;
      top: 16mm;
      right: 17mm;
      width: 25mm;
      height: 33mm;
      object-fit: cover;
      border: 1px solid #dbe3ef;
      background: #fff;
    }
    .resume-content {
      min-height: 262mm;
      outline: none;
      padding-right: __PHOTO_PAD__;
    }
    .resume-content:focus { outline: 2px solid #93c5fd; outline-offset: 6px; }
    .resume-content h1 {
      margin: 0 0 5px;
      font-size: 21px;
      line-height: 1.15;
      color: #111827;
      letter-spacing: 0;
    }
    .resume-content h2 {
      margin: 12px 0 6px;
      padding-bottom: 3px;
      border-bottom: 1px solid var(--line);
      font-size: 14.5px;
      line-height: 1.25;
      color: var(--accent);
      letter-spacing: 0;
    }
    .resume-content h3 {
      margin: 8px 0 4px;
      font-size: 13px;
      line-height: 1.28;
      color: #111827;
      letter-spacing: 0;
    }
    .resume-content p { margin: 3px 0; }
    .resume-content ul, .resume-content ol { margin: 4px 0 7px 18px; padding: 0; }
    .resume-content li { margin: 2px 0; padding-left: 2px; }
    .panel {
      margin-top: 18px;
      min-height: 240px;
      padding: 24px 28px;
      border: 1px solid var(--line);
      background: #fff;
    }
    .panel h1, .panel h2, .panel h3 { margin: 14px 0 8px; letter-spacing: 0; }
    .panel h1 { font-size: 20px; }
    .panel h2 { font-size: 16px; color: var(--accent); }
    .panel h3 { font-size: 14px; }
    .panel p { margin: 6px 0; }
    .panel ul, .panel ol { margin: 8px 0 12px 22px; padding: 0; }
    .empty {
      padding: 28px;
      color: var(--muted);
      border: 1px dashed #cbd5e1;
      background: #fff;
    }
    .opener-source { display: none; }
    .muted { color: var(--muted); }
    .ph-fill, .ph-confirm {
      display: inline;
      padding: 1px 5px;
      border-radius: 4px;
      font-weight: 700;
    }
    .ph-fill {
      background: #fee2e2;
      color: var(--danger);
      border: 1px dashed #dc2626;
    }
    .ph-confirm {
      background: #fef3c7;
      color: var(--warn);
      border: 1px dashed #d97706;
    }
    .changelog-fill {
      margin: 10px 0 18px;
      padding: 12px 14px;
      border-left: 4px solid #f59e0b;
      background: #fffbeb;
    }
    @page { size: A4; margin: 0; }
    @media (max-width: 920px) {
      .layout { grid-template-columns: 1fr; }
      .sidebar { position: static; max-height: none; }
      .job-header { flex-direction: column; }
      .job-actions { justify-content: flex-start; }
      .resume-wrap { width: calc(100vw - 28px); }
      .resume-page { margin-left: 0; margin-right: 0; }
    }
    @media print {
      body { background: #fff; }
      .topbar, .sidebar, .job-header, .recommendation, .tabs, .panel, .tab-panel:not([data-panel="resume"]) { display: none !important; }
      .layout { display: block; width: auto; margin: 0; }
      .job-view { display: none !important; }
      .job-view.active { display: block !important; }
      .tab-panel { display: none !important; }
      .tab-panel.active[data-panel="resume"] { display: block !important; }
      .resume-wrap { width: auto; margin: 0; padding: 0; overflow: visible; }
      .resume-page {
        width: 210mm;
        min-height: 297mm;
        margin: 0;
        padding: 16mm 17mm 15mm;
        box-shadow: none;
      }
      .resume-content { padding-right: __PHOTO_PAD__; }
    }
  </style>
</head>
<body>
  <header class="topbar">
    <h1>__TITLE__</h1>
    <div class="muted">按匹配度排序的岗位交付包</div>
  </header>
  <main class="layout">
    <aside class="sidebar">
      <div class="sidebar-title">岗位列表</div>
      <div class="job-list">__NAV_ITEMS__</div>
    </aside>
    <section class="content">__JOB_SECTIONS__</section>
  </main>
  <script>
    function currentJob() {
      return document.querySelector('.job-view.active');
    }
    function selectJob(index) {
      document.querySelectorAll('.job-item').forEach(item => item.classList.remove('active'));
      document.querySelectorAll('.job-view').forEach(item => item.classList.remove('active'));
      const nav = document.querySelectorAll('.job-item')[index - 1];
      const view = document.getElementById('job-' + index);
      if (nav) nav.classList.add('active');
      if (view) view.classList.add('active');
    }
    function selectTab(button, name) {
      const view = currentJob();
      if (!view) return;
      view.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
      view.querySelectorAll('.tab-panel').forEach(panel => panel.classList.remove('active'));
      button.classList.add('active');
      const panel = view.querySelector('[data-panel="' + name + '"]');
      if (panel) panel.classList.add('active');
    }
    function exportPdf() {
      const view = currentJob();
      if (!view) return;
      const page = view.querySelector('.resume-page');
      const filename = view.dataset.filename || '定制简历.pdf';
      if (window.html2pdf) {
        html2pdf().set({
          margin: 0,
          filename: filename,
          image: { type: 'jpeg', quality: 0.98 },
          html2canvas: { scale: 2, useCORS: true },
          jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
        }).from(page).save();
      } else {
        window.print();
      }
    }
    function copyOpener() {
      const view = currentJob();
      if (!view) return;
      const source = view.querySelector('.opener-source');
      const text = source ? source.value : '';
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(() => alert('开场白已复制'));
        return;
      }
      const temp = document.createElement('textarea');
      temp.value = text;
      document.body.appendChild(temp);
      temp.select();
      document.execCommand('copy');
      document.body.removeChild(temp);
      alert('开场白已复制');
    }
    function resetResume() {
      const view = currentJob();
      if (!view) return;
      const content = view.querySelector('.resume-content');
      if (!content) return;
      content.innerHTML = content.dataset.original || content.innerHTML;
      localStorage.removeItem(view.dataset.storage);
    }
    document.querySelectorAll('.job-view').forEach(view => {
      const content = view.querySelector('.resume-content');
      if (!content) return;
      const saved = localStorage.getItem(view.dataset.storage);
      if (saved) content.innerHTML = saved;
      content.addEventListener('input', () => {
        localStorage.setItem(view.dataset.storage, content.innerHTML);
      });
    });
  </script>
</body>
</html>"""
    return (
        template.replace("__TITLE__", safe_title)
        .replace("__NAV_ITEMS__", "\n".join(nav_items))
        .replace("__JOB_SECTIONS__", "\n".join(job_sections))
        .replace("__PHOTO_PAD__", "33mm" if photo_data_uri else "0")
    )


def extract_first_docx_image_data_uri(template_bytes: bytes) -> str:
    if not template_bytes:
        return ""
    try:
        with zipfile.ZipFile(BytesIO(template_bytes)) as docx_zip:
            names = [
                name
                for name in docx_zip.namelist()
                if name.startswith("word/media/") and not name.endswith("/")
            ]
            if not names:
                return ""
            image_name = sorted(names)[0]
            image_bytes = docx_zip.read(image_name)
    except Exception:
        return ""
    mime = mimetypes.guess_type(image_name)[0] or "image/png"
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _markdown_to_html(markdown_text: str) -> str:
    source = _normalize_resume_markdown(markdown_text)
    rendered = markdown.markdown(
        source,
        extensions=["extra", "sane_lists"],
        output_format="html5",
    )
    return _highlight_placeholders(rendered)


def _normalize_resume_markdown(markdown_text: str) -> str:
    lines = []
    for raw in markdown_text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            lines.append("")
            continue
        if line.lstrip().startswith(("• ", "· ")):
            indent = line[: len(line) - len(line.lstrip())]
            line = f"{indent}- {line.lstrip()[2:].strip()}"
        lines.append(line)
    return normalize_resume_project_blocks("\n".join(lines))


def _highlight_placeholders(rendered_html: str) -> str:
    rendered_html = re.sub(
        r"\[请填写[:：]([^\]]+)\]",
        r'<span class="ph-fill" title="请补全此处内容">[请填写：\1]</span>',
        rendered_html,
    )
    rendered_html = re.sub(
        r"\[需用户确认[:：]?([^\]]*)\]",
        r'<span class="ph-confirm" title="请核对真实性">[需用户确认：\1]</span>',
        rendered_html,
    )
    return rendered_html


def _highlight_changelog_fill(rendered_html: str) -> str:
    return re.sub(
        r"(<h[1-6][^>]*>[^<]*需用户回填[^<]*</h[1-6]>)([\s\S]*?)(?=<h[1-6]|$)",
        r'\1<div class="changelog-fill">\2</div>',
        rendered_html,
    )


def _empty_state(message: str) -> str:
    return f'<div class="empty">{html.escape(message)}</div>'


def _list_block(title: str, items: list[str]) -> str:
    cleaned = [str(item).strip() for item in items if str(item).strip()]
    if not cleaned:
        return ""
    rows = "".join(f"<li>{html.escape(item)}</li>" for item in cleaned)
    return f"<div><strong>{html.escape(title)}</strong><ul>{rows}</ul></div>"


def _pdf_filename(company: str, job_title: str) -> str:
    stem = "-".join(part.strip() for part in [company, job_title, "简历"] if part.strip()) or "定制简历"
    stem = re.sub(r'[\\/:*?"<>|]+', "", stem)
    return f"{stem}.pdf"


def _format_match_score(match_score: int | str | None) -> str:
    try:
        score = int(match_score) if match_score is not None else 0
    except (TypeError, ValueError):
        return "未分析"
    if score <= 0:
        return "未分析"
    return f"{max(0, min(100, score))}%"
