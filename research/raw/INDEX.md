# Raw Research Index: Few-Sample Fine-Tuning

Created: 2026-05-18

This folder contains downloaded source papers for research on fine-tuning with few samples, data-efficient instruction tuning, and parameter-efficient fine-tuning.

## Papers

| File | Title | Year / Venue | Source | Why it matters |
|---|---|---:|---|---|
| `lima_less_is_more_for_alignment_2305.11206.pdf` | LIMA: Less Is More for Alignment | 2023 | https://arxiv.org/abs/2305.11206 | Shows strong alignment from only 1,000 carefully curated examples; key evidence for quality-over-quantity SFT. |
| `less_targeted_instruction_tuning_2402.04333.pdf` | LESS: Selecting Influential Data for Targeted Instruction Tuning | 2024 / ICML | https://arxiv.org/abs/2402.04333 | Selects influential instruction data for target capabilities; reports 5% selected data can outperform full data. |
| `delift_data_efficient_instruction_finetuning_2411.04425.pdf` | DELIFT: Data Efficient Language model Instruction Fine Tuning | 2024/2025 | https://arxiv.org/abs/2411.04425 | Uses efficient utility-based data selection; reports up to 70% data reduction without performance loss. |
| `data_whisperer_fewshot_data_selection_2503.09622.pdf` | Data Whisperer | 2025 / ACL | Source URL needs verification; `https://arxiv.org/abs/2503.09622` is a quadrotor-control paper, not Data Whisperer. | Training-free, attention/few-shot based data selection; useful for selecting a small fine-tuning subset. |
| `dora_weight_decomposed_lora_2402.09353.pdf` | DoRA: Weight-Decomposed Low-Rank Adaptation | 2024 / ICML | https://arxiv.org/abs/2402.09353 | PEFT method improving LoRA by decomposing weights into magnitude and direction; useful when small-data LoRA underperforms. |
| `seedlora_efficient_llm_finetuning_liu25o.pdf` | SeedLoRA: A Fusion Approach to Efficient LLM Fine-Tuning | 2025 / ICML | https://proceedings.mlr.press/v267/liu25o.html | Fuses same-task LoRA adapters trained with different seeds; relevant for reasoning/code tasks where LoRA variance matters. |

## Project implication

For sentence-pruning data, start with a small, high-quality, verified dataset before scaling. Use evals and selection methods to choose examples that best represent the target pruning skill instead of training on all generated candidates.
