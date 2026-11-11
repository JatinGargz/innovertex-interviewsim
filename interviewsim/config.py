from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str
    session_minutes: int
    openai_api_key: str
    openai_base_url: str
    openai_model: str
    render_api_key: str
    render_workflow_slug: str
    app_public_url: str
    judge0_base_url: str
    judge0_api_key: str
    judge0_api_host: str
    judge0_language_id: int
    callback_secret: str
    nonilion_webhook_secret: str


def get_settings() -> Settings:
    raw_db_url = os.getenv("DATABASE_URL", "sqlite:///./data/interviewsim.sqlite3")
    if raw_db_url.startswith("postgres://"):
        raw_db_url = "postgresql+psycopg://" + raw_db_url.removeprefix("postgres://")
    elif raw_db_url.startswith("postgresql://"):
        raw_db_url = "postgresql+psycopg://" + raw_db_url.removeprefix("postgresql://")

    return Settings(
        database_url=raw_db_url,
        session_minutes=max(5, int(os.getenv("SESSION_MINUTES", "45"))),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        openai_model=os.getenv("OPENAI_MODEL", ""),
        render_api_key=os.getenv("RENDER_API_KEY", ""),
        render_workflow_slug=os.getenv("RENDER_WORKFLOW_SLUG", "interviewsim"),
        app_public_url=os.getenv("APP_PUBLIC_URL", "").rstrip("/"),
        judge0_base_url=os.getenv("JUDGE0_BASE_URL", "").rstrip("/"),
        judge0_api_key=os.getenv("JUDGE0_API_KEY", ""),
        judge0_api_host=os.getenv("JUDGE0_API_HOST", ""),
        judge0_language_id=int(os.getenv("JUDGE0_LANGUAGE_ID", "71")),
        callback_secret=os.getenv("INTERNAL_CALLBACK_SECRET", ""),
        nonilion_webhook_secret=os.getenv("NONILION_WEBHOOK_SECRET", ""),
    )


settings = get_settings()

