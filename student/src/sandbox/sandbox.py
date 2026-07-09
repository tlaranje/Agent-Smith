from .sandbox_config import SandboxConfig
from ..mcp import MCPClient
from pathlib import Path
from typing import Any
from rich import print
import tarfile
import base64
import docker
import io
import os


class Sandbox:
    def __init__(
        self,
        agent: str = "MBPP",
        image: str = "agent_sandbox:latest",
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

    def get_patch(self) -> str:
        out, _ = self._exec(
            "cd /testbed && git -c core.fileMode=false diff"
        )
        return out

    def _final_answer(self, answer_string: str) -> None:
        os.makedirs("/tmp/agent", exist_ok=True)
        with open(
            "/tmp/agent/final_result.py", "w", encoding="utf-8"
        ) as f:
            f.write(answer_string)

    def _restricted_builtins(self) -> dict:
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
        if self.mcp_client is None:
            return {}
        namespace: dict[str, Any] = {
            "__builtins__": self._restricted_builtins()
        }
        namespace.update(self.mcp_client.discover_tools())
        namespace["final_answer"] = self._final_answer
        return namespace

    def _write_code_to_container(self, code: str, path: str) -> None:
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

    def execute(
        self, code: str, test_list: list[str] | None = None
    ) -> tuple[str, bool]:
        if not self.config.validate_code(code):
            return (
                "Code rejected: disallowed import, "
                "file path, or use of eval/exec.",
                False,
            )

        self.container.exec_run("rm -f /tmp/agent/final_result.py")

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

        res = self.container.exec_run(
            "bash",
            [
                "-lc",
                (
                    f"ulimit -v {memory_kb}; "
                    f"timeout {timeout}s python3 /sandbox/code.py"
                ),
            ],
        )

        output = res.output.decode("utf-8", errors="replace")

        if res.exit_code == 124:
            return (
                f"{output}"
                f"[TIMEOUT]\nExecution exceeded {timeout} seconds.",
                False,
            )

        if res.exit_code == 137 or "MemoryError" in output:
            return (
                "[MEMORY LIMIT EXCEEDED]\n"
                f"Execution exceeded {self.config.max_memory_mb} MB.",
                False,
            )

        if res.exit_code != 0:
            return (
                f"[RUNTIME ERROR]\n{output}",
                False,
            )

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
            return answer, True

        return output, False

    def build(self, path: str = ".") -> None:
        dockerfile_path = os.path.join(path, "Dockerfile")
        if not os.path.exists(dockerfile_path):
            raise FileNotFoundError(
                f"Dockerfile not found in: {os.path.abspath(path)}"
            )

        try:
            with open(dockerfile_path, "r", encoding="utf-8") as f:
                dockerfile_content = f.read()

            self.client.images.build(
                fileobj=io.BytesIO(dockerfile_content.encode("utf-8")),
                path=None,
                tag=self.image,
                rm=True,
                forcerm=True,
            )

        except docker.errors.BuildError as e:
            raise e

        except Exception as e:
            raise e

    def _start_mcp_client(self) -> None:
        if self.mcp_client is not None:
            return

        server_env = dict(os.environ)
        server_env["IS_MCP_SERVER"] = "1"
        server_env["DOCKER_CONTAINER_ID"] = self.container.id
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
                    f"{self._root_path}/mcp_tools_swe_bench.py",
                ],
                env=server_env,
            )

    def start(self) -> None:
        if not self.container:
            try:
                self.container = self.client.containers.run(
                    self.image,
                    command="tail -f /dev/null",
                    detach=True,
                    remove=True,
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
        except docker.errors.ImageNotFound:
            raise RuntimeError(
                f"Image not found on Docker Hub: {self.image}"
            )
        except Exception as e:
            raise e

    def enter(self) -> None:
        if not self.container:
            return

        os.system(f"docker exec -it {self.container.id} bash")

    def stop(self) -> None:
        if self.container:
            try:
                self.container.stop()
                self.container = None
            except Exception as e:
                raise e

    def _exec(self, cmd: str) -> tuple[str, int]:
        result = self.container.exec_run(["bash", "-c", cmd])
        output = (
            result.output.decode("utf-8", errors="replace")
            if result.output
            else ""
        )
        return output, result.exit_code
