from contextlib import asynccontextmanager
from student.src.sandbox import Sandbox
from mcp.server.fastmcp import FastMCP, Context
import os


@asynccontextmanager
async def lifespan(server):
    if os.environ.get("IS_MCP_SERVER"):
        yield {}
    else:
        sandbox = Sandbox("SWE_BENCH")
        yield {"sandbox": sandbox}

mcp = FastMCP("mbpp-tools", lifespan=lifespan)


@mcp.tool()
def set_current_task_tests(test_list: list[str], ctx: Context) -> str:
    ctx.request_context.lifespan_context["current_task_tests"] = test_list
    return f"Task configured successfully with {len(test_list)} tests."


@mcp.tool()
def run_tests(code: str, ctx: Context) -> str:
    lc = ctx.request_context.lifespan_context
    current_task_tests = lc["current_task_tests"]
    sandbox: Sandbox = lc["sandbox"]

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
