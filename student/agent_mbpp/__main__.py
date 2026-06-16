import argparse
import json
from typing import Any
from src.agent import CodeAgent
from src.parser import MBPPTaskInput
from src.sandbox import Sandbox
from src.APIs import (
    GeminiAPI,
    GroqAPI,
    CohereAPI
)


def get_llms(model_name: str) -> list[Any]:
    models = {
        "gemini": GeminiAPI,
        "groq": GroqAPI,
        "cohere": CohereAPI,
    }

    if model_name not in models:
        raise ValueError(f"LLM model '{model_name}' not supported")

    ordered_models = [models[model_name]]

    for name, model in models.items():
        if name != model_name:
            ordered_models.append(model)

    return [model() for model in ordered_models]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="MBPP Agent"
    )
    parser.add_argument(
        "--task-file", default="../data/input/task.json"
    )
    parser.add_argument(
        "--output", default="../data/output/"
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
    sandbox: Sandbox = Sandbox()
    sandbox.build("..")
    sandbox.start()
    agent: CodeAgent = CodeAgent(
        get_llms(args.model_name), sandbox
    )
    solution = agent.give_task(task)
    with open(args.output, "w") as fd:
        ...
    sandbox.stop()


if __name__ == "__main__":
    main()
