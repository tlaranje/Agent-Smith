*This project has been created as part of the 42 curriculum by joesanto, tlaranje.*

# Agent Smith

## Description

Agent Smith is an experimental coding-agent project that combines large-language-model prompting, a Docker-based sandbox, and MCP-style tool access to solve tasks from  two benchmarks:

- MBPP-style Python programming tasks
- SWE-bench-style repository bug-fixing tasks

The system is designed to let an LLM read a task, write code or a patch, execute it in a restricted environment, inspect the results, and iterate until the solution passes validation. The project focuses on three ideas:

1. A safe execution loop for agent-generated code
2. A modular tool layer for testing and repository inspection
3. Two benchmark pathways for short coding tasks and real-world bug fixes

## System architecture

The repository is organized around four main layers:

- Agent layer: the MBPP and SWE-bench agents in the student/src/agent package orchestrate the reasoning loop, prompt construction, and retry strategy.
- Sandbox layer: the Docker-based sandbox in student/src/sandbox provides isolated execution, resource limits, and a restricted Python namespace.
- Tool layer: MCP servers in mcp_tools_mbpp.py and mcp_tools_swebench.py expose tools such as running tests, reading files, editing files, and searching code.
- Evaluation layer: the moulinette package consumes task definitions and validates generated solutions against the target benchmark.

## Agent loop explanation

The agent follows a simple feedback loop:

1. The task description and relevant tests are loaded.
2. The model generates Python code or a patch.
3. The code is executed inside the sandbox.
4. The sandbox output is returned to the model as structured feedback.
5. The model can retry, refine, or submit a final answer.

For MBPP tasks, success is typically reached when the submitted solution passes the provided tests. For SWE-bench tasks, the agent uses repository inspection tools to change the target code and then relies on the evaluation script to validate the patch.

## Sandbox design

The sandbox is implemented with Docker and is meant to be stricter than a normal local environment:

- Each execution runs inside an isolated container.
- Import usage is filtered through an allowlist.
- Dangerous constructs such as eval/exec are rejected.
- Execution time and memory are capped.
- The container exposes a small helper interface so the agent can write code, run tests, and produce a final result without arbitrary filesystem access.

This makes it suitable for evaluating untrusted agent-generated code while still allowing realistic task execution.

## Tool implementation details

The project uses MCP servers to provide a consistent interface between the agent and the sandbox:

- MBPP tools: run tests and report success or failure for small Python tasks.
- SWE-bench tools: read files, edit files, list files, search the repository, run commands, and retrieve a git patch.

The tool layer is intentionally narrow and explicit so the agent can interact with the environment without being given unrestricted shell access.

## Instructions

### Prerequisites

- Python 3.10+
- Docker with the Docker daemon available
- uv for dependency management
- API credentials in the environment for at least one supported provider (Gemini, Groq, OpenRouter, Cohere, or Mistral)

### Installation

```bash
uv sync
```

### Environment setup

Set the relevant API keys before running the agents, for example:

```bash
export GEMINI_API_KEY="your-key"
```

### Running the MBPP agent

```bash
cd student
uv run python -m agent_mbpp \
  --task-file ../data/input/mbpp_task.json \
  --output ../data/output/mbpp_task_solution.json \
  --model-name <model_name> \
  --provider-url <provider_url>
```

### Running the SWE-bench agent

```bash
cd student
uv run python -m agent_swebench \
  --task-file ../data/input/swebench_task.json \
  --output ../data/output/swebench_task_solution.json \
  --model-name <model_name> \
  --provider-url <provider_url>
```

## Benchmark results and analysis

This repository is prepared to benchmark two complementary regimes:

- MBPP for compact function-level synthesis
- SWE-bench for repository-level bug fixing

The current workspace includes sample task fixtures under data/input and a validation pipeline through the moulinette package. In practice, the expected behavior is:

- MBPP runs are faster and more deterministic because the agent only needs to produce a function-level solution.
- SWE-bench runs are more demanding because the agent must reason about repository structure, locate the relevant code, and apply a minimal patch.
- The retry loop improves robustness to syntax errors and incorrect assumptions, but performance still depends heavily on the quality of the underlying model and the quality of the tool feedback.

The benchmark report template is intended to summarize the results produced by the evaluation harness once runs are executed.

## Resources

### References

- https://github.com/0xS4cha/Agent-Smith
- https://modelcontextprotocol.io/docs/getting-started/intro

### AI usage

AI was used in three main places in this project:

- Prompt design for the MBPP and SWE-bench agents, including the system prompt and the observation feedback loop.
- API abstraction and provider fallback logic so the same agent can target multiple LLM backends.
- Tool-assisted problem solving, where the model uses MCP tools to inspect code, run tests, and iterate until the task is solved.

The AI component is therefore central to the agent loop, but the sandbox and evaluation harness remain responsible for enforcing execution safety and measuring correctness.
