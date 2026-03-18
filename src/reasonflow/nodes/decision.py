"""DecisionNode — conditional routing based on state."""

from __future__ import annotations

import asyncio
import inspect
from typing import Any, Callable

from reasonflow.nodes.base import BaseNode, NodeConfig


class DecisionNodeInstance(BaseNode):
    """A node that returns a routing decision."""

    async def execute(self, state: dict[str, Any], context: Any = None) -> dict[str, Any] | None:
        if asyncio.iscoroutinefunction(self.func):
            result = await self.func(state)
        else:
            result = self.func(state)

        # Result should be a string: node name to jump to, or "next"
        if isinstance(result, str):
            return {"_route": result}
        return None


def DecisionNode(func: Callable | None = None, **kwargs: Any) -> Any:
    """Decorator to create a DecisionNode.

    The function should return a string:
    - "next" to continue to the next node in the chain
    - A node name to jump to that node
    - Any other string is treated as a node name

    Usage:
        @DecisionNode
        def validate_sql(state):
            if not is_valid(state["sql"]):
                return "generate_sql"      # retry generation
            if is_destructive(state["sql"]):
                return "human_review"       # escalate
            return "next"                   # continue
    """
    def wrap(f: Callable) -> DecisionNodeInstance:
        config = NodeConfig(
            name=f.__name__,
            node_type="DecisionNode",
            **kwargs,
        )
        return DecisionNodeInstance(f, config)

    if func is not None:
        return wrap(func)
    return wrap
