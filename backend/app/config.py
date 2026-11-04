import os

from pydantic_settings import BaseSettings

# Serverless filesystems are read-only except /tmp, so on Vercel the SQLite
# file lives there (demo data resets when an instance recycles).
_default_db = (
    "sqlite:////tmp/rfq_flow.db" if os.environ.get("VERCEL") else "sqlite:///./rfq_flow.db"
)


class Settings(BaseSettings):
    # Local dev defaults to a SQLite file so the project runs with zero setup.
    # Point DATABASE_URL at Postgres (see docker-compose.yml) for a real deployment.
    database_url: str = _default_db

    # If either key is set, the extraction node uses that LLM with structured
    # output. With neither set it falls back to a local rules-based parser so
    # the pipeline (and the evals) still run offline.
    gemini_api_key: str | None = None
    google_api_key: str | None = None  # AI Studio keys are often under this name
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    gemini_model: str = "gemini-3.8-flash"
    extraction_model: str = "claude-sonnet-4-5"

    @property
    def effective_gemini_key(self) -> str | None:
        return self.gemini_api_key or self.google_api_key

    review_threshold: float = 0.85

    class Config:
        env_file = ".env"


settings = Settings()
