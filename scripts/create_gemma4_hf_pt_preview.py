#!/usr/bin/env python3
"""Preview PT dataset creation with the trained Gemma4 model hosted on Hugging Face.

This script is a thin data-gen entry point over the existing config loader,
pruning flow, JSONL writer, and manifest writer. It selects the BBH logical
deduction preview config, overrides only preview-safe knobs, and writes compact
PT rows plus audit files under outputs/datasets. It runs locally as an R&D
operator script while all generation calls go to Hugging Face-hosted inference.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import create_pruning_dataset  # noqa: E402
from llm_client import LLMConfig  # noqa: E402


DEFAULT_CONFIG = "config/bbh-logical-deduction-gemma4-hf-preview.toml"
MODEL_ID = "avreymi/reasoning-pruning-gemma-4-E2B-it-assistant"
DEFAULT_HF_PROVIDER = "hf-inference"
DEDICATED_TGI_MODEL = "huggingface/tgi"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create and print a small compact PT preview using the Hugging Face-hosted Gemma4 model."
    )
    parser.add_argument("--config", default=DEFAULT_CONFIG, help=f"Preview TOML config. Defaults to {DEFAULT_CONFIG}.")
    parser.add_argument("--limit", type=int, default=3, help="Number of source tasks to try. Defaults to 3.")
    parser.add_argument("--output", help="Override accepted JSONL output path under outputs/datasets for preview runs.")
    parser.add_argument(
        "--endpoint-url",
        default=None,
        help="Dedicated HF Inference Endpoint URL. Defaults to HF_GEMMA4_ENDPOINT_URL. When set, uses model=huggingface/tgi.",
    )
    parser.add_argument(
        "--hf-provider",
        default=None,
        help=(
            "HF serverless provider segment for LiteLLM when no endpoint URL is set. "
            "Defaults to HF_GEMMA4_PROVIDER or hf-inference. Serverless may not support this custom architecture."
        ),
    )
    return parser


def hosted_generation_config(args: argparse.Namespace, base: LLMConfig) -> LLMConfig:
    endpoint_url = args.endpoint_url or os.environ.get("HF_GEMMA4_ENDPOINT_URL")
    if endpoint_url:
        return replace(base, provider="huggingface", model=DEDICATED_TGI_MODEL, base_url=endpoint_url)

    provider = args.hf_provider or os.environ.get("HF_GEMMA4_PROVIDER") or DEFAULT_HF_PROVIDER
    return replace(base, provider="huggingface", model=f"huggingface/{provider}/{MODEL_ID}", base_url=None)


def preview_config_from_args(args: argparse.Namespace):
    config = create_pruning_dataset.load_pruning_config(args.config)
    source = replace(config.source, limit=args.limit)
    output = config.output
    if args.output:
        output = replace(output, accepted_path=args.output)
    generation = hosted_generation_config(args, config.generation)
    return replace(config, source=source, output=output, generation=generation)


def truncate(text: Any, limit: int = 220) -> str:
    compact = " ".join(str(text).split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def print_preview(records: list[dict[str, Any]], *, max_examples: int) -> None:
    print(f"Accepted compact preview examples: {len(records)}")
    for index, record in enumerate(records[:max_examples], start=1):
        print(f"\nExample {index}")
        print(f"id: {record.get('id', '')}")
        print(f"question: {truncate(record.get('question', ''))}")
        print(f"input_x: {truncate(record.get('input_x', ''))}")
        print(f"target_y: {truncate(record.get('target_y', ''))}")
        print(f"depth: {record.get('depth', '')}")
        print(f"decision: {json.dumps(record.get('decision', {}), sort_keys=True)}")


def run_preview(args: argparse.Namespace) -> tuple[int, int, str, Path]:
    config = preview_config_from_args(args)
    tasks = create_pruning_dataset.load_tasks(config.source)
    records, rejected = create_pruning_dataset.run_pipeline(tasks, config)

    written = create_pruning_dataset.write_jsonl(records, config.output.accepted_path)
    if config.output.rejected_path:
        create_pruning_dataset.write_jsonl(rejected, config.output.rejected_path)

    manifest_path = create_pruning_dataset.write_manifest(
        create_pruning_dataset.build_manifest(
            config,
            accepted_count=written,
            rejected_count=len(rejected),
            upload_requested=False,
            uploaded_url=None,
        ),
        config.output.accepted_path,
    )
    print_preview(records, max_examples=args.limit)
    return written, len(rejected), config.output.accepted_path, manifest_path


def main(argv: list[str] | None = None) -> int:
    create_pruning_dataset.load_env_file()
    args = build_parser().parse_args(argv)
    try:
        written, rejected, output_path, manifest_path = run_preview(args)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"\nWrote {written} accepted examples to {output_path}; rejected {rejected}.", file=sys.stderr)
    print(f"Wrote run manifest to {manifest_path}.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
