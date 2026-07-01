from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession
from rich import print
import asyncio
import httpx
import docker


async def main():
    client = docker.from_env()
    container = client.containers.run(
        "agent_sandbox:latest",
        command="tail -f /dev/null",
        detach=True,
        remove=True,
    )

    try:
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

                code = "def soma(a, b):\n    return a + b\n"
                result = await session.call_tool("run_tests", {"code": code})
                print("run_tests:", result)

    finally:
        container.stop()


asyncio.run(main())
