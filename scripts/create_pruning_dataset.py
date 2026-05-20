#!/usr/bin/env python3
"""Config-driven reasoning-pruning runner for reasoning-pruning data creation.

This wrapper loads `.env` without printing values, parses the TOML config,
loads real seed/Hugging Face tasks, calls the pruning flow, and writes accepted
training JSONL plus optional rejected/audit JSONL. Hugging Face upload is a
separate release decision made with `--upload-to-hf`, never a default side effect.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pruning_flow import decision_reference, load_pruning_config, load_tasks, run_pipeline  # noqa: E402
from storage import upload_jsonl_to_hf, write_jsonl  # noqa: E402


def load_env_file() -> None:
    """Load local environment variables without printing secret values."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create sentence-pruning JSONL data with real LiteLLM calls.")
    parser.add_argument("--config", default="config/default.toml", help="Path to TOML config. Defaults to config/default.toml.")
    parser.add_argument("--output", help="Safe override for output.accepted_path.")
    parser.add_argument("--limit", type=int, help="Safe override for source.limit.")
    parser.add_argument("--upload-to-hf", action="store_true", help="Release the accepted JSONL to the configured Hugging Face dataset repo.")
    return parser


def apply_overrides(config, args: argparse.Namespace):
    source = config.source
    output = config.output
    if args.limit is not None:
        source = replace(source, limit=args.limit)
    if args.output:
        output = replace(output, accepted_path=args.output)
    return replace(config, source=source, output=output)


def manifest_path_for(output_path: str | Path) -> Path:
    path = Path(output_path)
    return path.with_suffix(f"{path.suffix}.manifest.json") if path.suffix else path.with_name(f"{path.name}.manifest.json")


def config_sha256(config_path: str | Path) -> str | None:
    path = Path(config_path)
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def llm_manifest_metadata(llm_config) -> dict[str, Any]:
    """Return reproducibility metadata for an LLM config without persisting endpoint secrets."""
    return {
        "provider": llm_config.provider,
        "model": llm_config.model,
        "temperature": llm_config.temperature,
        "max_tokens": llm_config.max_tokens,
        "base_url_configured": bool(llm_config.base_url),
    }


def build_manifest(config, *, accepted_count: int, rejected_count: int, upload_requested: bool, uploaded_url: str | None) -> dict[str, Any]:
    return {
        "manifest_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "run_name": config.run_name,
        "format_version": config.format_version,
        "accepted_row_schema": {
            "name": "compact_pruning_transition",
            "keys": ["id", "question", "input_x", "target_y", "depth", "decision"],
            "decision_reference": "Rows store config path plus a deterministic sha256 revision of the decision-related config; full reproducibility metadata lives in this manifest.",
        },
        "config_path": config.path,
        "config_sha256": config_sha256(config.path),
        "source": asdict(config.source),
        "models": {
            "generation": llm_manifest_metadata(config.generation),
            "decision": llm_manifest_metadata(config.decision),
        },
        "iteration": asdict(config.iteration),
        "quality": asdict(config.quality),
        "prompts": asdict(config.prompts),
        "decision_reference": decision_reference(config),
        "output": {
            "accepted_path": config.output.accepted_path,
            "rejected_path": config.output.rejected_path,
            "manifest_path": str(manifest_path_for(config.output.accepted_path)),
            "hf_upload_repo": config.output.hf_upload_repo,
            "hf_upload_path": config.output.hf_upload_path or Path(config.output.accepted_path).name,
            "hf_private": config.output.hf_private,
        },
        "counts": {
            "accepted": accepted_count,
            "rejected": rejected_count,
        },
        "hf_release": {
            "upload_requested": upload_requested,
            "uploaded": uploaded_url is not None,
            "url": uploaded_url,
        },
    }


def write_manifest(manifest: dict[str, Any], output_path: str | Path) -> Path:
    path = manifest_path_for(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def run_from_args(args: argparse.Namespace) -> tuple[int, int, str | None, str, Path]:
    config = apply_overrides(load_pruning_config(args.config), args)

    if args.upload_to_hf and not config.output.hf_upload_repo:
        raise ValueError("--upload-to-hf requires output.hf_upload_repo in the config")

    tasks = load_tasks(config.source)
    records, rejected = run_pipeline(tasks, config)

    written = write_jsonl(records, config.output.accepted_path)
    if config.output.rejected_path:
        write_jsonl(rejected, config.output.rejected_path)

    uploaded_url = None
    if args.upload_to_hf:
        uploaded_url = upload_jsonl_to_hf(
            config.output.accepted_path,
            config.output.hf_upload_repo,
            config.output.hf_upload_path,
            private=config.output.hf_private,
        )

    manifest_path = write_manifest(
        build_manifest(config, accepted_count=written, rejected_count=len(rejected), upload_requested=args.upload_to_hf, uploaded_url=uploaded_url),
        config.output.accepted_path,
    )
    return written, len(rejected), uploaded_url, config.output.accepted_path, manifest_path


def main(argv: list[str] | None = None) -> int:
    load_env_file()
    args = build_parser().parse_args(argv)
    try:
        written, rejected, uploaded_url, output_path, manifest_path = run_from_args(args)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {written} accepted training examples to {output_path}; rejected {rejected}.", file=sys.stderr)
    print(f"Wrote run manifest to {manifest_path}.", file=sys.stderr)
    if uploaded_url:
        print(f"Uploaded JSONL to {uploaded_url}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
