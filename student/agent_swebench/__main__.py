import argparse
from pathlib import Path
from student.src.agent import SWEBenchAgent
from student.src.parser import SWEBenchTaskInput
from student.src.sandbox import Sandbox
from student.src.APIs import get_llms


def main() -> None:
    """
    Run the SWE-Bench agent end-to-end.

    Raises:
        FileNotFoundError: If the task file does not exist.
        OSError: If the output file cannot be written.
    """
    parser = argparse.ArgumentParser(
        description="SWE Bench Agent"
    )
    parser.add_argument(
        "--task-file", default="../data/input/swebench_task.json"
    )
    parser.add_argument(
        "--output", default="../data/output/swebench_task_solution.json"
    )
    parser.add_argument(
        "--model-name", default="gemini-2.5-flash-lite"
    )
    parser.add_argument(
        "--provider-url", default=None
    )
    args = parser.parse_args()
    task: SWEBenchTaskInput = SWEBenchTaskInput.from_file(
        args.task_file
    )

    # Sandbox is built from the task's own Docker image, since
    # SWE-Bench tasks require the original repo environment.
    sandbox: Sandbox = Sandbox("SWE_BENCH", task.docker_image)

    # max_iterations caps the number of agent steps to avoid
    # infinite loops when a fix is never found.
    agent: SWEBenchAgent = SWEBenchAgent(
        get_llms(args.model_name, args.provider_url),
        sandbox, max_iterations=30
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
