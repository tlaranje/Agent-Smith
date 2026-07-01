import cohere


class CohereAPI:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.client = cohere.ClientV2(api_key)
        self.api_url: str = "https://api.cohere.com"
        self.model_name = "command-a-plus-05-2026"

    def generate_messages(self, messages: list[dict]):
        from . import LLMResponse

        response = self.client.chat(
            model=self.model_name,
            messages=messages,
        )

        texts = [
            item.text
            for item in response.message.content
            if hasattr(item, "text")
        ]

        return LLMResponse(
            content="\n".join(texts),
            input_tokens=response.usage.tokens.input_tokens,
            output_tokens=response.usage.tokens.output_tokens,
            model_name=self.model_name,
        )
