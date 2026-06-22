from dotenv import load_dotenv
from groq import Groq
import os


class GroqAPI:
    def __init__(self) -> None:
        load_dotenv()
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.api_url: str = ""
        self.model_name = "llama-3.3-70b-versatile"

    def generate_messages(self, messages: list[dict]):
        from . import LLMResponse
        chat_completion = self.client.chat.completions.create(
            messages=messages,
            model=self.model_name
        )
        return LLMResponse(
            content=chat_completion.choices[0].message.content,
            input_tokens=chat_completion.usage.prompt_tokens,
            output_tokens=chat_completion.usage.completion_tokens,
            model_name=self.model_name
        )
