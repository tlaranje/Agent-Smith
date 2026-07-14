from groq.types.chat import ChatCompletionMessageParam
from typing import Any
from groq import Groq


class GroqAPI:
    def __init__(
        self, api_key: str, model_name: str = "llama-3.3-70b-versatile",
        api_url: str = "https://api.groq.com"
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.api_url = api_url
        self.client = Groq(api_key=api_key, base_url=api_url)

    def generate_messages(
        self, messages: list[ChatCompletionMessageParam]
    ) -> Any:
        """
        Send messages to the Groq chat API and wrap the result
        in a common LLMResponse.

        Args:
            messages: Conversation history as Groq chat message
                params.

        Returns:
            An LLMResponse with the generated content and token
            usage counts.
        """
        from . import LLMResponse

        chat_completion = self.client.chat.completions.create(
            messages=messages,
            model=self.model_name,
        )

        usage = chat_completion.usage

        input_tokens = usage.prompt_tokens if usage is not None else 0
        output_tokens = usage.completion_tokens if usage is not None else 0

        return LLMResponse(
            content=chat_completion.choices[0].message.content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model_name=self.model_name,
        )
