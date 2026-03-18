"""Tests for DAG execution engine."""

import pytest
from reasonflow import DAG, CodeNode, DecisionNode, parallel


class TestDAGBasic:
    def test_create_dag(self):
        dag = DAG("test")
        assert dag.name == "test"

    def test_no_chain_raises(self):
        dag = DAG("test")
        with pytest.raises(RuntimeError, match="no connected nodes"):
            dag.run()

    def test_single_code_node(self):
        @CodeNode
        def add_greeting(state):
            return {"greeting": f"Hello, {state['name']}!"}

        dag = DAG("test")
        dag.connect(add_greeting >> add_greeting)  # need at least chain
        # Actually let's test with proper connect
        dag2 = DAG("test2")
        chain = add_greeting  # single node
        dag2.connect(chain)
        result = dag2.run(name="World")
        assert result.success
        assert result["greeting"] == "Hello, World!"

    def test_linear_chain(self):
        @CodeNode
        def step1(state):
            return {"a": state["x"] + 1}

        @CodeNode
        def step2(state):
            return {"b": state["a"] * 2}

        @CodeNode
        def step3(state):
            return {"c": state["b"] + 10}

        dag = DAG("linear")
        dag.connect(step1 >> step2 >> step3)
        result = dag.run(x=5)
        assert result.success
        assert result["a"] == 6
        assert result["b"] == 12
        assert result["c"] == 22

    def test_state_flows_through(self):
        @CodeNode
        def set_x(state):
            return {"x": 10}

        @CodeNode
        def use_x(state):
            return {"y": state["x"] + state["initial"]}

        dag = DAG("flow")
        dag.connect(set_x >> use_x)
        result = dag.run(initial=5)
        assert result["x"] == 10
        assert result["y"] == 15


class TestDAGDecision:
    def test_decision_next(self):
        @CodeNode
        def step1(state):
            return {"val": 42}

        @DecisionNode
        def check(state):
            return "next"

        @CodeNode
        def step2(state):
            return {"done": True}

        dag = DAG("decision")
        dag.connect(step1 >> check >> step2)
        result = dag.run()
        assert result.success
        assert result["done"] is True

    def test_decision_routing(self):
        @CodeNode
        def init(state):
            return {"count": 0}

        @CodeNode
        def increment(state):
            return {"count": state["count"] + 1}

        @DecisionNode
        def check_count(state):
            if state["count"] < 3:
                return "increment"
            return "next"

        @CodeNode
        def finalize(state):
            return {"result": f"counted to {state['count']}"}

        dag = DAG("loop")
        dag.connect(init >> increment >> check_count >> finalize)
        result = dag.run()
        assert result.success
        assert result["count"] == 3
        assert result["result"] == "counted to 3"


class TestDAGParallel:
    def test_parallel_execution(self):
        @CodeNode
        def branch_a(state):
            return {"a_result": "from_a"}

        @CodeNode
        def branch_b(state):
            return {"b_result": "from_b"}

        @CodeNode
        def merge(state):
            return {"merged": f"{state['a_result']}+{state['b_result']}"}

        dag = DAG("parallel")
        dag.connect(parallel(branch_a, branch_b) >> merge)
        result = dag.run()
        assert result.success
        assert result["a_result"] == "from_a"
        assert result["b_result"] == "from_b"
        assert result["merged"] == "from_a+from_b"


class TestDAGTrace:
    def test_trace_recorded(self):
        @CodeNode
        def step1(state):
            return {"x": 1}

        @CodeNode
        def step2(state):
            return {"y": 2}

        dag = DAG("traced")
        dag.connect(step1 >> step2)
        result = dag.run()
        assert result.trace is not None
        assert len(result.trace.spans) == 2
        assert result.trace.spans[0].node_name == "step1"
        assert result.trace.spans[1].node_name == "step2"

    def test_trace_json(self):
        @CodeNode
        def node(state):
            return {"done": True}

        dag = DAG("json-trace")
        dag.connect(node)
        result = dag.run()
        json_str = result.trace.to_json()
        assert "json-trace" in json_str
        assert "node" in json_str


class TestDAGBudget:
    def test_budget_tracking(self):
        @CodeNode
        def step(state):
            return {"x": 1}

        dag = DAG("budget", budget="$1.00")
        dag.connect(step)
        result = dag.run()
        assert result.success
        assert result.total_cost == "$0.0000"  # CodeNodes have no LLM cost


class TestDAGErrors:
    def test_node_error_captured(self):
        @CodeNode
        def fail_node(state):
            raise ValueError("something broke")

        dag = DAG("error")
        dag.connect(fail_node)
        result = dag.run()
        assert not result.success
        assert "something broke" in result.error

    def test_optional_node_skipped_on_error(self):
        @CodeNode
        def good(state):
            return {"x": 1}

        @CodeNode
        def bad(state):
            raise RuntimeError("fail")

        bad.optional()

        @CodeNode
        def after(state):
            return {"done": True}

        dag = DAG("optional")
        dag.connect(good >> bad >> after)
        result = dag.run()
        assert result.success
        assert result["done"] is True
