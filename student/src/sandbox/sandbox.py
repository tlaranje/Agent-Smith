from .sandbox_config import SandboxConfig
from typing import Any
from rich import print
import docker
import io
import os


class Sandbox:
    def __init__(
        self, task_file: str = "task.json",
        image: str = "agent_sandbox:latest"
    ) -> None:
        self.image = image
        self.client = docker.from_env()
        self.container: Any = None
        self.task_file = task_file

    def execute(self, code: str) -> tuple[str, bool]:
        if not SandboxConfig().validate_code(code):
            return "", False

        with open("../data/docker/setup.py", "r") as f:
            setup = f.read()

        full_code = setup + "\n" + code

        with open("../data/docker/code.py", "w", encoding="utf-8") as f:
            f.write(full_code)

        res = self.container.exec_run("python3 /sandbox/code.py")
        output = res.output.decode("utf-8")

        check = self.container.exec_run("python3 /tmp/agent/final_result.py")

        if check.exit_code == 0:
            self.container.exec_run("rm /tmp/agent/final_result.py")
            return output, True

        return output, False

    # Docker
    def build(self, path: str = ".") -> None:
        dockerfile_path = os.path.join(path, "Dockerfile")
        if not os.path.exists(dockerfile_path):
            raise FileNotFoundError(
                f"Dockerfile not found in: {os.path.abspath(path)}"
            )

        abs_path = os.path.abspath(dockerfile_path)
        print(
            f"[bold blue][*][/bold blue] Reading Dockerfile from: "
            f"[yellow]{abs_path}[/yellow]"
        )
        try:
            with open(dockerfile_path, "r", encoding="utf-8") as f:
                dockerfile_content = f.read()

            print(
                f"[bold blue][*][/bold blue] Building Docker image "
                f"'[cyan]{self.image}[/cyan]'"
            )

            self.client.images.build(
                fileobj=io.BytesIO(dockerfile_content.encode("utf-8")),
                path=None,
                tag=self.image,
                rm=True,
                forcerm=True,
            )
            print(
                f"[bold green][+][/bold green] Docker image "
                f"'[cyan]{self.image}[/cyan]' built successfully!"
            )

        except docker.errors.BuildError as e:
            print(
                "[bold red][-] Critical error during Docker build:[/bold red]"
            )
            for log in e.build_log:
                if "stream" in log:
                    print(f"[red]>>> {log['stream'].strip()}[/red]")
            raise e

        except Exception as e:
            print(
                f"[bold red][-] Unexpected error during Docker daemon build: "
                f"{e}[/bold red]"
            )
            raise e

    def start(self) -> None:
        if not self.container:
            print(
                f"[bold blue][*][/bold blue] Starting sandbox container from "
                f"image '[cyan]{self.image}[/cyan]'..."
            )
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
                c_id = self.container.short_id
                print(
                    f"[bold green][+][/bold green] Sandbox online. "
                    f"Container ID: [bold magenta]{c_id}[/bold magenta]"
                )
            except Exception as e:
                print(
                    f"[bold red][-] Failed to start sandbox container: "
                    f"{e}[/bold red]"
                )
                raise e
        else:
            print(
                "[bold yellow][!] Sandbox container is already "
                "running.[/bold yellow]"
            )

    def enter(self) -> None:
        if not self.container:
            print(
                "[bold red][-] Container is not running. "
                "Cannot enter sandbox.[/bold red]"
            )
            return

        c_id = self.container.short_id
        print(
            f"\n[bold green][>>>] Entering Sandbox ({c_id}). "
            f"Type 'exit' to log out.[/bold green]"
        )
        print("[bold green]" + "=" * 60 + "[/bold green]")

        os.system(f"docker exec -it {self.container.id} bash")

        print("[bold green]" + "=" * 60 + "[/bold green]")
        print(
            "[bold green][<<<] Exited Sandbox. "
            "Returned to host system.[/bold green]\n"
        )

    def stop(self) -> None:
        if self.container:
            c_id = self.container.short_id
            print(
                f"[bold blue][*][/bold blue] Stopping sandbox container "
                f"([bold magenta]{c_id}[/bold magenta])..."
            )
            try:
                self.container.stop()
                self.container = None
                print(
                    "[bold green][+][/bold green] Sandbox container "
                    "stopped and removed successfully."
                )
            except Exception as e:
                print(
                    f"[bold red][-] Error while stopping container: "
                    f"{e}[/bold red]"
                )
                raise e
        else:
            print(
                "[bold yellow][!] No active sandbox container "
                "to stop.[/bold yellow]"
            )
