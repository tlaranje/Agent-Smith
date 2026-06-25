from contextlib import asynccontextmanager
from student.src.sandbox import Sandbox
from mcp.server.fastmcp import FastMCP, Context


@asynccontextmanager
async def lifespan(server):
    sandbox = Sandbox("SWE_BENCH")
    yield {"sandbox": sandbox}

mcp = FastMCP("swebench-tools", lifespan=lifespan)


@mcp.tool()
def read_file(
    filepath: str, ctx: Context, start_line: int | None = None,
    end_line: int | None = None
) -> str:
    """Read file with line numbers in cat -n format."""
    sandbox: Sandbox = ctx.request_context.lifespan_context["sandbox"]
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
def edit_file(filepath: str, old_str: str, new_str: str, ctx: Context) -> str:
    """Replace exact old_str with new_str in a file."""
    sandbox: Sandbox = ctx.request_context.lifespan_context["sandbox"]
    out, code = sandbox._exec(f"cat {filepath}")
    if code != 0:
        return f"ERROR: Could not read {filepath}: {out}"
    if old_str not in out:
        return (
            f"ERROR: old_str not found in {filepath}. Make sure it "
            "matches exactly including indentation and whitespace."
        )
    if out.count(old_str) > 1:
        return (
            f"ERROR: old_str matches {out.count(old_str)} locations in "
            f"{filepath}. Make it more specific."
        )
    new_content = out.replace(old_str, new_str, 1)
    sandbox._write_file(filepath, new_content)
    return f"OK: {filepath} updated successfully."


@mcp.tool()
def list_files(directory: str, ctx: Context, pattern: str = "*") -> str:
    """List files in a directory matching a pattern."""
    sandbox: Sandbox = ctx.request_context.lifespan_context["sandbox"]
    out, code = sandbox._exec(
        f"find {directory} -name '{pattern}' -type f | sort"
    )
    if code != 0:
        return f"ERROR: Could not list files in {directory}: {out}"
    return out or "No files found."


@mcp.tool()
def search_code(pattern: str, ctx: Context, file_pattern: str = "*.py") -> str:
    """grep-like search."""
    sandbox: Sandbox = ctx.request_context.lifespan_context["sandbox"]
    cmd = f"grep -rn --include='{file_pattern}' '{pattern}' /testbed"
    out, _ = sandbox._exec(cmd)
    return out or "No matches found."


@mcp.tool()
def search_function_or_class_definition_in_code(
    name: str, ctx: Context
) -> str:
    """Find def <name> or class <name>."""
    sandbox: Sandbox = ctx.request_context.lifespan_context["sandbox"]
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
    name: str, ctx: Context, filepath: str | None = None,
    line: int | None = None
) -> str:
    """Find all usages of a symbol."""
    sandbox: Sandbox = ctx.request_context.lifespan_context["sandbox"]
    search_path = filepath if filepath else "/testbed"
    cmd = f"grep -rn --include='*.py' '\\b{name}\\b' {search_path}"
    out, _ = sandbox._exec(cmd)
    return out or f"No references found for '{name}'."


@mcp.tool()
def run_tests(ctx: Context) -> str:
    """Execute the evaluation script stored at start() time."""
    sandbox: Sandbox = ctx.request_context.lifespan_context["sandbox"]
    sandbox._write_file("/tmp/eval_script.sh", sandbox.eval_script)
    out, code = sandbox._exec("bash /tmp/eval_script.sh")
    return f"Exit code: {code}\n{out}"


@mcp.tool()
def get_patch(ctx: Context) -> str:
    """Retrieve the unified git diff of all changes made to /testbed."""
    sandbox: Sandbox = ctx.request_context.lifespan_context["sandbox"]
    out, _ = sandbox._exec("cd /testbed && git -c core.fileMode=false diff")
    return out


@mcp.tool()
def run_command(command: str, ctx: Context, workdir: str = "/testbed") -> str:
    """Execute a shell command in the specified working directory."""
    sandbox: Sandbox = ctx.request_context.lifespan_context["sandbox"]
    out, code = sandbox._exec(f"cd {workdir} && {command}")
    return f"Exit code: {code}\nOutput:\n{out}"


if __name__ == "__main__":
    mcp.run()
