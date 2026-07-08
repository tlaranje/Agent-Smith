from google import genai
from typing import Any


class GeminiAPI:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.client = genai.Client(api_key=api_key)
        self.api_url: str = "https://generativelanguage.googleapis.com"
        self.model_name = "gemini-2.5-flash-lite"

    def generate_messages(self, messages: list[dict]) -> Any:
        from . import LLMResponse

        contents = [
            {
                "role": "model" if m["role"] == "assistant" else m["role"],
                "parts": [{"text": m["content"]}],
            }
            for m in messages
        ]

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=contents,
        )

        usage = response.usage_metadata

        input_tokens = (
            usage.prompt_token_count
            if usage is not None and usage.prompt_token_count is not None
            else 0
        )

        output_tokens = (
            usage.candidates_token_count
            if usage is not None and usage.candidates_token_count is not None
            else 0
        )

        return LLMResponse(
            content=response.text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model_name=self.model_name,
        )
