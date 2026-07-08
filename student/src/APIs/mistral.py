from mistralai.client import Mistral
from mistralai.client.models import (
    AssistantMessage,
    SystemMessage,
    UserMessage,
)
from typing import Any
from typing import TypeAlias

Message: TypeAlias = (
    UserMessage | AssistantMessage | SystemMessage
)


class MistralAPI:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.model_name = "mistral-medium-latest"
        self.client = Mistral(api_key=api_key)

    def generate_messages(self, messages: list[Message]) -> Any:
        from . import LLMResponse

        response = self.client.chat.complete(
            model=self.model_name,
            messages=messages,
        )

        usage = response.usage

        input_tokens = usage.prompt_tokens if usage is not None else 0
        output_tokens = usage.completion_tokens if usage is not None else 0

        return LLMResponse(
            content=response.choices[0].message.content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model_name=response.model,
        )
