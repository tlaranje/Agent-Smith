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
    """
    Infer which benchmark a template/task file belongs to.

    Inspects the JSON contents of the given file to decide whether it
    corresponds to an MBPP task or a SWE-Bench task. Falls back to
    "MBPP" whenever the file is missing, unreadable, or does not match
    any known signature.

    Args:
        template_path: Path to the sandbox template or task JSON file.

    Returns:
        The benchmark name, either "MBPP" or "SWE_BENCH".
    """
    # If there's no valid path, default to MBPP.
    if not template_path or not os.path.exists(template_path):
        return "MBPP"
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # MBPP tasks are identified by these keys.
        if "test_list" in data or "task_id" in data:
            return "MBPP"
        # SWE-Bench tasks are identified by these keys.
        if "instance_id" in data or "base_commit" in data:
            return "SWE_BENCH"
    except Exception:
        # Any parsing/reading error falls back to the default below.
        pass
    return "MBPP"


def load_sandbox_config(template_path: str) -> SandboxConfig:
    """
    Load a SandboxConfig instance from a JSON template file.

    Only fields recognized by SandboxConfig are kept; unknown fields
    present in the JSON file are silently ignored. If loading fails
    for any reason, a default SandboxConfig is returned instead.

    Args:
        template_path: Path to the JSON file containing configuration
            values for SandboxConfig.

    Returns:
        A SandboxConfig instance populated from the file, or a default
        instance if the file is missing or invalid.
    """
    if not template_path or not os.path.exists(template_path):
        return SandboxConfig()
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Filter out any keys that are not valid SandboxConfig fields.
        known_fields = set(SandboxConfig.model_fields.keys())
        filtered = {k: v for k, v in data.items() if k in known_fields}
        return SandboxConfig(**filtered)
    except Exception as e:
        # Warn the user and fall back to a default configuration.
        print(
            f"[yellow]Warning: could not load sandbox config from "
            f"{template_path} ({e}). Using defaults.[/yellow]"
        )
        return SandboxConfig()


def run_mcp_stdio(sandbox: Sandbox, mcp_command: str) -> None:
    """
    Build and start the sandbox, then run an MCP server over stdio.

    Prepares the environment variables required by the MCP server
    (container id and serialized sandbox config), resolves any ``.py``
    tokens in the command to absolute paths relative to the project
    root, and runs the resulting command as a subprocess.

    Args:
        sandbox: The Sandbox instance to build, start, and eventually
            stop.
        mcp_command: The shell command used to launch the MCP server,
            e.g. "python server.py --flag".

    Raises:
        ValueError: If ``mcp_command`` is empty after tokenization.
    """
    sandbox.build("..")
    sandbox.start()

    root_path = Path(__file__).parent.parent.parent

    # Environment variables consumed by the MCP server process.
    server_env = dict(os.environ)
    server_env["IS_MCP_SERVER"] = "1"
    server_env["DOCKER_CONTAINER_ID"] = sandbox.container.id
    server_env["SANDBOX_CONFIG_JSON"] = sandbox.config.model_dump_json()

    tokens = shlex.split(mcp_command)
    if not tokens:
        raise ValueError("--mcp-stdio requires a non-empty command")

    # Resolve relative .py script paths against the project root.
    resolved = []
    for tok in tokens:
        if tok.endswith(".py"):
            resolved.append(str(root_path / tok))
        else:
            resolved.append(tok)

    try:
        subprocess.run(resolved, env=server_env, check=True)
    finally:
        # Always stop the sandbox, even if the subprocess fails.
        sandbox.stop()


def _wait_for_server(url: str, timeout: float = 15.0) -> None:
    """
    Poll a URL until it responds or a timeout is reached.

    Args:
        url: The URL to poll with GET requests.
        timeout: Maximum number of seconds to wait before giving up.
            Defaults to 15.0.

    Raises:
        httpx.RequestError: If the server does not respond within the
            given timeout.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            httpx.get(url, timeout=1.0)
            return
        except httpx.RequestError:
            # Server not ready yet; wait briefly and retry.
            time.sleep(0.3)
    raise httpx.RequestError(
        f"Server at {url} did not start within {timeout}s"
    )


def run_mcp_http(
    sandbox: Sandbox, url: str, task_file: str, benchmark: str
) -> None:
    """
    Build and start the sandbox, then run an MCP server over HTTP.

    Launches the appropriate MCP server script (MBPP or SWE-Bench)
    as a subprocess exposing an HTTP API, waits for it to become
    available, initializes a session with the given task, and blocks
    until the process ends or the user interrupts execution.

    Args:
        sandbox: The Sandbox instance to build, start, and eventually
            stop.
        url: Base URL where the MCP HTTP server will be reachable.
        task_file: Path to the JSON file describing the task to send
            during session initialization.
        benchmark: Which benchmark server to launch, either "MBPP" or
            "SWE_BENCH".

    Raises:
        httpx.RequestError: If a network error occurs while
            communicating with the MCP server.
    """
    sandbox.build("..")
    sandbox.start()

    # Environment variables consumed by the MCP server process.
    server_env = dict(os.environ)
    server_env["IS_MCP_SERVER"] = "1"
    server_env["DOCKER_CONTAINER_ID"] = sandbox.container.id
    server_env["SANDBOX_CONFIG_JSON"] = sandbox.config.model_dump_json()

    # Pick the server script based on the target benchmark.
    root_path = Path(__file__).parent.parent.parent
    if benchmark == "SWE_BENCH":
        server_script = root_path / "mcp_tools_swebench.py"
    else:
        server_script = root_path / "mcp_tools_mbpp.py"

    server_process = subprocess.Popen(
        [sys.executable, str(server_script), "--http", "--port", "8000"],
        env=server_env,
    )

    try:
        # Wait until the HTTP server is up before initializing a session.
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

        print(
            "[cyan]MCP server is running. Press Ctrl+C to stop.[/cyan]"
        )
        # Keep the main process alive while the server runs.
        while server_process.poll() is None:
            time.sleep(0.5)

    except KeyboardInterrupt:
        # Graceful shutdown when the user presses Ctrl+C.
        print("[yellow]Shutting down MCP server...[/yellow]")
    except httpx.RequestError as exc:
        raise httpx.RequestError(
            "[bold red]Network error connecting to "
            f"MCP server:[/bold red] {exc}"
        )
    finally:
        # Ensure both the subprocess and the sandbox are cleaned up.
        server_process.terminate()
        server_process.wait()
        sandbox.stop()


def run_interactive_cli(sandbox: Sandbox) -> None:
    """
    Build, start, and enter an interactive sandbox session.

    Args:
        sandbox: The Sandbox instance to build, start, enter
            interactively, and eventually stop.
    """
    try:
        sandbox.build("..")
        sandbox.start()
        sandbox.enter()
    finally:
        # Always stop the sandbox, even if the interactive session fails.
        sandbox.stop()


def main() -> None:
    """
    Parse CLI arguments and dispatch to the appropriate run mode.

    Supports three mutually exclusive modes:
        1. ``--mcp-stdio``: run an MCP server over stdio.
        2. ``--mcp-server``: run an MCP server over HTTP.
        3. Neither flag: enter an interactive sandbox CLI session.

    The benchmark type and sandbox configuration are both inferred
    from the provided template/task file. Any uncaught exception is
    printed and causes the process to exit with status code 1.
    """
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

        # Determine benchmark and load the corresponding sandbox config.
        benchmark = discover_benchmark_from_template(args.sandbox_template)
        sandbox_config = load_sandbox_config(args.sandbox_template)

        # Select the agent name and docker image for the given benchmark.
        if benchmark == "MBPP":
            agent = "MBPP"
            image = "agent_sandbox:latest"
        else:
            agent = "SWE_BENCH"
            image = "swe_sandbox:latest"

        sandbox = Sandbox(agent, image, config=sandbox_config)

        # Dispatch to the requested run mode.
        if args.mcp_stdio:
            run_mcp_stdio(sandbox, args.mcp_stdio)

        elif args.mcp_server:
            run_mcp_http(
                sandbox, args.mcp_server, args.sandbox_template, benchmark
            )

        else:
            run_interactive_cli(sandbox)

    except Exception as e:
        print(f"[bold red]Error: [/bold red][red]{e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
