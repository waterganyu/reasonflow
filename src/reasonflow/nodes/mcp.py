"""MCPNode — connects to MCP servers for tool discovery and execution."""

from __future__ import annotations

import asyncio
import inspect
from typing import Any, Callable

from reasonflow.context import MCPContext, NodeContext
from reasonflow.nodes.base import BaseNode, NodeConfig


class MCPNodeInstance(BaseNode):
    """A node that interacts with an MCP server."""

    def __init__(self, func: Callable, config: NodeConfig, server: str):
        super().__init__(func, config)
        self.server = server

    async def execute(self, state: dict[str, Any], context: Any = None) -> dict[str, Any] | None:
        mcp_ctx = MCPContext(server=self.server, node_name=self.name)
        node_ctx = NodeContext(mcp=mcp_ctx)

        try:
            sig = inspect.signature(self.func)
            params = list(sig.parameters)
            if len(params) >= 2:
                result = self.func(state, node_ctx)
            else:
                result = self.func(state)
            if inspect.isawaitable(result):
                result = await result
        finally:
            await mcp_ctx.close()

        return result if isinstance(result, dict) else None


class MCPServer:
    """Reference to an MCP server, used when attaching tools to LLMNode."""

    def __init__(self, server: str):
        self.server = server

    def __repr__(self) -> str:
        return f"MCPServer({self.server!r})"


def MCPNode(
    func: Callable | None = None,
    *,
    server: str = "",
    max_retries: int = 0,
    retry_on: list[str] | None = None,
    **kwargs: Any,
) -> Any:
    """Decorator to create an MCPNode.

    Usage:
        @MCPNode(server="postgres://localhost:5432/mydb")
        def query_db(state, context):
            result = await context.mcp.call_tool("query", {"sql": state["sql"]})
            return {"results": result}

        @MCPNode(server="postgres://localhost:5432/mydb")
        def discover_schema(state):
            pass  # Just connects and makes tools available
    """
    def wrap(f: Callable) -> MCPNodeInstance:
        config = NodeConfig(
            name=f.__name__,
            node_type="MCPNode",
            max_retries=max_retries,
            retry_on=retry_on or [],
        )
        return MCPNodeInstance(f, config, server=server)

    if func is not None:
        return wrap(func)
    return wrap
