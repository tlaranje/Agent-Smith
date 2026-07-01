from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse
import docker
import os

mcp = FastMCP("mbpp-tools")


class SharedSandboxWrapper:
    def __init__(self, container):
        self.container = container

    def execute(self, code: str, test_list: list[str]) -> tuple[str, bool]:
        import io
        import tarfile

        full_script = code + "\n" + "\n".join(test_list) + "\n"

        tarstream = io.BytesIO()
        with tarfile.open(fileobj=tarstream, mode="w") as tar:
            data = full_script.encode("utf-8")
            tarinfo = tarfile.TarInfo(name="_exec_script.py")
            tarinfo.size = len(data)
            tar.addfile(tarinfo, io.BytesIO(data))
        tarstream.seek(0)

        self.container.put_archive("/tmp/agent", tarstream)

        exec_result = self.container.exec_run(
            ["python3", "/tmp/agent/_exec_script.py"],
            workdir="/tmp/agent",
        )

        output = exec_result.output.decode("utf-8", errors="replace")
        success = exec_result.exit_code == 0

        return output, success


class MBPPToolState:
    def __init__(self, sandbox: SharedSandboxWrapper | None) -> None:
        self.sandbox = sandbox
        self.current_task_tests: list[str] = []


if os.environ.get("IS_MCP_SERVER"):
    container_id = os.environ.get("DOCKER_CONTAINER_ID", "")
    if not container_id:
        raise RuntimeError(
            "IS_MCP_SERVER=1 mas DOCKER_CONTAINER_ID não está definido."
        )

    client = docker.from_env()
    container = client.containers.get(container_id)
    _state = MBPPToolState(SharedSandboxWrapper(container))
else:
    _state = MBPPToolState(None)


mcp = FastMCP("mbpp-tools")


@mcp.custom_route("/initialize", methods=["POST"])
async def initialize(request: Request) -> JSONResponse:
    payload = await request.json()

    container_id = payload.get("docker_container_id")
    task = payload.get("task", {})

    if not container_id:
        return JSONResponse(
            {"error": "docker_container_id is required"}, status_code=400
        )

    client = docker.from_env()
    container = client.containers.get(container_id)
    _state.sandbox = SharedSandboxWrapper(container)

    test_list = task.get("test_list", [])
    _state.current_task_tests = test_list

    return JSONResponse(
        {
            "status": "ok",
            "message": f"Session initialized with {len(test_list)} tests.",
        }
    )


@mcp.tool()
def set_current_task_tests(test_list: list[str] | None = None) -> str:
    if test_list is None:
        return "ERROR: test_list is required."

    _state.current_task_tests = test_list
    return f"Task configured successfully with {len(test_list)} tests."


@mcp.tool()
def run_tests(code: str | None = None) -> str:
    if code is None:
        return "ERROR: code is required."

    sandbox = _state.sandbox
    if not sandbox:
        return "ERROR: No active sandbox container session found."

    current_task_tests = _state.current_task_tests
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
