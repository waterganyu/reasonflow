"""MCP protocol client — connects to MCP servers for tool discovery and execution."""

from __future__ import annotations

from typing import Any


class MCPClient:
    """Client for connecting to MCP servers.

    Supports SSE (HTTP) and stdio transports.
    """

    def __init__(self, server: str):
        self.server = server
        self._session: Any = None
        self._transport: str = self._detect_transport(server)

    @staticmethod
    def _detect_transport(server: str) -> str:
        if server.startswith(("http://", "https://")):
            return "sse"
        if server.startswith("file://"):
            return "stdio"
        if "://" in server:
            # postgres://, mysql://, etc. — treated as stdio with adapter
            return "stdio"
        return "stdio"

    async def connect(self) -> None:
        """Establish connection to the MCP server."""
        try:
            from mcp import ClientSession
            from mcp.client.sse import sse_client
            from mcp.client.stdio import stdio_client
        except ImportError:
            raise ImportError(
                "MCP support requires the 'mcp' package. "
                "Install it with: pip install reasonflow[mcp]"
            )

        if self._transport == "sse":
            self._read, self._write = await sse_client(self.server).__aenter__()
            self._session = ClientSession(self._read, self._write)
            await self._session.__aenter__()
            await self._session.initialize()

    async def list_tools(self) -> list[dict[str, Any]]:
        """List available tools on the MCP server."""
        if not self._session:
            await self.connect()
        result = await self._session.list_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.inputSchema,
            }
            for tool in result.tools
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        """Call a tool on the MCP server."""
        if not self._session:
            await self.connect()
        result = await self._session.call_tool(name, arguments)
        # Extract text content from MCP response
        if hasattr(result, "content") and result.content:
            texts = []
            for item in result.content:
                if hasattr(item, "text"):
                    texts.append(item.text)
            return texts[0] if len(texts) == 1 else texts
        return result

    async def close(self) -> None:
        """Close the MCP connection."""
        if self._session:
            try:
                await self._session.__aexit__(None, None, None)
            except Exception:
                pass
            self._session = None
