from ..mcp import MCPClient
from pathlib import Path
from typing import Any
import contextlib
import docker
import io
import os


class Sandbox:
    def __init__(
        self, agent: str = "MBPP", image: str = "agent_sandbox:latest"
    ) -> None:
        self.image = image
        self.agent = agent
        self.client = docker.from_env()
        self.container: Any = None
        self.mcp_client: MCPClient | None = None

        self._root_path = Path(__file__).parent.parent.parent.parent

        # MBPP: MCP server não precisa de aceder ao container Docker,
        # por isso pode ser lançado imediatamente.
        # SWE_BENCH: o MCP server precisa do container ID, que só existe
        # depois de start()/pull(). O MCPClient é criado em _start_mcp_client().
        if agent == "MBPP":
            server_env = dict(os.environ)
            server_env["IS_MCP_SERVER"] = "1"
            self.mcp_client = MCPClient(
                command="uv",
                args=["run", "python", f"{self._root_path}/mcp_tools_mbpp.py"],
                env=server_env
            )

    def get_patch(self) -> str:
        """Retrieve the unified git diff of all changes made to /testbed."""
        out, _ = self._exec(
            "cd /testbed && git -c core.fileMode=false diff"
        )
        return out

    def _final_answer(self, answer_string: str):
        os.makedirs("/tmp/agent", exist_ok=True)
        with open("/tmp/agent/final_result.py", "w", encoding="utf-8") as f:
            f.write(answer_string)

    def _restricted_builtins(self) -> dict:
        import builtins
        safe_builtins = {}
        allowed = [
            'abs', 'all', 'any', 'bin', 'bool', 'chr', 'dict', 'divmod',
            'enumerate', 'filter', 'float', 'format', 'hash', 'hex', 'id',
            'int', 'isinstance', 'issubclass', 'iter', 'len', 'list', 'map',
            'max', 'min', 'next', 'oct', 'ord', 'pow', 'print', 'range',
            'repr', 'reversed', 'round', 'set', 'slice', 'sorted', 'str',
            'sum', 'tuple', 'type', 'zip', 'Exception', 'ValueError',
            'TypeError', 'AssertionError', 'IndexError', 'KeyError'
        ]
        for name in allowed:
            if hasattr(builtins, name):
                safe_builtins[name] = getattr(builtins, name)
        return safe_builtins

    def build_namespace(self) -> dict:
        namespace = {"__builtins__": self._restricted_builtins()}
        namespace.update(self.mcp_client.discover_tools())
        namespace["final_answer"] = self._final_answer
        return namespace

    def execute(
        self, code: str, test_list: list[str] | None = None
    ) -> tuple[str, bool]:
        if not SandboxConfig().validate_code(code):
            return (
                "[bold red]Code rejected: disallowed import, "
                "file path, or use of eval/exec.[/bold red]",
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

        stdout_capture = io.StringIO()

        res = self.container.exec_run("python3 /sandbox/code.py")
        output = res.output.decode("utf-8")

        if res.exit_code != 0:
            # print(
            #     "[bold red][!] The execution failed or failed "
            #     "in a test assert:[/bold red]"
            # )
            # print(f"[red]{output.strip()}[/red]")
            return output, False

        # Exit code 0 only means the script ran without raising.
        # It does NOT mean final_answer() was called. We confirm that
        # by checking whether final_result.py was written inside the
        # container during this run.
        check = self.container.exec_run(
            "test -f /tmp/agent/final_result.py"
        )

        if check.exit_code == 0:
            answer_res = self.container.exec_run(
                "cat /tmp/agent/final_result.py"
            )
            answer = answer_res.output.decode("utf-8")
            self.container.exec_run("rm -f /tmp/agent/final_result.py")
            return answer, True

        # Script ran fine (e.g. tests passed) but final_answer() was
        # never called -> not done yet, keep iterating.
        return output, False

    # Docker
    def build(self, path: str = ".") -> None:
        dockerfile_path = os.path.join(path, "Dockerfile")
        if not os.path.exists(dockerfile_path):
            raise FileNotFoundError(
                f"Dockerfile not found in: {os.path.abspath(path)}"
            )

        # abs_path = os.path.abspath(dockerfile_path)
        # print(
        #     f"[bold blue][*][/bold blue] Reading Dockerfile from: "
        #     f"[yellow]{abs_path}[/yellow]"
        # )
        try:
            with open(dockerfile_path, "r", encoding="utf-8") as f:
                dockerfile_content = f.read()

            # print(
            #     f"[bold blue][*][/bold blue] Building Docker image "
            #     f"'[cyan]{self.image}[/cyan]'"
            # )

            self.client.images.build(
                fileobj=io.BytesIO(dockerfile_content.encode("utf-8")),
                path=None,
                tag=self.image,
                rm=True,
                forcerm=True,
            )
            # print(
            #     f"[bold green][+][/bold green] Docker image "
            #     f"'[cyan]{self.image}[/cyan]' built successfully!"
            # )

        except docker.errors.BuildError as e:
            # print(
            #    "[bold red][-] Critical error during Docker build:[/bold red]"
            # )
            # for log in e.build_log:
            #     if "stream" in log:
            #         print(f"[red]>>> {log['stream'].strip()}[/red]")
            raise e

        except Exception as e:
            # print(
            #    f"[bold red][-] Unexpected error during Docker daemon build: "
            #     f"{e}[/bold red]"
            # )
            raise e

    def _start_mcp_client(self) -> None:
        """Lança o MCPClient para SWE_BENCH depois do container existir.
        Passa SANDBOX_CONTAINER_ID para o subprocesso MCP server poder
        ligar-se ao container já criado via docker.from_env()."""
        if self.agent != "SWE_BENCH" or self.mcp_client is not None:
            return
        server_env = dict(os.environ)
        server_env["IS_MCP_SERVER"] = "1"
        server_env["SANDBOX_CONTAINER_ID"] = self.container.id
        self.mcp_client = MCPClient(
            command="uv",
            args=["run", "python", f"{self._root_path}/mcp_tools_swe_bench.py"],
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
                    volumes={os.path.join(os.getcwd(), "../data/docker"): {
                        "bind": "/sandbox",
                        "mode": "rw"
                    }}
                )

                root_path = Path(__file__).parent.parent.parent.parent
                server_env = dict(os.environ)
                server_env["IS_MCP_SERVER"] = "1"
                server_env["DOCKER_CONTAINER_ID"] = self.container.id

                if self.agent == "MBPP":
                    self.mcp_client = MCPClient(
                        command="uv",
                        args=[
                            "run", "python", f"{root_path}/mcp_tools_mbpp.py"
                        ],
                        env=server_env
                    )
                elif self.agent == "SWE_BENCH":
                    self.mcp_client = MCPClient(
                        command="uv",
                        args=[
                            "run", "python",
                            f"{root_path}/mcp_tools_swe_bench.py"
                        ],
                        env=server_env
                    )
            except Exception as e:
                raise e
        # else:
            # print(
            #     "[bold yellow][!] Sandbox container is already "
            #     "running.[/bold yellow]"
            # )
        self._start_mcp_client()

    def pull(self) -> None:
        """Pull a pre-built image from Docker Hub"""
        try:
            self.client.images.pull(self.image)
            print("[bold green][+][/bold green] Image pulled successfully.")
        except docker.errors.ImageNotFound:
            raise RuntimeError(f"Image not found on Docker Hub: {self.image}")
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
        """Run a bash command inside the container, same pattern as your
        MBPP exec_run."""
        result = self.container.exec_run(["bash", "-c", cmd])
        output = result.output.decode("utf-8") if result.output else ""
        return output, result.exit_code
