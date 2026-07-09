from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse
from student.src.sandbox import Sandbox, SandboxConfig
import os

mcp = FastMCP("mbpp-tools")


def _load_config() -> SandboxConfig:
    raw = os.environ.get("SANDBOX_CONFIG_JSON", "")
    if raw:
        return SandboxConfig.model_validate_json(raw)
    return SandboxConfig()


sandbox: Sandbox | None = None
current_task_tests: list[str] = []

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
    global current_task_tests
    if test_list is None:
        return "ERROR: test_list is required."

    current_task_tests = test_list
    return f"Task configured successfully with {len(test_list)} tests."


@mcp.tool()
def run_tests(code: str | None = None) -> str:
    if code is None:
        return "ERROR: code is required."

    if not sandbox:
        return "ERROR: No active sandbox container session found."

    if not current_task_tests:
        return (
            "Error: No active task. Call set_current_task_tests "
            "first to load the tests."
        )

    output, success = sandbox.execute(code, test_list=current_task_tests)

    if success:
        return (
            f"SUCCESS: All tests passed successfully!\n\n"
            f"The solution code is valid.\n"
            f"Sandbox Output:\n{output}"
        )
    else:
        return (
            f"FAILURE: The code execution or a test assertion failed.\n"
            f"Analyze the error logs below to fix your implementation:\n\n"
            f"--- ERROR LOGS ---\n{output}"
        )


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
