# SeedLoRA

## Summary

[[SeedLoRA]] is a LoRA fusion approach that trains multiple same-task LoRA adapters with different random seeds and combines their complementary strengths.

## Details

SeedLoRA addresses the observation that [[LoRA]] can underperform full fine-tuning on complex tasks such as mathematical reasoning and code generation. Instead of fusing adapters trained on different tasks, it fuses adapters trained on the same task with different random seeds. The ICML 2025 abstract reports that this improves over standalone LoRA and narrows the gap to full fine-tuning.

For [[Sentence Pruning Dataset]] training, SeedLoRA is useful if single-adapter results vary strongly by seed. It is probably not the first POC step because it requires multiple training runs, but it is a good robustness option after a working LoRA baseline exists.

## Related

- [[LoRA]]
- [[DoRA]]
- [[Quality Over Quantity]]

## Sources

- Liu et al., “SeedLoRA: A Fusion Approach to Efficient LLM Fine-Tuning,” ICML 2025: https://proceedings.mlr.press/v267/liu25o.html
- `raw/seedlora_efficient_llm_finetuning_liu25o.pdf`
