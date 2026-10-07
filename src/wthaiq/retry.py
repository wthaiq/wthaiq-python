"""Retry policy for transient failures."""

from __future__ import annotations

import asyncio
import random as _random
import re
import time
from collections.abc import Awaitable, Callable

__all__ = ["RetryPolicy"]

_NEVER_RETRY_CODES = frozenset({"delivery_failed", "feature_unavailable"})
_NUMBER = re.compile(r"^[0-9]+(\.[0-9]+)?$")


class RetryPolicy:
    """Decides which failures are retried and how long to wait between attempts.

    Retried: connection errors and timeouts, ``429 too_many_requests``,
    ``409 idempotency_in_progress``, ``500``, ``502`` (except ``delivery_failed``), ``503``
    (except ``feature_unavailable``) and ``504``. Quota-style ``429`` codes
    (``daily_cap_reached``, ``reminder_limit_reached``, ``reminder_too_soon``,
    ``test_daily_limit``, ``test_email_limit``) and every other ``4xx`` are never retried.

    The delay honours ``Retry-After`` (capped at ``max_retry_after``); otherwise it is exponential
    backoff ``min(max_delay, initial_delay * 2**attempt)`` with jitter in ``[d/2, d]``.
    All durations are in seconds.
    """

    def __init__(
        self,
        *,
        initial_delay: float = 0.5,
        max_delay: float = 8.0,
        max_retry_after: float = 60.0,
        sleep: Callable[[float], None] | None = None,
        async_sleep: Callable[[float], Awaitable[None]] | None = None,
        random: Callable[[], float] | None = None,
    ) -> None:
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.max_retry_after = max_retry_after
        self._sleep = sleep if sleep is not None else time.sleep
        self._async_sleep = async_sleep if async_sleep is not None else asyncio.sleep
        self._random = random if random is not None else _random.random

    def should_retry(self, status: int | None, code: str | None) -> bool:
        """Whether a failed attempt may be retried. ``status`` is ``None`` for connection errors."""
        if status is None:
            return True
        if code is not None and code in _NEVER_RETRY_CODES:
            return False
        if status == 429:
            return code is None or code == "too_many_requests"
        if status == 409:
            return code == "idempotency_in_progress"
        return status in (500, 502, 503, 504)

    def delay(self, attempt: int, retry_after: str | None = None) -> float:
        """Seconds to wait before retry number ``attempt + 1`` (``attempt`` starts at 0)."""
        if retry_after is not None:
            value = retry_after.strip()
            if _NUMBER.match(value):
                return min(self.max_retry_after, max(0.0, float(value)))
        base = min(self.max_delay, self.initial_delay * (2.0**attempt))
        return base / 2 + (base / 2) * self._random()

    def sleep(self, seconds: float) -> None:
        self._sleep(seconds)

    async def async_sleep(self, seconds: float) -> None:
        await self._async_sleep(seconds)
