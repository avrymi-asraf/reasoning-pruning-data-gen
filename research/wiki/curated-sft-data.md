# Curated SFT Data

## Summary

[[Curated SFT Data]] is supervised fine-tuning data selected for high quality and behavioral coverage rather than raw size. It supports the idea that a small number of excellent examples can teach response style and task format.

## Details

LIMA fine-tuned a 65B LLaMA model with standard supervised loss on only 1,000 carefully curated prompts and responses, without RLHF or human preference modeling, and reported strong instruction-following performance. Its central implication for this project is not that 1,000 examples is always sufficient, but that high-quality examples can strongly shape model behavior when the base model already contains broad knowledge.

For [[Sentence Pruning Dataset]] creation, curated SFT means the `pruned_response` should be treated as the training target only after verification. The `original_response` is useful for provenance and analysis, not as the target behavior.

## Related

- [[Quality Over Quantity]]
- [[Sentence Pruning Dataset]]
- [[Data-Efficient Instruction Tuning]]

## Sources

- Zhou et al., LIMA abstract: https://arxiv.org/abs/2305.11206
- Training repo skill `fine-tuning-poc`, dataset contract.
