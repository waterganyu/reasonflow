"""Health check — parallel system checks with decision routing.

This shows:
- parallel() for concurrent system checks
- DecisionNode for conditional routing
- CodeNode generating alerts based on health status

Run with:
    reasonflow run examples/health_check.py
"""

import shutil
import subprocess
import os

from reasonflow import DAG, CodeNode, DecisionNode, parallel


@CodeNode
def check_disk(state):
    """Check disk usage."""
    total, used, free = shutil.disk_usage("/")
    pct_used = round(used / total * 100, 1)
    return {
        "disk_total_gb": round(total / (1024 ** 3), 1),
        "disk_used_gb": round(used / (1024 ** 3), 1),
        "disk_free_gb": round(free / (1024 ** 3), 1),
        "disk_pct_used": pct_used,
        "disk_status": "critical" if pct_used > 90 else "warning" if pct_used > 75 else "ok",
    }


@CodeNode
def check_memory(state):
    """Check memory usage via vm_stat (macOS) or /proc/meminfo (Linux)."""
    try:
        result = subprocess.run(["vm_stat"], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.splitlines()
            stats = {}
            for line in lines[1:]:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip().rstrip(".")
                    try:
                        stats[key] = int(val)
                    except ValueError:
                        pass

            page_size = 16384  # Apple Silicon default
            free_pages = stats.get("Pages free", 0) + stats.get("Pages speculative", 0)
            active = stats.get("Pages active", 0)
            wired = stats.get("Pages wired down", 0)
            total_est = free_pages + active + wired + stats.get("Pages inactive", 0)
            pct_used = round((active + wired) / max(total_est, 1) * 100, 1)

            return {
                "mem_total_gb": round(total_est * page_size / (1024 ** 3), 1),
                "mem_pct_used": pct_used,
                "mem_status": "critical" if pct_used > 90 else "warning" if pct_used > 75 else "ok",
            }
    except FileNotFoundError:
        pass

    return {"mem_total_gb": 0, "mem_pct_used": 0, "mem_status": "unknown"}


@CodeNode
def check_load(state):
    """Check system load average."""
    load1, load5, load15 = os.getloadavg()
    cpu_count = os.cpu_count() or 1
    load_ratio = load1 / cpu_count

    return {
        "load_1m": round(load1, 2),
        "load_5m": round(load5, 2),
        "load_15m": round(load15, 2),
        "cpu_count": cpu_count,
        "load_ratio": round(load_ratio, 2),
        "load_status": "critical" if load_ratio > 2 else "warning" if load_ratio > 1 else "ok",
    }


@DecisionNode
def evaluate_health(state):
    """Route based on overall health status."""
    statuses = [
        state.get("disk_status", "ok"),
        state.get("mem_status", "ok"),
        state.get("load_status", "ok"),
    ]

    if "critical" in statuses:
        return "generate_alert"
    if "warning" in statuses:
        return "generate_alert"
    return "generate_report"


@CodeNode
def generate_alert(state):
    """Generate an alert for unhealthy status."""
    issues = []
    if state.get("disk_status") in ("critical", "warning"):
        issues.append(f"Disk: {state['disk_pct_used']}% used ({state['disk_free_gb']}GB free)")
    if state.get("mem_status") in ("critical", "warning"):
        issues.append(f"Memory: {state['mem_pct_used']}% used")
    if state.get("load_status") in ("critical", "warning"):
        issues.append(f"Load: {state['load_1m']} (ratio: {state['load_ratio']}x on {state['cpu_count']} cores)")

    severity = "CRITICAL" if any(
        state.get(k) == "critical" for k in ("disk_status", "mem_status", "load_status")
    ) else "WARNING"

    return {
        "alert_severity": severity,
        "alert_issues": issues,
        "alert_message": f"[{severity}] System health alert: {'; '.join(issues)}",
    }


@CodeNode
def generate_report(state):
    """Generate an all-clear report."""
    return {
        "alert_severity": "OK",
        "alert_issues": [],
        "alert_message": (
            f"System healthy — "
            f"disk {state.get('disk_pct_used', '?')}%, "
            f"mem {state.get('mem_pct_used', '?')}%, "
            f"load {state.get('load_1m', '?')}"
        ),
    }


# ── Build the DAG ───────────────────────────────────────

dag = DAG("health-check")

dag.connect(
    parallel(check_disk, check_memory, check_load)
    >> evaluate_health
    >> generate_alert
)
dag.connect(evaluate_health >> generate_report)


if __name__ == "__main__":
    result = dag.run(debug=True)
    print(result.trace.summary())
    print()
    if result.success:
        severity = result.state.get("alert_severity", "?")
        print(f"Status: {severity}")
        print(result.state.get("alert_message", ""))
        if result.state.get("alert_issues"):
            print("\nIssues:")
            for issue in result.state["alert_issues"]:
                print(f"  - {issue}")
    else:
        print(f"Error: {result.error}")
