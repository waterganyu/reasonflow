"""LLMNode — makes LLM calls via litellm."""

from __future__ import annotations

import inspect
import json
from typing import Any, Callable

from reasonflow.context import LLMContext, NodeContext, _try_parse_json
from reasonflow.cost import parse_budget
from reasonflow.nodes.base import BaseNode, NodeConfig, _is_trivial_body


class LLMNodeInstance(BaseNode):
    """A node that calls an LLM."""

    def __init__(self, func: Callable, config: NodeConfig, model: str, auto_mode: bool):
        super().__init__(func, config)
        self.model = model
        self.auto_mode = auto_mode
        self.tools: list[Any] = config.metadata.get("tools", [])
        self.max_tool_calls: int = config.metadata.get("max_tool_calls", 10)

    async def execute(self, state: dict[str, Any], context: Any = None) -> dict[str, Any] | None:
        llm_ctx = LLMContext(model=self.model, node_name=self.name)
        node_ctx = NodeContext(llm=llm_ctx)

        if self.auto_mode:
            result = await self._auto_execute(state, llm_ctx)
        else:
            sig = inspect.signature(self.func)
            params = list(sig.parameters)
            if len(params) >= 2:
                result = self.func(state, node_ctx)
            else:
                result = self.func(state)
            if inspect.isawaitable(result):
                result = await result

        # Attach usage to context for trace recording
        if context and hasattr(context, "_record_llm_usage"):
            context._record_llm_usage(llm_ctx.last_usage)
        self._last_usage = llm_ctx.last_usage

        return result if isinstance(result, dict) else None

    async def _auto_execute(self, state: dict[str, Any], llm: LLMContext) -> dict[str, Any] | None:
        """Auto-mode: docstring is system prompt, state serialized as user message."""
        system_prompt = self.func.__doc__ or ""
        user_content = json.dumps(state, indent=2, default=str)

        response = await llm.complete(
            prompt=user_content,
            system=system_prompt.strip(),
        )

        if isinstance(response, dict):
            return response
        if isinstance(response, str):
            parsed = _try_parse_json(response)
            if isinstance(parsed, dict):
                return parsed
            # Plain text response — store under the node's name
            return {self.name: parsed}
        return None


def LLMNode(
    func: Callable | None = None,
    *,
    model: str = "claude-sonnet",
    budget: str | float | None = None,
    retry_on: list[str] | None = None,
    max_retries: int = 0,
    tools: list[Any] | None = None,
    max_tool_calls: int = 10,
    **kwargs: Any,
) -> Any:
    """Decorator to create an LLMNode.

    Usage:
        @LLMNode(model="claude-sonnet", budget="$0.05")
        def parse_question(state):
            '''Parse the user's question into structured intent.'''
            pass  # auto-mode: docstring is prompt

        @LLMNode(model="claude-sonnet")
        def custom_logic(state, context):
            result = await context.complete("Analyze this: " + state["text"])
            return {"analysis": result}
    """
    def wrap(f: Callable) -> LLMNodeInstance:
        auto_mode = _is_trivial_body(f)
        config = NodeConfig(
            name=f.__name__,
            node_type="LLMNode",
            budget=parse_budget(budget),
            max_retries=max_retries,
            retry_on=retry_on or [],
            metadata={"tools": tools or [], "max_tool_calls": max_tool_calls},
        )
        return LLMNodeInstance(f, config, model=model, auto_mode=auto_mode)

    if func is not None:
        return wrap(func)
    return wrap
