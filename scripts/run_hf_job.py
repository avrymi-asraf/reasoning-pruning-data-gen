#!/usr/bin/env python3
"""Transparent Hugging Face Job launcher for config-driven data creation.

This operational script launches the normal repository CLI in Hugging Face Jobs;
it does not implement generation, pruning, or a model-specific side pipeline.
The in-job flow clones this repo, runs `scripts/create_pruning_dataset.py` with a
TOML config, and can optionally copy ephemeral job outputs to a scratch dataset
repo for inspection. It is intended for local R&D use from the workspace root via
`uv run python scripts/run_hf_job.py`, with dry-run preview as the default.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python <3.11 compatibility
    import tomli as tomllib  # type: ignore


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = "config/bbh-logical-deduction-gemma4-hf-preview.toml"
DEFAULT_REPO_URL = "https://github.com/avrymi-asraf/reasoning-pruning-data-gen.git"
DEFAULT_IMAGE = "ghcr.io/astral-sh/uv:python3.11-bookworm"
DEFAULT_FLAVOR = "a10g-large"
DEFAULT_TIMEOUT = "7200"
DEFAULT_ARTIFACT_REPO_ID = "avreymi/reasoning-pruning-job-artifacts"
DEFAULT_ARTIFACT_PREFIX_TEMPLATE = "job-artifacts/{label}/outputs/datasets"
IN_JOB_HF_CLI = ["uvx", "--from", "huggingface_hub", "hf"]
SECRET_NAMES = ("HF_TOKEN", "GEMINI_API_KEY")
SAFE_LABEL_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def load_env_file() -> None:
    """Load .env if python-dotenv is installed, without printing values."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(PROJECT_ROOT / ".env", override=False)


def shell_join(parts: list[str]) -> str:
    return shlex.join(parts)


def is_executable_file(path: str | None) -> bool:
    """Return whether a resolved executable path is still runnable now."""
    return bool(path and Path(path).is_file() and os.access(path, os.X_OK))


def detect_hf_cli_command(mode: str = "auto") -> list[str]:
    """Return the local command prefix used to invoke the Hugging Face CLI."""
    uvx_path = shutil.which("uvx")
    hf_path = shutil.which("hf")

    if mode in {"auto", "uvx"} and is_executable_file(uvx_path):
        return [uvx_path or "uvx", "--from", "huggingface_hub", "hf"]
    if mode in {"auto", "hf"} and is_executable_file(hf_path):
        return [hf_path or "hf"]

    if mode == "uvx":
        raise SystemExit("uvx executable not found. Install uv/uvx or use --hf-cli auto/hf.")
    if mode == "hf":
        raise SystemExit("hf executable not found or not executable. Install huggingface_hub CLI or use --hf-cli auto/uvx.")
    raise SystemExit(
        "Hugging Face CLI launcher not found. Install uv/uvx so this launcher can run "
        "`uvx --from huggingface_hub hf`, install an executable `hf` command, or run the printed "
        "HF Jobs command from an environment that has one of those tools available."
    )


def sanitize_label(label: str) -> str:
    safe = SAFE_LABEL_RE.sub("-", label).strip(".-_")
    return safe or "hf-job"


def manifest_path_for(output_path: str | Path) -> str:
    path = Path(output_path)
    if path.suffix:
        return path.with_suffix(f"{path.suffix}.manifest.json").as_posix()
    return path.with_name(f"{path.name}.manifest.json").as_posix()


def read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as fh:
        return tomllib.load(fh)


def resolve_config_path(config: str) -> Path:
    path = Path(config)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if not path.exists():
        raise SystemExit(f"Config file not found: {path}")
    return path


def config_argument_for_job(config_path: Path) -> str:
    try:
        return config_path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise SystemExit("--config must point inside this repository so the cloned job can read it") from exc


def expected_artifact_paths(config_path: Path) -> list[str]:
    config = read_toml(config_path)
    output = config.get("output", {}) if isinstance(config.get("output", {}), dict) else {}
    accepted = output.get("accepted_path") or "outputs/datasets/run.jsonl"
    if not isinstance(accepted, str):
        raise SystemExit("output.accepted_path must be a string when artifact persistence is enabled")

    paths = [accepted]
    rejected = output.get("rejected_path")
    if isinstance(rejected, str) and rejected:
        paths.append(rejected)
    paths.append(manifest_path_for(accepted))
    return paths


def canonical_data_command(config_for_job: str) -> list[str]:
    return [
        "uv",
        "run",
        "--extra",
        "hf",
        "--extra",
        "gemma4",
        "python",
        "scripts/create_pruning_dataset.py",
        "--config",
        config_for_job,
    ]


def build_in_job_script(args: argparse.Namespace, config_path: Path) -> str:
    config_for_job = config_argument_for_job(config_path)
    repo_dir = Path(args.repo_url.rstrip("/")).stem.removesuffix(".git") or "reasoning-pruning-data-gen"
    lines = [
        "set -euo pipefail",
        "echo 'Cloning reasoning-pruning-data-gen for the normal config-driven pipeline.'",
        shell_join(["git", "clone", "--depth", "1", args.repo_url]),
        shell_join(["cd", repo_dir]),
    ]
    if args.ref:
        lines += [
            "echo 'Checking out requested git ref.'",
            shell_join(["git", "fetch", "--depth", "1", "origin", args.ref]),
            shell_join(["git", "checkout", "FETCH_HEAD"]),
        ]

    lines += [
        "echo 'Running canonical data generation command.'",
        shell_join(canonical_data_command(config_for_job)),
    ]

    if args.persist_artifacts:
        label = sanitize_label(args.artifact_label or Path(config_for_job).stem)
        prefix = args.artifact_prefix or DEFAULT_ARTIFACT_PREFIX_TEMPLATE.format(label=label)
        lines += [
            "",
            "echo 'Persisting scratch artifacts for retrieval; this is NOT dataset release.'",
            "echo 'Dataset release still requires separate review and the explicit --upload-to-hf gate.'",
        ]
        for local_path in expected_artifact_paths(config_path):
            remote_path = f"{prefix}/{Path(local_path).name}"
            lines.append(
                shell_join([
                    *IN_JOB_HF_CLI,
                    "upload",
                    args.artifact_repo,
                    local_path,
                    remote_path,
                    "--repo-type",
                    "dataset",
                    "--private",
                ])
            )
    return "\n".join(lines)


def build_hf_jobs_command(
    args: argparse.Namespace,
    in_job_script: str,
    hf_cli_command: list[str] | None = None,
) -> list[str]:
    cmd = [
        *(hf_cli_command or ["hf"]),
        "jobs",
        "run",
        "--flavor",
        args.flavor,
        "--timeout",
        args.timeout,
    ]
    for name in SECRET_NAMES:
        cmd += ["--secrets", name]
    cmd += [args.image, "bash", "-c", in_job_script]
    return cmd


def secret_presence() -> dict[str, bool]:
    return {name: bool(os.environ.get(name)) for name in SECRET_NAMES}


def require_secrets_present() -> None:
    missing = [name for name, present in secret_presence().items() if not present]
    if missing:
        raise SystemExit(f"Missing required environment variables for launch: {', '.join(missing)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preview or launch a Hugging Face Job that runs the normal config-driven data pipeline.",
    )
    parser.add_argument("--config", default=DEFAULT_CONFIG, help=f"Config TOML to run in the cloned repo (default: {DEFAULT_CONFIG})")
    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL, help="Git repo URL cloned inside the HF Job")
    parser.add_argument("--ref", default="", help="Optional git branch, tag, or commit to fetch and check out after clone")
    parser.add_argument("--image", default=DEFAULT_IMAGE, help="HF Jobs Docker image")
    parser.add_argument("--flavor", default=DEFAULT_FLAVOR, help="HF Jobs hardware flavor")
    parser.add_argument("--timeout", default=DEFAULT_TIMEOUT, help="HF Jobs timeout in seconds")
    parser.add_argument("--persist-artifacts", action="store_true", help="Append hf upload commands for accepted/rejected/manifest scratch retrieval")
    parser.add_argument("--artifact-repo", default=DEFAULT_ARTIFACT_REPO_ID, help="Private scratch dataset repo for persisted job artifacts")
    parser.add_argument("--artifact-prefix", default="", help="Remote prefix for scratch artifacts; default is job-artifacts/<label>/outputs/datasets")
    parser.add_argument("--artifact-label", default="", help="Label used in the default scratch artifact prefix")
    parser.add_argument("--hf-cli", choices=("auto", "uvx", "hf"), default="auto", help="Local HF CLI launcher to use; auto prefers uvx for a fresh huggingface_hub CLI")
    parser.add_argument("--launch", action="store_true", help="Actually launch the paid HF Job; without this flag the script only previews")
    return parser


def print_preview(in_job_script: str, hf_command: list[str], env_status: dict[str, bool], *, launch: bool) -> None:
    mode = "LAUNCH" if launch else "DRY RUN (no paid job launched)"
    print(f"# Mode: {mode}")
    print("# Secret presence (values are never printed):")
    for name, present in env_status.items():
        print(f"#   {name}: {'present' if present else 'missing'}")
    print("\n# In-job bash script passed to `bash -c`:")
    print(in_job_script)
    print("\n# Local HF CLI executable argv:")
    print(shell_join(hf_command))
    if not launch:
        print("\n# Add --launch to execute this paid HF Job.")


def main(argv: list[str] | None = None) -> int:
    load_env_file()
    args = build_parser().parse_args(argv)
    config_path = resolve_config_path(args.config)
    hf_cli_command = detect_hf_cli_command(args.hf_cli)
    in_job_script = build_in_job_script(args, config_path)
    hf_command = build_hf_jobs_command(args, in_job_script, hf_cli_command)
    print_preview(in_job_script, hf_command, secret_presence(), launch=args.launch)

    if not args.launch:
        return 0

    require_secrets_present()
    print("\nLaunching HF Job now...", file=sys.stderr)
    completed = subprocess.run(hf_command, cwd=PROJECT_ROOT, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
