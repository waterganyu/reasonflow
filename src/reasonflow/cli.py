"""CLI for ReasonFlow — run pipelines, view traces, discover MCP tools."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
from dotenv import load_dotenv

from reasonflow.dag import TRACE_DIR

load_dotenv()


@click.group()
@click.version_option(version="0.1.0", prog_name="reasonflow")
def main():
    """ReasonFlow — SDK-first agent orchestration."""
    pass


@main.command()
@click.argument("dag_module")
@click.option("--input", "-i", "input_json", default="{}", help="JSON input for the DAG")
@click.option("--var", "-v", multiple=True, help="Key=value pairs (e.g. -v question='hello')")
@click.option("--debug", is_flag=True, help="Print each node's output as it executes")
def run(dag_module: str, input_json: str, var: tuple[str, ...], debug: bool):
    """Run a DAG pipeline.

    DAG_MODULE is a Python module path or file (e.g. examples.text_to_sql or ./pipeline.py)
    """
    inputs = json.loads(input_json)
    for v in var:
        key, _, value = v.partition("=")
        inputs[key] = value

    dag = _load_dag(dag_module)
    if debug:
        dag.debug = True
    result = dag.run(**inputs)

    if result.success:
        click.echo(result.trace.summary())
        click.echo()
        # Print final state (excluding internal keys)
        output = {k: v for k, v in result.state.items() if not k.startswith("_")}
        click.echo(json.dumps(output, indent=2, default=str))
    else:
        click.echo(f"ERROR: {result.error}", err=True)
        click.echo(result.trace.summary())
        sys.exit(1)


@main.command()
@click.option("--last", is_flag=True, help="Show the most recent trace")
@click.option("--dag", "dag_name", default=None, help="Filter by DAG name")
@click.option("--run-id", default=None, help="Show a specific run")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def trace(last: bool, dag_name: str | None, run_id: str | None, as_json: bool):
    """View execution traces."""
    if not TRACE_DIR.exists():
        click.echo("No traces found. Run a pipeline first.")
        return

    traces = sorted(TRACE_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)
    if dag_name:
        traces = [t for t in traces if t.name.startswith(dag_name)]
    if run_id:
        traces = [t for t in traces if run_id in t.name]

    if not traces:
        click.echo("No matching traces found.")
        return

    if last:
        traces = [traces[-1]]

    for trace_path in traces:
        data = json.loads(trace_path.read_text())
        if as_json:
            click.echo(json.dumps(data, indent=2))
        else:
            _print_trace_summary(data)
        click.echo()


@main.command("mcp")
@click.argument("subcommand")
@click.argument("server", default="")
def mcp_cmd(subcommand: str, server: str):
    """MCP tools — discover available tools on an MCP server.

    Usage: reasonflow mcp discover postgres://localhost:5432/mydb
    """
    if subcommand == "discover":
        if not server:
            click.echo("Usage: reasonflow mcp discover <server-url>", err=True)
            sys.exit(1)
        _discover_mcp(server)
    else:
        click.echo(f"Unknown MCP subcommand: {subcommand}", err=True)
        sys.exit(1)


def _load_dag(module_path: str):
    """Load a DAG from a Python module."""
    import importlib
    import importlib.util

    if module_path.endswith(".py") or "/" in module_path or "\\" in module_path:
        # File path
        path = Path(module_path).resolve()
        spec = importlib.util.spec_from_file_location("_dag_module", path)
        if not spec or not spec.loader:
            click.echo(f"Cannot load: {module_path}", err=True)
            sys.exit(1)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    else:
        # Module path
        mod = importlib.import_module(module_path)

    # Find the DAG object
    from reasonflow.dag import DAG
    dags = [v for v in vars(mod).values() if isinstance(v, DAG)]
    if not dags:
        click.echo(f"No DAG found in {module_path}", err=True)
        sys.exit(1)
    return dags[0]


def _print_trace_summary(data: dict):
    """Print a human-readable trace summary."""
    click.echo(f"DAG: {data['dag_name']} (run: {data['run_id']})")
    click.echo(
        f"Total: {data['total_duration_ms']}ms | {data['total_cost']} | "
        f"{data['total_tokens']['input']}+{data['total_tokens']['output']} tokens"
    )
    click.echo()
    click.echo(f"{'Node':<25} {'Type':<12} {'Duration':>10} {'Cost':>10} {'Tokens':>12} {'Status':>8}")
    click.echo("-" * 80)
    for s in data["spans"]:
        status = "ERROR" if s.get("error") else "OK"
        tokens = f"{s['tokens_in']}+{s['tokens_out']}"
        click.echo(
            f"{s['node_name']:<25} {s['node_type']:<12} {s['duration_ms']:>8.0f}ms "
            f"${s['cost']:>8.4f} {tokens:>12} {status:>8}"
        )


def _discover_mcp(server: str):
    """Discover tools on an MCP server."""
    import asyncio

    async def _discover():
        from reasonflow.mcp_client import MCPClient
        client = MCPClient(server)
        await client.connect()
        tools = await client.list_tools()
        await client.close()
        return tools

    try:
        tools = asyncio.run(_discover())
        click.echo(f"MCP Server: {server}")
        click.echo(f"Tools found: {len(tools)}")
        click.echo()
        for tool in tools:
            click.echo(f"  {tool['name']}")
            if tool.get("description"):
                click.echo(f"    {tool['description']}")
    except Exception as e:
        click.echo(f"Error connecting to MCP server: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
