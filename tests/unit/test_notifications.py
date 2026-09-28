"""
Testes do Escalation Webhook Engine (v4.1.0 Módulo C).
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import httpx
import pytest

from backend.core.config import Settings
from backend.notifications.models import (
    EscalationPayload,
    NotificationResult,
    WebhookProvider,
)
from backend.notifications.webhook import EscalationNotifier


def _make_payload() -> EscalationPayload:
    return EscalationPayload(
        event="tdd_loop.escalated",
        project_name="FounderAI",
        mission_id="mid-123",
        goal="implementar X",
        attempts=3,
        max_retries=3,
        final_summary="Falha persistente após 3 tentativas.",
        last_error="AssertionError",
        stdout_tail="...",
        stderr_tail="E assert 1 == 2",
        created_at=datetime(2026, 9, 27, 12, 0, 0),
    )


def _make_settings(webhook_url: str = "https://example.com/hook") -> Settings:
    return Settings(
        NOTIFICATION_WEBHOOK_URL=webhook_url,
        NOTIFICATION_PROVIDER="GENERIC",
        NOTIFICATION_TIMEOUT_SECONDS=5.0,
    )


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


# ─────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────

def test_webhook_provider_enum() -> None:
    assert WebhookProvider.GENERIC.value == "GENERIC"
    assert WebhookProvider.DISCORD.value == "DISCORD"


def test_escalation_payload_defaults() -> None:
    p = EscalationPayload(
        event="x", project_name="p", mission_id="m",
        attempts=1, max_retries=3, final_summary="ok",
    )
    assert p.last_error is None
    assert p.stdout_tail == ""
    assert p.created_at is not None


def test_notification_result_tipado() -> None:
    r = NotificationResult(sent=True, provider=WebhookProvider.SLACK, status_code=200)
    assert r.sent is True
    assert r.error is None


# ─────────────────────────────────────────────────────────────
# Webhook sem URL configurada
# ─────────────────────────────────────────────────────────────

def test_notifica_sem_url_retorna_erro_sem_lancar() -> None:
    notifier = EscalationNotifier(config=_make_settings(webhook_url=""))
    result = _run(notifier.notify(_make_payload()))
    assert isinstance(result, NotificationResult)
    assert result.sent is False
    assert "não configurada" in (result.error or "")
    assert result.status_code is None


# ─────────────────────────────────────────────────────────────
# Envio bem-sucedido
# ─────────────────────────────────────────────────────────────

def test_envio_generico_sucesso() -> None:
    recorded: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        return httpx.Response(200, json={"ok": True})

    notifier = EscalationNotifier(
        config=_make_settings(),
        transport=httpx.MockTransport(handler),
    )
    result = _run(notifier.notify(_make_payload()))
    assert result.sent is True
    assert result.status_code == 200
    assert result.provider == WebhookProvider.GENERIC
    assert len(recorded) == 1


def test_envio_discord_payload_formatado() -> None:
    recorded: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request)
        return httpx.Response(204)

    notifier = EscalationNotifier(
        config=_make_settings(),
        transport=httpx.MockTransport(handler),
    )
    result = _run(notifier.notify(_make_payload(), provider=WebhookProvider.DISCORD))
    assert result.sent is True
    assert result.provider == WebhookProvider.DISCORD
    body = recorded[0].content.decode("utf-8")
    assert "FounderAI" in body
    assert "Escalation" in body or "Escala" in body


# ─────────────────────────────────────────────────────────────
# Falhas graciosas (never-throw)
# ─────────────────────────────────────────────────────────────

def test_timeout_retorna_sent_false_sem_lancar() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    notifier = EscalationNotifier(
        config=_make_settings(),
        transport=httpx.MockTransport(handler),
    )
    result = _run(notifier.notify(_make_payload()))
    assert result.sent is False
    assert "Timeout" in (result.error or "")
    assert result.status_code is None


def test_http_500_retorna_sent_false_com_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    notifier = EscalationNotifier(
        config=_make_settings(),
        transport=httpx.MockTransport(handler),
    )
    result = _run(notifier.notify(_make_payload()))
    assert result.sent is False
    assert result.status_code == 500
    assert "HTTP 500" in (result.error or "")


def test_erro_de_conexao_retorna_sent_false() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    notifier = EscalationNotifier(
        config=_make_settings(),
        transport=httpx.MockTransport(handler),
    )
    result = _run(notifier.notify(_make_payload()))
    assert result.sent is False
    assert "ConnectError" in (result.error or "")


def test_provider_invalido_fallback_generic() -> None:
    cfg = _make_settings()
    cfg.NOTIFICATION_PROVIDER = "PROVIDER_INEXISTENTE"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    notifier = EscalationNotifier(
        config=cfg, transport=httpx.MockTransport(handler)
    )
    result = _run(notifier.notify(_make_payload()))
    assert result.sent is True
    assert result.provider == WebhookProvider.GENERIC