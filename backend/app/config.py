from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "SentiPort AI - Hackathon Morski"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str
    # Opcjonalny - projekt nie korzysta już z OpenAI (agent głosowy
    # realizowany jest przez ElevenLabs w innym module).
    OPENAI_API_KEY: Optional[str] = None

    # Agent ekstrakcji danych z maili - prawdziwa konwersacja ElevenLabs
    # (Chat Mode, bez audio), nie zwykły REST endpoint.
    # ELEVENLABS_API_KEY: klucz API z konta kolegi (xi-api-key).
    # ELEVENLABS_AGENT_ID: ID konkretnego agenta skonfigurowanego do
    # parsowania maili nominacyjnych (agent_...).
    ELEVENLABS_API_KEY: Optional[str] = None
    ELEVENLABS_AGENT_ID: Optional[str] = None

    # Drugi, OSOBNY agent ElevenLabs (FUN-003/FUN-011) - dostaje pełną
    # historię statku z bazy i proponuje konfigurację + wskazuje braki/
    # niespójności do dopytania armatora. Inny agent_id niż ten do
    # ekstrakcji maila, ale ten sam klucz API.
    ELEVENLABS_ENRICHMENT_AGENT_ID: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )


settings = Settings()