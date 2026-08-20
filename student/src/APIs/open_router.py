from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from typing import Any


class OpenRouterAPI:
    def __init__(
        self, api_key: str,
        model_name: str = "meta-llama/llama-3.3-70b-instruct",
        api_url: str = "https://openrouter.ai/api/v1"
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.api_url = api_url
        self.client = OpenAI(
            api_key=api_key,
            base_url=api_url,
            timeout=8.0,
            max_retries=0,
        )

    def generate_messages(
        self, messages: list[ChatCompletionMessageParam],
        max_output_tokens: int = 700,
    ) -> Any:
        """
        Send messages to the OpenRouter chat API (OpenAI-
        compatible) and wrap the result in a common LLMResponse.

        Args:
            messages: Conversation history as OpenAI-style chat
                message params.

        Returns:
            An LLMResponse with the generated content and token
            usage counts.
        """
        from . import LLMResponse

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            max_tokens=max_output_tokens,
        )

        usage = response.usage

        return LLMResponse(
            content=response.choices[0].message.content,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            model_name=self.model_name,
        )
