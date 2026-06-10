from __future__ import annotations

import base64
import html
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
    resume_html = _markdown_to_html(resume_markdown)
    safe_title = html.escape(title or "定制简历")
    safe_storage_key = html.escape(storage_key, quote=True)
    photo_html = (
        f'<img class="resume-photo" src="{html.escape(photo_data_uri, quote=True)}" alt="简历照片">'
        if photo_data_uri
        else ""
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{safe_title}</title>
  <style>
    :root {{
      --ink: #111827;
      --muted: #4b5563;
      --line: #d1d5db;
      --accent: #1f4f7a;
      --paper: #ffffff;
      --bg: #eef2f7;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: "Microsoft YaHei", "Source Han Sans CN", "Noto Sans CJK SC", Arial, sans-serif;
      font-size: 13px;
      line-height: 1.46;
    }}
    .toolbar {{
      position: sticky;
      top: 0;
      z-index: 10;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 10px 16px;
      background: rgba(255, 255, 255, .96);
      border-bottom: 1px solid var(--line);
    }}
    .toolbar-title {{
      font-size: 14px;
      font-weight: 700;
      color: var(--ink);
    }}
    .toolbar-actions {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    button {{
      height: 34px;
      border: 1px solid #cbd5e1;
      background: #fff;
      color: #111827;
      padding: 0 12px;
      border-radius: 6px;
      font: inherit;
      cursor: pointer;
    }}
    button.primary {{
      background: #1f4f7a;
      border-color: #1f4f7a;
      color: #fff;
    }}
    .save-status {{
      min-width: 88px;
      color: var(--muted);
      font-size: 12px;
    }}
    .page-shell {{
      padding: 24px 12px 36px;
    }}
    .page {{
      position: relative;
      width: 210mm;
      min-height: 297mm;
      margin: 0 auto;
      padding: 18mm 18mm 16mm;
      background: var(--paper);
      box-shadow: 0 12px 36px rgba(15, 23, 42, .18);
    }}
    .resume-photo {{
      position: absolute;
      top: 18mm;
      right: 18mm;
      width: 26mm;
      height: 34mm;
      object-fit: cover;
      border: 1px solid #e5e7eb;
      background: #fff;
    }}
    #resume {{
      outline: none;
      padding-right: {("34mm" if photo_data_uri else "0")};
    }}
    #resume h1 {{
      margin: 0 0 6px;
      font-size: 22px;
      line-height: 1.15;
      color: #111827;
      letter-spacing: 0;
    }}
    #resume h2 {{
      margin: 13px 0 6px;
      padding-bottom: 3px;
      border-bottom: 1px solid var(--line);
      font-size: 15px;
      line-height: 1.25;
      color: var(--accent);
    }}
    #resume h3 {{
      margin: 9px 0 4px;
      font-size: 13.5px;
      line-height: 1.28;
      color: #111827;
    }}
    #resume p {{
      margin: 3px 0;
    }}
    #resume ul, #resume ol {{
      margin: 4px 0 7px 18px;
      padding: 0;
    }}
    #resume li {{
      margin: 2px 0;
      padding-left: 2px;
    }}
    #resume strong {{
      font-weight: 700;
    }}
    #resume a {{
      color: #0f4c81;
      text-decoration: none;
    }}
    .ph-fill, .ph-confirm {{
      display: inline;
      padding: 1px 4px;
      border-radius: 4px;
      font-weight: 700;
    }}
    .ph-fill {{
      background: #fff7ed;
      color: #c2410c;
    }}
    .ph-confirm {{
      background: #eff6ff;
      color: #1d4ed8;
    }}
    @page {{
      size: A4;
      margin: 0;
    }}
    @media print {{
      body {{
        background: #fff;
      }}
      .toolbar {{
        display: none;
      }}
      .page-shell {{
        padding: 0;
      }}
      .page {{
        width: 210mm;
        min-height: 297mm;
        margin: 0;
        padding: 18mm 18mm 16mm;
        box-shadow: none;
      }}
      #resume {{
        padding-right: {("34mm" if photo_data_uri else "0")};
      }}
    }}
  </style>
</head>
<body>
  <div class="toolbar">
    <div class="toolbar-title">{safe_title}</div>
    <div class="toolbar-actions">
      <span class="save-status" id="save-status">已自动保存</span>
      <button id="restore-btn" type="button">还原初始版本</button>
      <button class="primary" id="print-btn" type="button">打印 / 保存 PDF</button>
    </div>
  </div>
  <main class="page-shell">
    <section class="page">
      {photo_html}
      <article id="resume" contenteditable="true">{resume_html}</article>
    </section>
  </main>
  <script>
    const storageKey = "{safe_storage_key}";
    const initialHtml = document.getElementById("resume").innerHTML;
    const resumeEl = document.getElementById("resume");
    const statusEl = document.getElementById("save-status");
    const saved = localStorage.getItem(storageKey);
    if (saved !== null) {{
      resumeEl.innerHTML = saved;
    }}
    let timer = null;
    resumeEl.addEventListener("paste", event => {{
      event.preventDefault();
      const text = (event.clipboardData || window.clipboardData).getData("text/plain");
      document.execCommand("insertText", false, text);
    }});
    resumeEl.addEventListener("input", () => {{
      statusEl.textContent = "编辑中...";
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {{
        localStorage.setItem(storageKey, resumeEl.innerHTML);
        statusEl.textContent = "已自动保存";
      }}, 400);
    }});
    document.getElementById("restore-btn").addEventListener("click", () => {{
      localStorage.removeItem(storageKey);
      resumeEl.innerHTML = initialHtml;
      statusEl.textContent = "已还原";
    }});
    document.getElementById("print-btn").addEventListener("click", () => window.print());
  </script>
</body>
</html>"""


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


def _markdown_to_html(resume_markdown: str) -> str:
    source = _normalize_resume_markdown(resume_markdown)
    rendered = markdown.markdown(
        source,
        extensions=["extra", "sane_lists"],
        output_format="html5",
    )
    return _highlight_placeholders(rendered)


def _normalize_resume_markdown(resume_markdown: str) -> str:
    lines = []
    for raw in resume_markdown.splitlines():
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
