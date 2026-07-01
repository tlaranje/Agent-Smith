from student.src.sandbox.sandbox_config import SandboxConfig
from student.src.sandbox.sandbox import Sandbox
from pathlib import Path
from rich import print
import subprocess
import argparse
import httpx
import shlex
import json
import time
import sys
import os


def discover_benchmark_from_template(template_path: str) -> str:
    if not template_path or not os.path.exists(template_path):
        return "MBPP"
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "test_list" in data or "task_id" in data:
            return "MBPP"
        if "instance_id" in data or "base_commit" in data:
            return "SWE_BENCH"
    except Exception:
        pass
    return "MBPP"


def load_sandbox_config(template_path: str) -> SandboxConfig:
    if not template_path or not os.path.exists(template_path):
        return SandboxConfig()
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        known_fields = set(SandboxConfig.model_fields.keys())
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return SandboxConfig(**filtered)
    except Exception as e:
        print(
            f"[yellow]Warning: could not load sandbox config from "
            f"{template_path} ({e}). Using defaults.[/yellow]"
        )
        return SandboxConfig()


def run_mcp_stdio(sandbox: Sandbox, mcp_command: str) -> None:
    sandbox.build("..")
    sandbox.start()

    root_path = Path(__file__).parent.parent.parent

    server_env = dict(os.environ)
    server_env["IS_MCP_SERVER"] = "1"
    server_env["DOCKER_CONTAINER_ID"] = sandbox.container.id

    tokens = shlex.split(mcp_command)
    if not tokens:
        raise ValueError("--mcp-stdio requires a non-empty command")

    resolved = []
    for tok in tokens:
        if tok.endswith(".py"):
            resolved.append(str(root_path / tok))
        else:
            resolved.append(tok)

    try:
        subprocess.run(resolved, env=server_env, check=True)
    finally:
        sandbox.stop()


def _wait_for_server(url: str, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            httpx.get(url, timeout=1.0)
            return
        except httpx.RequestError:
            time.sleep(0.3)
    raise httpx.RequestError(
        f"Server at {url} did not start within {timeout}s"
    )


def run_mcp_http(sandbox: Sandbox, url: str, task_file: str) -> None:
    sandbox.build("..")
    sandbox.start()

    server_env = dict(os.environ)
    server_env["IS_MCP_SERVER"] = "1"
    server_env["DOCKER_CONTAINER_ID"] = sandbox.container.id

    root_path = Path(__file__).parent.parent.parent
    server_script = root_path / "mcp_tools_mbpp.py"

    server_process = subprocess.Popen(
        [sys.executable, str(server_script), "--http", "--port", "8000"],
        env=server_env,
    )

    try:
        _wait_for_server(url, timeout=15.0)

        with open(task_file, "r", encoding="utf-8") as f:
            task_data = json.load(f)

        payload = {
            "docker_container_id": sandbox.container.id,
            "task": task_data,
        }

        response = httpx.post(f"{url}/initialize", json=payload, timeout=60.0)

        if response.status_code == 200:
            print("[green]Session initialized on MCP server.[/green]")
        else:
            print(f"[bold red]MCP Server Error:[/bold red] {response.text}")

    except httpx.RequestError as exc:
        raise httpx.RequestError(
            "[bold red]Network error connecting to "
            f"MCP server:[/bold red] {exc}"
        )
    finally:
        server_process.terminate()
        server_process.wait()
        sandbox.stop()


def run_interactive_cli(sandbox: Sandbox) -> None:
    try:
        sandbox.build("..")
        sandbox.start()
        sandbox.enter()
    finally:
        sandbox.stop()


def main() -> None:
    try:
        parser = argparse.ArgumentParser(description="Sandbox CLI")

        parser.add_argument("--mcp-stdio", metavar="COMMAND", default=None)
        parser.add_argument("--mcp-server", metavar="URL", default=None)

        parser.add_argument(
            "sandbox_template",
            nargs="?",
            default="data/input/mbpp_task.json",
            help="Path to sandbox_template.json (SandboxConfig) "
                 "or a task file used to infer the benchmark.",
        )

        args = parser.parse_args()

        benchmark = discover_benchmark_from_template(args.sandbox_template)
        sandbox_config = load_sandbox_config(args.sandbox_template)

        if benchmark == "MBPP":
            agent = "MBPP"
            image = "agent_sandbox:latest"
        else:
            agent = "SWE_BENCH"
            image = "swe_sandbox:latest"

        sandbox = Sandbox(agent, image, config=sandbox_config)

        if args.mcp_stdio:
            run_mcp_stdio(sandbox, args.mcp_stdio)

        elif args.mcp_server:
            run_mcp_http(sandbox, args.mcp_server, args.sandbox_template)

        else:
            run_interactive_cli(sandbox)

    except Exception as e:
        print(f"[bold red]Error: [/bold red][red]{e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
