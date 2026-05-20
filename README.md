# Reasoning Pruning Data Gen

Config-driven runner for creating pruning-transition (PT) examples. The dataset trains the local transition `question + useful reasoning prefix -> next useful step after pruning`. Runs require real LiteLLM-backed model calls.

## Quickstart

```bash
uv run --extra dev python -m pytest
uv run python scripts/create_pruning_dataset.py --config config/default.toml
```

The script loads `.env` with `python-dotenv`. Credentials must be provided through environment variables or `.env`; do not print or commit secret values. A `GEMINI_API_KEY` in the environment or `.env` is enough for the default Gemini run.

## Project layout

- `config/default.toml` — source, output, model, iteration, quality, HF, and prompt settings.
- `config/bbh-logical-deduction.toml` — selected BBH logical deduction baseline source config.
- `scripts/create_pruning_dataset.py` — config-driven runner with `--config`, `--output`, `--limit`, and explicit `--upload-to-hf` release gate.
- `scripts/llm_client.py` — LiteLLM config and call wrapper.
- `scripts/pruning_flow.py` — task loading, splitting, first-span decisions, verification, iterative depth, record assembly.
- `scripts/storage.py` — accepted/rejected JSONL plus optional Hugging Face upload.

## Algorithm

For each question, the runner generates reasoning, segments it into ordered units, asks the decision model for the first safely removable contiguous span, validates that span, and saves one accepted record with:

- `input_x`: original/current context plus useful prefix before the span
- `target_y`: next kept unit after the skipped span
- `removed_span`, `full_generation_before_pruning`, `pruned_context_after_decision`
- observability metadata including units, removed ids, verification, models, source, and `format_version`

Then `pruned_context_after_decision` becomes the context for the next depth until stop/no-prune, validation failure, or `max_depth`.

## Config-driven local and baseline runs

```bash
# Local seed/dev run for prompt and pipeline iteration.
uv run python scripts/create_pruning_dataset.py --config config/default.toml

# SVAMP baseline run for Hugging Face dataset work.
uv run --extra hf python scripts/create_pruning_dataset.py --config config/svamp.toml
```

Edit source, output paths, provider/model/base URL/temperature, quality gates, and prompts in TOML config files. Accepted, rejected, and manifest files are written temporarily under `outputs/datasets/`; source samples are cached under `outputs/sources/`. Final generated datasets belong in private Hugging Face dataset repos checked out under `../reasoning-pruning-datasets`, while private model/checkpoint repos belong under `../reasoning-pruning-models`. Secrets stay in environment variables or `.env`; the runner loads `.env` without printing values.

## Optional Hugging Face source

Set `[source] source = "hf"` plus `hf_dataset`, `hf_config`, `hf_split`, and `hf_text_field` in a config file, then run:

```bash
uv run --extra hf python scripts/create_pruning_dataset.py --config config/svamp.toml
```

The selected baseline source for optimized data work is `config/bbh-logical-deduction.toml`, which uses `lukaemon/bbh`, config `logical_deduction_five_objects`, split `test`, prompt field `input`, and answer field `target`.

## Optional Hugging Face upload

Local generation is the default. Configuring `output.hf_upload_repo` or `output.hf_upload_path` only prepares release metadata; it does not upload by itself. Each run writes the local JSONL and a neighboring `*.jsonl.manifest.json` file.

To release to Hugging Face, pass the explicit upload gate. Upload uses Hugging Face auth from `HF_TOKEN` or local login state:

```bash
uv run --extra hf python scripts/create_pruning_dataset.py --config config/default.toml --upload-to-hf
```

Set `output.hf_upload_repo`, `output.hf_upload_path`, and `output.hf_private` explicitly in the config before uploading.
