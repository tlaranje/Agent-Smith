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
    """
    Load numbered API keys (e.g. PREFIX_0, PREFIX_1, ...) from
    the environment, falling back to a single unsuffixed PREFIX.
    """
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
    priority_model_name: str, priority_provider_url: str | None
) -> dict[str, list]:
    """
    Build the ordered mapping of provider name to LLM clients.

    The provider matching the requested priority model is placed
    first (using all its available keys and the given provider
    URL), followed by every other configured provider, so the
    agent can fail over between them.

    Args:
        priority_model_name: Name of the model to use first.
        priority_provider_url: Optional custom API URL to use
            only for the priority provider's clients.

    Returns:
        A dict mapping provider name to a list of instantiated
        API clients, with the priority provider listed first.

    Raises:
        ValueError: If no provider matches priority_model_name.
        RuntimeError: If no API keys are found for the provider
            that matches priority_model_name.
    """
    from .gemini import GeminiAPI
    from .groq import GroqAPI
    from .open_router import OpenRouterAPI
    from .cohere import CohereAPI
    from .mistral import MistralAPI
    from .cerebras import CerebrasAPI
    from .local import LocalAPI

    # Each provider maps to (client class, env var prefix, list of
    # model-name prefixes used to detect this provider). A provider
    # with `env_prefix` set to None does not require API keys (for
    # example local self-hosted models).
    provider_map = {
        "gemini": (GeminiAPI, "GEMINI_API_KEY", [
            "gemini/", "gemini-"
        ]),
        "groq": (GroqAPI, "GROQ_API_KEY", [
            "groq/", "llama-", "llama3-", "mixtral-"
        ]),
        "openrouter": (OpenRouterAPI, "OPENROUTER_API_KEY", [
                "openrouter/", "meta-llama/", "google/",
                "anthropic/", "mistralai/"
        ]),
        "cohere": (CohereAPI, "COHERE_API_KEY", ["cohere/", "command"]),
        "mistral": (MistralAPI, "MISTRAL_API_KEY", [
            "mistral/", "mistral-", "codestral-", "devstral-", "open-mistral-"
        ]),
        "cerebras": (CerebrasAPI, "CEREBRAS_API_KEY", [
            "cerebras/", "gpt-oss-", "gemma-4-", "zai-glm-"
        ]),
        "local": (LocalAPI, None, ["local/", "local-"]),
    }

    def find_provider(model_name: str) -> str:
        """
        Find the provider whose longest matching prefix fits model_name.

        Raises:
            ValueError: If no provider prefix matches.
        """
        model = model_name.lower()
        best_provider = None
        best_prefix_len = -1
        for provider, (_, _, prefixes) in provider_map.items():
            for prefix in prefixes:
                if model.startswith(prefix) and len(prefix) > best_prefix_len:
                    best_provider = provider
                    best_prefix_len = len(prefix)
        if best_provider is None:
            raise ValueError(
                f"Could not determine provider for model '{model_name}'."
            )
        return best_provider

    priority_provider = find_provider(priority_model_name)
    ordered_providers: dict[str, list] = {}

    # Instantiate the priority provider first, using every key
    # found and the (optional) custom provider URL.
    cls, env_prefix, _ = provider_map[priority_provider]
    # Providers with env_prefix == None are keyless (local models).
    if env_prefix is None:
        ordered_providers[priority_provider] = [
            cls(
                model_name=priority_model_name,
                **(
                    {"api_url": priority_provider_url}
                    if priority_provider_url else {}
                )
            )
        ]
    else:
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

    # Add the remaining providers as fallbacks, in declaration
    # order, using their default model name and URL.
    for name, (cls, env_prefix, _) in provider_map.items():
        if name == priority_provider:
            continue
        if env_prefix is None:
            # Keyless provider (local) - instantiate without api_key.
            ordered_providers[name] = [cls()]
            continue

        keys = _load_keys(env_prefix)
        ordered_providers[name] = [
            cls(
                api_key=key,
            )
            for key in keys
        ]

    return ordered_providers
