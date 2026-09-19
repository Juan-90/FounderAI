"""
Configurações centrais do FounderAI v3.5 (Fase 2 — Arquitetura Híbrida).

Carrega variáveis do `.env` via pydantic-settings (Pydantic V2) e expõe:
  • Provedores LLM tipados (`ProviderName`) com fallback Cloud → Local;
  • Overrides opcionais por papel (Architect, SecurityCoder, ProductStrategist);
  • Campos legados da Fase 1 (Ollama, PostgreSQL, Qdrant, App) intactos,
    garantindo retrocompatibilidade com a suíte de 108 testes.
"""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Tipo único para nomes de provedores (Cloud + Local).
ProviderName = Literal["groq", "openrouter", "openai", "local"]


class Settings(BaseSettings):
    """Settings da aplicação (12-factor via env/.env)."""

    # ─────────────────────────────────────────────
    # Fase 2 — Provedores LLM (agnósticos)
    # ─────────────────────────────────────────────
    PRIMARY_PROVIDER: ProviderName = "groq"
    FALLBACK_PROVIDER: ProviderName = "local"
    LLM_TIMEOUT_SECONDS: float = 60.0

    # Overrides opcionais por papel (None → usa PRIMARY_PROVIDER)
    ARCHITECT_PROVIDER: ProviderName | None = None
    SECURITYCODER_PROVIDER: ProviderName | None = None
    PRODUCTSTRATEGIST_PROVIDER: ProviderName | None = None

    # ─────────────────────────────────────────────
    # Fase 2 — Endpoints e credenciais Cloud
    # ─────────────────────────────────────────────
    GROQ_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    # ─────────────────────────────────────────────
    # Legado Fase 1 — Ollama local (retrocompatibilidade)
    # ─────────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_timeout: float = 60.0
    model_primary: str = "gemma2:2b"
    model_reasoning: str = "gemma2:2b"
    council_model: str = "gemma2:2b"

    # ─────────────────────────────────────────────
    # PostgreSQL
    # ─────────────────────────────────────────────
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "fundador_ia"
    postgres_user: str = "fundador"
    postgres_password: str = "fundador"

    # ─────────────────────────────────────────────
    # Qdrant
    # ─────────────────────────────────────────────
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "missions"

    # ─────────────────────────────────────────────
    # App
    # ─────────────────────────────────────────────
    app_name: str = "Fundador IA"
    app_version: str = "0.2.0"
    debug: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ─────────────────────────────────────────────
    # Helpers tipados (usados pelo LLMClient)
    # ─────────────────────────────────────────────
    @property
    def postgres_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    def base_url_for(self, provider: ProviderName) -> str:
        """URL base (padrão OpenAI-compatible) de cada provedor."""
        urls: dict[ProviderName, str] = {
            "groq": self.GROQ_BASE_URL,
            "openrouter": self.OPENROUTER_BASE_URL,
            "openai": self.OPENAI_BASE_URL,
            "local": self.ollama_base_url,
        }
        return urls[provider]

    def api_key_for(self, provider: ProviderName) -> str:
        """Chave de API do provedor (vazia para local)."""
        keys: dict[ProviderName, str] = {
            "groq": self.GROQ_API_KEY,
            "openrouter": self.OPENROUTER_API_KEY,
            "openai": self.OPENAI_API_KEY,
            "local": "",
        }
        return keys[provider]

    def default_model_for(self, provider: ProviderName) -> str:
        """Modelo padrão por provedor."""
        models: dict[ProviderName, str] = {
            "groq": "llama-3.3-70b-versatile",
            "openrouter": "openai/gpt-4o-mini",
            "openai": "gpt-4o-mini",
            "local": self.council_model,
        }
        return models[provider]


settings = Settings()