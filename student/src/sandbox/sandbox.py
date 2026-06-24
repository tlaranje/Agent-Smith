from .sandbox_config import SandboxConfig
from typing import Any
from rich import print
import tarfile
import docker
import io
import os


class Sandbox:
    def __init__(self, image: str = "agent_sandbox:latest") -> None:
        self.image = image
        self.client = docker.from_env()
        self.container: Any = None

    def execute(
        self, code: str, test_list: list[str] | None = None
    ) -> tuple[str, bool]:
        try:
            SandboxConfig().validate_code(code)
        except Exception as e:
            return (
                f"[bold red]{e}[/bold red]", False
            )

        self.container.exec_run("rm -f /tmp/agent/final_result.py")

        with open("../data/docker/setup.py", "r") as f:
            setup = f.read()

        full_code = setup + "\n" + code

        if test_list:
            full_code += "\n\n# --- AUTOMATED TESTS ---\n"
            for test in test_list:
                full_code += f"{test}\n"

        with open("../data/docker/code.py", "w", encoding="utf-8") as f:
            f.write(full_code)

        res = self.container.exec_run("python3 /sandbox/code.py")
        output = res.output.decode("utf-8")

        if res.exit_code != 0:
            # print(
            #     "[bold red][!] The execution failed or failed "
            #     "in a test assert:[/bold red]"
            # )
            # print(f"[red]{output.strip()}[/red]")
            return output, False
        elif res.exit_code == 0:
            return '"""\n' + code + '"""', True

        check = self.container.exec_run("python3 /tmp/agent/final_result.py")
        # with open("tmp/agent/final_result.py", "r") as fd:
        #     data = fd.read()
        if check.exit_code == 0:
            self.container.exec_run("rm -f /tmp/agent/final_result.py")
            return output, True

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

    def start(self) -> None:
        if not self.container:
            # print(
            #    f"[bold blue][*][/bold blue] Starting sandbox container from "
            #     f"image '[cyan]{self.image}[/cyan]'..."
            # )
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
                # c_id = self.container.short_id
                # print(
                #     f"[bold green][+][/bold green] Sandbox online. "
                #     f"Container ID: [bold magenta]{c_id}[/bold magenta]"
                # )
            except Exception as e:
                # print(
                #     f"[bold red][-] Failed to start sandbox container: "
                #     f"{e}[/bold red]"
                # )
                raise e
        # else:
            # print(
            #     "[bold yellow][!] Sandbox container is already "
            #     "running.[/bold yellow]"
            # )

    def pull(self) -> None:
        """Pull a pre-built image from Docker Hub"""
        print(
            f"[bold blue][*][/bold blue] Pulling image '[cyan]{self.image}[/cyan]'...")
        try:
            self.client.images.pull(self.image)
            print("[bold green][+][/bold green] Image pulled successfully.")
        except docker.errors.ImageNotFound:
            raise RuntimeError(f"Image not found on Docker Hub: {self.image}")
        except Exception as e:
            raise e

    def enter(self) -> None:
        if not self.container:
            # print(
            #     "[bold red][-] Container is not running. "
            #     "Cannot enter sandbox.[/bold red]"
            # )
            return

        # c_id = self.container.short_id
        # print(
        #     f"\n[bold green][>>>] Entering Sandbox ({c_id}). "
        #     f"Type 'exit' to log out.[/bold green]"
        # )
        # print("[bold green]" + "=" * 60 + "[/bold green]")

        os.system(f"docker exec -it {self.container.id} bash")

        # print("[bold green]" + "=" * 60 + "[/bold green]")
        # print(
        #     "[bold green][<<<] Exited Sandbox. "
        #     "Returned to host system.[/bold green]\n"
        # )

    def stop(self) -> None:
        if self.container:
            # c_id = self.container.short_id
            # print(
            #     f"[bold blue][*][/bold blue] Stopping sandbox container "
            #     f"([bold magenta]{c_id}[/bold magenta])..."
            # )
            try:
                self.container.stop()
                self.container = None
                # print(
                #     "[bold green][+][/bold green] Sandbox container "
                #     "stopped and removed successfully."
                # )
            except Exception as e:
                # print(
                #     f"[bold red][-] Error while stopping container: "
                #     f"{e}[/bold red]"
                # )
                raise e
        # else:
            # print(
            #     "[bold yellow][!] No active sandbox container "
            #     "to stop.[/bold yellow]"
            # )

    def _exec(self, cmd: str) -> tuple[str, int]:
        """Run a bash command inside the container, same pattern as your
        MBPP exec_run."""
        result = self.container.exec_run(["bash", "-c", cmd])
        output = result.output.decode("utf-8") if result.output else ""
        return output, result.exit_code

    def _write_file(self, container_path: str, content: str) -> None:
        """
        Write a file into the container using put_archive (tar stream).
        Avoids all shell escaping issues — same idea as your MBPP sandbox
        writing code.py to the volume, but works without a shared volume.
        """
        dir_path = os.path.dirname(container_path)
        filename = os.path.basename(container_path)

        content_bytes = content.encode("utf-8")
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode="w") as tar:
            info = tarfile.TarInfo(name=filename)
            info.size = len(content_bytes)
            tar.addfile(info, io.BytesIO(content_bytes))
        tar_stream.seek(0)

        self.container.put_archive(dir_path, tar_stream)

    def read_file(
        self,
        filepath: str,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> str:
        """
        Read file with line numbers in cat -n format:
            1  line one
            2  line two
        """
        out, code = self._exec(f"cat {filepath}")
        if code != 0:
            return f"ERROR: Could not read {filepath}: {out}"

        lines = out.splitlines()

        start = (start_line - 1) if start_line else 0
        end = end_line if end_line else len(lines)
        selected = lines[start:end]

        result = []
        for i, line in enumerate(selected, start=start + 1):
            result.append(f"{i:6}\t{line}")

        return "\n".join(result)

    def edit_file(self, filepath: str, old_str: str, new_str: str) -> str:
        """Replace exact old_str with new_str in a file."""
        out, code = self._exec(f"cat {filepath}")
        if code != 0:
            return f"ERROR: Could not read {filepath}: {out}"

        if old_str not in out:
            return (
                f"ERROR: old_str not found in {filepath}. "
                "Make sure it matches exactly including "
                "indentation and whitespace."
            )
        if out.count(old_str) > 1:
            return (
                f"ERROR: old_str matches {out.count(old_str)} locations in {
                    filepath}. "
                "Make it more specific."
            )

        new_content = out.replace(old_str, new_str, 1)
        self._write_file(filepath, new_content)
        return f"OK: {filepath} updated successfully."

    def list_files(self, directory: str, pattern: str = "*") -> str:
        """List files in a directory matching a pattern."""
        out, code = self._exec(
            f"find {directory} -name '{pattern}' -type f | sort")
        if code != 0:
            return f"ERROR: Could not list files in {directory}: {out}"
        return out or "No files found."

    def search_code(self, pattern: str, file_pattern: str = "*.py") -> str:
        """
        grep-like search. Output format:
            /absolute/path_to_file.py:<line>:<match>
            /absolute/path_to_other_file.py:<line>:<match>
        """
        cmd = f"grep -rn --include='{file_pattern}' '{pattern}' /testbed"
        out, _ = self._exec(cmd)
        return out or "No matches found."

    def search_function_or_class_definition_in_code(self, name: str) -> str:
        """
        Find def <name> or class <name>. Output format same as search_code:
            /absolute/path_to_file.py:<line>:<match>
        """
        cmd = f"grep -rn --include='*.py' -E '^(def {name}|class {
            name})' /testbed"
        out, _ = self._exec(cmd)

        if not out:
            cmd = f"grep -rn --include='*.py' -E '(def {name}|class {
                name})\\b' /testbed"
            out, _ = self._exec(cmd)

        return out or f"No definition found for '{name}'."

    def find_references(
        self,
        name: str,
        filepath: str | None = None,
        line: int | None = None,
    ) -> str:
        """
        Find all usages of a symbol. Output format same as search_code:
            /absolute/path_to_file.py:<line>:<match>
        """
        search_path = filepath if filepath else "/testbed"
        cmd = f"grep -rn --include='*.py' '\\b{name}\\b' {search_path}"
        out, _ = self._exec(cmd)
        return out or f"No references found for '{name}'."

    def run_tests(self) -> str:
        """Execute the evaluation script stored at start() time."""
        self._write_file("/tmp/eval_script.sh", self.eval_script)
        out, code = self._exec("bash /tmp/eval_script.sh")
        return f"Exit code: {code}\n{out}"

    def get_patch(self) -> str:
        """Retrieve the unified git diff of all changes made to /testbed."""
        out, _ = self._exec("cd /testbed && git -c core.fileMode=false diff")
        return out

    def run_command(self, command: str, workdir: str = "/testbed") -> str:
        """
        Execute a shell command in the specified working directory.
        Returns stdout, stderr, and exit code.
        """
        out, code = self._exec(f"cd {workdir} && {command}")
        return f"Exit code: {code}\nOutput:\n{out}"
