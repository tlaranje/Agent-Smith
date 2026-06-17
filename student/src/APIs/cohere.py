from dotenv import load_dotenv
from typing import Any
import cohere
import os


class CohereAPI:
    def __init__(self) -> None:
        load_dotenv()
        self.client = cohere.ClientV2(os.getenv("COHERE_API_KEY"))
        self.api_url: str = ""
        self.model_name = "command-a-plus-05-2026"

    def generate(self, prompt: str):
        from . import LLMResponse
        messages = [
            {
                "role": "user",
                "content": prompt
            }
        ]

        response = self.client.chat(
            model=self.model_name,
            messages=messages
        )

        texts = [
            item.text
            for item in response.message.content
            if hasattr(item, "text")
        ]

        content = "\n".join(texts)

        return LLMResponse(
            content=content,
            input_tokens=response.usage.tokens.input_tokens,
            output_tokens=response.usage.tokens.output_tokens,
            model_name=self.model_name
        )
