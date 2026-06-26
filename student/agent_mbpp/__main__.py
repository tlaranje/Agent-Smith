from src.parser import MBPPTaskInput
from src.sandbox import Sandbox
from src.agent import MBPPAgent
from src.APIs import get_llms
from pathlib import Path
import argparse


def main() -> None:
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
        "--model-name", default="gemini"
    )
    parser.add_argument(
        "--provider-url"
    )
    args = parser.parse_args()
    task: MBPPTaskInput = MBPPTaskInput.from_file(
        args.task_file
    )

    sandbox = Sandbox("MBPP")
    sandbox.start()
    sandbox.mcp_client.call_tool(
            "set_current_task_tests", test_list=task.test_list
    )

    agent: MBPPAgent = MBPPAgent(
        sandbox, get_llms(args.model_name)
    )
    solution = agent.solve(task)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as fd:
        fd.write(solution.model_dump_json(indent=4))


if __name__ == "__main__":
    main()
