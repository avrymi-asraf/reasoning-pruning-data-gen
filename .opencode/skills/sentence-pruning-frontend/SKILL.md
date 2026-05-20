---
name: sentence-pruning-frontend
description: Use when building or extending the management UI for any reasoning-pruning repo (data, train, experiments). Covers tech stack, design system, server architecture, CSS components, tab layout, config forms, run streaming, output browsing, and per-repo extension guide.
---

# Reasoning Pruning Frontend Guide

This skill is the single source of truth for building management UIs across all three repos:

| Repo | Path | Purpose |
|------|------|---------|
| Data | `/home/avreymi/code/reasoning-pruning/reasoning-pruning-data-gen` | Dataset creation & pruning |
| Train | `/home/avreymi/code/reasoning-pruning/reasoning-pruning-train` | LoRA/QLoRA fine-tuning |
| Experiments | `/home/avreymi/code/reasoning-pruning/reasoning-pruning-experiments` | Eval runs, metrics, comparisons |

The Data repo's frontend is the **reference implementation**. The Train and Experiments repos extend it with their own tabs — the same design language, CSS variables, server pattern, and component classes throughout.

---

## 1. Tech stack and philosophy

**Single-file HTML + FastAPI. No build pipeline.**

- One `pruning-playground.html` at the repo root. All CSS and JS are inline.
- One `server.py` at the repo root. FastAPI serves the HTML and exposes API endpoints.
- `uv` for all Python dependencies. No npm, no webpack, no transpilation.
- The HTML is ~1500–2000 lines. This is intentional: one file to open, one file to edit.

**Why no React/Vue/bundler?** These are research tools for a small team. A single HTML file loads instantly, requires no build step, and can be read/edited by an AI agent without understanding a module graph. When the UI grows complex enough to need a framework, migrate then — not before.

---

## 2. Running the server

Every repo has the same entry point:

```bash
# From the repo root
uv run python server.py
# Server listens on http://localhost:8765
```

**Adding the fastapi dependency** (once per repo):
```bash
uv add "fastapi[standard]>=0.100"
# or manually add to pyproject.toml dependencies
```

The server serves `pruning-playground.html` at `GET /` and exposes API routes under `/api/`. The port is **8765** by convention across all repos (each repo uses a different port if run simultaneously — 8765 for data, 8766 for train, 8767 for evaluate).

---

## 3. CSS design system

All CSS lives in the `<style>` block of the HTML. **Never change the root variables** — they define the shared visual identity.

```css
:root {
  --bg: #0f1117;        /* page background */
  --surface: #1a1d27;   /* panel backgrounds, header */
  --surface2: #242736;  /* form fields, cards */
  --border: #2e3146;    /* borders, dividers */
  --text: #e2e4ef;      /* primary text */
  --muted: #7b7f99;     /* labels, hints, secondary text */
  --accent: #5b6aff;    /* active tabs, focus rings, links */
  --accent-dim: #3d4acc;/* btn-primary background */
  --green: #3ecf8e;     /* success, btn-run, kept units */
  --red: #f66;          /* errors, removed units */
  --yellow: #f5c543;    /* warnings, running status */
  --orange: #ff8c42;    /* parse errors */
  --radius: 8px;
  --mono: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
  --sans: system-ui, -apple-system, sans-serif;
}
```

### Core layout

```css
body { display: flex; flex-direction: column; height: 100vh; overflow: hidden; }
/* header → tab-nav → tab-content (flex: 1) → .main (grid 1fr 1fr) → .panel */
```

The body is a vertical flex column. The active tab content takes all remaining height. Inside each tab, `.main` is a 2-column CSS grid.

### Typography rules
- Body text: 14px `var(--sans)`
- Section labels: 11px, uppercase, `font-weight: 600`, `color: var(--muted)`, `letter-spacing: 0.5px`
- Form field labels: 11px, `color: var(--muted)`
- Monospace (IDs, logs, code): `var(--mono)`, 12px
- Panel headers: 11px, uppercase, `font-weight: 600`, `color: var(--muted)`

---

## 4. Component catalog

Copy these exact class names and patterns. Do not invent new class names for things already covered here.

### Header
```html
<header>
  <h1>Sentence Pruning</h1>
  <span class="subtitle">Data Manager</span>  <!-- or "Training" / "Evaluation" -->
  <div class="spacer"></div>
  <span class="badge" id="serverBadge">server</span>
</header>
```

### Tab navigation
```html
<div class="tab-nav">
  <button class="tab-btn active" onclick="switchTab('run')">⚙ Config &amp; Run</button>
  <button class="tab-btn" onclick="switchTab('outputs')">📂 Outputs</button>
  <button class="tab-btn" onclick="switchTab('tool')">🔬 Tool Name</button>
</div>
```

`switchTab(name)` toggles `.active` on both `.tab-btn` elements and `.tab-content` divs.

### Two-panel layout
```html
<div class="main">         <!-- CSS grid: 1fr 1fr -->
  <div class="panel">      <!-- left: config / file list -->
    <div class="panel-header">⚙ Settings</div>
    <div class="panel-body"> ... </div>
  </div>
  <div class="panel">      <!-- right: prompts / details / execution -->
    ...
  </div>
</div>
```

### Config file bar
```html
<div class="config-bar">
  <span style="font-size:11px;color:var(--muted)">Config:</span>
  <select id="configSelect" onchange="onConfigSelectChange()"></select>
  <input type="text" id="configNameInput" placeholder="name" style="width:160px" />
  <button onclick="loadSelectedConfig()">Load</button>
  <button class="btn-primary" onclick="saveConfig()">Save</button>
  <button onclick="newConfig()">New</button>
</div>
```

### Form sections (left panel)
```html
<div class="form-section">
  <div class="form-section-header">[section-name]</div>
  <div class="form-row">          <!-- grid: 1fr 1fr -->
    <div class="field">
      <label class="field-label">field_name</label>
      <input type="text" id="cfg_section_field" />
    </div>
    <div class="field"> ... </div>
  </div>
  <div class="form-row triple">   <!-- grid: 1fr 1fr 1fr -->
    ...
  </div>
  <label class="checkbox-row">
    <input type="checkbox" id="cfg_flag" />
    flag_name
  </label>
</div>
```

**ID convention**: `cfg_{section}_{field}` — e.g. `cfg_gen_model`, `cfg_iter_max_depth`.

### Prompt accordion (right panel)
```html
<div class="prompt-item open" id="pi-name">
  <div class="prompt-item-header" onclick="togglePrompt('pi-name')">
    <span class="prompt-item-title">prompt_field_name</span>
    <span class="prompt-item-arrow">▲</span>
  </div>
  <div class="prompt-item-body">
    <div style="font-size:11px;color:var(--muted);margin-bottom:4px">
      Placeholders: {task_prompt}, {answer_hint}
    </div>
    <textarea class="prompt-editor" id="cfg_p_field_name"></textarea>
  </div>
</div>
```

The first item should be `.open` by default. `togglePrompt(id)` flips `.open` and rotates the arrow.

### Execution panel (bottom of right panel)
```html
<div class="exec-panel">
  <div class="exec-header">
    <button class="btn-run" id="runBtn" onclick="startRun()">▶ Run</button>
    <button onclick="stopRun()" id="stopBtn" style="display:none" class="btn-danger">■ Stop</button>
    <span class="run-status" id="runStatus">idle</span>
    <label class="checkbox-row" style="margin-left:4px;font-size:11px;color:var(--muted)">
      <input type="checkbox" id="someOption" />
      option label
    </label>
    <div style="flex:1"></div>
    <button onclick="clearLog()" style="font-size:11px">Clear log</button>
  </div>
  <div class="log-viewer" id="logViewer">
    <span style="color:var(--muted)">Run output will appear here…</span>
  </div>
</div>
```

The run-status badge classes: `run-status` (base) + `running` / `done` / `error`.

### Output file list (left panel, Tab 2)
```html
<div class="file-list" id="fileList"></div>
```

Built in JS:
```js
function buildFileRow(f) {
  const row = document.createElement('div');
  row.className = 'file-row';
  row.innerHTML = `
    <span class="file-name">${escapeHtml(f.name)}</span>
    <span class="file-meta">${f.count} records · ${formatBytes(f.size)}</span>
  `;
  row.onclick = () => selectFile(f.path, row);
  return row;
}
```

### Record card (right panel, Tab 2)
```html
<div class="record-card">
  <div class="record-id">${rec.id}</div>
  <div class="record-meta">
    <span>depth: ${rec.depth}</span>
    <span>status: ${rec.quality_status}</span>
  </div>
  <div>
    <div class="record-field-label">field name</div>
    <div class="record-field-value">${value}</div>
  </div>
  <div>
    <div class="record-field-label">removed_span</div>
    <div class="record-field-value removed">${rec.removed_span}</div>
  </div>
  <div>
    <div class="record-field-label">target_y</div>
    <div class="record-field-value target">${rec.target_y}</div>
  </div>
</div>
```

Key `.record-field-value` modifiers: `.removed` (red), `.target` (green).

### Button variants
```css
button              /* default: surface2 bg, muted */
button.btn-primary  /* accent-dim bg, white text — Save */
button.btn-run      /* green bg, dark text — Run */
button.btn-danger   /* red-tinted — Stop */
button.btn-copy     /* accent-dim, turns .copied (green) on success */
button.active       /* accent bg, white — toggle states */
```

---

## 5. Server architecture

`server.py` lives at the repo root. Standard structure:

```python
PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = PROJECT_ROOT / "config"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
HTML_FILE = PROJECT_ROOT / "pruning-playground.html"

app = FastAPI(title="Sentence Pruning <Repo> Manager")
_runs: dict[str, dict] = {}   # in-memory run store

@app.get("/", response_class=HTMLResponse)
async def index(): return HTML_FILE.read_text(encoding="utf-8")
```

### Standard endpoints (implement all in every repo)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/configs` | List `config/*.toml` |
| GET | `/api/config/{name}` | Load and parse a config |
| POST | `/api/config/{name}` | Save config (body: `{"data": {...}}`) |
| POST | `/api/run` | Start subprocess, return `{"run_id": "..."}` |
| GET | `/api/run/{id}/stream` | SSE stream of subprocess output |
| GET | `/api/run/{id}/status` | `{"status": "running"/"done"/"error"}` |
| GET | `/api/outputs` | List `outputs/**/*.jsonl` |
| GET | `/api/output?path=...&page=N&page_size=5` | Paginated JSONL records |

### SSE streaming pattern

```python
async def _run_task(run_id: str, cmd: list[str]) -> None:
    env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=str(PROJECT_ROOT),
        env=env,
    )
    while True:
        raw = await proc.stdout.readline()
        if not raw: break
        _runs[run_id]["lines"].append(raw.decode(errors="replace"))
    await proc.wait()
    _runs[run_id]["status"] = "done" if proc.returncode == 0 else "error"

@app.get("/api/run/{run_id}/stream")
async def stream_run(run_id: str) -> StreamingResponse:
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
```

### TOML builder

The server reconstructs a valid TOML string from the form JSON so configs saved from the UI are identical in structure to hand-written configs:

```python
def build_toml(data: dict) -> str:
    lines = []
    def _val(v):
        if isinstance(v, bool): return "true" if v else "false"
        if isinstance(v, str): return f'"{v}"'
        if isinstance(v, (int, float)): return str(v)
        if isinstance(v, list): return "[" + ", ".join(_val(i) for i in v) + "]"
        return f'"{v}"'
    for section in ["run", "source", "output", "generation", "decision",
                    "iteration", "quality", "prompts"]:  # adjust per repo
        if section not in data: continue
        lines.append(f"[{section}]")
        for key, val in data[section].items():
            if isinstance(val, str) and "\n" in val:
                lines.append(f'{key} = """\n{val}\n"""')
            else:
                lines.append(f"{key} = {_val(val)}")
        lines.append("")
    return "\n".join(lines)
```

---

## 6. JavaScript patterns

### Server health check
```js
async function checkServer() {
  try {
    const r = await fetch('/api/configs', { signal: AbortSignal.timeout(2000) });
    if (r.ok) {
      document.getElementById('serverBadge').textContent = 'server ✓';
      document.getElementById('serverBadge').style.color = 'var(--green)';
      return true;
    }
  } catch {}
  document.getElementById('serverBadge').textContent = 'server offline';
  document.getElementById('serverBadge').style.color = 'var(--red)';
  return false;
}
```

### Config load/save cycle
```js
async function loadConfigList() {
  const { configs } = await fetch('/api/configs').then(r => r.json());
  const sel = document.getElementById('configSelect');
  sel.innerHTML = '<option value="">— select —</option>';
  configs.forEach(c => {
    const opt = document.createElement('option');
    opt.value = c.name; opt.textContent = c.name;
    sel.appendChild(opt);
  });
}

async function loadSelectedConfig() {
  const name = document.getElementById('configNameInput').value.trim()
             || document.getElementById('configSelect').value;
  const { data } = await fetch(`/api/config/${name}`).then(r => r.json());
  populateForm(data);
}

async function saveConfig() {
  const name = document.getElementById('configNameInput').value.trim();
  const data = collectFormData();   // reads all form fields into a dict
  await fetch(`/api/config/${name}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ data }),
  });
}
```

### Form helpers
```js
function setValue(id, val) {
  const el = document.getElementById(id);
  if (!el) return;
  if (el.tagName === 'SELECT') {
    const opt = [...el.options].find(o => o.value === String(val));
    if (opt) el.value = String(val);
  } else { el.value = val ?? ''; }
}
function str(id)  { return (document.getElementById(id)?.value ?? '').trim(); }
function num(id)  { const v = str(id); return v === '' ? null : parseInt(v, 10); }
function numF(id) { const v = str(id); return v === '' ? null : parseFloat(v); }
```

### Run + SSE streaming
```js
let _activeEventSource = null;

async function startRun() {
  const name = document.getElementById('configNameInput').value.trim();
  if (!name) { alert('Load or save a config first.'); return; }

  document.getElementById('runBtn').disabled = true;
  document.getElementById('stopBtn').style.display = '';
  setRunStatus('running');
  appendLog(`\n▶ Starting run: ${name}\n`);

  const body = { config_name: name /*, other options */ };
  const { run_id } = await fetch('/api/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then(r => r.json());

  if (_activeEventSource) _activeEventSource.close();
  _activeEventSource = new EventSource(`/api/run/${run_id}/stream`);
  _activeEventSource.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.line) appendLog(data.line);
    if (data.done) { _activeEventSource.close(); finishRun(data.status); }
  };
  _activeEventSource.onerror = () => { appendLog('✗ Stream error\n'); finishRun('error'); };
}

function finishRun(status) {
  document.getElementById('runBtn').disabled = false;
  document.getElementById('stopBtn').style.display = 'none';
  setRunStatus(status);
}

function setRunStatus(status) {
  const el = document.getElementById('runStatus');
  el.textContent = status;
  el.className = 'run-status';
  if (status === 'running') el.classList.add('running');
  else if (status === 'done') el.classList.add('done');
  else if (['error', 'stopped'].includes(status)) el.classList.add('error');
}

function appendLog(text) {
  const v = document.getElementById('logViewer');
  if (v.querySelector('span[style]')) v.innerHTML = '';
  v.textContent += text;
  v.scrollTop = v.scrollHeight;
}
```

### Output browser
```js
let _selectedPath = null, _currentPage = 0, _totalRecords = 0;
const PAGE_SIZE = 5;

async function loadOutputsList() {
  const { files } = await fetch('/api/outputs').then(r => r.json());
  const list = document.getElementById('fileList');
  list.innerHTML = '';
  files.forEach(f => {
    const row = document.createElement('div');
    row.className = 'file-row' + (f.path === _selectedPath ? ' active' : '');
    row.innerHTML = `<span class="file-name">${escapeHtml(f.name)}</span>
                     <span class="file-meta">${f.count} records · ${formatBytes(f.size)}</span>`;
    row.onclick = () => selectFile(f.path, row);
    list.appendChild(row);
  });
}

async function selectFile(path, rowEl) {
  _selectedPath = path; _currentPage = 0;
  document.querySelectorAll('.file-row').forEach(r => r.classList.remove('active'));
  rowEl.classList.add('active');
  loadRecordsPage();
}

async function loadRecordsPage() {
  const { total, page, records } = await fetch(
    `/api/output?path=${encodeURIComponent(_selectedPath)}&page=${_currentPage}&page_size=${PAGE_SIZE}`
  ).then(r => r.json());
  _totalRecords = total; _currentPage = page;
  renderRecords(records, total, page);
}
```

### Prompt accordion toggle
```js
function togglePrompt(id) {
  const el = document.getElementById(id);
  el.classList.toggle('open');
  el.querySelector('.prompt-item-arrow').textContent =
    el.classList.contains('open') ? '▲' : '▼';
}
```

---

## 7. Per-repo extension guide

### Data repo (reference — already built)

`server.py` runs `scripts/create_pruning_dataset.py`. Config sections: `[run]`, `[source]`, `[output]`, `[generation]`, `[decision]`, `[iteration]`, `[quality]`, `[prompts]`.

**Tab 1 — Config & Run**: Left = full config form. Right = 5 prompt accordion + exec-panel.
Extra run options: `upload_to_hf` checkbox → `--upload-to-hf` flag.

**Tab 2 — Outputs**: Lists `outputs/datasets/*.jsonl`. Record fields: `id`, `depth`, `source_question`, `removed_span`, `input_x`, `target_y`, `decision_explanation`.

**Tab 3 — Playground**: Manual prompt sandbox for testing pruning decisions offline.

---

### Train repo (to be built — port 8766)

`server.py` runs `scripts/train_lora_poc.py`. Config sections: `[run]`, `[model]`, `[dataset]`, `[lora]`, `[training]`, `[output]`.

**Tab 1 — Config & Run**: Left = training config form. Right = exec-panel (training is long — log shows loss, step, epoch). Extra options: `--validate-only` checkbox.

Config form sections:
- `[run]` → run_name, random_seed
- `[model]` → base_model, revision, load_in_4bit
- `[dataset]` → path (points to data repo output), max_samples
- `[lora]` → r, lora_alpha, target_modules, dropout
- `[training]` → epochs, batch_size, lr, gradient_accumulation_steps, warmup_steps
- `[output]` → checkpoint_dir, push_to_hub, hub_repo

**Tab 2 — Checkpoints**: Lists `checkpoints/*/run_metadata.json`. Record card shows: run_name, base_model, dataset_path, lora_r, epochs, final_loss, timestamp.

**Tab 3 — Loss Curve**: Reads `run_metadata.json` loss history and renders a simple SVG or ASCII chart. Optional: link to Weights & Biases run URL.

---

### Evaluate repo (to be built — port 8767)

`server.py` runs `scripts/evaluate_pruning_run.py`. Config sections: `[run]`, `[model]`, `[datasets]`, `[output]`.

**Tab 1 — Config & Run**: Left = eval config form. Right = exec-panel. Extra options: dataset path override, checkpoint path override.

Config form sections:
- `[run]` → run_name, random_seed
- `[model]` → checkpoint_path or hub_model_id, base_model_id (for comparison)
- `[datasets]` → eval_dataset_paths (list of JSONL), benchmark_datasets
- `[output]` → report_path, push_results_to_hub

**Tab 2 — Results**: Lists `outputs/*.json` eval reports. Record card shows: run_name, model, dataset, accepted_count, metrics (accuracy, compression_ratio, coherence_score), timestamp.

**Tab 3 — Compare**: Side-by-side view of two eval reports. Highlight which model is better on each metric. Use colored deltas (green = improvement, red = regression).

---

## 8. Adding the server to a new repo

1. Add to `pyproject.toml`:
   ```toml
   dependencies = ["fastapi[standard]>=0.100", ...]
   ```

2. Run `uv sync` to install.

3. Copy `server.py` from the Data repo as a starting point and adapt:
   - Change the title in `FastAPI(title="...")`
   - Change the port in the `__main__` block (8766 for train, 8767 for eval)
   - Update `SCRIPTS_DIR` paths
   - Adapt the `RunBody` model and `_run_task` command list
   - Adapt the `build_toml()` section order

4. Create `pruning-playground.html` by copying the Data repo's version and:
   - Change `<title>` and `header h1`/subtitle
   - Update the three tab labels and `id="tab-*"` values
   - Replace the left-panel config form with the new repo's config sections
   - Replace the prompt accordion with whatever right-panel content fits
   - Replace the Tab 3 content with the repo-specific tool
   - Update `collectFormData()` and `populateForm()` to match new config structure
   - Keep all CSS variables, component classes, and JS helper functions identical

---

## 9. Shared utilities (copy verbatim)

```js
// Always include these in every HTML file
function escapeHtml(s) {
  return String(s ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;')
                         .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function formatBytes(b) {
  if (b < 1024) return `${b} B`;
  if (b < 1048576) return `${(b/1024).toFixed(1)} KB`;
  return `${(b/1048576).toFixed(1)} MB`;
}

// Tab switching — use TABS array matching tab IDs and button order
const TABS = ['run', 'outputs', 'tool'];   // adjust per repo
function switchTab(name) {
  TABS.forEach(t => document.getElementById(`tab-${t}`).classList.toggle('active', t === name));
  document.querySelectorAll('.tab-btn').forEach((btn, i) => btn.classList.toggle('active', TABS[i] === name));
  if (name === 'outputs') loadOutputsList();
}

// Boot sequence — always call in this order
document.addEventListener('DOMContentLoaded', () => {
  checkServer().then(ok => { if (ok) loadConfigList(); });
});
```

---

## 10. Softlinks

The skill file at `.opencode/skills/sentence-pruning-frontend/SKILL.md` lives in the Data repo. It is symlinked into the other repos so all three repos share one copy:

```bash
# From reasoning-pruning-experiments
ln -s /home/avreymi/code/reasoning-pruning/reasoning-pruning-data-gen/.opencode/skills/sentence-pruning-frontend \
      .opencode/skills/sentence-pruning-frontend

# From reasoning-pruning-train
ln -s /home/avreymi/code/reasoning-pruning/reasoning-pruning-data-gen/.opencode/skills/sentence-pruning-frontend \
      .opencode/skills/sentence-pruning-frontend
```

Update this skill whenever the Data repo UI is refactored — the symlinks ensure the other repos pick up the change immediately.

---

## 11. What not to do

- Do not add a JS framework (React, Vue, Svelte) or a bundler. One HTML file is the constraint.
- Do not change CSS root variables. Add new utility classes if needed, but never rename or revalue the existing ones.
- Do not split the HTML into multiple files — serving complexity is not worth it at this scale.
- Do not add backend state to the database. The `_runs` dict is intentionally ephemeral.
- Do not auto-upload to HF on every run. Upload is always an explicit `--upload-to-hf` flag.
- Do not use `r1_version` — it was renamed to `format_version = "1.0"` across all configs.
