from pydantic import BaseModel


class CodeAgent:
    def __init__(self, llm, sandbox, max_iterations: int = 10) -> None:
        self.llm = llm
        self.sandbox = sandbox
        self.max_iterations: int = max_iterations

    def give_task(self, task: BaseModel) -> str:
        observations: str = ""
        for _ in range(self.max_iterations):
            prompt: str = self.build_prompt(
                task=task, observations=observations
            )
            llm_response: str = self.llm.generate(prompt)
            print(llm_response)
            code: str = self.extract_code(llm_response)
            result = self.sandbox.execute(code)
            if result.final_answer:
                return result.final_answer
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
