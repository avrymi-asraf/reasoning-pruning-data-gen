---
name: sentence-pruning-frontend
description: Use when building or extending optional local management UIs for any reasoning-pruning repo (data, train, experiments). Covers single-file HTML/FastAPI conventions, shared visual components, output inspection, config editing aids, and repo-specific UI boundaries.
---

<sentence-pruning-frontend>
This skill guides the lightweight local UIs used across the reasoning-pruning repos. These UIs are inspection and configuration aids for researchers; they are not the canonical execution path for serious Data repo creation. In the Data repo, canonical creation is Hugging Face Jobs running the config-driven CLI (`scripts/create_pruning_dataset.py --config ...`), with Hub release only after explicit user approval and the CLI's release gate. All buttons that run, copy, or release anything must show the exact command/script next to the button before action.

Topics covered:
- **Use [frontend-scope]** to keep UI responsibilities inside repo boundaries.
- **Use [tech-stack]** for the shared no-build architecture.
- **Use [design-system]** for CSS variables, layout, and reusable components.
- **Use [local-server-pattern]** for optional API/server structure.
- **Use [data-repo-ui-boundaries]** before touching the Data repo UI.
- **Use [repo-extension-guide]** for Train and Experiments UI variants.
- **Use [verification]** before finishing UI work.
</sentence-pruning-frontend>

<frontend-scope>
The reasoning-pruning system has three repos with separate responsibilities:

| Repo | Purpose | UI role |
|------|---------|---------|
| Data | Generate sentence-pruning datasets | Optional local config editing, preview inspection, and output browsing |
| Train | Fine-tune checkpoints from versioned datasets | Optional local training config aid and checkpoint browser |
| Experiments | Evaluate checkpoints and compare results | Optional local evaluation config aid and report browser |

Do not let a UI blur repo boundaries. Data UIs must not become training dashboards; Train UIs must not generate datasets; Experiments UIs must not own checkpoint training. Cross-repo handoff stays file-based through versioned datasets, manifests, checkpoints, and evaluation reports.
</frontend-scope>

<tech-stack>
Use the smallest local web stack that fits the research workflow:

- One root HTML file with inline CSS/JS for the browser UI.
- One root FastAPI server file when a live local API is needed.
- `uv` for Python dependencies; no npm, bundler, transpiler, React, Vue, or Svelte unless the user explicitly asks to migrate.
- Localhost only by default. Never expose secrets in logs, HTML, URLs, or browser storage.

The single-file approach is intentional: agents and researchers can read and edit the UI without a build graph. Keep helpers simple and colocated until the user asks for a larger frontend architecture.
</tech-stack>

<design-system>
Keep the shared visual identity stable. Reuse these CSS variables and add new component classes only when an existing class does not fit:

```css
:root {
  --bg: #0f1117;
  --surface: #1a1d27;
  --surface2: #242736;
  --border: #2e3146;
  --text: #e2e4ef;
  --muted: #7b7f99;
  --accent: #5b6aff;
  --accent-dim: #3d4acc;
  --green: #3ecf8e;
  --red: #f66;
  --yellow: #f5c543;
  --orange: #ff8c42;
  --radius: 8px;
  --mono: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
  --sans: system-ui, -apple-system, sans-serif;
}
```

Layout conventions:
- `body` is a full-height vertical flex column.
- Header, tab navigation, and active tab content stay visible without page reloads.
- A `.main` area normally uses a two-column grid: left for lists/forms, right for details/previews/logs.
- Use 14px sans-serif body text, 11px uppercase muted section labels, and 12px monospace for IDs, paths, logs, and JSON.

Common component classes:
- Header: `header`, `.subtitle`, `.spacer`, `.badge`.
- Tabs: `.tab-nav`, `.tab-btn`, `.tab-content`, `.active`.
- Panels: `.main`, `.panel`, `.panel-header`, `.panel-body`.
- Forms: `.form-section`, `.form-section-header`, `.form-row`, `.field`, `.field-label`, `.checkbox-row`.
- Buttons: `.btn-primary`, `.btn-run`, `.btn-danger`, `.btn-copy`, `.active`.
- Output browsing: `.file-list`, `.file-row`, `.file-name`, `.file-meta`, `.record-card`, `.record-id`, `.record-meta`, `.record-field-label`, `.record-field-value`, `.removed`, `.target`.

Prefer semantic text labels over clever icon-only controls. Existing class names are part of the shared UI language; rename them only as part of an intentional full UI cleanup.
</design-system>

<local-server-pattern>
When a repo needs a local UI backend, use a root-level FastAPI app that serves the HTML and exposes a small `/api/*` surface. Keep server state ephemeral and transparent:

```python
PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_DIR = PROJECT_ROOT / "config"
HTML_FILE = PROJECT_ROOT / "pruning-playground.html"

app = FastAPI(title="Sentence Pruning <Repo> Manager")
_runs: dict[str, dict] = {}

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML_FILE.read_text(encoding="utf-8")
```

Typical endpoints:
- `GET /api/configs` lists repo config files.
- `GET /api/config/{name}` loads a config for editing.
- `POST /api/config/{name}` saves a config using the repo's normal TOML structure.
- `GET /api/outputs` lists generated local outputs, reports, or checkpoints.
- `GET /api/output?...` returns paginated JSONL/JSON details for inspection.
- Optional run endpoints may stream local subprocess logs for development only; they must call the repo's normal CLI path and must never bypass explicit release gates.
- `POST /api/command-preview` should return the exact local command, canonical HF Jobs in-job command, copy-visible HF Jobs script text, secret names/presence booleans only, whether upload is gated in, and `launches_paid_job: false`.
- `GET /api/env-status` may report only secret-name presence booleans, never values.

Use SSE for log streaming when needed: keep an in-memory run record, log the exact command before execution, spawn a subprocess with `PYTHONUNBUFFERED=1`, append stdout/stderr lines, and stream JSON events until status is `done`, `error`, or `stopped`. Provide a stop endpoint that terminates/kills the subprocess and marks the run `stopped`.
</local-server-pattern>

<data-repo-ui-boundaries>
The Data repo UI is optional. Treat root UI files such as `server.py` and `pruning-playground.html` as local aids for editing TOML configs, inspecting outputs under `outputs/`, previewing visible commands, running the normal local CLI path, and manually exploring prompts. Do not describe them as the active/default way to create durable datasets.

Canonical Data creation is:

```bash
uv run --extra hf --extra gemma4 python scripts/create_pruning_dataset.py --config config/bbh-logical-deduction-gemma4-hf-preview.toml
```

For real Gemma4 dataset work, this command runs inside Hugging Face Jobs with the approved image/flavor and encrypted secrets. The UI may show a copy-visible HF Jobs script/command, but it should not directly launch paid jobs unless the user explicitly asks for that implementation later. The UI may help prepare or inspect the same config/output artifacts, but final dataset selection still requires manifest/audit inspection and copying/versioning selected artifacts under `../reasoning-pruning-datasets`.

Hub release behavior must stay exceptional. Do not add normal form controls that make upload look routine. If a UI exposes release behavior at all, it must be clearly labeled as requiring explicit user approval, default off, require an explicit checkbox plus typed phrase such as `UPLOAD`, and include a visible `--upload-to-hf` in the command preview only when the gate is satisfied. The UI must invoke only the canonical CLI release gate rather than implementing its own upload path.

Output views in the Data repo should include accepted JSONL rows, rejected/audit JSONL rows with reason/error/source question/decision details, and manifest JSON with both a short summary and raw JSON. Restrict output browsing to `outputs/` and prevent path traversal for reads and writes.
</data-repo-ui-boundaries>

<repo-extension-guide>
For Train and Experiments, copy the local UI conventions but adapt the content to the repo's ownership:

**Train repo**
- Config sections should match training config files: run, model, dataset, LoRA/QLoRA, training, output.
- Output views should inspect checkpoint directories and `run_metadata.json`.
- Logs may show loss, step, epoch, and checkpoint paths.
- Do not generate or mutate Data repo datasets from the Train UI.

**Experiments repo**
- Config sections should match evaluation/experiment configs: run, model/checkpoint, datasets, benchmark settings, output.
- Output views should inspect evaluation reports and comparisons.
- Comparison tabs may show metric deltas with green for improvement and red for regression.
- Do not train checkpoints or launch Data repo generation from the Experiments UI.

If the shared Data repo skill directory is symlinked into other repos, edit the source skill in the Data repo so the shared guidance stays consistent.
</repo-extension-guide>

<javascript-patterns>
Use small explicit JS helpers:

```js
function escapeHtml(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;')
                        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function setValue(id, val) {
  const el = document.getElementById(id);
  if (!el) return;
  if (el.tagName === 'SELECT') el.value = String(val ?? '');
  else el.value = val ?? '';
}

function str(id) { return (document.getElementById(id)?.value ?? '').trim(); }
function num(id) { const v = str(id); return v === '' ? null : parseInt(v, 10); }
function numF(id) { const v = str(id); return v === '' ? null : parseFloat(v); }
```

For tab switching, keep one `TABS` array and toggle `.active` on matching buttons and content panels. For output browsing, paginate records so large JSONL files do not freeze the browser. Render untrusted file contents with `escapeHtml` or text nodes, never raw `innerHTML`.
</javascript-patterns>

<verification>
Before finishing UI or skill changes:

1. Re-read the edited sections for repo-boundary wording.
2. Confirm the Data repo UI is framed only as optional local config/inspection support.
3. Confirm Hub release wording says explicit user approval and the canonical CLI gate are required.
4. Run focused checks available in the repo, such as `git diff --check` and any quick no-network tests relevant to the touched files.
5. For this skill specifically, keep `SKILL.md` under 300 lines.
</verification>

<anti-patterns>
- Do not add a frontend framework or build system for these local tools unless explicitly requested.
- Do not change the shared CSS root variables casually.
- Do not store backend run state in a database for the local UI.
- Do not print secrets or raw tokens in local logs or browser-rendered responses.
- Do not make release/upload actions look routine; they require explicit approval and the repo's normal release gate.
- Do not use stale config names such as `r1_version`; current configs use `format_version = "1.0"` where applicable.
</anti-patterns>
