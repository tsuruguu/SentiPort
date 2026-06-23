from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "SentiPort AI - Hackathon Morski"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str
    OPENAI_API_KEY: str

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()