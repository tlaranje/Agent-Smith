from student.parser import MBPPTaskInput
from student.sandbox import Sandbox
from student.agent import MBPPAgent
from student.APIs import get_llms
from rich import print
import traceback
import docker
import sys


def main() -> None:
    try:
        sandbox = Sandbox("agent_sandbox:latest")

        task = MBPPTaskInput().from_file("data/input/task.json")

        agent = MBPPAgent(sandbox, get_llms())

        print(f"[green]{agent.solve(task)}[green]")
    except (Exception, docker.errors.BuildError) as e:
        traceback.print_exc()
        print(f"[bold red]{e}[/bold red]", file=sys.stderr)


if __name__ == "__main__":
    main()
