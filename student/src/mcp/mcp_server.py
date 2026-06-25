from mcp.server.fastmcp import FastMCP
from typing import Any


class MCPServer:
    def __init__(self) -> None:
        self.mcp = FastMCP("MBPP Test Runner")
        self.current_task_tests: list[str] = []

    def run(self, transport: Any = "stdio") -> None:
        self.mcp.run(transport=transport)
