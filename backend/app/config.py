"""Application configuration via environment variables."""

from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    app_name: str = "Plum Claims Processing System"
    debug: bool = True

    # LLM
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # Cursor SDK
    cursor_api_key: str = ""
    cursor_model: str = "gpt-5.4-nano"

    # LLM Provider Configuration (cursor | antigravity | nvidia)
    llm_provider: str = "cursor"

    # Antigravity SDK
    antigravity_api_key: str = ""
    antigravity_model: Optional[str] = None

    # NVIDIA NIM
    nvidia_api_key: str = ""
    nvidia_model: str = "deepseek-ai/deepseek-v4-flash"
    nvidia_vision_model: str = "meta/llama-3.2-11b-vision-instruct"

    # Database
    database_url: str = "sqlite+aiosqlite:///./claims.db"

    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ]

    # Paths
    policy_terms_path: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "policy_terms.json",
    )
    test_cases_path: str = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "test_cases.json",
    )

    model_config = {
        "env_file": os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"),
        "env_file_encoding": "utf-8"
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
