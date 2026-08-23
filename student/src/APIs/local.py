import os
from typing import Any, List


class LocalAPI:
    """Simple local model wrapper compatible with other API classes.

    Loads a model from LOCAL_MODELS_PATH/<model_name> when the
    provided `model_name` uses the `local/` or `local-` prefix.
    Uses Hugging Face `transformers` pipeline if available.
    """

    def __init__(self, api_key: str | None = None,
                 model_name: str = "local/default",
                 api_url: str | None = None) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.api_url = "local"

        # Determine model folder name: accept both `local/name` and
        # `local-name` syntaxes.
        name = model_name
        if name.startswith("local/"):
            name = name.split("/", 1)[1]
        elif name.startswith("local-"):
            name = name.split("-", 1)[1]

        base = os.getenv("LOCAL_MODELS_PATH", "./local")
        self.model_path = os.path.join(base, name)

        # Lazy-loaded resources
        self._tokenizer = None
        self._model = None
        self._generator = None

    def _ensure_loaded(self) -> None:
        if self._generator is not None:
            return

        try:
            from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
            import torch
        except Exception as e:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "Local models require the 'transformers' and 'torch' packages. "
                f"Import failed: {e}"
            )

        if not os.path.exists(self.model_path):
            raise FileNotFoundError(
                f"Local model path not found: {self.model_path}"
            )

        # Load tokenizer and model; rely on HF auto-detection for device.
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        self._model = AutoModelForCausalLM.from_pretrained(
            self.model_path,
            trust_remote_code=True,
        )

        self._generator = pipeline(
            "text-generation",
            model=self._model,
            tokenizer=self._tokenizer,
            device_map="auto",
            trust_remote_code=True,
        )

    def generate_messages(
        self, messages: List[dict], max_output_tokens: int = 700,
        max_retries: int = 1
    ) -> Any:
        """Generate a completion given a list of OpenAI-style messages.

        Returns an object compatible with `LLMResponse` used across
        the project: (`content`, `input_tokens`, `output_tokens`,
        `model_name`).
        """
        from . import LLMResponse

        # Make sure local model is loaded (may raise helpful errors).
        self._ensure_loaded()

        # Convert message list to a single prompt string.
        prompt_lines = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            prompt_lines.append(f"{role}: {content}")
        prompt = "\n".join(prompt_lines)

        # Prepare a GenerationConfig to avoid the transformers
        # deprecation warnings about mixing generation_config with
        # explicit arguments. Compute a safe `max_length` so the
        # model's `max_length` from disk does not conflict with
        # `max_new_tokens`.
        try:
            from transformers import GenerationConfig
        except Exception:
            GenerationConfig = None

        # Tokenize prompt to compute input length and set max_length
        input_ids = self._tokenizer(prompt).get("input_ids", [])
        input_len = len(input_ids)

        if GenerationConfig is not None:
            gen_conf = GenerationConfig(
                max_new_tokens=max_output_tokens,
                do_sample=False,
                num_return_sequences=1,
                max_length=input_len + max_output_tokens,
            )
            result = self._generator(prompt, generation_config=gen_conf)
        else:
            # Fallback when transformers lacks GenerationConfig: pass
            # explicit args (may trigger deprecation warnings).
            result = self._generator(
                prompt,
                max_new_tokens=max_output_tokens,
                do_sample=False,
                num_return_sequences=1,
            )

        generated_text = result[0].get("generated_text", "")
        content = generated_text
        if generated_text.startswith(prompt):
            content = generated_text[len(prompt) :].lstrip("\n")

        # Token accounting using tokenizer
        total_ids = self._tokenizer(generated_text).get("input_ids", [])
        input_tokens = input_len
        output_tokens = max(0, len(total_ids) - input_tokens)

        return LLMResponse(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model_name=self.model_name,
        )
