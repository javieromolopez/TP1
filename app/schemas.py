"""Pydantic models and the topic-catalog loader (spec: Topic catalog)."""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ValidationError

TOPICS_PATH = Path(__file__).with_name("topics.json")


class TopicCatalogError(ValueError):
    """topics.json is invalid. The message names the failed rule and the topic id."""

    def __init__(self, rule: str, topic_id: str, detail: str):
        super().__init__(f"topics.json: topic '{topic_id}' failed rule '{rule}': {detail}")
        self.rule = rule
        self.topic_id = topic_id


class ArrangementRule(BaseModel):
    id: str
    text: str


class Topic(BaseModel):
    id: str
    display_name: str
    required_parts: list[str]
    forbidden_parts: list[str] = []
    arrangement_rules: list[ArrangementRule]
    labels: list[str]

    @property
    def with_article(self) -> str:
        """'a plant cell', 'an animal cell': for the prompts' English."""
        name = self.display_name.lower()
        return f"{'an' if name[0] in 'aeiou' else 'a'} {name}"


# Critique schema (spec § Critique schema). Fields a critic may reasonably omit have defaults (plan R7).

class Part(BaseModel):
    name: str
    status: Literal["present", "missing", "mislabeled", "unclear"]
    note: str = ""


class ArrangementResult(BaseModel):
    rule: str
    ok: bool
    note: str = ""


class TextIssue(BaseModel):
    label_text: str
    problem: Literal["garbled", "misspelled", "wrong_part"]


class Critique(BaseModel):
    parts: list[Part]
    forbidden_found: list[str] = []
    arrangement: list[ArrangementResult] = []
    text_issues: list[TextIssue] = []
    people_present: bool = False
    narrative: str


def _check_topic(topic: Topic) -> None:
    """Cross-field checks that type validation cannot catch (plan R6 b-e, plus review fixes)."""
    if not topic.required_parts:
        raise TopicCatalogError("nonempty_required_parts", topic.id, "required_parts is empty")

    rule_ids = [r.id for r in topic.arrangement_rules]
    duplicates = sorted({r for r in rule_ids if rule_ids.count(r) > 1})
    if duplicates:
        raise TopicCatalogError(
            "unique_arrangement_rule_ids", topic.id, f"duplicate rule ids {duplicates}"
        )

    overlap = sorted(set(topic.required_parts) & set(topic.forbidden_parts))
    if overlap:
        raise TopicCatalogError(
            "required_forbidden_disjoint", topic.id, f"{overlap} are both required and forbidden"
        )

    folded = [p.casefold() for p in topic.required_parts]
    if len(folded) != len(set(folded)):
        raise TopicCatalogError(
            "unique_required_parts", topic.id, "two required parts differ only in case"
        )

    if sorted(topic.labels) != sorted(topic.required_parts):
        raise TopicCatalogError(
            "labels_equal_parts", topic.id, "labels must be exactly the required parts"
        )


def load_style_block(path: Path = TOPICS_PATH) -> str:
    """The shared image-style text, with a {labels} placeholder (spec § Topic catalog)."""
    return json.loads(Path(path).read_text())["style_block"]


def load_topics(path: Path = TOPICS_PATH) -> dict[str, Topic]:
    """Load and validate the catalog, in file order. Raises TopicCatalogError on any bad entry."""
    raw = json.loads(Path(path).read_text())
    topics: dict[str, Topic] = {}
    for index, entry in enumerate(raw["topics"]):
        topic_id = entry.get("id", f"#{index}") if isinstance(entry, dict) else f"#{index}"
        try:
            topic = Topic.model_validate(entry)
        except ValidationError as exc:
            raise TopicCatalogError("schema", topic_id, str(exc)) from exc
        if topic.id in topics:
            raise TopicCatalogError("unique_topic_ids", topic.id, "id appears more than once")
        _check_topic(topic)
        topics[topic.id] = topic
    return topics
