import time
from typing import Any, List, TypeAlias, Union
from mistralai.client import Mistral
from mistralai.client.models import (
    AssistantMessage,
    SystemMessage,
    ToolMessage,
    UserMessage,
)

Message: TypeAlias = Union[
    UserMessage, AssistantMessage, SystemMessage, ToolMessage
]


class MistralAPI:

    def __init__(
        self,
        api_key: str,
        model_name: str = "codestral-latest",
        api_url: str = "https://api.mistral.ai",
    ) -> None:
        self.api_key: str = api_key
        self.model_name: str = model_name
        self.api_url: str = api_url
        self.client: Mistral = Mistral(
            api_key=api_key, server_url=api_url
        )

    def generate_messages(
        self, messages: List[Message], max_retries: int = 5
    ) -> Any:
        from . import LLMResponse

        delay: float = 2.0

        for attempt in range(max_retries):
            try:
                response = self.client.chat.complete(
                    model=self.model_name,
                    messages=messages,
                )

                usage = response.usage
                input_tokens = (
                    usage.prompt_tokens if usage is not None else 0
                )
                output_tokens = (
                    usage.completion_tokens if usage is not None else 0
                )
                message = response.choices[0].message
                content = (
                    message.content
                    if message and isinstance(message.content, str)
                    else ""
                )

                return LLMResponse(
                    content=content,
                    input_tokens=(
                        input_tokens if input_tokens is not None else 0
                    ),
                    output_tokens=(
                        output_tokens if output_tokens is not None else 0
                    ),
                    model_name=response.model,
                )

            except Exception as e:
                error_msg = str(e)
                is_rate_limit = (
                    "429" in error_msg
                    or "Too Many Requests" in error_msg
                    or "quota" in error_msg.lower()
                )

                if is_rate_limit:
                    if attempt == max_retries - 1:
                        raise e

                    time.sleep(delay)
                    delay *= 2
                else:
                    raise e

        raise RuntimeError(
            "Falha critica: O Agent Smith excedeu o número de retries."
        )
