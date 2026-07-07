from mistralai.client import Mistral


class MistralAPI:
    def __init__(self, api_key: str):
        self.client = Mistral(api_key=api_key)
        self.api_url = ""
        self.model_name = "mistral-medium-latest"

    def generate_messages(self, messages):
        from . import LLMResponse

        response = self.client.chat.complete(
            model=self.model_name,
            messages=messages,
        )

        return LLMResponse(
            content=response.choices[0].message.content,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            model_name=response.model,
        )
