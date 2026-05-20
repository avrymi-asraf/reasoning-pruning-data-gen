---
name: huggingface-datasets
description: Guides Hugging Face dataset loading and optional gated Hub releases for the reasoning-pruning Data repo. Use when discovering external reasoning datasets, configuring HF sources, testing one HF dataset, or releasing inspected JSONL with --upload-to-hf.
---

<huggingface-datasets>
Use this skill when replacing the built-in seed tasks with an external Hugging Face dataset or when releasing an inspected local pruning-transition JSONL file to a Hugging Face dataset repo. HF has two separate roles here: input source (`source = "hf"`) and optional cloud release target (`--upload-to-hf`). Local dataset creation is always the default; upload happens only after an explicit release decision. Generation and pruning still use the required live LiteLLM client configured in `config/default.toml`.
</huggingface-datasets>

<loading-workflow>
1. Use the optional extra: `uv run --extra hf ...`.
2. Identify the dataset name, optional config, split, and text field that contains the task prompt, then put those values in `[source]` in `config/default.toml` or a copied config.
3. Run the SVAMP baseline (or another dataset config) with credentials loaded from environment or `.env` and no upload flag:
   `uv run --extra hf python scripts/create_pruning_dataset.py --config config/svamp.toml`
4. Inspect accepted counts plus `input_x`, `target_y`, removed span, and task metadata quality before scaling up.
</loading-workflow>

<upload-workflow>
1. Local JSONL output remains required. The runner also writes a local `*.manifest.json` beside the accepted JSONL.
2. Use the optional extra so `huggingface_hub` is available: `uv run --extra hf ...`.
3. Authenticate with `HF_TOKEN` or `huggingface-cli login`; never print token values.
4. Upload only after a release decision. Configure `output.hf_upload_repo`; use private repos for early data, and set a versioned path such as `output.hf_upload_path = "data/v0.1.0/train.jsonl"`.
5. Run with the explicit gate after confirming the local sample and path are correct: `uv run --extra hf python scripts/create_pruning_dataset.py --config config/default.toml --upload-to-hf`.
6. If `--upload-to-hf` is omitted, no upload happens even when a repo is configured. If the flag is present without a repo id, the run fails clearly before generation/upload work. If the Hub path is empty, the local JSONL basename is used.
7. Copy or upload the local manifest with the release (for example `data/v0.1.0/manifest.json`) because the runner currently uploads only the accepted JSONL automatically.
</upload-workflow>

<selection-guidance>
Prefer reasoning-heavy prompts with clear final answers: arithmetic, word problems, symbolic logic, or multi-step QA. Avoid datasets whose text field mixes answer labels into the prompt unless that is intentional and documented in `task_metadata`.
</selection-guidance>

<common-mistakes>
- Do not make `datasets` a required dependency for unit tests.
- Put Hugging Face source settings in config, and use live LiteLLM calls for generation and pruning decisions.
- Do not run large remote loads before checking a small `--limit` sample.
- Do not treat HF source loading as approval to upload; input and release are separate decisions.
- Do not save low-quality prompts simply because the pipeline accepted them; dataset choice still needs review.
- Do not push to Hugging Face without `--upload-to-hf`, an explicit repo id, a private/versioned target for early releases, and user approval.
</common-mistakes>
