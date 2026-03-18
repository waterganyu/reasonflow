"""Test runner — run pytest, decide on failures, analyze with LLM.

This shows:
- Running pytest via subprocess
- DecisionNode routing: pass vs fail
- LLMNode analyzing test failures and suggesting fixes

Run with:
    reasonflow run examples/test_runner.py -v test_path="tests/"
"""

import subprocess

from reasonflow import DAG, LLMNode, CodeNode, DecisionNode


@CodeNode
def run_tests(state):
    """Execute pytest and capture results."""
    test_path = state.get("test_path", "tests/")
    extra_args = state.get("pytest_args", "")

    cmd = ["python", "-m", "pytest", test_path, "-v", "--tb=short"]
    if extra_args:
        cmd.extend(extra_args.split())

    result = subprocess.run(cmd, capture_output=True, text=True)

    # Parse output for summary
    lines = result.stdout.splitlines()
    summary_line = ""
    for line in reversed(lines):
        if "passed" in line or "failed" in line or "error" in line:
            summary_line = line.strip()
            break

    # Extract failed test names
    failed_tests = []
    for line in lines:
        if "FAILED" in line:
            failed_tests.append(line.strip())

    return {
        "test_output": result.stdout,
        "test_stderr": result.stderr,
        "test_exit_code": result.returncode,
        "test_summary": summary_line,
        "failed_tests": failed_tests,
        "failed_count": len(failed_tests),
        "all_passed": result.returncode == 0,
    }


@DecisionNode
def check_results(state):
    """Route based on test results."""
    if state.get("all_passed"):
        return "report_success"
    return "analyze_failures"


@CodeNode
def report_success(state):
    """All tests passed — generate success report."""
    return {
        "report": f"All tests passed! {state.get('test_summary', '')}",
        "needs_fix": False,
    }


@LLMNode(model="claude-haiku", budget="$0.05")
def analyze_failures(state):
    """You are a senior developer debugging test failures.

    Test summary: {test_summary}
    Failed tests: {failed_count}

    Full output:
    {test_output}

    Stderr:
    {test_stderr}

    For each failed test:
    1. Identify the likely root cause
    2. Suggest a specific fix
    3. Rate confidence (high/medium/low)

    Return as JSON with keys:
    - "failures" (list of {{"test": str, "root_cause": str, "fix": str, "confidence": str}})
    - "common_pattern" (str or null — if failures share a root cause)
    - "priority_fix" (str — which test to fix first and why)
    """
    pass


@CodeNode
def format_report(state):
    """Format the analysis into a readable report."""
    lines = ["Test Failure Analysis", "=" * 40, ""]

    if state.get("common_pattern"):
        lines.append(f"Common pattern: {state['common_pattern']}")
        lines.append("")

    lines.append(f"Priority fix: {state.get('priority_fix', 'N/A')}")
    lines.append("")

    for f in state.get("failures", []):
        lines.append(f"Test: {f.get('test', '?')}")
        lines.append(f"  Root cause: {f.get('root_cause', '?')}")
        lines.append(f"  Fix: {f.get('fix', '?')}")
        lines.append(f"  Confidence: {f.get('confidence', '?')}")
        lines.append("")

    report = "\n".join(lines)
    return {"report": report, "needs_fix": True}


# ── Build the DAG ───────────────────────────────────────

dag = DAG("test-runner", budget="$0.10")

dag.connect(run_tests >> check_results >> report_success)
dag.connect(check_results >> analyze_failures >> format_report)


if __name__ == "__main__":
    result = dag.run(debug=True)
    print(result.trace.summary())
    print()
    if result.success:
        print(result.state.get("report", ""))
    else:
        print(f"Error: {result.error}")
