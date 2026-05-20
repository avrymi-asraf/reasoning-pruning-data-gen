# Quality Over Quantity

## Summary

[[Quality Over Quantity]] is the working principle that a small, carefully verified training set can be more useful than a large noisy one, especially for focused model behavior changes such as [[Sentence Pruning Dataset]] construction.

## Details

The evidence base points in the same direction from multiple angles. [[Curated SFT Data]] shows that alignment behavior can be learned from small high-quality sets. [[LESS]], [[DELIFT]], and [[Data Whisperer]] all propose selecting useful subsets instead of training on all available examples. This aligns with the project's need to avoid teaching harmful over-shortening or incoherent reasoning.

For sentence pruning, this means rejected or uncertain pruning decisions should not be kept as weak training data. The first dataset versions should be small, inspectable, and evaluation-linked. Scaling should happen after the decision and verification components show precision.

## Related

- [[Sentence Pruning Dataset]]
- [[Curated SFT Data]]
- [[Data-Efficient Instruction Tuning]]
- [[Targeted Data Selection]]

## Sources

- `raw/INDEX.md` project implication.
- Zhou et al., LIMA abstract: https://arxiv.org/abs/2305.11206
- Xia et al., LESS abstract: https://arxiv.org/abs/2402.04333
- Agarwal et al., DELIFT abstract: https://arxiv.org/abs/2411.04425
