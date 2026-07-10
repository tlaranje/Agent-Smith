from typing import Any

from cerebras.cloud.sdk import Cerebras


class CerebrasAPI:
    def __init__(
        self,
        api_key: str,
        model_name: str = "gpt-oss-120b",
        api_url: str = "https://api.cerebras.ai",
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.api_url = api_url

        self.client = Cerebras(
            api_key=api_key,
            base_url=api_url,
        )

    def generate_messages(
        self,
        messages: list[dict[str, Any]],
    ) -> Any:
        from . import LLMResponse

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            max_completion_tokens=512
        )

        usage = getattr(response, "usage", None)

        input_tokens = (
            int(getattr(usage, "prompt_tokens", 0))
            if usage is not None
            else 0
        )

        output_tokens = (
            int(getattr(usage, "completion_tokens", 0))
            if usage is not None
            else 0
        )

        content = ""
        if getattr(response, "choices", None):
            message = response.choices[0].message
            content = message.content or ""

        return LLMResponse(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model_name=self.model_name,
        )
