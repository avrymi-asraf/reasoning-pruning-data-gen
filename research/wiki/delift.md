# DELIFT

## Summary

[[DELIFT]] is a [[Data-Efficient Instruction Tuning]] method that selects useful and diverse subsets of fine-tuning data using pairwise utility metrics and submodular functions.

## Details

DELIFT targets three fine-tuning stages: instruction tuning, task-specific fine-tuning, and continual fine-tuning. Instead of relying on expensive gradient calculations, it estimates how beneficial one data sample is for improving model responses to other samples. The paper reports up to 70% data reduction without compromising performance across tasks and model scales.

For [[Sentence Pruning Dataset]] work, DELIFT is relevant because the project will likely need multiple data versions and continual additions. Utility-based subset selection could help decide which newly generated pruning examples are worth adding to the next dataset version.

## Related

- [[Data-Efficient Instruction Tuning]]
- [[Quality Over Quantity]]
- [[Targeted Data Selection]]

## Sources

- Agarwal et al., “DELIFT: Data Efficient Language model Instruction Fine Tuning”: https://arxiv.org/abs/2411.04425
- `raw/delift_data_efficient_instruction_finetuning_2411.04425.pdf`
