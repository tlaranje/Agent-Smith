from student.src.parser import MBPPTaskInput
from student.src.sandbox import Sandbox
from student.src.agent import MBPPAgent
from student.src.APIs import get_llms
from pathlib import Path
import argparse


def main() -> None:
    """
    Run the MBPP agent end-to-end.

    Raises:
        FileNotFoundError: If the task file does not exist.
        OSError: If the output file cannot be written.
    """
    parser = argparse.ArgumentParser(
        description="MBPP Agent"
    )
    parser.add_argument(
        "--task-file", default="../data/input/mbpp_task.json"
    )
    parser.add_argument(
        "--output", default="../data/output/mbpp_task_solution.json"
    )
    parser.add_argument(
        "--model-name", default="gemini-2.5-flash-lite"
    )
    parser.add_argument(
        "--provider-url", default=None
    )
    args = parser.parse_args()
    task: MBPPTaskInput = MBPPTaskInput.from_file(
        args.task_file
    )

    # Build and start an isolated sandbox to run the agent's
    # generated code safely.
    sandbox = Sandbox("MBPP")
    sandbox.build("..")
    sandbox.start()

    agent: MBPPAgent = MBPPAgent(
        sandbox, get_llms(args.model_name, args.provider_url)
    )
    solution = agent.solve(task)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as fd:
        fd.write(solution.model_dump_json(indent=4))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(e)
