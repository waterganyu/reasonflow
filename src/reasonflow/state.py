"""Shared state management for DAG execution."""

from __future__ import annotations

import copy
from typing import Any


class SharedState(dict):
    """Dict-based shared state passed between nodes.

    Supports merge semantics (new keys added, existing keys overwritten)
    and optional snapshot history for debugging/replay.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._history: list[dict[str, Any]] = []

    def snapshot(self, node_name: str) -> None:
        """Save a deep copy of current state tagged with the node name."""
        self._history.append({
            "node": node_name,
            "state": copy.deepcopy(dict(self)),
        })

    def merge(self, updates: dict[str, Any] | None) -> None:
        """Merge updates into state. None values are skipped."""
        if updates:
            self.update(updates)

    def frozen_copy(self) -> dict[str, Any]:
        """Return a deep copy for safe node input."""
        return copy.deepcopy(dict(self))

    @property
    def history(self) -> list[dict[str, Any]]:
        return list(self._history)
