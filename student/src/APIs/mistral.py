from mistralai.client import Mistral
from mistralai.client.models import (
    AssistantMessage,
    SystemMessage,
    UserMessage,
    ToolMessage
)
from typing import Any
from typing import TypeAlias

Message: TypeAlias = (
    UserMessage | AssistantMessage | SystemMessage | ToolMessage
)


class MistralAPI:
    def __init__(
        self,
        api_key: str,
        model_name: str = "mistral-medium-latest",
        api_url: str = "https://api.mistral.ai"
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.api_url = api_url
        self.client = Mistral(
            api_key=api_key,
            server_url=api_url
        )

    def generate_messages(self, messages: list[Message]) -> Any:
        from . import LLMResponse

        response = self.client.chat.complete(
            model=self.model_name,
            messages=messages,
            stop=["<end_code>"]
        )

        usage = response.usage

        input_tokens = usage.prompt_tokens if usage is not None else 0
        output_tokens = usage.completion_tokens if usage is not None else 0
        message = response.choices[0].message
        content = (
            message.content if message and isinstance(message.content, str)
            else ""
        )

        return LLMResponse(
            content=content,
            input_tokens=input_tokens if input_tokens is not None else 0,
            output_tokens=output_tokens if output_tokens is not None else 0,
            model_name=response.model,
        )
