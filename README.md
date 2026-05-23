# Reasoning Pruning Data Gen

Config-driven runner for creating pruning-transition (PT) examples. The canonical data-creation workflow is now **Hugging Face Jobs running the normal repo CLI/config path**: Jobs provide the paid execution environment, while `scripts/create_pruning_dataset.py` remains the only data-generation entry point.

## Canonical workflow: HF Jobs + normal config runner

Run the Gemma4 preview config inside a Hugging Face Job. The only data creation command inside the job is:

```bash
uv run --extra hf --extra gemma4 python scripts/create_pruning_dataset.py --config config/bbh-logical-deduction-gemma4-hf-preview.toml
```

Use this HF Jobs shape:

- Image: `ghcr.io/astral-sh/uv:python3.11-bookworm`
- Flavor: `a10g-large`
- Encrypted secrets: `HF_TOKEN` and `GEMINI_API_KEY`
- Source: clone/download `https://github.com/avrymi-asraf/reasoning-pruning-data-gen.git`
- Action: run the normal config command above
- Logs: print sanitized manifest, accepted, and rejected summaries only; never print secret values

Artifact-persistence proof after the HF Jobs upload fix: HF Job [`6a11634de3c0b51e1ca5db6a`](https://huggingface.co/jobs/avreymi/6a11634de3c0b51e1ca5db6a) completed successfully, and scratch artifact upload/download/sync worked with `accepted=0`, `rejected=30`, and `hf_release.upload_requested=false`. This proves artifact workflow only, not data quality. Earlier successful data-quality preview: HF Job `6a106a46b33ece92698c06f8` accepted `3`, rejected `0`, using generation model `avreymi/reasoning-pruning-gemma-4-E2B-it` and decision model `gemini/gemini-2.5-flash-lite`.

### Transparent HF Jobs launcher

`scripts/run_hf_job.py` is an operational launcher for the workflow above. It prints the exact in-job `bash -c` script and local HF CLI command, defaults to dry-run, and only launches paid compute when `--launch` is present. In auto mode it prefers executable `uvx --from huggingface_hub hf`, then falls back to a usable `hf` executable, and the printed command matches the selected launcher. It does not replace `scripts/create_pruning_dataset.py` and does not create a side generation pipeline.

Preview the command without launching:

```bash
uv run python scripts/run_hf_job.py
```

Launch the paid HF Job after reviewing the printed command:

```bash
uv run python scripts/run_hf_job.py --launch
```

Recommended preview launch when you need to retrieve accepted/rejected/manifest files later:

```bash
uv run python scripts/run_hf_job.py \
  --persist-artifacts \
  --artifact-label bbh-logical-deduction-preview-001 \
  --launch
```

HF Jobs job filesystems are ephemeral and there is no direct job filesystem download. The runner writes outputs inside the job under the TOML-configured paths, normally `outputs/datasets/`; those files become local only if you persist them during the job and then sync/download them. `--persist-artifacts` appends visible in-job `uvx --from huggingface_hub hf upload ...` commands that copy accepted JSONL, rejected/audit JSONL, and the manifest to a private scratch dataset repo for retrieval by the local UI/server sync or equivalent `hf download` commands. Do not use bare `hf upload` inside the job image; that caused job `6a115610b33ece92698c13af` to fail with exit 127 after pipeline outputs were written. This scratch persistence is for inspection only and is separate from dataset release: `--upload-to-hf` remains the explicit release gate and is not added by the launcher.

Secrets are passed to HF Jobs by name (`HF_TOKEN`, `GEMINI_API_KEY`). The launcher prints whether each secret is present, but never prints secret values.

## Quick preview loop

1. Edit the TOML config, especially source limits, output path, model settings, prompts, and quality gates.
2. Keep limits small for preview runs; `config/bbh-logical-deduction-gemma4-hf-preview.toml` is the current quick iteration config.
3. Dry-run `scripts/run_hf_job.py`, then launch a small HF Job; use `--persist-artifacts --artifact-label ...` if you need files back locally.
4. Inspect accepted JSONL, rejected/audit JSONL, and `*.manifest.json` summaries after persisting/syncing them.
5. Adjust the config and rerun previews until the accepted/rejected examples look right.
6. Scale only after the preview summaries are clean.

Do not create one-off generation scripts or alternate data paths. Do not use `--upload-to-hf` unless the user explicitly approves a release/upload action.

## Where results go

The runner writes accepted JSONL, rejected/audit JSONL, and a neighboring manifest under the configured output path, usually `outputs/datasets/`. Files in `outputs/datasets/` are quick inspection products only, whether produced in a job or locally.

Durable selected datasets must be copied/versioned under `../reasoning-pruning-datasets` as private Hugging Face dataset repos. A selected release should include accepted JSONL, rejected/audit JSONL, manifest/source/config metadata, manual inspection notes when useful, and a git commit/revision. Generator checkpoints should be referenced from `../reasoning-pruning-models` or a clear remote/model artifact reference.

## Project layout

- `config/*.toml` — source, output, model, iteration, quality, HF, and prompt settings.
- `config/bbh-logical-deduction-gemma4-hf-preview.toml` — current Gemma4 HF Jobs preview config.
- `scripts/create_pruning_dataset.py` — the single data-generation CLI with `--config`, `--output`, `--limit`, and explicit `--upload-to-hf` gate.
- `scripts/llm_client.py` — LiteLLM and configured generation backend calls.
- `scripts/pruning_flow.py` — task loading, splitting, first-span decisions, verification, iterative depth, record assembly.
- `scripts/storage.py` — accepted/rejected JSONL plus optional Hugging Face upload.
- `server.py` and `pruning-playground.html` — optional local UI/config/inspection aids, not the canonical interface.

## Algorithm

For each question, the runner generates reasoning, segments it into ordered units, asks the decision model for the first safely removable contiguous span, validates that span, and saves one compact accepted record with `id`, `question`, `input_x`, `target_y`, `depth`, and `decision`. The manifest and rejected/audit output preserve heavier provenance and quality details.

Then the pruned context becomes the context for the next depth until stop/no-prune, validation failure, or `max_depth`.

## Optional local development aids

Local runs are for tests, config editing, and cheap smoke checks. They are not the active data-creation path for Gemma4 hardware runs.

```bash
uv run --extra dev python -m pytest
uv run python scripts/create_pruning_dataset.py --config config/default.toml
uv run server.py
```

The script loads `.env` with `python-dotenv`, but credentials should remain in environment variables, `.env`, or HF Job secrets and must never be printed or committed.

## Optional Hugging Face upload gate

Configuring `output.hf_upload_repo` or `output.hf_upload_path` only prepares metadata. Uploads require explicit approval and the explicit gate:

```bash
uv run --extra hf python scripts/create_pruning_dataset.py --config <config.toml> --upload-to-hf
```

Prefer the safe workflow first: HF Jobs preview -> inspect -> select -> copy/version under `../reasoning-pruning-datasets` -> commit. Use direct upload only when a release has been approved.
