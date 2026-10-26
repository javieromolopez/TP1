"""Step 8 proof: the critic sends the image and checklist, never the generation prompt (spec behavior 5)."""

import asyncio
import json

import pytest

from app.critic import MODEL, checklist_text, critique
from app.prompt_builder import build_image_prompt
from app.schemas import load_style_block, load_topics
from tests.conftest import data_url, png_bytes, reply

TOPICS = load_topics()
PNG = png_bytes()


def run(topic, **kwargs):
    return asyncio.run(critique(topic, PNG, **kwargs))


def sent(fake_chat, index=0):
    body, kwargs = fake_chat.calls[index]
    (message,) = body["messages"]
    text_parts = [p["text"] for p in message["content"] if p["type"] == "text"]
    image_parts = [p for p in message["content"] if p["type"] == "image_url"]
    return body, kwargs, "\n".join(text_parts), image_parts


@pytest.mark.parametrize("topic_id", list(TOPICS))
def test_request_has_image_and_full_checklist(fake_chat, topic_id):
    topic = TOPICS[topic_id]
    fake_chat.replies = [reply({"content": "{}"})]
    run(topic)

    _, _, text, images = sent(fake_chat)
    assert [p["image_url"]["url"] for p in images] == [data_url(PNG)]
    for part in topic.required_parts + topic.forbidden_parts:
        assert f'"{part}"' in text, part
    for rule in topic.arrangement_rules:
        assert f"{rule.id}: {rule.text}" in text


@pytest.mark.parametrize("topic_id", list(TOPICS))
def test_request_never_contains_the_generation_prompt(fake_chat, topic_id):
    topic = TOPICS[topic_id]
    fake_chat.replies = [reply({"content": "{}"})]
    run(topic)

    body, _, text, _ = sent(fake_chat)
    whole_body = json.dumps(body, ensure_ascii=False)
    assert build_image_prompt(topic) not in whole_body
    template = load_style_block().replace("{labels}", ". ")
    for sentence in (s.strip() for s in template.split(". ")):
        if sentence:
            assert sentence not in text, sentence


def test_model_settings_timeout_and_retry(fake_chat):
    fake_chat.replies = [reply({"content": "{}"})]
    run(TOPICS["flower"])

    body, kwargs, _, _ = sent(fake_chat)
    assert body["model"] == MODEL == "openai/gpt-4o"
    assert body["temperature"] == 0
    assert body["response_format"] == {"type": "json_object"}
    assert kwargs == {"timeout": 30, "retry_5xx": True}


def test_retry_note_is_included(fake_chat):
    fake_chat.replies = [reply({"content": "{}"})]
    run(TOPICS["flower"], retry_note="parts missing from the reply: ['ovary']")

    _, _, text, _ = sent(fake_chat)
    assert "parts missing from the reply: ['ovary']" in text


def test_returns_the_raw_reply_text(fake_chat):
    fake_chat.replies = [reply({"content": '```json\n{"parts": []}\n```'})]
    assert run(TOPICS["flower"]) == '```json\n{"parts": []}\n```'


def test_empty_content_returns_empty_string(fake_chat):
    fake_chat.replies = [reply({"content": None})]
    assert run(TOPICS["flower"]) == ""


def test_checklist_uses_the_right_article():
    """Review: PR #3 caught "a animal cell"."""
    assert "diagram of an animal cell" in checklist_text(TOPICS["animal-cell"])
    assert "diagram of a flower" in checklist_text(TOPICS["flower"])
