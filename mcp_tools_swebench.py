from student.src.sandbox import Sandbox, SandboxConfig
from starlette.responses import JSONResponse
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
import base64
import os
import re

mcp = FastMCP("swe-bench-tools")


def _load_config() -> SandboxConfig:
    raw = os.environ.get("SANDBOX_CONFIG_JSON", "")
    if raw:
        return SandboxConfig.model_validate_json(raw)
    return SandboxConfig()


def _attach(container_id: str, eval_script: str = "") -> Sandbox:
    instance = Sandbox.attach(
        "SWE_BENCH", container_id=container_id, config=_load_config()
    )
    instance.eval_script = eval_script or base64.b64decode(
        os.environ.get("EVAL_SCRIPT_B64", "")
    ).decode("utf-8")
    instance._exec("git config --global --add safe.directory /testbed")
    return instance


sandbox: Sandbox | None = None

if os.environ.get("IS_MCP_SERVER"):
    container_id = os.environ.get("DOCKER_CONTAINER_ID", "")
    if not container_id:
        raise RuntimeError(
            "IS_MCP_SERVER=1 mas DOCKER_CONTAINER_ID não está definido."
        )
    sandbox = _attach(container_id)


@mcp.custom_route("/initialize", methods=["POST"])
async def initialize(request: Request) -> JSONResponse:
    global sandbox
    payload = await request.json()

    container_id = payload.get("docker_container_id")
    task = payload.get("task", {})

    if not container_id:
        return JSONResponse(
            {"error": "docker_container_id is required"}, status_code=400
        )

    sandbox = _attach(container_id, eval_script=task.get("eval_script", ""))

    return JSONResponse(
        {
            "status": "ok",
            "message": (
                f"Session initialized for instance "
                f"{task.get('instance_id', 'unknown')}."
            ),
        }
    )


@mcp.tool()
def read_file(
    filepath: str, start_line: int | None = None,
    end_line: int | None = None
) -> str:
    if not sandbox:
        return "ERROR: No active sandbox container session found."

    out, code = sandbox._exec(f"cat {filepath}")
    if code != 0:
        return f"ERROR: Could not read {filepath}: {out}"

    lines = out.splitlines()
    start = (start_line - 1) if start_line else 0
    end = end_line if end_line else len(lines)
    selected = lines[start:end]

    result = []
    for i, line in enumerate(selected, start=start + 1):
        result.append(f"{i:6}\t{line}")
    return "\n".join(result)


@mcp.tool()
def edit_file(filepath: str, old_str: str, new_str: str) -> str:
    if not sandbox:
        return "ERROR: No active sandbox container session found."

    out, code = sandbox._exec(f"cat {filepath}")
    if code != 0:
        return f"ERROR: Could not read {filepath}: {out}"

    pattern = re.escape(old_str)
    matches = list(re.finditer(pattern, out, flags=re.MULTILINE))

    if not matches:
        return (
            f"ERROR: old_str not found in {filepath}. "
            "Make sure it matches exactly, including whitespace."
        )

    if len(matches) > 1:
        return (
            f"ERROR: old_str matched {len(matches)} locations in "
            f"{filepath}. Please provide more surrounding context."
        )

    match = matches[0]
    new_content = out[:match.start()] + new_str + out[match.end():]

    if new_content == out:
        return (
            "ERROR: Replacement produced no changes. "
            "The requested replacement is identical to the current file."
        )

    try:
        sandbox._write_file(filepath, new_content)
    except Exception as e:
        return f"ERROR: write to {filepath} failed: {e}"

    verify, _ = sandbox._exec(f"cat {filepath}")
    if verify != new_content:
        return f"ERROR: write to {filepath} did not persist."

    return f"OK: {filepath} updated successfully."


@mcp.tool()
def list_files(directory: str, pattern: str = "*") -> str:
    if not sandbox:
        return "ERROR: No active sandbox container session found."

    out, code = sandbox._exec(
        f"find {directory} -name '{pattern}' -type f | sort"
    )
    if code != 0:
        return f"ERROR: Could not list files in {directory}: {out}"
    return out or "No files found."


@mcp.tool()
def search_code(pattern: str, file_pattern: str = "*.py") -> str:
    if not sandbox:
        return "ERROR: No active sandbox container session found."

    cmd = f"grep -rn --include='{file_pattern}' '{pattern}' /testbed"
    out, _ = sandbox._exec(cmd)
    return out or "No matches found."


@mcp.tool()
def search_function_or_class_definition_in_code(name: str) -> str:
    if not sandbox:
        return "ERROR: No active sandbox container session found."

    cmd = f"grep -rn --include='*.py' -E '^(def {name}|class {name})' /testbed"
    out, _ = sandbox._exec(cmd)
    if not out:
        cmd = (
            "grep -rn --include='*.py' -E "
            f"'(def {name}|class {name})\\b' /testbed"
        )
        out, _ = sandbox._exec(cmd)
    return out or f"No definition found for '{name}'."


@mcp.tool()
def find_references(
    name: str, filepath: str | None = None,
    line: int | None = None
) -> str:
    if not sandbox:
        return "ERROR: No active sandbox container session found."

    search_path = filepath if filepath else "/testbed"
    cmd = f"grep -rn --include='*.py' '\\b{name}\\b' {search_path}"
    out, _ = sandbox._exec(cmd)
    return out or f"No references found for '{name}'."


@mcp.tool()
def run_tests() -> str:
    if not sandbox:
        return "ERROR: No active sandbox container session found."

    sandbox._write_file("/tmp/eval_script.sh", sandbox.eval_script)
    out, code = sandbox._exec(
        "bash /tmp/eval_script.sh",
        timeout=sandbox.config.max_execution_time_seconds,
    )
    return f"Exit code: {code}\n{out}"


@mcp.tool()
def run_command(command: str, workdir: str = "/testbed") -> str:
    """Execute a shell command in the specified working directory."""
    if not sandbox:
        return "ERROR: No active sandbox container session found."

    out, code = sandbox._exec(f"cd {workdir} && {command}")
    return f"Exit code: {code}\nOutput:\n{out}"


@mcp.tool()
def get_patch() -> str:
    """Retrieve the unified git diff of all changes made to /testbed."""
    if not sandbox:
        return "ERROR: No active sandbox container session found."

    return sandbox.get_patch()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--http", action="store_true")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if args.http:
        mcp.settings.port = args.port
        mcp.run(transport="streamable-http")
    else:
        mcp.run()
