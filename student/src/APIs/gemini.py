from google.genai.types import GenerateContentConfig
from google.genai.types import HttpOptions
from google import genai
from typing import Any


class GeminiAPI:
    def __init__(
        self, api_key: str, model_name: str = "gemini-2.5-flash-lite",
        api_url: str = "https://generativelanguage.googleapis.com"
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.api_url = api_url
        self.client = genai.Client(
            api_key=api_key,
            http_options=HttpOptions(base_url=api_url, timeout=8000),
        )

    def generate_messages(
        self, messages: list[dict], max_output_tokens: int = 700
    ) -> Any:
        """
        Send messages to the Gemini API and wrap the result in
        a common LLMResponse.

        Args:
            messages: Conversation history as a list of role/
                content dicts. The "assistant" role is mapped to
                Gemini's "model" role.

        Returns:
            An LLMResponse with the generated content and token
            usage counts. If the model returns no text, content
            is set to a placeholder string describing the finish
            reason.
        """
        from . import LLMResponse

        contents = [
            {
                "role": "model" if m["role"] == "assistant" else m["role"],
                "parts": [{"text": m["content"]}],
            }
            for m in messages
        ]

        # Disable "thinking" tokens when supported by the installed
        # SDK version, to keep responses fast and cheap; fall back
        # to a plain config on older SDKs that lack ThinkingConfig.
        try:
            from google.genai.types import ThinkingConfig
            config = GenerateContentConfig(
                max_output_tokens=max_output_tokens,
                thinking_config=ThinkingConfig(thinking_budget=0),
            )
        except (ImportError, TypeError):
            config = GenerateContentConfig(max_output_tokens=max_output_tokens)

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=config,
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

        content = response.text
        if not content:
            finish_reason = None
            if response.candidates:
                finish_reason = response.candidates[0].finish_reason
            content = f"(empty response, finish_reason={finish_reason})"

        return LLMResponse(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model_name=self.model_name,
        )
