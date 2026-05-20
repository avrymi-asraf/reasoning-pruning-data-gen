# LoRA

## Summary

[[LoRA]] is a parameter-efficient fine-tuning method that trains low-rank adapter updates instead of updating all model weights. It is the project's likely first training baseline for small focused experiments.

## Details

LoRA is attractive for [[Sentence Pruning Dataset]] training because it reduces GPU memory and makes repeated experiments cheaper. The training repo skill recommends LoRA-first runs with low learning rates, few steps or epochs, modest adapter ranks, and prompt masking so only `pruned_response` tokens contribute to loss.

The limitation is that LoRA can lag full fine-tuning on complex tasks such as mathematical reasoning and code generation. [[DoRA]] and [[SeedLoRA]] are relevant follow-ups if simple LoRA underperforms.

## Related

- [[DoRA]]
- [[SeedLoRA]]
- [[Curated SFT Data]]

## Sources

- Training repo skill `fine-tuning-poc`.
- Liu et al., SeedLoRA abstract: https://proceedings.mlr.press/v267/liu25o.html
- Liu et al., DoRA abstract: https://arxiv.org/abs/2402.09353
