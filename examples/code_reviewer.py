"""Code reviewer — review git diff with an LLM.

This shows:
- Capturing git diff output via subprocess
- LLMNode performing code review
- Saving review results to a file

Run with:
    reasonflow run examples/code_reviewer.py -v repo_path="."
"""

import subprocess
from datetime import datetime
from pathlib import Path

from reasonflow import DAG, LLMNode, CodeNode


@CodeNode
def get_diff(state):
    """Get staged or unstaged changes from the repo."""
    repo = state.get("repo_path", ".")

    # Try staged first, fall back to unstaged
    result = subprocess.run(
        ["git", "-C", repo, "diff", "--cached"],
        capture_output=True,
        text=True,
    )

    diff = result.stdout.strip()
    diff_type = "staged"

    if not diff:
        result = subprocess.run(
            ["git", "-C", repo, "diff"],
            capture_output=True,
            text=True,
        )
        diff = result.stdout.strip()
        diff_type = "unstaged"

    if not diff:
        result = subprocess.run(
            ["git", "-C", repo, "diff", "HEAD~1"],
            capture_output=True,
            text=True,
        )
        diff = result.stdout.strip()
        diff_type = "last commit"

    # Truncate very large diffs
    max_chars = 8000
    truncated = len(diff) > max_chars
    if truncated:
        diff = diff[:max_chars] + "\n... (truncated)"

    return {"diff": diff, "diff_type": diff_type, "truncated": truncated}


@LLMNode(model="claude-sonnet", budget="$0.10")
def review_code(state):
    """You are a senior code reviewer. Review this diff carefully.

    Diff type: {diff_type}

    ```diff
    {diff}
    ```

    Provide a thorough review covering:
    1. Potential bugs or logic errors
    2. Security concerns
    3. Performance issues
    4. Style and readability
    5. Suggestions for improvement

    Return as JSON with keys:
    - "severity" (one of: "clean", "minor", "major", "critical")
    - "issues" (list of {{"category": str, "description": str, "line_hint": str}})
    - "summary" (one sentence overall assessment)
    """
    pass


@CodeNode
def save_review(state):
    """Save the review to a file."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    review_dir = Path.home() / ".reasonflow" / "reviews"
    review_dir.mkdir(parents=True, exist_ok=True)
    review_path = review_dir / f"code_review_{timestamp}.txt"

    lines = [
        f"Code Review — {timestamp}",
        f"Diff type: {state.get('diff_type', 'unknown')}",
        f"Severity: {state.get('severity', 'unknown')}",
        "",
        f"Summary: {state.get('summary', 'N/A')}",
        "",
        "Issues:",
    ]

    for issue in state.get("issues", []):
        lines.append(f"  [{issue.get('category', '?')}] {issue.get('description', '')}")
        if issue.get("line_hint"):
            lines.append(f"    Near: {issue['line_hint']}")

    review = "\n".join(lines) + "\n"
    review_path.write_text(review)

    return {"review_text": review, "review_path": str(review_path)}


# ── Build the DAG ───────────────────────────────────────

dag = DAG("code-reviewer", budget="$0.15", debug=True)

dag.connect(get_diff >> review_code >> save_review)


if __name__ == "__main__":
    result = dag.run(repo_path=".")
    print(result.trace.summary())
    print()
    if result.success:
        print(result.state["review_text"])
        print(f"Review saved to: {result.state['review_path']}")
    else:
        print(f"Error: {result.error}")
