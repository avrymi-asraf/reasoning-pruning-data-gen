---
name: litellm-data-generation
description: Guides required LiteLLM generation and pruning decisions for the reasoning-pruning Data repo. Use when running Gemini Flash Lite data generation, choosing generation/decision models, or debugging LiteLLM JSON decisions.
---

<litellm-data-generation>
Use this skill when the Data repo reasoning-pruning runner calls live models through LiteLLM. Runs require a real model and default to Gemini Flash Lite (`gemini/gemini-2.5-flash-lite`) for both reasoning generation and pruning decisions, with optional Hugging Face hosted generation through `provider = "huggingface"`. Source, output, provider/model/base-url, temperatures, iteration limits, quality gates, HF settings, and prompts live in config files; LiteLLM calls are isolated in `scripts/llm_client.py`. Unit tests may monkeypatch the Python call; runnable dataset creation uses live LiteLLM calls.
</litellm-data-generation>

<safe-live-workflow>
1. Keep credentials in provider environment variables or `.env`; do not print, copy, or commit secret values. `GEMINI_API_KEY` is expected for the default Gemini run.
2. Let the script load `.env`, or source it without echoing values: `set -a && source .env && set +a`.
3. Edit prompts and model settings in `config/default.toml` when needed; do not hard-code prompt changes in Python.
4. Run the local seed/dev config first:
   `uv run python scripts/create_pruning_dataset.py --config config/default.toml`
5. Inspect the JSONL for `input_x`, `target_y`, removed span, decision rationale, prompt config path, and verification checks before scaling up.
</safe-live-workflow>

<huggingface-hosted-workflow>
For a model served on Hugging Face, set `provider = "huggingface"`. Serverless inference provider routing uses model strings like `huggingface/<provider>/<org>/<model>` with `HF_TOKEN`; dedicated HF Inference Endpoints/TGI use `model = "huggingface/tgi"` and the endpoint URL in `base_url`, which the runner forwards to LiteLLM as `api_base`. Do not put tokens or endpoint URLs in docs, manifests, or committed configs; prefer environment variables and wrapper scripts that only record `base_url_configured`. Custom architectures may not run on generic serverless providers, so a dedicated endpoint can be required even when the model repo exists on the Hub.
</huggingface-hosted-workflow>

<decision-json-contract>
Pruning decisions must return strict JSON only: `{"status":"remove","remove_unit_ids":["u001"],"rationale":"..."}` or `{"status":"no_prune","remove_unit_ids":[],"rationale":"..."}` or `{"status":"stop","remove_unit_ids":[],"rationale":"..."}`. A `remove` decision must name the first safely removable contiguous span and leave a next kept unit for `target_y`. Malformed JSON, unknown ids, non-contiguous spans, empty/all spans, too-long spans, or no next target go to reject/audit output, not training data.
</decision-json-contract>

<output-schema>
Accepted training JSONL is compact local-transition data with exactly `id`, `question`, `input_x`, `target_y`, `depth`, and `decision`. `input_x` is the question/current context plus the useful prefix, and `target_y` is the next useful sentence after the skipped span. Heavy provenance such as removed span details, full generation, source metadata, verification, model metadata, prompts, and rejected examples belongs in the manifest or private audit output, not every accepted row.
</output-schema>

<common-mistakes>
- Use `uv run python scripts/create_pruning_dataset.py --config config/default.toml` or a dataset-specific config under `config/*.toml` for runnable dataset creation.
- Do not require live credentials for unit tests; monkeypatch the Python LiteLLM call instead.
- Do not paste API keys into docs, config, outputs, or prompts.
- Do not save rejected or malformed live examples as training data.
- Do not hide provider switching in docs; use `config/default.toml` provider/model/base-url fields for OpenAI-compatible/local experiments.
- Do not assume an HF model repo is automatically runnable through serverless inference; test a tiny preview and fall back to a dedicated endpoint when provider mapping/auth/custom-architecture errors occur.
</common-mistakes>
