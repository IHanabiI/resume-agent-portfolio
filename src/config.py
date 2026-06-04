from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[1]
PROMPT_DIR = ROOT_DIR / "src" / "prompts"
OUTPUT_DIR = ROOT_DIR / "outputs"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")
    openai_base_url: str = Field(default="", alias="OPENAI_BASE_URL")
    enable_demo_fallback: bool = Field(default=True, alias="OPENAI_ENABLE_DEMO_FALLBACK")
    app_password: str = Field(default="", alias="APP_PASSWORD")


@lru_cache
def get_settings() -> Settings:
    load_dotenv(ROOT_DIR / ".env", override=True, encoding="utf-8-sig")
    return Settings()


def load_prompt(name: str) -> str:
    path = PROMPT_DIR / name
    return path.read_text(encoding="utf-8")
