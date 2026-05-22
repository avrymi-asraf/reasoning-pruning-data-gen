---
name: huggingface-inference-endpoints
description: Guides Hugging Face serverless inference and dedicated Inference Endpoint deployment, especially custom model architectures, custom Docker images, endpoint health routes, and OpenAI-compatible serving for LiteLLM. Use when creating or debugging HF Inference Endpoints, custom handlers, custom images, or provider support failures.
---

<huggingface-inference-endpoints>
Use this skill when deploying or debugging Hugging Face serverless inference, provider-routed inference, or dedicated Inference Endpoints. It focuses on the failure boundary between Hub model repos, provider catalogs, HF Inference Toolkit handlers, TGI, and bespoke Docker images. For LiteLLM-backed applications, prefer endpoints that expose a known API shape such as OpenAI-compatible `/v1/chat/completions` and verify that shape before debugging prompts or model behavior.
</huggingface-inference-endpoints>

<serverless-provider-limitations>
Public Hub visibility and repo metadata do not guarantee that a model can run through HF serverless/provider inference. Provider routes can fail because the provider catalog has not deployed that repo/architecture, even if `pipeline_tag`, `library_name`, and chat templates are correct. Metadata controls Hub display, filtering, widgets, and API task inference, but it does not force Together/SambaNova/HF provider onboarding. Before debugging prompts, check whether the public source model is deployed by an Inference Provider; if it is not, a private copy is unlikely to become provider-routable just by changing tags.
</serverless-provider-limitations>

<dedicated-endpoints-and-handlers>
A dedicated HF Inference Endpoint with `handler.py` can be enough when the default HF Inference Toolkit stack supports the model's architecture and dependencies. `requirements.txt` and `handler.py` customize work inside the Toolkit runtime, but they are not a reliable way to fix failures that occur before the handler is imported. Architectures that require bleeding-edge Transformers or unusual import paths may fail during toolkit startup; this can happen even for a regular target model, not only a custom assistant architecture. When startup logs show dependency/model-type import failures before handler code executes, prefer a different endpoint engine such as vLLM/SGLang if compatible, or move to a full custom image rather than repeatedly editing the handler.
</dedicated-endpoints-and-handlers>

<engine-selection>
Choose the endpoint engine before assuming the repo is broken. TGI is optimized but not universal; its supported-model list currently covers Gemma, Gemma2, Gemma3, and Gemma3 Text, not Gemma4, and HF endpoint docs present vLLM/SGLang as first-class engines for new LLM serving. vLLM can serve many Transformer-backed models and may be worth a cheap trial for regular Gemma4, but a validated Transformers custom image is safer when the model requires unreleased Transformers classes. If a model is multimodal or conditional-generation shaped, verify the correct loader/task (`AutoModelForImageTextToText`, `AutoModelForMultimodalLM`, or model-specific docs) rather than assuming `AutoModelForCausalLM` is always the right default.
</engine-selection>

<custom-image-workflow>
Use a custom image when the model needs exact runtime control. `huggingface_hub` supports both `create_inference_endpoint(..., custom_image=...)` and `update_inference_endpoint(..., custom_image=...)`; the shape is:

```python
custom_image={"url": "<registry>/<image>:<tag>", "health_route": "/health"}
```

Set `MODEL_PATH=/repository` and load the model from `/repository`, because HF mounts the selected model repo there. The image should install the exact Transformers/runtime version needed, avoid HF Inference Toolkit if it conflicts, serve `/health`, expose the configured port, and expose the inference route your client expects. For LiteLLM, prefer an OpenAI-compatible `/v1/chat/completions` route so the endpoint can be configured with a stable `base_url`/`api_base`. A public Docker Hub image is the lowest-friction registry path; HF docs also document Docker Hub, AWS ECR, Azure ACR, and Google GCR for custom container image hosting.
</custom-image-workflow>

<gemma4-runtime-notes>
For regular Gemma4, validate the runtime before endpoint spend. A working local stack in May 2026 used Transformers main/dev with `Gemma4Processor` and `Gemma4ForConditionalGeneration`; `AutoProcessor`, `AutoTokenizer`, `AutoModelForCausalLM`, `AutoModelForImageTextToText`, and `AutoModelForMultimodalLM` all mapped correctly in that stack. Include `torchvision` as well as `torch`, `accelerate`, `safetensors`, and `sentencepiece`, because Gemma4 processor import can pass through video/image processor code. If the endpoint runtime lacks these exact pieces, default Toolkit may fail before handler code runs.
</gemma4-runtime-notes>

<tgi-limitations>
TGI is not a universal custom model runtime. It only works for architectures supported by that TGI build, so a public TGI image can start, download the repo, and then fail with unsupported `model_type`. If the architecture is custom, verify TGI support before spending time on endpoint prompts or handler changes.
</tgi-limitations>

<cost-and-safety>
Pause failed or idle dedicated endpoints while debugging to avoid unnecessary cost. Never print, commit, or paste `HF_TOKEN`; pass credentials through environment variables or HF-managed endpoint secrets. Logs and manifests should record that a token or base URL was configured, not the secret value itself.
</cost-and-safety>

<case-study-reasoning-pruning-gemma4>
In this project, `avreymi/reasoning-pruning-gemma-4-E2B-it-assistant` uses custom `Gemma4AssistantForCausalLM` with `model_type=gemma4_assistant`. Serverless routes `hf-inference`, `together`, and `sambanova` failed because provider routing did not support the repo/model as served. A dedicated endpoint with `handler.py` and `requirements.txt` pushed at revision `b3e057db790b87c21060af335e9e18a32d72beaa` still failed before the handler due to bleeding-edge Transformers/Gemma4 import conflicts in the default Inference Toolkit. TGI tag `3.3.5` was unavailable, and TGI `3.3.4` failed with unsupported `gemma4_assistant`.

The regular copied target repo `avreymi/reasoning-pruning-gemma-4-E2B-it` from `google/gemma-4-E2B-it` uses `Gemma4ForConditionalGeneration` with `model_type=gemma4`, but serverless chat/text-generation routes still did not serve the private copied repo, and a default custom endpoint also failed during the Transformers import/`AutoModelForCausalLM` path before inference. The lesson is that switching from assistant to regular Gemma 4 avoids the `gemma4_assistant` rejection, but not the default-runtime incompatibility. The correct next path for either repo is a bespoke FastAPI/Transformers image in a registry HF can pull.

Research in May 2026 found that the public `google/gemma-4-E2B-it` was not deployed by any HF Inference Provider, so provider routing is unlikely for the private copy until the source model/provider catalog changes. For the regular model, the best cheap next endpoint experiment is the official vLLM engine or a task/loader change for Gemma4 before building Docker. For the assistant model, a bespoke image remains most likely unless vLLM's Transformers backend can load the custom architecture with the required trust/runtime settings.
</case-study-reasoning-pruning-gemma4>
