"""Reasoning-pruning data-generation flow for the reasoning-pruning-data-gen repo.

This module owns config loading, task loading, reasoning segmentation, strict reasoning-pruning
decision validation, iterative context updates, and compact accepted JSONL row
assembly. The CLI supplies paths/storage; tests inject a fake call_fn only at the
Python boundary so the runnable system still uses real LiteLLM calls.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from llm_client import DEFAULT_MODEL, LLMConfig, call_llm

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    import tomli as tomllib  # type: ignore


FORMAT_VERSION = "1.0"
BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")
FINAL_RE = re.compile(r"final answer\s*:\s*([^\r\n]+)", re.I)
SECRET_VALUE_RE = re.compile(r"(?i)(api[_-]?key|token|secret|password|authorization|bearer)\s*[:=]\s*[^\s,;]+")
BEARER_VALUE_RE = re.compile(r"(?i)\bbearer\s+[^\s,;]+")
LONG_SECRET_RE = re.compile(r"\b[A-Za-z0-9_\-]{32,}\b")


@dataclass(frozen=True)
class Task:
    id: str
    prompt: str
    source: str = "seed"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Unit:
    id: str
    index: int
    text: str


@dataclass(frozen=True)
class SourceConfig:
    source: str = "seed"
    limit: int | None = 1
    hf_dataset: str | None = None
    hf_config: str | None = None
    hf_split: str = "train"
    hf_text_field: str | None = None
    answer_fields: tuple[str, ...] = ("Answer", "answer", "target")


@dataclass(frozen=True)
class OutputConfig:
    accepted_path: str = "outputs/datasets/seed_dev.jsonl"
    rejected_path: str | None = "outputs/datasets/seed_dev.rejected.jsonl"
    hf_upload_repo: str | None = None
    hf_upload_path: str | None = None
    hf_private: bool = False


@dataclass(frozen=True)
class IterationConfig:
    max_depth: int = 1
    min_generated_units: int = 3
    max_removable_span_length: int = 1
    stop_statuses: tuple[str, ...] = ("no_prune", "stop")


@dataclass(frozen=True)
class QualityConfig:
    require_final_answer_preservation: bool = False
    reject_obvious_incoherence: bool = True


@dataclass(frozen=True)
class PromptConfig:
    generation_system: str
    generation_user_template: str
    continuation_user_template: str
    decision_system: str
    decision_user_template: str


@dataclass(frozen=True)
class PruningConfig:
    path: str
    run_name: str
    format_version: str
    random_seed: int | None
    source: SourceConfig
    output: OutputConfig
    generation: LLMConfig
    decision: LLMConfig
    iteration: IterationConfig
    quality: QualityConfig
    prompts: PromptConfig


@dataclass(frozen=True)
class PruningDecision:
    status: str
    remove_unit_ids: list[str]
    rationale: str


@dataclass(frozen=True)
class SpanValidation:
    accepted: bool
    reason: str | None = None
    removed_units: list[Unit] = field(default_factory=list)
    prefix_units: list[Unit] = field(default_factory=list)
    next_unit: Unit | None = None


@dataclass(frozen=True)
class VerificationResult:
    passed: bool
    reasons: list[str]
    checks: dict[str, bool]


@dataclass(frozen=True)
class AcceptedTransition:
    row: dict[str, Any]
    pruned_context_after_decision: str


CallLLM = Callable[..., str]


SEED_TASKS = [
    Task("seed-arithmetic-1", "If a train travels 45 miles in 1.5 hours, what is its average speed in miles per hour?", metadata={"answer": "30", "kind": "arithmetic"}),
    Task("seed-word-1", "Maya has 12 marbles. She gives 3 to Leo and buys 8 more. How many marbles does she have now?", metadata={"answer": "17", "kind": "word_problem"}),
    Task("seed-logic-1", "All bloops are razzies. All razzies are lazzies. Is every bloop definitely a lazzie?", metadata={"answer": "yes", "kind": "logic"}),
    Task("seed-arithmetic-2", "A recipe uses 2 cups of flour for 8 cookies. How many cups are needed for 20 cookies?", metadata={"answer": "5", "kind": "ratio"}),
    Task("seed-word-2", "There are 24 students split equally into 4 teams. Two students leave each team. How many students remain total?", metadata={"answer": "16", "kind": "word_problem"}),
    Task("seed-logic-2", "If the red box is heavier than the blue box and the blue box is heavier than the green box, which box is lightest?", metadata={"answer": "green", "kind": "logic"}),
]


def load_pruning_config(path: str | Path) -> PruningConfig:
    config_path = Path(path)
    with config_path.open("rb") as handle:
        data = tomllib.load(handle)

    prompts = data.get("prompts", {})
    required_prompt_keys = ["generation_system", "generation_user_template", "continuation_user_template", "decision_system", "decision_user_template"]
    missing = [key for key in required_prompt_keys if not isinstance(prompts.get(key), str) or not prompts[key].strip()]
    if missing:
        raise ValueError(f"config missing prompt strings: {', '.join(missing)}")
    _require_placeholders(prompts["generation_user_template"], ["{task_prompt}", "{answer_hint}"], "generation_user_template")
    _require_placeholders(prompts["continuation_user_template"], ["{task_prompt}", "{current_context}", "{answer_hint}"], "continuation_user_template")
    _require_placeholders(prompts["decision_user_template"], ["{task_prompt}", "{current_context}", "{generation}", "{unit_lines}", "{max_span_length}"], "decision_user_template")

    source = data.get("source", {})
    output = data.get("output", {})
    generation = data.get("generation", {})
    decision = data.get("decision", {})
    iteration = data.get("iteration", {})
    quality = data.get("quality", {})
    run = data.get("run", {})

    return PruningConfig(
        path=str(config_path),
        run_name=str(run.get("run_name", "seed-dev")),
        format_version=str(run.get("format_version", FORMAT_VERSION)),
        random_seed=run.get("random_seed"),
        source=SourceConfig(
            source=str(source.get("source", "seed")),
            limit=source.get("limit", 1),
            hf_dataset=_optional_str(source.get("hf_dataset")),
            hf_config=_optional_str(source.get("hf_config")),
            hf_split=str(source.get("hf_split", "train")),
            hf_text_field=_optional_str(source.get("hf_text_field")),
            answer_fields=tuple(str(field_name) for field_name in source.get("answer_fields", ["Answer", "answer", "target"])),
        ),
        output=OutputConfig(
            accepted_path=str(output.get("accepted_path", "outputs/datasets/seed_dev.jsonl")),
            rejected_path=_optional_str(output.get("rejected_path")),
            hf_upload_repo=_optional_str(output.get("hf_upload_repo")),
            hf_upload_path=_optional_str(output.get("hf_upload_path")),
            hf_private=bool(output.get("hf_private", False)),
        ),
        generation=_model_config(generation, default_temperature=0.2),
        decision=_model_config(decision, default_temperature=0.0),
        iteration=IterationConfig(
            max_depth=int(iteration.get("max_depth", 1)),
            min_generated_units=int(iteration.get("min_generated_units", 3)),
            max_removable_span_length=int(iteration.get("max_removable_span_length", 1)),
            stop_statuses=tuple(iteration.get("stop_statuses", ["no_prune", "stop"])),
        ),
        quality=QualityConfig(
            require_final_answer_preservation=bool(quality.get("require_final_answer_preservation", False)),
            reject_obvious_incoherence=bool(quality.get("reject_obvious_incoherence", True)),
        ),
        prompts=PromptConfig(
            generation_system=prompts["generation_system"].strip(),
            generation_user_template=prompts["generation_user_template"].strip(),
            continuation_user_template=prompts["continuation_user_template"].strip(),
            decision_system=prompts["decision_system"].strip(),
            decision_user_template=prompts["decision_user_template"].strip(),
        ),
    )


def _model_config(data: dict[str, Any], *, default_temperature: float) -> LLMConfig:
    return LLMConfig(
        provider=str(data.get("provider", "gemini")),
        model=str(data.get("model", DEFAULT_MODEL)),
        base_url=_optional_str(data.get("base_url")),
        temperature=float(data.get("temperature", default_temperature)),
        max_tokens=data.get("max_tokens"),
        timeout=data.get("timeout"),
        retries=int(data.get("retries", 0)),
        model_revision=_optional_str(data.get("model_revision")),
        dtype=_optional_str(data.get("dtype")),
        device_map=_optional_str(data.get("device_map")),
        top_p=float(data["top_p"]) if data.get("top_p") is not None else None,
        transformers_loader=str(data.get("transformers_loader", "auto_model_for_image_text_to_text")),
    )


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _require_placeholders(template: str, placeholders: list[str], name: str) -> None:
    missing = [placeholder for placeholder in placeholders if placeholder not in template]
    if missing:
        raise ValueError(f"{name} must include placeholders: {', '.join(missing)}")


def load_tasks(config: SourceConfig) -> list[Task]:
    if config.source == "seed":
        return load_seed_tasks(config.limit)
    if config.source == "hf":
        return load_hf_tasks(config.hf_dataset, config.hf_config, config.hf_split, config.hf_text_field, config.limit, config.answer_fields)
    raise ValueError("source must be 'seed' or 'hf'.")


def load_seed_tasks(limit: int | None) -> list[Task]:
    return SEED_TASKS[:limit] if limit is not None else list(SEED_TASKS)


def load_hf_tasks(dataset_name: str | None, config: str | None, split: str, text_field: str | None, limit: int | None, answer_fields: tuple[str, ...] = ("Answer", "answer", "target")) -> list[Task]:
    if not dataset_name or not text_field:
        raise ValueError("Hugging Face source requires hf_dataset and hf_text_field in config.")
    try:
        from datasets import load_dataset  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Hugging Face loading requires the optional extra: uv run --extra hf ...") from exc

    dataset = load_dataset(dataset_name, config, split=split) if config else load_dataset(dataset_name, split=split)
    rows = dataset.select(range(min(limit, len(dataset)))) if limit is not None else dataset
    tasks: list[Task] = []
    for index, row in enumerate(rows):
        prompt = str(row[text_field]).strip()
        if prompt:
            metadata = hf_task_metadata(row, dataset_name, config, split, index, answer_fields)
            tasks.append(Task(f"hf-{dataset_name}-{index}", prompt, "hf", metadata))
    return tasks


def hf_task_metadata(row: dict[str, Any], dataset_name: str, config: str | None, split: str, row_index: int, answer_fields: tuple[str, ...]) -> dict[str, Any]:
    metadata: dict[str, Any] = {"dataset": dataset_name, "config": config, "split": split, "row_index": row_index}
    for field_name in answer_fields:
        if field_name in row and is_small_scalar(row[field_name]):
            metadata[field_name] = row[field_name]
    return metadata


def is_small_scalar(value: Any) -> bool:
    if value is None:
        return True
    if not isinstance(value, (str, int, float, bool)):
        return False
    return len(str(value)) <= 500


def answer_hint_for_task(task: Task) -> str:
    return f"\nKnown final answer: {task.metadata['answer']}" if "answer" in task.metadata else ""


def generate_reasoning(task: Task, current_context: str, depth: int, config: PruningConfig, call_fn: CallLLM = call_llm) -> str:
    if depth == 1:
        prompt = config.prompts.generation_user_template.format(task_prompt=task.prompt, answer_hint=answer_hint_for_task(task))
    else:
        prompt = config.prompts.continuation_user_template.format(task_prompt=task.prompt, current_context=current_context, answer_hint=answer_hint_for_task(task))
    return call_fn(prompt, config.generation, system=config.prompts.generation_system)


def split_units(text: str) -> list[Unit]:
    chunks: list[str] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if re.match(r"^\s*(?:[-*•]|\d+[.)])\s+", line):
            chunks.append(line.strip())
        else:
            chunks.extend(part.strip() for part in BOUNDARY_RE.split(line.strip()) if part.strip())
    return [Unit(f"u{index:03d}", index, chunk) for index, chunk in enumerate(chunks)]


def choose_first_removable_span(task: Task, current_context: str, generation: str, units: list[Unit], config: PruningConfig, call_fn: CallLLM = call_llm) -> PruningDecision:
    unit_lines = "\n".join(f"{unit.id}: {unit.text}" for unit in units)
    prompt = config.prompts.decision_user_template.format(
        task_prompt=task.prompt,
        answer_hint=answer_hint_for_task(task),
        current_context=current_context,
        generation=generation,
        unit_lines=unit_lines,
        max_span_length=config.iteration.max_removable_span_length,
    )
    raw = call_fn(prompt, config.decision, system=config.prompts.decision_system, response_format={"type": "json_object"})
    parsed = json.loads(raw)
    status = parsed.get("status")
    if status not in {"remove", "no_prune", "stop"}:
        raise ValueError("decision status must be remove, no_prune, or stop")
    ids = parsed.get("remove_unit_ids", [])
    if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
        raise ValueError("remove_unit_ids must be a list of strings")
    return PruningDecision(status=status, remove_unit_ids=ids, rationale=str(parsed.get("rationale", parsed.get("explanation", ""))))


def validate_removable_span(units: list[Unit], decision: PruningDecision, config: PruningConfig) -> SpanValidation:
    if decision.status != "remove":
        return SpanValidation(False, decision.status)
    if not decision.remove_unit_ids:
        return SpanValidation(False, "empty_span")
    by_id = {unit.id: unit for unit in units}
    if any(unit_id not in by_id for unit_id in decision.remove_unit_ids):
        return SpanValidation(False, "unknown_unit_id")
    removed = [by_id[unit_id] for unit_id in decision.remove_unit_ids]
    indexes = sorted(unit.index for unit in removed)
    if len(indexes) != len(set(indexes)):
        return SpanValidation(False, "duplicate_unit_id")
    if indexes != list(range(indexes[0], indexes[-1] + 1)):
        return SpanValidation(False, "non_contiguous_span")
    if len(indexes) > config.iteration.max_removable_span_length:
        return SpanValidation(False, "span_too_long")
    if len(indexes) >= len(units):
        return SpanValidation(False, "removes_all_units")
    next_index = indexes[-1] + 1
    if next_index >= len(units):
        return SpanValidation(False, "no_next_kept_unit")
    next_unit = units[next_index]
    prefix = [unit for unit in units if unit.index < indexes[0]]
    removed_ordered = [unit for unit in units if unit.index in indexes]
    return SpanValidation(True, removed_units=removed_ordered, prefix_units=prefix, next_unit=next_unit)


def build_input_x(task: Task, current_context: str, prefix_units: list[Unit]) -> str:
    parts = [current_context.strip(), *(unit.text for unit in prefix_units)]
    return "\n".join(part for part in parts if part).strip()


def build_pruned_context(current_context: str, prefix_units: list[Unit], next_unit: Unit) -> str:
    parts = [current_context.strip(), *(unit.text for unit in prefix_units), next_unit.text]
    return "\n".join(part for part in parts if part).strip()


def verify_transition(generation: str, input_x: str, target_y: str, units: list[Unit], span: SpanValidation, config: PruningConfig) -> VerificationResult:
    checks = {
        "input_x_non_empty": bool(input_x.strip()),
        "target_y_non_empty": bool(target_y.strip()),
        "removed_some_not_all": 0 < len(span.removed_units) < len(units),
        "has_next_target": span.next_unit is not None,
        "final_answer_preserved_when_required": True,
        "has_no_obvious_incoherence": True,
    }
    if config.quality.require_final_answer_preservation:
        checks["final_answer_preserved_when_required"] = final_answer(generation) is None or final_answer(generation) == final_answer(reconstruct_generation_after_skip(units, span.removed_units))
    if config.quality.reject_obvious_incoherence:
        checks["has_no_obvious_incoherence"] = not has_obvious_incoherence(input_x + "\n" + target_y)
    return VerificationResult(all(checks.values()), [name for name, passed in checks.items() if not passed], checks)


def reconstruct_generation_after_skip(units: list[Unit], removed_units: list[Unit]) -> str:
    removed = {unit.id for unit in removed_units}
    return " ".join(unit.text for unit in units if unit.id not in removed).strip()


def final_answer(text: str) -> str | None:
    match = FINAL_RE.search(text)
    if not match:
        return None
    answer = re.sub(r"\s+", " ", match.group(1).strip().lower())
    return strip_terminal_sentence_punctuation(answer)


def strip_terminal_sentence_punctuation(answer: str) -> str:
    while answer.endswith(("!", "?")):
        answer = answer[:-1].rstrip()
    if answer.endswith("."):
        answer = answer[:-1].rstrip()
    return answer


def has_obvious_incoherence(text: str) -> bool:
    lowered = text.lower()
    return any(fragment in lowered for fragment in ["therefore therefore", "because because", "..", "?."])


def decision_reference(config: PruningConfig) -> dict[str, str]:
    return {
        "config": config.path,
        "commit": decision_config_revision(config),
    }


def decision_config_revision(config: PruningConfig) -> str:
    payload = {
        "decision": asdict(config.decision),
        "decision_system": config.prompts.decision_system,
        "decision_user_template": config.prompts.decision_user_template,
        "iteration": asdict(config.iteration),
        "quality": asdict(config.quality),
        "format_version": config.format_version,
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def reject_record(task: Task, depth: int, reason: str, current_context: str, generation: str = "", decision: PruningDecision | None = None, error: Exception | None = None) -> dict[str, Any]:
    record = {
        "source_question": task.prompt,
        "task_id": task.id,
        "source": task.source,
        "depth": depth,
        "reason": reason,
        "current_context": current_context,
        "generation": generation,
        "decision": asdict(decision) if decision else None,
    }
    if error is not None:
        record["error_category"] = error.__class__.__name__
        record["error_message"] = sanitize_error_message(str(error))
    return record


def sanitize_error_message(message: str, limit: int = 300) -> str:
    scrubbed = SECRET_VALUE_RE.sub(lambda match: f"{match.group(1)}=[REDACTED]", message)
    scrubbed = BEARER_VALUE_RE.sub("Bearer [REDACTED]", scrubbed)
    scrubbed = LONG_SECRET_RE.sub("[REDACTED]", scrubbed)
    scrubbed = re.sub(r"\s+", " ", scrubbed).strip()
    if len(scrubbed) > limit:
        return scrubbed[: limit - 3].rstrip() + "..."
    return scrubbed


def build_accepted_transition(task: Task, depth: int, current_context: str, span: SpanValidation, config: PruningConfig) -> AcceptedTransition:
    assert span.next_unit is not None
    input_x = build_input_x(task, current_context, span.prefix_units)
    pruned_context = build_pruned_context(current_context, span.prefix_units, span.next_unit)
    row = {
        "id": f"{config.run_name}/{task.id}/{depth}",
        "question": task.prompt,
        "input_x": input_x,
        "target_y": span.next_unit.text,
        "depth": depth,
        "decision": decision_reference(config),
    }
    return AcceptedTransition(row=row, pruned_context_after_decision=pruned_context)


def run_pipeline(tasks: list[Task], config: PruningConfig, call_fn: CallLLM = call_llm) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for task in tasks:
        current_context = task.prompt
        for depth in range(1, config.iteration.max_depth + 1):
            try:
                generation = generate_reasoning(task, current_context, depth, config, call_fn)
            except Exception as exc:
                rejected.append(reject_record(task, depth, f"generation_error:{exc.__class__.__name__}", current_context, error=exc))
                break

            units = split_units(generation)
            if len(units) < config.iteration.min_generated_units:
                rejected.append(reject_record(task, depth, "too_few_units", current_context, generation))
                break

            try:
                decision = choose_first_removable_span(task, current_context, generation, units, config, call_fn)
            except Exception as exc:
                rejected.append(reject_record(task, depth, f"decision_error:{exc.__class__.__name__}", current_context, generation, error=exc))
                break

            if decision.status in config.iteration.stop_statuses:
                break

            span = validate_removable_span(units, decision, config)
            if not span.accepted:
                rejected.append(reject_record(task, depth, span.reason or "invalid_span", current_context, generation, decision))
                break

            assert span.next_unit is not None
            input_x = build_input_x(task, current_context, span.prefix_units)
            verification = verify_transition(generation, input_x, span.next_unit.text, units, span, config)
            if not verification.passed:
                rejected.append(reject_record(task, depth, ";".join(verification.reasons), current_context, generation, decision))
                break

            transition = build_accepted_transition(task, depth, current_context, span, config)
            accepted.append(transition.row)
            current_context = transition.pruned_context_after_decision

    return accepted, rejected
