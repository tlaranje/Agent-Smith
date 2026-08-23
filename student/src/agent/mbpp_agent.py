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

RED = "\033[91m"
YELLOW = "\033[93m"
END = "\033[0m"

SYSTEM_PROMPT = """Solve the MBPP task with the exact requested function signature.
Return only short executable Python code: no explanation, docstring, repeated
tests, or alternative solutions. After the implementation passes, call
final_answer("<the clean function code>")."""

MAX_MBPP_OUTPUT_TOKENS = 1500
MAX_RESPONSE_TOKENS = 700


def short_error(e: Exception, max_len: int = 150) -> str:
    msg = str(e).replace("\n", " ").strip()

    match = re.search(r"'message':\s*'([^']*)'", msg)
    if match:
        msg = match.group(1)
    else:
        msg = re.sub(r"^\w*Error:?\s*", "", msg)
        msg = re.sub(r"^\d{3}[\s\-:]*[A-Z_]*\.?\s*", "", msg)

    if ". " in msg:
        msg = msg.split(". ")[0] + "."

    if len(msg) > max_len:
        msg = msg[:max_len].rstrip() + "..."

    return msg.strip()


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
    """Output from student solution - this is what students must produce."""
    task_id: str
    benchmark: str
    success: bool
    solution: str
    system_prompt: str
    iterations: int
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    total_time_seconds: float
    steps: List["StepMetrics"] = Field(default_factory=list)
    error: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


def _coerce(value: str) -> Any:
    """
    Try to interpret a raw XML-captured string as a Python/JSON
    literal (int, float, bool, list, dict...) before falling back to
    the original string. json.loads already distinguishes these
    correctly for the JSON/ReAct formats, but the <invoke> XML format
    is captured via plain regex, so this is only needed here.
    """
    try:
        return json.loads(value)
    except (json.JSONDecodeError, ValueError):
        return value


_INTERNAL_ONLY_TOOLS = {"set_current_task_tests", "run_tests"}


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
        """
        Switch to the next available LLM client.

        Raises:
            ValueError: If there are no more LLM clients/tokens
                left to fall back to.
        """
        if self.current_llm_index + 1 >= len(self.llms):
            raise ValueError("Error no more tokens.")

        self.current_llm_index = (self.current_llm_index + 1)
        self.llm = self.llms[self.current_llm_index]

    def solve(self, task: MBPPTaskInput) -> SolutionOutput:
        """
        Solve an MBPP task by iterating with the LLM and sandbox.

        Args:
            task: The MBPP task definition, including the function
                signature and the tests it must pass.

        Returns:
            The resulting SolutionOutput, either with a passing
            solution or marked as failed after max_iterations.
        """
        start_time = time.time()
        steps: list[StepMetrics] = []
        total_requests = 0
        total_input_tokens = 0
        total_output_tokens = 0

        self.sandbox.start()
        assert self.sandbox.mcp_client is not None

        # Register this task's tests in the sandbox so the
        # run_tests tool knows what to check against.
        self.sandbox.mcp_client.call_tool(
            "set_current_task_tests", test_list=task.test_list
        )

        # Build the tool manual shown to the LLM, hiding the
        # internal-only tools (task setup, test runner).
        manual = self.sandbox.mcp_client.generate_manual(
            exclude=_INTERNAL_ONLY_TOOLS
        )

        prompt = self.build_prompt(task, manual)

        messages = [
            {
                "role": "user",
                "content": prompt,
            }
        ]
        # Run the LLM interaction loop but capture and return partial
        # progress on failure so callers always get a populated JSON
        # report (with success=False) instead of an empty result.
        try:
            for iteration in range(self.max_iterations):
                retries = 0
                # Keep retrying with fallback LLMs until one call
                # succeeds (e.g. handles rate limits/key errors).
                while True:
                    try:
                        request_start = time.time()
                        remaining_output = (
                            MAX_MBPP_OUTPUT_TOKENS - total_output_tokens
                        )
                        if remaining_output <= 0:
                            # Return structured failure with collected
                            # steps so far instead of raising.
                            return SolutionOutput(
                                task_id=str(task.task_id),
                                benchmark="mbpp",
                                success=False,
                                solution="",
                                system_prompt=prompt,
                                iterations=iteration,
                                total_requests=total_requests,
                                total_input_tokens=total_input_tokens,
                                total_output_tokens=total_output_tokens,
                                total_time_seconds=time.time() - start_time,
                                steps=steps,
                                error="MBPP output token budget exhausted",
                            )
                        response = self.llm.generate_messages(
                            messages,
                            max_output_tokens=min(
                                MAX_RESPONSE_TOKENS, remaining_output
                            ),
                        )
                        request_time_ms = (time.time() - request_start) * 1000
                        total_requests += 1
                        break
                    except Exception as e:
                        retries += 1
                        print(
                            f"{RED}[Warning] Error occurred with "
                            f"{self.llm.model_name}: {type(e).__name__}: "
                            f"{short_error(e)}{END}",
                            file=sys.stderr,
                        )
                        if retries >= len(self.llms):
                            raise RuntimeError(
                                "All LLM providers/keys failed after "
                                f"{retries} retries. Last error: {e}"
                            ) from e
                        self.chose_llm()
                        print(
                            f"{YELLOW}[Warning] Switching API key"
                            f" of LLM model {self.llm.model_name}{END}",
                            file=sys.stderr,
                        )

                code = self.extract_code(response.content or "")

                sandbox_output = self.sandbox.mcp_client.call_tool(
                    "run_tests", code=code
                )
                try:
                    test_result = json.loads(sandbox_output)
                except json.JSONDecodeError:
                    test_result = {
                        "success": False,
                        "output": sandbox_output,
                    }
                done = bool(test_result.get("success", False))

                steps.append(StepMetrics(
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
                ))
                total_input_tokens += response.input_tokens
                total_output_tokens += response.output_tokens
                if done:
                    return SolutionOutput(
                        task_id=str(task.task_id),
                        benchmark="mbpp",
                        success=True,
                        solution=str(test_result.get("output") or code),
                        system_prompt=prompt,
                        iterations=iteration + 1,
                        total_requests=total_requests,
                        total_input_tokens=total_input_tokens,
                        total_output_tokens=total_output_tokens,
                        total_time_seconds=time.time() - start_time,
                        steps=steps,
                    )
                # Do not resend the growing conversation. The next request
                # only needs the task and the latest execution observation.
                messages = [{
                    "role": "user",
                    "content": (
                        f"Task: {task.task_definition}\n"
                        f"Signature: {task.function_definition}\n"
                        f"Previous code:\n{code}\n"
                        f"Latest result:\n{sandbox_output}\n"
                        "Return only the corrected code."
                    ),
                }]
        except Exception as e:
            # Stop sandbox and return partial SolutionOutput with error
            try:
                self.sandbox.stop()
            except Exception:
                pass
            return SolutionOutput(
                task_id=str(task.task_id),
                benchmark="mbpp",
                success=False,
                solution="",
                system_prompt=prompt if 'prompt' in locals() else "",
                iterations=iteration if 'iteration' in locals() else 0,
                total_requests=total_requests,
                total_input_tokens=total_input_tokens,
                total_output_tokens=total_output_tokens,
                total_time_seconds=time.time() - start_time,
                steps=steps,
                error=str(e),
            )
        finally:
            try:
                self.sandbox.stop()
            except Exception:
                pass

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
        """
        Extract executable code from a raw LLM response.

        Tries several known formats in order (markdown code block,
        <invoke> XML, <tool_call> JSON, ReAct-style Action/Action
        Input, and bare XML), converting tool calls into an
        equivalent `result = tool(...)` call. Falls back to the
        stripped raw text if nothing matches.

        Args:
            text: The raw text returned by the LLM.

        Returns:
            A string of Python code ready to run in the sandbox.
        """
        # Preferred format: a fenced ```python``` code block.
        match = re.search(
            r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE
        )
        if match:
            return match.group(1).strip()

        # Anthropic-style <invoke name="tool"><parameter ...>
        # tool-call format.
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
                args[param.group(1)] = _coerce(param.group(2).strip())

            params = ", ".join(f"{k}={v!r}" for k, v in args.items())
            return f"result = {tool}({params})"

        # <tool_call>{"name": ..., "arguments": {...}}</tool_call>
        # format used by some open models.
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

        # ReAct-style "Action: tool\nAction Input: {...}" format.
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

        # Last resort: try parsing the whole text as a bare
        # <invoke> XML element.
        try:
            root = ET.fromstring(text)
            if root.tag == "invoke":
                tool = root.attrib["name"]
                args = {
                    child.attrib["name"]: _coerce((child.text or "").strip())
                    for child in root.findall("parameter")
                }
                params = ", ".join(f"{k}={v!r}" for k, v in args.items())
                return f"result = {tool}({params})"
        except ET.ParseError:
            pass

        return text.strip()
