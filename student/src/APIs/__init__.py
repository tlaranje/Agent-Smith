from .gemini import GeminiAPI
from .groq import GroqAPI
from .cohere import CohereAPI
from pydantic import BaseModel


class LLMResponse(BaseModel):
    content: str
    input_tokens: int
    output_tokens: int
    model_name: str


__all__ = ["GeminiAPI", "GroqAPI", "CohereAPI"]
