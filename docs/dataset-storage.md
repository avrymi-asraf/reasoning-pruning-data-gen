# Dataset Storage and Versioning Recommendation

## Recommendation

Use private Hugging Face Hub dataset repositories as the canonical stores for selected reasoning-pruning datasets. Keep local checkouts under `../reasoning-pruning-datasets`; private model/checkpoint repos belong under `../reasoning-pruning-models`.

`outputs/datasets/` is temporary inspection space for HF Jobs and local runs. It is not the durable dataset store.

## Safe workflow

1. Preview the HF Jobs command without launching paid compute:

```bash
uv run python scripts/run_hf_job.py
```

2. Run a small HF Jobs preview with the normal config runner. The launcher runs this command inside the job:

```bash
uv run --extra hf --extra gemma4 python scripts/create_pruning_dataset.py --config config/bbh-logical-deduction-gemma4-hf-preview.toml
```

```bash
uv run python scripts/run_hf_job.py --launch
```

3. Prefer persisting scratch artifacts during preview jobs so files can be retrieved after the ephemeral job filesystem is gone:

```bash
uv run python scripts/run_hf_job.py \
  --persist-artifacts \
  --artifact-label bbh-logical-deduction-preview-001 \
  --launch
```

4. Inspect sanitized summaries plus the accepted JSONL, rejected/audit JSONL, and `*.manifest.json` after syncing/downloading persisted artifacts.
5. Iterate with small TOML limits/config changes until the preview is acceptable.
6. Scale the HF Job only after the preview loop is clean.
7. Select a dataset version manually.
8. Copy accepted JSONL, rejected/audit JSONL, manifest/source/config metadata, and review notes into a private dataset repo under `../reasoning-pruning-datasets`.
9. Commit the dataset repo and record the dataset revision for downstream training/evaluation.

Do not pass `--upload-to-hf` unless the user explicitly approves a release/upload. Configuring `output.hf_upload_repo` alone is not approval; without `--upload-to-hf`, runs stay local/job-local.

## HF Jobs scratch artifacts

HF Jobs does not provide a direct job filesystem download. During a job, `scripts/create_pruning_dataset.py` writes accepted, rejected/audit, and manifest files under the configured output paths, usually `outputs/datasets/`, but those files are lost unless the job script copies them somewhere persistent.

`scripts/run_hf_job.py` auto mode prefers executable `uvx --from huggingface_hub hf`, then falls back to a usable `hf` executable; dry-runs print the exact selected local launcher command. `scripts/run_hf_job.py --persist-artifacts --artifact-label <label>` appends visible in-job `uvx --from huggingface_hub hf upload ...` commands. These upload expected output files to a private scratch dataset repo under a label-specific prefix so the local UI/server sync, or equivalent `hf download` commands, can restore them into local `outputs/datasets/` for inspection. Do not use bare `hf upload` inside the HF Jobs image; job `6a115610b33ece92698c13af` proved that command can be missing and fail with exit 127 after pipeline outputs are written. Job `6a11634de3c0b51e1ca5db6a` proved the fixed `uvx --from huggingface_hub hf upload ...` artifact persistence/upload/download/sync path, with `accepted=0`, `rejected=30`, and no dataset release (`hf_release.upload_requested=false`).

Scratch artifact persistence is not dataset release. It is separate from `--upload-to-hf`, which remains the explicit approved release gate for selected datasets. The launcher passes HF Job secrets by name (`HF_TOKEN`, `GEMINI_API_KEY`) and prints only presence/missing status, never secret values.

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
