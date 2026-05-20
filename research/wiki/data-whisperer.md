# Data Whisperer

## Summary

[[Data Whisperer]] is a training-free data selection method for task-specific LLM fine-tuning that uses few-shot in-context learning and attention-based weighting to score candidate examples.

## Details

Available summaries describe Data Whisperer as using the target LLM's few-shot in-context behavior to score data samples, then applying context-aware weighting based on attention signals to reduce order sensitivity. Reported claims include using 10% of GSM8K data to outperform the full GSM8K dataset on Llama-3-8B-Instruct, a 3.1-point improvement over existing methods, and 7.4x speedup.

For [[Sentence Pruning Dataset]] work, the key appeal is that a training-free selection method may be usable before investing in adapter training. Candidate pruning examples could be scored against a small set of gold pruning demonstrations.

> ⚠️ Source issue: `raw/INDEX.md` maps Data Whisperer to `https://arxiv.org/abs/2503.09622`, but that arXiv page is a quadrotor control paper, not Data Whisperer. Treat this source identifier as incorrect until fixed; use ACL Anthology or the correct paper URL when available.

## Related

- [[Data-Efficient Instruction Tuning]]
- [[Targeted Data Selection]]
- [[Quality Over Quantity]]

## Sources

- `raw/data_whisperer_fewshot_data_selection_2503.09622.pdf` (local filename; identifier needs verification).
- Web search summary for “Data Whisperer: Efficient Data Selection for Task-Specific LLM Fine-Tuning via Few-Shot In-Context Learning,” ACL 2025.
