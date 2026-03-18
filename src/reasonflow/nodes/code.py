"""CodeNode — wraps a pure Python function."""

from __future__ import annotations

import asyncio
import inspect
from typing import Any, Callable

from reasonflow.nodes.base import BaseNode, NodeConfig


class CodeNodeInstance(BaseNode):
    """A node that executes a plain Python function."""

    async def execute(self, state: dict[str, Any], context: Any = None) -> dict[str, Any] | None:
        if asyncio.iscoroutinefunction(self.func):
            result = await self.func(state)
        else:
            result = self.func(state)
        return result if isinstance(result, dict) else None


def CodeNode(func: Callable | None = None, **kwargs: Any) -> Any:
    """Decorator to create a CodeNode.

    Usage:
        @CodeNode
        def transform(state):
            return {"upper": state["text"].upper()}
    """
    def wrap(f: Callable) -> CodeNodeInstance:
        config = NodeConfig(
            name=f.__name__,
            node_type="CodeNode",
            **kwargs,
        )
        return CodeNodeInstance(f, config)

    if func is not None:
        return wrap(func)
    return wrap
