"""Multi-model debate — parallel LLMs argue, then a judge synthesizes.

This shows:
- parallel() with multiple LLMNodes hitting different models
- Fan-in to a synthesis/judge LLMNode
- Comparing perspectives from different LLMs

Run with:
    reasonflow run examples/multi_model_debate.py -v question="Should companies adopt AI coding assistants?"
"""

from reasonflow import DAG, LLMNode, parallel


@LLMNode(model="claude-haiku", budget="$0.05")
def perspective_a(state):
    """You are a pragmatic CTO who focuses on developer productivity and ROI.

    Question: {question}

    Argue your position in 3-4 sentences. Be specific with examples.
    """
    pass


@LLMNode(model="gpt-4o-mini", budget="$0.05")
def perspective_b(state):
    """You are a security-focused engineering lead concerned about code quality and IP risks.

    Question: {question}

    Argue your position in 3-4 sentences. Be specific with examples.
    """
    pass


@LLMNode(model="claude-sonnet", budget="$0.10")
def perspective_c(state):
    """You are a senior developer who cares about craft, learning, and long-term skill development.

    Question: {question}

    Argue your position in 3-4 sentences. Be specific with examples.
    """
    pass


@LLMNode(model="claude-sonnet", budget="$0.10")
def judge(state):
    """You are a balanced moderator. Three experts debated this question:

    Question: {question}

    Perspective A (CTO — productivity focus):
    {perspective_a}

    Perspective B (Security lead — risk focus):
    {perspective_b}

    Perspective C (Senior dev — craft focus):
    {perspective_c}

    Synthesize their arguments into a balanced verdict:
    1. Where they agree
    2. Key tensions between perspectives
    3. Your recommended approach

    Return as JSON with keys: "consensus" (list), "tensions" (list), "verdict" (string).
    """
    pass


# ── Build the DAG ───────────────────────────────────────

dag = DAG("multi-model-debate", budget="$0.50", debug=True)

dag.connect(
    parallel(perspective_a, perspective_b, perspective_c)
    >> judge
)


if __name__ == "__main__":
    question = "Should companies adopt AI coding assistants?"
    result = dag.run(question=question)
    print(result.trace.summary())
    print()
    if result.success:
        print(f"Question: {question}\n")
        print("=== Verdict ===")
        print(result.state.get("verdict", "N/A"))
        print("\n=== Consensus Points ===")
        for point in result.state.get("consensus", []):
            print(f"  - {point}")
        print("\n=== Key Tensions ===")
        for tension in result.state.get("tensions", []):
            print(f"  - {tension}")
    else:
        print(f"Error: {result.error}")
