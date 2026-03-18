"""Docker cleanup — inventory containers and images, decide what to prune.

This shows:
- parallel() for concurrent Docker inventory
- DecisionNode routing based on waste found
- CodeNode executing cleanup (dry-run by default)

Run with:
    reasonflow run examples/docker_cleanup.py
    reasonflow run examples/docker_cleanup.py -v dry_run="false"
"""

import json
import subprocess

from reasonflow import DAG, CodeNode, DecisionNode, parallel


@CodeNode
def list_containers(state):
    """List all containers including stopped ones."""
    result = subprocess.run(
        ["docker", "ps", "-a", "--format", "{{json .}}"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return {
            "containers": [],
            "container_error": result.stderr.strip() or "Docker not available",
        }

    containers = []
    for line in result.stdout.strip().splitlines():
        if line:
            try:
                containers.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    stopped = [c for c in containers if c.get("State") != "running"]
    running = [c for c in containers if c.get("State") == "running"]

    return {
        "containers_total": len(containers),
        "containers_running": len(running),
        "containers_stopped": len(stopped),
        "stopped_containers": [
            {"id": c.get("ID", ""), "name": c.get("Names", ""), "image": c.get("Image", ""), "status": c.get("Status", "")}
            for c in stopped
        ],
    }


@CodeNode
def list_images(state):
    """List all Docker images and find dangling ones."""
    result = subprocess.run(
        ["docker", "images", "--format", "{{json .}}"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return {
            "images": [],
            "image_error": result.stderr.strip() or "Docker not available",
        }

    images = []
    for line in result.stdout.strip().splitlines():
        if line:
            try:
                images.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    dangling = [i for i in images if i.get("Repository") == "<none>"]
    total_size = sum(_parse_size(i.get("Size", "0B")) for i in images)
    dangling_size = sum(_parse_size(i.get("Size", "0B")) for i in dangling)

    return {
        "images_total": len(images),
        "images_dangling": len(dangling),
        "images_total_size_mb": round(total_size / (1024 * 1024), 1),
        "images_dangling_size_mb": round(dangling_size / (1024 * 1024), 1),
        "dangling_images": [
            {"id": i.get("ID", ""), "size": i.get("Size", ""), "created": i.get("CreatedSince", "")}
            for i in dangling
        ],
    }


def _parse_size(size_str: str) -> int:
    """Parse Docker size strings like '1.5GB' into bytes."""
    import re
    match = re.match(r"([\d.]+)\s*(B|KB|MB|GB|TB)", size_str, re.IGNORECASE)
    if not match:
        return 0
    value = float(match.group(1))
    unit = match.group(2).upper()
    multipliers = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
    return int(value * multipliers.get(unit, 1))


@CodeNode
def check_volumes(state):
    """Check for unused Docker volumes."""
    result = subprocess.run(
        ["docker", "volume", "ls", "--format", "{{json .}}"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return {"volumes_total": 0, "volume_error": result.stderr.strip()}

    volumes = []
    for line in result.stdout.strip().splitlines():
        if line:
            try:
                volumes.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    # Check dangling volumes
    dangling_result = subprocess.run(
        ["docker", "volume", "ls", "-f", "dangling=true", "--format", "{{json .}}"],
        capture_output=True,
        text=True,
    )

    dangling = []
    if dangling_result.returncode == 0:
        for line in dangling_result.stdout.strip().splitlines():
            if line:
                try:
                    dangling.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    return {
        "volumes_total": len(volumes),
        "volumes_dangling": len(dangling),
    }


@DecisionNode
def evaluate_waste(state):
    """Decide if cleanup is needed."""
    stopped = state.get("containers_stopped", 0)
    dangling_images = state.get("images_dangling", 0)
    dangling_volumes = state.get("volumes_dangling", 0)

    # Any errors mean Docker isn't available
    if state.get("container_error") or state.get("image_error"):
        return "report_status"

    waste = stopped + dangling_images + dangling_volumes
    if waste > 0:
        return "run_cleanup"
    return "report_status"


@CodeNode
def run_cleanup(state):
    """Execute Docker cleanup (dry-run by default)."""
    dry_run = str(state.get("dry_run", "true")).lower() != "false"
    actions = []

    stopped = state.get("containers_stopped", 0)
    dangling_img = state.get("images_dangling", 0)
    dangling_vol = state.get("volumes_dangling", 0)

    if dry_run:
        if stopped:
            actions.append(f"Would remove {stopped} stopped container(s)")
        if dangling_img:
            actions.append(f"Would remove {dangling_img} dangling image(s) ({state.get('images_dangling_size_mb', 0)}MB)")
        if dangling_vol:
            actions.append(f"Would remove {dangling_vol} dangling volume(s)")
        return {"cleanup_actions": actions, "cleanup_mode": "dry-run"}

    # Actual cleanup
    if stopped:
        result = subprocess.run(["docker", "container", "prune", "-f"], capture_output=True, text=True)
        actions.append(f"Removed stopped containers: {result.stdout.strip()}")

    if dangling_img:
        result = subprocess.run(["docker", "image", "prune", "-f"], capture_output=True, text=True)
        actions.append(f"Removed dangling images: {result.stdout.strip()}")

    if dangling_vol:
        result = subprocess.run(["docker", "volume", "prune", "-f"], capture_output=True, text=True)
        actions.append(f"Removed dangling volumes: {result.stdout.strip()}")

    return {"cleanup_actions": actions, "cleanup_mode": "executed"}


@CodeNode
def report_status(state):
    """Generate a status report without cleanup."""
    errors = []
    if state.get("container_error"):
        errors.append(f"Containers: {state['container_error']}")
    if state.get("image_error"):
        errors.append(f"Images: {state['image_error']}")

    return {
        "cleanup_actions": errors or ["No cleanup needed — everything looks clean"],
        "cleanup_mode": "skipped",
    }


# ── Build the DAG ───────────────────────────────────────

dag = DAG("docker-cleanup")

dag.connect(
    parallel(list_containers, list_images, check_volumes)
    >> evaluate_waste
    >> run_cleanup
)
dag.connect(evaluate_waste >> report_status)


if __name__ == "__main__":
    result = dag.run(debug=True)
    print(result.trace.summary())
    print()
    if result.success:
        print(f"Containers: {result.state.get('containers_total', 0)} total, "
              f"{result.state.get('containers_stopped', 0)} stopped")
        print(f"Images: {result.state.get('images_total', 0)} total, "
              f"{result.state.get('images_dangling', 0)} dangling "
              f"({result.state.get('images_dangling_size_mb', 0)}MB)")
        print(f"Volumes: {result.state.get('volumes_total', 0)} total, "
              f"{result.state.get('volumes_dangling', 0)} dangling")
        print(f"\nMode: {result.state.get('cleanup_mode', '?')}")
        for action in result.state.get("cleanup_actions", []):
            print(f"  - {action}")
    else:
        print(f"Error: {result.error}")
