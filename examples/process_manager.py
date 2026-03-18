"""Process manager — demonstrates bash command execution via CodeNodes.

This shows:
- Running shell commands (ps, grep, kill) from CodeNodes
- Chaining results through pipeline state
- Saving an action report to file

Run with:
    reasonflow run examples/process_manager.py
"""

import subprocess
from datetime import datetime
from pathlib import Path

from reasonflow import DAG, CodeNode


@CodeNode
def list_processes(state):
    """Run ps aux and capture all running processes."""
    result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
    return {
        "ps_output": result.stdout,
        "ps_line_count": len(result.stdout.strip().splitlines()),
    }


@CodeNode
def find_whatsapp(state):
    """Grep ps output for WhatsApp processes."""
    lines = state.get("ps_output", "").splitlines()
    matches = [l for l in lines if "whatsapp" in l.lower()]
    pids = []
    for line in matches:
        parts = line.split()
        if len(parts) >= 2:
            pids.append(parts[1])
    return {
        "whatsapp_lines": matches,
        "whatsapp_pids": pids,
        "whatsapp_found": len(pids) > 0,
    }


@CodeNode
def kill_whatsapp(state):
    """Kill WhatsApp processes if any were found."""
    pids = state.get("whatsapp_pids", [])
    if not pids:
        return {"kill_results": [], "action": "skipped — WhatsApp not running"}

    results = []
    for pid in pids:
        proc = subprocess.run(["kill", pid], capture_output=True, text=True)
        results.append({
            "pid": pid,
            "success": proc.returncode == 0,
            "error": proc.stderr.strip() if proc.returncode != 0 else None,
        })
    killed = [r["pid"] for r in results if r["success"]]
    return {
        "kill_results": results,
        "action": f"killed {len(killed)} process(es)" if killed else "kill failed",
    }


@CodeNode
def save_report(state):
    """Save a report of everything that happened."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_dir = Path.home() / ".reasonflow" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"process_manager_{timestamp}.txt"

    lines = [
        f"Process Manager Report — {timestamp}",
        "=" * 50,
        "",
        f"Total processes scanned: {state.get('ps_line_count', 0)}",
        f"WhatsApp found: {state.get('whatsapp_found', False)}",
        f"WhatsApp PIDs: {state.get('whatsapp_pids', [])}",
        "",
        f"Action taken: {state.get('action', 'none')}",
        "",
    ]

    for result in state.get("kill_results", []):
        status = "killed" if result["success"] else f"failed: {result['error']}"
        lines.append(f"  PID {result['pid']}: {status}")

    if state.get("whatsapp_lines"):
        lines += ["", "Matched process lines:", ""]
        lines += [f"  {l}" for l in state["whatsapp_lines"]]

    report = "\n".join(lines) + "\n"
    report_path.write_text(report)

    return {"report": report, "report_path": str(report_path)}


# ── Build the DAG ───────────────────────────────────────

dag = DAG("process-manager")

dag.connect(
    list_processes >> find_whatsapp >> kill_whatsapp >> save_report
)


if __name__ == "__main__":
    result = dag.run(debug=True)
    print(result.trace.summary())
    print()
    print(result.state["report"])
    print(f"Report saved to: {result.state['report_path']}")
