from student.src.sandbox.sandbox_config import SandboxConfig
from student.src.sandbox.sandbox import Sandbox
from rich import print
import argparse
import httpx
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
    Build and start the sandbox, initializing the MCP server over stdio,
    and then launch a Python REPL bound to the MCP-provided tools.

    Args:
        sandbox: The Sandbox instance.
        mcp_command: The shell command to launch the custom MCP server.
    """
    print("[bold green][+][/bold green] Building and starting Sandbox...")
    sandbox.build("..")

    sandbox.start(custom_command=mcp_command)

    try:
        sandbox.repl()
    finally:
        if sandbox.mcp_client:
            sandbox.mcp_client.close()
        sandbox.stop()


def run_interactive_cli(sandbox: Sandbox) -> None:
    """
    Build, start, and enter an interactive sandbox session (Python REPL).

    Args:
        sandbox: The Sandbox instance to build, start, enter
            interactively, and eventually stop.
    """
    try:
        sandbox.build("..")
        sandbox.start()
        sandbox.repl()
    finally:
        if sandbox.mcp_client:
            sandbox.mcp_client.close()
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
    Build and start the sandbox, then connect to an already-running
    MCP server over HTTP at the given URL, initializing a session for
    the given task and launching a REPL bound to its tools.

    Args:
        sandbox: The Sandbox instance to build, start, and eventually
            stop.
        url: URL of the MCP server to connect to (e.g.
            http://localhost:18080/mcp).
        task_file: Path to the JSON file describing the task to send
            during session initialization.
        benchmark: Which benchmark this task belongs to, either
            "MBPP" or "SWE_BENCH".
    """
    print("[bold green][+][/bold green] Building and starting Sandbox...")
    sandbox.build("..")
    sandbox.start()

    try:
        # Initialize the remote server's session with this container
        # and task, using its /initialize endpoint.
        base_url = url.rsplit("/mcp", 1)[0] if url.endswith("/mcp") else url

        with open(task_file, "r", encoding="utf-8") as f:
            task_data = json.load(f)

        payload = {
            "docker_container_id": sandbox.container.id,
            "task": task_data,
        }

        response = httpx.post(
            f"{base_url}/initialize", json=payload, timeout=60.0
        )

        if response.status_code == 200:
            print("[green]Session initialized on MCP server.[/green]")
        else:
            print(f"[bold red]MCP Server Error:[/bold red] {response.text}")

        # Connect as an MCP client to the already-running server.
        sandbox.mcp_client = sandbox.mcp_client or None
        from student.src.mcp import MCPClient  # ajusta ao teu import real
        sandbox.mcp_client = MCPClient(url=url)

        sandbox.repl()

    except httpx.RequestError as e:
        raise httpx.RequestError(
            f"[bold red]Network error connecting to MCP server:[/bold red] {e}"
        )
    finally:
        if sandbox.mcp_client:
            sandbox.mcp_client.close()
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
