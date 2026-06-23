from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "SentiPort AI - Hackathon Morski"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str
    # Opcjonalny - projekt nie korzysta już z OpenAI (agent głosowy
    # realizowany jest przez ElevenLabs w innym module).
    OPENAI_API_KEY: Optional[str] = None

    # Agent ekstrakcji danych z maili (wrapper kolegi na ElevenLabs).
    # AGENT_API_URL = pełny endpoint, na który wysyłamy {nomination_id, email}.
    # AGENT_API_KEY = opcjonalny token, jeśli agent wymaga autoryzacji.
    AGENT_API_URL: Optional[str] = None
    AGENT_API_KEY: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()