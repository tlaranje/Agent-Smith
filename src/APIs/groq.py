from dotenv import load_dotenv
from groq import Groq
import os


class GroqAPI:
    def __init__(self) -> None:
        load_dotenv()
        self.client = Groq(
            api_key=os.getenv("GEMINI_API_KEY_1")
        )

    def generate(self, prompt: str) -> str | None:
        chat_completion = self.client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.3-70b-versatile",
        )

        return chat_completion.choices[0].message.content
