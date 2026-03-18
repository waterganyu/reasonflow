"""DAG engine — connects nodes, executes pipelines, tracks everything."""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from reasonflow.cost import CostTracker, parse_budget
from reasonflow.nodes.base import BaseNode, NodeChain, ParallelGroup
from reasonflow.retry import retry_async, NodeExecutionError
from reasonflow.state import SharedState
from reasonflow.trace import Span, Trace


# Directory for storing traces
TRACE_DIR = Path.home() / ".reasonflow" / "traces"


@dataclass
class DAGResult:
    """Result of a DAG execution."""

    state: dict[str, Any]
    trace: Trace
    total_cost: str
    tokens: dict[str, int]
    success: bool = True
    error: str | None = None

    def __getitem__(self, key: str) -> Any:
        return self.state[key]

    def __contains__(self, key: str) -> bool:
        return key in self.state

    def __repr__(self) -> str:
        return (
            f"DAGResult(success={self.success}, cost={self.total_cost}, "
            f"tokens={self.tokens})"
        )


class DAG:
    """Directed Acyclic Graph for agent pipeline execution.

    Usage:
        dag = DAG("my-pipeline", budget="$0.30")
        dag.connect(node_a >> node_b >> node_c)
        result = dag.run(question="What is X?")
    """

    def __init__(
        self,
        name: str,
        budget: str | float | None = None,
        on_budget_exceeded: str = "warn",
        debug: bool = False,
    ):
        self.name = name
        self.budget = parse_budget(budget)
        self.on_budget_exceeded = on_budget_exceeded
        self.debug = debug
        self._chain: NodeChain | None = None
        self._nodes: dict[str, BaseNode] = {}

    def connect(self, chain: NodeChain | BaseNode) -> None:
        """Set the execution chain for this DAG."""
        if isinstance(chain, BaseNode):
            nc = NodeChain()
            nc.add(chain)
            chain = nc
        self._chain = chain
        # Index all nodes by name for routing
        self._index_nodes(chain)

    def _index_nodes(self, chain: NodeChain) -> None:
        for item in chain.items:
            if isinstance(item, ParallelGroup):
                for node in item.nodes:
                    self._nodes[node.name] = node
            elif isinstance(item, BaseNode):
                self._nodes[item.name] = item

    def run(self, **inputs: Any) -> DAGResult:
        """Run the DAG synchronously. Wraps async execution."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already in an async context — use nest_asyncio or run in thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self._run_async(**inputs))
                return future.result()
        else:
            return asyncio.run(self._run_async(**inputs))

    async def run_async(self, **inputs: Any) -> DAGResult:
        """Run the DAG asynchronously."""
        return await self._run_async(**inputs)

    async def _run_async(self, **inputs: Any) -> DAGResult:
        if not self._chain:
            raise RuntimeError(f"DAG '{self.name}' has no connected nodes. Call dag.connect() first.")

        run_id = uuid.uuid4().hex[:12]
        state = SharedState(inputs)
        trace = Trace(dag_name=self.name, run_id=run_id)
        cost_tracker = CostTracker(
            budget=self.budget,
            on_exceeded=self.on_budget_exceeded,
        )

        trace.start()
        error_msg: str | None = None

        try:
            await self._execute_chain(
                self._chain, state, trace, cost_tracker
            )
        except Exception as e:
            error_msg = str(e)
        finally:
            trace.stop()
            # Save trace
            self._save_trace(trace)

        return DAGResult(
            state=dict(state),
            trace=trace,
            total_cost=f"${cost_tracker.total_cost:.4f}",
            tokens={
                "input": cost_tracker.total_tokens_in,
                "output": cost_tracker.total_tokens_out,
            },
            success=error_msg is None,
            error=error_msg,
        )

    async def _execute_chain(
        self,
        chain: NodeChain,
        state: SharedState,
        trace: Trace,
        cost_tracker: CostTracker,
    ) -> None:
        items = chain.items
        i = 0
        while i < len(items):
            item = items[i]

            if isinstance(item, ParallelGroup):
                await self._execute_parallel(item, state, trace, cost_tracker)
                i += 1
            elif isinstance(item, BaseNode):
                route = await self._execute_node(item, state, trace, cost_tracker)
                if route and route != "next":
                    # Find the target node index in the chain
                    target_idx = self._find_node_index(items, route)
                    if target_idx is not None:
                        i = target_idx
                    else:
                        raise NodeExecutionError(
                            f"DecisionNode '{item.name}' routed to unknown node: {route!r}",
                            error_type="routing_error",
                            node_name=item.name,
                        )
                else:
                    i += 1
            else:
                i += 1

    async def _execute_node(
        self,
        node: BaseNode,
        state: SharedState,
        trace: Trace,
        cost_tracker: CostTracker,
    ) -> str | None:
        """Execute a single node, handling retries and budget checks."""
        # Budget check
        budget_action = cost_tracker.check_budget(node.name)
        if budget_action == "halt":
            raise NodeExecutionError(
                f"Budget exceeded before node '{node.name}'",
                error_type="budget_exceeded",
                node_name=node.name,
            )
        if budget_action and node.config.is_optional:
            return None  # Skip optional nodes on budget issues

        span = Span(
            node_name=node.name,
            node_type=node.node_type,
            input_keys=list(state.keys()),
        )
        span.start()
        state.snapshot(node.name)

        try:
            policy = node.config.retry_policy
            frozen = state.frozen_copy()

            async def _exec():
                return await node.execute(frozen)

            result, retries = await retry_async(_exec, policy)
            span.retries = retries

            # Merge results into state
            if result:
                route = result.pop("_route", None)
                state.merge(result)
                span.output_keys = list(result.keys())
            else:
                route = None

            # Debug output
            if self.debug or node._debug:
                self._print_debug(node.name, result)

            # Record LLM cost if available
            if hasattr(node, "_last_usage") and node._last_usage:
                usage = node._last_usage
                model = getattr(node, "model", "unknown")
                cost = cost_tracker.record(
                    node.name, model,
                    usage.get("tokens_in", 0),
                    usage.get("tokens_out", 0),
                )
                span.tokens_in = usage.get("tokens_in", 0)
                span.tokens_out = usage.get("tokens_out", 0)
                span.cost = cost
                span.model = model

            span.stop()
            trace.add_span(span)
            return route

        except Exception as e:
            span.stop(error=str(e))
            trace.add_span(span)
            if node.config.is_optional:
                return None
            raise

    async def _execute_parallel(
        self,
        group: ParallelGroup,
        state: SharedState,
        trace: Trace,
        cost_tracker: CostTracker,
    ) -> None:
        """Execute parallel nodes concurrently and merge results."""
        tasks = []
        for node in group.nodes:
            tasks.append(
                self._execute_node(node, state, trace, cost_tracker)
            )
        await asyncio.gather(*tasks)

    @staticmethod
    def _find_node_index(
        items: list[BaseNode | ParallelGroup], target_name: str
    ) -> int | None:
        for i, item in enumerate(items):
            if isinstance(item, BaseNode) and item.name == target_name:
                return i
        return None

    @staticmethod
    def _print_debug(node_name: str, result: dict[str, Any] | None) -> None:
        """Print a node's output for debugging."""
        if not result:
            print(f"  [{node_name}] → (no output)")
            return
        parts = []
        for k, v in result.items():
            s = repr(v)
            if len(s) > 80:
                s = s[:77] + "..."
            parts.append(f"{k}={s}")
        print(f"  [{node_name}] → {', '.join(parts)}")

    def _save_trace(self, trace: Trace) -> None:
        """Save trace to ~/.reasonflow/traces/"""
        try:
            TRACE_DIR.mkdir(parents=True, exist_ok=True)
            path = TRACE_DIR / f"{self.name}_{trace.run_id}.json"
            trace.save(path)
        except Exception:
            pass  # Don't fail the run because of trace saving

    def __repr__(self) -> str:
        nodes = len(self._nodes)
        return f"DAG({self.name!r}, nodes={nodes})"
