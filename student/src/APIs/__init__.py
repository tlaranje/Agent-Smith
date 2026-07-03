from dataclasses import dataclass
from dotenv import load_dotenv
import os

load_dotenv()


@dataclass
class LLMResponse:
    content: str
    input_tokens: int
    output_tokens: int
    model_name: str


def _load_keys(prefix: str) -> list[str]:
    keys = []
    for i in range(0, 20):
        key = os.getenv(f"{prefix}_{i}")
        if key:
            keys.append(key)
    if not keys:
        key = os.getenv(prefix)
        if key:
            keys.append(key)
    return keys


def get_llms(priority_provider: str) -> dict[str, list]:
    from .gemini import GeminiAPI
    from .groq import GroqAPI
    from .open_router import OpenRouterAPI
    from .cohere import CohereAPI
    from .mistral import MistralAPI

    provider_map = {
        "gemini": (GeminiAPI, "GEMINI_API_KEY"),
        "groq": (GroqAPI, "GROQ_API_KEY"),
        "openrouter": (OpenRouterAPI, "OPENROUTER_API_KEY"),
        "cohere": (CohereAPI, "COHERE_API_KEY"),
        "mistral": (MistralAPI, "MISTRAL_API_KEY"),
    }

    priority_name = priority_provider.lower()
    if priority_name not in provider_map:
        raise ValueError(
            f"Unknown priority provider '{priority_provider}'. "
            f"Valid options: {list(provider_map.keys())}"
        )

    cls, env_prefix = provider_map[priority_name]
    priority_keys = _load_keys(env_prefix)

    if not priority_keys:
        raise RuntimeError(
            f"Priority provider '{priority_provider}' requested, "
            f"but no keys found for {env_prefix} in environment variables."
        )

    ordered_providers = {
        priority_name: [cls(api_key=key) for key in priority_keys]
    }

    for name, (cls, env_prefix) in provider_map.items():
        keys = _load_keys(env_prefix)
        instances = []
        if keys:
            for key in keys:
                instances.append(cls(api_key=key))
        ordered_providers[name] = instances

    return ordered_providers
