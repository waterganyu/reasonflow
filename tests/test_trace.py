"""Tests for trace system."""

import json
import pytest
from reasonflow.trace import Span, Trace


class TestSpan:
    def test_timing(self):
        span = Span(node_name="test", node_type="CodeNode")
        span.start()
        span.stop()
        assert span.duration_ms >= 0
        assert span.error is None

    def test_error(self):
        span = Span(node_name="test", node_type="CodeNode")
        span.start()
        span.stop(error="broke")
        assert span.error == "broke"

    def test_to_dict(self):
        span = Span(
            node_name="n1",
            node_type="LLMNode",
            tokens_in=100,
            tokens_out=50,
            cost=0.001,
            model="claude-sonnet",
        )
        d = span.to_dict()
        assert d["node_name"] == "n1"
        assert d["tokens_in"] == 100
        assert d["model"] == "claude-sonnet"


class TestTrace:
    def test_totals(self):
        trace = Trace(dag_name="test", run_id="abc")
        trace.start()
        s1 = Span(node_name="a", node_type="LLMNode", tokens_in=100, tokens_out=50, cost=0.001)
        s2 = Span(node_name="b", node_type="LLMNode", tokens_in=200, tokens_out=100, cost=0.003)
        trace.add_span(s1)
        trace.add_span(s2)
        trace.stop()

        assert trace.total_tokens_in == 300
        assert trace.total_tokens_out == 150
        assert trace.total_cost == 0.004

    def test_to_json(self):
        trace = Trace(dag_name="test", run_id="xyz")
        trace.start()
        trace.add_span(Span(node_name="n", node_type="CodeNode"))
        trace.stop()
        j = json.loads(trace.to_json())
        assert j["dag_name"] == "test"
        assert len(j["spans"]) == 1

    def test_summary(self):
        trace = Trace(dag_name="test", run_id="abc")
        trace.start()
        trace.add_span(Span(node_name="step1", node_type="CodeNode"))
        trace.stop()
        s = trace.summary()
        assert "step1" in s
        assert "CodeNode" in s
