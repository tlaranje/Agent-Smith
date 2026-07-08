from google import genai
from typing import Any
from google.genai.types import HttpOptions


class GeminiAPI:
    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.5-flash-lite",
        api_url: str = "https://generativelanguage.googleapis.com"
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.api_url = api_url
        self.client = genai.Client(
            api_key=api_key,
            http_options=HttpOptions(base_url=api_url)
        )

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
