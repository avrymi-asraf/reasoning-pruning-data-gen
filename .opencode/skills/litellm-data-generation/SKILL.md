---
name: litellm-data-generation
description: Guides required LiteLLM generation and pruning decisions for the sentence-pruning Data repo. Use when running Gemini Flash Lite data generation, choosing generation/decision models, or debugging LiteLLM JSON decisions.
---

<litellm-data-generation>
Use this skill when the Data repo sentence-pruning runner calls live models through LiteLLM. Runs require a real model and default to Gemini Flash Lite (`gemini/gemini-2.5-flash-lite`) for both reasoning generation and pruning decisions. Source, output, provider/model/base-url, temperatures, iteration limits, quality gates, HF settings, and prompts live in `config/default.toml`; LiteLLM calls are isolated in `scripts/llm_client.py`. Unit tests may monkeypatch the Python call; runnable dataset creation uses live LiteLLM calls.
</litellm-data-generation>

<safe-live-workflow>
1. Keep credentials in provider environment variables or `.env`; do not print, copy, or commit secret values. `GEMINI_API_KEY` is expected for the default Gemini run.
2. Let the script load `.env`, or source it without echoing values: `set -a && source .env && set +a`.
3. Edit prompts and model settings in `config/default.toml` when needed; do not hard-code prompt changes in Python.
4. Run the local seed/dev config first:
   `uv run python scripts/create_pruning_dataset.py --config config/default.toml`
5. Inspect the JSONL for `input_x`, `target_y`, removed span, decision rationale, prompt config path, and verification checks before scaling up.
</safe-live-workflow>

<decision-json-contract>
Pruning decisions must return strict JSON only: `{"status":"remove","remove_unit_ids":["u001"],"rationale":"..."}` or `{"status":"no_prune","remove_unit_ids":[],"rationale":"..."}` or `{"status":"stop","remove_unit_ids":[],"rationale":"..."}`. A `remove` decision must name the first safely removable contiguous span and leave a next kept unit for `target_y`. Malformed JSON, unknown ids, non-contiguous spans, empty/all spans, too-long spans, or no next target go to reject/audit output, not training data.
</decision-json-contract>

<output-schema>
Accepted training JSONL is local-transition data: `input_x = question/current context + useful prefix`, `target_y = next useful sentence after the skipped span`, plus `removed_span`, `full_generation_before_pruning`, `pruned_context_after_decision`, `decision_explanation`, `quality_status`, units, source/task metadata, verification, model metadata, and `format_version`.
</output-schema>

<common-mistakes>
- Use `uv run python scripts/create_pruning_dataset.py --config config/default.toml` or a dataset-specific config under `config/*.toml` for runnable dataset creation.
- Do not require live credentials for unit tests; monkeypatch the Python LiteLLM call instead.
- Do not paste API keys into docs, config, outputs, or prompts.
- Do not save rejected or malformed live examples as training data.
- Do not hide provider switching in docs; use `config/default.toml` provider/model/base-url fields for OpenAI-compatible/local experiments.
</common-mistakes>
