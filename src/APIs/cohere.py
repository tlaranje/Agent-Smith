from dotenv import load_dotenv
from typing import Any
import cohere
import os


class CohereAPI:
    def __init__(self) -> None:
        load_dotenv()
        self.client = cohere.ClientV2(os.getenv("COHERE_API_KEY"))

    def generate(self, prompt: str) -> str | None:
        messages: list[Any] = [
            {"role": "user", "content": prompt}
        ]
        chat_completion = self.client.chat(
            model="command-a-plus-05-2026",
            messages=messages
        )

        assert chat_completion.message.content is not None

        texts = [
            item.text
            for item in chat_completion.message.content
            if hasattr(item, "text")
        ]

        return "\n".join(texts)
