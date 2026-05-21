"""
handler.py — Custom Inference Endpoint handler for Gemma 4 E2B Assistant.

This handler enables Hugging Face Inference Endpoints to serve the custom
Gemma4AssistantForCausalLM architecture, which is not supported by HF's
default serverless inference pipeline.

The handler accepts OpenAI-compatible chat completions (messages array),
applies the Gemma 4 chat template, generates text, and returns the response
in OpenAI chat completion format. This makes it compatible with LiteLLM's
huggingface/tgi provider routing.

Usage:
    - Place handler.py and requirements.txt in the model repo root.
    - Deploy as a Custom Inference Endpoint on Hugging Face.
    - LiteLLM calls: model="huggingface/tgi", api_base="<endpoint-url>"
"""

from typing import Any, Dict, List

import torch
from transformers import AutoModelForCausalLM, AutoProcessor


class EndpointHandler:
    """Custom handler for Gemma 4 E2B Assistant on HF Inference Endpoints."""

    def __init__(self, path: str = ""):
        """Load model and processor at endpoint startup.

        Args:
            path: Local path to model weights (provided by HF Inference Toolkit).
        """
        self.processor = AutoProcessor.from_pretrained(path)
        self.model = AutoModelForCausalLM.from_pretrained(
            path,
            torch_dtype=torch.bfloat16,
            device_map="auto",
        )
        self.model.eval()

    def __call__(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single chat completion request.

        Args:
            data: Request payload containing:
                - messages: List of {role, content} dicts (OpenAI format)
                - temperature: Sampling temperature (default: 0.2)
                - max_tokens: Max new tokens (default: 1200)
                - top_p: Top-p sampling (default: 0.95)
                - top_k: Top-k sampling (default: 64)

        Returns:
            OpenAI-compatible chat completion response dict.
        """
        # Extract parameters
        messages = data.get("messages", [])
        temperature = data.get("temperature", 0.2)
        max_tokens = data.get("max_tokens", 1200)
        top_p = data.get("top_p", 0.95)
        top_k = data.get("top_k", 64)

        # Apply chat template (no thinking mode for pruning data generation)
        prompt = self.processor.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        # Tokenize
        inputs = self.processor(text=prompt, return_tensors="pt").to(
            self.model.device
        )
        input_len = inputs["input_ids"].shape[-1]

        # Generate
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                max_new_tokens=max_tokens,
                do_sample=temperature > 0,
            )

        # Decode only the generated tokens
        generated_text = self.processor.decode(
            outputs[0][input_len:], skip_special_tokens=False
        )

        # Return OpenAI-compatible format
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": generated_text,
                    },
                    "finish_reason": "stop",
                    "index": 0,
                }
            ],
            "usage": {
                "prompt_tokens": int(input_len),
                "completion_tokens": int(outputs[0].shape[-1] - input_len),
                "total_tokens": int(outputs[0].shape[-1]),
            },
        }
