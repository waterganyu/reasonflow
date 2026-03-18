"""Git changelog — generate release notes from git log.

This shows:
- Running git commands via subprocess in CodeNodes
- Passing structured commit data to an LLMNode
- Generating formatted release notes

Run with:
    reasonflow run examples/git_changelog.py -v repo_path="."
"""

import subprocess
from pathlib import Path

from reasonflow import DAG, LLMNode, CodeNode


@CodeNode
def get_commits(state):
    """Fetch recent git commits from the repo."""
    repo = state.get("repo_path", ".")
    count = state.get("commit_count", 20)

    result = subprocess.run(
        ["git", "-C", repo, "log", f"-{count}", "--pretty=format:%h|%an|%s|%ad", "--date=short"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return {"commits": [], "error": result.stderr.strip()}

    commits = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("|", 3)
        if len(parts) == 4:
            commits.append({
                "hash": parts[0],
                "author": parts[1],
                "message": parts[2],
                "date": parts[3],
            })

    return {"commits": commits, "commit_count": len(commits)}


@CodeNode
def get_tags(state):
    """Get recent tags to identify version boundaries."""
    repo = state.get("repo_path", ".")

    result = subprocess.run(
        ["git", "-C", repo, "tag", "--sort=-creatordate", "-l"],
        capture_output=True,
        text=True,
    )

    tags = result.stdout.strip().splitlines()[:5] if result.returncode == 0 else []
    return {"recent_tags": tags}


@LLMNode(model="claude-haiku", budget="$0.05")
def generate_changelog(state):
    """You are a technical writer. Generate clean release notes from these git commits.

    Commits:
    {commits}

    Recent tags: {recent_tags}

    Group commits by category (Features, Fixes, Refactoring, Docs, Other).
    Use clear, user-facing language. Skip merge commits.
    Return as JSON with keys: "version" (suggested), "date", "sections" (dict of category -> list of changes).
    """
    pass


# ── Build the DAG ───────────────────────────────────────

dag = DAG("git-changelog", budget="$0.10", debug=True)

dag.connect(get_commits >> get_tags >> generate_changelog)


if __name__ == "__main__":
    result = dag.run(repo_path=".")
    print(result.trace.summary())
    print()
    if result.success:
        print(f"Analyzed {result.state.get('commit_count', 0)} commits")
        sections = result.state.get("sections", {})
        for category, changes in sections.items():
            print(f"\n## {category}")
            for change in changes:
                print(f"  - {change}")
    else:
        print(f"Error: {result.error}")
