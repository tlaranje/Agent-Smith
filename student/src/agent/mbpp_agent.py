from typing import Any, Optional, List
from pydantic import BaseModel, Field
from ..parser import MBPPTaskInput
import xml.etree.ElementTree as ET
from ..sandbox import Sandbox
from datetime import datetime
import json
import time
import sys
import re

SYSTEM_PROMPT = """
You are an expert Python programmer.

You solve one programming task at a time.

The available sandbox tools are documented below.

Use the tools as normal Python functions.

Requirements:

- Produce correct Python code.
- Follow the requested function signature exactly.
- Use the provided tools whenever necessary.
- Do not import unavailable modules.
- Do not access resources outside the sandbox.
- Return only executable Python code.
- Do not include markdown or explanations.
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
    def __init__(self, sandbox: Sandbox, llms: dict[str, list],
                 max_iterations: int = 10) -> None:
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

        self.sandbox.start()
        assert self.sandbox.mcp_client is not None

        manual = self.sandbox.mcp_client.generate_manual()

        prompt = self.build_prompt(task, manual)

        messages = [
            {
                "role": "user",
                "content": prompt,
            }
        ]

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
                        print(
                            "[Warning] Error occurred"
                            f" with {self.llm.model_name}",
                            file=sys.stderr,
                        )
                        self.chose_llm()
                        print(
                            "[Warning] Switching API key"
                            f" of LLM model {self.llm.model_name}",
                            file=sys.stderr,
                        )

                code = self.extract_code(response.content)

                final_answer_shim = (
                    "import os as _os\n"
                    "def final_answer(answer_string):\n"
                    "    _os.makedirs('/tmp/agent', exist_ok=True)\n"
                    "    with open('/tmp/agent/final_result.py', 'w', "
                    "encoding='utf-8') as _f:\n"
                    "        _f.write(answer_string)\n\n"
                )

                code = self.extract_code(response.content)
                sandbox_output = self.sandbox.mcp_client.call_tool(
                    "run_tests", code=code
                )
                done = (
                    "SUCCESS: All tests passed successfully!" in sandbox_output
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
                        system_prompt=prompt,
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
            system_prompt=prompt,
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
    def build_prompt(task: MBPPTaskInput, manual: str) -> str:
        task_data = task.model_dump()

        lines = [
            SYSTEM_PROMPT,
            "",
            manual,
            "",
            "## Task",
            f"Description: {task_data['task_definition']}",
            (
                "Function signature: "
                f"{task_data['function_definition']}"
            ),
            "Tests to pass:",
            *[f"  {t}" for t in task_data["test_list"]],
            "",
            "Write your solution:",
        ]

        return "\n".join(lines)

    @staticmethod
    def extract_code(text: str) -> str:
        match = re.search(
            r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE
        )
        if match:
            return match.group(1).strip()

        match = re.search(
            r"<invoke\s+name=\"([^\"]+)\">(.*?)</invoke>", text, re.DOTALL
        )
        if match:
            tool = match.group(1)
            body = match.group(2)
            args = {}

            for param in re.finditer(
                r"<parameter\s+name=\"([^\"]+)\">(.*?)</parameter>",
                body, re.DOTALL
            ):
                args[param.group(1)] = param.group(2).strip()

            params = ", ".join(f"{k}={v!r}" for k, v in args.items())
            return f"result = {tool}({params})"

        match = re.search(
            r"<tool_call>\s*(\{.*?\})\s*</tool_call>", text, re.DOTALL,
        )
        if match:
            try:
                obj = json.loads(match.group(1))
                tool = obj["name"]
                args = obj.get("arguments", {})
                params = ", ".join(f"{k}={v!r}" for k, v in args.items())
                return f"result = {tool}({params})"
            except (json.JSONDecodeError, KeyError, TypeError):
                pass

        match = re.search(
            r"Action:\s*(\w+)\s*"r"Action Input:\s*(\{.*?\})", text, re.DOTALL,
        )
        if match:
            tool = match.group(1)
            try:
                args = json.loads(match.group(2))
            except json.JSONDecodeError:
                args = {}

            params = ", ".join(f"{k}={v!r}" for k, v in args.items())
            return f"result = {tool}({params})"

        try:
            root = ET.fromstring(text)
            if root.tag == "invoke":
                tool = root.attrib["name"]
                args = {
                    child.attrib["name"]: child.text or ""
                    for child in root.findall("parameter")
                }
                params = ", ".join(f"{k}={v!r}" for k, v in args.items())
                return f"result = {tool}({params})"
        except ET.ParseError:
            pass

        return text.strip()
