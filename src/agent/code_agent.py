from src.APIs import GeminiAPI, GroqAPI, CohereAPI
from pydantic import BaseModel
from typing import Any
from rich import print
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

    def give_task(self, task: BaseModel) -> str:
        observations: str = ""
        for i in range(self.max_iterations):
            prompt: str = self.build_prompt(
                task=task, observations=observations
            )
            while True:
                try:
                    llm_response: str = self.llm.generate(prompt)
                    print(f"=== Iteration {i+1} ===")
                    # print(llm_response)
                    # print("=" * 40)
                    break
                except Exception:
                    self.chose_llm()

            code: str = self.extract_code(llm_response)
            result, done = self.sandbox.execute(code)

            if done:
                print(f"✓ Solution found in iteration {i+1}!")
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
            return "\n".join(match).strip()

        return text.strip()
