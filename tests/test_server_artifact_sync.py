"""Tests for the optional local Data UI scratch artifact sync path.

The server remains a local inspection aid around the normal config-driven data
pipeline. These tests cover the explicit HF Job scratch-retrieval workflow that
downloads already-uploaded job artifacts into `outputs/datasets/` without
launching jobs, generating data, or uploading/releasing datasets.
"""

from __future__ import annotations

from pathlib import Path
import subprocess

from fastapi.testclient import TestClient

import server


def assert_no_bare_hf_upload_line(script: str) -> None:
    assert not any(line.startswith("hf upload") for line in script.splitlines())


def test_hf_job_script_persist_artifacts_uses_uvx_upload() -> None:
    body = server.CommandBody(
        config_name=server.CANONICAL_CONFIG,
        persist_artifacts=True,
        artifact_label="preview label",
    )

    script = server.build_hf_job_script(body)

    assert "uvx --from huggingface_hub hf upload avreymi/reasoning-pruning-job-artifacts" in script
    assert_no_bare_hf_upload_line(script)


def test_command_preview_persist_artifacts_shows_uvx_upload() -> None:
    client = TestClient(server.app)
    response = client.post(
        "/api/command-preview",
        json={
            "config_name": server.CANONICAL_CONFIG,
            "persist_artifacts": True,
            "artifact_label": "preview label",
        },
    )

    assert response.status_code == 200, response.text
    script = response.json()["hf_jobs_script"]
    assert "uvx --from huggingface_hub hf upload avreymi/reasoning-pruning-job-artifacts" in script
    assert_no_bare_hf_upload_line(script)


def test_hf_job_preview_builds_no_launch_dry_run_with_persist_artifacts() -> None:
    client = TestClient(server.app)
    response = client.post(
        "/api/hf-job/preview",
        json={
            "config": f"config/{server.CANONICAL_CONFIG}.toml",
            "persist_artifacts": True,
            "artifact_repo": "avreymi/reasoning-pruning-job-artifacts",
            "artifact_prefix": "job-artifacts/preview/outputs/datasets",
            "artifact_label": "preview",
            "hf_cli": "uvx",
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["launches_paid_job"] is False
    assert "uv run python scripts/run_hf_job.py" in data["command"]
    assert "--persist-artifacts" in data["command"]
    assert "--artifact-prefix job-artifacts/preview/outputs/datasets" in data["command"]
    assert "--launch" not in data["command"]


def test_hf_job_preview_rejects_launch_request() -> None:
    client = TestClient(server.app)
    response = client.post(
        "/api/hf-job/preview",
        json={"config": f"config/{server.CANONICAL_CONFIG}.toml", "launch": True},
    )

    assert response.status_code == 400
    assert "--launch" in response.text


def test_hf_job_dry_run_executes_exact_no_launch_command(monkeypatch) -> None:
    client = TestClient(server.app)
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="# Mode: DRY RUN\n", stderr="")

    monkeypatch.setattr(server.subprocess, "run", fake_run)
    response = client.post(
        "/api/hf-job/dry-run",
        json={"config": f"config/{server.CANONICAL_CONFIG}.toml", "hf_cli": "auto"},
    )

    assert response.status_code == 200, response.text
    assert calls
    assert calls[0][:4] == ["uv", "run", "python", "scripts/run_hf_job.py"]
    assert "--launch" not in calls[0]
    assert response.json()["launches_paid_job"] is False


def test_local_server_preview_is_copy_only() -> None:
    client = TestClient(server.app)
    response = client.get("/api/local-server/preview")

    assert response.status_code == 200
    assert response.json() == {
        "command": "uv run server.py",
        "command_parts": ["uv", "run", "server.py"],
        "copy_only": True,
    }


def test_html_fetches_local_server_preview_for_copy_command() -> None:
    html = server.HTML_FILE.read_text(encoding="utf-8")

    assert "fetch('/api/local-server/preview')" in html
    assert 'id="localServerCommandBox">uv run server.py' not in html


def test_build_toml_round_trips_gemma4_fields_and_unknown_section() -> None:
    data = server.load_config_data(server.CANONICAL_CONFIG)
    data["extra_section"] = {"kept": "yes"}

    parsed = server.tomllib.loads(server.build_toml(data))

    assert parsed["generation"]["provider"] == "transformers"
    assert parsed["generation"]["model_revision"]
    assert parsed["generation"]["dtype"] == "bfloat16"
    assert parsed["generation"]["device_map"] == "auto"
    assert parsed["generation"]["transformers_loader"] == "auto_model_for_image_text_to_text"
    assert parsed["generation"]["top_p"] == 0.95
    assert parsed["output"]["hf_upload_path"] == ""
    assert parsed["iteration"]["stop_statuses"] == ["no_prune", "stop"]
    assert parsed["extra_section"] == {"kept": "yes"}


def test_artifact_sync_rejects_traversal_prefix() -> None:
    client = TestClient(server.app)
    response = client.post(
        "/api/artifacts/sync-preview",
        json={
            "repo_id": "avreymi/reasoning-pruning-job-artifacts",
            "repo_type": "dataset",
            "artifact_prefix": "job-artifacts/../outputs/datasets",
            "expected_basenames": ["run.jsonl"],
        },
    )
    assert response.status_code == 400


def test_artifact_sync_rejects_non_basename_output() -> None:
    client = TestClient(server.app)
    response = client.post(
        "/api/artifacts/sync-preview",
        json={
            "repo_id": "avreymi/reasoning-pruning-job-artifacts",
            "repo_type": "dataset",
            "artifact_prefix": "job-artifacts/job-123/outputs/datasets",
            "expected_basenames": ["nested/run.jsonl"],
        },
    )
    assert response.status_code == 400


def test_artifact_sync_preview_skips_stale_hf_path(monkeypatch, tmp_path: Path) -> None:
    client = TestClient(server.app)
    uvx = tmp_path / "uvx"
    uvx.write_text("#!/bin/sh\n", encoding="utf-8")
    uvx.chmod(0o755)
    monkeypatch.setattr(
        server.shutil,
        "which",
        lambda executable: {"hf": str(tmp_path / "missing-hf"), "uvx": str(uvx)}.get(executable),
    )

    response = client.post(
        "/api/artifacts/sync-preview",
        json={
            "repo_id": "avreymi/reasoning-pruning-job-artifacts",
            "repo_type": "dataset",
            "artifact_prefix": "job-artifacts/job-123/outputs/datasets",
            "expected_basenames": ["run.jsonl"],
        },
    )

    assert response.status_code == 200
    assert response.json()["command"].startswith(f"{uvx} --from huggingface_hub hf download")


def test_artifact_sync_copies_only_expected_files(monkeypatch, tmp_path: Path) -> None:
    client = TestClient(server.app)
    datasets_dir = tmp_path / "outputs" / "datasets"
    monkeypatch.setattr(server, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(server, "DATASETS_DIR", datasets_dir)

    async def fake_download(body: server.ArtifactSyncBody, temp_dir: Path) -> tuple[list[str], str]:
        artifact_dir = temp_dir / body.artifact_prefix
        artifact_dir.mkdir(parents=True)
        for name in body.expected_basenames:
            (artifact_dir / name).write_text(f"{name}\n", encoding="utf-8")
        (artifact_dir / "unexpected.jsonl").write_text("do not copy\n", encoding="utf-8")
        return ["hf", "download", body.repo_id, "--local-dir", str(temp_dir)], "ok"

    monkeypatch.setattr(server, "run_hf_download", fake_download)
    response = client.post(
        "/api/artifacts/sync",
        json={
            "repo_id": "avreymi/reasoning-pruning-job-artifacts",
            "repo_type": "dataset",
            "artifact_prefix": "job-artifacts/job-123/outputs/datasets",
            "expected_basenames": ["run.jsonl", "run.rejected.jsonl", "run.jsonl.manifest.json"],
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["synced"] is True
    assert [item["basename"] for item in data["files"]] == [
        "run.jsonl",
        "run.rejected.jsonl",
        "run.jsonl.manifest.json",
    ]
    assert (datasets_dir / "run.jsonl").read_text(encoding="utf-8") == "run.jsonl\n"
    assert not (datasets_dir / "unexpected.jsonl").exists()
