## Project Goal

* **Description:** This repo creates training datasets for *sentence pruning* — teaching a model to skip redundant intermediate reasoning steps while preserving correctness. Hugging Face Jobs is the canonical execution environment, and each job runs the normal repo CLI/config path: `uv run --extra hf --extra gemma4 python scripts/create_pruning_dataset.py --config config/bbh-logical-deduction-gemma4-hf-preview.toml`. The pipeline loads reasoning tasks, generates chain-of-thought outputs with the configured generator, identifies the first safely removable contiguous reasoning span using a decision LLM, verifies quality, and saves high-quality `(input_x → target_y)` training examples as JSONL. Generated datasets are uploaded to Hugging Face Hub only with explicit approval and the `--upload-to-hf` gate.

* **Role in the multi-repo system:** This repository is the **data creation layer** for the reasoning-pruning project. It must not take over training or evaluation responsibilities: `reasoning-pruning-train` consumes the generated PT datasets and writes checkpoints/metadata, while `reasoning-pruning-experiments` coordinates experiment management, benchmark evaluation, and checkpoint-chain tracking. Cross-repo integration is file-based rather than Python imports between repos.

* **Core handoff chain:** Every serious dataset run should preserve enough metadata to reconstruct:

```text
generator checkpoint -> generated dataset version -> trained checkpoint
```

For this repo, that means recording the selected generator checkpoint/model, checkpoint commit or artifact reference when available, prompt/config versions, source dataset, decision configuration, output dataset version/path, and manifest details. Downstream repos should be able to consume the dataset and metadata without inspecting this repo's internal runtime state.

---

## Project Structure

* **Architecture:** Three loosely coupled layers:
  1. **Config layer** — TOML files in `config/` fully describe a run: source dataset, model choices, prompts, iteration limits, quality filters, and output paths.
  2. **Pipeline layer** — `scripts/pruning_flow.py` owns the core logic: task loading, LLM generation, unit segmentation, pruning decisions, span validation, quality verification, and record assembly. `scripts/llm_client.py` wraps LiteLLM; `scripts/storage.py` handles JSONL writing and optional Hub upload.
  3. **Entry points** — HF Jobs runs `scripts/create_pruning_dataset.py` with a TOML config. `server.py` and `pruning-playground.html` are optional local UI/config/inspection aids, not the canonical interface.

* **Repo boundaries:** Keep this repo focused on acquiring tasks, generating reasoning traces with the selected generator `G`, finding the first safe removable span with decision component `D`, and writing versioned dataset artifacts. Do not add training orchestration, checkpoint evaluation, or benchmark dashboards here unless the user explicitly changes the repo boundary; those belong in `reasoning-pruning-train` and `reasoning-pruning-experiments`.

* **Code Flow:**
  1. Load TOML config → `PruningConfig` dataclass (validates required prompt placeholders).
  2. Load tasks: `seed` (6 hardcoded math/logic tasks) or `hf` (Hugging Face `datasets` library).
  3. For each task, iterate up to `max_depth`:
     - Generate chain-of-thought reasoning via the *generation* LLM.
     - Split generation into ordered `Unit` objects (`u000`, `u001`, …) at sentence boundaries.
     - Ask the *decision* LLM (JSON-mode) for the first safely removable contiguous span.
     - Validate span: known IDs, contiguous, not all units, ≤ `max_removable_span_length`, has a next kept unit.
     - Verify quality: non-empty inputs, no obvious incoherence, optional final-answer preservation.
     - Build an accepted row with compact training fields (`input_x`, `target_y`) plus pruning/provenance fields; run/audit metadata belongs in the manifest and rejected JSONL artifacts.
     - Set `pruned_context_after_decision` as the new context for the next depth.
  4. Write accepted JSONL + rejected/audit JSONL + `*.manifest.json` locally.
   5. Inspect previews, then copy/version selected artifacts under `../reasoning-pruning-datasets`; optionally upload accepted JSONL to Hugging Face Hub only with explicit approval and `--upload-to-hf`.

---

## File Structure

```
/reasoning-pruning-data-gen
├── server.py                    # Optional local management UI server
├── pruning-playground.html      # Optional local config/inspection UI
├── pyproject.toml               # uv project: dependencies, optional extras (hf, dev)
├── config/
│   ├── default.toml             # Default config (seed source, Gemini models)
│   ├── gsm8k.toml               # GSM8K HF dataset config
│   ├── svamp.toml               # SVAMP HF dataset config
│   ├── strategyqa.toml          # StrategyQA HF dataset config
│   └── bbh-multistep-arithmetic.toml
├── scripts/
│   ├── create_pruning_dataset.py  # CLI entry point: args, config overrides, manifest write
│   ├── pruning_flow.py            # Core pipeline: tasks, generation, decisions, records
│   ├── llm_client.py              # LiteLLM wrapper + LLMConfig dataclass
│   └── storage.py                 # write_jsonl + upload_jsonl_to_hf
├── tests/
│   └── test_pruning_flow.py       # No-network unit tests (fake LLM call injection)
├── docs/
│   ├── dataset-storage.md       # HF Hub versioning, layout, upload workflow
│   └── R1.md                    # Canonical algorithm and record-shape note
├── experiments/                 # Folder-per-experiment research notebook and index
├── research/
│   ├── INDEX.md
│   ├── raw/                     # Raw research notes
│   └── wiki/                    # Reference material
└── outputs/                     # Generated JSONL datasets (gitignored)
    └── datasets/
        └── *.jsonl              # Accepted training examples
        └── *.rejected.jsonl     # Audit examples
        └── *.manifest.json      # Run manifest
```

* `config/`: TOML config files — one per dataset/experiment. Fully describes source, models, prompts, iteration, quality, and output paths.
* `scripts/`: All executable logic. The pipeline is importable for testing; the CLI runner is the public data-creation entry point and is run inside HF Jobs for real Gemma4 dataset creation.
* `tests/`: No-network pytest suite. LLM calls are injected via `call_fn` parameter; no mocking of internal logic.
* `docs/`: Project-specific documents: algorithm note and storage strategy.
* `experiments/`: Serious research notebook. Experiments are pre-declared folders named like `NNN-short-title/`, each with a `README.md` explaining the investigation and files. Read `experiments/README.md` before proposing a new approach, but do not create/update experiment folders or index records unless the user explicitly commands or approves the experiment.
* `research/`: Background research notes and references.
* `outputs/`: Job/local generated datasets (gitignored). Inspect only; selected durable datasets must be copied/versioned under `../reasoning-pruning-datasets`.

---

## Cross-Repo Artifact Stores

Nearby cooperating artifact stores are part of the expected workflow:

```text
reasoning-pruning-datasets/      # local clone(s) of private Hugging Face dataset repos
reasoning-pruning-models/        # local clone(s) of private Hugging Face model repos
```

Use `outputs/` for HF Jobs/local run products, inspection, rejected/audit files, and temporary/generated files. When a dataset is selected as a durable training input, create or update the appropriate private Hugging Face dataset repo locally under `../reasoning-pruning-datasets` and version it by commit/revision. Generator checkpoints should be referenced from `../reasoning-pruning-models` or a clear remote/model artifact reference; do not treat unversioned job/local outputs as the final long-term dataset store.

The data repo's artifact metadata should support file-based handoffs:

* `reasoning-pruning-data-gen` → writes versioned PT JSONL plus manifest/source metadata.
* `reasoning-pruning-train` → reads dataset artifacts and writes checkpoints plus `run_metadata.json`.
* `reasoning-pruning-experiments` → reads dataset/checkpoint/training metadata and records evaluation results and checkpoint chains.

---

## Building and Running

**Prerequisites:**
* Hugging Face Jobs with image `ghcr.io/astral-sh/uv:python3.11-bookworm` and flavor `a10g-large` for real Gemma4 data creation
* [uv](https://docs.astral.sh/uv/) package manager
* Encrypted HF Job secrets `HF_TOKEN` and `GEMINI_API_KEY`
* Python 3.10+ locally only for tests/config smoke runs

**Build Steps:**
1. Install dependencies: `uv sync`
2. For Hugging Face dataset source or Hub upload: `uv sync --extra hf`
3. For running tests: `uv sync --extra dev`

**Canonical data creation:**

```bash
uv run --extra hf --extra gemma4 python scripts/create_pruning_dataset.py --config config/bbh-logical-deduction-gemma4-hf-preview.toml
```

Run that command inside an HF Job that clones/downloads `https://github.com/avrymi-asraf/reasoning-pruning-data-gen.git`, uses image `ghcr.io/astral-sh/uv:python3.11-bookworm`, flavor `a10g-large`, encrypted `HF_TOKEN` and `GEMINI_API_KEY`, and prints sanitized manifest/accepted/rejected summaries. Earlier successful data-quality preview: job `6a106a46b33ece92698c06f8`, accepted `3`, rejected `0`, generation model `avreymi/reasoning-pruning-gemma-4-E2B-it`, decision model `gemini/gemini-2.5-flash-lite`. Artifact persistence proof after the `uvx --from huggingface_hub hf upload ...` fix: job `6a11634de3c0b51e1ca5db6a`, accepted `0`, rejected `30`, `hf_release.upload_requested=false`; this proves scratch upload/download/sync, not data quality.

Local-only development aids:
```bash
uv run python scripts/create_pruning_dataset.py --config config/default.toml
uv run server.py
```

Tests:
```bash
uv run --extra dev python -m pytest
```

---

## Status

Active research and development with one clear data-creation path: HF Jobs runs the config-driven CLI. The core dataset pipeline is working: config loading, seed and HF task loading, configured generation, LiteLLM decision calls, first removable-span decisions, span validation, quality verification, JSONL output with manifests, and explicit-gate Hub upload. Current work is to iterate through small HF Jobs previews, inspect accepted/rejected/manifest summaries, preserve generator/dataset metadata for downstream training and evaluation, and copy selected datasets into private versioned repos under `../reasoning-pruning-datasets`.

---

## Code Writing Rules 📝
Do not create new documentation files (unless explicitly requested). Only update documentation via the `README` if necessary.

### File Header (Mandatory)
In the header of every code file, you **must** describe how that file relates to the **overall project architecture** and **code flow**.

Each code file **must** include a short description (no more than 4–5 sentences) that explains the following:
- Its role in the **big picture** (as defined in the **Project Structure** section).
- Its connection to the main **code flow** of the project.
- The intended **execution environment** (where this code will run, as defined in the **Project Goal** section).
Remember to update important documents, remember to update your memory.
Shared documents are super super important, they allow you to learn from mistakes and move forward. Remember to use them and update them.

The skills folder has tutorials on how to handle important tools and things. Remember to read - and if you need to update them, update them. Integrate the new information with the existing information, don't reinvent the wheel.
The docs folder has important documents that are only relevant to this project. Plans, etc. If there is a document that relates to your task, use it - and update it. Again - integrate the information, don't reinvent the wheel.
Remember to update your memory. This is important
We are in research and development, not a running product. We are not interested in backward compatibility. It is much more important that the code is clean, clear and readable.
