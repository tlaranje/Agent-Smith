from src.parser import MBPPTaskInput
from src.sandbox import Sandbox
from src.agent import CodeAgent
from rich import print
import traceback
import docker
import sys


def main() -> None:
    try:
        args = sys.argv[1:]
        task_file = (
            args[0] if args and not args[0].startswith("-") else "task.json"
        )

        sandbox = Sandbox(task_file, "agent_sandbox:latest")

        task = MBPPTaskInput().from_file("data/input/task.json")

        agent = CodeAgent(sandbox)

        sandbox.build()
        sandbox.start()
        agent.give_task(task)
        sandbox.stop()
    except (Exception, docker.errors.BuildError) as e:
        traceback.print_exc()
        print(f"[bold red]{e}[/bold red]")


""" def main() -> None:
    try:
        mbp = MBPPTaskInput()
        print(mbp.from_file("data/input/task.json"))
    except (Exception, docker.errors.BuildError) as e:
        traceback.print_exc()
        print(f"[bold red]{e}[/bold red]") """


if __name__ == "__main__":
    main()
