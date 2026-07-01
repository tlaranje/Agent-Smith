from typing import Any, Optional, List
from pydantic import BaseModel, Field
from ..parser import MBPPTaskInput
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


class MBPPAgent:
    def __init__(self, sandbox, llms, max_iterations: int = 10) -> None:
        self.sandbox = sandbox

        self.sandbox.build("..")

        self.max_iterations: int = max_iterations
        self.llms: list[Any] = [api for llm in llms.values() for api in llm]
        self.llm: Any = self.llms[0]
        self.current_llm_index: int = 0

    def chose_llm(self) -> None:
        if self.current_llm_index + 1 >= len(self.llms):
            raise ValueError("Error no more tokens.")

        self.current_llm_index = (self.current_llm_index + 1)
        self.llm = self.llms[self.current_llm_index]

    def solve(self, task: MBPPTaskInput) -> SolutionOutput:
        start_time = time.time()
        steps: list[StepMetrics] = []
        total_requests = 0
        total_input_tokens = 0
        total_output_tokens = 0
        messages = [{"role": "user", "content": self.build_prompt(task)}]

        self.sandbox.start()

        try:
            for iteration in range(self.max_iterations):
                retries = 0
                while True:
                    try:
                        request_start = time.time()
                        response = self.llm.generate_messages(messages)
                        request_time_ms = (time.time() - request_start) * 1000
                        total_requests += 1
                        break
                    except Exception:
                        retries += 1
                        self.chose_llm()
                code = self.extract_code(response.content)

                final_answer_shim = (
                    "import os as _os\n"
                    "def final_answer(answer_string):\n"
                    "    _os.makedirs('/tmp/agent', exist_ok=True)\n"
                    "    with open('/tmp/agent/final_result.py', 'w', "
                    "encoding='utf-8') as _f:\n"
                    "        _f.write(answer_string)\n\n"
                )

                if "final_answer(" in code:
                    import io
                    import contextlib
                    stdout_capture = io.StringIO()
                    try:
                        namespace = self.sandbox.build_namespace()
                        with contextlib.redirect_stdout(stdout_capture), \
                             contextlib.redirect_stderr(stdout_capture):
                            exec(code, namespace, namespace)
                        done = True
                        sandbox_output = "Task completed using final_answer."
                    except Exception as e:
                        done = False
                        sandbox_output = f"Error executing final_answer: {e}"
                else:
                    sandbox_output = self.sandbox.mcp_client.call_tool(
                        "run_tests", code=code
                    )
                    done = (
                        "SUCCESS: All tests passed successfully!"
                        in sandbox_output
                    )
                steps.append(StepMetrics(
                    step=iteration + 1,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    request_time_ms=request_time_ms,
                    api_url=self.llm.api_url,
                    model_name=self.llm.model_name,
                    llm_output=response.content,
                    sandbox_input=final_answer_shim + code,
                    sandbox_output=sandbox_output,
                    retries=retries,
                ))
                total_input_tokens += response.input_tokens
                total_output_tokens += response.output_tokens
                if done:
                    return SolutionOutput(
                        task_id=str(task.task_id),
                        benchmark="mbpp",
                        success=True,
                        solution=final_answer_shim + code,
                        system_prompt=SYSTEM_PROMPT,
                        iterations=iteration + 1,
                        total_requests=total_requests,
                        total_input_tokens=total_input_tokens,
                        total_output_tokens=total_output_tokens,
                        total_time_seconds=time.time() - start_time,
                        steps=steps,
                    )
                messages.append(
                    {"role": "assistant", "content": response.content})
                messages.append({
                    "role": "user",
                    "content": self._format_observation(
                        sandbox_output, iteration
                    )
                })
        finally:
            self.sandbox.stop()

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

    def _format_observation(self, sandbox_output: str, iteration: int) -> str:
        """Give the model structured feedback rather than raw stdout."""
        remaining = self.max_iterations - iteration - 1
        return (
            f"Execution result:\n```\n{sandbox_output}\n```\n\n"
            f"You have {remaining} attempt(s) remaining. "
            "If tests passed, call final_answer(). "
            "Otherwise fix the issue above."
        )

    @staticmethod
    def build_prompt(task: MBPPTaskInput) -> str:
        """Initial message — includes system prompt + task description."""
        task_data = task.model_dump()
        lines = [
            SYSTEM_PROMPT,
            "\n## Task",
            f"Description: {task_data['task_definition']}",
            f"Function signature: {task_data['function_definition']}",
            "Tests to pass:",
            *[f"  {t}" for t in task_data['test_list']],
            "\nWrite your solution:",
        ]
        return "\n".join(lines)

    @staticmethod
    def extract_code(text: str) -> str:
        pattern = r"```[\w+]*\n([\s\S]*?)\n```"
        match = re.findall(pattern, text)

        if match:
            return "\n".join(match).strip()

        return text.strip()
