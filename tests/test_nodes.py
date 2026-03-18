"""Tests for node types and the >> operator."""

import pytest
from reasonflow import CodeNode, DecisionNode, LLMNode, parallel
from reasonflow.nodes.base import NodeChain, ParallelGroup


# ── CodeNode ────────────────────────────────────────────


class TestCodeNode:
    def test_decorator_creates_node(self):
        @CodeNode
        def my_node(state):
            return {"x": 1}

        assert my_node.name == "my_node"
        assert my_node.node_type == "CodeNode"

    @pytest.mark.asyncio
    async def test_execute(self):
        @CodeNode
        def upper(state):
            return {"text": state["text"].upper()}

        result = await upper.execute({"text": "hello"})
        assert result == {"text": "HELLO"}

    @pytest.mark.asyncio
    async def test_execute_none_return(self):
        @CodeNode
        def noop(state):
            pass

        result = await noop.execute({"x": 1})
        assert result is None

    @pytest.mark.asyncio
    async def test_async_code_node(self):
        @CodeNode
        async def async_node(state):
            return {"doubled": state["n"] * 2}

        result = await async_node.execute({"n": 5})
        assert result == {"doubled": 10}


# ── DecisionNode ────────────────────────────────────────


class TestDecisionNode:
    def test_decorator(self):
        @DecisionNode
        def router(state):
            return "next"

        assert router.name == "router"
        assert router.node_type == "DecisionNode"

    @pytest.mark.asyncio
    async def test_route_next(self):
        @DecisionNode
        def router(state):
            return "next"

        result = await router.execute({"x": 1})
        assert result == {"_route": "next"}

    @pytest.mark.asyncio
    async def test_route_to_node(self):
        @DecisionNode
        def router(state):
            if state["valid"]:
                return "next"
            return "retry_node"

        result = await router.execute({"valid": False})
        assert result == {"_route": "retry_node"}


# ── >> Operator (chaining) ──────────────────────────────


class TestChaining:
    def test_two_nodes(self):
        @CodeNode
        def a(state):
            pass

        @CodeNode
        def b(state):
            pass

        chain = a >> b
        assert isinstance(chain, NodeChain)
        assert len(chain.items) == 2
        assert chain.items[0].name == "a"
        assert chain.items[1].name == "b"

    def test_three_nodes(self):
        @CodeNode
        def a(state):
            pass

        @CodeNode
        def b(state):
            pass

        @CodeNode
        def c(state):
            pass

        chain = a >> b >> c
        assert len(chain.items) == 3

    def test_chain_with_parallel(self):
        @CodeNode
        def a(state):
            pass

        @CodeNode
        def b(state):
            pass

        @CodeNode
        def c(state):
            pass

        group = parallel(a, b)
        chain = group >> c
        assert isinstance(chain, NodeChain)
        assert isinstance(chain.items[0], ParallelGroup)
        assert chain.items[1].name == "c"

    def test_optional(self):
        @CodeNode
        def a(state):
            pass

        a.optional()
        assert a.config.is_optional is True


# ── parallel() ──────────────────────────────────────────


class TestParallel:
    def test_creates_group(self):
        @CodeNode
        def a(state):
            pass

        @CodeNode
        def b(state):
            pass

        group = parallel(a, b)
        assert isinstance(group, ParallelGroup)
        assert len(group.nodes) == 2

    def test_repr(self):
        @CodeNode
        def x(state):
            pass

        @CodeNode
        def y(state):
            pass

        group = parallel(x, y)
        assert "parallel(x, y)" in repr(group)
