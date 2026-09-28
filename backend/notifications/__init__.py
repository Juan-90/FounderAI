"""
Escalation Webhook Engine — FounderAI v4.1.0 (Módulo C).

Notificações assíncronas best-effort para escalonar falhas persistentes
do TDDLoop (escalated=True) a canais externos (Discord/Slack/Telegram/generic).
"""

from backend.notifications.models import (
    EscalationPayload,
    NotificationResult,
    WebhookProvider,
)
from backend.notifications.webhook import EscalationNotifier

__all__ = [
    "EscalationNotifier",
    "EscalationPayload",
    "NotificationResult",
    "WebhookProvider",
]