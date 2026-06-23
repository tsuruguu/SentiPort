from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "SentiPort AI - Hackathon Morski"
    API_V1_STR: str = "/api/v1"

    # URL do bazy PostgreSQL / PostGIS
    DATABASE_URL: str

    # Klucze do AI (konieczne dla llm_parser_service)
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()