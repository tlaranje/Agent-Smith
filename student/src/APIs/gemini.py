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

        usage = response.usage

        return LLMResponse(
            content=response.text,
            input_tokens=usage.prompt_token_count or 0,
            output_tokens=usage.candidates_token_count or 0,
            model_name=self.model_name,
        )
