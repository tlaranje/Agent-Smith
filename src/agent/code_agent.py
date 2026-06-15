from src.APIs import GeminiAPI, GroqAPI
from pydantic import BaseModel
from typing import Any


class CodeAgent:
    def __init__(self, sandbox, max_iterations: int = 10) -> None:
        self.sandbox = sandbox
        self.max_iterations: int = max_iterations
        self.llms: list[Any] = [GeminiAPI(), GroqAPI()]
        self.llm: Any

    def chose_llm(self) -> None:
        self.llm = self.llms[0]

    def give_task(self, task: BaseModel) -> str:
        self.chose_llm()

        observations: str = ""
        for _ in range(self.max_iterations):
            prompt: str = self.build_prompt(
                task=task, observations=observations
            )
            try:
                llm_response: str = self.llm.generate(prompt)
            except Exception:
                self.chose_llm()

            print(llm_response)
            code: str = self.extract_code(llm_response)
            result = self.sandbox.execute(code)
            observations = result.output
        return (
            "Could not generate the requested "
            f"code within {self.max_iterations} iterations."
        )

    @staticmethod
    def build_prompt(task: BaseModel, observations: str) -> str:
        prompt: str = ""
        for key, value in task.model_dump().items():
            prompt += f"{key} - {value}\n"
        prompt += f"observations: {observations}\n"
        return prompt

    @staticmethod
    def extract_code(text: str) -> str:
        return text
