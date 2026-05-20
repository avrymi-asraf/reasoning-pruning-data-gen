# DoRA

## Summary

[[DoRA]] is a parameter-efficient fine-tuning method that decomposes pretrained weights into magnitude and direction, then applies LoRA-style low-rank updates to the directional component.

## Details

The DoRA paper argues that standard [[LoRA]] can have an accuracy gap versus full fine-tuning. By separating magnitude and direction, DoRA aims to improve learning capacity and training stability while avoiding additional inference overhead. Reported applications include LLaMA, LLaVA, and VL-BART tasks such as commonsense reasoning and visual instruction tuning.

For [[Sentence Pruning Dataset]] training, DoRA is a second-line method if baseline LoRA is unstable or fails to learn pruning behavior from small data.

## Related

- [[LoRA]]
- [[SeedLoRA]]
- [[Data-Efficient Instruction Tuning]]

## Sources

- Liu et al., “DoRA: Weight-Decomposed Low-Rank Adaptation,” ICML 2024: https://arxiv.org/abs/2402.09353
- `raw/dora_weight_decomposed_lora_2402.09353.pdf`
