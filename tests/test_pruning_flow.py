"""No-network tests for the reasoning-pruning flow."""

from __future__ import annotations

import json
import sys
import types
from argparse import Namespace
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import pruning_flow  # noqa: E402
import create_pruning_dataset  # noqa: E402
import llm_client  # noqa: E402
from llm_client import DEFAULT_MODEL, LLMConfig  # noqa: E402


def write_config(tmp_path: Path, *, max_depth: int = 1, max_span: int = 2) -> Path:
    path = tmp_path / "default.toml"
    path.write_text(
        f'''
[run]
run_name = "test-run"
format_version = "1.0"

[source]
source = "seed"
limit = 1
answer_fields = ["Answer", "answer", "target"]

[output]
accepted_path = "{tmp_path / 'accepted.jsonl'}"
rejected_path = "{tmp_path / 'rejected.jsonl'}"

[generation]
provider = "gemini"
model = "{DEFAULT_MODEL}"
temperature = 0.2

[decision]
provider = "gemini"
model = "{DEFAULT_MODEL}"
temperature = 0.0

[iteration]
max_depth = {max_depth}
min_generated_units = 3
max_removable_span_length = {max_span}
stop_statuses = ["no_prune", "stop"]

[quality]
require_final_answer_preservation = false
reject_obvious_incoherence = true

[prompts]
generation_system = "Be clear."
generation_user_template = "Task: {{task_prompt}}{{answer_hint}}"
continuation_user_template = "Task: {{task_prompt}} Context: {{current_context}}{{answer_hint}}"
decision_system = "Return JSON."
decision_user_template = "Task: {{task_prompt}} Context: {{current_context}} Generation: {{generation}} Units: {{unit_lines}} Max: {{max_span_length}}"
'''.strip(),
        encoding="utf-8",
    )
    return path


def write_config_with_base_urls(tmp_path: Path) -> Path:
    path = write_config(tmp_path)
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        f'model = "{DEFAULT_MODEL}"\ntemperature = 0.2',
        f'model = "{DEFAULT_MODEL}"\nbase_url = "https://user:secret@example.test/v1?api_key=hidden"\ntemperature = 0.2',
        1,
    )
    text = text.replace(
        f'model = "{DEFAULT_MODEL}"\ntemperature = 0.0',
        f'model = "{DEFAULT_MODEL}"\nbase_url = "https://decision:secret@example.test/v1?token=hidden"\ntemperature = 0.0',
        1,
    )
    path.write_text(text, encoding="utf-8")
    return path


def write_config_with_hf_repo(tmp_path: Path, repo_id: str = "org/release-dataset") -> Path:
    path = write_config(tmp_path)
    text = path.read_text(encoding="utf-8")
    text = text.replace("[generation]", f'hf_upload_repo = "{repo_id}"\nhf_upload_path = "data/v0.1.0/train.jsonl"\nhf_private = true\n\n[generation]')
    path.write_text(text, encoding="utf-8")
    return path


def load_test_config(tmp_path: Path, **kwargs) -> pruning_flow.PruningConfig:
    return pruning_flow.load_pruning_config(write_config(tmp_path, **kwargs))


def test_config_loading_requires_prompt_placeholders(tmp_path):
    config = load_test_config(tmp_path)

    assert config.source.source == "seed"
    assert config.source.answer_fields == ("Answer", "answer", "target")
    assert config.output.accepted_path.endswith("accepted.jsonl")
    assert config.generation.model == DEFAULT_MODEL
    assert config.iteration.max_depth == 1

    bad_path = write_config(tmp_path)
    text = bad_path.read_text(encoding="utf-8").replace(" Units: {unit_lines}", "")
    bad_path.write_text(text, encoding="utf-8")

    try:
        pruning_flow.load_pruning_config(bad_path)
    except ValueError as exc:
        assert "{unit_lines}" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("bad config should fail")


def test_huggingface_and_transformers_providers_are_allowed():
    config = LLMConfig(provider="huggingface", model="huggingface/hf-inference/org/model")
    transformers_config = LLMConfig(provider="transformers", model="org/gemma4", model_revision="abc123", dtype="bfloat16", device_map="auto", top_p=0.95)

    assert config.provider == "huggingface"
    assert config.model == "huggingface/hf-inference/org/model"
    assert transformers_config.provider == "transformers"
    assert transformers_config.model_revision == "abc123"
    assert transformers_config.dtype == "bfloat16"
    assert transformers_config.device_map == "auto"
    assert transformers_config.top_p == 0.95


def test_transformers_generation_config_fields_parse(tmp_path):
    path = write_config(tmp_path)
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        f'provider = "gemini"\nmodel = "{DEFAULT_MODEL}"\ntemperature = 0.2',
        '\n'.join(
            [
                'provider = "transformers"',
                'model = "avreymi/reasoning-pruning-gemma-4-E2B-it"',
                'model_revision = "bd9b988310985cb4769a5039b580448bab2fb3ec"',
                'temperature = 0.2',
                'top_p = 0.95',
                'max_tokens = 1200',
                'dtype = "bfloat16"',
                'device_map = "auto"',
                'transformers_loader = "auto_model_for_image_text_to_text"',
            ]
        ),
        1,
    )
    path.write_text(text, encoding="utf-8")

    config = pruning_flow.load_pruning_config(path)

    assert config.generation.provider == "transformers"
    assert config.generation.model_revision == "bd9b988310985cb4769a5039b580448bab2fb3ec"
    assert config.generation.dtype == "bfloat16"
    assert config.generation.device_map == "auto"
    assert config.generation.top_p == 0.95
    assert config.generation.max_tokens == 1200


def test_transformers_provider_dispatches_to_backend_without_importing_transformers(monkeypatch):
    captured = {}

    def fake_transformers(prompt, config, *, system=None):
        captured.update({"prompt": prompt, "provider": config.provider, "system": system})
        return "generated"

    monkeypatch.setattr(llm_client, "_call_transformers", fake_transformers)

    text = llm_client.call_llm("hello", LLMConfig(provider="transformers", model="org/gemma4"), system="Be clear.")

    assert text == "generated"
    assert captured == {"prompt": "hello", "provider": "transformers", "system": "Be clear."}


def test_transformers_backend_uses_chat_template_and_generated_token_decode(monkeypatch):
    calls = {}

    class FakeTensor:
        shape = (1, 3)

        def to(self, device):
            calls["input_device"] = device
            return self

    class FakeProcessor:
        @classmethod
        def from_pretrained(cls, model, **kwargs):
            calls["processor_load"] = (model, kwargs)
            return cls()

        def apply_chat_template(self, messages, **kwargs):
            calls["template"] = (messages, kwargs)
            return {"input_ids": FakeTensor()}

        def decode(self, ids, **kwargs):
            calls["decode"] = (ids, kwargs)
            return "generated text"

    class FakeModel:
        device = "cuda:0"

        @classmethod
        def from_pretrained(cls, model, **kwargs):
            calls["model_load"] = (model, kwargs)
            return cls()

        def generate(self, **kwargs):
            calls["generate"] = kwargs
            return [[10, 11, 12, 99, 100]]

    class FakeInferenceMode:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    fake_torch = types.SimpleNamespace(
        bfloat16="bf16",
        float16="fp16",
        float32="fp32",
        inference_mode=lambda: FakeInferenceMode(),
    )
    fake_transformers = types.SimpleNamespace(
        AutoProcessor=FakeProcessor,
        AutoModelForImageTextToText=FakeModel,
        Gemma4ForConditionalGeneration=FakeModel,
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)
    monkeypatch.setenv("HF_TOKEN", "hf_test_token")

    config = LLMConfig(
        provider="transformers",
        model="org/gemma4",
        model_revision="rev1",
        dtype="bfloat16",
        device_map="auto",
        max_tokens=128,
        temperature=0.2,
        top_p=0.95,
    )

    backend = llm_client.TransformersChatBackend(config)
    text = backend.generate(llm_client._transformers_messages("prompt", "system"), max_new_tokens=128, temperature=0.2, top_p=0.95)

    assert text == "generated text"
    assert calls["processor_load"] == ("org/gemma4", {"revision": "rev1", "token": "hf_test_token"})
    assert calls["model_load"] == ("org/gemma4", {"revision": "rev1", "token": "hf_test_token", "dtype": "bf16", "device_map": "auto"})
    assert calls["template"][1] == {"add_generation_prompt": True, "tokenize": True, "return_dict": True, "return_tensors": "pt"}
    assert calls["input_device"] == "cuda:0"
    assert calls["generate"]["max_new_tokens"] == 128
    assert calls["generate"]["temperature"] == 0.2
    assert calls["generate"]["top_p"] == 0.95
    assert calls["decode"] == ([99, 100], {"skip_special_tokens": True})


def test_huggingface_endpoint_base_url_maps_to_litellm_api_base(monkeypatch):
    captured = {}

    class FakeMessage:
        content = "ok"

    class FakeChoice:
        message = FakeMessage()

    class FakeResponse:
        choices = [FakeChoice()]

    def fake_completion(**kwargs):
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setitem(sys.modules, "litellm", types.SimpleNamespace(completion=fake_completion))

    text = llm_client.call_llm(
        "hello",
        LLMConfig(provider="huggingface", model="huggingface/tgi", base_url="https://secret-endpoint.example"),
    )

    assert text == "ok"
    assert captured["model"] == "huggingface/tgi"
    assert captured["api_base"] == "https://secret-endpoint.example"
    assert "base_url" not in captured


def test_accepted_depth_1_record_has_training_schema(tmp_path):
    config = load_test_config(tmp_path)

    def fake_call(prompt: str, llm_config: LLMConfig, **kwargs: object) -> str:
        if kwargs.get("response_format"):
            return json.dumps({"status": "remove", "remove_unit_ids": ["u001"], "rationale": "redundant restatement"})
        return "Compute 3 plus 4. This repeats that we need addition. 3 plus 4 is 7. Final answer: 7."

    records, rejected = pruning_flow.run_pipeline([pruning_flow.Task("t1", "What is 3 plus 4?", metadata={"answer": "7"})], config, call_fn=fake_call)

    assert rejected == []
    assert len(records) == 1
    record = records[0]
    assert list(record.keys()) == ["id", "question", "input_x", "target_y", "depth", "decision"]
    assert record["id"] == "test-run/t1/1"
    assert record["question"] == "What is 3 plus 4?"
    assert record["depth"] == 1
    assert record["input_x"].endswith("Compute 3 plus 4.")
    assert record["target_y"] == "3 plus 4 is 7."
    assert record["decision"] == pruning_flow.decision_reference(config)
    assert record["decision"]["config"] == config.path
    assert record["decision"]["commit"].startswith("sha256:")


def validation_result(unit_ids: list[str], tmp_path: Path, *, max_span: int = 2) -> pruning_flow.SpanValidation:
    config = load_test_config(tmp_path, max_span=max_span)
    units = pruning_flow.split_units("A. B. C. D.")
    decision = pruning_flow.PruningDecision("remove", unit_ids, "test")
    return pruning_flow.validate_removable_span(units, decision, config)


def test_validation_rejects_non_contiguous_unknown_all_and_no_next(tmp_path):
    assert validation_result(["u000", "u002"], tmp_path).reason == "non_contiguous_span"
    assert validation_result(["u999"], tmp_path).reason == "unknown_unit_id"
    assert validation_result(["u000", "u001", "u002", "u003"], tmp_path, max_span=4).reason == "removes_all_units"
    assert validation_result(["u003"], tmp_path).reason == "no_next_kept_unit"
    assert validation_result(["u001", "u002", "u003"], tmp_path, max_span=2).reason == "span_too_long"


def test_iterative_depth_can_produce_depth_2(tmp_path):
    config = load_test_config(tmp_path, max_depth=2)
    decisions = iter([
        {"status": "remove", "remove_unit_ids": ["u001"], "rationale": "first redundant"},
        {"status": "remove", "remove_unit_ids": ["u001"], "rationale": "continuation setup redundant"},
    ])

    def fake_call(prompt: str, llm_config: LLMConfig, **kwargs: object) -> str:
        if kwargs.get("response_format"):
            return json.dumps(next(decisions))
        if "Context:" in prompt:
            return "We continue from seven. This setup is removable. Add one more to get 8. Final answer: 8."
        return "Start with three plus four. This is just framing. The sum is seven. Final answer: 7."

    records, rejected = pruning_flow.run_pipeline([pruning_flow.Task("t1", "What is 3 plus 4 then add 1?")], config, call_fn=fake_call)

    assert rejected == []
    assert [record["depth"] for record in records] == [1, 2]
    expected_pruned_context = "What is 3 plus 4 then add 1?\nStart with three plus four.\nThe sum is seven."
    assert records[1]["input_x"].startswith(expected_pruned_context)
    assert records[1]["target_y"] == "Add one more to get 8."


def test_stop_and_no_prune_do_not_create_accepted_output(tmp_path):
    config = load_test_config(tmp_path)

    for status in ["stop", "no_prune"]:
        local_config = replace(config, run_name=f"test-{status}")

        def fake_call(prompt: str, llm_config: LLMConfig, **kwargs: object) -> str:
            if kwargs.get("response_format"):
                return json.dumps({"status": status, "remove_unit_ids": [], "rationale": "done"})
            return "Step one. Step two. Final answer: 2."

        records, rejected = pruning_flow.run_pipeline([pruning_flow.Task("t1", "Task")], local_config, call_fn=fake_call)
        assert records == []
        assert rejected == []


def test_malformed_decision_goes_to_reject_audit_not_training(tmp_path):
    config = load_test_config(tmp_path)

    def fake_call(prompt: str, llm_config: LLMConfig, **kwargs: object) -> str:
        if kwargs.get("response_format"):
            return "not json"
        return "Step one. Step two. Final answer: 2."

    records, rejected = pruning_flow.run_pipeline([pruning_flow.Task("t1", "Task")], config, call_fn=fake_call)

    assert records == []
    assert len(rejected) == 1
    assert rejected[0]["reason"] == "decision_error:JSONDecodeError"


def test_hf_metadata_preserves_configured_small_answer_fields_only():
    row = {
        "question_concat": "How many?",
        "Answer": 42,
        "answer": "forty two",
        "target": "x" * 600,
        "large_payload": {"do": "not copy"},
    }

    metadata = pruning_flow.hf_task_metadata(row, "ChilleD/SVAMP", None, "train", 3, ("Answer", "answer", "target"))

    assert metadata == {
        "dataset": "ChilleD/SVAMP",
        "config": None,
        "split": "train",
        "row_index": 3,
        "Answer": 42,
        "answer": "forty two",
    }


def test_reject_audit_sanitizes_exception_messages(tmp_path):
    config = load_test_config(tmp_path)

    def fake_call(prompt: str, llm_config: LLMConfig, **kwargs: object) -> str:
        raise RuntimeError("failed with api_key=sk-live-secret and token: abcdef0123456789abcdef0123456789")

    records, rejected = pruning_flow.run_pipeline([pruning_flow.Task("t1", "Task")], config, call_fn=fake_call)

    assert records == []
    assert rejected[0]["reason"] == "generation_error:RuntimeError"
    assert rejected[0]["error_category"] == "RuntimeError"
    assert "sk-live-secret" not in rejected[0]["error_message"]
    assert "abcdef0123456789abcdef0123456789" not in rejected[0]["error_message"]
    assert "[REDACTED]" in rejected[0]["error_message"]


def test_final_answer_decimal_helpers_remain_stable():
    assert pruning_flow.final_answer("Final answer: 2.5.") == "2.5"
    assert pruning_flow.final_answer("Final answer: yes!") == "yes"


def test_hf_repo_config_does_not_upload_without_cli_release_flag(tmp_path, monkeypatch):
    config_path = write_config_with_hf_repo(tmp_path)
    called = {"upload": False}

    monkeypatch.setattr(create_pruning_dataset, "load_tasks", lambda source: [pruning_flow.Task("t1", "Task")])
    monkeypatch.setattr(create_pruning_dataset, "run_pipeline", lambda tasks, config: ([{"id": "accepted-1", "question": "Task", "input_x": "Task", "target_y": "Step", "depth": 1, "decision": pruning_flow.decision_reference(config)}], []))

    def fail_upload(*args, **kwargs):  # pragma: no cover - should never be called
        called["upload"] = True
        raise AssertionError("upload should be gated by --upload-to-hf")

    monkeypatch.setattr(create_pruning_dataset, "upload_jsonl_to_hf", fail_upload)

    written, rejected, uploaded_url, output_path, manifest_path = create_pruning_dataset.run_from_args(
        Namespace(config=str(config_path), output=None, limit=None, upload_to_hf=False)
    )

    assert written == 1
    assert rejected == 0
    assert uploaded_url is None
    assert called["upload"] is False
    assert Path(output_path).exists()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["hf_release"] == {"upload_requested": False, "uploaded": False, "url": None}
    assert manifest["counts"] == {"accepted": 1, "rejected": 0}
    assert manifest["accepted_row_schema"]["keys"] == ["id", "question", "input_x", "target_y", "depth", "decision"]
    assert manifest["decision_reference"] == pruning_flow.decision_reference(create_pruning_dataset.load_pruning_config(config_path))


def test_explicit_hf_upload_calls_helper_without_network(tmp_path, monkeypatch):
    config_path = write_config_with_hf_repo(tmp_path)
    calls = []

    monkeypatch.setattr(create_pruning_dataset, "load_tasks", lambda source: [pruning_flow.Task("t1", "Task")])
    monkeypatch.setattr(create_pruning_dataset, "run_pipeline", lambda tasks, config: ([{"id": "accepted-1", "question": "Task", "input_x": "Task", "target_y": "Step", "depth": 1, "decision": pruning_flow.decision_reference(config)}], [{"id": "rejected-1"}]))

    def fake_upload(output_path, repo_id, path_in_repo=None, *, private=False):
        calls.append((Path(output_path).name, repo_id, path_in_repo, private))
        return f"https://huggingface.co/datasets/{repo_id}/blob/main/{path_in_repo}"

    monkeypatch.setattr(create_pruning_dataset, "upload_jsonl_to_hf", fake_upload)

    written, rejected, uploaded_url, _output_path, manifest_path = create_pruning_dataset.run_from_args(
        Namespace(config=str(config_path), output=None, limit=None, upload_to_hf=True)
    )

    assert written == 1
    assert rejected == 1
    assert calls == [("accepted.jsonl", "org/release-dataset", "data/v0.1.0/train.jsonl", True)]
    assert uploaded_url == "https://huggingface.co/datasets/org/release-dataset/blob/main/data/v0.1.0/train.jsonl"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["hf_release"]["upload_requested"] is True
    assert manifest["hf_release"]["uploaded"] is True


def test_manifest_sanitizes_llm_base_urls(tmp_path):
    config = create_pruning_dataset.load_pruning_config(write_config_with_base_urls(tmp_path))

    manifest = create_pruning_dataset.build_manifest(
        config,
        accepted_count=1,
        rejected_count=0,
        upload_requested=False,
        uploaded_url=None,
    )
    manifest_json = json.dumps(manifest, sort_keys=True)

    assert "base_url" not in manifest["models"]["generation"]
    assert "base_url" not in manifest["models"]["decision"]
    assert manifest["models"]["generation"]["base_url_configured"] is True
    assert manifest["models"]["decision"]["base_url_configured"] is True
    assert "user:secret" not in manifest_json
    assert "decision:secret" not in manifest_json
    assert "api_key=hidden" not in manifest_json
    assert "token=hidden" not in manifest_json


def test_upload_to_hf_without_repo_fails_before_generation(tmp_path, monkeypatch):
    config_path = write_config(tmp_path)

    def fail_load_tasks(source):  # pragma: no cover - should fail before task loading
        raise AssertionError("missing repo should fail before generation work")

    monkeypatch.setattr(create_pruning_dataset, "load_tasks", fail_load_tasks)

    try:
        create_pruning_dataset.run_from_args(Namespace(config=str(config_path), output=None, limit=None, upload_to_hf=True))
    except ValueError as exc:
        assert "--upload-to-hf requires output.hf_upload_repo" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("missing upload repo should fail clearly")
