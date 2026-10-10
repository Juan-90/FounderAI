"""
Política de retry/backoff (v5.5.3).

backoff_seconds(): exponencial com base maior para HTTP 429 (rate limit),
respeitando um teto (cap). Usada pelo GroqProvider e demais transports.
"""

from __future__ import annotations

DEFAULT_BASE: float = 2.0
RATE_LIMIT_BASE: float = 4.0     # v5.5.3: backoff ligeiramente maior p/ 429
DEFAULT_CAP: float = 30.0


def backoff_seconds(
    attempt: int,
    status_code: int | None = None,
    base: float = DEFAULT_BASE,
    cap: float = DEFAULT_CAP,
    rate_limit_base: float = RATE_LIMIT_BASE,
) -> float:
    """Delay exponencial p/ a tentativa `attempt` (1-based).

    429 -> usa rate_limit_base (maior); demais -> base. Sempre <= cap.
    """
    factor = rate_limit_base if status_code == 429 else base
    delay = factor * (2 ** max(0, attempt - 1))
    return min(delay, cap)