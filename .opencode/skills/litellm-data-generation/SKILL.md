---
name: litellm-data-generation
description: Guides required LiteLLM generation and pruning decisions for the reasoning-pruning Data repo. Use when running HF Jobs previews, Gemini Flash Lite decisions, Gemma4 config-driven generation, or debugging LiteLLM JSON decisions.
---

<litellm-data-generation>
Use this skill when the Data repo runner calls live models for reasoning-pruning data creation. The canonical workflow is Hugging Face Jobs running the normal config command; LiteLLM remains the decision-model interface and can also support hosted models when a real endpoint exists. Source, outputs, providers, models, temperatures, limits, quality gates, HF settings, and prompts live in TOML config files; do not create one-off generation scripts.
</litellm-data-generation>

<canonical-hf-jobs-workflow>
HF Jobs is the execution environment. Inside the job, clone/download `https://github.com/avrymi-asraf/reasoning-pruning-data-gen.git` and run only:

```bash
uv run --extra hf --extra gemma4 python scripts/create_pruning_dataset.py --config config/bbh-logical-deduction-gemma4-hf-preview.toml
```

Use image `ghcr.io/astral-sh/uv:python3.11-bookworm`, flavor `a10g-large`, encrypted `HF_TOKEN` and `GEMINI_API_KEY`, and sanitized logs. Recent successful preview: job `6a106a46b33ece92698c06f8`, accepted `3`, rejected `0`, generator `avreymi/reasoning-pruning-gemma-4-E2B-it`, decision model `gemini/gemini-2.5-flash-lite`.
</canonical-hf-jobs-workflow>

<quick-preview-loop>
1. Keep limits small in the preview TOML.
2. Run the canonical command in an HF Job.
3. Inspect accepted JSONL, rejected/audit JSONL, and manifest summaries.
4. Change TOML config/limits, rerun previews, and inspect again.
5. Scale only after accepted and rejected examples look right.

Local commands such as `uv run python scripts/create_pruning_dataset.py --config config/default.toml` are for development smoke checks, not the Gemma4 data-creation path.
</quick-preview-loop>

<decision-json-contract>
Pruning decisions must return strict JSON only: `{"status":"remove","remove_unit_ids":["u001"],"rationale":"..."}` or `{"status":"no_prune","remove_unit_ids":[],"rationale":"..."}` or `{"status":"stop","remove_unit_ids":[],"rationale":"..."}`. A `remove` decision must name the first safely removable contiguous span and leave a next kept unit for `target_y`. Malformed JSON, unknown ids, non-contiguous spans, empty/all spans, too-long spans, or no next target go to reject/audit output, not training data.
</decision-json-contract>

<artifact-policy>
`outputs/datasets/` is temporary job/local inspection output. Durable selected datasets must be copied/versioned under `../reasoning-pruning-datasets` as private HF dataset repos with accepted JSONL, rejected/audit JSONL, manifest/source/config metadata, and a commit. Use `--upload-to-hf` only with explicit approval.
</artifact-policy>

<common-mistakes>
- Do not print, paste, or commit `HF_TOKEN`, `GEMINI_API_KEY`, endpoint credentials, or secret-bearing URLs.
- Do not create standalone/one-off generation scripts; add provider/backend support to the normal runner if needed.
- Do not treat serverless providers, TGI, custom endpoints, or HF Inference Endpoints as active data-generation paths for this repo.
- Do not debug prompts when the real failure is malformed decision JSON or provider/model availability.
- Do not save rejected or malformed live examples as training data.
</common-mistakes>
