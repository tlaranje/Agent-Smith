from dotenv import load_dotenv
import cohere
import os


class CohereAPI:
    def __init__(self) -> None:
        load_dotenv()
        self.client = cohere.ClientV2(os.getenv("COHERE_API_KEY"))
        self.api_url: str = ""
        self.model_name = "command-a-plus-05-2026"

    def generate_messages(self, messages: list[dict]):
        from . import LLMResponse

        response = self.client.chat(
            model=self.model_name,
            messages=messages
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
            model_name=self.model_name
        )
