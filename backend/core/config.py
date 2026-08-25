"""
Configurações centrais do Fundador IA.
Carrega variáveis do .env via pydantic-settings.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Ollama ──────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_timeout: float = 8.0
    model_primary: str = "gemma4:e4b"
    model_reasoning: str = "gemma4:e4b"

    # Modelo usado pelo Conselho Consultivo (configurável)
    council_model: str = "gemma4:e4b"

    # ── PostgreSQL ───────────────────────────────────
    postgres_host: str = "localhost"
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

    # ── Qdrant ───────────────────────────────────────
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "missions"

    # ── App ──────────────────────────────────────────
    app_name: str = "Fundador IA"
    app_version: str = "0.2.0"
    debug: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()