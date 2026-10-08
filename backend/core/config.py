"""
Configurações centrais do FounderAI (v5.0.0 GA).

Cobre v4.0 (Sandbox) → v4.7 (DISCOVER) → v5.0 (Golden Missions), com
checagem de ambiente (environment_warnings) e validação de provedores.
"""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderName = Literal["groq", "openrouter", "openai", "local"]


class Settings(BaseSettings):
    """Settings da aplicação (12-factor via env/.env)."""

    # ── Fase 2 — Provedores LLM ──
    PRIMARY_PROVIDER: ProviderName = "groq"
    FALLBACK_PROVIDER: ProviderName = "local"
    LLM_TIMEOUT_SECONDS: float = 60.0
    LLM_LOCAL_TIMEOUT_SECONDS: float = 180.0
    LLM_HTTP_RETRIES: int = 2
    LLM_RETRY_BACKOFF_SECONDS: float = 1.5
    ARCHITECT_PROVIDER: ProviderName | None = None
    SECURITYCODER_PROVIDER: ProviderName | None = None
    PRODUCTSTRATEGIST_PROVIDER: ProviderName | None = None

    # ── Fase 2 — Endpoints e credenciais Cloud ──
    GROQ_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"

    # ── Modelos customizáveis (v4.0) ──
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    OPENROUTER_MODEL: str = "openai/gpt-4o-mini"
    OPENAI_MODEL: str = "gpt-4o-mini"

    # ── Fase 3 — Limites de Contexto ──
    MAX_FILE_CHARS: int = 15000
    MAX_TOTAL_CONTEXT_CHARS: int = 40000

    # ── v4.0 Fase A — Sandbox ──
    SANDBOX_ENABLED: bool = True
    SANDBOX_IMAGE: str = "founderai-sandbox-python:v1"
    SANDBOX_TIMEOUT_SECONDS: int = 20
    SANDBOX_MAX_OUTPUT_BYTES: int = 1048576

    # ── v4.1.0 Módulo A — Pre-Sandbox Guardrail ──
    STATIC_ANALYSIS_ENABLED: bool = True
    STATIC_ANALYSIS_MYPY_ENABLED: bool = True
    STATIC_ANALYSIS_MAX_CYCLES: int = 2
    STATIC_ANALYSIS_TIMEOUT_SECONDS: float = 30.0

    # ── v4.1.0 Módulo C — Escalation Webhook ──
    ESCALATION_WEBHOOK_ENABLED: bool = False
    ESCALATION_WEBHOOK_URL: str | None = None
    ESCALATION_WEBHOOK_PROVIDER: str = "generic"
    ESCALATION_WEBHOOK_TIMEOUT_SECONDS: int = 8

    # ── v4.2.0 — BUILD Mode ──
    BUILD_MODE_ENABLED: bool = True
    BUILD_DEFAULT_PROJECT_TYPE: str = "WEB_APP"
    BUILD_DEFAULT_DEPLOYMENT_STRATEGY: str = "PRIVATE"
    BUILD_ARTIFACTS_DIR: str = "artifacts/build"

    # ── v4.3.0 — BUILD Path B (Game 2D) ──
    BUILD_GAME_ENABLED: bool = True
    BUILD_GAME_ENGINE: str = "pygame"
    BUILD_GAME_HEADLESS: bool = True

    # ── v4.4.0 — VALIDATE Mode (Path C) ──
    VALIDATE_MODE_ENABLED: bool = True
    VALIDATE_ARTIFACTS_DIR: str = "artifacts/validate"
    VALIDATE_DEFAULT_VERDICT_IF_UNCERTAIN: str = "INVESTIGATE"

    # ── v4.5.0 — VALIDATE_AND_BUILD (Ponte Direta) ──
    VALIDATE_AND_BUILD_ENABLED: bool = True
    VAB_REQUIRE_HUMAN_CONFIRMATION: bool = True
    VAB_MIN_CONFIDENCE_TO_AUTOBUILD: float = 0.75
    VAB_ARTIFACTS_DIR: str = "artifacts/validate_and_build"

    # ── v4.6.0 — SELF-AUDIT (Auditoria Interna) ──
    SELF_AUDIT_ENABLED: bool = True
    SELF_AUDIT_MAX_MISSIONS_PER_MODE: int = 3
    SELF_AUDIT_ADVERSARIAL_ENABLED: bool = True
    SELF_AUDIT_ARTIFACTS_DIR: str = "artifacts/self_audit"
    SELF_AUDIT_AUDITOR_PROVIDER: str = "ollama"
    SELF_AUDIT_AUDITOR_MODEL: str = "llama3.1:8b"

    # ── v4.7.0 — DISCOVER (Mapeamento de Oportunidades) ──
    DISCOVER_MODE_ENABLED: bool = True
    DISCOVER_MAX_OPPORTUNITIES: int = 8
    DISCOVER_INTERNAL_CANDIDATES: int = 16
    DISCOVER_ARTIFACTS_DIR: str = "artifacts/discover"
    DISCOVER_HANDOFF_TO_VALIDATE: bool = True

    # ── v5.0.0 GA — Golden Missions ──
    GOLDEN_ENABLED: bool = True
    GOLDEN_ARTIFACTS_DIR: str = "artifacts/golden"

        # ── v5.2.0 — Evidence Layer ──
    EVIDENCE_ENABLED: bool = True
    EVIDENCE_PROVIDER: str = "mock"                 # "mock" | "http"
    EVIDENCE_HTTP_ENDPOINT: str = ""
    EVIDENCE_HTTP_API_KEY: str = ""
    EVIDENCE_MAX_QUERIES_PER_MISSION: int = 3
    EVIDENCE_MAX_RESULTS_PER_QUERY: int = 5
    EVIDENCE_TIMEOUT_SECONDS: float = 10.0
    EVIDENCE_FAIL_OPEN: bool = True

        # Cache de evidências (v5.2.1)
    EVIDENCE_CACHE_ENABLED: bool = True
    EVIDENCE_CACHE_TTL_SECONDS: int = 86400       # 24 horas
    EVIDENCE_CACHE_BYPASS: bool = False

        # Provedores reais de busca (v5.2.1)
    TAVILY_API_KEY: str = ""
    SERPER_API_KEY: str = ""

    # ── Legado Fase 1 — Ollama ──
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_timeout: float = 60.0
    model_primary: str = "gemma2:2b"
    model_reasoning: str = "gemma2:2b"
    council_model: str = "gemma2:2b"

    # ── PostgreSQL ─
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "fundador_ia"
    postgres_user: str = "fundador"
    postgres_password: str = "fundador"

    # ── Qdrant ──
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "missions"

    # ── App ──
    app_name: str = "Fundador IA"
    app_version: str = "5.0.0"
    debug: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def postgres_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    def base_url_for(self, provider: ProviderName) -> str:
        urls: dict[ProviderName, str] = {
            "groq": self.GROQ_BASE_URL,
            "openrouter": self.OPENROUTER_BASE_URL,
            "openai": self.OPENAI_BASE_URL,
            "local": self.ollama_base_url,
        }
        return urls[provider]

    def api_key_for(self, provider: ProviderName) -> str:
        keys: dict[ProviderName, str] = {
            "groq": self.GROQ_API_KEY,
            "openrouter": self.OPENROUTER_API_KEY,
            "openai": self.OPENAI_API_KEY,
            "local": "",
        }
        return keys[provider]

    def default_model_for(self, provider: ProviderName) -> str:
        models: dict[ProviderName, str] = {
            "groq": self.GROQ_MODEL,
            "openrouter": self.OPENROUTER_MODEL,
            "openai": self.OPENAI_MODEL,
            "local": self.council_model,
        }
        return models[provider]

    def timeout_for(self, provider: ProviderName) -> float:
        """Timeout por provedor: local usa teto maior (codegen lento em CPU)."""
        if provider == "local":
            return max(self.LLM_LOCAL_TIMEOUT_SECONDS, 120.0)
        return self.LLM_TIMEOUT_SECONDS

    def validate_provider_config(self) -> list[str]:
        warnings: list[str] = []
        primary = self.PRIMARY_PROVIDER
        fallback = self.FALLBACK_PROVIDER

        if primary in ("groq", "openrouter", "openai"):
            key = self.api_key_for(primary)
            if not key or not key.strip():
                warnings.append(
                    f"Provedor primário '{primary}' sem API key configurada "
                    f"(defina {primary.upper()}_API_KEY no .env). "
                    f"Sistema usará fallback automático para '{fallback}'."
                )

        if fallback in ("groq", "openrouter", "openai"):
            key = self.api_key_for(fallback)
            if not key or not key.strip():
                warnings.append(
                    f"Provedor de fallback '{fallback}' sem API key. "
                    f"Em caso de falha do primário, não haverá rede de segurança."
                )

        role_map: dict[str, ProviderName | None] = {
            "Architect": self.ARCHITECT_PROVIDER,
            "SecurityCoder": self.SECURITYCODER_PROVIDER,
            "ProductStrategist": self.PRODUCTSTRATEGIST_PROVIDER,
        }
        for role, provider in role_map.items():
            if provider is None:
                continue
            if provider in ("groq", "openrouter", "openai"):
                role_key = self.api_key_for(provider)
                if not role_key or not role_key.strip():
                    warnings.append(
                        f"Override de '{role}' aponta para '{provider}' "
                        f"sem API key correspondente. Usará fallback."
                    )

        return warnings

    def environment_warnings(self) -> list[str]:
        """Avisos de inicialização quando variáveis essenciais estão ausentes (v5.0)."""
        warnings: list[str] = []
        if self.PRIMARY_PROVIDER != "local" and not (self.api_key_for(self.PRIMARY_PROVIDER) or "").strip():
            warnings.append(
                f"PRIMARY_PROVIDER='{self.PRIMARY_PROVIDER}' sem API key; "
                "o fallback será acionado."
            )
        if self.FALLBACK_PROVIDER != "local" and not (self.api_key_for(self.FALLBACK_PROVIDER) or "").strip():
            warnings.append(
                f"FALLBACK_PROVIDER='{self.FALLBACK_PROVIDER}' sem API key; "
                "sem rede de segurança em falhas do primário."
            )
        if self.PRIMARY_PROVIDER == "local" and self.FALLBACK_PROVIDER == "local":
            warnings.append(
                "Ambos os provedores são locais: requer Ollama rodando ('ollama serve')."
            )
        return warnings


settings = Settings()