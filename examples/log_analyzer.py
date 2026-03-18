"""Log analyzer — parse log files, extract errors, and categorize with LLM.

This shows:
- Reading and filtering log files in CodeNodes
- Pattern matching for error extraction
- LLMNode categorizing and prioritizing errors

Run with:
    reasonflow run examples/log_analyzer.py -v log_path="/var/log/system.log"
"""

import re
from datetime import datetime
from pathlib import Path

from reasonflow import DAG, LLMNode, CodeNode


@CodeNode
def read_logs(state):
    """Read log file and extract recent entries."""
    log_path = state.get("log_path", "/var/log/system.log")
    max_lines = state.get("max_lines", 500)
    path = Path(log_path)

    if not path.exists():
        # Generate sample logs for demo
        return _generate_sample_logs()

    lines = path.read_text().splitlines()
    recent = lines[-max_lines:] if len(lines) > max_lines else lines

    return {
        "log_lines": recent,
        "total_lines": len(lines),
        "lines_read": len(recent),
        "log_source": str(path),
    }


def _generate_sample_logs():
    """Generate sample log entries for demo."""
    logs = [
        "2025-03-05 10:01:23 INFO  [main] Application started successfully",
        "2025-03-05 10:01:24 INFO  [db] Connected to PostgreSQL at localhost:5432",
        "2025-03-05 10:02:15 WARN  [http] Slow query: GET /api/users took 2340ms",
        "2025-03-05 10:02:18 ERROR [http] Connection timeout: upstream server api.example.com:8080",
        "2025-03-05 10:03:01 INFO  [worker] Processing batch job #4521",
        "2025-03-05 10:03:45 ERROR [db] Deadlock detected in transaction 8832",
        "2025-03-05 10:03:45 ERROR [db] Rolling back transaction 8832",
        "2025-03-05 10:04:12 WARN  [mem] Heap usage at 78% (1.2GB / 1.5GB)",
        "2025-03-05 10:05:00 INFO  [scheduler] Cron job 'cleanup' started",
        "2025-03-05 10:05:33 ERROR [http] 500 Internal Server Error: /api/orders/create",
        "2025-03-05 10:05:33 ERROR [http] NullPointerException at OrderService.java:142",
        "2025-03-05 10:06:01 WARN  [auth] Failed login attempt for user 'admin' from 192.168.1.50",
        "2025-03-05 10:06:02 WARN  [auth] Failed login attempt for user 'admin' from 192.168.1.50",
        "2025-03-05 10:06:03 WARN  [auth] Failed login attempt for user 'admin' from 192.168.1.50",
        "2025-03-05 10:07:15 ERROR [disk] Write failed: /data/cache — No space left on device",
        "2025-03-05 10:08:00 INFO  [http] Health check OK — uptime 6h 23m",
    ]
    return {
        "log_lines": logs,
        "total_lines": len(logs),
        "lines_read": len(logs),
        "log_source": "(generated sample data)",
    }


@CodeNode
def extract_errors(state):
    """Filter log lines for errors and warnings."""
    lines = state.get("log_lines", [])

    errors = []
    warnings = []
    for line in lines:
        lower = line.lower()
        if "error" in lower or "exception" in lower or "fatal" in lower:
            errors.append(line)
        elif "warn" in lower:
            warnings.append(line)

    # Deduplicate similar errors
    unique_errors = list(dict.fromkeys(errors))

    return {
        "errors": unique_errors,
        "warnings": warnings,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "unique_error_count": len(unique_errors),
    }


@LLMNode(model="claude-haiku", budget="$0.05")
def categorize_errors(state):
    """You are a DevOps engineer analyzing application logs.

    Log source: {log_source}
    Total lines: {total_lines}
    Errors found: {error_count} ({unique_error_count} unique)
    Warnings found: {warning_count}

    Errors:
    {errors}

    Warnings:
    {warnings}

    Categorize each error by:
    1. Root cause category (network, database, disk, application, security)
    2. Severity (critical, high, medium, low)
    3. Recommended action

    Return as JSON with keys:
    - "categories" (list of {{"error": str, "category": str, "severity": str, "action": str}})
    - "most_urgent" (string — the single most important issue to fix first)
    - "overall_health" (one of: "healthy", "degraded", "critical")
    """
    pass


# ── Build the DAG ───────────────────────────────────────

dag = DAG("log-analyzer", budget="$0.10", debug=True)

dag.connect(read_logs >> extract_errors >> categorize_errors)


if __name__ == "__main__":
    result = dag.run()
    print(result.trace.summary())
    print()
    if result.success:
        print(f"Source: {result.state.get('log_source')}")
        print(f"Lines: {result.state.get('total_lines')}")
        print(f"Errors: {result.state.get('error_count')} | Warnings: {result.state.get('warning_count')}")
        print(f"\nOverall health: {result.state.get('overall_health', 'unknown')}")
        print(f"Most urgent: {result.state.get('most_urgent', 'N/A')}")
        print("\nCategories:")
        for cat in result.state.get("categories", []):
            print(f"  [{cat.get('severity', '?')}] {cat.get('category', '?')}: {cat.get('error', '?')}")
            print(f"    Action: {cat.get('action', '?')}")
    else:
        print(f"Error: {result.error}")
