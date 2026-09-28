"""
EscalationNotifier — envio assíncrono never-throw de webhooks (v4.1.0).

Lê configuração de ESCALATION_WEBHOOK_* (unificado; NOTIFICATION_* removido).
Contrato: `notify(...)` NUNCA lança exceção para o chamador.
"""

from __future__ import annotations

from typing import Any

import httpx

from backend.core.config import Settings, settings
from backend.notifications.models import (
    EscalationPayload,
    NotificationResult,
    WebhookProvider,
)


class EscalationNotifier:
    """Cliente assíncrono para envio de webhooks de escalação."""

    def __init__(
        self,
        config: Settings | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._config: Settings = config if config is not None else settings
        self._transport: httpx.AsyncBaseTransport | None = transport

    def _http_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self._config.ESCALATION_WEBHOOK_TIMEOUT_SECONDS,
            transport=self._transport,
        )

    def _provider(self, override: WebhookProvider | None) -> WebhookProvider:
        if override is not None:
            return override
        raw = (self._config.ESCALATION_WEBHOOK_PROVIDER or "generic").upper()
        try:
            return WebhookProvider(raw)
        except ValueError:
            return WebhookProvider.GENERIC

    @staticmethod
    def _build_generic_body(payload: EscalationPayload) -> dict[str, Any]:
        return payload.model_dump(mode="json")

    @staticmethod
    def _build_discord_body(payload: EscalationPayload) -> dict[str, Any]:
        return {
            "content": "🔴 **FounderAI — Escalação**",
            "embeds": [{
                "title": f"{payload.project_name} / {payload.mission_id}",
                "description": payload.final_summary,
                "color": 0xFF5252,
                "fields": [
                    {"name": "Tentativas", "value": f"{payload.attempts}/{payload.max_retries}", "inline": True},
                    {"name": "Evento", "value": payload.event, "inline": True},
                    {"name": "Último erro", "value": payload.last_error or "—"},
                ],
                "timestamp": payload.created_at.isoformat(),
            }],
        }

    @staticmethod
    def _build_slack_body(payload: EscalationPayload) -> dict[str, Any]:
        return {
            "text": "🔴 *FounderAI — Escalação*",
            "blocks": [
                {"type": "header", "text": {"type": "plain_text", "text": f"{payload.project_name} / {payload.mission_id}"}},
                {"type": "section", "text": {"type": "mrkdwn", "text": payload.final_summary}},
                {"type": "section", "fields": [
                    {"type": "mrkdwn", "text": f"*Tentativas:*\n{payload.attempts}/{payload.max_retries}"},
                    {"type": "mrkdwn", "text": f"*Evento:*\n{payload.event}"},
                ]},
            ],
        }

    @staticmethod
    def _build_telegram_body(payload: EscalationPayload) -> dict[str, Any]:
        text = (
            f"🔴 *FounderAI — Escalação*\n\n"
            f"*Projeto:* {payload.project_name}\n"
            f"*Missão:* `{payload.mission_id}`\n"
            f"*Tentativas:* {payload.attempts}/{payload.max_retries}\n\n"
            f"{payload.final_summary}"
        )
        return {"text": text, "parse_mode": "Markdown"}

    def _build_request(
        self, provider: WebhookProvider, payload: EscalationPayload
    ) -> dict[str, Any]:
        builders = {
            WebhookProvider.GENERIC:  self._build_generic_body,
            WebhookProvider.DISCORD:  self._build_discord_body,
            WebhookProvider.SLACK:    self._build_slack_body,
            WebhookProvider.TELEGRAM: self._build_telegram_body,
        }
        return builders[provider](payload)

    async def notify(
        self,
        payload: EscalationPayload,
        url: str | None = None,
        provider: WebhookProvider | None = None,
    ) -> NotificationResult:
        """
        Envia webhook. NUNCA lança exceção: falhas viram
        NotificationResult(sent=False, error=...).
        """
        effective_url = url or self._config.ESCALATION_WEBHOOK_URL
        effective_provider = self._provider(provider)

        if not effective_url:
            return NotificationResult(
                sent=False,
                provider=effective_provider,
                status_code=None,
                error="ESCALATION_WEBHOOK_URL não configurada.",
            )

        try:
            body = self._build_request(effective_provider, payload)
        except Exception as exc:
            return NotificationResult(
                sent=False,
                provider=effective_provider,
                status_code=None,
                error=f"Falha ao construir payload: {type(exc).__name__}: {exc}",
            )

        try:
            async with self._http_client() as client:
                response = await client.post(
                    effective_url,
                    json=body,
                    headers={"Content-Type": "application/json"},
                )
                if response.is_success:
                    return NotificationResult(
                        sent=True,
                        provider=effective_provider,
                        status_code=response.status_code,
                        error=None,
                    )
                return NotificationResult(
                    sent=False,
                    provider=effective_provider,
                    status_code=response.status_code,
                    error=f"HTTP {response.status_code}: {response.text[:200]}",
                )
        except httpx.TimeoutException:
            return NotificationResult(
                sent=False,
                provider=effective_provider,
                status_code=None,
                error=f"Timeout após {self._config.ESCALATION_WEBHOOK_TIMEOUT_SECONDS}s.",
            )
        except httpx.RequestError as exc:
            return NotificationResult(
                sent=False,
                provider=effective_provider,
                status_code=None,
                error=f"{type(exc).__name__}: {exc}",
            )
        except Exception as exc:
            return NotificationResult(
                sent=False,
                provider=effective_provider,
                status_code=None,
                error=f"Erro inesperado: {type(exc).__name__}: {exc}",
            )