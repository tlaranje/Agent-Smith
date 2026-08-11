from student.src.mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import TextContent
from typing import Callable, Any
import threading
import asyncio
import os


class MCPClient:
    def __init__(
        self, command: str | None = None, args: list[str] | None = None,
        env: dict | None = None, url: str | None = None
    ) -> None:
        """
        Create an MCP client connected via stdio or HTTP.

        Starts a dedicated background event loop/thread and
        connects synchronously before returning.

        Args:
            command: Executable to spawn for a stdio-based server.
                Required if url is not given.
            args: Command-line arguments for the stdio server.
            env: Environment variables for the stdio server.
                Defaults to a copy of the current environment.
            url: URL of a streamable-HTTP MCP server. Required if
                command is not given.

        Raises:
            ValueError: If neither command nor url is provided.
        """
        if not command and not url:
            raise ValueError("MCPClient requires either command or url")

        self._command: str | None = command
        self._args = args or []
        self._env = env if env is not None else dict(os.environ)
        self._url = url

        # Run all async MCP calls on a private loop/thread so this
        # class exposes a plain synchronous API to callers.
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        self._session: ClientSession | None = None
        self._stdio_cm: Any = None
        self._session_cm: Any = None
        self._http_cm: Any = None

        future = asyncio.run_coroutine_threadsafe(self._connect(), self._loop)
        future.result()

    async def _connect(self) -> None:
        """
        Open the transport (HTTP or stdio) and initialize the
        MCP session on the background event loop.
        """
        if self._url:
            self._http_cm = streamablehttp_client(self._url)
            read_stream, write_stream, _get_session_id = (
                await self._http_cm.__aenter__()
            )
        else:
            assert self._command is not None
            server_params = StdioServerParameters(
                command=self._command,
                args=self._args,
                env=self._env,
            )
            self._stdio_cm = stdio_client(server_params)
            read_stream, write_stream = await self._stdio_cm.__aenter__()

        self._session_cm = ClientSession(read_stream, write_stream)
        self._session = await self._session_cm.__aenter__()
        assert self._session is not None
        await self._session.initialize()

    def _run_loop(self) -> None:
        """
        Entry point for the background thread: run the private
        event loop forever.
        """
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def _call_tool_async(self, name: str, /, **kwargs: Any) -> str:
        """
        Call a tool on the MCP session and return its text
        content, or an empty string if there is none.
        """
        assert self._session is not None
        result = await self._session.call_tool(name, arguments=kwargs)
        if not result.content:
            return ""
        content = result.content[0]
        if isinstance(content, TextContent):
            return content.text
        return ""

    def call_tool(self, name: str, /, **kwargs: Any) -> str:
        """
        Call an MCP tool synchronously, translating errors into
        readable error strings instead of raising.

        Args:
            name: Name of the tool to call.
            **kwargs: Arguments passed to the tool.

        Returns:
            The tool's text output, or a formatted error message
            if the tool name is unknown, the arguments are invalid,
            or execution fails.
        """
        allowed_tools_name: list[str] = [t.name for t in self.list_tools()]
        if name not in allowed_tools_name:
            return (
                f"ERROR:\n"
                f"Unknown tool name: '{name}'\n\n"
                f"Available tools:\n"
                + "\n".join(f"- {t}" for t in allowed_tools_name)
            )

        try:
            future = asyncio.run_coroutine_threadsafe(
                self._call_tool_async(name, **kwargs),
                self._loop
            )
            return future.result()

        except TypeError as e:
            return (
                f"ERROR:\n"
                f"Invalid arguments for tool '{name}'.\n"
                f"Details: {str(e)}\n"
                f"Received args: {kwargs}"
            )

        except Exception as e:
            return (
                f"ERROR:\n"
                f"Tool execution failed.\n"
                f"Tool: {name}\n"
                f"Exception: {str(e)}"
            )

    def discover_tools(self) -> dict[str, Callable[..., str]]:
        """
        Build a dict of callable Python wrappers, one per
        available MCP tool, keyed by tool name.
        """
        if self._session is None:
            return {}

        future = asyncio.run_coroutine_threadsafe(
            self._session.list_tools(), self._loop
        )
        tools_response = future.result()

        wrappers: dict[str, Callable[..., str]] = {}
        for tool in tools_response.tools:
            wrappers[tool.name] = self._make_wrapper(tool.name)
        return wrappers

    def _make_wrapper(self, tool_name: str) -> Callable[..., str]:
        """
        Create a closure that calls call_tool with a fixed
        tool_name, so it can be used as a plain Python function.
        """
        def wrapper(**kwargs: Any) -> str:
            return self.call_tool(tool_name, **kwargs)
        wrapper.__name__ = tool_name
        return wrapper

    def close(self) -> None:
        """
        Tear down the session and transport, then stop the
        background event loop and join its thread.
        """
        async def _shutdown() -> None:
            if self._session_cm:
                await self._session_cm.__aexit__(None, None, None)
            if self._stdio_cm:
                await self._stdio_cm.__aexit__(None, None, None)
            if self._http_cm:
                await self._http_cm.__aexit__(None, None, None)

        future = asyncio.run_coroutine_threadsafe(_shutdown(), self._loop)
        future.result()
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=2)

    def list_tools(self) -> Any:
        """
        Return the list of tools exposed by the connected MCP
        server, or an empty dict if not yet connected.
        """
        if self._session is None:
            return {}

        future = asyncio.run_coroutine_threadsafe(
            self._session.list_tools(), self._loop
        )
        return future.result().tools

    def generate_manual(self, exclude: set[str] | None = None) -> str:
        """
        Build a human/LLM-readable manual describing each
        available tool as a callable Python function.

        Args:
            exclude: Tool names to omit from the manual (e.g.
                internal-only tools not meant for the LLM).

        Returns:
            A Markdown string listing each tool's description,
            arguments, and a usage example, or a message saying
            no tools are available.
        """
        exclude = exclude or set()
        tools = [t for t in self.list_tools() if t.name not in exclude]

        if not tools:
            return "No tools are currently available."

        sections = [
            "## Available Tools",
            "",
            "Call tools as Python functions.",
            "Example:",
            "result = tool_name(arg=value)",
            "",
        ]

        for tool in tools:
            sections.append(f"### {tool.name}")

            if tool.description:
                sections.append(tool.description.strip())

            schema = tool.inputSchema or {}
            props = schema.get("properties", {})
            required = set(schema.get("required", []))

            if props:
                sections.append("")
                sections.append("Arguments:")

                for name, info in props.items():
                    typ = info.get("type", "any")
                    desc = info.get("description", "")
                    req = "required" if name in required else "optional"

                    line = f"- {name} ({typ}, {req})"

                    if desc:
                        line += f": {desc}"

                    sections.append(line)

                example = ", ".join(
                    f"{name}=..."
                    for name in props
                )
                sections.append("")
                sections.append(
                    f"Example: result = {tool.name}({example})"
                )
            else:
                sections.append("")
                sections.append("Arguments: none")
                sections.append("")
                sections.append(
                    f"Example: result = {tool.name}()"
                )

            sections.append("")

        return "\n".join(sections).strip()
