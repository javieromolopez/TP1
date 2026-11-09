"""No-key tests for the label text check (spec behaviors 19, 20): the critic transcribes, the code compares."""

import json

from app.label_check import check_labels
from app.schemas import load_topics

CELL = load_topics()["animal-cell"]


def read(*labels):
    return json.dumps({"labels": list(labels)})


def test_every_label_read_exactly_is_ok():
    result = check_labels(CELL, read(*CELL.labels))
    assert result.ok is True
    assert result.missing == [] and result.unexpected == [] and result.error is None
    assert result.read == CELL.labels


def test_case_surrounding_punctuation_and_spaces_are_ignored():
    shouted = [f"  {label.upper()}:  " for label in CELL.labels]
    assert check_labels(CELL, read(*shouted)).ok is True


def test_a_misspelled_label_is_missing_and_unexpected():
    labels = [("mitochondrin" if label == "mitochondrion" else label) for label in CELL.labels]
    result = check_labels(CELL, read(*labels))
    assert result.ok is False
    assert result.missing == ["mitochondrion"]
    assert result.unexpected == ["mitochondrin"]


def test_a_label_not_drawn_is_missing():
    result = check_labels(CELL, read(*CELL.labels[1:]))
    assert result.ok is False
    assert result.missing == [CELL.labels[0]]
    assert result.unexpected == []


def test_a_gibberish_label_is_unexpected_and_the_check_fails():
    result = check_labels(CELL, read(*CELL.labels, "Erimpeloom"))
    assert result.ok is False
    assert result.unexpected == ["Erimpeloom"]


def test_missing_labels_come_back_in_catalog_order():
    result = check_labels(CELL, read())
    assert result.missing == CELL.labels


def test_json_in_a_fence_is_read():
    assert check_labels(CELL, "```json\n" + read(*CELL.labels) + "\n```").ok is True


def test_a_reply_that_is_not_json_is_a_failed_check_not_a_crash():
    for raw in ["I see a cell.", "", '{"labels": "nucleus"}', '{"labels": [1, 2]}', '{"words": []}', "[]"]:
        result = check_labels(CELL, raw)
        assert result.ok is None
        assert result.error
        assert result.missing == [] and result.unexpected == []


def test_the_label_read_is_logged_to_runs_jsonl_like_every_model_call(monkeypatch):
    """Review on #18 asked for this proof: read_labels goes through openrouter.chat, which logs (behavior 14)."""
    import asyncio

    import httpx

    from app import openrouter
    from app.label_check import read_labels

    payload = {"choices": [{"message": {"content": read("nucleus")}}],
               "usage": {"prompt_tokens": 850, "completion_tokens": 12, "cost": 0.0029}}
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(openrouter, "TRANSPORT", httpx.MockTransport(lambda request: httpx.Response(200, json=payload)))
    assert asyncio.run(read_labels(b"png")) == read("nucleus")
    lines = [json.loads(line) for line in openrouter.RUNS_PATH.read_text().splitlines()]
    assert len(lines) == 1
    assert lines[0]["model"] == "openai/gpt-4o"
    assert lines[0]["cost"] == 0.0029
