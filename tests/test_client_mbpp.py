from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession
from rich import print
import asyncio
import httpx
import docker

# uv run sandbox --mcp-server http://localhost:8000
# ../data/input/swebench_task.json


async def main():
    """
    Smoke-test the MCP HTTP server against a live sandbox
    container: start a container, initialize a session with a
    sample task, then call run_tests with a sample solution.

    Raises:
        docker.errors.APIError: If the container fails to start.
    """
    client = docker.from_env()
    container = client.containers.run(
        "agent_sandbox:latest",
        command="tail -f /dev/null",
        detach=True,
        remove=True,
    )

    try:
        # Register the container and its test list with the MCP
        # server before opening a tool session.
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                "http://localhost:8000/initialize",
                json={
                    "docker_container_id": container.id,
                    "task": {"test_list": ["assert soma(2, 3) == 5"]},
                },
            )
            print("initialize:", resp.status_code, resp.json())

        async with streamablehttp_client("http://localhost:8000/mcp") as (
                   read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Run a correct sample solution through run_tests
                # to confirm the tool call round-trips correctly.
                code = "def soma(a, b):\n    return a + b\n"
                result = await session.call_tool("run_tests", {"code": code})
                print("run_tests:", result)

    finally:
        # Always stop the container, even if a request above fails.
        container.stop()


asyncio.run(main())
