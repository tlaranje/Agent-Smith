from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse
from student.src.sandbox import Sandbox, SandboxConfig
import json as json_module
import os

mcp = FastMCP("mbpp-tools")


def _load_config() -> SandboxConfig:
    """
    Load a SandboxConfig from the SANDBOX_CONFIG_JSON env var,
    falling back to defaults if it is not set.
    """
    raw = os.environ.get("SANDBOX_CONFIG_JSON", "")
    if raw:
        return SandboxConfig.model_validate_json(raw)
    return SandboxConfig()


sandbox: Sandbox | None = None
current_task_tests: list[str] = []

# When launched as a subprocess by Sandbox.start(), attach to the
# already-running container instead of creating a new one.
if os.environ.get("IS_MCP_SERVER"):
    container_id = os.environ.get("DOCKER_CONTAINER_ID", "")
    if not container_id:
        raise RuntimeError(
            "IS_MCP_SERVER=1 mas DOCKER_CONTAINER_ID não está definido."
        )
    sandbox = Sandbox.attach(
        "MBPP", container_id=container_id, config=_load_config()
    )


@mcp.custom_route("/initialize", methods=["POST"])
async def initialize(request: Request) -> JSONResponse:
    """
    HTTP endpoint used by clients to (re)attach the server to a
    running container and load the task's tests for this session.
    """
    global sandbox, current_task_tests
    payload = await request.json()

    container_id = payload.get("docker_container_id")
    task = payload.get("task", {})

    if not container_id:
        return JSONResponse(
            {"error": "docker_container_id is required"}, status_code=400
        )

    sandbox = Sandbox.attach(
        "MBPP", container_id=container_id, config=_load_config()
    )
    current_task_tests = task.get("test_list", [])

    return JSONResponse(
        {
            "status": "ok",
            "message": (
                f"Session initialized with "
                f"{len(current_task_tests)} tests."
            ),
        }
    )


@mcp.tool()
def set_current_task_tests(test_list: list[str] | None = None) -> str:
    """
    Configure the tests used by run_tests for the current task.

    Args:
        test_list: List of assert statements to run against the
            submitted solution.

    Returns:
        A confirmation message, or an error string if test_list
        is missing.
    """
    global current_task_tests
    if test_list is None:
        return "ERROR: test_list is required."

    current_task_tests = test_list
    return f"Task configured successfully with {len(test_list)} tests."


@mcp.tool()
def run_tests(
    code: str | None = None, test_list: list[str] | None = None
) -> str:
    """
    Run submitted code against the current task's tests inside
    the sandbox.

    Success is determined by whether the code executed cleanly
    (no assertion failure, runtime error, timeout, or memory
    limit violation) — it does not require final_answer() to
    have been called.

    Args:
        code: The Python solution code to execute.
        test_list: Optional list of assert statements to run
            against the submitted solution. If omitted, falls
            back to the tests configured via set_current_task_tests.

    Returns:
        A JSON string with "success" (bool) and "output" (str)
        fields describing the result of the execution.
    """
    if code is None:
        return json_module.dumps(
            {"success": False, "output": "ERROR: code is required."}
        )
    if not sandbox:
        return json_module.dumps({
            "success": False,
            "output": "ERROR: No active sandbox container session found."
        })

    tests_to_run = test_list if test_list is not None else current_task_tests
    output, final_answer_called = sandbox.execute(code, test_list=tests_to_run)

    # Treat runtime errors, timeouts, memory exceeded, and explicit
    # sandbox validation rejections as failures. Previously the
    # "Code rejected: ..." message could be mis-classified as a
    # success because it doesn't start with the runtime error
    # prefixes; ensure it's treated as a failure here.
    ran_cleanly = not output.startswith((
        "[RUNTIME ERROR]", "[TIMEOUT]", "[MEMORY LIMIT EXCEEDED]",
        "Code rejected:"
    ))

    return json_module.dumps({
        "success": ran_cleanly,
        "output": output,
    })


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
