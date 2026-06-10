from __future__ import annotations

import base64
import html
import json
import mimetypes
import re
import zipfile
from io import BytesIO

import markdown


def build_editable_resume_html(
    resume_markdown: str,
    *,
    title: str = "定制简历",
    photo_data_uri: str = "",
    storage_key: str = "resume-agent-editable-resume",
) -> str:
    return build_job_delivery_html(
        resume_markdown=resume_markdown,
        title=title,
        photo_data_uri=photo_data_uri,
        storage_key=storage_key,
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
    return "\n".join(lines).strip()


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
