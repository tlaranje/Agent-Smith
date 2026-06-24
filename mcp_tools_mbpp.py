# mcp_tools_mbpp.py
import os
from student.src.sandbox import Sandbox
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("mbpp-tools")


class MBPPToolState:
    def __init__(self, sandbox: Sandbox | None) -> None:
        self.sandbox = sandbox
        self.current_task_tests: list[str] = []


if not os.environ.get("IS_MCP_SERVER"):
    _state = MBPPToolState(sandbox=Sandbox("MBPP"))
else:
    _state = MBPPToolState(sandbox=None)


@mcp.tool()
def set_current_task_tests(test_list: list[str]) -> str:
    _state.current_task_tests = test_list
    return f"Task configured successfully with {len(test_list)} tests."


@mcp.tool()
def run_tests(code: str) -> str:
    if not _state.current_task_tests:
        return (
            "Error: No active task. Call set_current_task_tests "
            "first to load the tests."
        )

    if _state.sandbox is None:
        return "Error: Sandbox targets missing in current context context."

    output, success = _state.sandbox.execute(
        code, test_list=_state.current_task_tests
    )

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
