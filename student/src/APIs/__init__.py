from dataclasses import dataclass
from dotenv import load_dotenv
import os

load_dotenv()


@dataclass
class LLMResponse:
    content: str | None
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


def get_llms(
    priority_model_name: str,
    priority_provider_url: str | None
) -> dict[str, list]:
    from .gemini import GeminiAPI
    from .groq import GroqAPI
    from .open_router import OpenRouterAPI
    from .cohere import CohereAPI
    from .mistral import MistralAPI

    provider_map = {
        "gemini": (
            GeminiAPI,
            "GEMINI_API_KEY",
            ["gemini-"],
        ),
        "groq": (
            GroqAPI,
            "GROQ_API_KEY",
            [
                "llama-",
                "llama3-",
                "mixtral-",
            ],
        ),
        "openrouter": (
            OpenRouterAPI,
            "OPENROUTER_API_KEY",
            [
                "meta-llama/",
                "google/",
                "anthropic/",
                "mistralai/",
            ],
        ),
        "cohere": (
            CohereAPI,
            "COHERE_API_KEY",
            [
                "command",
            ],
        ),
        "mistral": (
            MistralAPI,
            "MISTRAL_API_KEY",
            [
                "mistral-",
            ],
        ),
    }

    def find_provider(model_name: str) -> str:
        model = model_name.lower()

        for provider, (_, _, prefixes) in provider_map.items():
            for prefix in prefixes:
                if model.startswith(prefix):
                    return provider

        raise ValueError(
            f"Could not determine provider for model '{model_name}'."
        )

    priority_provider = find_provider(priority_model_name)

    ordered_providers: dict[str, list] = {}

    cls, env_prefix, _ = provider_map[priority_provider]

    keys = _load_keys(env_prefix)

    if not keys:
        raise RuntimeError(
            f"No API keys found for {priority_provider}"
        )

    ordered_providers[priority_provider] = [
        cls(
            api_key=key,
            model_name=priority_model_name,
            **(
                {"api_url": priority_provider_url}
                if priority_provider_url else {}
            )
        )
        for key in keys
    ]

    for name, (cls, env_prefix, _) in provider_map.items():
        if name == priority_provider:
            continue

        keys = _load_keys(env_prefix)

        ordered_providers[name] = [
            cls(
                api_key=key,
            )
            for key in keys
        ]

    return ordered_providers
