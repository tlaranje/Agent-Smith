from .gemini import GeminiAPI
from .groq import GroqAPI
from .cohere import CohereAPI
from .open_router import OpenRouterAPI
from pydantic import BaseModel
from typing import Any


class LLMResponse(BaseModel):
    content: str
    input_tokens: int
    output_tokens: int
    model_name: str


def get_llms(model_name: str = "gemini") -> list[Any]:
    models = {
        "gemini": GeminiAPI,
        "groq": GroqAPI,
        "cohere": CohereAPI,
        "open_router": OpenRouterAPI
    }

    if model_name not in models:
        raise ValueError(f"LLM model '{model_name}' not supported")

    ordered_models = [models[model_name]]

    for name, model in models.items():
        if name != model_name:
            ordered_models.append(model)

    return [model() for model in ordered_models]


__all__ = ["GeminiAPI", "GroqAPI", "CohereAPI"]
