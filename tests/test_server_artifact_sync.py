"""Tests for the optional local Data UI scratch artifact sync path.

The server remains a local inspection aid around the normal config-driven data
pipeline. These tests cover the explicit HF Job scratch-retrieval workflow that
downloads already-uploaded job artifacts into `outputs/datasets/` without
launching jobs, generating data, or uploading/releasing datasets.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import server


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
