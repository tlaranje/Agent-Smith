import asyncio
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    print("[*] Connecting to MCPServer via stdio...")

    server_params = StdioServerParameters(
        command="uv",
        args=["run", "python", "mcp_tools_mbpp.py"],
        env=dict(os.environ),
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            print("[*] Initializing session handshake...")
            await session.initialize()

            print("\n--- Listing available tools ---")
            tools_response = await session.list_tools()
            for tool in tools_response.tools:
                print(f"Tool found: {tool.name} - {tool.description}")

            print("\n--- Testing 'set_current_task' ---")
            task_result = await session.call_tool(
                "set_current_task", arguments={"test_list": ["assert True"]}
            )
            print(f"Server Response: {task_result.content[0].text}")

            print("\n--- Testing 'run_tests' ---")

            code_sample = """def minha_funcao():\n    return True\n"""

            test_result = await session.call_tool(
                "run_tests", arguments={"code": code_sample}
            )
            print(f"Server Response:\n{test_result.content[0].text}")


if __name__ == "__main__":
    asyncio.run(main())
