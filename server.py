#!/usr/bin/env python3
"""Optional local backend for the Sentence Pruning Data UI.

This server is a transparent development aid for editing config TOML, previewing
the exact CLI commands, running the normal local CLI subprocess, and inspecting
files under `outputs/`. Canonical data creation remains Hugging Face Jobs running
the repo's config-driven `scripts/create_pruning_dataset.py` command; this server
does not launch paid jobs or implement an alternate pipeline. It is intended for
local R&D use from the workspace root via `uv run server.py`.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import shlex
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = PROJECT_ROOT / "config"
HTML_FILE = PROJECT_ROOT / "pruning-playground.html"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
DATASETS_DIR = OUTPUTS_DIR / "datasets"

CANONICAL_CONFIG = "bbh-logical-deduction-gemma4-hf-preview"
CANONICAL_COMMAND = [
    "uv",
    "run",
    "--extra",
    "hf",
    "--extra",
    "gemma4",
    "python",
    "scripts/create_pruning_dataset.py",
    "--config",
    f"config/{CANONICAL_CONFIG}.toml",
]
SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
SAFE_REPO_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*$")
SECRET_NAMES = ["HF_TOKEN", "GEMINI_API_KEY"]
DEFAULT_ARTIFACT_REPO_ID = "avreymi/reasoning-pruning-job-artifacts"
DEFAULT_ARTIFACT_PREFIX_TEMPLATE = "job-artifacts/{label}/outputs/datasets"
HF_JOB_UPLOAD_COMMAND_PREFIX = ["uvx", "--from", "huggingface_hub", "hf", "upload"]
DEFAULT_HF_JOB_REPO_URL = "https://github.com/avrymi-asraf/reasoning-pruning-data-gen.git"
DEFAULT_HF_JOB_IMAGE = "ghcr.io/astral-sh/uv:python3.11-bookworm"
DEFAULT_HF_JOB_FLAVOR = "a10g-large"
DEFAULT_HF_JOB_TIMEOUT = "7200"
HF_JOB_CLI_CHOICES = {"auto", "uvx", "hf"}

app = FastAPI(title="Sentence Pruning Data Manager")

# Ephemeral in-memory run store keyed by run_id.
_runs: dict[str, dict[str, Any]] = {}


# ── Path, command, and validation helpers ─────────────────────────────────────

def shell_join(parts: list[str]) -> str:
    return shlex.join(parts)


def manifest_path_for(output_path: str | Path) -> Path:
    path = Path(output_path)
    return path.with_suffix(f"{path.suffix}.manifest.json") if path.suffix else path.with_name(f"{path.name}.manifest.json")


def resolved_under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def validate_config_name(name: str) -> str:
    if not name or not SAFE_NAME_RE.fullmatch(name):
        raise HTTPException(400, "Config name must contain only letters, numbers, _, ., or -")
    return name


def config_path_for_name(name: str, *, must_exist: bool = True) -> Path:
    safe_name = validate_config_name(name)
    path = CONFIG_DIR / f"{safe_name}.toml"
    if not resolved_under(path, CONFIG_DIR):
        raise HTTPException(400, "Config path must stay under config/")
    if must_exist and not path.exists():
        raise HTTPException(404, f"Config '{safe_name}' not found")
    return path


def load_config_data(name: str) -> dict[str, Any]:
    path = config_path_for_name(name)
    with path.open("rb") as fh:
        return tomllib.load(fh)


def validate_output_write_path(path_text: str) -> str:
    path = Path(path_text)
    if path.is_absolute() or ".." in path.parts:
        raise HTTPException(400, "Output path must be relative and stay under outputs/")
    if path.suffix != ".jsonl":
        raise HTTPException(400, "Output path must end with .jsonl")
    full = PROJECT_ROOT / path
    if not resolved_under(full, OUTPUTS_DIR):
        raise HTTPException(400, "Output path must stay under outputs/")
    return path.as_posix()


def validate_repo_id(repo_id: str) -> str:
    if not repo_id or not SAFE_REPO_ID_RE.fullmatch(repo_id) or ".." in repo_id:
        raise HTTPException(400, "repo_id must look like namespace/name and contain no traversal")
    return repo_id


def validate_artifact_prefix(prefix: str) -> str:
    path = Path(prefix)
    if not prefix or path.is_absolute() or ".." in path.parts:
        raise HTTPException(400, "artifact prefix must be a relative repo path with no traversal")
    for part in path.parts:
        if not SAFE_NAME_RE.fullmatch(part):
            raise HTTPException(400, "artifact prefix parts may contain only letters, numbers, _, ., or -")
    return path.as_posix()


def validate_output_basename(name: str) -> str:
    if not name or Path(name).name != name or not SAFE_NAME_RE.fullmatch(name):
        raise HTTPException(400, "Expected output files must be basenames with only letters, numbers, _, ., or -")
    if not (name.endswith(".jsonl") or name.endswith(".json")):
        raise HTTPException(400, "Expected output files must end with .jsonl or .json")
    return name


def validate_expected_basenames(names: list[str]) -> list[str]:
    if not names:
        raise HTTPException(400, "At least one expected output basename is required")
    if len(names) > 10:
        raise HTTPException(400, "Too many expected output files")
    seen: set[str] = set()
    safe: list[str] = []
    for name in names:
        checked = validate_output_basename(name)
        if checked not in seen:
            seen.add(checked)
            safe.append(checked)
    return safe


def validate_config_output_paths(data: dict[str, Any]) -> None:
    output = data.get("output")
    if output is None:
        return
    if not isinstance(output, dict):
        raise HTTPException(400, "Config output section must be a table")

    for key in ("accepted_path", "rejected_path"):
        value = output.get(key)
        if value is None or value == "":
            continue
        if not isinstance(value, str):
            raise HTTPException(400, f"output.{key} must be a string path")
        validate_output_write_path(value)


def validate_saved_config_output_paths(name: str) -> None:
    validate_config_output_paths(load_config_data(name))


def output_read_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute() or ".." in path.parts:
        raise HTTPException(400, "Output path must be relative and stay under outputs/")
    full = PROJECT_ROOT / path
    if not resolved_under(full, OUTPUTS_DIR):
        raise HTTPException(400, "Output path must stay under outputs/")
    if not full.exists() or full.suffix not in {".jsonl", ".json"}:
        raise HTTPException(404, "Output file not found")
    return full


def build_local_command(body: "CommandBody") -> list[str]:
    validate_saved_config_output_paths(body.config_name)
    cmd = [
        "uv",
        "run",
        "python",
        "scripts/create_pruning_dataset.py",
        "--config",
        f"config/{body.config_name}.toml",
    ]
    if body.limit is not None:
        if body.limit < 1:
            raise HTTPException(400, "limit must be >= 1")
        cmd += ["--limit", str(body.limit)]
    if body.output_path:
        cmd += ["--output", validate_output_write_path(body.output_path)]
    if upload_gate_satisfied(body):
        cmd += ["--upload-to-hf"]
    return cmd


def build_local_server_command() -> list[str]:
    return ["uv", "run", "server.py"]


def upload_gate_satisfied(body: "CommandBody") -> bool:
    return bool(body.upload_to_hf and body.upload_approval and body.upload_phrase == "UPLOAD")


def build_hf_job_script(body: "CommandBody") -> str:
    local_command = build_local_command(body)
    in_job_command = list(CANONICAL_COMMAND) if body.config_name == CANONICAL_CONFIG else [
        "uv",
        "run",
        "--extra",
        "hf",
        "--extra",
        "gemma4",
        "python",
        "scripts/create_pruning_dataset.py",
        "--config",
        f"config/{body.config_name}.toml",
    ]
    extra_args = local_command[6:]
    if extra_args:
        in_job_command += extra_args

    lines = [
        "# Copy-visible HF Jobs script. This UI does not launch the paid job.",
        "# Requires encrypted HF Job secrets named HF_TOKEN and GEMINI_API_KEY.",
        "# Confirm image/flavor in the HF Jobs UI or CLI before launching.",
        shell_join(in_job_command),
    ]
    if body.persist_artifacts:
        repo_id = validate_repo_id(body.artifact_repo_id or DEFAULT_ARTIFACT_REPO_ID)
        prefix = validate_artifact_prefix(body.artifact_prefix or default_artifact_prefix(body))
        lines += [
            "",
            "# Explicit scratch artifact persistence for later local download.",
            "# This is NOT dataset release; it uploads run artifacts to a private scratch dataset repo.",
            "# There is no direct hf jobs download for ephemeral job-local files.",
        ]
        for path in expected_artifact_paths(body):
            remote_path = f"{prefix}/{Path(path).name}"
            lines.append(shell_join(HF_JOB_UPLOAD_COMMAND_PREFIX + [repo_id, path, remote_path, "--repo-type", "dataset", "--private"]))
    return "\n".join(lines)


def default_artifact_prefix(body: "CommandBody") -> str:
    label = body.artifact_label or body.config_name or "manual-job-label"
    safe_label = re.sub(r"[^A-Za-z0-9_.-]+", "-", label).strip(".-_") or "manual-job-label"
    return DEFAULT_ARTIFACT_PREFIX_TEMPLATE.format(label=safe_label)


def expected_artifact_paths(body: "CommandBody") -> list[str]:
    config = load_config_data(body.config_name)
    output = config.get("output", {}) if isinstance(config.get("output", {}), dict) else {}
    accepted = validate_output_write_path(body.output_path or output.get("accepted_path") or "outputs/datasets/run.jsonl")
    paths = [accepted]
    rejected = output.get("rejected_path")
    if isinstance(rejected, str) and rejected:
        paths.append(validate_output_write_path(rejected))
    paths.append(manifest_path_for(accepted).as_posix())
    return paths


def expected_artifact_basenames(body: "CommandBody") -> list[str]:
    return validate_expected_basenames([Path(path).name for path in expected_artifact_paths(body)])


def hf_cli_prefix() -> list[str]:
    uvx_path = shutil.which("uvx")
    if uvx_path and Path(uvx_path).is_file() and os.access(uvx_path, os.X_OK):
        return [uvx_path, "--from", "huggingface_hub", "hf"]
    hf_path = shutil.which("hf")
    if hf_path and Path(hf_path).is_file() and os.access(hf_path, os.X_OK):
        return [hf_path]
    return ["uvx", "--from", "huggingface_hub", "hf"]


def build_hf_download_command(body: "ArtifactSyncBody") -> list[str]:
    repo_id = validate_repo_id(body.repo_id)
    prefix = validate_artifact_prefix(body.artifact_prefix)
    filenames = [f"{prefix}/{name}" for name in validate_expected_basenames(body.expected_basenames)]
    return hf_cli_prefix() + ["download", repo_id, *filenames, "--repo-type", body.repo_type, "--local-dir", "<temp-dir>"]


def build_hf_job_dry_run_command(body: "HFJobBody") -> list[str]:
    if body.launch:
        raise HTTPException(400, "HF Jobs --launch is intentionally unavailable from this UI")
    config_path = body.config or f"config/{CANONICAL_CONFIG}.toml"
    if Path(config_path).is_absolute() or ".." in Path(config_path).parts:
        raise HTTPException(400, "HF job config must be a relative config path")
    if not config_path.startswith("config/") or not config_path.endswith(".toml"):
        raise HTTPException(400, "HF job config must look like config/<name>.toml")
    config_name = Path(config_path).stem
    config_path_for_name(config_name)
    if body.hf_cli not in HF_JOB_CLI_CHOICES:
        raise HTTPException(400, "hf_cli must be one of auto, uvx, hf")

    cmd = [
        "uv",
        "run",
        "python",
        "scripts/run_hf_job.py",
        "--config",
        config_path,
        "--repo-url",
        body.repo_url,
        "--image",
        body.image,
        "--flavor",
        body.flavor,
        "--timeout",
        body.timeout,
        "--artifact-repo",
        validate_repo_id(body.artifact_repo),
        "--hf-cli",
        body.hf_cli,
    ]
    if body.ref:
        cmd += ["--ref", body.ref]
    if body.persist_artifacts:
        cmd.append("--persist-artifacts")
    if body.artifact_prefix:
        cmd += ["--artifact-prefix", validate_artifact_prefix(body.artifact_prefix)]
    if body.artifact_label:
        cmd += ["--artifact-label", body.artifact_label]
    return cmd


async def run_hf_download(body: "ArtifactSyncBody", temp_dir: Path) -> tuple[list[str], str]:
    cmd = build_hf_download_command(body)
    cmd = [str(temp_dir) if part == "<temp-dir>" else part for part in cmd]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(PROJECT_ROOT),
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        detail = (stderr or stdout).decode(errors="replace")[-1200:]
        raise HTTPException(502, f"hf download failed with exit {proc.returncode}: {detail}")
    return cmd, stdout.decode(errors="replace")


def copy_downloaded_artifacts(temp_dir: Path, body: "ArtifactSyncBody") -> list[dict[str, Any]]:
    prefix = validate_artifact_prefix(body.artifact_prefix)
    basenames = validate_expected_basenames(body.expected_basenames)
    DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    copied: list[dict[str, Any]] = []
    for basename in basenames:
        source = temp_dir / prefix / basename
        if not source.exists() or not source.is_file():
            raise HTTPException(404, f"Downloaded artifact not found: {prefix}/{basename}")
        destination = DATASETS_DIR / basename
        if not resolved_under(destination, DATASETS_DIR):
            raise HTTPException(400, "Destination must stay under outputs/datasets/")
        shutil.copy2(source, destination)
        copied.append({
            "basename": basename,
            "path": str(destination.relative_to(PROJECT_ROOT)),
            "size": destination.stat().st_size,
        })
    return copied


# ── HTML ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return HTML_FILE.read_text(encoding="utf-8")


# ── Config API ───────────────────────────────────────────────────────────────

@app.get("/api/configs")
async def list_configs() -> dict:
    configs = []
    for p in sorted(CONFIG_DIR.glob("*.toml")):
        if SAFE_NAME_RE.fullmatch(p.stem):
            configs.append({"name": p.stem, "path": f"config/{p.name}"})
    return {"configs": configs, "canonical_config": CANONICAL_CONFIG}


@app.get("/api/config/{name}")
async def get_config(name: str) -> dict:
    return {"name": name, "data": load_config_data(name)}


class SaveConfigBody(BaseModel):
    data: dict[str, Any]


@app.post("/api/config/{name}")
async def save_config(name: str, body: SaveConfigBody) -> dict:
    CONFIG_DIR.mkdir(exist_ok=True)
    path = config_path_for_name(name, must_exist=False)
    validate_config_output_paths(body.data)
    path.write_text(build_toml(body.data), encoding="utf-8")
    return {"saved": True, "path": f"config/{path.name}"}


# ── Run API ───────────────────────────────────────────────────────────────────

class CommandBody(BaseModel):
    config_name: str
    limit: int | None = None
    output_path: str | None = None
    upload_to_hf: bool = False
    upload_approval: bool = False
    upload_phrase: str | None = None
    persist_artifacts: bool = False
    artifact_repo_id: str | None = DEFAULT_ARTIFACT_REPO_ID
    artifact_prefix: str | None = None
    artifact_label: str | None = None


class RunBody(CommandBody):
    pass


class ArtifactSyncBody(BaseModel):
    repo_id: str = DEFAULT_ARTIFACT_REPO_ID
    repo_type: str = "dataset"
    artifact_prefix: str
    expected_basenames: list[str]


class HFJobBody(BaseModel):
    config: str = f"config/{CANONICAL_CONFIG}.toml"
    repo_url: str = DEFAULT_HF_JOB_REPO_URL
    ref: str = ""
    image: str = DEFAULT_HF_JOB_IMAGE
    flavor: str = DEFAULT_HF_JOB_FLAVOR
    timeout: str = DEFAULT_HF_JOB_TIMEOUT
    persist_artifacts: bool = False
    artifact_repo: str = DEFAULT_ARTIFACT_REPO_ID
    artifact_prefix: str = ""
    artifact_label: str = ""
    hf_cli: str = "auto"
    launch: bool = False


@app.post("/api/command-preview")
async def command_preview(body: CommandBody) -> dict:
    local_cmd = build_local_command(body)
    canonical_text = shell_join(CANONICAL_COMMAND)
    sync_body = ArtifactSyncBody(
        repo_id=body.artifact_repo_id or DEFAULT_ARTIFACT_REPO_ID,
        repo_type="dataset",
        artifact_prefix=body.artifact_prefix or default_artifact_prefix(body),
        expected_basenames=expected_artifact_basenames(body),
    )
    sync_cmd = build_hf_download_command(sync_body)
    return {
        "local_command": shell_join(local_cmd),
        "local_command_parts": local_cmd,
        "canonical_command": canonical_text,
        "hf_jobs_script": build_hf_job_script(body),
        "artifact_repo_id": sync_body.repo_id,
        "artifact_prefix": sync_body.artifact_prefix,
        "artifact_expected_basenames": sync_body.expected_basenames,
        "artifact_sync_command": shell_join(sync_cmd),
        "secret_names": SECRET_NAMES,
        "env_presence": {name: bool(os.environ.get(name)) for name in SECRET_NAMES},
        "launches_paid_job": False,
        "upload_flag_included": "--upload-to-hf" in local_cmd,
    }


@app.get("/api/local-server/preview")
async def local_server_preview() -> dict:
    cmd = build_local_server_command()
    return {"command": shell_join(cmd), "command_parts": cmd, "copy_only": True}


@app.post("/api/hf-job/preview")
async def hf_job_preview(body: HFJobBody) -> dict:
    cmd = build_hf_job_dry_run_command(body)
    return {
        "command": shell_join(cmd),
        "command_parts": cmd,
        "launches_paid_job": False,
        "secret_names": SECRET_NAMES,
        "env_presence": {name: bool(os.environ.get(name)) for name in SECRET_NAMES},
    }


@app.post("/api/hf-job/dry-run")
async def hf_job_dry_run(body: HFJobBody) -> dict:
    cmd = build_hf_job_dry_run_command(body)
    completed = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "command": shell_join(cmd),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "launches_paid_job": False,
    }


@app.get("/api/env-status")
async def env_status() -> dict:
    return {"secrets": {name: bool(os.environ.get(name)) for name in SECRET_NAMES}}


@app.post("/api/artifacts/sync-preview")
async def artifact_sync_preview(body: ArtifactSyncBody) -> dict:
    if body.repo_type != "dataset":
        raise HTTPException(400, "Only repo_type=dataset is supported for scratch artifacts")
    cmd = build_hf_download_command(body)
    return {
        "command": shell_join(cmd),
        "repo_id": validate_repo_id(body.repo_id),
        "repo_type": body.repo_type,
        "artifact_prefix": validate_artifact_prefix(body.artifact_prefix),
        "expected_basenames": validate_expected_basenames(body.expected_basenames),
    }


@app.post("/api/artifacts/sync")
async def sync_artifacts(body: ArtifactSyncBody) -> dict:
    if body.repo_type != "dataset":
        raise HTTPException(400, "Only repo_type=dataset is supported for scratch artifacts")
    validate_repo_id(body.repo_id)
    validate_artifact_prefix(body.artifact_prefix)
    validate_expected_basenames(body.expected_basenames)
    with tempfile.TemporaryDirectory(prefix="hf-job-artifacts-") as tmp:
        temp_dir = Path(tmp)
        command, stdout = await run_hf_download(body, temp_dir)
        copied = copy_downloaded_artifacts(temp_dir, body)
    return {
        "synced": True,
        "command": shell_join(command),
        "files": copied,
        "stdout_tail": stdout[-1200:],
    }


@app.post("/api/run")
async def start_run(body: RunBody) -> dict:
    cmd = build_local_command(body)
    run_id = str(uuid.uuid4())[:8]
    command_text = shell_join(cmd)
    _runs[run_id] = {
        "status": "running",
        "stop_requested": False,
        "lines": [f"$ {command_text}\n"],
        "command": command_text,
        "process": None,
    }
    asyncio.create_task(_run_task(run_id, cmd))
    return {"run_id": run_id, "command": command_text}


async def _run_task(run_id: str, cmd: list[str]) -> None:
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    try:
        run = _runs[run_id]
        if run.get("stop_requested"):
            run["status"] = "stopped"
            return

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(PROJECT_ROOT),
            env=env,
        )
        run = _runs[run_id]
        run["process"] = proc
        if run.get("stop_requested"):
            run["status"] = "stopped"
            await _terminate_process_for_stop(run, proc)
            return

        assert proc.stdout is not None
        while True:
            raw = await proc.stdout.readline()
            if not raw:
                break
            run["lines"].append(raw.decode(errors="replace"))
        await proc.wait()
        if run.get("stop_requested") or run["status"] == "stopped":
            run["status"] = "stopped"
            run["returncode"] = proc.returncode
            return
        run["status"] = "done" if proc.returncode == 0 else "error"
        run["returncode"] = proc.returncode
    except Exception as exc:
        run = _runs[run_id]
        if run.get("stop_requested") or run["status"] == "stopped":
            run["status"] = "stopped"
            return
        run["status"] = "error"
        run["lines"].append(f"[server error] {exc}\n")


async def _terminate_process_for_stop(run: dict[str, Any], proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is None:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            run["lines"].append("[server] terminate timed out; killing subprocess\n")
            proc.kill()
            await proc.wait()
    run["returncode"] = proc.returncode


@app.post("/api/run/{run_id}/stop")
async def stop_run(run_id: str) -> dict:
    if run_id not in _runs:
        raise HTTPException(404, "Run not found")
    run = _runs[run_id]
    proc = run.get("process")
    run["stop_requested"] = True
    if run["status"] != "running":
        return {"status": run["status"]}
    run["status"] = "stopped"
    run["lines"].append("[server] stop requested; terminating subprocess\n")
    if proc and proc.returncode is None:
        await _terminate_process_for_stop(run, proc)
    else:
        run["returncode"] = getattr(proc, "returncode", None)
    return {"status": "stopped"}


@app.get("/api/run/{run_id}/stream")
async def stream_run(run_id: str) -> StreamingResponse:
    if run_id not in _runs:
        raise HTTPException(404, "Run not found")

    async def _gen():
        idx = 0
        while True:
            run = _runs[run_id]
            while idx < len(run["lines"]):
                yield f"data: {json.dumps({'line': run['lines'][idx]})}\n\n"
                idx += 1
            if run["status"] != "running":
                yield f"data: {json.dumps({'done': True, 'status': run['status']})}\n\n"
                break
            await asyncio.sleep(0.15)

    return StreamingResponse(_gen(), media_type="text/event-stream")


@app.get("/api/run/{run_id}/status")
async def run_status(run_id: str) -> dict:
    if run_id not in _runs:
        raise HTTPException(404, "Run not found")
    run = _runs[run_id]
    return {"status": run["status"], "line_count": len(run["lines"]), "command": run.get("command")}


# ── Output browser API ────────────────────────────────────────────────────────

@app.get("/api/outputs")
async def list_outputs() -> dict:
    files = []
    if OUTPUTS_DIR.exists():
        for p in sorted(OUTPUTS_DIR.rglob("*.json*")):
            if p.suffix not in {".jsonl", ".json"} or not resolved_under(p, OUTPUTS_DIR):
                continue
            count = count_records(p)
            files.append({
                "name": p.name,
                "path": str(p.relative_to(PROJECT_ROOT)),
                "kind": output_kind(p),
                "size": p.stat().st_size,
                "count": count,
            })
    return {"files": files}


@app.get("/api/output")
async def get_output(path: str, page: int = 0, page_size: int = 5) -> dict:
    full = output_read_path(path)
    page = max(0, page)
    page_size = min(max(1, page_size), 50)
    if full.suffix == ".jsonl":
        raw_lines = [ln for ln in full.read_text(encoding="utf-8").splitlines() if ln.strip()]
        total = len(raw_lines)
        start = page * page_size
        records = []
        for ln in raw_lines[start : start + page_size]:
            try:
                records.append(json.loads(ln))
            except Exception as exc:
                records.append({"parse_error": str(exc), "raw": ln})
        return {"kind": output_kind(full), "total": total, "page": page, "page_size": page_size, "records": records}

    try:
        parsed = json.loads(full.read_text(encoding="utf-8"))
    except Exception as exc:
        parsed = {"parse_error": str(exc), "raw": full.read_text(encoding="utf-8")}
    return {"kind": output_kind(full), "total": 1, "page": 0, "page_size": 1, "records": [parsed]}


def output_kind(path: Path) -> str:
    name = path.name
    if name.endswith(".manifest.json"):
        return "manifest"
    if name.endswith(".rejected.jsonl"):
        return "rejected"
    if path.suffix == ".jsonl":
        return "accepted-jsonl"
    return "json"


def count_records(path: Path) -> int:
    try:
        if path.suffix == ".jsonl":
            return sum(1 for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip())
        return 1
    except Exception:
        return -1


# ── TOML builder ──────────────────────────────────────────────────────────────

def build_toml(data: dict[str, Any]) -> str:
    lines: list[str] = []

    def _val(v: Any) -> str:
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, str):
            return json.dumps(v)
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, list):
            return "[" + ", ".join(_val(item) for item in v) + "]"
        return json.dumps(str(v))

    section_order = ["run", "source", "output", "generation", "decision", "iteration", "quality", "prompts"]
    section_order += [key for key in data.keys() if key not in section_order]
    for section in section_order:
        if section not in data:
            continue
        if not isinstance(data[section], dict):
            lines.append(f"{section} = {_val(data[section])}")
            continue
        lines.append(f"[{section}]")
        for key, val in data[section].items():
            if val is None:
                continue
            if isinstance(val, str) and "\n" in val:
                lines.append(f'{key} = """\n{val}\n"""')
            else:
                lines.append(f"{key} = {_val(val)}")
        lines.append("")

    return "\n".join(lines)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8765, reload=False)
