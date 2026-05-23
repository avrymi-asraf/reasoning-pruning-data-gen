---
name: huggingface-inference-endpoints
description: Records historical Hugging Face serverless, Inference Endpoint, TGI, and custom endpoint findings for reasoning-pruning. Use when investigating why endpoint-style model serving is deprecated here or when explicitly asked to revisit endpoint infrastructure.
---

<huggingface-inference-endpoints>
This project does not use HF Inference Endpoints, serverless providers, TGI, or custom endpoints as active data-generation paths. The canonical path is HF Jobs running the normal config runner. Load this skill only to understand historical endpoint failures or if the user explicitly asks to revisit serving infrastructure.
</huggingface-inference-endpoints>

<canonical-replacement>
For Gemma4 data creation, use HF Jobs with image `ghcr.io/astral-sh/uv:python3.11-bookworm`, flavor `a10g-large`, encrypted `HF_TOKEN` and `GEMINI_API_KEY`, a clone/download of `https://github.com/avrymi-asraf/reasoning-pruning-data-gen.git`, and the normal command:

```bash
uv run --extra hf --extra gemma4 python scripts/create_pruning_dataset.py --config config/bbh-logical-deduction-gemma4-hf-preview.toml
```

Successful preview reference: job `6a106a46b33ece92698c06f8`, accepted `3`, rejected `0`, generator `avreymi/reasoning-pruning-gemma-4-E2B-it`, decision model `gemini/gemini-2.5-flash-lite`.
</canonical-replacement>

<historical-findings>
- HF serverless/provider routing did not reliably serve the tested Gemma4 repos; provider catalog support was the blocker.
- A dedicated default-runtime HF Inference Endpoint with root `handler.py` and `requirements.txt` failed before useful inference because the stock runtime could not load the needed Gemma4/Transformers stack.
- TGI did not support the tested Gemma4/custom architecture path.
- A custom Docker endpoint was technically possible for permanent serving but is unnecessary operational surface for batch dataset generation.
</historical-findings>

<rules-for-this-repo>
- Do not create or resurrect root endpoint artifacts such as `handler.py` or `requirements.txt` for normal data generation.
- Do not present endpoint/serverless/TGI/custom Docker approaches as active alternatives in README, AGENTS, skills, or runbooks.
- If serving is explicitly revisited, keep it separate from the canonical data-creation path and require a new decision record.
- Never print or commit `HF_TOKEN`, endpoint credentials, or secret-bearing URLs.
</rules-for-this-repo>
