import argparse
from pathlib import Path
from src.agent import SWEBenchAgent
from src.parser import SWEBenchTaskInput
from src.sandbox import Sandbox
from src.APIs import get_llms


def main() -> None:
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
        "--model-name", default="gemini"
    )
    parser.add_argument(
        "--provider-url"
    )
    args = parser.parse_args()
    task: SWEBenchTaskInput = SWEBenchTaskInput.from_file(
        args.task_file
    )
    sandbox: Sandbox = Sandbox("SWE_BENCH", task.docker_image)
    agent: SWEBenchAgent = SWEBenchAgent(
        get_llms(args.model_name), sandbox
    )
    solution = agent.solve(task)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as fd:
        fd.write(solution.model_dump_json(indent=4))


if __name__ == "__main__":
    main()
