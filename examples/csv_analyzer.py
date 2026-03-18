"""CSV analyzer — read a CSV, compute stats, and get LLM insights.

This shows:
- Reading and parsing CSV files in a CodeNode
- Computing statistics without pandas (stdlib only)
- LLMNode interpreting data patterns

Run with:
    reasonflow run examples/csv_analyzer.py -v csv_path="data.csv"
"""

import csv
import statistics
from pathlib import Path

from reasonflow import DAG, LLMNode, CodeNode


@CodeNode
def read_csv(state):
    """Read and parse the CSV file."""
    csv_path = state.get("csv_path", "data.csv")
    path = Path(csv_path)

    if not path.exists():
        # Generate sample data if no file provided
        return _generate_sample_data()

    with open(path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    return {
        "headers": list(rows[0].keys()) if rows else [],
        "row_count": len(rows),
        "rows": rows,
        "csv_path": str(path),
    }


def _generate_sample_data():
    """Generate sample sales data for demo purposes."""
    import random
    random.seed(42)

    rows = []
    products = ["Widget A", "Widget B", "Gadget X", "Gadget Y"]
    regions = ["North", "South", "East", "West"]
    for month in range(1, 13):
        for product in products:
            for region in regions:
                rows.append({
                    "month": str(month),
                    "product": product,
                    "region": region,
                    "units": str(random.randint(50, 500)),
                    "revenue": str(round(random.uniform(1000, 25000), 2)),
                })

    return {
        "headers": ["month", "product", "region", "units", "revenue"],
        "row_count": len(rows),
        "rows": rows,
        "csv_path": "(generated sample data)",
    }


@CodeNode
def compute_stats(state):
    """Compute summary statistics for numeric columns."""
    rows = state.get("rows", [])
    headers = state.get("headers", [])

    if not rows:
        return {"stats": {}, "sample_rows": []}

    # Detect numeric columns
    stats = {}
    for col in headers:
        values = []
        for row in rows:
            try:
                values.append(float(row[col]))
            except (ValueError, KeyError):
                break
        else:
            if values:
                stats[col] = {
                    "min": round(min(values), 2),
                    "max": round(max(values), 2),
                    "mean": round(statistics.mean(values), 2),
                    "median": round(statistics.median(values), 2),
                    "stdev": round(statistics.stdev(values), 2) if len(values) > 1 else 0,
                    "sum": round(sum(values), 2),
                }

    # Sample rows for the LLM
    sample = rows[:5]

    return {"stats": stats, "sample_rows": sample}


@LLMNode(model="claude-haiku", budget="$0.05")
def analyze_data(state):
    """You are a data analyst. Analyze this CSV dataset.

    File: {csv_path}
    Total rows: {row_count}
    Columns: {headers}

    Statistics:
    {stats}

    Sample rows:
    {sample_rows}

    Provide:
    1. A brief description of the dataset
    2. Key patterns or trends in the numbers
    3. Any anomalies or notable observations
    4. One actionable recommendation

    Return as JSON with keys: "description", "patterns" (list), "anomalies" (list), "recommendation".
    """
    pass


# ── Build the DAG ───────────────────────────────────────

dag = DAG("csv-analyzer", budget="$0.10", debug=True)

dag.connect(read_csv >> compute_stats >> analyze_data)


if __name__ == "__main__":
    result = dag.run()
    print(result.trace.summary())
    print()
    if result.success:
        print(f"Dataset: {result.state.get('csv_path')}")
        print(f"Rows: {result.state.get('row_count')}")
        print(f"\nDescription: {result.state.get('description', 'N/A')}")
        print(f"\nPatterns:")
        for p in result.state.get("patterns", []):
            print(f"  - {p}")
        print(f"\nRecommendation: {result.state.get('recommendation', 'N/A')}")
    else:
        print(f"Error: {result.error}")
