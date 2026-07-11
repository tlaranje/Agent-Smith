from mcp.client.streamable_http import streamablehttp_client
from mcp import ClientSession
from rich import print
import asyncio
import httpx
import docker

# uv run sandbox --mcp-server http://localhost:8000
# ../data/input/mbpp_task.json


async def main():
    """
    Smoke-test the MCP HTTP server for SWE-bench-style tools:
    start a container, initialize a session, then exercise
    run_command, read_file, edit_file, and get_patch in sequence.

    Raises:
        docker.errors.APIError: If the container fails to start.
    """
    client = docker.from_env()
    container = client.containers.run(
        "swe_sandbox:latest",
        command="tail -f /dev/null",
        detach=True,
        remove=True,
    )

    try:
        # Initialize an empty git repo in /testbed so get_patch has
        # something valid to diff against later.
        setup = container.exec_run(
            ["bash", "-c", "mkdir -p /testbed && cd /testbed && git init"]
        )
        print("setup /testbed:", setup.output.decode("utf-8", "replace"))

        # Register the container and task with the MCP server
        # before opening a tool session.
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                "http://localhost:8000/initialize",
                json={
                    "docker_container_id": container.id,
                    "task": {
                        "instance_id": "manual-test-1",
                        "eval_script": "echo 'placeholder eval script'",
                    },
                },
            )
            print("initialize:", resp.status_code, resp.json())

        async with streamablehttp_client("http://localhost:8000/mcp") as (
                   read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools = await session.list_tools()
                print(
                    "tools available:",
                    [t.name for t in tools.tools],
                )

                # Create a file, then read/edit it to exercise the
                # core file-manipulation tools end to end.
                result = await session.call_tool(
                    "run_command",
                    {
                        "command": (
                            "printf 'hello\\n' > file.txt && cat file.txt"
                        ),
                        "workdir": "/testbed",
                    },
                )
                print("run_command:", result)

                result = await session.call_tool(
                    "read_file",
                    {"filepath": "/testbed/file.txt"},
                )
                print("read_file:", result)

                result = await session.call_tool(
                    "edit_file",
                    {
                        "filepath": "/testbed/file.txt",
                        "old_str": "hello",
                        "new_str": "hello world",
                    },
                )
                print("edit_file:", result)

                # Stage the change and confirm get_patch reflects it.
                result = await session.call_tool(
                    "run_command",
                    {"command": "git add -A", "workdir": "/testbed"},
                )
                print("git add:", result)

                result = await session.call_tool("get_patch", {})
                print("get_patch:", result)

    finally:
        container.stop()


asyncio.run(main())
