from dotenv import load_dotenv
from google import genai
import os


class GeminiAPI:
    def __init__(self) -> None:
        load_dotenv()
        self.client = genai.Client(
            api_key=os.getenv("GEMINI_API_KEY_1")
        )

    def generate(self, prompt: str) -> str | None:
        response = self.client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=prompt,
        )
        return response.text
