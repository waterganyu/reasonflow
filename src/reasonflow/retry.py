"""Retry logic with error-type awareness and backoff."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable


class NodeExecutionError(Exception):
    """Raised when a node execution fails."""

    def __init__(self, message: str, error_type: str = "unknown", node_name: str = ""):
        super().__init__(message)
        self.error_type = error_type
        self.node_name = node_name


@dataclass
class RetryPolicy:
    """Configures retry behavior for a node."""

    max_retries: int = 0
    retry_on: list[str] = field(default_factory=list)  # error types to retry
    backoff_base: float = 1.0  # seconds
    backoff_max: float = 30.0
    jitter: bool = True

    def should_retry(self, error: Exception, attempt: int) -> bool:
        if attempt >= self.max_retries:
            return False
        if not self.retry_on:
            return True  # retry on all errors if no filter
        error_type = getattr(error, "error_type", type(error).__name__)
        return any(t in str(error_type) or t in str(error) for t in self.retry_on)

    def delay(self, attempt: int) -> float:
        delay = min(self.backoff_base * (2 ** attempt), self.backoff_max)
        if self.jitter:
            delay *= 0.5 + random.random()
        return delay


async def retry_async(
    fn: Callable[..., Awaitable[Any]],
    policy: RetryPolicy,
    *args: Any,
    **kwargs: Any,
) -> tuple[Any, int]:
    """Execute an async function with retry policy. Returns (result, retries)."""
    last_error: Exception | None = None
    for attempt in range(policy.max_retries + 1):
        try:
            result = await fn(*args, **kwargs)
            return result, attempt
        except Exception as e:
            last_error = e
            if not policy.should_retry(e, attempt + 1):
                break
            delay = policy.delay(attempt)
            await asyncio.sleep(delay)
    raise last_error  # type: ignore[misc]
