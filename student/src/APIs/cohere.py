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
        self, api_key: str, model_name: str = "command-a-plus-05-2026",
        api_url: str = "https://api.cohere.com"
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.api_url: str = api_url
        self.client = cohere.ClientV2(
            api_key=api_key,
            base_url=api_url,
            timeout=8.0,
        )

    def generate_messages(
        self, messages: list[ChatMessage], max_output_tokens: int = 700
    ) -> Any:
        """
        Send messages to the Cohere chat API and wrap the
        result in a common LLMResponse.

        Args:
            messages: Conversation history as Cohere chat message
                objects (user, assistant, system, or tool).

        Returns:
            An LLMResponse with the generated content (joined text
            blocks) and token usage counts.
        """
        from . import LLMResponse

        response = self.client.chat(
            model=self.model_name,
            messages=messages,
            max_tokens=max_output_tokens,
        )

        content = response.message.content

        # Cohere can return multiple content blocks; keep only the
        # text ones and join them into a single string.
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
