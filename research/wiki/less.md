# LESS

## Summary

[[LESS]] is an optimizer-aware method for [[Targeted Data Selection]] in instruction tuning. It estimates data influence through low-rank gradient similarity to a few examples representing the desired target capability.

## Details

LESS stands for Low-rank gradiEnt Similarity Search. It builds a reusable gradient datastore with low-dimensional gradient features, adapts influence-style selection to Adam and variable-length instruction data, and selects examples similar to target examples. The paper reports that training on a selected 5% of data can often outperform training on the full dataset, and that selection can transfer across model sizes and families.

For [[Sentence Pruning Dataset]] work, LESS suggests a later-stage selection method once there are seed examples of good pruning behavior. A practical near-term approximation is to manually define high-quality target exemplars and select/generated examples most similar in pruning rationale, correctness preservation, and reasoning type.

## Related

- [[Targeted Data Selection]]
- [[Data-Efficient Instruction Tuning]]
- [[Quality Over Quantity]]

## Sources

- Xia et al., “LESS: Selecting Influential Data for Targeted Instruction Tuning,” ICML 2024: https://arxiv.org/abs/2402.04333
- `raw/less_targeted_instruction_tuning_2402.04333.pdf`
