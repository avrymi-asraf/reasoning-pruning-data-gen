"""Model client wrapper for the reasoning-pruning data runner.

The config parser builds LLMConfig objects and the pruning flow calls this module.
Provider/model choices stay explicit while normal runs use LiteLLM and Gemma4 HF
Jobs can run a local Transformers backend through the same config-driven runner.
Configured endpoint URLs are forwarded only to LiteLLM and are not printed or added
to manifests by this layer. Secrets are read by provider SDKs from the environment;
this file never prints them.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any


DEFAULT_MODEL = "gemini/gemini-2.5-flash-lite"
ALLOWED_PROVIDERS = {"gemini", "openai", "openai-compatible", "local", "huggingface", "transformers"}
_TRANSFORMERS_BACKENDS: dict[tuple[str, str | None, str | None, str | None, str], Any] = {}


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str = DEFAULT_MODEL
    base_url: str | None = None
    temperature: float = 0.0
    max_tokens: int | None = None
    timeout: int | float | None = None
    retries: int = 0
    model_revision: str | None = None
    dtype: str | None = None
    device_map: str | None = None
    top_p: float | None = None
    transformers_loader: str = "auto_model_for_image_text_to_text"

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
    """Call the configured model backend and return message text."""
    if config.provider == "transformers":
        return _call_transformers(prompt, config, system=system)

    return _call_litellm(prompt, config, system=system, response_format=response_format)


def _call_litellm(
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


def _call_transformers(prompt: str, config: LLMConfig, *, system: str | None = None) -> str:
    """Run a local Transformers chat-generation backend, loaded lazily for HF Jobs."""
    backend = _transformers_backend(config)
    messages = _transformers_messages(prompt, system)
    return backend.generate(messages, max_new_tokens=config.max_tokens, temperature=config.temperature, top_p=config.top_p)


def _transformers_messages(prompt: str, system: str | None) -> list[dict[str, list[dict[str, str]]]]:
    text = f"{system.strip()}\n\n{prompt}" if system and system.strip() else prompt
    return [{"role": "user", "content": [{"type": "text", "text": text}]}]


def _transformers_backend(config: LLMConfig):
    key = (config.model, config.model_revision, config.dtype, config.device_map, config.transformers_loader)
    if key not in _TRANSFORMERS_BACKENDS:
        _TRANSFORMERS_BACKENDS[key] = TransformersChatBackend(config)
    return _TRANSFORMERS_BACKENDS[key]


class TransformersChatBackend:
    """Small Transformers chat wrapper used only when provider='transformers'."""

    def __init__(self, config: LLMConfig) -> None:
        try:
            import torch  # type: ignore
            from transformers import AutoModelForImageTextToText, AutoProcessor, Gemma4ForConditionalGeneration  # type: ignore
        except ImportError as exc:
            raise RuntimeError("Transformers generation requires: uv run --extra gemma4 ...") from exc

        hf_token = os.environ.get("HF_TOKEN")
        self.torch = torch
        load_kwargs: dict[str, Any] = {}
        if config.model_revision:
            load_kwargs["revision"] = config.model_revision
        if hf_token:
            load_kwargs["token"] = hf_token
        self.processor = AutoProcessor.from_pretrained(config.model, **load_kwargs)
        loader_name = config.transformers_loader
        if loader_name == "gemma4_for_conditional_generation":
            loader = Gemma4ForConditionalGeneration
        elif loader_name == "auto_model_for_image_text_to_text":
            loader = AutoModelForImageTextToText
        else:
            raise ValueError("transformers_loader must be 'auto_model_for_image_text_to_text' or 'gemma4_for_conditional_generation'.")

        kwargs: dict[str, Any] = dict(load_kwargs)
        if config.dtype:
            dtype = _torch_dtype(torch, config.dtype)
            if dtype is not None:
                kwargs["dtype"] = dtype
        if config.device_map:
            kwargs["device_map"] = config.device_map
        self.model = loader.from_pretrained(config.model, **kwargs)

    def generate(self, messages: list[dict[str, list[dict[str, str]]]], *, max_new_tokens: int | None, temperature: float, top_p: float | None) -> str:
        inputs = self.processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        )
        inputs = {key: value.to(self.model.device) for key, value in inputs.items()}
        input_len = inputs["input_ids"].shape[-1]
        do_sample = temperature > 0
        generate_kwargs: dict[str, Any] = {"max_new_tokens": max_new_tokens or 1024, "do_sample": do_sample}
        if do_sample:
            generate_kwargs["temperature"] = temperature
            if top_p is not None:
                generate_kwargs["top_p"] = top_p
        with self.torch.inference_mode():
            output_ids = self.model.generate(**inputs, **generate_kwargs)
        generated_ids = output_ids[0][input_len:]
        return str(self.processor.decode(generated_ids, skip_special_tokens=True)).strip()


def _torch_dtype(torch_module: Any, dtype_name: str):
    normalized = dtype_name.strip().lower()
    mapping = {
        "auto": None,
        "float16": torch_module.float16,
        "fp16": torch_module.float16,
        "bfloat16": torch_module.bfloat16,
        "bf16": torch_module.bfloat16,
        "float32": torch_module.float32,
        "fp32": torch_module.float32,
    }
    if normalized not in mapping:
        raise ValueError("dtype must be one of: auto, float16, fp16, bfloat16, bf16, float32, fp32.")
    return mapping[normalized]
