#!/usr/bin/env python3
"""FastAPI management server for the Sentence Pruning Data UI.

Run with:
    uv run server.py
or:
    uvicorn server:app --host 0.0.0.0 --port 8765 --reload
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
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
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
HTML_FILE = PROJECT_ROOT / "pruning-playground.html"

app = FastAPI(title="Sentence Pruning Data Manager")

# In-memory run store keyed by run_id
_runs: dict[str, dict[str, Any]] = {}


# ── HTML ─────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return HTML_FILE.read_text(encoding="utf-8")


# ── Config API ───────────────────────────────────────────────────────────────

@app.get("/api/configs")
async def list_configs() -> dict:
    configs = []
    for p in sorted(CONFIG_DIR.glob("*.toml")):
        configs.append({"name": p.stem, "path": f"config/{p.name}"})
    return {"configs": configs}


@app.get("/api/config/{name}")
async def get_config(name: str) -> dict:
    path = CONFIG_DIR / f"{name}.toml"
    if not path.exists():
        raise HTTPException(404, f"Config '{name}' not found")
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    return {"name": name, "data": data}


class SaveConfigBody(BaseModel):
    data: dict[str, Any]


@app.post("/api/config/{name}")
async def save_config(name: str, body: SaveConfigBody) -> dict:
    CONFIG_DIR.mkdir(exist_ok=True)
    path = CONFIG_DIR / f"{name}.toml"
    path.write_text(build_toml(body.data), encoding="utf-8")
    return {"saved": True, "path": f"config/{path.name}"}


# ── Run API ───────────────────────────────────────────────────────────────────

class RunBody(BaseModel):
    config_name: str
    limit: int | None = None
    output_path: str | None = None
    upload_to_hf: bool = False


@app.post("/api/run")
async def start_run(body: RunBody) -> dict:
    run_id = str(uuid.uuid4())[:8]
    _runs[run_id] = {"status": "running", "lines": []}
    asyncio.create_task(_run_task(run_id, body))
    return {"run_id": run_id}


async def _run_task(run_id: str, body: RunBody) -> None:
    cmd = [
        sys.executable,
        str(SCRIPTS_DIR / "create_pruning_dataset.py"),
        "--config", str(CONFIG_DIR / f"{body.config_name}.toml"),
    ]
    if body.limit is not None:
        cmd += ["--limit", str(body.limit)]
    if body.output_path:
        cmd += ["--output", body.output_path]
    if body.upload_to_hf:
        cmd += ["--upload-to-hf"]

    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=str(PROJECT_ROOT),
            env=env,
        )
        assert proc.stdout is not None
        while True:
            raw = await proc.stdout.readline()
            if not raw:
                break
            _runs[run_id]["lines"].append(raw.decode(errors="replace"))
        await proc.wait()
        _runs[run_id]["status"] = "done" if proc.returncode == 0 else "error"
        _runs[run_id]["returncode"] = proc.returncode
    except Exception as exc:
        _runs[run_id]["status"] = "error"
        _runs[run_id]["lines"].append(f"[server error] {exc}\n")


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
    return {"status": run["status"], "line_count": len(run["lines"])}


# ── Output browser API ────────────────────────────────────────────────────────

@app.get("/api/outputs")
async def list_outputs() -> dict:
    outputs_dir = PROJECT_ROOT / "outputs"
    files = []
    if outputs_dir.exists():
        for p in sorted(outputs_dir.rglob("*.jsonl")):
            try:
                lines = [ln for ln in p.read_text().splitlines() if ln.strip()]
                count = len(lines)
            except Exception:
                count = -1
            files.append({
                "name": p.name,
                "path": str(p.relative_to(PROJECT_ROOT)),
                "size": p.stat().st_size,
                "count": count,
            })
    return {"files": files}


@app.get("/api/output")
async def get_output(path: str, page: int = 0, page_size: int = 5) -> dict:
    full = PROJECT_ROOT / path
    if not full.exists() or full.suffix != ".jsonl":
        raise HTTPException(404, "Output file not found")
    raw_lines = [ln for ln in full.read_text().splitlines() if ln.strip()]
    total = len(raw_lines)
    start = page * page_size
    records = []
    for ln in raw_lines[start : start + page_size]:
        try:
            records.append(json.loads(ln))
        except Exception:
            pass
    return {"total": total, "page": page, "page_size": page_size, "records": records}


# ── TOML builder ──────────────────────────────────────────────────────────────

def build_toml(data: dict[str, Any]) -> str:
    lines: list[str] = []

    def _val(v: Any) -> str:
        if isinstance(v, bool):
            return "true" if v else "false"
        if isinstance(v, str):
            return f'"{v}"'
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, list):
            return "[" + ", ".join(_val(item) for item in v) + "]"
        return f'"{v}"'

    section_order = ["run", "source", "output", "generation", "decision", "iteration", "quality", "prompts"]
    for section in section_order:
        if section not in data:
            continue
        lines.append(f"[{section}]")
        for key, val in data[section].items():
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
