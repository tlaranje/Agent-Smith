from typing import Any, cast
from cerebras.cloud.sdk import Cerebras
from cerebras.cloud.sdk.types.chat.chat_completion import (
    ChatCompletionResponse,
)


class CerebrasAPI:
    def __init__(
        self, api_key: str, model_name: str = "gpt-oss-120b",
        api_url: str = "https://api.cerebras.ai",
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.api_url = api_url

        self.client = Cerebras(api_key=api_key, base_url=api_url)

    def generate_messages(self, messages: list[dict[str, str]]) -> Any:
        """
        Send messages to the Cerebras chat API and wrap the
        result in a common LLMResponse.

        Args:
            messages: Conversation history as a list of role/
                content dicts.

        Returns:
            An LLMResponse with the generated content and token
            usage counts.
        """
        from . import LLMResponse

        chat_completion = cast(
            ChatCompletionResponse,
            self.client.chat.completions.create(
                model=self.model_name,
                messages=cast(list[dict[str, object]], messages),
                stream=False,
            )
        )

        usage = chat_completion.usage

        input_tokens = usage.prompt_tokens if usage is not None else 0
        output_tokens = usage.completion_tokens if usage is not None else 0

        # Usage fields can be None depending on the API response,
        # so default to 0 to keep token counts numeric.
        return LLMResponse(
            content=chat_completion.choices[0].message.content,
            input_tokens=input_tokens if input_tokens is not None else 0,
            output_tokens=output_tokens if output_tokens is not None else 0,
            model_name=self.model_name,
        )
