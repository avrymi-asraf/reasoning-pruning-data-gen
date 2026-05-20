# Targeted Data Selection

## Summary

[[Targeted Data Selection]] chooses training examples for a specific desired capability rather than general instruction-following quality. For this project, the target capability is efficient, correct reasoning through [[Sentence Pruning Dataset]] examples.

## Details

[[LESS]] explicitly frames this setting as targeted instruction tuning: real applications may need a specialized skill such as reasoning, so selected data should embody that capability. The selected data can be based on few target examples and, in LESS, can transfer across model sizes and families.

For sentence pruning, target examples should include cases where removed units are genuinely redundant, pruned outputs remain coherent, and correctness is verifiable. Negative or borderline examples should be kept for evaluation or prompt debugging, not automatically mixed into SFT.

## Related

- [[LESS]]
- [[Data-Efficient Instruction Tuning]]
- [[Quality Over Quantity]]
- [[Sentence Pruning Dataset]]

## Sources

- Xia et al., LESS abstract: https://arxiv.org/abs/2402.04333
- `/home/avreymi/code/sentence-pruning/sentence-pruning-evaluate/docs/plan.md` sections 4.2 and 6.
