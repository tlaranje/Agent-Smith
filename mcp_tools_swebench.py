from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse
import docker
import base64
import tarfile
import io
import os
import re

mcp = FastMCP("swe-bench-tools")


class SharedSandboxWrapper:
    def __init__(self, container):
        self.container = container
        self.eval_script = ""


class ContainerShim:
    def __init__(self, container_id: str) -> None:
        client = docker.from_env()
        self._container = client.containers.get(container_id)
        self.eval_script: str = base64.b64decode(
            os.environ.get("EVAL_SCRIPT_B64", "")
        ).decode("utf-8")
        self._exec("git config --global --add safe.directory /testbed")

    def _exec(self, cmd: str) -> tuple[str, int]:
        result = self._container.exec_run(["bash", "-c", cmd], stream=False)
        raw_output = result.output
        output = (
            raw_output.decode("utf-8", errors="replace")
            if isinstance(raw_output, bytes) else ""
        )
        exit_code = result.exit_code if result.exit_code is not None else 1
        return output, exit_code

    def _write_file(self, filepath: str, content: str) -> None:
        directory = os.path.dirname(filepath)
        filename = os.path.basename(filepath)

        self._exec(f"mkdir -p {directory}")

        data = content.encode("utf-8")
        tarstream = io.BytesIO()
        with tarfile.open(fileobj=tarstream, mode="w") as tar:
            tarinfo = tarfile.TarInfo(name=filename)
            tarinfo.size = len(data)
            tar.addfile(tarinfo, io.BytesIO(data))
        tarstream.seek(0)

        ok = self._container.put_archive(directory, tarstream)
        if not ok:
            raise RuntimeError(
                f"put_archive failed while writing {filepath}"
            )


class SWEBenchToolState:
    def __init__(self, sandbox: ContainerShim | None) -> None:
        self.sandbox = sandbox


if os.environ.get("IS_MCP_SERVER"):
    container_id = os.environ.get("DOCKER_CONTAINER_ID", "")
    if not container_id:
        raise RuntimeError(
            "IS_MCP_SERVER=1 mas DOCKER_CONTAINER_ID não está definido."
        )
    _state = SWEBenchToolState(sandbox=ContainerShim(container_id))
else:
    _state = SWEBenchToolState(sandbox=None)


@mcp.custom_route("/initialize", methods=["POST"])
async def initialize(request: Request) -> JSONResponse:
    payload = await request.json()

    container_id = payload.get("docker_container_id")
    task = payload.get("task", {})

    if not container_id:
        return JSONResponse(
            {"error": "docker_container_id is required"}, status_code=400
        )

    shim = ContainerShim(container_id)
    eval_script = task.get("eval_script", "")
    if eval_script:
        shim.eval_script = eval_script

    _state.sandbox = shim

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
    if not _state.sandbox:
        return "ERROR: No active sandbox container session found."

    out, code = _state.sandbox._exec(f"cat {filepath}")
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
    sandbox = _state.sandbox

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

    new_content = (
        out[:match.start()]
        + new_str
        + out[match.end():]
    )

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
    sandbox = _state.sandbox
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
    sandbox = _state.sandbox
    if not sandbox:
        return "ERROR: No active sandbox container session found."

    cmd = f"grep -rn --include='{file_pattern}' '{pattern}' /testbed"
    out, _ = sandbox._exec(cmd)
    return out or "No matches found."


@mcp.tool()
def search_function_or_class_definition_in_code(name: str) -> str:
    sandbox = _state.sandbox
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
    sandbox = _state.sandbox
    if not sandbox:
        return "ERROR: No active sandbox container session found."

    search_path = filepath if filepath else "/testbed"
    cmd = f"grep -rn --include='*.py' '\\b{name}\\b' {search_path}"
    out, _ = sandbox._exec(cmd)
    return out or f"No references found for '{name}'."


@mcp.tool()
def run_tests() -> str:
    sandbox = _state.sandbox
    if not sandbox:
        return "ERROR: No active sandbox container session found."

    sandbox._write_file("/tmp/eval_script.sh", sandbox.eval_script)
    out, code = sandbox._exec("bash /tmp/eval_script.sh")
    return f"Exit code: {code}\n{out}"


@mcp.tool()
def run_command(command: str, workdir: str = "/testbed") -> str:
    """Execute a shell command in the specified working directory."""
    if not _state.sandbox:
        return "ERROR: No active sandbox container session found."

    out, code = _state.sandbox._exec(f"cd {workdir} && {command}")
    return f"Exit code: {code}\nOutput:\n{out}"


@mcp.tool()
def get_patch() -> str:
    """Retrieve the unified git diff of all changes made to /testbed."""
    if not _state.sandbox:
        return "ERROR: No active sandbox container session found."

    out, _ = _state.sandbox._exec(
        "cd /testbed && git -c core.fileMode=false diff"
    )
    return out


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
