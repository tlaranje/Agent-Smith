from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import TextContent
from typing import Callable, Any
import concurrent.futures
import threading
import asyncio
import os


class MCPClient:
    def __init__(
        self, command: str | None = None, args: list[str] | None = None,
        env: dict | None = None, url: str | None = None
    ) -> None:
        if not command and not url:
            raise ValueError("MCPClient requires either command or url")

        self._command = command
        self._args = args or []
        self._env = env if env is not None else dict(os.environ)
        self._url = url
        self._session: ClientSession | None = None
        self._connect_error: Exception | None = None

        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        self._queue: asyncio.Queue = asyncio.run_coroutine_threadsafe(
            self._make_queue(), self._loop
        ).result()

        self._ready = threading.Event()
        self._worker_future = asyncio.run_coroutine_threadsafe(
            self._worker(), self._loop
        )

        self._ready.wait(timeout=30)
        if self._connect_error is not None:
            raise self._connect_error

    async def _make_queue(self) -> asyncio.Queue:
        return asyncio.Queue()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    async def _worker(self) -> None:
        stdio_cm = http_cm = session_cm = None
        try:
            if self._url:
                http_cm = streamablehttp_client(self._url)
                read_stream, write_stream, _ = await http_cm.__aenter__()
            else:
                assert self._command is not None
                server_params = StdioServerParameters(
                    command=self._command, args=self._args, env=self._env,
                )
                stdio_cm = stdio_client(server_params)
                read_stream, write_stream = await stdio_cm.__aenter__()

            session_cm = ClientSession(read_stream, write_stream)
            self._session = await session_cm.__aenter__()
            await self._session.initialize()
        except Exception as e:
            self._connect_error = e
            self._ready.set()
            return
        finally:
            if self._connect_error is None:
                self._ready.set()

        try:
            while True:
                item = await self._queue.get()
                if item is None:
                    break
                coro, fut = item
                try:
                    result = await coro
                    if not fut.done():
                        fut.set_result(result)
                except Exception as e:
                    if not fut.done():
                        fut.set_exception(e)
        finally:
            if session_cm:
                await session_cm.__aexit__(None, None, None)
            if stdio_cm:
                await stdio_cm.__aexit__(None, None, None)
            if http_cm:
                await http_cm.__aexit__(None, None, None)

    def _submit(self, coro) -> Any:
        fut: Any = concurrent.futures.Future()

        async def _enqueue():
            await self._queue.put((coro, fut))

        asyncio.run_coroutine_threadsafe(_enqueue(), self._loop).result()
        return fut.result()

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
        allowed_tools_name = [t.name for t in self.list_tools()]
        if name not in allowed_tools_name:
            return (
                f"ERROR:\nUnknown tool name: '{name}'\n\n"
                f"Available tools:\n" + "\n".join(f"- {t}" for t in allowed_tools_name)
            )
        try:
            return self._submit(self._call_tool_async(name, **kwargs))
        except TypeError as e:
            return f"ERROR:\nInvalid arguments for tool '{name}'.\nDetails: {str(e)}\nReceived args: {kwargs}"
        except Exception as e:
            return f"ERROR:\nTool execution failed.\nTool: {name}\nException: {str(e)}"

    def list_tools(self) -> Any:
        if self._session is None:
            return []
        return self._submit(self._session.list_tools()).tools

    def discover_tools(self) -> dict[str, Callable[..., str]]:
        if self._session is None:
            return {}
        tools_response = self._submit(self._session.list_tools())
        return {t.name: self._make_wrapper(t.name) for t in tools_response.tools}

    def _make_wrapper(self, tool_name: str) -> Callable[..., str]:
        def wrapper(**kwargs: Any) -> str:
            return self.call_tool(tool_name, **kwargs)
        wrapper.__name__ = tool_name
        return wrapper

    def close(self) -> None:
        async def _signal_shutdown():
            await self._queue.put(None)

        asyncio.run_coroutine_threadsafe(_signal_shutdown(), self._loop).result()
        try:
            self._worker_future.result(timeout=5)
        except Exception:
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)

    def generate_manual(self, exclude: set[str] | None = None) -> str:
        exclude = exclude or set()
        tools = [t for t in self.list_tools() if t.name not in exclude]

        if not tools:
            return "No tools are currently available."

        sections = [
            "## Available Tools", "", "Call tools as Python functions.",
            "Example:", "result = tool_name(arg=value)", "",
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
                example = ", ".join(f"{name}=..." for name in props)
                sections.append("")
                sections.append(f"Example: result = {tool.name}({example})")
            else:
                sections.append("")
                sections.append("Arguments: none")
                sections.append("")
                sections.append(f"Example: result = {tool.name}()")

            sections.append("")

        return "\n".join(sections).strip()
