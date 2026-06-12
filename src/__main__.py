from src.sandbox import Sandbox
from rich import print
import traceback
import docker
import fire


class Main:
    def __init__(self, image_name: str = "agent_sandbox:latest") -> None:
        self.sandbox = Sandbox(image_name)

    def build_container(self, path: str = ".") -> None:
        self.sandbox.build(path)


def main() -> None:
    try:
        fire.Fire(Main)
    except (Exception, docker.errors.BuildError) as e:
        traceback.print_exc()
        print(f"[bold red]{e}[/bold red]")


if __name__ == "__main__":
    main()
