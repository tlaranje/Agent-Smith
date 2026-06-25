from student.src.sandbox import Sandbox
from mcp.server.fastmcp import FastMCP
import os

mcp = FastMCP("swebench-tools")


class SWEBenchToolState:
    def __init__(self, sandbox: Sandbox | None) -> None:
        self.sandbox = sandbox


if not os.environ.get("IS_MCP_SERVER"):
    _state = SWEBenchToolState(sandbox=Sandbox("SWE_BENCH"))
else:
    _state = SWEBenchToolState(sandbox=None)


@mcp.tool()
def read_file(
    filepath: str,
    start_line: int | None = None,
    end_line: int | None = None,
) -> str:
    """
    Read file with line numbers in cat -n format:
        1  line one
        2  line two
    """
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
    """Replace exact old_str with new_str in a file."""
    out, code = _state.sandbox._exec(f"cat {filepath}")
    if code != 0:
        return f"ERROR: Could not read {filepath}: {out}"

    if old_str not in out:
        return (
            f"ERROR: old_str not found in {filepath}. "
            "Make sure it matches exactly including "
            "indentation and whitespace."
        )
    if out.count(old_str) > 1:
        return (
            f"ERROR: old_str matches {out.count(old_str)} locations in "
            f"{filepath}. Make it more specific."
        )

    new_content = out.replace(old_str, new_str, 1)
    _state.sandbox._write_file(filepath, new_content)
    return f"OK: {filepath} updated successfully."


@mcp.tool()
def list_files(directory: str, pattern: str = "*") -> str:
    """List files in a directory matching a pattern."""
    out, code = _state.sandbox._exec(
        f"find {directory} -name '{pattern}' -type f | sort"
    )
    if code != 0:
        return f"ERROR: Could not list files in {directory}: {out}"
    return out or "No files found."


@mcp.tool()
def search_code(pattern: str, file_pattern: str = "*.py") -> str:
    """
    grep-like search. Output format:
        /absolute/path_to_file.py:<line>:<match>
    """
    cmd = f"grep -rn --include='{file_pattern}' '{pattern}' /testbed"
    out, _ = _state.sandbox._exec(cmd)
    return out or "No matches found."


@mcp.tool()
def search_function_or_class_definition_in_code(name: str) -> str:
    """
    Find def <name> or class <name>.
    """
    cmd = f"grep -rn --include='*.py' -E '^(def {name}|class {name})' /testbed"
    out, _ = _state.sandbox._exec(cmd)

    if not out:
        cmd = (
            f"grep -rn --include='*.py' -E '(def {name}|class {name})\\b' "
            "/testbed"
        )
        out, _ = _state.sandbox._exec(cmd)

    return out or f"No definition found for '{name}'."


@mcp.tool()
def find_references(
    name: str,
    filepath: str | None = None,
    line: int | None = None,
) -> str:
    """Find all usages of a symbol."""
    search_path = filepath if filepath else "/testbed"
    cmd = f"grep -rn --include='*.py' '\\b{name}\\b' {search_path}"
    out, _ = _state.sandbox._exec(cmd)
    return out or f"No references found for '{name}'."


@mcp.tool()
def run_tests() -> str:
    """Execute the evaluation script stored at start() time."""
    _state.sandbox._write_file(
        "/tmp/eval_script.sh", _state.sandbox.eval_script
    )
    out, code = _state.sandbox._exec("bash /tmp/eval_script.sh")
    return f"Exit code: {code}\n{out}"


@mcp.tool()
def get_patch() -> str:
    """Retrieve the unified git diff of all changes made to /testbed."""
    out, _ = _state.sandbox._exec(
        "cd /testbed && git -c core.fileMode=false diff"
    )
    return out


@mcp.tool()
def run_command(command: str, workdir: str = "/testbed") -> str:
    """Execute a shell command in the specified working directory."""
    out, code = _state.sandbox._exec(f"cd {workdir} && {command}")
    return f"Exit code: {code}\nOutput:\n{out}"


if __name__ == "__main__":
    mcp.run()
