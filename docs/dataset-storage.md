# Dataset Storage and Versioning Recommendation

## Recommendation

Use private Hugging Face Hub dataset repositories as the canonical stores for generated reasoning-pruning datasets. Keep local checkouts of those dataset repos under `../reasoning-pruning-datasets`; private model/checkpoint repos belong under `../reasoning-pruning-models`.

Why this fits this repo:

- The output is already JSONL and the project has an explicit Hugging Face release gate: config names the repo/path, and `--upload-to-hf` performs the upload.
- Hugging Face dataset repos are Git-backed, support commit history, tags, branches/revisions, private repos, dataset cards, and programmatic upload.
- Training and evaluation repos can load exact revisions from the Hub, making experiments reproducible.

## Proposed layout

Create or check out private dataset repos under `../reasoning-pruning-datasets`, for example:

```text
<org-or-user>/reasoning-pruning-data-gen
```

Inside the repo, store stable releases by versioned paths:

```text
README.md
data/
  v0.1.0/
    train.jsonl
    validation.jsonl
    rejected.jsonl        # optional audit file, keep private if sensitive/noisy
    manifest.json
  v0.2.0/
    train.jsonl
    validation.jsonl
    rejected.jsonl
    manifest.json
```

For larger runs, prefer Parquet for published training splits, but keep JSONL locally and/or as an audit artifact because it is simple and matches the current pipeline. Treat `outputs/datasets/` as temporary generation space; copy reviewed accepted, rejected, and manifest files into the private dataset repo and commit them there.

## Versioning policy

Use semantic versions:

- `v0.x.y`: experimental/prerelease datasets.
- Increment minor (`v0.2.0`) when source mix, prompts, model choices, pruning algorithm, schema, or quality filters change.
- Increment patch (`v0.2.1`) for small fixes that do not change intended semantics.
- Tag stable Hub commits with the same version, e.g. `v0.2.0`.
- Record the exact Hub commit SHA/revision in training and evaluation configs.

`main` should point to the latest recommended stable dataset. Use branches or non-default paths for experiments.

## Required manifest per version

Every run writes a local manifest next to the accepted JSONL, for example `outputs/datasets/seed_dev.jsonl.manifest.json`. Each released version should include or copy that manifest as `manifest.json` with at least:

- dataset version and creation timestamp
- git commit of this Data repo, if available
- generator model, decision model, and verification settings
- source datasets/configs/splits and limits
- prompts/config file hash or copied config path
- schema/format version
- counts: accepted, rejected, train, validation
- quality notes/manual review status
- Hugging Face commit SHA after upload

Current implementation writes the local run manifest with counts, source settings, model settings, config path/hash, format version, timestamp, and whether upload happened. It does not upload the manifest automatically yet, so copy/release it with the JSONL when publishing a version.

## Safe upload workflow

1. Generate locally first under `outputs/datasets/`.
2. Inspect a small sample manually: `input_x`, `target_y`, removed span, task metadata, and rejected audit examples.
3. Copy reviewed artifacts into the corresponding private dataset repo under `../reasoning-pruning-datasets` and commit them there.
4. Upload only after deciding this run is a release and setting an explicit repo in config:
    - `output.hf_upload_repo = "<org-or-user>/reasoning-pruning-data-gen"`
    - `output.hf_upload_path = "data/v0.1.0/train.jsonl"`
    - `output.hf_private = true` for early releases.
5. Run with the HF optional extra, token from environment, and the explicit upload gate:

```bash
uv run --extra hf python scripts/create_pruning_dataset.py --config config/default.toml --upload-to-hf
```

Without `--upload-to-hf`, the run remains local-only even when `output.hf_upload_repo` is configured. If `--upload-to-hf` is passed without `output.hf_upload_repo`, the script fails before generation/upload work. If `output.hf_upload_path` is empty, the local JSONL basename is used as the Hub path.

6. Add/update the dataset card (`README.md`) with schema, sources, intended use, limitations, and version table.
7. Copy the local manifest into the version directory or upload it separately as `data/<version>/manifest.json`.
8. Tag the uploaded commit on Hugging Face as the release version.

## Alternatives considered

- S3/GCS/Azure Blob: good for cheap raw archival, but weaker discoverability and less convenient for training/evaluation consumers unless additional registry tooling is added.
- DVC: strong Git-style data tracking with arbitrary cloud remotes, useful later if local pipelines become large and multi-stage. More operational overhead now.
- lakeFS: powerful for very large data lakes and zero-copy branches, likely overkill for early reasoning-pruning JSONL/Parquet releases.

Decision: start with Hugging Face Hub. Add S3/DVC later only if dataset size, privacy, or workflow complexity outgrows Hub-only storage.
