# Gemma4 Model Interface Decision Record

## Decision

The active Gemma4 data-generation path is **Hugging Face Jobs running the normal repo CLI/config runner**. HF Jobs is the execution environment; the repo command remains the only data creation interface:

```bash
uv run --extra hf --extra gemma4 python scripts/create_pruning_dataset.py --config config/bbh-logical-deduction-gemma4-hf-preview.toml
```

Use image `ghcr.io/astral-sh/uv:python3.11-bookworm`, flavor `a10g-large`, encrypted `HF_TOKEN` and `GEMINI_API_KEY`, clone/download `https://github.com/avrymi-asraf/reasoning-pruning-data-gen.git`, run the command above, and print sanitized accepted/rejected/manifest summaries. Never print tokens or secret-bearing URLs.

Successful preview reference: HF Job `6a106a46b33ece92698c06f8`, accepted `3`, rejected `0`, generation model `avreymi/reasoning-pruning-gemma-4-E2B-it`, decision model `gemini/gemini-2.5-flash-lite`.

## Why this is the current path

- The project is config-driven: TOML config selects source data, generator, decision model, limits, prompts, and outputs.
- The batch workload should produce inspected JSONL plus manifests, not a long-running serving API.
- HF Jobs provides paid hardware and secrets while keeping the same pipeline, validation, rejected/audit records, and manifest writing.
- The validated Gemma4 path uses the configured Transformers backend for generation and LiteLLM/Gemini for pruning decisions.

## Runbook

1. Keep preview limits small in `config/bbh-logical-deduction-gemma4-hf-preview.toml` or a nearby config.
2. Launch an HF Job using the image/flavor/secrets above.
3. Inside the job, clone/download the repo and run only the canonical command.
4. Print sanitized summaries: output paths, accepted count, rejected count, model names, config path/hash, and manifest fields. Do not print secret values.
5. Inspect accepted JSONL, rejected/audit JSONL, and manifest.
6. Iterate by changing config TOML/limits and rerunning previews.
7. When a run is selected, copy accepted JSONL, rejected/audit JSONL, manifest/source/config metadata into a private dataset repo under `../reasoning-pruning-datasets` and commit it.

Do not use `--upload-to-hf` unless the user explicitly approves a release/upload.

## Historical rejected alternatives

These approaches are not active data-generation paths. Keep references only to explain why they were rejected; do not resurrect them for normal dataset creation.

| Alternative | Result | Current status |
| --- | --- | --- |
| One-off standalone generation scripts | Validated early Gemma4 loading/decode details but bypassed pruning decisions, manifests, and config ownership. | Deleted/rejected. Do not recreate. |
| Hugging Face Serverless / Inference Providers | Provider/catalog routing did not serve the tested Gemma4 repos reliably. | Historical only. |
| Dedicated Hugging Face Inference Endpoint default runtime | `handler.py`/`requirements.txt` customization failed before useful inference because the stock runtime could not handle the needed Gemma4/Transformers stack. | Historical only; root endpoint artifacts are stale. |
| TGI | Tested paths did not support Gemma4/custom architecture. | Historical only unless future support is proven separately. |
| Custom Docker endpoint | Technically possible for permanent serving, but heavier than needed for batch dataset creation. | Not active. |
| Local GPU generation | Useful for dependency/class checks, but insufficient for real Gemma4 generation on the current local hardware. | Development aid only. |

## Implementation boundary

If the model interface needs to change, integrate it as config/backend support in `scripts/llm_client.py` and continue to run `scripts/create_pruning_dataset.py --config ...`. External systems such as HF Jobs provide compute; they must not become separate generation pipelines.
