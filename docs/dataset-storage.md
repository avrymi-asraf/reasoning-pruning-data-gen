# Dataset Storage and Versioning Recommendation

## Recommendation

Use private Hugging Face Hub dataset repositories as the canonical stores for selected reasoning-pruning datasets. Keep local checkouts under `../reasoning-pruning-datasets`; private model/checkpoint repos belong under `../reasoning-pruning-models`.

`outputs/datasets/` is temporary inspection space for HF Jobs and local runs. It is not the durable dataset store.

## Safe workflow

1. Run a small HF Jobs preview with the normal config runner:

```bash
uv run --extra hf --extra gemma4 python scripts/create_pruning_dataset.py --config config/bbh-logical-deduction-gemma4-hf-preview.toml
```

2. Inspect sanitized summaries plus the accepted JSONL, rejected/audit JSONL, and `*.manifest.json`.
3. Iterate with small TOML limits/config changes until the preview is acceptable.
4. Scale the HF Job only after the preview loop is clean.
5. Select a dataset version manually.
6. Copy accepted JSONL, rejected/audit JSONL, manifest/source/config metadata, and review notes into a private dataset repo under `../reasoning-pruning-datasets`.
7. Commit the dataset repo and record the dataset revision for downstream training/evaluation.

Do not pass `--upload-to-hf` unless the user explicitly approves a release/upload. Configuring `output.hf_upload_repo` alone is not approval; without `--upload-to-hf`, runs stay local/job-local.

## Proposed durable layout

```text
README.md
data/
  v0.1.0/
    train.jsonl
    rejected.jsonl
    manifest.json
    source-config.toml
    review-notes.md
  v0.2.0/
    train.jsonl
    rejected.jsonl
    manifest.json
    source-config.toml
```

Use semantic versions for selected datasets: increment minor when sources, prompts, models, pruning logic, schema, or quality filters change; increment patch for small corrections. Tag stable Hub commits with the same version and record the exact Hub revision in training/evaluation configs.

## Required metadata

Every selected dataset version should preserve:

- accepted JSONL and rejected/audit JSONL
- run manifest with accepted/rejected counts
- source dataset/config/split/limit
- generator model and revision/commit when available
- decision model and decision config
- prompt/config version or copied config file
- data repo commit/hash when available
- manual inspection status or quality notes
- durable dataset repo commit/revision

This metadata preserves the handoff chain:

```text
generator checkpoint -> generated dataset version -> trained checkpoint
```

## Direct upload gate

Direct upload through the data runner is available only as an explicitly approved release action:

```bash
uv run --extra hf python scripts/create_pruning_dataset.py --config <config.toml> --upload-to-hf
```

Before using it, set `output.hf_upload_repo`, `output.hf_upload_path`, and `output.hf_private` in config. Prefer copy/version/commit under `../reasoning-pruning-datasets` for selected datasets so review and metadata are visible before release.
