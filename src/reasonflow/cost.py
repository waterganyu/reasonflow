"""Token cost tracking and budget enforcement."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# Pricing per 1M tokens (input, output) in USD
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # Claude — https://platform.claude.com/docs/en/about-claude/pricing
    "claude-opus-4-6": (5.0, 25.0),
    "claude-opus-4-5": (5.0, 25.0),
    "claude-opus-4-1": (15.0, 75.0),
    "claude-opus-4": (15.0, 75.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-sonnet-4-5": (3.0, 15.0),
    "claude-sonnet-4": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-haiku-3-5": (0.80, 4.0),
    # Claude shortcuts (latest per tier)
    "claude-opus": (5.0, 25.0),
    "claude-sonnet": (3.0, 15.0),
    "claude-haiku": (1.0, 5.0),
    # OpenAI — https://openai.com/api/pricing/
    "gpt-5.2": (1.75, 14.0),
    "gpt-5.1": (1.25, 10.0),
    "gpt-5": (1.25, 10.0),
    "gpt-4.1": (2.0, 8.0),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.60),
    "o3": (2.0, 8.0),
    "o3-mini": (1.10, 4.40),
    "o4-mini": (1.10, 4.40),
    "o1": (15.0, 60.0),
    # Gemini — https://ai.google.dev/gemini-api/docs/pricing
    "gemini/gemini-2.5-pro": (1.25, 10.0),
    "gemini/gemini-2.5-flash": (0.30, 2.50),
    "gemini/gemini-2.0-flash": (0.10, 0.40),
    "gemini/gemini-1.5-pro": (1.25, 5.0),
    # Deepseek
    "deepseek/deepseek-chat": (0.14, 0.28),
    # Fallback
    "default": (3.0, 15.0),
}


def parse_budget(budget: str | float | None) -> float | None:
    """Parse a budget string like '$0.50' into a float, or pass through."""
    if budget is None:
        return None
    if isinstance(budget, (int, float)):
        return float(budget)
    match = re.match(r"\$?([\d.]+)", str(budget))
    if match:
        return float(match.group(1))
    raise ValueError(f"Cannot parse budget: {budget!r}")


def calculate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Calculate cost for a given model and token counts."""
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])
    cost = (tokens_in * pricing[0] + tokens_out * pricing[1]) / 1_000_000
    return round(cost, 6)


@dataclass
class CostTracker:
    """Accumulates cost across nodes in a DAG run."""

    budget: float | None = None
    on_exceeded: str = "warn"  # warn, degrade, halt
    entries: list[dict[str, Any]] = field(default_factory=list)

    @property
    def total_cost(self) -> float:
        return round(sum(e["cost"] for e in self.entries), 6)

    @property
    def total_tokens_in(self) -> int:
        return sum(e["tokens_in"] for e in self.entries)

    @property
    def total_tokens_out(self) -> int:
        return sum(e["tokens_out"] for e in self.entries)

    def record(
        self, node_name: str, model: str, tokens_in: int, tokens_out: int
    ) -> float:
        cost = calculate_cost(model, tokens_in, tokens_out)
        self.entries.append({
            "node": node_name,
            "model": model,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost": cost,
        })
        return cost

    @property
    def budget_exceeded(self) -> bool:
        if self.budget is None:
            return False
        return self.total_cost > self.budget

    @property
    def budget_remaining(self) -> float | None:
        if self.budget is None:
            return None
        return round(self.budget - self.total_cost, 6)

    def check_budget(self, node_name: str) -> str | None:
        """Check budget status. Returns action if exceeded: 'warn', 'degrade', 'halt'."""
        if not self.budget_exceeded:
            return None
        return self.on_exceeded
