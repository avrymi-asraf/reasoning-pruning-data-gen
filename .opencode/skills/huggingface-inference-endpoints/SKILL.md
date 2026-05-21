---
name: huggingface-inference-endpoints
description: Guides Hugging Face serverless inference and dedicated Inference Endpoint deployment, especially custom model architectures, custom Docker images, endpoint health routes, and OpenAI-compatible serving for LiteLLM. Use when creating or debugging HF Inference Endpoints, custom handlers, custom images, or provider support failures.
---

<huggingface-inference-endpoints>
Use this skill when deploying or debugging Hugging Face serverless inference, provider-routed inference, or dedicated Inference Endpoints. It focuses on the failure boundary between Hub model repos, provider catalogs, HF Inference Toolkit handlers, TGI, and bespoke Docker images. For LiteLLM-backed applications, prefer endpoints that expose a known API shape such as OpenAI-compatible `/v1/chat/completions` and verify that shape before debugging prompts or model behavior.
</huggingface-inference-endpoints>

<serverless-provider-limitations>
Public Hub visibility does not guarantee that a model can run through HF serverless inference. Provider routes can fail because the selected provider does not support the repo, the model is not exposed as a chat model, or the provider's catalog has not onboarded that architecture. Routes such as `hf-inference`, Together, and SambaNova only work when their backend catalog supports the specific repo/model; treat provider unsupported/not-chat-model errors as serving support failures, not prompt failures.
</serverless-provider-limitations>

<dedicated-endpoints-and-handlers>
A dedicated HF Inference Endpoint with `handler.py` can be enough when the default HF Inference Toolkit stack supports the model's architecture and dependencies. Architectures that require bleeding-edge Transformers or unusual import paths may fail before `handler.py` runs, because the toolkit imports pinned or incompatible dependencies during startup. This can happen even for a regular target model, not only a custom assistant architecture, when the model metadata expects a dev Transformers version. When startup logs show dependency/model-type import failures before handler code executes, move to a full custom image rather than repeatedly editing the handler.
</dedicated-endpoints-and-handlers>

<custom-image-workflow>
Use a custom image when the model needs exact runtime control. `huggingface_hub` supports both `create_inference_endpoint(..., custom_image=...)` and `update_inference_endpoint(..., custom_image=...)`; the shape is:

```python
custom_image={"url": "<registry>/<image>:<tag>", "health_route": "/health"}
```

Set `MODEL_PATH=/repository` and load the model from `/repository`, because HF mounts the model repo there. The image should install the exact Transformers/runtime version needed, avoid HF Inference Toolkit if it conflicts, serve `/health`, and expose the inference route your client expects. For LiteLLM, prefer an OpenAI-compatible `/v1/chat/completions` route so the endpoint can be configured with a stable `base_url`/`api_base`.
</custom-image-workflow>

<tgi-limitations>
TGI is not a universal custom model runtime. It only works for architectures supported by that TGI build, so a public TGI image can start, download the repo, and then fail with unsupported `model_type`. If the architecture is custom, verify TGI support before spending time on endpoint prompts or handler changes.
</tgi-limitations>

<cost-and-safety>
Pause failed or idle dedicated endpoints while debugging to avoid unnecessary cost. Never print, commit, or paste `HF_TOKEN`; pass credentials through environment variables or HF-managed endpoint secrets. Logs and manifests should record that a token or base URL was configured, not the secret value itself.
</cost-and-safety>

<case-study-reasoning-pruning-gemma4>
In this project, `avreymi/reasoning-pruning-gemma-4-E2B-it-assistant` uses custom `Gemma4AssistantForCausalLM` with `model_type=gemma4_assistant`. Serverless routes `hf-inference`, `together`, and `sambanova` failed because provider routing did not support the repo/model as served. A dedicated endpoint with `handler.py` and `requirements.txt` pushed at revision `b3e057db790b87c21060af335e9e18a32d72beaa` still failed before the handler due to bleeding-edge Transformers/Gemma4 import conflicts in the default Inference Toolkit. TGI tag `3.3.5` was unavailable, and TGI `3.3.4` failed with unsupported `gemma4_assistant`.

The regular copied target repo `avreymi/reasoning-pruning-gemma-4-E2B-it` from `google/gemma-4-E2B-it` uses `Gemma4ForConditionalGeneration` with `model_type=gemma4`, but serverless chat/text-generation routes still did not serve the private copied repo, and a default custom endpoint also failed during the Transformers import/`AutoModelForCausalLM` path before inference. The lesson is that switching from assistant to regular Gemma 4 avoids the `gemma4_assistant` rejection, but not the default-runtime incompatibility. The correct next path for either repo is a bespoke FastAPI/Transformers image in a registry HF can pull.
</case-study-reasoning-pruning-gemma4>
