from src.parser import MBPPTaskInput
from src.sandbox import Sandbox
from src.agent import MBPPAgent
from src.APIs import get_llms
from pathlib import Path
import argparse
import json


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

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        agent: MBPPAgent = MBPPAgent(
            sandbox, get_llms(args.model_name, args.provider_url)
        )
        solution = agent.solve(task)
        output_data = solution.model_dump_json(indent=4)
    except Exception as e:
        # Always emit schema-valid JSON after an API timeout or provider
        # failure, so the exam can report execution failure accurately.
        output_data = json.dumps({
            "task_id": str(task.task_id),
            "benchmark": "mbpp",
            "success": False,
            "solution": "",
            "system_prompt": "",
            "iterations": 0,
            "total_requests": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_time_seconds": 0.0,
            "steps": [],
            "error": str(e),
        }, indent=4)
    finally:
        try:
            sandbox.stop()
        except Exception:
            pass

    with open(output_path, "w") as fd:
        fd.write(output_data)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(e)
