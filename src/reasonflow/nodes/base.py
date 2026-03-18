"""Base node and chain classes for DAG construction."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Callable

from reasonflow.retry import RetryPolicy


@dataclass
class NodeConfig:
    """Configuration shared by all node types."""

    name: str
    node_type: str
    budget: float | None = None
    max_retries: int = 0
    retry_on: list[str] = field(default_factory=list)
    is_optional: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def retry_policy(self) -> RetryPolicy:
        return RetryPolicy(
            max_retries=self.max_retries,
            retry_on=self.retry_on,
        )


class BaseNode:
    """Base class for all node types."""

    def __init__(self, func: Callable, config: NodeConfig):
        self.func = func
        self.config = config
        self.name = config.name
        self.node_type = config.node_type
        self._debug = False

    def __rshift__(self, other: BaseNode | NodeChain | ParallelGroup) -> NodeChain:
        chain = NodeChain()
        chain.add(self)
        if isinstance(other, NodeChain):
            for item in other.items:
                chain.add(item)
        else:
            chain.add(other)
        return chain

    def optional(self) -> BaseNode:
        """Mark this node as optional (skipped on budget exceeded or errors)."""
        self.config.is_optional = True
        return self

    def debug(self) -> BaseNode:
        """Enable debug output for this node — prints its output after execution."""
        self._debug = True
        return self

    async def execute(self, state: dict[str, Any], context: Any = None) -> dict[str, Any] | None:
        """Execute this node. Subclasses override this."""
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"{self.config.node_type}({self.name!r})"


class NodeChain:
    """Ordered sequence of nodes/groups connected with >>."""

    def __init__(self):
        self.items: list[BaseNode | ParallelGroup] = []

    def add(self, item: BaseNode | ParallelGroup) -> None:
        self.items.append(item)

    def __rshift__(self, other: BaseNode | NodeChain | ParallelGroup) -> NodeChain:
        if isinstance(other, NodeChain):
            for item in other.items:
                self.items.append(item)
        else:
            self.items.append(other)
        return self

    def __repr__(self) -> str:
        return " >> ".join(repr(item) for item in self.items)


class ParallelGroup:
    """A group of nodes to execute in parallel."""

    def __init__(self, nodes: list[BaseNode]):
        self.nodes = nodes
        self.name = f"parallel({', '.join(n.name for n in nodes)})"

    def __rshift__(self, other: BaseNode | NodeChain | ParallelGroup) -> NodeChain:
        chain = NodeChain()
        chain.add(self)
        if isinstance(other, NodeChain):
            for item in other.items:
                chain.add(item)
        else:
            chain.add(other)
        return chain

    def __repr__(self) -> str:
        return self.name


def parallel(*nodes: BaseNode) -> ParallelGroup:
    """Create a parallel execution group."""
    return ParallelGroup(list(nodes))


def _is_trivial_body(func: Callable) -> bool:
    """Check if a function body is just `pass` or `return None`."""
    try:
        source = inspect.getsource(func)
        # Single-pass: skip decorators, def line, comments, and docstrings
        in_docstring = False
        filtered = []
        for raw_line in source.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith("@") or line.startswith("def "):
                continue
            # Handle docstring boundaries
            for quote in ('"""', "'''"):
                if quote in line:
                    count = line.count(quote)
                    if count >= 2:
                        # Opens and closes on same line (e.g. """one-liner""")
                        continue
                    in_docstring = not in_docstring
                    break
            else:
                # No triple-quote found on this line
                if in_docstring:
                    continue
                filtered.append(line)
                continue
            # Line had a triple-quote — skip it (it's a docstring boundary)
            continue
        return not filtered or all(l in ("pass", "return None", "...") for l in filtered)
    except (OSError, TypeError):
        return False
