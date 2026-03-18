# ReasonFlow

SDK-first, MCP-native agent orchestration framework.

```python
from reasonflow import DAG, LLMNode, CodeNode, DecisionNode, parallel

@CodeNode
def step1(state):
    return {"greeting": f"Hello, {state['name']}!"}

@CodeNode
def step2(state):
    return {"upper": state["greeting"].upper()}

dag = DAG("hello")
dag.connect(step1 >> step2)
result = dag.run(name="World")
print(result["upper"])  # HELLO, WORLD!
```

## Install

```bash
pip install reasonflow
```

## Setup

Copy `.env.example` to `.env` and add your API keys:

```bash
cp .env.example .env
```

Supports cloud providers (OpenAI, Anthropic, Google) and local models via Ollama — use model names like `ollama/llama3` in `@LLMNode(model=...)`.

## Features

- 4 node types: `LLMNode`, `MCPNode`, `CodeNode`, `DecisionNode`
- `>>` operator for DAG construction
- `parallel()` for concurrent branches
- Automatic cost/token tracking per node
- Built-in retries with error-type awareness
- MCP-native tool integration
- JSON execution traces
- CLI: `reasonflow run`, `reasonflow trace`
- Debug mode: `--debug` flag, `DAG(debug=True)`, or per-node `.debug()`

## Examples

```bash
# Research pipeline — parallel branches + LLM synthesis
reasonflow run examples/research_pipeline.py -v topic="AI safety"

# Multi-model debate — 3 LLMs argue in parallel, judge synthesizes
reasonflow run examples/multi_model_debate.py -v question="Should we adopt microservices?"

# Email drafter — bullets → LLM draft → LLM review → save
reasonflow run examples/email_drafter.py -v recipient="Engineering" -v subject="Q1 Update"

# Code reviewer — git diff → LLM code review → saved report
reasonflow run examples/code_reviewer.py -v repo_path="."

# CSV analyzer — parse CSV + compute stats → LLM insights
reasonflow run examples/csv_analyzer.py -v csv_path="data.csv"

# Git changelog — git log → LLM-generated release notes
reasonflow run examples/git_changelog.py -v repo_path="."

# Web scraper — fetch URL → strip HTML → LLM summary
reasonflow run examples/web_scraper_summarizer.py -v url="https://example.com"

# Log analyzer — read logs → grep errors → LLM categorize
reasonflow run examples/log_analyzer.py -v log_path="/var/log/system.log"

# Health check — parallel system checks → DecisionNode → alert/report
reasonflow run examples/health_check.py

# Test runner — pytest → DecisionNode → LLM failure analysis
reasonflow run examples/test_runner.py -v test_path="tests/"

# Process manager — ps/grep/kill via CodeNodes
reasonflow run examples/process_manager.py

# Run & analyze — execute a Python script → LLM analyzes output
reasonflow run examples/run_and_analyze.py

# Docker cleanup — parallel inventory → decide → prune (dry-run default)
reasonflow run examples/docker_cleanup.py

# Debug mode — see each node's output
reasonflow run examples/process_manager.py --debug
```
