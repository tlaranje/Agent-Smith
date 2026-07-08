from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent
from typing import Callable, Any
import threading
import asyncio
import os


class MCPClient:
    def __init__(
        self, command: str, args: list[str], env: dict | None = None
    ) -> None:
        self._command = command
        self._args = args
        self._env = env if env is not None else dict(os.environ)

        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        self._session: ClientSession | None = None
        self._stdio_cm: Any = None
        self._session_cm: Any = None

        future = asyncio.run_coroutine_threadsafe(self._connect(), self._loop)
        future.result()

    async def _connect(self) -> None:
        server_params = StdioServerParameters(
            command=self._command,
            args=self._args,
            env=self._env,
        )
        self._stdio_cm = stdio_client(server_params)
        read_stream, write_stream = await self._stdio_cm.__aenter__()

        self._session_cm = ClientSession(read_stream, write_stream)
        self._session = await self._session_cm.__aenter__()
        await self._session.initialize()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def _call_tool_async(self, name: str, /, **kwargs: Any) -> str:
        assert self._session is not None
        result = await self._session.call_tool(name, arguments=kwargs)
        if not result.content:
            return ""
        content = result.content[0]
        if isinstance(content, TextContent):
            return content.text
        return ""

    def call_tool(self, name: str, /, **kwargs: Any) -> str:
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
        def wrapper(**kwargs: Any) -> str:
            return self.call_tool(tool_name, **kwargs)
        wrapper.__name__ = tool_name
        return wrapper

    def close(self) -> None:
        async def _shutdown() -> None:
            if self._session_cm:
                await self._session_cm.__aexit__(None, None, None)
            if self._stdio_cm:
                await self._stdio_cm.__aexit__(None, None, None)

        future = asyncio.run_coroutine_threadsafe(_shutdown(), self._loop)
        future.result()
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=2)

    def list_tools(self) -> Any:
        if self._session is None:
            return {}

        future = asyncio.run_coroutine_threadsafe(
            self._session.list_tools(), self._loop
        )
        return future.result().tools
