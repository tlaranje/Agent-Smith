from src.APIs import GeminiAPI, GroqAPI
from pydantic import BaseModel
from typing import Any
import re


class CodeAgent:
    def __init__(self, sandbox, max_iterations: int = 10) -> None:
        self.sandbox = sandbox
        self.max_iterations: int = max_iterations
        self.llms: list[Any] = [GeminiAPI(), GroqAPI()]
        self.llm: Any = self.llms[0]
        self.current_llm_index: int = 0

    def chose_llm(self) -> None:
        self.current_llm_index = (self.current_llm_index + 1) % len(self.llms)
        self.llm = self.llms[self.current_llm_index]

    def give_task(self, task: BaseModel) -> str:
        observations: str = ""
        for _ in range(self.max_iterations):
            prompt: str = self.build_prompt(
                task=task, observations=observations
            )
            try:
                llm_response: str = self.llm.generate(prompt)
            except Exception:
                self.chose_llm()
                llm_response = self.llm.generate(prompt)

            code: str = self.extract_code(llm_response)
            result = self.sandbox.execute(code)
            observations = result
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
        pattern = r"```[\w+]*\n([\s\S]*?)\n```"
        match = re.findall(pattern, text)

        if match:
            return "\n".join(match).strip()

        return text.strip()
