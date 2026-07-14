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
    Smoke-test the MCP HTTP server for SWE-bench-style tools:
    Start a container, initialize a session, dynamically detect the
    working directory, and exercise run_command, read_file, edit_file,
    and get_patch (both staged and unstaged) in sequence.

    Raises:
        docker.errors.APIError: If the container fails to start.
    """
    client = docker.from_env()
    print(
        "[bold green][+][/bold green] Starting temporary "
        "SWE-bench container..."
    )
    container = client.containers.run(
        "swe_sandbox:latest",
        command="tail -f /dev/null",
        detach=True,
        remove=True,
    )

    try:
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

        print(
            "[bold green][+][/bold green] Connecting to MCP streamable "
            "HTTP transport..."
        )
        async with streamablehttp_client("http://localhost:8000/mcp") as (
                   read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools = await session.list_tools()
                print(
                    "tools available:",
                    [t.name for t in tools.tools],
                )

                # 1. DYNAMICALLY DETECT THE DEFAULT WORKDIR OF THE MCP SERVER
                # This ensures git initialization and tool execution
                # run in the exact same directory.
                pwd_result = await session.call_tool(
                    "run_command",
                    {"command": "pwd"}
                )

                # Ultra-safe parsing: extract the line starting with
                # a forward slash '/'
                default_workdir = "/testbed"  # Safe fallback
                if pwd_result.content and len(pwd_result.content) > 0:
                    lines = pwd_result.content[0].text.split("\n")
                    for line in lines:
                        clean_line = line.strip()
                        if clean_line.startswith("/"):
                            default_workdir = clean_line
                            break

                print(
                    f"[bold blue][i][/bold blue] Target workdir selected: "
                    f"{default_workdir}"
                )

                # 2. INITIALIZE GIT REPOSITORY INSIDE THE CONTAINER
                # Create the folder, set wide open permissions
                # to prevent user/permission
                # conflicts from the MCP environment, and initialize git.
                setup_cmd = (
                    f"mkdir -p {default_workdir} && "
                    f"chmod -R 777 {default_workdir} && "
                    f"cd {default_workdir} && "
                    "git init && "
                    "git config user.email 'agent@smith.com' && "
                    "git config user.name 'Agent Smith' && "
                    "echo 'base' > file.txt && "
                    "git add file.txt && "
                    "git commit -m 'Initial commit'"
                )
                setup = container.exec_run(["bash", "-c", setup_cmd])
                print(
                    "setup /testbed:",
                    setup.output.decode("utf-8", "replace").strip()
                )

                # 3. PERFORM FILE MODIFICATIONS THROUGH MCP TOOLS
                result = await session.call_tool(
                    "run_command",
                    {
                        "command": (
                            "printf 'hello\\n' > file.txt && cat file.txt"
                        ),
                        "workdir": default_workdir,
                    },
                )
                print("run_command:", result)

                result = await session.call_tool(
                    "read_file",
                    {"filepath": f"{default_workdir}/file.txt"},
                )
                print("read_file:", result)

                result = await session.call_tool(
                    "edit_file",
                    {
                        "filepath": f"{default_workdir}/file.txt",
                        "old_str": "hello",
                        "new_str": "hello world",
                    },
                )
                print("edit_file:", result)

                # 4. TEST GET_PATCH WITH UNSTAGED CHANGES
                print(
                    "[bold green][+][/bold green] Testing get_patch with "
                    "unstaged changes:"
                )
                result_unstaged = await session.call_tool("get_patch", {})
                print("get_patch (unstaged):", result_unstaged)

                # 5. STAGE THE CHANGES (GIT ADD)
                result = await session.call_tool(
                    "run_command",
                    {"command": "git add -A", "workdir": default_workdir},
                )
                print("git add:", result)

                # 6. TEST GET_PATCH WITH STAGED CHANGES
                print(
                    "[bold green][+][/bold green] Testing "
                    "get_patch after git add:"
                )
                result_staged = await session.call_tool("get_patch", {})
                print("get_patch (after git add):", result_staged)

    finally:
        print("[bold yellow][!][/bold yellow] Stopping test container...")
        container.stop()
        print("[bold green][+][/bold green] Container stopped.")


if __name__ == "__main__":
    asyncio.run(main())
