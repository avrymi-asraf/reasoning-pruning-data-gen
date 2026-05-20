# Sentence Pruning Dataset

## Summary

The [[Sentence Pruning Dataset]] is the Data repo's core artifact: compact pruning-transition examples that teach a model to continue from a useful reasoning prefix directly to the next useful step after a skipped span. It is meant to train efficient local continuation behavior, not to store full verbose-output-to-short-output rewrite pairs.

## Details

The project plan defines a loop: generate reasoning with generator `G`, segment it into sentences or reasoning steps, ask decision model `D` for the first safely removable contiguous span, save `input_x = question + useful prefix` and `target_y = next useful step after the skipped span`, then feed the pruned context back into `G` for deeper pruning transitions.

Accepted JSONL rows should stay compact:

- `id`
- `question`
- `input_x`
- `target_y`
- `depth`
- `decision` with `config` and `commit`/revision reference

Heavy provenance should live at the dataset/manifest or private audit level rather than inside every accepted training row. This includes source dataset revision, generator model revision, decision model and prompt/config revision, prompt text or path, pruning config, run counts, and rejected/audit details.

Because the data is expensive and sensitive, the repo should prefer [[Quality Over Quantity]] and use eval-driven acceptance rather than maximizing volume.

## Related

- [[Quality Over Quantity]]
- [[Curated SFT Data]]
- [[Targeted Data Selection]]
- [[Data-Efficient Instruction Tuning]]

## Sources

- `/home/avreymi/code/sentence-pruning/sentence-pruning-evaluate/docs/plan.md` sections 1, 4.1-4.3, 6.
- `/home/avreymi/code/reasoning-pruning/reasoning-pruning-data-gen/docs/plan.md` JSON Schema and reasoning-pruning-data-gen sections.
- `raw/INDEX.md` project implication.
