# Research Wiki Schema

This folder follows the LLM Wiki pattern: `raw/` contains immutable source documents, while `wiki/` contains synthesized, interlinked markdown pages that compound over time.

## Page Rules

- One concept per page, Wikipedia style.
- Use Obsidian-style `[[wiki-links]]` for cross-references.
- Flag contradictions or source problems inline with `> ⚠️`.
- Filenames are kebab-case and match the concept name.
- Every page must include `Summary`, `Details`, `Related`, and `Sources` sections.
- Always update `wiki/index.md` and append to `wiki/log.md` after ingest/query/lint operations.

## Operations

### Ingest

Read new files in `raw/`, extract stable concepts, create or update relevant pages in `wiki/`, update `wiki/index.md`, and append `[INGEST]` to `wiki/log.md`.

### Query

Answer using only `wiki/` pages. If the answer is useful and non-trivial, save it as a wiki page, update `wiki/index.md`, and append `[QUERY]` to `wiki/log.md`.

### Lint

Audit for stale claims, contradictions, orphaned pages, missing cross-links, or oversized pages. Fix in place and append `[LINT]` to `wiki/log.md`.
