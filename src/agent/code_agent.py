from src.APIs import GeminiAPI, GroqAPI, CohereAPI
from pydantic import BaseModel
from typing import Any
from rich import print
import re

SYSTEM_PROMPT = """
You are an expert Python coding agent executing code in a secure sandbox.

CRITICAL FORMAT RULES:
1. Every response MUST contain exactly ONE Python code block enclosed
in triple backticks (```python ... ```).
2. Inside this single code block, you MUST first define the requested
function, and immediately after, call the `final_answer` function.
3. The argument passed to `final_answer` MUST be a valid Python STRING
literal (enclosed in quotes or triple quotes) containing your clean function
definition. Do NOT pass the raw function name.

EXACT EXAMPLE FORMAT TO FOLLOW:
```python
def extract_rear(test_tuple):
    # Your implementation here
    return [s[-1] for s in test_tuple]

# Correct invocation passing a STRING literal containing the code:
final_answer(\"\"\"def extract_rear(test_tuple):
    return [s[-1] for s in test_tuple]\"\"\")
"""


class CodeAgent:
    def __init__(self, sandbox, max_iterations: int = 10) -> None:
        self.sandbox = sandbox
        self.max_iterations: int = max_iterations
        self.llms: list[Any] = [GroqAPI(), GeminiAPI(), CohereAPI()]
        self.llm: Any = self.llms[0]
        self.current_llm_index: int = 0

    def chose_llm(self) -> None:
        if self.current_llm_index + 1 >= len(self.llms):
            raise ValueError("Error no more tokens.")

        self.current_llm_index = (self.current_llm_index + 1)
        self.llm = self.llms[self.current_llm_index]

    def give_task(self, task) -> str:
        observations: str = ""
        for i in range(self.max_iterations):
            prompt: str = self.build_prompt(
                task=task, observations=observations
            )
            while True:
                try:
                    llm_response: str = self.llm.generate(prompt)
                    # print(f"=== Iteration {i+1} ===")
                    # print(llm_response)
                    # print("=" * 40)
                    break
                except Exception:
                    self.chose_llm()

            code: str = self.extract_code(llm_response)
            result, done = self.sandbox.execute(code, test_list=task.test_list)

            if done:
                # print(f"✓ Solution found in iteration {i+1}!")
                return result

            observations = result
        return (
            "Could not generate the requested "
            f"code within {self.max_iterations} iterations."
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
            return match[-1].strip()

        return text.strip()
