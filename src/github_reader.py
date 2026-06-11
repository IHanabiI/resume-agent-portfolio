from __future__ import annotations

import base64
import re
from urllib.parse import urlparse

import requests
import urllib3
from requests import exceptions as request_exceptions

from src.schemas import GitHubContext, GitHubRepositoryEvidence


GITHUB_API = "https://api.github.com"
GITHUB_HEADERS = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "resume-agent-github-reader",
    "X-GitHub-Api-Version": "2022-11-28",
}

_ssl_fallback_used = False


def collect_github_context(input_text: str, max_repos: int = 6) -> GitHubContext:
    global _ssl_fallback_used
    _ssl_fallback_used = False
    targets = _parse_targets(input_text)
    if not targets:
        return GitHubContext(source=input_text, summary="未识别到 GitHub 用户名或仓库链接。")

    repos: list[GitHubRepositoryEvidence] = []
    raw: list[str] = []
    errors: list[str] = []
    profile_url = ""

    for owner, repo in targets:
        if repo:
            evidence = _fetch_repo(owner, repo)
            if evidence:
                repos.append(evidence)
                raw.append(_repo_to_text(evidence))
            else:
                errors.append(f"未能读取仓库：{owner}/{repo}")
        else:
            profile_url = f"https://github.com/{owner}"
            try:
                user_repos = _fetch_user_repos(owner, max_repos=max_repos)
            except Exception as exc:
                errors.append(f"未能读取用户 {owner} 的仓库列表：{exc}")
                user_repos = []
            for repo_info in user_repos:
                evidence = _fetch_repo(owner, repo_info["name"], repo_info=repo_info)
                if evidence:
                    repos.append(evidence)
                    raw.append(_repo_to_text(evidence))
                else:
                    errors.append(f"未能读取仓库：{owner}/{repo_info.get('name', '')}")

    repos = repos[:max_repos]
    languages = sorted({lang for repo in repos for lang in repo.languages})
    repo_names = "、".join(repo.name for repo in repos[:5])
    summary = (
        f"GitHub 共收集到 {len(repos)} 个公开仓库。"
        f"主要语言/技术：{'、'.join(languages[:12]) or '未识别'}。"
        f"代表仓库：{repo_names or '未识别'}。"
    )
    if errors:
        summary += f" 读取提示：{'；'.join(errors[:3])}"
    if _ssl_fallback_used:
        summary += " 本机 Python 证书链校验失败，已对 GitHub 公共 API 使用宽松验证重试。"
    return GitHubContext(
        source=input_text,
        profile_url=profile_url,
        summary=summary,
        repositories=repos,
        raw_evidence=raw + errors,
    )


def github_context_to_text(context: GitHubContext) -> str:
    if not context.repositories and not context.summary:
        return ""
    lines = ["# GitHub 公开证据", context.summary]
    if context.profile_url:
        lines.append(f"Profile: {context.profile_url}")
    for repo in context.repositories:
        lines.extend(
            [
                "",
                f"## {repo.name}",
                f"- URL: {repo.url}",
                f"- Description: {repo.description or '无'}",
                f"- Languages: {', '.join(repo.languages) or '未知'}",
                f"- Topics: {', '.join(repo.topics) or '无'}",
                f"- Updated: {repo.updated_at}",
            ]
        )
        if repo.readme_excerpt:
            lines.append(f"- README excerpt: {repo.readme_excerpt}")
    return "\n".join(lines)


def _parse_targets(text: str) -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    for token in re.split(r"[\s,，;；]+", text.strip()):
        if not token:
            continue
        if "github.com" in token:
            parsed = urlparse(token if token.startswith("http") else f"https://{token}")
            parts = [part for part in parsed.path.strip("/").split("/") if part]
            if len(parts) >= 2:
                targets.append((parts[0], parts[1].removesuffix(".git")))
            elif len(parts) == 1:
                targets.append((parts[0], ""))
        elif re.fullmatch(r"[A-Za-z0-9-]{1,39}", token):
            targets.append((token, ""))
    seen: set[tuple[str, str]] = set()
    unique: list[tuple[str, str]] = []
    for target in targets:
        if target not in seen:
            unique.append(target)
            seen.add(target)
    return unique


def _fetch_user_repos(owner: str, max_repos: int) -> list[dict]:
    return _get_json(
        f"{GITHUB_API}/users/{owner}/repos",
        params={"sort": "updated", "direction": "desc", "per_page": max_repos},
    )


def _fetch_repo(owner: str, repo: str, repo_info: dict | None = None) -> GitHubRepositoryEvidence | None:
    try:
        info = repo_info or _get_json(f"{GITHUB_API}/repos/{owner}/{repo}")
        languages = list(_get_json(info["languages_url"]).keys())[:8] if info.get("languages_url") else []
        readme = _fetch_readme_excerpt(owner, repo)
        return GitHubRepositoryEvidence(
            name=info.get("full_name") or f"{owner}/{repo}",
            url=info.get("html_url") or f"https://github.com/{owner}/{repo}",
            description=info.get("description") or "",
            languages=languages,
            topics=info.get("topics") or [],
            readme_excerpt=readme,
            updated_at=info.get("updated_at") or "",
        )
    except Exception:
        return None


def _fetch_readme_excerpt(owner: str, repo: str) -> str:
    try:
        data = _get_json(f"{GITHUB_API}/repos/{owner}/{repo}/readme")
        content = data.get("content", "")
        if not content:
            return ""
        decoded = base64.b64decode(content).decode("utf-8", errors="ignore")
        return _clean_text(decoded)[:1200]
    except Exception:
        return ""


def _get_json(url: str, params: dict | None = None) -> dict:
    response = _github_get(url, params=params)
    response.raise_for_status()
    return response.json()


def _github_get(url: str, params: dict | None = None) -> requests.Response:
    global _ssl_fallback_used
    try:
        return requests.get(url, params=params, headers=GITHUB_HEADERS, timeout=15)
    except request_exceptions.SSLError:
        if not url.startswith(GITHUB_API):
            raise
        _ssl_fallback_used = True
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        return requests.get(url, params=params, headers=GITHUB_HEADERS, timeout=15, verify=False)


def _clean_text(text: str) -> str:
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", text)
    text = re.sub(r"\[[^\]]+\]\([^)]+\)", "", text)
    text = re.sub(r"[#>*_`|~-]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _repo_to_text(repo: GitHubRepositoryEvidence) -> str:
    return (
        f"{repo.name} | {repo.url} | {repo.description} | "
        f"Languages: {', '.join(repo.languages)} | Topics: {', '.join(repo.topics)} | "
        f"README: {repo.readme_excerpt[:500]}"
    )
