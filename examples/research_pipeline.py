"""Research pipeline — demonstrates parallel branches with fan-in.

This shows:
- parallel() for concurrent execution
- Multiple CodeNodes gathering data simultaneously
- LLMNode synthesizing parallel results
- Trace showing parallel timing

Run with:
    reasonflow run examples/research_pipeline.py -v topic="AI safety"
"""

from reasonflow import DAG, LLMNode, CodeNode, parallel


@CodeNode
def research_web(state):
    """Simulate web search results."""
    topic = state.get("topic", "unknown")
    return {
        "web_results": [
            f"Web result 1 about {topic}: Latest developments...",
            f"Web result 2 about {topic}: Expert opinions...",
            f"Web result 3 about {topic}: Recent papers...",
        ]
    }


@CodeNode
def research_internal(state):
    """Simulate internal database search."""
    topic = state.get("topic", "unknown")
    return {
        "db_results": [
            f"Internal doc 1: Company policy on {topic}",
            f"Internal doc 2: Previous analysis of {topic}",
        ]
    }


@CodeNode
def research_code(state):
    """Simulate code repository search."""
    topic = state.get("topic", "unknown")
    return {
        "code_results": [
            f"repo/src/main.py: Implementation related to {topic}",
            f"repo/tests/test_core.py: Tests for {topic} features",
        ]
    }


@LLMNode(model="gpt-5.2", budget="$0.15")
def synthesize(state):
    """You are a research analyst. Synthesize findings from multiple sources
    into a comprehensive report.

    Web research: {web_results}
    Internal documents: {db_results}
    Code references: {code_results}

    Provide a structured summary with key findings and recommendations.
    Return as JSON with keys: "summary", "key_findings" (list), "recommendations" (list).
    """
    pass


# ── Build the DAG ───────────────────────────────────────

dag = DAG("research-pipeline", budget="$0.25")

dag.connect(
    parallel(research_web, research_internal, research_code)
    >> synthesize
)


if __name__ == "__main__":
    result = dag.run(topic="AI safety")
    print(result.trace.summary())
    print()
    for key in ["web_results", "db_results", "code_results"]:
        print(f"{key}: {len(result.state.get(key, []))} items")
