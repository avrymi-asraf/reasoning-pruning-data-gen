"""LiteLLM client wrapper for the reasoning-pruning data runner.

The config parser builds LLMConfig objects and the pruning flow calls this module.
Provider/model choices stay explicit while LiteLLM model strings do routing, including
Hugging Face serverless and dedicated endpoint calls. Configured endpoint URLs are
forwarded only to LiteLLM and are not printed or added to manifests by this layer.
Secrets are read by provider SDKs from the environment; this file never prints them.
"""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_MODEL = "gemini/gemini-2.5-flash-lite"
ALLOWED_PROVIDERS = {"gemini", "openai", "openai-compatible", "local", "huggingface"}


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str = DEFAULT_MODEL
    base_url: str | None = None
    temperature: float = 0.0
    max_tokens: int | None = None
    timeout: int | float | None = None
    retries: int = 0

    def __post_init__(self) -> None:
        if self.provider not in ALLOWED_PROVIDERS:
            allowed = ", ".join(sorted(ALLOWED_PROVIDERS))
            raise ValueError(f"Unsupported provider '{self.provider}'. Choose one of: {allowed}.")
        if not self.model:
            raise ValueError("LLM model must not be empty.")


def call_llm(
    prompt: str,
    config: LLMConfig,
    *,
    system: str | None = None,
    response_format: dict[str, str] | None = None,
) -> str:
    """Call a real LiteLLM model and return the message text."""
    try:
        from litellm import completion  # type: ignore
    except ImportError as exc:
        raise RuntimeError("LiteLLM is required. Install project dependencies with uv sync.") from exc

    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    kwargs: dict[str, object] = {
        "model": config.model,
        "messages": messages,
        "temperature": config.temperature,
    }
    if response_format is not None:
        kwargs["response_format"] = response_format
    if config.base_url:
        kwargs["api_base"] = config.base_url
    if config.max_tokens is not None:
        kwargs["max_tokens"] = config.max_tokens
    if config.timeout is not None:
        kwargs["timeout"] = config.timeout
    if config.retries:
        kwargs["num_retries"] = config.retries

    response = completion(**kwargs)
    return str(response.choices[0].message.content)
