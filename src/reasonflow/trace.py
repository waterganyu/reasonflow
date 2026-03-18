"""Execution trace recording and export."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class Span:
    """A single node execution span."""

    node_name: str
    node_type: str
    start_time: float = 0.0
    end_time: float = 0.0
    duration_ms: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0.0
    model: str | None = None
    error: str | None = None
    retries: int = 0
    input_keys: list[str] = field(default_factory=list)
    output_keys: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def start(self) -> None:
        self.start_time = time.time()

    def stop(self, error: str | None = None) -> None:
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        if error:
            self.error = error

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["duration_ms"] = round(d["duration_ms"], 2)
        d["cost"] = round(d["cost"], 6)
        return d


@dataclass
class Trace:
    """Full execution trace for a DAG run."""

    dag_name: str
    run_id: str
    spans: list[Span] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0

    def start(self) -> None:
        self.start_time = time.time()

    def stop(self) -> None:
        self.end_time = time.time()

    def add_span(self, span: Span) -> None:
        self.spans.append(span)

    @property
    def total_duration_ms(self) -> float:
        return round((self.end_time - self.start_time) * 1000, 2)

    @property
    def total_tokens_in(self) -> int:
        return sum(s.tokens_in for s in self.spans)

    @property
    def total_tokens_out(self) -> int:
        return sum(s.tokens_out for s in self.spans)

    @property
    def total_cost(self) -> float:
        return round(sum(s.cost for s in self.spans), 6)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dag_name": self.dag_name,
            "run_id": self.run_id,
            "total_duration_ms": self.total_duration_ms,
            "total_tokens": {
                "input": self.total_tokens_in,
                "output": self.total_tokens_out,
            },
            "total_cost": f"${self.total_cost:.4f}",
            "spans": [s.to_dict() for s in self.spans],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, path: str | Path) -> None:
        Path(path).write_text(self.to_json())

    def summary(self) -> str:
        lines = [
            f"DAG: {self.dag_name} (run: {self.run_id})",
            f"Total: {self.total_duration_ms}ms | ${self.total_cost:.4f} | "
            f"{self.total_tokens_in}+{self.total_tokens_out} tokens",
            "",
            f"{'Node':<25} {'Type':<12} {'Duration':>10} {'Cost':>10} {'Tokens':>12} {'Status':>8}",
            "-" * 80,
        ]
        for s in self.spans:
            status = "ERROR" if s.error else "OK"
            tokens = f"{s.tokens_in}+{s.tokens_out}"
            lines.append(
                f"{s.node_name:<25} {s.node_type:<12} {s.duration_ms:>8.0f}ms "
                f"${s.cost:>8.4f} {tokens:>12} {status:>8}"
            )
        return "\n".join(lines)
