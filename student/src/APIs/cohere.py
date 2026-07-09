import cohere
from typing import Any
from cohere.types import (
    UserChatMessageV2,
    AssistantChatMessageV2,
    SystemChatMessageV2,
    ToolChatMessageV2,
)
from typing import TypeAlias

ChatMessage: TypeAlias = (
    UserChatMessageV2
    | AssistantChatMessageV2
    | SystemChatMessageV2
    | ToolChatMessageV2
)


class CohereAPI:
    def __init__(
        self,
        api_key: str,
        model_name: str = "command-a-plus-05-2026",
        api_url: str = "https://api.cohere.com"
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.api_url: str = api_url
        self.client = cohere.ClientV2(
            api_key=api_key,
            base_url=api_url
        )

    def generate_messages(self, messages: list[ChatMessage]) -> Any:
        from . import LLMResponse

        response = self.client.chat(
            model=self.model_name,
            messages=messages,
            stop_sequences=["<end_code>"],
        )

        content = response.message.content

        texts = (
            [
                item.text
                for item in content
                if hasattr(item, "text")
            ]
            if content is not None
            else []
        )

        usage = response.usage
        tokens = usage.tokens if usage is not None else None

        input_tokens = (
            int(tokens.input_tokens)
            if tokens is not None and tokens.input_tokens is not None
            else 0
        )

        output_tokens = (
            int(tokens.output_tokens)
            if tokens is not None and tokens.output_tokens is not None
            else 0
        )

        return LLMResponse(
            content="\n".join(texts),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model_name=self.model_name,
        )
