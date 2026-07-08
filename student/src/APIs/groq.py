from groq import Groq
from groq.types.chat import ChatCompletionMessageParam
from typing import Any


class GroqAPI:
    def __init__(
        self,
        api_key: str,
        model_name: str = "llama-3.3-70b-versatile",
        api_url: str = "https://api.groq.com/openai/v1"
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.api_url = api_url
        self.client = Groq(
            api_key=api_key,
            base_url=api_url
        )

    def generate_messages(self,
                          messages: list[ChatCompletionMessageParam]) -> Any:
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
