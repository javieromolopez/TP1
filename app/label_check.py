"""Label text check: the critic transcribes the labels, the code compares them (spec § Label text check, behaviors 18-22).

The critic is never told which labels to expect and never asked whether a label is right,
so it cannot grade its own reading. Comparison goes through app.checker's build_report:
each expected label is an answer-key entry, so an expected label that was not read is an
un-answered row (missing) and a label read that the topic lacks is an invented row (unexpected).
"""

import base64
import re
from dataclasses import asdict, dataclass, field

from app import critic, openrouter
from app.checker import build_report, parse_critique
from app.schemas import Topic

LABEL_PROMPT = """List every text label in this image exactly as printed, character for character, including any misspellings.
Do not correct, translate or complete anything. Do not include the title.
Return only one JSON object: {"labels": ["<label as printed>", ...]}"""
UNAVAILABLE = "label read unavailable"
_EDGE_PUNCT = re.compile(r"^[^\w]+|[^\w]+$")


@dataclass(frozen=True)
class LabelCheck:
    ok: bool | None  # None when the label read failed: nothing could be compared
    missing: list[str] = field(default_factory=list)
    unexpected: list[str] = field(default_factory=list)
    read: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _norm(label: str) -> str:
    """Case, surrounding punctuation and repeated spaces only: "nucleeus" still differs from "nucleus"."""
    return _EDGE_PUNCT.sub("", " ".join(label.split())).casefold()


async def read_labels(png: bytes, *, model: str = critic.MODEL) -> str:
    """One narrow vision call. Returns the raw reply text; check_labels parses it."""
    body = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": LABEL_PROMPT},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(png).decode()}},
                ],
            }
        ],
    }
    result = await openrouter.chat(body, timeout=critic.CRITIC_TIMEOUT_S, retry_5xx=True)
    # A reply without choices is a failed read, not a KeyError (review on #18): "" fails check_labels.
    choices = result.data.get("choices") or [{}]
    return (choices[0].get("message") or {}).get("content") or ""


def check_labels(topic: Topic, raw: str) -> LabelCheck:
    parsed = parse_critique(raw)
    labels = None if parsed.failed else parsed.value.get("labels")
    if not isinstance(labels, list) or not all(isinstance(x, str) for x in labels):
        return LabelCheck(ok=None, error='the label read was not JSON with a "labels" list of strings')

    read = [x.strip() for x in labels if _norm(x)]
    answer_key = {_norm(label): True for label in topic.labels}
    report = build_report(answer_key, {_norm(x): True for x in read})
    unanswered = {row.part for row in report.rows if row.critiqued is None}
    missing = [label for label in topic.labels if _norm(label) in unanswered]
    unexpected = list(dict.fromkeys(x for x in read if _norm(x) not in answer_key))
    return LabelCheck(ok=report.is_ok, missing=missing, unexpected=unexpected, read=read)


async def label_check(topic: Topic, png: bytes) -> LabelCheck:
    """Read and check. A failed read never fails the request (behavior 22)."""
    try:
        raw = await read_labels(png)
    except (openrouter.OpenRouterTimeout, openrouter.OpenRouterError):
        return LabelCheck(ok=None, error=UNAVAILABLE)
    return check_labels(topic, raw)
