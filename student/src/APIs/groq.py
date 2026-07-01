from groq import Groq


class GroqAPI:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.client = Groq(api_key=api_key)
        self.api_url: str = "https://api.groq.com/openai/v1"
        self.model_name = "llama-3.3-70b-versatile"

    def generate_messages(self, messages: list[dict]):
        from . import LLMResponse

        chat_completion = self.client.chat.completions.create(
            messages=messages,
            model=self.model_name,
        )

        return LLMResponse(
            content=chat_completion.choices[0].message.content,
            input_tokens=chat_completion.usage.prompt_tokens,
            output_tokens=chat_completion.usage.completion_tokens,
            model_name=self.model_name,
        )
