"""Step 2 proof: the topic catalog loads, and a bad catalog stops the server (spec behavior 2)."""

import copy
import json
from pathlib import Path

import pytest

from app.schemas import TOPICS_PATH, TopicCatalogError, load_topics

EXPECTED_IDS = ["plant-cell", "animal-cell", "water-cycle", "simple-circuit", "flower"]


@pytest.fixture(scope="module")
def topics():
    return load_topics()


def test_load_topics_returns_five_ids(topics):
    assert list(topics) == EXPECTED_IDS


def test_topic_ids_unique(topics):
    ids = [t.id for t in topics.values()]
    assert len(ids) == len(set(ids))


def test_each_topic_has_nonempty_required_parts(topics):
    for topic in topics.values():
        assert topic.required_parts, topic.id


def test_arrangement_rule_ids_unique_per_topic(topics):
    for topic in topics.values():
        rule_ids = [r.id for r in topic.arrangement_rules]
        assert len(rule_ids) == len(set(rule_ids)), topic.id


def test_required_and_forbidden_disjoint(topics):
    for topic in topics.values():
        assert not set(topic.required_parts) & set(topic.forbidden_parts), topic.id


def test_label_strings_match_part_names(topics):
    for topic in topics.values():
        for label in topic.labels:
            assert label in topic.required_parts, f"{topic.id}: label {label!r}"


def _plant_cell(raw):
    return next(t for t in raw["topics"] if t["id"] == "plant-cell")


def _empty_required(raw):
    _plant_cell(raw)["required_parts"] = []


def _duplicate_rule_id(raw):
    rules = _plant_cell(raw)["arrangement_rules"]
    rules.append({"id": "A1", "text": "a second rule reusing the id A1"})


def _vacuole_forbidden(raw):
    _plant_cell(raw)["forbidden_parts"] = ["vacuole"]


def _missing_field(raw):
    del _plant_cell(raw)["display_name"]


def _wrong_type(raw):
    _plant_cell(raw)["required_parts"] = "nucleus"


@pytest.mark.parametrize(
    "mutate, rule",
    [
        (_empty_required, "nonempty_required_parts"),
        (_duplicate_rule_id, "unique_arrangement_rule_ids"),
        (_vacuole_forbidden, "required_forbidden_disjoint"),
        (_missing_field, "schema"),
        (_wrong_type, "schema"),
    ],
    ids=["empty-required", "duplicate-A1", "vacuole-forbidden", "missing-field", "wrong-type"],
)
def test_bad_topics_rejected_at_startup(tmp_path: Path, mutate, rule):
    raw = copy.deepcopy(json.loads(TOPICS_PATH.read_text()))
    mutate(raw)
    bad = tmp_path / "topics.json"
    bad.write_text(json.dumps(raw))

    with pytest.raises(TopicCatalogError) as err:
        load_topics(bad)

    message = str(err.value)
    assert rule in message
    assert "plant-cell" in message
