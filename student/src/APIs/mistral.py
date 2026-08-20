from mistralai.client.models import (
    AssistantMessage, SystemMessage, ToolMessage, UserMessage,
)
from typing import Any, List, TypeAlias, Union
from mistralai.client import Mistral
import time

Message: TypeAlias = Union[
    UserMessage, AssistantMessage, SystemMessage, ToolMessage
]


class MistralAPI:

    def __init__(
        self, api_key: str, model_name: str = "codestral-latest",
        api_url: str = "https://api.mistral.ai",
    ) -> None:
        self.api_key: str = api_key
        self.model_name: str = model_name
        self.api_url: str = api_url
        self.client: Mistral = Mistral(
            api_key=api_key,
            server_url=api_url,
            timeout_ms=8000,
        )

    def generate_messages(
        self, messages: List[Message], max_output_tokens: int = 700,
        max_retries: int = 1
    ) -> Any:
        """
        Send messages to the Mistral chat API, retrying with
        exponential backoff on rate-limit errors, and wrap the
        result in a common LLMResponse.

        Args:
            messages: Conversation history as Mistral message
                objects (user, assistant, system, or tool).
            max_retries: Maximum number of attempts before giving
                up on rate-limit errors.

        Returns:
            An LLMResponse with the generated content and token
            usage counts.

        Raises:
            Exception: Re-raised immediately for any non-rate-limit
                error, or after exhausting max_retries for
                rate-limit errors.
            RuntimeError: If the retry loop exits without returning
                or raising (should not normally happen).
        """
        from . import LLMResponse

        delay: float = 2.0

        for attempt in range(max_retries):
            try:
                response = self.client.chat.complete(
                    model=self.model_name,
                    messages=messages,
                    max_tokens=max_output_tokens,
                )

                usage = response.usage
                input_tokens = (
                    usage.prompt_tokens if usage is not None else 0
                )
                output_tokens = (
                    usage.completion_tokens if usage is not None else 0
                )
                message = response.choices[0].message
                content = (
                    message.content
                    if message and isinstance(message.content, str)
                    else ""
                )

                return LLMResponse(
                    content=content,
                    input_tokens=(
                        input_tokens if input_tokens is not None else 0
                    ),
                    output_tokens=(
                        output_tokens if output_tokens is not None else 0
                    ),
                    model_name=response.model,
                )

            except Exception as e:
                error_msg = str(e)
                is_rate_limit = (
                    "429" in error_msg
                    or "Too Many Requests" in error_msg
                    or "quota" in error_msg.lower()
                )

                if is_rate_limit:
                    # Exhausted retries on a rate-limit error:
                    # give up and propagate the exception.
                    if attempt == max_retries - 1:
                        raise e

                    # Exponential backoff before the next attempt.
                    time.sleep(delay)
                    delay *= 2
                else:
                    # Non-rate-limit errors are not retried.
                    raise e

        # Should be unreachable: the loop above always either
        # returns or raises.
        raise RuntimeError(
            "Critical failure: Agent Smith exceeded the retry limit."
        )
