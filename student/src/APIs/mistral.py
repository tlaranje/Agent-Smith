from mistralai.client import Mistral
from typing import Any


class MistralAPI:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.model_name: str = "mistral-medium-latest"
        self.client = Mistral(api_key=api_key)

    def generate_messages(self, messages: list[dict]) -> Any:
        from . import LLMResponse

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=messages,
        )

        return LLMResponse(
            content=response.choices[0].message.content,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            model_name=response.model,
        )
