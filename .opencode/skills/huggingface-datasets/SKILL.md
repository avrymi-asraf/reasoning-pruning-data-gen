---
name: huggingface-datasets
description: Guides Hugging Face dataset loading, preview inspection, and gated Hub releases for the reasoning-pruning Data repo. Use when discovering HF sources, configuring dataset TOML, inspecting HF Jobs outputs, or releasing selected JSONL with explicit approval.
---

# Hugging Face Datasets for Reasoning-Pruning

Use this skill for selecting Hugging Face dataset sources, checking Dataset Viewer metadata, and preserving selected generated datasets. The active data-creation path is HF Jobs running the normal config runner; dataset work should support that path rather than creating separate scripts.

## Canonical generation context

HF Jobs should clone/download this repo and run:

```bash
uv run --extra hf --extra gemma4 python scripts/create_pruning_dataset.py --config config/bbh-logical-deduction-gemma4-hf-preview.toml
```

Use image `ghcr.io/astral-sh/uv:python3.11-bookworm`, flavor `a10g-large`, encrypted `HF_TOKEN` and `GEMINI_API_KEY`, and sanitized accepted/rejected/manifest summaries. Recent successful preview: job `6a106a46b33ece92698c06f8`, accepted `3`, rejected `0`.

## Source dataset discovery

Use the Dataset Viewer API for read-only exploration:

- Base URL: `https://datasets-server.huggingface.co`
- List subsets/splits: `/splits?dataset=<namespace/repo>`
- Preview rows: `/first-rows?dataset=<namespace/repo>&config=<config>&split=<split>`
- Paginate rows: `/rows?dataset=<namespace/repo>&config=<config>&split=<split>&offset=<int>&length=<int>`
- Search text: `/search?dataset=<namespace/repo>&config=<config>&split=<split>&query=<text>`
- List parquet shards: `/parquet?dataset=<namespace/repo>`
- Gated/private datasets require `Authorization: Bearer <HF_TOKEN>`; never print the token.

Map the selected source into TOML: `hf_dataset`, `hf_config`, `hf_split`, `hf_text_field`, optional `answer_fields`, and small preview `limit`. Do not hard-code dataset transforms in a new script unless the pipeline itself needs a reusable feature.

## Preview and inspection loop

1. Configure a small source limit in TOML.
2. Run the canonical command in an HF Job.
3. Inspect accepted JSONL, rejected/audit JSONL, and the manifest.
4. Adjust config and rerun previews before scaling.

`outputs/datasets/` is temporary inspection output only.

## Durable dataset storage

When a run is selected, copy/version it under `../reasoning-pruning-datasets` as a private HF dataset repo. Preserve accepted JSONL, rejected/audit JSONL, manifest/source/config metadata, and a commit/revision so downstream training can reference an immutable dataset version.

Use `--upload-to-hf` only after explicit approval. Configuring `output.hf_upload_repo` is not enough; the upload gate must be intentionally passed for a release.
