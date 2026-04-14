from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Model: "gemini" | "groq" | "ollama" | "anthropic"
    llm_provider: str = "groq"

    # API Keys
    google_api_key: str = ""
    groq_api_key: str = ""
    anthropic_api_key: str = ""

    gemini_model: str = "gemini-2.0-flash"
    groq_model: str = "llama-3.3-70b-versatile"
    ollama_model: str = "llama3.2"
    ollama_base_url: str = "http://localhost:11434"
    anthropic_model: str = "claude-sonnet-4-20250514"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
