"""Settings, read from environment / backend/.env."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    llm_model: str = "google_genai:gemini-3.5-flash-lite"
    google_api_key: str = ""
    anthropic_api_key: str = ""
    groq_api_key: str = ""

    # Public demo: seed synthetic documents for a fictional person, block uploads/deletes.
    demo_mode: bool = False
    chat_rate_limit_per_hour: int = 30  # per client IP, 0 disables

    storage_dir: str = "storage"
    database_url: str = "sqlite:///storage/docmitra.db"
    cors_origins: str = "http://localhost:5174"
    reminder_lead_days: int = 30
    max_upload_bytes: int = 10 * 1024 * 1024

    @property
    def storage_path(self) -> Path:
        path = Path(self.storage_dir)
        return path if path.is_absolute() else BACKEND_DIR / path

    @property
    def llm_configured(self) -> bool:
        provider = self.llm_model.split(":", 1)[0]
        if provider == "google_genai":
            return bool(self.google_api_key)
        if provider == "anthropic":
            return bool(self.anthropic_api_key)
        if provider == "groq":
            return bool(self.groq_api_key)
        return True  # other providers read their own env vars


settings = Settings()
