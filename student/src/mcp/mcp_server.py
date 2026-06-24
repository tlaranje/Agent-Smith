from mcp.server.fastmcp import FastMCP


class MCPServer:
    def __init__(self) -> None:
        self.mcp = FastMCP("MBPP Test Runner")
        self.current_task_tests: list[str] = []

    def run(self, transport: str = "stdio") -> None:
        self.mcp.run(transport=transport)
