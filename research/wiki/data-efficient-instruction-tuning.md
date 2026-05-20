# Data-Efficient Instruction Tuning

## Summary

[[Data-Efficient Instruction Tuning]] studies how to fine-tune language models with less data by selecting, curating, or weighting examples so that redundant or low-utility samples are excluded.

## Details

The main pattern is that not all instruction examples contribute equally. [[LESS]] selects examples whose low-rank gradient features are similar to target capability examples. [[DELIFT]] uses pairwise utility and submodular selection to choose useful, diverse subsets across several fine-tuning stages. [[Data Whisperer]] attempts a training-free route using few-shot in-context behavior and attention-derived weights.

For [[Sentence Pruning Dataset]] work, data-efficient instruction tuning suggests two design choices: create verified examples first, then select subsets that best represent the desired pruning behavior; do not assume every generated candidate should enter the training set.

## Related

- [[Quality Over Quantity]]
- [[Targeted Data Selection]]
- [[LESS]]
- [[DELIFT]]
- [[Data Whisperer]]

## Sources

- `raw/INDEX.md`.
- Xia et al., LESS abstract: https://arxiv.org/abs/2402.04333
- Agarwal et al., DELIFT abstract: https://arxiv.org/abs/2411.04425
- Data Whisperer web search summary and source pointers.
