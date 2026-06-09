from __future__ import annotations

from datetime import datetime
from pathlib import Path

from src.schemas import EvidenceItem, FactCheckResult, TailoredResumeResult


def build_evidence_markdown(evidence_map: list[EvidenceItem]) -> str:
    lines = [
        "| 简历内容 | 来源类型 | 来源文本 | 状态 |",
        "|---|---|---|---|",
    ]
    for item in evidence_map:
        lines.append(
            f"| {_cell(item.resume_claim)} | {_cell(item.source_type)} | {_cell(item.source_text)} | {_cell(item.status)} |"
        )
    return "\n".join(lines)


def build_full_markdown(
    tailored: TailoredResumeResult,
    fact_check: FactCheckResult,
) -> str:
    lines = [
        "# 定制简历",
        "",
        fact_check.final_resume_markdown or tailored.resume_markdown,
        "",
        "# 开场白",
        "",
        tailored.opener_markdown or "暂无开场白。",
        "",
        "# 改动说明",
        "",
        tailored.changelog_markdown or _fallback_changelog(tailored),
        "",
        "## 已融入岗位关键词",
    ]
    lines.append("- " + "、".join(tailored.integrated_keywords) if tailored.integrated_keywords else "- 无")
    lines.extend(["", "## 仍建议补充的信息"])
    if tailored.still_missing_info:
        for item in tailored.still_missing_info:
            lines.append(f"- {item}")
    else:
        lines.append("- 暂无")
    lines.extend(["", "## 事实来源映射表", build_evidence_markdown(fact_check.evidence_map)])
    return "\n".join(lines)


def save_markdown(content: str, output_dir: Path, filename: str = "tailored_resume.md") -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename
    path.write_text(content, encoding="utf-8")
    dated = output_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
    dated.write_text(content, encoding="utf-8")
    return path


def _cell(value: str) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")[:500]


def _fallback_changelog(tailored: TailoredResumeResult) -> str:
    lines = ["## 已做调整"]
    if tailored.optimization_notes:
        for note in tailored.optimization_notes:
            lines.append(f"- {note}")
    else:
        lines.append("- 已根据岗位要求调整简历表达。")
    return "\n".join(lines)
