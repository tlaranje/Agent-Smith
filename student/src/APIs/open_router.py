from openai import OpenAI
from typing import Any


class OpenRouterAPI:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.api_url: str = "https://openrouter.ai/api/v1"
        self.model_name = "meta-llama/llama-3.3-70b-instruct"
        self.client = OpenAI(
            api_key=api_key,
            base_url=self.api_url,
        )

    def generate_messages(self, messages: list[dict]) -> Any:
        from . import LLMResponse

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
        )

        print(response.usage)

        usage = response.usage

        return LLMResponse(
            content=response.choices[0].message.content,
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            model_name=self.model_name,
        )
