from mcp.server.fastmcp import FastMCP
from src.sandbox import Sandbox


class MCPServer:
    def __init__(self) -> None:
        self.mcp = FastMCP("MBPP Test Runner")
        self.sandbox = Sandbox()
        self.current_task_tests: list[str] = []

        @self.mcp.tool()
        def set_current_task(test_list: list[str]) -> str:
            self.current_task_tests = test_list
            return f"Task configured successfully with {len(test_list)} tests."

        @self.mcp.tool()
        def run_tests(code: str) -> str:
            if not self.current_task_tests:
                return (
                    "Error: No active task. Call set_current_task "
                    "first to load the tests."
                )

            # print(
            #   "[*] Running tests inside the Sandbox for the received code..."
            # )

            output, success = self.sandbox.execute(
                code, test_list=self.current_task_tests
            )

            if success:
                return (
                    f"SUCCESS: All tests passed successfully!\n\n"
                    f"The solution code is valid.\n"
                    f"Sandbox Output:\n{output}"
                )
            else:
                return (
                    f"FAILURE: The code execution or a "
                    "test assertion failed.\n"
                    f"Analyze the error logs below to fix "
                    "your implementation:\n\n"
                    f"--- ERROR LOGS ---\n{output}"
                )

    def run(self, transport: str = "stdio") -> None:
        # print("[*] Starting sandbox container...")
        self.sandbox.start()

        try:
            self.mcp.run(transport=transport)
        finally:
            # print("[*] Stopping and cleaning up sandbox container...")
            self.sandbox.stop()
