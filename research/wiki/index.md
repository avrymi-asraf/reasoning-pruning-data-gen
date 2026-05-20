# Research Wiki Index

## Project Concepts

- [[Sentence Pruning Dataset]] — project-specific dataset-generation objective and quality criteria.
- [[Quality Over Quantity]] — working principle for small, verified training corpora.

## Data Selection and Efficient Fine-Tuning

- [[Data-Efficient Instruction Tuning]] — umbrella concept for reducing SFT data volume without losing capability.
- [[Targeted Data Selection]] — selecting examples for a specific downstream capability.
- [[Curated SFT Data]] — hand- or model-curated supervised examples for alignment and behavior shaping.
- [[LESS]] — optimizer-aware gradient-similarity data selection.
- [[DELIFT]] — utility/submodular data selection across instruction, task, and continual fine-tuning.
- [[Data Whisperer]] — training-free few-shot/attention-based data selection.

## Parameter-Efficient Fine-Tuning

- [[LoRA]] — low-rank adapter baseline for small focused fine-tuning.
- [[DoRA]] — weight-decomposed LoRA variant improving stability/capacity.
- [[SeedLoRA]] — fusing same-task LoRA adapters trained with different seeds.

## Source Status

- Raw PDFs and source index live in `raw/`.
- First ingest used source abstracts, project plan, and `raw/INDEX.md`; full PDF extraction should be added later for deeper paper-specific pages.
