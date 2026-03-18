"""Node execution context — provides LLM and MCP helpers to node functions."""

from __future__ import annotations

import json
from typing import Any


class LLMContext:
    """Provides LLM completion helpers inside node functions."""

    def __init__(self, model: str, node_name: str):
        self.model = model
        self.node_name = node_name
        self._last_usage: dict[str, int] = {}

    async def complete(
        self,
        prompt: str,
        system: str | None = None,
        response_format: dict | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> str | dict[str, Any]:
        """Call LLM and return response text or parsed JSON."""
        import litellm

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = await litellm.acompletion(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

        self._last_usage = {
            "tokens_in": response.usage.prompt_tokens,
            "tokens_out": response.usage.completion_tokens,
        }

        content = response.choices[0].message.content or ""

        if response_format:
            return _try_parse_json(content)
        return content

    @property
    def last_usage(self) -> dict[str, int]:
        return self._last_usage


class MCPContext:
    """Provides MCP tool calling helpers inside node functions."""

    def __init__(self, server: str, node_name: str):
        self.server = server
        self.node_name = node_name
        self._client: Any = None

    async def connect(self) -> None:
        from reasonflow.mcp_client import MCPClient
        self._client = MCPClient(self.server)
        await self._client.connect()

    async def list_tools(self) -> list[dict[str, Any]]:
        if not self._client:
            await self.connect()
        return await self._client.list_tools()

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        if not self._client:
            await self.connect()
        return await self._client.call_tool(name, arguments or {})

    async def close(self) -> None:
        if self._client:
            await self._client.close()
            self._client = None


class NodeContext:
    """Combined context passed to node functions."""

    def __init__(
        self,
        llm: LLMContext | None = None,
        mcp: MCPContext | None = None,
    ):
        self.llm = llm
        self.mcp = mcp

    async def complete(self, prompt: str, **kwargs: Any) -> str | dict[str, Any]:
        """Shorthand for self.llm.complete()."""
        if not self.llm:
            raise RuntimeError("No LLM context available in this node")
        return await self.llm.complete(prompt, **kwargs)


def _try_parse_json(text: str) -> dict[str, Any] | str:
    """Try to parse JSON from LLM response, handling markdown code blocks."""
    text = text.strip()
    # Strip markdown code block if present
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return text
