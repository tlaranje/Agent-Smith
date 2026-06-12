from google import genai


class GeminiAPI:
    def __init__(self) -> None:
        self.client = genai.Client()

    def generate(self, prompt: str) -> str | None:
        response = self.client.models.generate_content(
            model='gemini-2.5-flash-lite',
            contents=prompt,
        )
        return response.text
