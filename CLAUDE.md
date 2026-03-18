# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Development

```bash
# Install with all optional deps (MCP support + dev tools)
pip install -e ".[all]"

# Run full test suite
python -m pytest tests/ -v

# Run a single test file
python -m pytest tests/test_dag.py -v

# Run a single test
python -m pytest tests/test_dag.py::test_simple_chain -v

# CLI usage
reasonflow run examples/research_pipeline.py -v topic="AI safety"
reasonflow run examples/multi_model_debate.py -v question="Should we adopt microservices?"
reasonflow run examples/health_check.py --debug
reasonflow trace --last
reasonflow mcp discover <server-url>
```

Python >=3.10 required. Build backend is hatchling. Tests use pytest with `asyncio_mode = "auto"` (no need for `@pytest.mark.asyncio`).

### Environment setup

Copy `.env.example` to `.env` and add API keys. LLMs are called via litellm, which reads keys from env vars:
- Cloud: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`
- Local (Ollama): no key needed, use model names like `ollama/llama3`

## Architecture

ReasonFlow is an SDK-first agent orchestration framework. Pipelines are built as DAGs of nodes connected with the `>>` operator.

### Execution flow

`DAG.run(**inputs)` → `SharedState` initialized → nodes execute sequentially (or in parallel via `parallel()`) → each node receives a frozen state copy, returns a dict merged back into shared state → `DAGResult` returned with final state, trace, cost, and token totals.

Traces are automatically saved to `~/.reasonflow/traces/`.

### Core modules (`src/reasonflow/`)

- **dag.py** — `DAG` class orchestrates execution: chain traversal, budget checks before each node, retry wrapping, span recording, DecisionNode routing (jumps to named nodes in the chain). Supports `debug=True` to print each node's output.
- **nodes/base.py** — `BaseNode` (abstract), `NodeChain` (built via `>>`), `ParallelGroup` (built via `parallel()`). All node types inherit `BaseNode`. Nodes have `.optional()` and `.debug()` modifiers.
- **nodes/llm.py** — `LLMNode` decorator. Two modes: *auto* (docstring becomes system prompt, state auto-injected) and *custom* (function receives `NodeContext` for explicit `ctx.llm.complete()` calls). Uses litellm under the hood. Tracks `_last_usage` for cost. Auto-mode detection uses `_is_trivial_body()` in base.py.
- **nodes/code.py** — `CodeNode` decorator. Wraps sync/async Python functions. No cost tracking.
- **nodes/decision.py** — `DecisionNode` decorator. Function returns `"next"` or a node name string; DAG engine jumps accordingly.
- **nodes/mcp.py** — `MCPNode` decorator + `MCPServer` config. Connects to MCP servers, discovers tools, invokes them.
- **state.py** — `SharedState`: dict-like container with `merge()`, `snapshot()` (history per node), `frozen_copy()` (deep copy for safe node input).
- **cost.py** — `CostTracker` with model pricing table, budget enforcement modes ("warn"/"degrade"/"halt"), `parse_budget()` for "$X.XX" strings.
- **retry.py** — `RetryPolicy` dataclass, `retry_async()` with exponential backoff + jitter, `NodeExecutionError` with typed errors.
- **trace.py** — `Span` (per-node timing/tokens/cost/error), `Trace` (collection of spans, JSON serialization).
- **context.py** — `NodeContext` combining `LLMContext` and `MCPContext`, passed to custom-mode LLMNode/MCPNode functions.
- **cli.py** — Click-based CLI: `run` (with `--debug`), `trace`, `mcp discover`.

### Examples (`examples/`)

13 runnable examples covering: LLM pipelines (email_drafter, code_reviewer, git_changelog, csv_analyzer, log_analyzer, web_scraper_summarizer, run_and_analyze), parallel execution (multi_model_debate, research_pipeline, health_check, docker_cleanup), DecisionNode routing (health_check, docker_cleanup, test_runner), and pure CodeNode chains (process_manager). Most generate sample data when run without arguments.

### Key patterns

- Nodes are created via decorators (`@CodeNode`, `@LLMNode(model=...)`, etc.) that wrap functions into `BaseNode` subclasses.
- `>>` operator on nodes builds a `NodeChain`; `parallel(a, b, c)` creates a `ParallelGroup` within a chain.
- `DAG.run()` is sync (wraps async internally); `DAG.run_async()` for native async usage.
- Budget checking happens *before* each node execution in `_execute_node`.
- DecisionNode routing works by searching the chain's items list for a node with the matching name and jumping to that index.
- Debug output: `DAG("name", debug=True)` or `node.debug()` for per-node, or `--debug` via CLI. Prints each node's output keys/values (truncated to 80 chars).
