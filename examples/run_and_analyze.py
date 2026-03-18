"""Run a Python script and send its output to an LLM for analysis.

This shows:
- Running a Python script via subprocess in a CodeNode
- Passing stdout to an LLMNode for analysis
- Chaining bash execution with LLM reasoning

Run with:
    reasonflow run examples/run_and_analyze.py
"""

import subprocess
from pathlib import Path

from reasonflow import DAG, LLMNode, CodeNode


@CodeNode
def run_script(state):
    """Execute the Python script and capture its output."""
    script = Path(__file__).parent / "another_code_example.py"
    result = subprocess.run(
        ["python", str(script)],
        capture_output=True,
        text=True,
    )
    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.returncode,
    }


@LLMNode(model="gpt-5.2", budget="$0.10")
def analyze_output(state):
    """You are a business analyst. Analyze the script output below and provide:
    1. A brief summary of the data
    2. Key insights or trends
    3. One actionable recommendation

    Script output:
    {stdout}

    Keep your response concise (3-5 sentences).
    """
    pass


# ── Build the DAG ───────────────────────────────────────

dag = DAG("run-and-analyze", budget="$0.15", debug=True)

dag.connect(run_script >> analyze_output)


if __name__ == "__main__":
    result = dag.run()
    print(result.trace.summary())
    print()
    if result.success:
        print("=== Script Output ===")
        print(result.state["stdout"])
        print("=== LLM Analysis ===")
        # analyze_output returns parsed JSON or raw string
        for key in result.state:
            if key not in ("stdout", "stderr", "exit_code"):
                print(f"{key}: {result.state[key]}")
    else:
        print(f"Error: {result.error}")
