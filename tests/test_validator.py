"""Step 9 proof: the validator and its one retry (spec behaviors 6, 7)."""

import asyncio
import json

import pytest

from app import critic, validator
from app.schemas import load_topics
from app.validator import (
    CRITIQUE_UNAVAILABLE,
    CritiqueInvalid,
    critique_with_retry,
    validate,
)
from tests.conftest import png_bytes

CIRCUIT = load_topics()["simple-circuit"]  # battery, wire, switch, light bulb; rules A1-A3


def good_reply(**overrides) -> dict:
    data = {
        "parts": [{"name": p, "status": "present", "note": ""} for p in CIRCUIT.required_parts],
        "forbidden_found": [],
        "arrangement": [{"rule": r.id, "ok": True, "note": ""} for r in CIRCUIT.arrangement_rules],
        "text_issues": [],
        "people_present": False,
        "narrative": "The circuit is complete and every part is labeled.",
    }
    data.update(overrides)
    return data


GOOD = json.dumps(good_reply())


# Behavior 6: fences and prose around the JSON

def test_fenced_reply_parses_same_as_bare():
    assert validate(CIRCUIT, f"```json\n{GOOD}\n```") == validate(CIRCUIT, GOOD)


def test_json_inside_prose_parses():
    assert validate(CIRCUIT, f"Here is the critique: {GOOD} Hope this helps!") == validate(CIRCUIT, GOOD)


def test_part_names_match_case_insensitively_and_are_canonicalized():
    data = good_reply()
    data["parts"][3]["name"] = "Light Bulb"
    critique = validate(CIRCUIT, json.dumps(data))
    assert [p.name for p in critique.parts] == CIRCUIT.required_parts


# Behavior 7: every invalid shape raises

def parts_without(name):
    return [p for p in good_reply()["parts"] if p["name"] != name]


@pytest.mark.parametrize(
    "raw, reason",
    [
        ("Sorry, I cannot evaluate this image.", "not JSON"),
        ('{"parts": [', "not JSON"),
        (json.dumps(good_reply(parts=[{"name": "battery", "status": "great"}])), "schema"),
        (json.dumps(good_reply(narrative=None)), "schema"),
        (json.dumps(good_reply(parts=parts_without("switch"))), "missing"),
        (json.dumps(good_reply(parts=good_reply()["parts"] + [{"name": "resistor", "status": "present"}])), "unknown part"),
        (json.dumps(good_reply(parts=good_reply()["parts"] + [{"name": "wire", "status": "present"}])), "more than once"),
        (json.dumps(good_reply(arrangement=[{"rule": "A1", "ok": True}])), "arrangement"),
        (json.dumps(good_reply(narrative="word " * 81)), "80 words"),
    ],
    ids=["prose-refusal", "truncated", "bad-status", "null-narrative", "omitted-part",
         "invented-part", "duplicate-part", "missing-rules", "long-narrative"],
)
def test_invalid_replies_raise(raw, reason):
    with pytest.raises(CritiqueInvalid) as err:
        validate(CIRCUIT, raw)
    assert reason in err.value.reason


# Behavior 7: exactly one retry, with the error included

@pytest.fixture
def fake_critique(monkeypatch):
    calls = []
    replies = []

    async def fake(topic, png, *, retry_note=None):
        calls.append(retry_note)
        return replies.pop(0)

    monkeypatch.setattr(critic, "critique", fake)
    return calls, replies


def run_retry():
    return asyncio.run(critique_with_retry(CIRCUIT, png_bytes()))


def test_valid_first_reply_makes_one_call(fake_critique):
    calls, replies = fake_critique
    replies.extend([GOOD])
    critique, error = run_retry()
    assert calls == [None]
    assert error is None and critique.narrative.startswith("The circuit")


def test_one_retry_carries_the_first_error(fake_critique):
    calls, replies = fake_critique
    replies.extend([json.dumps(good_reply(parts=parts_without("switch"))), GOOD])
    critique, error = run_retry()

    assert len(calls) == 2
    assert calls[0] is None
    assert "switch" in calls[1]
    assert critique is not None and error is None


def test_second_failure_returns_no_critique(fake_critique):
    calls, replies = fake_critique
    replies.extend(["not json", "still not json", GOOD])
    critique, error = run_retry()

    assert len(calls) == 2
    assert critique is None
    assert error == CRITIQUE_UNAVAILABLE == "Critique unavailable — try again."


def test_validator_does_not_decide_the_verdict():
    """The verdict is computed by app.verdict in the API, not taken from anything the model says."""
    assert not hasattr(validator, "verdict")
