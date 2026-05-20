# Sentence Pruning Dataset

## Summary

The [[Sentence Pruning Dataset]] is the Data repo's core artifact: examples where a model-generated response is shortened by removing redundant reasoning units while preserving correctness, completeness, and coherence. It is meant to train models to produce efficient reasoning rather than merely shorter answers.

## Details

The project plan defines a loop: generate an answer, segment it into sentences or reasoning steps, decide which units can be removed, verify the pruned answer, and save only high-quality examples. Later iterations may feed the pruned sequence back into the model and prune new continuations.

The dataset should preserve provenance:

- original prompt
- original response
- pruned response
- removed unit identifiers
- decision rationale
- verification outcome
- pruning depth or iteration metadata

Because the data is expensive and sensitive, the repo should prefer [[Quality Over Quantity]] and use eval-driven acceptance rather than maximizing volume.

## Related

- [[Quality Over Quantity]]
- [[Curated SFT Data]]
- [[Targeted Data Selection]]
- [[Data-Efficient Instruction Tuning]]

## Sources

- `/home/avreymi/code/sentence-pruning/sentence-pruning-evaluate/docs/plan.md` sections 1, 4.1-4.3, 6.
- `raw/INDEX.md` project implication.
