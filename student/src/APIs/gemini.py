from dotenv import load_dotenv
from google import genai
import os


class GeminiAPI:
    def __init__(self) -> None:
        load_dotenv()
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY_1"))
        self.api_url: str = ""
        self.model_name = "gemini-2.5-flash-lite"

    def generate(self, prompt: str):
        from . import LLMResponse
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
        )

        return LLMResponse(
            content=response.text,
            input_tokens=response.usage_metadata.prompt_token_count,
            output_tokens=response.usage_metadata.candidates_token_count,
            model_name=self.model_name
        )
