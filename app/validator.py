"""Turns the critic's reply into a Critique the UI can trust, with one retry (spec behaviors 6, 7)."""

import json
import re

from pydantic import ValidationError

from app import critic
from app.schemas import Critique, Topic

CRITIQUE_UNAVAILABLE = "Critique unavailable — try again."
MAX_NARRATIVE_WORDS = 80
FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


class CritiqueInvalid(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _json_object(raw: str) -> dict:
    fenced = FENCE.search(raw)
    text = fenced.group(1) if fenced else raw
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise CritiqueInvalid("not JSON: the reply has no {...} object")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise CritiqueInvalid(f"not JSON: {exc}") from exc


def validate(topic: Topic, raw_text: str) -> Critique:
    """Parse and check the reply against the topic. Raises CritiqueInvalid; never returns a partial critique."""
    try:
        critique = Critique.model_validate(_json_object(raw_text))
    except ValidationError as exc:
        problems = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        raise CritiqueInvalid(f"schema: {problems}") from exc

    # Part names: match case-insensitively, then use the catalog's spelling.
    canonical = {p.casefold(): p for p in topic.required_parts}
    unknown = [p.name for p in critique.parts if p.name.casefold() not in canonical]
    if unknown:
        raise CritiqueInvalid(f"unknown part names {unknown}; use only {topic.required_parts}")
    for part in critique.parts:
        part.name = canonical[part.name.casefold()]

    names = [p.name for p in critique.parts]
    repeated = sorted({n for n in names if names.count(n) > 1})
    if repeated:
        raise CritiqueInvalid(f"parts reported more than once: {repeated}")
    missing = [p for p in topic.required_parts if p not in names]
    if missing:
        raise CritiqueInvalid(f"parts missing from the reply: {missing}")

    # Every arrangement rule once, so a skipped rule cannot pass as "ok".
    expected_rules = [r.id for r in topic.arrangement_rules]
    reported_rules = [a.rule for a in critique.arrangement]
    if sorted(reported_rules) != sorted(expected_rules):
        raise CritiqueInvalid(f"arrangement must report each rule once: expected {expected_rules}, got {reported_rules}")

    words = len(critique.narrative.split())
    if words > MAX_NARRATIVE_WORDS:
        raise CritiqueInvalid(f"narrative is {words} words; the limit is {MAX_NARRATIVE_WORDS} words")
    return critique


async def critique_with_retry(topic: Topic, png: bytes) -> tuple[Critique | None, str | None]:
    """At most two critic calls. Returns (critique, None) or (None, CRITIQUE_UNAVAILABLE)."""
    raw = await critic.critique(topic, png)
    try:
        return validate(topic, raw), None
    except CritiqueInvalid as first:
        retry_note = first.reason

    raw = await critic.critique(topic, png, retry_note=retry_note)
    try:
        return validate(topic, raw), None
    except CritiqueInvalid:
        return None, CRITIQUE_UNAVAILABLE
