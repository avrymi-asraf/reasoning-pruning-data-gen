"""Tests for the transparent Hugging Face Job launcher.

The launcher is only an operational wrapper around the normal config-driven data
pipeline. These tests verify command construction and dry-run safety without
launching paid Jobs, uploading artifacts, or calling external services.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import scripts.run_hf_job as run_hf_job


def make_args(**overrides: object) -> argparse.Namespace:
    values = {
        "config": run_hf_job.DEFAULT_CONFIG,
        "repo_url": run_hf_job.DEFAULT_REPO_URL,
        "ref": "",
        "image": run_hf_job.DEFAULT_IMAGE,
        "flavor": run_hf_job.DEFAULT_FLAVOR,
        "timeout": run_hf_job.DEFAULT_TIMEOUT,
        "persist_artifacts": False,
        "artifact_repo": run_hf_job.DEFAULT_ARTIFACT_REPO_ID,
        "artifact_prefix": "",
        "artifact_label": "",
        "hf_cli": "auto",
        "launch": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def test_builds_bash_c_job_command_for_canonical_config() -> None:
    args = make_args()
    config_path = run_hf_job.PROJECT_ROOT / run_hf_job.DEFAULT_CONFIG
    script = run_hf_job.build_in_job_script(args, config_path)
    command = run_hf_job.build_hf_jobs_command(args, script)

    assert "uv run --extra hf --extra gemma4 python scripts/create_pruning_dataset.py --config config/bbh-logical-deduction-gemma4-hf-preview.toml" in script
    assert "--upload-to-hf" not in script
    assert command[:3] == ["hf", "jobs", "run"]
    assert command[-4:] == [run_hf_job.DEFAULT_IMAGE, "bash", "-c", script]
    assert command.count("--secrets") == 2
    assert "HF_TOKEN" in command
    assert "GEMINI_API_KEY" in command


def make_executable(path: Path) -> str:
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(0o755)
    return str(path)


def test_auto_prefers_uvx_hf_cli_launcher(monkeypatch, tmp_path) -> None:
    hf = make_executable(tmp_path / "hf")
    uvx = make_executable(tmp_path / "uvx")

    def fake_which(executable: str) -> str | None:
        return {"hf": hf, "uvx": uvx}.get(executable)

    monkeypatch.setattr(run_hf_job.shutil, "which", fake_which)

    assert run_hf_job.detect_hf_cli_command() == [uvx, "--from", "huggingface_hub", "hf"]


def test_detects_forced_hf_cli_absolute_path(monkeypatch, tmp_path) -> None:
    hf = make_executable(tmp_path / "hf")

    def fake_which(executable: str) -> str | None:
        return hf if executable == "hf" else None

    monkeypatch.setattr(run_hf_job.shutil, "which", fake_which)

    assert run_hf_job.detect_hf_cli_command("hf") == [hf]


def test_detects_uvx_hf_cli_fallback(monkeypatch, tmp_path) -> None:
    uvx = make_executable(tmp_path / "uvx")

    def fake_which(executable: str) -> str | None:
        return uvx if executable == "uvx" else None

    monkeypatch.setattr(run_hf_job.shutil, "which", fake_which)

    assert run_hf_job.detect_hf_cli_command() == [uvx, "--from", "huggingface_hub", "hf"]


def test_skips_stale_hf_path_and_selects_uvx(monkeypatch, tmp_path) -> None:
    uvx = make_executable(tmp_path / "uvx")
    stale_hf = str(tmp_path / "missing-hf")

    def fake_which(executable: str) -> str | None:
        return {"hf": stale_hf, "uvx": uvx}.get(executable)

    monkeypatch.setattr(run_hf_job.shutil, "which", fake_which)

    assert run_hf_job.detect_hf_cli_command() == [uvx, "--from", "huggingface_hub", "hf"]


def test_fails_early_when_no_hf_cli_launcher(monkeypatch) -> None:
    monkeypatch.setattr(run_hf_job.shutil, "which", lambda _executable: None)

    try:
        run_hf_job.detect_hf_cli_command()
    except SystemExit as exc:
        message = str(exc)
    else:  # pragma: no cover - defensive assertion clarity
        raise AssertionError("expected SystemExit")

    assert "Hugging Face CLI launcher not found" in message
    assert "uvx --from huggingface_hub hf" in message


def test_persist_artifacts_appends_scratch_uploads() -> None:
    args = make_args(persist_artifacts=True, artifact_label="preview label")
    config_path = run_hf_job.PROJECT_ROOT / run_hf_job.DEFAULT_CONFIG
    script = run_hf_job.build_in_job_script(args, config_path)

    assert "this is NOT dataset release" in script
    assert "uvx --from huggingface_hub hf upload avreymi/reasoning-pruning-job-artifacts" in script
    assert "job-artifacts/preview-label/outputs/datasets/bbh_logical_deduction_gemma4_hf_preview.jsonl" in script
    assert "bbh_logical_deduction_gemma4_hf_preview.rejected.jsonl" in script
    assert "bbh_logical_deduction_gemma4_hf_preview.jsonl.manifest.json" in script


def test_dry_run_does_not_launch(monkeypatch, capsys, tmp_path) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(run_hf_job.subprocess, "run", fake_run)
    uvx = make_executable(tmp_path / "uvx")
    monkeypatch.setattr(run_hf_job.shutil, "which", lambda executable: uvx if executable == "uvx" else None)
    exit_code = run_hf_job.main([])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert calls == []
    assert "DRY RUN" in output
    assert "bash -c" in output


def test_dry_run_prints_uvx_fallback_command(monkeypatch, capsys, tmp_path) -> None:
    uvx = make_executable(tmp_path / "uvx")

    def fake_which(executable: str) -> str | None:
        return uvx if executable == "uvx" else None

    monkeypatch.setattr(run_hf_job.shutil, "which", fake_which)

    exit_code = run_hf_job.main([])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert f"{uvx} --from huggingface_hub hf jobs run" in output
    assert "\n# Local HF CLI executable argv:\nhf jobs run" not in output


def test_launch_uses_absolute_hf_cli_path_when_forced(monkeypatch, tmp_path) -> None:
    calls: list[list[str]] = []
    hf = make_executable(tmp_path / "hf")

    def fake_which(executable: str) -> str | None:
        return hf if executable == "hf" else None

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(run_hf_job.shutil, "which", fake_which)
    monkeypatch.setattr(run_hf_job.subprocess, "run", fake_run)
    monkeypatch.setenv("HF_TOKEN", "test-token")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    exit_code = run_hf_job.main(["--hf-cli", "hf", "--launch"])

    assert exit_code == 0
    assert calls
    assert calls[0][:4] == [hf, "jobs", "run", "--flavor"]


def test_launch_uses_uvx_fallback_without_file_not_found(monkeypatch, tmp_path) -> None:
    calls: list[list[str]] = []
    uvx = make_executable(tmp_path / "uvx")

    def fake_which(executable: str) -> str | None:
        return uvx if executable == "uvx" else None

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(run_hf_job.shutil, "which", fake_which)
    monkeypatch.setattr(run_hf_job.subprocess, "run", fake_run)
    monkeypatch.setenv("HF_TOKEN", "test-token")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    exit_code = run_hf_job.main(["--launch"])

    assert exit_code == 0
    assert calls
    assert calls[0][:5] == [uvx, "--from", "huggingface_hub", "hf", "jobs"]


def test_launch_skips_stale_hf_path_and_uses_uvx(monkeypatch, tmp_path) -> None:
    calls: list[list[str]] = []
    uvx = make_executable(tmp_path / "uvx")
    stale_hf = str(tmp_path / "missing-hf")

    def fake_which(executable: str) -> str | None:
        return {"hf": stale_hf, "uvx": uvx}.get(executable)

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(run_hf_job.shutil, "which", fake_which)
    monkeypatch.setattr(run_hf_job.subprocess, "run", fake_run)
    monkeypatch.setenv("HF_TOKEN", "test-token")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    exit_code = run_hf_job.main(["--launch"])

    assert exit_code == 0
    assert calls
    assert calls[0][:5] == [uvx, "--from", "huggingface_hub", "hf", "jobs"]
    assert stale_hf not in calls[0]
