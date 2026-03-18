"""Text-to-SQL pipeline — the canonical ReasonFlow example.

This demonstrates:
- LLMNode for LLM calls (auto-mode with docstring prompts)
- CodeNode for pure Python logic
- DecisionNode for conditional routing
- >> operator for chaining
- Budget tracking
- Trace output

Run with:
    reasonflow run examples/text_to_sql.py -v question="top 10 customers?"

Or from Python:
    result = dag.run(question="What were our top 10 customers last month?")
"""

from reasonflow import DAG, LLMNode, CodeNode, DecisionNode


@LLMNode(model="claude-sonnet", budget="$0.05")
def parse_question(state):
    """You are a query parser. Given a natural language question about a database,
    extract the user's intent as a JSON object with keys: "action" (string),
    "entities" (list of strings), "filters" (dict), "limit" (int or null).

    Return valid JSON only."""
    pass


@CodeNode
def mock_schema(state):
    """Simulate fetching a database schema (replace with MCPNode in production)."""
    return {
        "schema": {
            "customers": ["id", "name", "email", "created_at"],
            "orders": ["id", "customer_id", "amount", "created_at"],
            "products": ["id", "name", "price", "category"],
        }
    }


@LLMNode(model="claude-sonnet", budget="$0.10", max_retries=2, retry_on=["syntax_error"])
def generate_sql(state):
    """You are a SQL expert. Given a parsed intent and database schema,
    generate a PostgreSQL query. Return ONLY the SQL query, no explanation.

    Intent: {intent}
    Schema: {schema}
    """
    pass


@DecisionNode
def validate_sql(state):
    """Check if the generated SQL is safe to execute."""
    sql = str(state.get("sql", state.get("generate_sql", "")))
    dangerous = ["DROP", "DELETE", "TRUNCATE", "ALTER", "UPDATE"]
    if any(kw in sql.upper() for kw in dangerous):
        return "generate_sql"  # retry with safer generation
    return "next"


@CodeNode
def mock_execute(state):
    """Simulate query execution (replace with MCPNode in production)."""
    return {
        "results": [
            {"name": "Acme Corp", "total": 2_300_000},
            {"name": "Globex Inc", "total": 1_850_000},
            {"name": "Initech", "total": 1_420_000},
        ]
    }


@LLMNode(model="claude-haiku", budget="$0.01")
def explain_results(state):
    """You are a data analyst. Given SQL query results, provide a clear,
    concise natural language explanation. Be specific about numbers.

    Question: {question}
    Results: {results}
    """
    pass


# ── Build the DAG ───────────────────────────────────────

dag = DAG("text-to-sql", budget="$0.30", on_budget_exceeded="degrade")

dag.connect(
    parse_question
    >> mock_schema
    >> generate_sql
    >> validate_sql
    >> mock_execute
    >> explain_results
)


if __name__ == "__main__":
    result = dag.run(question="What were our top 10 customers last month?")
    print(result.trace.summary())
    print()
    print("Final state:", {k: v for k, v in result.state.items() if not k.startswith("_")})
