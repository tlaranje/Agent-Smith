from dotenv import load_dotenv
from openai import OpenAI
from typing import Any
import os


class OpenRouterAPI:
    def __init__(self) -> None:
        load_dotenv()

        self.model_name = "meta-llama/llama-3.3-70b-instruct"

        self.client = OpenAI(
            api_key=os.getenv("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
        )

    def generate_messages(self, messages: list[dict]) -> Any:
        from . import LLMResponse

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
        )

        usage = response.usage

        return LLMResponse(
            content=response.choices[0].message.content,
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            model_name=self.model_name,
        )
