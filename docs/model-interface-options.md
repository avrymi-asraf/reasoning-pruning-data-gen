# Gemma4 Model Interface Options for Data Generation

This document records the model-interface and execution paths tested for running the Gemma4 generation model in the reasoning-pruning data-generation project. The project needs a reliable way to generate reasoning traces for batch dataset creation; it does not currently need a permanent always-on serving API. The current choice for this project is to run the normal config-driven data-generation runner with a Transformers generation provider, optionally inside Hugging Face Jobs.

## Current decision

Use the existing **config-driven runner** as the only workflow for Gemma4 batch generation. Hugging Face Jobs is just the paid execution environment for that normal command.

Why this is the best fit now:

- The repo architecture is config-driven: `config/*.toml` selects source data, generation backend, decision model, limits, and outputs.
- The data-generation workload is batch-oriented: run jobs, write JSONL, inspect outputs, release/version datasets.
- Hugging Face Jobs can run custom Python with selected paid hardware, secrets, logs, and timeouts.
- Jobs avoid maintaining a permanent serving endpoint while still running on hardware large enough for the model.
- Validation succeeded on `a10g-large` with the correct Gemma4 chat-template invocation and generated-token-only decoding.
- This path keeps generation, pruning decisions, validation, manifests, and output writing in one project-supported code path.

Run it locally from this repo checkout as:

```bash
uv run --extra hf --extra gemma4 python scripts/create_pruning_dataset.py --config config/bbh-logical-deduction-gemma4-hf-preview.toml
```

For paid hardware, run that same project command inside a Hugging Face Job from a remote repo checkout or a container image that already contains the current repo. The HF Jobs shape is `hf jobs run IMAGE COMMAND...`; it is not a special `uv` subcommand:

```bash
hf jobs run IMAGE uv run --extra hf --extra gemma4 python scripts/create_pruning_dataset.py --config config/bbh-logical-deduction-gemma4-hf-preview.toml
```

Do not treat this as directly runnable for the current local tree unless the image or command first provides the repo contents. The current local blocker is that there is no git remote/local folder mount available to HF Jobs, so a paid config-driven job needs either a pushed remote that the job can clone or an image containing the current repo. Pass required credentials as HF Job secrets/environment variables, including `HF_TOKEN` for gated model/dataset access and `GEMINI_API_KEY` for the configured Gemini decision model.

The prior standalone HF Jobs script was deleted because it bypassed the project architecture, split raw generation away from the pruning/decision flow, and created a second hidden workflow. Do not recreate dedicated model/job scripts for normal dataset generation; add provider/backend support to `scripts/llm_client.py` and config fields instead.

## Relevant model repositories

Two model repository shapes matter for the interface decisions:

| Repo | Shape | Notes |
| --- | --- | --- |
| `avreymi/reasoning-pruning-gemma-4-E2B-it-assistant` | Custom assistant model | Uses custom architecture `Gemma4AssistantForCausalLM`. Useful for the assistant-tuned variant, but many hosted inference systems reject or cannot route custom architectures. |
| `avreymi/reasoning-pruning-gemma-4-E2B-it` | Regular copied model | Copied from `google/gemma-4-E2B-it`; regular `model_type=gemma4`; loads as `Gemma4ForConditionalGeneration`. This is easier for custom Python jobs and dependency validation, but still not automatically supported by all hosted inference providers. |

## Comparison table

| Option | What it is good for | Result | Verdict |
| --- | --- | --- | --- |
| Config-driven runner with Transformers generation provider | Keeping generation, pruning decisions, validation, manifests, and output writing behind `scripts/create_pruning_dataset.py --config config/*.toml`; running the same command locally for validation or inside HF Jobs for paid hardware. | Chosen path. `provider="transformers"` lazy-loads torch/Transformers only for generation, while the decision model remains the existing LiteLLM/Gemini config. | Use this workflow. |
| LiteLLM config-driven interface | Calling hosted generation and decision models behind the existing config-driven path; switching providers without changing core pipeline logic. | Structural support exists for `provider="huggingface"` and `base_url`/`api_base`. It works as an interface layer only if there is a working endpoint/server behind it. | Keep for hosted endpoints, but not the current Gemma4 batch path. |
| Hugging Face Serverless / Inference Providers | Zero-ops hosted inference when a model is in a supported provider/catalog path. | Failed for the custom assistant architecture. The regular copied repo also was not routed as a supported chat model. Provider/catalog support is decisive; repository metadata alone was not enough. | Not viable for Gemma4 here right now. |
| Dedicated Hugging Face Inference Endpoint, default runtime | Managed always-on or scalable endpoint without maintaining full custom infrastructure. | Tried `handler.py` and `requirements.txt`. The default HF Inference Toolkit/runtime failed before useful inference because it could not handle bleeding-edge Gemma4/custom imports/loaders. Endpoint was paused to avoid cost. | Not viable with the default runtime for this model stack now. |
| TGI | High-throughput text generation serving for supported causal/chat models. | TGI supports Gemma/Gemma2/Gemma3 families but not Gemma4 in the tested path. It rejected the assistant/custom `model_type`. | Not viable until Gemma4 support lands and is verified. |
| Custom Docker endpoint | Permanent API with full control over dependencies, loaders, endpoints, and request/response shape. | Built and pushed `docker.io/avreymi/reasoning-pruning-gemma4-endpoint:gemma4-e2b-it-20260521`, digest `sha256:46fb178bd30733029893eda6145ddc8d6e764205da28d9982a664b152bffe11a`. Image exposes `/health`, `/generate`, and `/v1/chat/completions`; model path is `/repository`. | Technically viable later for a permanent API, but more moving parts than needed for batch dataset creation. |
| Local generation | Cheap validation of dependencies, class mappings, tokenization, and small code paths. | Dependency validation succeeded in `/tmp/opencode/gemma4-dep-venv`; `AutoProcessor`, tokenizer, config, and model mappings work. Full generation is unsafe on local 8GB VRAM for about 10GB weights. | Use only for zero-cost class/dependency checks, not real generation. |
| Hugging Face Jobs | Paid ephemeral batch runs with custom Python, selected hardware, secrets/env, logs, and timeout control. | Validated as an execution environment on `a10g-large`. Historical standalone validation proved the model-loading/decode pattern, but no special scripts are part of the current workflow. | Chosen path for this project. |

## Details by option

### 1. Config-driven runner with Transformers generation provider

The existing project architecture is config-driven: `config/*.toml` selects source datasets, generation and decision models, prompts, limits, and output locations. Gemma4 now uses that same path by setting generation `provider = "transformers"` in `config/bbh-logical-deduction-gemma4-hf-preview.toml` and running the normal runner:

```bash
uv run --extra hf --extra gemma4 python scripts/create_pruning_dataset.py --config config/bbh-logical-deduction-gemma4-hf-preview.toml
```

For paid hardware, run the same project command in Hugging Face Jobs from a remote clone or image containing this repo. The command shape is:

```bash
hf jobs run IMAGE uv run --extra hf --extra gemma4 python scripts/create_pruning_dataset.py --config config/bbh-logical-deduction-gemma4-hf-preview.toml
```

This is an execution-environment pattern, not a complete command for the current local checkout. Without a pushed git remote or an image containing the current repo, HF Jobs has no local folder mount to run from. Provide `HF_TOKEN` and `GEMINI_API_KEY` through HF Job secrets/environment variables.

The generation backend lazy-imports torch/Transformers only when `provider="transformers"`, applies the Gemma4 chat template with `add_generation_prompt=True`, moves tensors to the model device, and decodes only generated tokens. The decision model remains configured through the existing LiteLLM/Gemini `[decision]` section.

Verdict: this is the chosen workflow.

### 2. LiteLLM config-driven interface

The existing project architecture is config-driven: `config/*.toml` selects source datasets, generation and decision models, prompts, limits, and output locations. The pipeline then calls `scripts/create_pruning_dataset.py`, which delegates model calls through `scripts/llm_client.py` and writes records/manifests through the pipeline/storage layer.

For Gemma4 hosted generation, the interface was extended so configs can specify the Hugging Face provider and endpoint base URL. This gives the pipeline a clean way to call a hosted model once a server exists.

What works:

- `provider="huggingface"` can be represented in config.
- Configured `base_url` can be mapped to LiteLLM `api_base`.
- Manifest metadata is sanitized so it records provider/model and whether a base URL was configured, without persisting raw endpoint URLs.

What does not work by itself:

- LiteLLM is only the client abstraction. It cannot fix unsupported model hosting.
- It still requires a working Hugging Face Inference Endpoint, custom Docker endpoint, or other OpenAI-compatible endpoint.

Verdict: keep LiteLLM for the decision model and hosted generation endpoints, but use the Transformers provider for Gemma4 batch generation unless a reliable serving endpoint exists.

### 3. Hugging Face Serverless / Inference Providers

Serverless inference and Inference Providers are attractive because they avoid endpoint setup. For this project they were not sufficient.

Observed outcome:

- The assistant/custom architecture repo `avreymi/reasoning-pruning-gemma-4-E2B-it-assistant` was not usable through this path.
- The regular copied repo `avreymi/reasoning-pruning-gemma-4-E2B-it` also was not routed as a supported chat model.
- The failure mode appears provider/catalog driven. A repository can have reasonable metadata and still not be accepted by the hosted provider path.

Verdict: not a dependable path for Gemma4 generation in this project at this time.

### 4. Dedicated Hugging Face Inference Endpoint with default runtime

A dedicated endpoint would fit the existing LiteLLM interface if the runtime could load the model. The default Hugging Face Inference Endpoint runtime was tested with repository-level customization (`handler.py` and `requirements.txt`).

Observed outcome:

- The endpoint failed before useful inference.
- The default HF Inference Toolkit/runtime could not handle the required bleeding-edge Gemma4/custom imports/loaders.
- The endpoint was paused to avoid unnecessary cost.

Verdict: not viable with the default runtime for this model stack right now. Revisit only if HF endpoint runtimes support Gemma4 directly or if the project chooses a custom container endpoint.

### 5. TGI

Text Generation Inference would be a strong serving option if the model family were supported.

Observed outcome:

- TGI supports earlier Gemma families such as Gemma, Gemma2, and Gemma3 in the relevant paths.
- The tested TGI path did not support Gemma4.
- It rejected the assistant/custom `model_type`.

Verdict: not viable now. Re-check later if TGI adds Gemma4 support and verify with the regular copied model before trying custom assistant variants.

### 6. Custom Docker endpoint

A custom Docker endpoint gives full control over runtime dependencies and API shape. This is the right approach if the project later needs a long-running OpenAI-compatible Gemma4 API.

Built image:

```text
docker.io/avreymi/reasoning-pruning-gemma4-endpoint:gemma4-e2b-it-20260521
sha256:46fb178bd30733029893eda6145ddc8d6e764205da28d9982a664b152bffe11a
```

Image stack:

- PyTorch CUDA runtime
- `torch 2.12` with CUDA 13.0
- `torchvision 0.27` with CUDA 13.0
- Transformers development commit `52b82b2`
- `accelerate`
- `safetensors`
- `sentencepiece`
- `tokenizers`
- `huggingface_hub`
- FastAPI/Uvicorn

Exposed endpoints:

- `/health`
- `/generate`
- `/v1/chat/completions`

Runtime model path:

```text
/repository
```

What works:

- Full dependency control.
- Can expose an OpenAI-compatible chat endpoint for LiteLLM.
- Can be reused later if the project needs a persistent model server.

What is not ideal now:

- More operational surface than needed for batch generation.
- Requires endpoint deployment, monitoring, runtime debugging, and cost management.
- The project currently needs generated dataset artifacts more than a permanent API.

Verdict: viable later for permanent serving; not the chosen first path for data generation.

### 7. Local generation

Local validation was useful for confirming the Python dependency stack and model class mappings without paying for cloud runtime.

Observed outcome:

- Dependency validation succeeded in `/tmp/opencode/gemma4-dep-venv`.
- `AutoProcessor`, tokenizer, config, and model mappings work.
- The regular model path can resolve to Gemma4 classes, including `Gemma4ForConditionalGeneration`.
- Full generation is unsafe on local 8GB VRAM because the weights are roughly 10GB and generation needs additional memory.

Verdict: use local runs for class/dependency checks only. Do not use local full generation as the real data-generation path on the current machine.

### 8. Hugging Face Jobs

Hugging Face Jobs are the chosen execution environment for paid Gemma4 batch runs. They are paid, ephemeral command runs on selected HF hardware. They can receive environment variables/secrets, run the normal project command, stream logs, and terminate when the batch job finishes.

Validation results:

- Job `6a0e9756ac8efd7fbbb2ad43` on `a10g-large` loaded the model and ran, but decoded only the prompt. The issue was not model loading; it was the generation/decode pattern. The script did not correctly apply the chat template with a generation prompt and did not decode generated tokens only.
- Job `6a0e98d93fef25139d6ca713` on `a10g-large` succeeded. It used `processor.apply_chat_template(..., add_generation_prompt=True, tokenize=True, return_dict=True, return_tensors="pt")` and decoded only the new generated tokens. The generated output was:

```text
If $x=2$, then $x+3 = 2+3 = 5$.
```
- Preview batch job `6a1016afb33ece92698c0377` completed on `a10g-large` with the now-deleted standalone script. That result validated the model-loading and decoding pattern, but the script was removed because it bypassed the repo's config-driven pipeline.

Verdict: use HF Jobs only to run the normal `scripts/create_pruning_dataset.py --config ...` command on suitable hardware.

## Correct Gemma4 generation pattern

The Transformers provider uses the chat template and decodes only generated tokens. It also uses `dtype=` rather than deprecated `torch_dtype=` when loading models.

```python
import torch
from transformers import AutoProcessor, Gemma4ForConditionalGeneration

model_id = "avreymi/reasoning-pruning-gemma-4-E2B-it"

processor = AutoProcessor.from_pretrained(model_id)
model = Gemma4ForConditionalGeneration.from_pretrained(
    model_id,
    dtype=torch.bfloat16,
    device_map="auto",
)

messages = [
    {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": "If x = 2, what is x + 3? Show one short reasoning step.",
            }
        ],
    }
]

inputs = processor.apply_chat_template(
    messages,
    add_generation_prompt=True,
    tokenize=True,
    return_dict=True,
    return_tensors="pt",
)
inputs = {key: value.to(model.device) for key, value in inputs.items()}

with torch.inference_mode():
    output_ids = model.generate(
        **inputs,
        max_new_tokens=128,
        do_sample=False,
    )

prompt_length = inputs["input_ids"].shape[-1]
generated_ids = output_ids[0][prompt_length:]
text = processor.decode(generated_ids, skip_special_tokens=True).strip()

print(text)
```

Important notes:

- Use `processor.apply_chat_template` for chat-format inputs.
- Pass `add_generation_prompt=True` so generation starts in the assistant slot.
- Pass `tokenize=True`, `return_dict=True`, and `return_tensors="pt"` for model-ready tensors.
- Move tensors to the model device before generation.
- Decode `output_ids[0][prompt_length:]`, not the full sequence, otherwise the output can appear to be only the prompt or can include prompt text mixed with generated text.
- Prefer `dtype=` over deprecated `torch_dtype=` in future scripts.

## Operational recommendations

### Secrets and environment

- Use `.env`, HF Job secrets, or environment variables for `HF_TOKEN`.
- Never print tokens, endpoint URLs with credentials, or secret environment values.
- Keep logs useful but sanitized: model repo, job id, hardware, counts, paths, and errors are useful; secrets are not.

### Cost and lifecycle

- Treat HF Jobs and endpoints as paid resources.
- Start with very small preview jobs: one or a few prompts, low `max_new_tokens`, clear timeout.
- Confirm the output shape before scaling.
- Prefer jobs that terminate automatically after writing artifacts.
- Pause or delete unused endpoints.

### Artifact storage

Local `outputs/` files are temporary R&D outputs. Serious datasets should be copied or written into private Hugging Face dataset repositories under the adjacent artifact store:

```text
../reasoning-pruning-datasets
```

Generator model/checkpoint references should point to private model repos or clear remote artifacts under:

```text
../reasoning-pruning-models
```

Every serious run must preserve this chain:

```text
generator checkpoint -> generated dataset version -> trained checkpoint
```

For this repo, the dataset manifest should record at least:

- generator model repo and revision/commit when available
- generation script/config version
- decision model and decision config
- source dataset/config/split/limit
- output dataset repo/path/version
- accepted/rejected counts
- manual inspection notes or quality status
- data repo commit when available

### Integration with the existing pipeline

The existing pipeline expects a generation model interface and then runs pruning decisions, validation, and JSONL writing. Gemma4 is integrated as `provider="transformers"` in the normal generation config, so HF Jobs should run the full data-generation flow inside the job rather than producing side-channel raw generations.

Do not create a second hidden workflow that bypasses manifests and versioning. The output must still be reviewed JSONL plus manifest artifacts that downstream training can consume.

## Next implementation plan

1. Run the preview through the normal runner in HF Jobs.
2. Inspect accepted/rejected JSONL and manifest.
3. Version artifacts.
   - Copy accepted JSONL, rejected/audit JSONL, and manifest into the private dataset repo under `../reasoning-pruning-datasets`.
   - Commit and tag/version the dataset.
   - Record the exact generator model reference and dataset commit for downstream training.
4. Only after this path is stable, consider whether a permanent custom Docker endpoint is worth maintaining.

## Final recommendation

For the current R&D stage, use the normal config-driven runner with the Transformers generation provider, and run that command inside Hugging Face Jobs when paid hardware is needed. The custom Docker endpoint is valuable as a fallback or future API path, but the config-driven batch workflow is simpler, cleaner, and better aligned with the project goal: create inspected, versioned reasoning-pruning datasets with reproducible model and dataset metadata.
