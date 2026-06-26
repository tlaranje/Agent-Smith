from mcp.server.fastmcp import FastMCP
import docker
import os

mcp = FastMCP("mbpp-tools")


class SharedSandboxWrapper:
    def __init__(self, container):
        self.container = container

    def execute(self, code: str, test_list: list[str]) -> tuple[str, bool]:
        import io
        import contextlib

        global_vars = {"__builtins__": __builtins__}
        local_vars = {}
        stdout_capture = io.StringIO()

        try:
            with contextlib.redirect_stdout(stdout_capture), \
                 contextlib.redirect_stderr(stdout_capture):
                exec(code, global_vars, local_vars)
                for test in test_list:
                    exec(test, global_vars, local_vars)
            return stdout_capture.getvalue(), True
        except Exception as e:
            return stdout_capture.getvalue() + f"Exception raised: {e}", False


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


@mcp.tool()
def set_current_task_tests(
    test_list: list[str] | None = None, **kwargs
) -> str:
    if "args" in kwargs and isinstance(kwargs["args"], dict):
        test_list = kwargs["args"].get("test_list", test_list)

    if test_list is None:
        return "ERROR: test_list is required."

    _state.current_task_tests = test_list
    return f"Task configured successfully with {len(test_list)} tests."


@mcp.tool()
def run_tests(code: str | None = None, **kwargs) -> str:
    if "args" in kwargs and isinstance(kwargs["args"], dict):
        code = kwargs["args"].get("code", code)

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
    mcp.run()
