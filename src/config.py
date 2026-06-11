from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[1]
PROMPT_DIR = ROOT_DIR / "src" / "prompts"
OUTPUT_DIR = ROOT_DIR / "outputs"
WORKSPACE_DIR = ROOT_DIR / "data" / "workspaces"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")
    openai_base_url: str = Field(default="", alias="OPENAI_BASE_URL")
    enable_demo_fallback: bool = Field(default=True, alias="OPENAI_ENABLE_DEMO_FALLBACK")
    app_password: str = Field(default="", alias="APP_PASSWORD")
    workspace_salt: str = Field(default="", alias="WORKSPACE_SALT")
    allowed_workspace_keys: str = Field(default="Hanabi", alias="ALLOWED_WORKSPACE_KEYS")
    openai_timeout_seconds: float = Field(default=45.0, alias="OPENAI_TIMEOUT_SECONDS")
    fast_analysis_mode: bool = Field(default=True, alias="RESUME_AGENT_FAST_ANALYSIS")
    fast_fact_check: bool = Field(default=True, alias="RESUME_AGENT_FAST_FACT_CHECK")


@lru_cache
def get_settings() -> Settings:
    load_dotenv(ROOT_DIR / ".env", override=True, encoding="utf-8-sig")
    _load_streamlit_secrets()
    return Settings()


def load_prompt(name: str) -> str:
    path = PROMPT_DIR / name
    return path.read_text(encoding="utf-8")


def _load_streamlit_secrets() -> None:
    try:
        import streamlit as st
    except Exception:
        return

    try:
        secrets = st.secrets
        for key in [
            "OPENAI_API_KEY",
            "OPENAI_MODEL",
            "OPENAI_BASE_URL",
            "OPENAI_ENABLE_DEMO_FALLBACK",
            "APP_PASSWORD",
            "WORKSPACE_SALT",
            "ALLOWED_WORKSPACE_KEYS",
            "OPENAI_TIMEOUT_SECONDS",
            "RESUME_AGENT_FAST_ANALYSIS",
            "RESUME_AGENT_FAST_FACT_CHECK",
        ]:
            if key in secrets:
                os.environ[key] = str(secrets[key])
    except Exception:
        return
