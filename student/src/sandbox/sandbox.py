from docker.errors import BuildError, ImageNotFound
from .sandbox_config import SandboxConfig
from ..mcp import MCPClient
from pathlib import Path
from typing import Any
from rich import print
import tarfile
import base64
import docker
import shlex
import io
import os


class Sandbox:
    def __init__(
        self, agent: str = "MBPP", image: str = "agent_sandbox:latest",
        config: SandboxConfig | None = None,
    ) -> None:
        self.image = image
        self.agent = agent
        self.config = config if config is not None else SandboxConfig()
        self.client = docker.from_env()
        self.container: Any = None
        self.mcp_client: MCPClient | None = None
        self.eval_script: str = ""

        self._root_path = Path(__file__).parent.parent.parent.parent

    @classmethod
    def attach(
        cls, agent: str, container_id: str,
        config: SandboxConfig | None = None,
        image: str = "agent_sandbox:latest",
    ) -> "Sandbox":
        """
        Reconnect to an already-running container (used inside the
        MCP tool server subprocess, which does not manage the
        container's lifecycle itself).
        """
        instance = cls(agent=agent, image=image, config=config)
        instance.container = instance.client.containers.get(container_id)
        return instance

    def get_patch(self) -> str:
        """Return the current git diff of /testbed as a string."""
        out, _ = self._exec(
            "cd /testbed && git -c core.fileMode=false diff"
        )
        return out

    def _final_answer(self, answer_string: str) -> None:
        """
        Persist the agent's final answer to a fixed path so it
        can be retrieved after the sandboxed code finishes running.
        """
        os.makedirs("/tmp/agent", exist_ok=True)
        with open(
            "/tmp/agent/final_result.py", "w", encoding="utf-8"
        ) as f:
            f.write(answer_string)

    def _restricted_builtins(self) -> dict:
        """
        Build a minimal, safe subset of __builtins__ for use as
        the namespace of sandboxed code (no I/O, no import, no
        exec/eval-related builtins).
        """
        import builtins
        safe_builtins = {}
        allowed = [
            'abs', 'all', 'any', 'bin', 'bool', 'chr', 'dict', 'divmod',
            'enumerate', 'filter', 'float', 'format', 'hash', 'hex', 'id',
            'int', 'isinstance', 'issubclass', 'iter', 'len', 'list',
            'map', 'max', 'min', 'next', 'oct', 'ord', 'pow', 'print',
            'range', 'repr', 'reversed', 'round', 'set', 'slice',
            'sorted', 'str', 'sum', 'tuple', 'type', 'zip', 'Exception',
            'ValueError', 'TypeError', 'AssertionError', 'IndexError',
            'KeyError',
        ]
        for name in allowed:
            if hasattr(builtins, name):
                safe_builtins[name] = getattr(builtins, name)
        return safe_builtins

    def build_namespace(self) -> dict:
        """
        Build the execution namespace exposed to sandboxed code:
        restricted builtins, the MCP tools as callables, and
        final_answer.
        """
        if self.mcp_client is None:
            return {}
        namespace: dict[str, Any] = {
            "__builtins__": self._restricted_builtins()
        }
        namespace.update(self.mcp_client.discover_tools())
        namespace["final_answer"] = self._final_answer
        return namespace

    def _write_code_to_container(self, code: str, path: str) -> None:
        """
        Write `code` into the running container at `path` by
        streaming an in-memory tar archive (avoids touching the
        host filesystem).
        """
        directory = os.path.dirname(path)
        filename = os.path.basename(path)

        tarstream = io.BytesIO()
        with tarfile.open(fileobj=tarstream, mode="w") as tar:
            data = code.encode("utf-8")
            tarinfo = tarfile.TarInfo(name=filename)
            tarinfo.size = len(data)
            tar.addfile(tarinfo, io.BytesIO(data))
        tarstream.seek(0)

        self.container.put_archive(directory, tarstream)

    def _write_file(self, filepath: str, content: str) -> None:
        """
        Alias used by the SWE-bench tools (mkdir -p first, since the
        target directory may not exist yet, e.g. /tmp/eval_script.sh).
        """
        if not filepath.startswith("/"):
            filepath = f"/testbed/{filepath}"
        directory = os.path.dirname(filepath)
        self._exec(f"mkdir -p {directory}")
        self._write_code_to_container(content, filepath)

    def execute(
        self, code: str, test_list: list[str] | None = None
    ) -> tuple[str, bool]:
        """
        Validate, inject helpers into, and run a piece of code
        inside the sandboxed container.

        Args:
            code: The Python source to run.
            test_list: Optional test statements appended after the
                code (used for MBPP-style tasks).

        Returns:
            A tuple of (output, success). output is either the
            final_answer content on success, or the raw
            stdout/stderr / an error message on failure. success is
            True only if final_answer was called and the process
            exited cleanly.
        """
        if not self.config.validate_code(code):
            return (
                "Code rejected: disallowed import, "
                "file path, or use of eval/exec.",
                False,
            )

        self.container.exec_run("rm -f /tmp/agent/final_result.py")

        # Inject a final_answer() shim so the LLM's generated code
        # can "return" a result by writing to a known file, which we
        # read back afterward.
        final_answer_shim = (
            "import os as _os\n"
            "def final_answer(answer_string):\n"
            "    _os.makedirs('/tmp/agent', exist_ok=True)\n"
            "    with open('/tmp/agent/final_result.py', 'w', "
            "encoding='utf-8') as _f:\n"
            "        _f.write(answer_string)\n\n"
        )
        code = final_answer_shim + code

        if test_list:
            code += "\n\n# --- AUTOMATED TESTS ---\n"
            for test in test_list:
                code += f"{test}\n"

        self._write_code_to_container(code, "/sandbox/code.py")

        timeout = self.config.max_execution_time_seconds
        memory_kb = self.config.max_memory_mb * 1024

        # ulimit caps virtual memory; timeout caps wall-clock time,
        # both enforced inside the container itself.
        res = self.container.exec_run(
            cmd=["bash", "-lc", (
                f"ulimit -v {memory_kb}; "
                f"timeout {timeout}s python3 /sandbox/code.py"
            )],
        )

        output = res.output.decode("utf-8", errors="replace")

        # --- OUTPUT SIZE TRUNCATION CHECK ---
        # Get max limit from config if available, otherwise
        # default to 1,000,000 characters
        max_chars = getattr(self.config, "max_output_chars", 1000000)
        is_truncated = False
        if len(output) > max_chars:
            output = output[:max_chars]
            is_truncated = True

        if res.exit_code == 124:
            warn_msg = (
                f"{output}\n\n"
                f"[TIMEOUT] Execution exceeded {timeout} seconds.\n"
                "[PARTIAL OUTPUT] The execution hit the timeout. "
                "The output above is partial."
            )
            if is_truncated:
                warn_msg += (
                    "\n[TRUNCATED] The output also exceeded the "
                    f"size limit of {max_chars} characters and was cut short."
                )
            return warn_msg, False

        if res.exit_code == 137 or "MemoryError" in output:
            return (
                "[MEMORY LIMIT EXCEEDED]\n"
                f"Execution exceeded {self.config.max_memory_mb} MB.",
                False,
            )

        if res.exit_code != 0:
            warn_msg = f"[RUNTIME ERROR]\n{output}"
            if is_truncated:
                warn_msg += (
                    "\n\n[TRUNCATED] Output was truncated "
                    f"because it exceeded {max_chars} characters."
                )
            return warn_msg, False

        check = self.container.exec_run(
            "test -f /tmp/agent/final_result.py"
        )

        if check.exit_code == 0:
            answer_res = self.container.exec_run(
                "cat /tmp/agent/final_result.py"
            )
            answer = answer_res.output.decode(
                "utf-8", errors="replace"
            )
            self.container.exec_run("rm -f /tmp/agent/final_result.py")
            # Truncate final answer as well if it exceeds limits
            if len(answer) > max_chars:
                answer = (
                    f"{answer[:max_chars]}\n\n"
                    "[TRUNCATED] Final answer output was truncated "
                    f"because it exceeded {max_chars} characters."
                )
            return answer, True

        if is_truncated:
            output += (
                "\n\n[TRUNCATED] Output was truncated "
                f"because it exceeded {max_chars} characters."
            )

        return output, False

    def build(self, path: str = ".") -> None:
        """
        Build the sandbox Docker image from a Dockerfile.

        Args:
            path: Directory containing the Dockerfile.

        Raises:
            FileNotFoundError: If no Dockerfile exists at path.
            BuildError: If the Docker build itself fails.
        """
        dockerfile_path = os.path.join(path, "Dockerfile")
        if not os.path.exists(dockerfile_path):
            raise FileNotFoundError(
                f"Dockerfile not found in: {os.path.abspath(path)}"
            )

        try:
            with open(dockerfile_path, "r", encoding="utf-8") as f:
                dockerfile_content = f.read()

            # path=None means Docker only sees the Dockerfile
            # contents, not the surrounding build context/files.
            self.client.images.build(
                fileobj=io.BytesIO(dockerfile_content.encode("utf-8")),
                path=None,
                tag=self.image,
                rm=True,
                forcerm=True,
            )

        except BuildError as e:
            raise e

        except Exception as e:
            raise e

    def _start_mcp_client(self) -> None:
        """
        Launch the appropriate MCP tool server subprocess for
        this agent type, passing it the container id and config so
        it can act on the already-running sandbox.
        """
        if self.mcp_client is not None:
            return

        server_env = dict(os.environ)
        server_env["IS_MCP_SERVER"] = "1"
        server_env["DOCKER_CONTAINER_ID"] = self.container.id
        server_env["SANDBOX_CONFIG_JSON"] = self.config.model_dump_json()
        server_env["EVAL_SCRIPT_B64"] = base64.b64encode(
            self.eval_script.encode("utf-8")
        ).decode("ascii")

        if self.agent == "MBPP":
            self.mcp_client = MCPClient(
                command="uv",
                args=[
                    "run", "python",
                    f"{self._root_path}/mcp_tools_mbpp.py",
                ],
                env=server_env,
            )

        elif self.agent == "SWE_BENCH":
            self.mcp_client = MCPClient(
                command="uv",
                args=[
                    "run", "python",
                    f"{self._root_path}/mcp_tools_swebench.py",
                ],
                env=server_env,
            )

    def start(self) -> None:
        """
        Start the sandbox container (if not already running)
        with no network access and a memory cap, then start its
        MCP tool server.

        Raises:
            Exception: Re-raised if the container fails to start.
        """
        if not self.container:
            try:
                self.container = self.client.containers.run(
                    self.image,
                    command="tail -f /dev/null",
                    detach=True,
                    remove=True,
                    network_mode="none",
                    mem_limit=f"{self.config.max_memory_mb}m",
                    volumes={
                        os.path.join(
                            os.getcwd(), "../data/docker"
                        ): {
                            "bind": "/sandbox",
                            "mode": "rw",
                        }
                    },
                )
                self._start_mcp_client()
            except Exception as e:
                raise e

    def pull(self) -> None:
        """
        Pull self.image from the registry.

        Raises:
            RuntimeError: If the image is not found.
            Exception: Re-raised for any other pull failure.
        """
        try:
            print(
                f"[bold green][+][/bold green] Pulling image "
                f"'{self.image}'."
            )
            self.client.images.pull(self.image)
            print(
                "[bold green][+][/bold green] Image pulled "
                "successfully."
            )
        except ImageNotFound:
            raise RuntimeError(
                f"Image not found on Docker Hub: {self.image}"
            )
        except Exception as e:
            raise e

    def enter(self) -> None:
        """
        Open an interactive bash shell inside the running
        container (for manual debugging).
        """
        if not self.container:
            return

        os.system(f"docker exec -it {self.container.id} bash")

    def stop(self) -> None:
        """
        Stop and discard the running container, if any.

        Raises:
            Exception: Re-raised if stopping the container fails.
        """
        if self.container:
            try:
                self.container.stop()
                self.container = None
            except Exception as e:
                raise e

    def _exec(
        self, cmd: str, timeout: int | None = None
    ) -> tuple[str, int]:
        """
        Run a shell command inside the container with a wall-clock
        timeout. Memory is bounded by the container's cgroup mem_limit
        (set at container start), not by a per-command ulimit, since
        commands run here (git, pip, etc.) can need large virtual
        memory mappings without actually using much physical memory.

        Args:
            cmd: Shell command to run.
            timeout: Timeout in seconds; defaults to
                config.max_execution_time_seconds.

        Returns:
            A tuple of (output, exit_code). output has a
            "[TIMEOUT]", "[MEMORY LIMIT EXCEEDED]", or "[TRUNCATED]" note
            appended if the command exceeded the configured limits.
        """
        effective_timeout = (
            timeout
            if timeout is not None
            else self.config.max_execution_time_seconds
        )

        # Quote the command so it survives being passed as a single
        # argument to bash -c.
        wrapped_cmd = (
            f"timeout {effective_timeout}s bash -c {shlex.quote(cmd)}"
        )

        result = self.container.exec_run(["bash", "-c", wrapped_cmd])

        output = (
            result.output.decode("utf-8", errors="replace")
            if result.output
            else ""
        )

        # --- OUTPUT SIZE TRUNCATION CHECK ---
        max_chars = getattr(self.config, "max_output_chars", 1000000)
        is_truncated = False
        if len(output) > max_chars:
            output = output[:max_chars]
            is_truncated = True

        if result.exit_code == 124:
            output += (
                f"\n[TIMEOUT] Command exceeded {effective_timeout} seconds.\n"
                "[PARTIAL OUTPUT] The command execution hit "
                "the timeout; the output above is partial."
            )
        elif (
            result.exit_code == 137
            or "MemoryError" in output
        ):
            output += (
                "\n[MEMORY LIMIT EXCEEDED] "
                f"Command exceeded {self.config.max_memory_mb} MB."
            )

        if is_truncated:
            output += (
                f"\n[TRUNCATED] Tool output was truncated because it exceeded "
                f"the maximum limit of {max_chars} characters."
            )

        return output, result.exit_code
