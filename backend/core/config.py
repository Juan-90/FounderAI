"""
Configurações centrais do Fundador IA.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Ollama
    ollama_base_url: str = "http://ollama:11434"
    model_primary: str = "gemma4:e4b"        # Mission Intelligence, Scorecard
    model_reasoning: str = "gemma4:e4b"      # Reality Engine, Contrarian Engine (Qwen3 14B requer GPU dedicada)

    # PostgreSQL
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "fundador_ia"
    postgres_user: str = "fundador"
    postgres_password: str = "fundador"

    @property
    def postgres_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Qdrant
    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333
    qdrant_collection: str = "missions"

    # App
    app_name: str = "Fundador IA"
    app_version: str = "0.1.0"
    debug: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()