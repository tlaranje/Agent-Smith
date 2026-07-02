from mcp.server.fastmcp import FastMCP
from rich import print
import docker
import base64
import sys
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
        result = self._container.exec_run(["bash", "-c", cmd])
        output = result.output.decode("utf-8") if result.output else ""
        return output, result.exit_code

    def _write_file(self, filepath: str, content: str) -> None:
        import base64
        encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
        self._exec(
            f"echo {encoded} | base64 -d > {filepath}"
        )


class SWEBenchToolState:
    def __init__(self, sandbox: ContainerShim | None) -> None:
        self.sandbox = sandbox

    def _write_file(self, filepath: str, content: str) -> None:
        escaped_content = content.replace("'", "'\\''")
        cmd = f"cat << 'EOF' > {filepath}\n{escaped_content}\nEOF"
        self.container.exec_run(["bash", "-c", cmd])


if os.environ.get("IS_MCP_SERVER"):
    container_id = os.environ.get("DOCKER_CONTAINER_ID", "")
    if not container_id:
        raise RuntimeError(
            "IS_MCP_SERVER=1 mas DOCKER_CONTAINER_ID não está definido."
        )
    _state = SWEBenchToolState(sandbox=ContainerShim(container_id))
else:
    _state = SWEBenchToolState(sandbox=None)


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

    # print("old file:", sandbox._exec(f"cat {filepath}"), file=sys.stderr)

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

    sandbox._write_file(filepath, new_content)

    diff, _ = sandbox._exec(f"git -C /testbed diff -- {filepath}")

    if not diff.strip():
        return (
            "WARNING: File was rewritten but git reports no modifications."
        )

    return f"OK: {filepath} updated successfully."

    # print("new file:", sandbox._exec(f"cat {filepath}"), file=sys.stderr)

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
    out, code = _state.sandbox._exec(f"cd {workdir} && {command}")
    return f"Exit code: {code}\nOutput:\n{out}"


@mcp.tool()
def get_patch() -> str:
    print("get_patch: ", _state.sandbox._exec("git status"), file=sys.stderr)
    print("get_path:", _state.sandbox._exec("ls"), file=sys.stderr)
    """Retrieve the unified git diff of all changes made to /testbed."""
    out, _ = _state.sandbox._exec(
        "cd /testbed && git -c core.fileMode=false diff"
    )
    return out


if __name__ == "__main__":
    mcp.run()
