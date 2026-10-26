"""Diagram critic: the image plus the topic's checklist, never the generation prompt (spec § Diagram critic)."""

import base64

from app import openrouter
from app.schemas import Topic

MODEL = "openai/gpt-4o"
CRITIC_TIMEOUT_S = 30

SCHEMA_EXAMPLE = """{
  "parts": [{"name": "<required part name>", "status": "present", "note": "short note"}],
  "forbidden_found": ["<forbidden part name>"],
  "arrangement": [{"rule": "A1", "ok": true, "note": ""}],
  "text_issues": [{"label_text": "<text as drawn>", "problem": "misspelled"}],
  "people_present": false,
  "narrative": "Two to four sentences for a student."
}"""


def _quoted(names: list[str]) -> str:
    return ", ".join(f'"{n}"' for n in names) if names else "(none)"


def checklist_text(topic: Topic) -> str:
    rules = "\n".join(f"- {r.id}: {r.text}" for r in topic.arrangement_rules)
    return f"""You are checking a science diagram of {topic.with_article} for a school class. Judge only what is visible in the image.

Required parts. Report each one exactly once in "parts", using exactly these names: {_quoted(topic.required_parts)}.
status is "present" (drawn and labeled correctly), "missing", "mislabeled" (drawn, but the label points to the wrong thing), or "unclear".

Parts that must NOT appear. List any you can see in "forbidden_found", using these names: {_quoted(topic.forbidden_parts)}.

Arrangement rules. Report each one in "arrangement" by its id, with ok true or false:
{rules}

In "text_issues", list every label whose text is garbled, misspelled, or attached to the wrong part (problem: "garbled", "misspelled" or "wrong_part").
Set "people_present" to true if any person, face or hand appears anywhere in the image.
"narrative" is two to four sentences for a student, at most 80 words.

Return only one JSON object in this shape:
{SCHEMA_EXAMPLE}"""


async def critique(topic: Topic, png: bytes, *, retry_note: str | None = None, model: str = MODEL) -> str:
    """Return the critic's raw reply text. Parsing and validation happen in app.validator."""
    text = checklist_text(topic)
    if retry_note:
        text += f"\n\nYour previous reply was invalid: {retry_note}. Return only JSON in the shape above."

    image_url = "data:image/png;base64," + base64.b64encode(png).decode()
    body = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": text},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ],
    }
    result = await openrouter.chat(body, timeout=CRITIC_TIMEOUT_S, retry_5xx=True)
    return result.data["choices"][0]["message"].get("content") or ""
