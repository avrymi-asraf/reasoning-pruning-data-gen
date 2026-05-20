"""Storage helpers for the sentence-pruning data runner.

Accepted local JSONL is always written first and is the default durable output.
Rejected/audit JSONL uses the same writer but is kept separate from training data.
Hugging Face upload is opt-in from the CLI and imports huggingface_hub only when used.
Auth comes from HF_TOKEN or local login state; token values are never printed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def write_jsonl(records: Iterable[dict[str, Any]], output_path: str | Path) -> int:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            count += 1
    return count


def upload_jsonl_to_hf(output_path: str | Path, repo_id: str, path_in_repo: str | None = None, *, private: bool = False) -> str:
    try:
        from huggingface_hub import create_repo, upload_file  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Hugging Face upload requires the optional extra: uv run --extra hf ...") from exc

    local_path = Path(output_path)
    if not local_path.exists():
        raise FileNotFoundError(f"Local JSONL output does not exist: {local_path}")

    target_path = path_in_repo or local_path.name
    create_repo(repo_id=repo_id, repo_type="dataset", private=private, exist_ok=True)
    upload_file(
        path_or_fileobj=str(local_path),
        path_in_repo=target_path,
        repo_id=repo_id,
        repo_type="dataset",
    )
    return f"https://huggingface.co/datasets/{repo_id}/blob/main/{target_path}"
