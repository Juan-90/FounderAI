"""
Configurações centrais do FounderAI v3.5 (Fase 2 + Fase 3).

Carrega variáveis do `.env` via pydantic-settings (Pydantic V2) e expõe:
  • Provedores LLM tipados (`ProviderName`) com fallback Cloud → Local (Fase 2);
  • Overrides opcionais por papel (Architect, SecurityCoder, etc.) (Fase 2);
  • Limites de contexto para `prepare_context_payload` (Fase 3);
  • Campos legados da Fase 1 (Ollama, PostgreSQL, Qdrant, App) intactos.
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
    # Fase 3 — Limites de Contexto
    # ─────────────────────────────────────────────
    MAX_FILE_CHARS: int = 15000
    MAX_TOTAL_CONTEXT_CHARS: int = 40000

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

        # ─────────────────────────────────────────────
    # Fase 3 — Validação de configuração (Bloco 2)
    # ─────────────────────────────────────────────
    def validate_provider_config(self) -> list[str]:
        """
        Verifica consistência entre provedor primário e credenciais.

        Returns:
            Lista de mensagens de alerta (vazia = configuração OK).
            Se o provedor Cloud primário estiver sem API key, o sistema
            cairá automaticamente em `FALLBACK_PROVIDER` no runtime.
        """
        warnings: list[str] = []
        primary = self.PRIMARY_PROVIDER
        fallback = self.FALLBACK_PROVIDER

        # Cloud sem chave → alertar que o fallback será usado
        if primary in ("groq", "openrouter", "openai"):
            key = self.api_key_for(primary)
            if not key or not key.strip():
                warnings.append(
                    f"Provedor primário '{primary}' sem API key configurada "
                    f"(defina {primary.upper()}_API_KEY no .env). "
                    f"Sistema usará fallback automático para '{fallback}'."
                )

        # Fallback Cloud também sem chave → alerta crítico (sem rede de segurança)
        if fallback in ("groq", "openrouter", "openai"):
            key = self.api_key_for(fallback)
            if not key or not key.strip():
                warnings.append(
                    f"Provedor de fallback '{fallback}' sem API key. "
                    f"Em caso de falha do primário, não haverá rede de segurança."
                )

        # Overrides por papel com provedor Cloud inválido
        role_map: dict[str, ProviderName | None] = {
            "Architect": self.ARCHITECT_PROVIDER,
            "SecurityCoder": self.SECURITYCODER_PROVIDER,
            "ProductStrategist": self.PRODUCTSTRATEGIST_PROVIDER,
        }
        for role, provider in role_map.items():
            if provider is None:
                continue
            if provider in ("groq", "openrouter", "openai"):
                if not self.api_key_for(provider) or not self.api_key_for(provider).strip():
                    warnings.append(
                        f"Override de '{role}' aponta para '{provider}' "
                        f"sem API key correspondente. Usará fallback."
                    )

        return warnings


settings = Settings()