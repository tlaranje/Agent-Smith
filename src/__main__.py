from src.sandbox import Sandbox
from rich import print
import traceback
import docker
import fire
import sys


class Main:
    def __init__(
        self, task_file: str = "task.json",
        image_name: str = "agent_sandbox:latest"
    ) -> None:
        self.sandbox = Sandbox(task_file, image_name)

    def build(self, path: str = ".") -> None:
        self.sandbox.build(path)

    def start(self) -> None:
        self.sandbox.start()

    def enter(self) -> None:
        self.sandbox.start()

        self.sandbox.enter()

    def stop(self) -> None:
        self.sandbox.stop()


def main() -> None:
    try:
        args = sys.argv[1:]
        task_file = (
            args[0] if args and not args[0].startswith("-") else "task.json"
        )
        m = Main(task_file=task_file)

        if len(args) <= 1:
            m.sandbox.build()
            m.sandbox.start()
            # m.sandbox.enter()
            m.sandbox.stop()
        else:
            fire.Fire(m)
    except (Exception, docker.errors.BuildError) as e:
        traceback.print_exc()
        print(f"[bold red]{e}[/bold red]")


if __name__ == "__main__":
    main()
