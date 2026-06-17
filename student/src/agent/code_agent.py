from src.APIs import GeminiAPI, GroqAPI, CohereAPI
from pydantic import BaseModel, Field
from typing import Any, Optional, List
from rich import print
from datetime import datetime
import time

import re

SYSTEM_PROMPT = """
You are a coding agent solving Python programming tasks.

You operate in a loop: each iteration you write Python code that gets
executed inside a secure sandbox.
You can see the stdout/stderr or exceptions of your code in the next
iteration as observations.

## Objectives
1. Read the task description and function signature.
2. Write the implementation alongside a test runner execution if you
want to verify it.
3. Once your code passes the required test cases (or you verify it works),
you MUST submit using:
   final_answer("your complete clean function code here")

## Formatting Rules
Always respond strictly with Python code wrapped inside a markdown code block:
```python
# You can write helper logic, run prints, or execute the required assert
# statements here to test.
def your_function():
    ...

# If tests pass, call this to finish the task:
final_answer("def your_function():\\n    ...")
"""


class StepMetrics(BaseModel):
    """Metrics for a single agent step."""
    step: int
    input_tokens: int
    output_tokens: int
    request_time_ms: float
    api_url: str
    model_name: str
    llm_output: str
    sandbox_input: str
    sandbox_output: str
    retries: int
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class SolutionOutput(BaseModel):
    """Output from student solution - this is what students must
    produce."""
    task_id: str
    benchmark: str  # "mbpp" or "swebench"
    success: bool
    solution: str  # Code for MBPP, patch for SWE-bench
    system_prompt: str
    iterations: int
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_time_seconds: float
    steps: List["StepMetrics"] = Field(default_factory=list)
    error: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class CodeAgent:
    def __init__(self, llms, sandbox, max_iterations: int = 10) -> None:
        self.sandbox = sandbox
        self.max_iterations: int = max_iterations
        self.llms: list[Any] = llms
        self.llm: Any = self.llms[0]
        self.current_llm_index: int = 0

    def chose_llm(self) -> None:
        if self.current_llm_index + 1 >= len(self.llms):
            raise ValueError("Error no more tokens.")

        self.current_llm_index = (self.current_llm_index + 1)
        self.llm = self.llms[self.current_llm_index]

    def give_task(self, task: BaseModel) -> SolutionOutput:
        start_time = time.time()

        observations = ""
        steps: list[StepMetrics] = []

        total_requests = 0
        total_input_tokens = 0
        total_output_tokens = 0

        for iteration in range(self.max_iterations):

            prompt = self.build_prompt(
                task=task,
                observations=observations
            )

            retries = 0

            while True:
                try:
                    request_start = time.time()

                    response = self.llm.generate(prompt)

                    request_time_ms = (
                        time.time() - request_start
                    ) * 1000

                    total_requests += 1
                    break

                except Exception:
                    retries += 1
                    self.chose_llm()

            code = self.extract_code(response.content)

            sandbox_output, done = self.sandbox.execute(code)

            step = StepMetrics(
                step=iteration + 1,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                request_time_ms=request_time_ms,
                api_url=self.llm.api_url,
                model_name=self.llm.model_name,
                llm_output=response.content,
                sandbox_input=code,
                sandbox_output=sandbox_output,
                retries=retries,
            )

            steps.append(step)

            total_input_tokens += response.input_tokens
            total_output_tokens += response.output_tokens

            if done:
                return SolutionOutput(
                    task_id=str(task.task_id),
                    benchmark="mbpp",
                    success=True,
                    solution=sandbox_output,
                    system_prompt=SYSTEM_PROMPT,
                    iterations=iteration + 1,
                    total_requests=total_requests,
                    total_input_tokens=total_input_tokens,
                    total_output_tokens=total_output_tokens,
                    total_time_seconds=time.time() - start_time,
                    steps=steps,
                )

            observations = sandbox_output

        return SolutionOutput(
            task_id=str(task.task_id),
            benchmark="mbpp",
            success=False,
            solution="",
            system_prompt=SYSTEM_PROMPT,
            iterations=self.max_iterations,
            total_requests=total_requests,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
            total_time_seconds=time.time() - start_time,
            steps=steps,
            error="Maximum iterations reached",
        )

    @staticmethod
    def build_prompt(task: BaseModel, observations: str) -> str:
        task_data = task.model_dump()

        prompt = SYSTEM_PROMPT
        prompt += "\n## Task\n"
        prompt += f"Description: {task_data['task_definition']}\n"
        prompt += f"Function signature: {task_data['function_definition']}\n"
        prompt += "Tests to pass:\n"
        for test in task_data['test_list']:
            prompt += f"  {test}\n"

        if observations:
            prompt += f"\n## Last execution output\n{observations}\n"

        prompt += "\nWrite your solution:"
        return prompt

    @staticmethod
    def extract_code(text: str) -> str:
        pattern = r"```[\w+]*\n([\s\S]*?)\n```"
        match = re.findall(pattern, text)

        if match:
            return "\n".join(match).strip()

        return text.strip()
